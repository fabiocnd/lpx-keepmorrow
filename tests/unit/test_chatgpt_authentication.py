"""Synthetic issuer tests for bounded, resource-specific access-token verification."""

import asyncio
import base64
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

try:
    from cryptography.hazmat.primitives.asymmetric import rsa
    import httpx
    import jwt
    from keepmorrow.integrations.chatgpt.authentication import (
        AuthenticationConfig, AuthenticationConfigurationError, ConfiguredTokenVerifier,
    )
except ImportError:
    OPTIONAL_AUTH_AVAILABLE = False
else:
    OPTIONAL_AUTH_AVAILABLE = True


@unittest.skipUnless(OPTIONAL_AUTH_AVAILABLE, "Install the optional ChatGPT dependencies to test token verification.")
class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.rotated_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    async def asyncSetUp(self) -> None:
        self.now = 1_800_000_000
        self.ticks = 1000.0
        self.config = AuthenticationConfig(
            issuer="https://identity.example.test", audience="https://keepmorrow.example.test/mcp",
            jwks_uri="https://identity.example.test/keys",
        )
        self.calls = 0
        self.failure = None
        self.response = self.jwks(self.private_key, "primary")

        async def fetch():
            self.calls += 1
            await asyncio.sleep(0)
            if self.failure is not None:
                raise self.failure
            return self.response

        self.fetch = fetch
        self.verifier = ConfiguredTokenVerifier(
            self.config, fetch_jwks=fetch, clock=lambda: self.now, monotonic=lambda: self.ticks,
        )

    @staticmethod
    def jwks(key, identifier):
        public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        public.update(kid=identifier, alg="RS256", use="sig", key_ops=["verify"])
        return json.dumps({"keys": [public]}).encode()

    def claims(self, **changes):
        claims = dict(
            iss=self.config.issuer, aud=self.config.audience, sub="synthetic-owner",
            client_id="synthetic-client", iat=self.now, exp=self.now + 600,
            scope="keepmorrow:access", email="must-not-escape@example.test",
        )
        claims.update(changes)
        return claims

    def token(self, *, claims=None, key=None, **headers):
        return jwt.encode(
            self.claims() if claims is None else claims, key or self.private_key,
            algorithm="RS256", headers={"kid": "primary", "typ": "at+jwt", **headers},
        )

    async def test_valid_access_token_returns_only_needed_verified_claims(self) -> None:
        token = self.token()
        verified = await self.verifier.verify_token(token)
        self.assertIsNotNone(verified)
        self.assertEqual(verified.subject, "synthetic-owner")
        self.assertEqual(verified.client_id, "synthetic-client")
        self.assertEqual(verified.resource, self.config.audience)
        self.assertEqual(verified.claims, {"iss": self.config.issuer})
        self.assertEqual(verified.scopes, ["keepmorrow:access"])
        self.assertEqual(verified.expires_at, self.now + 600)
        self.assertEqual(self.calls, 1)
        self.assertIsNotNone(await self.verifier.verify_token(token))
        self.assertEqual(self.calls, 1)

    async def test_wrong_identity_audience_or_scope_fail_before_key_fetch(self) -> None:
        invalid = (
            {"iss": "https://attacker.example.test"}, {"aud": "https://other.example.test/mcp"},
            {"sub": ""}, {"scope": "unrelated:scope"}, {"scope": "keepmorrow:access keepmorrow:access"},
            {"scope": ["keepmorrow:access"]}, {"aud": [self.config.audience, self.config.audience]},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assertIsNone(await self.verifier.verify_token(self.token(claims=self.claims(**changes))))
        self.assertEqual(self.calls, 0)

    async def test_required_claims_cannot_be_missing_or_coerced(self) -> None:
        for name in ("iss", "aud", "sub", "exp", "iat", "scope", "client_id"):
            claims = self.claims()
            del claims[name]
            with self.subTest(missing=name):
                self.assertIsNone(await self.verifier.verify_token(self.token(claims=claims)))
        for changes in ({"exp": True}, {"iat": str(self.now)}, {"nbf": 1.5}, {"exp": self.now + 100_000}, {"iat": self.now + 1000}):
            with self.subTest(changes=changes):
                self.assertIsNone(await self.verifier.verify_token(self.token(claims=self.claims(**changes))))
        self.assertEqual(self.calls, 0)

    async def test_expiry_not_before_and_issue_time_use_injected_current_time(self) -> None:
        token = self.token(claims=self.claims(nbf=self.now + 1))
        self.assertIsNone(await self.verifier.verify_token(token))
        self.now += 1
        self.assertIsNotNone(await self.verifier.verify_token(token))
        self.now += 599
        self.assertIsNone(await self.verifier.verify_token(token))

    async def test_token_expiring_during_key_fetch_is_rejected_after_fetch(self) -> None:
        token = self.token(claims=self.claims(exp=self.now + 1))

        async def fetch():
            self.now += 1
            return self.response

        verifier = ConfiguredTokenVerifier(self.config, fetch_jwks=fetch, clock=lambda: self.now)
        self.assertIsNone(await verifier.verify_token(token))

    async def test_machine_grants_and_ambiguous_client_identity_are_rejected(self) -> None:
        for changes in (
            {"gty": "client_credentials"}, {"gty": "client-credentials"}, {"grant_type": "client_credentials"},
            {"sub": "synthetic-client"}, {"azp": "different-client"}, {"client_id": ""},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(await self.verifier.verify_token(self.token(claims=self.claims(**changes))))
        claims = self.claims(azp="synthetic-client")
        del claims["client_id"]
        verified = await self.verifier.verify_token(self.token(claims=claims))
        self.assertEqual(verified.client_id, "synthetic-client")

    async def test_unapproved_algorithm_token_type_and_token_selected_key_urls_are_rejected(self) -> None:
        for headers in (
            {"typ": "JWT"}, {"typ": "id+jwt"}, {"kid": ""},
            {"jku": "https://attacker.example.test/keys"}, {"x5u": "https://attacker.example.test/key"},
            {"jwk": {"kty": "RSA"}}, {"crit": ["custom"]},
        ):
            with self.subTest(headers=headers):
                self.assertIsNone(await self.verifier.verify_token(self.token(**headers)))
        hmac = jwt.encode(self.claims(), b"x" * 32, algorithm="HS256", headers={"kid": "primary", "typ": "at+jwt"})
        self.assertIsNone(await self.verifier.verify_token(hmac))
        self.assertEqual(self.calls, 0)

    async def test_legacy_jwt_type_requires_explicit_operator_configuration(self) -> None:
        config = replace(self.config, accepted_token_types=("JWT",))
        verifier = ConfiguredTokenVerifier(config, fetch_jwks=self.fetch, clock=lambda: self.now)
        self.assertIsNotNone(await verifier.verify_token(self.token(typ="JWT")))

    async def test_forged_signature_never_authenticates_and_refreshes_are_rate_bounded(self) -> None:
        self.assertIsNotNone(await self.verifier.verify_token(self.token()))
        forged = self.token(key=self.rotated_key)
        for _ in range(10):
            self.assertIsNone(await self.verifier.verify_token(forged))
        self.assertEqual(self.calls, 1)
        self.ticks += self.config.refresh_cooldown_seconds
        self.assertIsNone(await self.verifier.verify_token(forged))
        self.assertEqual(self.calls, 2)
        self.assertIsNotNone(await self.verifier.verify_token(self.token()))

    async def test_unknown_keys_share_one_refresh_and_rotation_can_be_observed(self) -> None:
        self.assertIsNotNone(await self.verifier.verify_token(self.token()))
        self.response = self.jwks(self.rotated_key, "rotated")
        rotated = self.token(key=self.rotated_key, kid="rotated")
        self.assertIsNone(await self.verifier.verify_token(rotated))
        self.assertEqual(self.calls, 1)
        self.ticks += self.config.refresh_cooldown_seconds
        results = await asyncio.gather(*(self.verifier.verify_token(rotated) for _ in range(20)))
        self.assertTrue(all(result is not None for result in results))
        self.assertEqual(self.calls, 2)
        self.assertIsNone(await self.verifier.verify_token(self.token()))

    async def test_rotation_reusing_a_key_id_retries_signature_once_after_cooldown(self) -> None:
        self.assertIsNotNone(await self.verifier.verify_token(self.token()))
        self.response = self.jwks(self.rotated_key, "primary")
        self.ticks += self.config.refresh_cooldown_seconds
        rotated = await self.verifier.verify_token(self.token(key=self.rotated_key))
        self.assertIsNotNone(rotated)
        self.assertEqual(self.calls, 2)

    async def test_expired_cache_is_not_used_when_the_provider_is_unavailable(self) -> None:
        token = self.token()
        self.assertIsNotNone(await self.verifier.verify_token(token))
        self.ticks += self.config.jwks_ttl_seconds
        self.failure = OSError("synthetic provider failure containing private diagnostic detail")
        self.assertIsNone(await self.verifier.verify_token(token))
        self.assertIsNone(await self.verifier.verify_token(token))
        self.assertEqual(self.calls, 2)

    async def test_key_inventory_size_duplicates_private_keys_and_weak_keys_fail_closed(self) -> None:
        valid = json.loads(self.response)
        weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        private = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key))
        private.update(kid="primary", alg="RS256")
        invalid = (
            b"x" * (self.config.max_jwks_bytes + 1), b'{"keys": [], "keys": []}',
            json.dumps({"keys": [valid["keys"][0], valid["keys"][0]]}).encode(),
            json.dumps({"keys": [private]}).encode(), self.jwks(weak, "primary"),
            json.dumps({"keys": valid["keys"] * 33}).encode(),
        )
        for response in invalid:
            with self.subTest(length=len(response)):
                self.response = response
                verifier = ConfiguredTokenVerifier(self.config, fetch_jwks=self.fetch, clock=lambda: self.now)
                self.assertIsNone(await verifier.verify_token(self.token()))

    async def test_oversized_malformed_and_duplicate_claim_tokens_fail_without_fetch(self) -> None:
        for token in (None, "", "a.b", "a.b.c.d", "x" * (self.config.max_token_bytes + 1), "☃.payload.signature"):
            with self.subTest(token_type=type(token).__name__):
                self.assertIsNone(await self.verifier.verify_token(token))
        original = self.token().split(".")
        for segment, value in ((0, b'{"alg":"RS256","alg":"RS256"}'), (1, b'{"sub":"a","sub":"b"}')):
            modified = list(original)
            modified[segment] = base64.urlsafe_b64encode(value).rstrip(b"=").decode()
            self.assertIsNone(await self.verifier.verify_token(".".join(modified)))
        self.assertEqual(self.calls, 0)

    async def test_cancellation_propagates_instead_of_becoming_an_authentication_result(self) -> None:
        entered = asyncio.Event()

        async def fetch():
            entered.set()
            await asyncio.Future()

        verifier = ConfiguredTokenVerifier(self.config, fetch_jwks=fetch, clock=lambda: self.now)
        task = asyncio.create_task(verifier.verify_token(self.token()))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_default_fetch_rejects_redirects_compressed_or_oversized_responses(self) -> None:
        real_client = httpx.AsyncClient

        class RawBytes(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield self.body

            def __init__(self, body):
                self.body = body

        for status, headers, body in (
            (302, {"location": "https://attacker.example.test"}, b""),
            (200, {"content-encoding": "gzip"}, b"compressed"),
            (200, {"content-length": str(self.config.max_jwks_bytes + 1)}, b"{}"),
            (200, {}, b"x" * (self.config.max_jwks_bytes + 1)),
        ):
            observed = []

            def handler(request):
                observed.append(str(request.url))
                self.assertNotIn("authorization", request.headers)
                self.assertNotIn("cookie", request.headers)
                return httpx.Response(status, headers=headers, stream=RawBytes(body))

            def client(**options):
                self.assertFalse(options["follow_redirects"])
                self.assertFalse(options["trust_env"])
                return real_client(transport=httpx.MockTransport(handler), **options)

            verifier = ConfiguredTokenVerifier(self.config, clock=lambda: self.now)
            with self.subTest(status=status, headers=headers), patch(
                "keepmorrow.integrations.chatgpt.authentication.httpx.AsyncClient", side_effect=client
            ):
                self.assertIsNone(await verifier.verify_token(self.token()))
            self.assertEqual(observed, [self.config.jwks_uri])

    def test_operator_configuration_rejects_unsafe_urls_and_unbounded_limits(self) -> None:
        for changes in (
            {"issuer": "http://identity.example.test"}, {"jwks_uri": "file:///tmp/keys"},
            {"audience": "https://user:password@resource.example.test"},
            {"issuer": "https://identity.example.test#fragment"}, {"max_token_bytes": True},
            {"required_scopes": ()}, {"accepted_token_types": ("none",)},
            {"jwks_ttl_seconds": 1, "refresh_cooldown_seconds": 2},
        ):
            with self.subTest(changes=changes), self.assertRaises(AuthenticationConfigurationError):
                replace(self.config, **changes)


if __name__ == "__main__":
    unittest.main()
