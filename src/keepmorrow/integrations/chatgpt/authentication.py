"""Bounded RS256 access-token validation for a configured external issuer.

This is a resource-server verifier, not an authorization server. It never
discovers an issuer or key URL from an untrusted token and never issues tokens.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import math
import re
import time
from typing import Any
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
from mcp.server.auth.provider import AccessToken

_BASE64URL = re.compile(r"[A-Za-z0-9_-]+\Z")
JWKSFetcher = Callable[[], Awaitable[bytes]]


class AuthenticationConfigurationError(ValueError):
    """The operator's resource-server configuration is unsupported."""


def _https_url(value: object, *, issuer: bool = False) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 2048 or any(ord(char) <= 32 for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == "https" and parsed.hostname and parsed.port != 0
            and parsed.username is None and parsed.password is None and not parsed.fragment
            and (not issuer or not parsed.query)
        )
    except ValueError:
        return False


def _text(value: object, maximum: int) -> bool:
    return bool(
        isinstance(value, str) and 1 <= len(value) <= maximum and value.strip() == value
        and all(32 <= ord(char) < 127 for char in value)
    )


def _scope(value: object) -> bool:
    return _text(value, 128) and " " not in value and '"' not in value and "\\" not in value


@dataclass(frozen=True, slots=True)
class AuthenticationConfig:
    """An immutable, operator-reviewed external issuer and bounded JWT profile.

    This pilot supports RS256 and standard space-separated `scope` claims.
    Provider-specific profiles require explicit review; JWT is not accepted as
    a token type by default because it also commonly labels identity tokens.
    """

    issuer: str
    audience: str
    jwks_uri: str
    required_scopes: tuple[str, ...] = ("keepmorrow:access",)
    accepted_token_types: tuple[str, ...] = ("at+jwt", "application/at+jwt")
    jwks_ttl_seconds: int = 300
    refresh_cooldown_seconds: int = 10
    jwks_timeout_seconds: int = 5
    max_token_bytes: int = 16_384
    max_jwks_bytes: int = 262_144
    max_token_lifetime_seconds: int = 3600
    clock_skew_seconds: int = 0

    def __post_init__(self) -> None:
        valid = (
            _https_url(self.issuer, issuer=True) and _https_url(self.audience)
            and _https_url(self.jwks_uri)
            and isinstance(self.required_scopes, tuple) and 1 <= len(self.required_scopes) <= 32
            and all(_scope(value) for value in self.required_scopes)
            and len(set(self.required_scopes)) == len(self.required_scopes)
            and isinstance(self.accepted_token_types, tuple) and 1 <= len(self.accepted_token_types) <= 3
            and all(value in ("at+jwt", "application/at+jwt", "JWT") for value in self.accepted_token_types)
            and len(set(self.accepted_token_types)) == len(self.accepted_token_types)
        )
        bounds = (
            (self.jwks_ttl_seconds, 1, 3600), (self.refresh_cooldown_seconds, 1, 300),
            (self.jwks_timeout_seconds, 1, 30), (self.max_token_bytes, 1024, 65_536),
            (self.max_jwks_bytes, 1024, 1_048_576), (self.max_token_lifetime_seconds, 60, 86_400),
            (self.clock_skew_seconds, 0, 60),
        )
        if not valid or any(type(value) is not int or not lower <= value <= upper for value, lower, upper in bounds):
            raise AuthenticationConfigurationError("Invalid external authentication configuration.")
        if self.refresh_cooldown_seconds > self.jwks_ttl_seconds:
            raise AuthenticationConfigurationError("The key-refresh cooldown cannot exceed the cache lifetime.")


def _json_object(data: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate authentication metadata field.")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError("Unsupported authentication metadata number.")

    result = json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("Authentication metadata requires an object.")
    return result


def _decode_segment(value: object, maximum: int) -> bytes:
    if (not isinstance(value, str) or len(value) > ((maximum + 2) // 3) * 4
            or _BASE64URL.fullmatch(value) is None):
        raise ValueError("Unsupported authentication encoding.")
    result = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if len(result) > maximum or base64.urlsafe_b64encode(result).rstrip(b"=").decode("ascii") != value:
        raise ValueError("Unsupported authentication encoding.")
    return result


class ConfiguredTokenVerifier:
    """Implement MCP TokenVerifier with a bounded asynchronous JWKS cache.

    One refresh runs at a time. Unknown key IDs and invalid signatures can cause
    at most one refresh per cooldown interval, rather than one request per
    attacker-selected key ID. Expired caches are never used after refresh failure.
    Successful cache entries remain usable only until their configured TTL.

    fetch_jwks, when injected, is trusted server code returning bounded bytes
    from the configured provider. It is primarily a synthetic-test seam. The
    default fetch uses HTTPS, no redirects, no cookies, no ambient proxy settings,
    bounded uncompressed response bytes, and a total timeout.
    """

    def __init__(
        self,
        config: AuthenticationConfig,
        *,
        fetch_jwks: JWKSFetcher | None = None,
        clock: Callable[[], int] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if (not isinstance(config, AuthenticationConfig) or not callable(monotonic)
                or (clock is not None and not callable(clock))
                or (fetch_jwks is not None and not callable(fetch_jwks))):
            raise AuthenticationConfigurationError("Invalid external authentication verifier configuration.")
        self.config = config
        self._fetch_jwks = fetch_jwks or self._fetch_configured_jwks
        self._clock = clock or (lambda: int(time.time()))
        self._monotonic = monotonic
        self._keys: dict[str, rsa.RSAPublicKey] = {}
        self._cache_expires_at = 0.0
        self._last_refresh_attempt: float | None = None
        self._refresh_lock = asyncio.Lock()

    async def _fetch_configured_jwks(self) -> bytes:
        async with httpx.AsyncClient(
            follow_redirects=False, trust_env=False,
            timeout=httpx.Timeout(self.config.jwks_timeout_seconds),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
        ) as client:
            async with client.stream(
                "GET", self.config.jwks_uri,
                headers={"Accept": "application/jwk-set+json, application/json", "Accept-Encoding": "identity"},
            ) as response:
                if response.status_code != 200 or response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise ValueError("The configured key endpoint returned an unsupported response.")
                length = response.headers.get("content-length")
                if length is not None and (not length.isascii() or not length.isdigit() or not 0 <= int(length) <= self.config.max_jwks_bytes):
                    raise ValueError("The configured key response exceeds its size limit.")
                chunks = bytearray()
                async for chunk in response.aiter_raw(chunk_size=16_384):
                    if len(chunks) + len(chunk) > self.config.max_jwks_bytes:
                        raise ValueError("The configured key response exceeds its size limit.")
                    chunks.extend(chunk)
                return bytes(chunks)

    def _parse_keys(self, data: bytes) -> dict[str, rsa.RSAPublicKey]:
        if not isinstance(data, bytes) or not 1 <= len(data) <= self.config.max_jwks_bytes:
            raise ValueError("The configured key response is unsupported.")
        document = _json_object(data)
        entries = document.get("keys")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
            raise ValueError("The configured key inventory is unsupported.")
        seen: set[str] = set()
        result: dict[str, rsa.RSAPublicKey] = {}
        for entry in entries:
            if not isinstance(entry, dict) or not _text(entry.get("kid"), 128):
                raise ValueError("The configured key inventory is malformed.")
            identifier = entry["kid"]
            if identifier in seen:
                raise ValueError("The configured key inventory has ambiguous identifiers.")
            seen.add(identifier)
            if entry.get("kty") != "RSA" or entry.get("alg", "RS256") != "RS256" or entry.get("use", "sig") != "sig":
                continue
            if "key_ops" in entry and entry["key_ops"] != ["verify"]:
                continue
            if any(name in entry for name in ("d", "p", "q", "dp", "dq", "qi", "oth")):
                raise ValueError("The configured endpoint must expose public keys only.")
            modulus_bytes = _decode_segment(entry.get("n"), 512)
            exponent_bytes = _decode_segment(entry.get("e"), 4)
            if (len(modulus_bytes) < 256 or not modulus_bytes[0]
                    or int.from_bytes(exponent_bytes, "big") != 65537):
                raise ValueError("The configured RSA key parameters are unsupported.")
            key = rsa.RSAPublicNumbers(65537, int.from_bytes(modulus_bytes, "big")).public_key()
            if not 2048 <= key.key_size <= 4096:
                raise ValueError("The configured RSA key size is unsupported.")
            result[identifier] = key
        if not result:
            raise ValueError("The configured endpoint has no supported signing key.")
        return result

    async def _key(self, identifier: str, *, refresh: bool = False) -> rsa.RSAPublicKey | None:
        now = self._monotonic()
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            return None
        if not refresh and now < self._cache_expires_at and identifier in self._keys:
            return self._keys[identifier]
        async with self._refresh_lock:
            now = self._monotonic()
            if not refresh and now < self._cache_expires_at and identifier in self._keys:
                return self._keys[identifier]
            if self._last_refresh_attempt is not None and now - self._last_refresh_attempt < self.config.refresh_cooldown_seconds:
                return None
            self._last_refresh_attempt = now
            try:
                async with asyncio.timeout(self.config.jwks_timeout_seconds):
                    keys = self._parse_keys(await self._fetch_jwks())
            except (httpx.HTTPError, OSError, TimeoutError, ValueError, TypeError, RecursionError):
                return None
            self._keys = keys
            self._cache_expires_at = self._monotonic() + self.config.jwks_ttl_seconds
            return keys.get(identifier)

    def _validate_claim_shape(self, claims: dict[str, Any]) -> tuple[str, list[str]]:
        if claims.get("iss") != self.config.issuer or not _text(claims.get("sub"), 255):
            raise ValueError("The access-token identity is unsupported.")
        audience = claims.get("aud")
        audiences = [audience] if isinstance(audience, str) else audience
        if (not isinstance(audiences, list) or not 1 <= len(audiences) <= 8
                or any(not _text(value, 2048) for value in audiences)
                or len(set(audiences)) != len(audiences) or self.config.audience not in audiences):
            raise ValueError("The access-token audience is unsupported.")
        for name in ("iat", "exp"):
            if type(claims.get(name)) is not int or not 0 <= claims[name] <= 253402300799:
                raise ValueError("The access-token lifetime is unsupported.")
        if "nbf" in claims and (type(claims["nbf"]) is not int or not 0 <= claims["nbf"] <= claims["exp"]):
            raise ValueError("The access-token lifetime is unsupported.")
        if not 0 < claims["exp"] - claims["iat"] <= self.config.max_token_lifetime_seconds:
            raise ValueError("The access-token lifetime is unsupported.")
        if claims.get("gty") == "client-credentials" or claims.get("gty") == "client_credentials" or claims.get("grant_type") == "client_credentials":
            raise ValueError("A service-client grant cannot establish this user principal.")
        client_id, authorized_party = claims.get("client_id"), claims.get("azp")
        if client_id is not None and not _text(client_id, 255):
            raise ValueError("The access-token client is unsupported.")
        if authorized_party is not None and not _text(authorized_party, 255):
            raise ValueError("The access-token client is unsupported.")
        if client_id is not None and authorized_party is not None and client_id != authorized_party:
            raise ValueError("The access-token client is ambiguous.")
        selected_client = client_id if client_id is not None else authorized_party
        if selected_client is None or selected_client == claims["sub"]:
            raise ValueError("The access token requires a distinct user subject and client.")
        scope = claims.get("scope")
        if not isinstance(scope, str) or len(scope) > 4096:
            raise ValueError("The access-token scope is unsupported.")
        scopes = scope.split(" ")
        if (not 1 <= len(scopes) <= 32 or any(not _scope(value) for value in scopes)
                or len(set(scopes)) != len(scopes) or not set(self.config.required_scopes) <= set(scopes)):
            raise ValueError("The access-token scope is unsupported.")
        return selected_client, scopes

    def _validate_current_time(self, claims: dict[str, Any]) -> None:
        now = self._clock()
        if type(now) is not int or not 0 <= now <= 253402300799:
            raise ValueError("The authentication clock is unavailable.")
        skew = self.config.clock_skew_seconds
        if (claims["exp"] <= now - skew or claims["iat"] > now + skew
                or claims.get("nbf", claims["iat"]) > now + skew):
            raise ValueError("The access token is not currently valid.")

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return a verified SDK token or one indistinguishable invalid outcome.

        No token, claim body, key bytes, network URL, or verification exception is
        logged here. The returned credential is request-local and must not enter
        the operation or consent journal. Request cancellation propagates.
        """
        try:
            if not isinstance(token, str) or not token.isascii() or not 1 <= len(token) <= self.config.max_token_bytes:
                return None
            segments = token.split(".")
            if len(segments) != 3:
                return None
            header = _json_object(_decode_segment(segments[0], 2048))
            claims = _json_object(_decode_segment(segments[1], self.config.max_token_bytes))
            _decode_segment(segments[2], 512)
            if (header.get("alg") != "RS256" or header.get("typ") not in self.config.accepted_token_types
                    or not _text(header.get("kid"), 128) or "crit" in header
                    or "b64" in header or "jku" in header or "x5u" in header or "jwk" in header):
                return None
            client_id, scopes = self._validate_claim_shape(claims)
            self._validate_current_time(claims)
            key = await self._key(header["kid"])
            if key is None:
                return None
            options = {
                "require": ["iss", "aud", "sub", "exp", "iat"],
                "verify_exp": False, "verify_iat": False, "verify_nbf": False,
                "enforce_minimum_key_length": True,
            }
            try:
                verified = jwt.decode(token, key, algorithms=["RS256"], issuer=self.config.issuer, audience=self.config.audience, options=options)
            except jwt.InvalidSignatureError:
                key = await self._key(header["kid"], refresh=True)
                if key is None:
                    return None
                verified = jwt.decode(token, key, algorithms=["RS256"], issuer=self.config.issuer, audience=self.config.audience, options=options)
            # The injected UTC clock is authoritative for lifetime checks. Check
            # again after network/key work so a token cannot expire while waiting.
            self._validate_current_time(verified)
            return AccessToken(
                token=token, client_id=client_id, scopes=scopes, expires_at=verified["exp"],
                resource=self.config.audience, subject=verified["sub"], claims={"iss": self.config.issuer},
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
            return None
