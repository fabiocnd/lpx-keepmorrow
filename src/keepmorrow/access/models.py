"""Explicit identity, policy, and consent contracts for connected processing.

These values describe an authenticated boundary's decisions. Constructing a
Principal does not validate a token or prove that a human accepted anything.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import hashlib
import json
import re

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_ACTION = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_ACTIONS = 32


class AccessError(ValueError):
    """A content-free failure at an access-control boundary."""

    code = "invalid_access_request"


class AccessDenied(AccessError):
    """Missing, foreign, stale, revoked, and expired scopes share one outcome."""

    code = "access_denied"

    def __init__(self) -> None:
        super().__init__("The requested access is unavailable or not authorized.")


def validate_token(value: object) -> str:
    """Validate a bounded opaque metadata identifier without normalizing it."""
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        raise AccessError("Access metadata requires a supported opaque identifier.")
    return value


def validate_action(value: object) -> str:
    if not isinstance(value, str) or _ACTION.fullmatch(value) is None:
        raise AccessError("Access actions require a supported operation identifier.")
    return value


def validate_actions(values: Iterable[str]) -> frozenset[str]:
    """Bound work while consuming an iterable, including a generator."""
    if isinstance(values, (str, bytes)):
        raise AccessError("At least one explicit action is required.")
    result: set[str] = set()
    try:
        for index, value in enumerate(values):
            if index >= MAX_ACTIONS:
                raise AccessError("The action scope exceeds the supported limit.")
            action = validate_action(value)
            if action in result:
                raise AccessError("Duplicate actions are not a valid scope.")
            result.add(action)
    except TypeError as error:
        raise AccessError("Actions must be an explicit bounded iterable.") from error
    if not result:
        raise AccessError("At least one explicit action is required.")
    return frozenset(result)


def validate_timestamp(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 253402300799:
        raise AccessError("Timestamps must be UTC Unix seconds in the supported range.")
    return value


def validate_version(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 2**63 - 2:
        raise AccessError("A positive grant version is required.")
    return value


def _identity_text(value: object, maximum: int) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= maximum
            or value.strip() != value or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise AccessError("The authenticated identity is malformed.")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise AccessError("The authenticated identity is malformed.") from error
    return value


@dataclass(frozen=True, slots=True)
class Principal:
    """An exact issuer/subject pair supplied only after credential validation.

    Email addresses, source account namespaces, and model arguments are not
    identity evidence. Issuer and subject are not normalized: a changed issuer
    or differently cased subject denotes a different principal. Only the
    domain-separated digest is persisted by AccessStore.
    """

    issuer: str
    subject: str
    principal_id: str = field(init=False)

    def __post_init__(self) -> None:
        _identity_text(self.issuer, 2048)
        _identity_text(self.subject, 255)
        encoded = json.dumps([self.issuer, self.subject], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(b"lpx-keepmorrow.principal.v1\x00" + encoded).hexdigest()
        object.__setattr__(self, "principal_id", "principal_" + digest)


@dataclass(frozen=True, slots=True)
class PolicySet:
    """The exact version and bytes displayed by the trusted acceptance surface."""

    terms_version: str
    terms_sha256: str
    privacy_version: str
    privacy_sha256: str

    def __post_init__(self) -> None:
        validate_token(self.terms_version)
        validate_token(self.privacy_version)
        for digest in (self.terms_sha256, self.privacy_sha256):
            if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
                raise AccessError("Policy documents require exact lowercase SHA-256 digests.")

    def as_dict(self) -> dict[str, str]:
        return {
            "terms_version": self.terms_version,
            "terms_sha256": self.terms_sha256,
            "privacy_version": self.privacy_version,
            "privacy_sha256": self.privacy_sha256,
        }


@dataclass(frozen=True, slots=True)
class Grant:
    """An immutable allowed scope; its monotonic version changes on revocation."""

    grant_id: str
    principal_id: str
    resource_id: str
    generation: str
    actions: frozenset[str]
    purpose: str
    recipient: str
    grant_version: int
    created_at: int
    expires_at: int
    revoked_at: int | None


@dataclass(frozen=True, slots=True)
class HumanAcceptance:
    """A trusted interaction's scoped receipt, distinct from a resource grant."""

    acceptance_id: str
    principal_id: str
    grant_id: str
    grant_version: int
    resource_id: str
    generation: str
    actions: frozenset[str]
    purpose: str
    recipient: str
    policies: PolicySet
    interaction_id: str
    accepted_at: int
    expires_at: int
    revoked_at: int | None


@dataclass(frozen=True, slots=True)
class AccessDecision:
    """A scoped authorization observation, not a reusable bearer credential."""

    grant_id: str
    grant_version: int
    acceptance_id: str
    principal_id: str
    resource_id: str
    generation: str
    action: str
    authorized_at: int


@dataclass(frozen=True, slots=True)
class AuthorizedGrant:
    """Listing metadata restricted to the principal's currently accepted actions.

    expires_at is the administrative grant's upper bound; individual acceptance
    receipts can expire sooner. Content admission must call require_access even
    after this listing succeeds.
    """

    grant_id: str
    grant_version: int
    resource_id: str
    generation: str
    actions: frozenset[str]
    purpose: str
    recipient: str
    expires_at: int
