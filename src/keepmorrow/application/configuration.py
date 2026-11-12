"""Operator-owned configuration, separate from every model-supplied argument.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from ..access.models import PolicySet, Principal, validate_token
from ..archive.filesystem import open_regular, safe_directory
from ..consent import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
OPERATION_RESERVATION_BYTES = 2 * 1024**3


class ConfigurationError(ValueError):
    """A fixed configuration failure without a credential or filesystem path."""


def https_url(value: object, *, origin_only: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ConfigurationError("A bounded HTTPS URL is required.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ConfigurationError("The configured endpoint must be a plain HTTPS URL.") from error
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or port == 0 or parsed.query or parsed.fragment or any(ord(char) < 33 for char in value)
            or (origin_only and parsed.path not in ("", "/"))):
        raise ConfigurationError("The configured endpoint must be a plain HTTPS URL.")
    return value.rstrip("/") if origin_only else value


@dataclass(frozen=True, slots=True)
class Resource:
    resource_id: str
    generation: str
    principal_id: str
    path: Path
    kind: str = "collection"

    def __post_init__(self) -> None:
        validate_token(self.resource_id)
        validate_token(self.principal_id)
        if not isinstance(self.generation, str) or _DIGEST.fullmatch(self.generation) is None:
            raise ConfigurationError("A collection generation must be its exact manifest SHA-256.")
        if not isinstance(self.path, Path) or not self.path.is_absolute() or self.kind not in {"collection", "package"}:
            raise ConfigurationError("Resource storage must be an operator-selected absolute path.")


@dataclass(frozen=True, slots=True)
class BrowserOAuth:
    client_id: str
    authorization_endpoint: str
    token_endpoint: str
    client_secret_env: str | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.client_id, str) or not 1 <= len(self.client_id) <= 255
                or any(ord(char) < 32 for char in self.client_id)):
            raise ConfigurationError("A registered browser OAuth client is required.")
        https_url(self.authorization_endpoint)
        https_url(self.token_endpoint)
        if self.client_secret_env is not None and (
            not isinstance(self.client_secret_env, str)
            or re.fullmatch(r"LPX_[A-Z0-9_]{1,96}", self.client_secret_env) is None
        ):
            raise ConfigurationError("Client secrets must use a dedicated LPX environment variable.")


@dataclass(frozen=True, slots=True)
class ServiceConfiguration:
    state_directory: Path
    policy_directory: Path
    public_origin: str
    principals: tuple[Principal, ...]
    resources: tuple[Resource, ...] = ()
    mode: str = "operator"
    port: int = 8765
    oauth_issuer: str | None = None
    oauth_jwks_uri: str | None = None
    browser_oauth: BrowserOAuth | None = None
    max_upload_bytes: int = 128 * 1024 * 1024
    max_storage_bytes: int = 4 * 1024 * 1024 * 1024
    retention_seconds: int = 24 * 60 * 60

    def __post_init__(self) -> None:
        if self.mode not in {"operator", "oauth"} or type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ConfigurationError("Unsupported service mode or port.")
        for path in (self.state_directory, self.policy_directory):
            if not isinstance(path, Path) or not path.is_absolute():
                raise ConfigurationError("Service directories must be absolute operator-selected paths.")
        if (not isinstance(self.principals, tuple) or not 1 <= len(self.principals) <= 10
                or any(not isinstance(value, Principal) for value in self.principals)
                or len({value.principal_id for value in self.principals}) != len(self.principals)):
            raise ConfigurationError("The private pilot requires one to ten explicit identities.")
        owners = {value.principal_id for value in self.principals}
        if (not isinstance(self.resources, tuple) or len(self.resources) > 256
                or any(not isinstance(value, Resource) for value in self.resources)
                or len({value.resource_id for value in self.resources}) != len(self.resources)
                or any(value.principal_id not in owners for value in self.resources)):
            raise ConfigurationError("Resource registrations must be unique and explicitly owned.")
        for value, minimum, maximum in (
            (self.max_upload_bytes, 1, 1024**3), (self.max_storage_bytes, 1024**3, 100 * 1024**3),
            (self.retention_seconds, 60, 7 * 24 * 3600),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ConfigurationError("A service limit is outside the supported pilot envelope.")
        # Admission reserves the entire upload pool independently of a job's
        # workspace. Reject configurations that can never admit their first job.
        if self.max_storage_bytes < self.upload_pool_bytes + OPERATION_RESERVATION_BYTES:
            raise ConfigurationError("Storage must cover the upload pool and one operation reservation.")
        if self.mode == "operator":
            if (self.public_origin != f"http://127.0.0.1:{self.port}" or len(self.principals) != 1
                    or self.principals[0].issuer != "urn:lpx-keepmorrow:local-operator"
                    or self.oauth_issuer or self.oauth_jwks_uri or self.browser_oauth):
                raise ConfigurationError("Operator mode is restricted to one local identity on loopback.")
        else:
            if https_url(self.public_origin, origin_only=True) != self.public_origin:
                raise ConfigurationError("The public origin must omit a trailing slash.")
            https_url(self.oauth_issuer)
            https_url(self.oauth_jwks_uri)
            if self.browser_oauth is None or any(value.issuer != self.oauth_issuer for value in self.principals):
                raise ConfigurationError("OAuth mode requires an issuer, registered browser client, and matching identities.")

    @property
    def resource_url(self) -> str:
        return self.public_origin + "/mcp"

    @property
    def upload_pool_bytes(self) -> int:
        """Return the shared logical upload budget used by admission accounting."""
        return 4 * self.max_upload_bytes

    def principal(self, issuer: str, subject: str) -> Principal:
        candidate = Principal(issuer, subject)
        for principal in self.principals:
            if principal == candidate:
                return principal
        from ..access.models import AccessDenied
        raise AccessDenied()

    def policies(self) -> tuple[PolicySet, dict[str, bytes]]:
        root = safe_directory(self.policy_directory)
        documents: dict[str, bytes] = {}
        for key, name in (("terms", "terms-of-use.md"), ("privacy", "privacy-notice.md")):
            with open_regular(root / name) as source:
                data = source.read(128 * 1024 + 1)
            if not data or len(data) > 128 * 1024:
                raise ConfigurationError("The policy document is empty or exceeds its supported size.")
            version = CURRENT_TERMS_VERSION if key == "terms" else CURRENT_PRIVACY_VERSION
            if version not in data.decode("utf-8"):
                raise ConfigurationError("Bundled policy bytes do not identify the current version.")
            documents[key] = data
        return PolicySet(
            CURRENT_TERMS_VERSION, hashlib.sha256(documents["terms"]).hexdigest(),
            CURRENT_PRIVACY_VERSION, hashlib.sha256(documents["privacy"]).hexdigest(),
        ), documents


def load_configuration(path: Path) -> ServiceConfiguration:
    """Decode a bounded, strict JSON configuration without reading collection data."""
    try:
        def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ConfigurationError("Duplicate configuration fields are unsupported.")
                result[key] = value
            return result

        with open_regular(path) as source:
            data = source.read(128 * 1024 + 1)
        if len(data) > 128 * 1024:
            raise ConfigurationError("The configuration exceeds its supported byte limit.")
        value = json.loads(data, object_pairs_hook=unique)
        allowed = {field for field in ServiceConfiguration.__dataclass_fields__}
        if not isinstance(value, dict) or set(value) - allowed:
            raise ConfigurationError("The configuration contains unsupported fields.")
        value["state_directory"] = Path(value["state_directory"])
        value["policy_directory"] = Path(value["policy_directory"])
        value["principals"] = tuple(Principal(**item) for item in value["principals"])
        value["resources"] = tuple(Resource(**{**item, "path": Path(item["path"])}) for item in value.get("resources", []))
        if value.get("browser_oauth") is not None:
            value["browser_oauth"] = BrowserOAuth(**value["browser_oauth"])
        return ServiceConfiguration(**value)
    except ConfigurationError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError) as error:
        raise ConfigurationError("The service configuration could not be validated.") from error
