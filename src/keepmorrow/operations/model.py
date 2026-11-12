"""Bounded, immutable contracts for reviewed background operations.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, fields
from typing import Any, Literal, TypeAlias


class OperationError(RuntimeError):
    """An operation cannot satisfy its ownership, state, or resource contract."""


class OperationBusy(OperationError):
    """The bounded queue or the exclusive worker is already occupied."""


class OperationCancelled(OperationError):
    """The active attempt must stop before publication authorization."""


class OperationCleanupRequired(OperationError):
    """Private temporary bytes cannot yet be proven absent or safely removed."""


class StaleAttempt(OperationError):
    """The caller no longer owns this operation attempt."""


class IdempotencyConflict(OperationError):
    """An existing principal-scoped key identifies different parameters."""


OperationKind: TypeAlias = Literal["import", "recovery", "association", "package", "unpack"]
OperationState: TypeAlias = Literal[
    "queued", "running", "verifying", "completed", "partial", "cancel_requested",
    "cancelled", "interrupted", "failed", "expired",
]
TERMINAL_STATES = frozenset({"completed", "partial", "cancelled", "failed", "expired"})
ACTIVE_STATES = frozenset({"running", "verifying", "cancel_requested"})
PENDING_STATES = frozenset({"queued", "running", "verifying", "cancel_requested", "interrupted"})
FAILURE_CODES = frozenset({
    "execution_failed", "executor_incomplete", "authorization_denied", "integrity_failed",
    "input_unavailable", "resource_limit", "publication_failed", "worker_interrupted",
    "reconciliation_failed", "plan_expired", "attempt_limit", "cancelled", "cleanup_required",
})
COVERAGE_GAPS = frozenset({
    "association_unknown", "unresolved_artifacts", "unsupported_records",
    "unsupported_content", "incomplete_source", "selection_omissions",
})
_OPAQUE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ACTION = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_ACTION_BY_KIND = {
    "import": "import", "recovery": "recover", "association": "associate",
    "package": "package", "unpack": "unpack",
}


def require_opaque_id(value: object) -> str:
    """Reject paths and free-form text at identifier-only boundaries."""
    if not isinstance(value, str) or _OPAQUE_ID.fullmatch(value) is None:
        raise OperationError("An identifier must be a bounded opaque token.")
    return value


def require_digest(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise OperationError("A digest must be lowercase SHA-256 hexadecimal.")
    return value


def _bounded_text(value: object, maximum_bytes: int) -> str:
    if not isinstance(value, str) or not value:
        raise OperationError("A required text parameter is missing.")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as error:
        raise OperationError("Text parameters require valid Unicode scalar values.") from error
    if size > maximum_bytes or any(unicodedata.category(char).startswith("C") for char in value):
        raise OperationError("A text parameter exceeds its supported contract.")
    return value


def _nonnegative_integer(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise OperationError("A count must be a bounded nonnegative integer.")
    return value


@dataclass(frozen=True, slots=True)
class OperationLimits:
    """Admission ceilings do not replace the executor's actual byte limits."""

    max_pending_operations: int = 16
    max_pending_per_principal: int = 4
    max_prepared_per_principal: int = 32
    max_reserved_bytes: int = 4 * 1024**3
    max_operation_reserved_bytes: int = 2 * 1024**3
    max_plan_bytes: int = 16 * 1024
    max_result_bytes: int = 4096
    max_attempts: int = 3
    plan_ttl_seconds: int = 3600
    review_ttl_seconds: int = 900
    max_list_items: int = 100

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or not 0 < value <= 2**63 - 1:
                raise OperationError("Operation limits require positive bounded integers.")
        if self.max_operation_reserved_bytes > self.max_reserved_bytes:
            raise OperationError("One operation cannot reserve more than the total byte budget.")
        if self.max_pending_per_principal > self.max_pending_operations:
            raise OperationError("A principal's queue cannot exceed the global queue.")
        if self.max_plan_bytes > 64 * 1024 or self.max_result_bytes > 16 * 1024:
            raise OperationError("Journal document ceilings exceed their supported maximum.")
        if self.max_attempts > 10 or self.max_list_items > 100:
            raise OperationError("Retry and list ceilings exceed their supported maximum.")


@dataclass(frozen=True, slots=True)
class AuthorizationScope:
    resource_id: str
    generation: str
    grant_id: str
    grant_version: int
    acceptance_id: str
    action: str

    def __post_init__(self) -> None:
        for value in (self.resource_id, self.generation, self.grant_id, self.acceptance_id):
            require_opaque_id(value)
        if type(self.grant_version) is not int or not 1 <= self.grant_version <= 2**63 - 1:
            raise OperationError("A grant version must be a positive bounded integer.")
        if not isinstance(self.action, str) or _ACTION.fullmatch(self.action) is None:
            raise OperationError("The authorization action is invalid.")

    def as_dict(self) -> dict[str, str | int]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class ImportParameters:
    input_handle: str
    input_sha256: str
    account_namespace: str
    previous_generation: str | None = None

    def __post_init__(self) -> None:
        require_opaque_id(self.input_handle)
        require_digest(self.input_sha256)
        _bounded_text(self.account_namespace, 256)
        if self.previous_generation is not None:
            require_opaque_id(self.previous_generation)


@dataclass(frozen=True, slots=True)
class RecoveryParameters:
    conversation_keys: tuple[str, ...] = ()
    project_id: str | None = None
    revision_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.conversation_keys) is not tuple or len(self.conversation_keys) > 100:
            raise OperationError("Recovery selection requires a tuple of at most 100 identities.")
        for key in self.conversation_keys:
            require_digest(key)
        if len(set(self.conversation_keys)) != len(self.conversation_keys):
            raise OperationError("Recovery selection contains duplicate identities.")
        if bool(self.conversation_keys) == (self.project_id is not None):
            raise OperationError("Select conversation identities or one project.")
        if self.project_id is not None:
            _bounded_text(self.project_id, 256)
        if self.revision_id is not None:
            require_digest(self.revision_id)
            if self.project_id is not None or len(self.conversation_keys) != 1:
                raise OperationError("A revision requires exactly one conversation identity.")


@dataclass(frozen=True, slots=True)
class AssociationParameters:
    conversation_key: str
    state: str
    project_id: str | None
    reason: str

    def __post_init__(self) -> None:
        require_digest(self.conversation_key)
        if (not isinstance(self.state, str)
                or self.state not in {"project_confirmed", "standalone_confirmed", "association_unknown"}):
            raise OperationError("The association state is unsupported.")
        if (self.state == "project_confirmed") != (self.project_id is not None):
            raise OperationError("A confirmed project requires exactly one project identifier.")
        if self.project_id is not None:
            _bounded_text(self.project_id, 256)
        _bounded_text(self.reason, 1024)


@dataclass(frozen=True, slots=True)
class PackageParameters:
    """Package the immutable generation named by the authorization scope."""


@dataclass(frozen=True, slots=True)
class UnpackParameters:
    input_handle: str
    input_sha256: str

    def __post_init__(self) -> None:
        require_opaque_id(self.input_handle)
        require_digest(self.input_sha256)


OperationParameters: TypeAlias = (
    ImportParameters | RecoveryParameters | AssociationParameters | PackageParameters | UnpackParameters
)
_PARAMETER_TYPES: dict[str, type[OperationParameters]] = {
    "import": ImportParameters,
    "recovery": RecoveryParameters,
    "association": AssociationParameters,
    "package": PackageParameters,
    "unpack": UnpackParameters,
}


def parameter_document(parameters: OperationParameters) -> tuple[OperationKind, dict[str, Any]]:
    for kind, parameter_type in _PARAMETER_TYPES.items():
        if type(parameters) is parameter_type:
            result = {field.name: getattr(parameters, field.name) for field in fields(parameters)}
            if isinstance(parameters, RecoveryParameters):
                result["conversation_keys"] = sorted(parameters.conversation_keys)
            return kind, result  # type: ignore[return-value]
    raise OperationError("The operation parameter type is unsupported.")


def parse_parameters(kind: str, value: object) -> OperationParameters:
    parameter_type = _PARAMETER_TYPES.get(kind)
    if parameter_type is None or not isinstance(value, dict):
        raise OperationError("The stored operation parameter schema is unsupported.")
    if set(value) != {field.name for field in fields(parameter_type)}:
        raise OperationError("The stored operation parameter schema is invalid.")
    arguments = dict(value)
    if kind == "recovery":
        if not isinstance(arguments["conversation_keys"], list):
            raise OperationError("The stored recovery selection is invalid.")
        arguments["conversation_keys"] = tuple(arguments["conversation_keys"])
    try:
        return parameter_type(**arguments)
    except (TypeError, KeyError) as error:
        raise OperationError("The stored operation parameters are invalid.") from error


def canonical_document(
    principal_id: str, parameters: OperationParameters, scope: AuthorizationScope, reservation_bytes: int,
) -> bytes:
    require_opaque_id(principal_id)
    if not isinstance(scope, AuthorizationScope):
        raise OperationError("An explicit authorization scope is required.")
    _nonnegative_integer(reservation_bytes)
    kind, values = parameter_document(parameters)
    if scope.action != _ACTION_BY_KIND[kind]:
        raise OperationError("The operation kind requires its exact authorization action.")
    return json.dumps({
        "version": 1, "principal_id": principal_id, "kind": kind,
        "parameters": values, "scope": scope.as_dict(), "reservation_bytes": reservation_bytes,
    }, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


@dataclass(frozen=True, slots=True)
class OperationPlan:
    plan_id: str
    principal_id: str
    kind: OperationKind
    parameters: OperationParameters
    scope: AuthorizationScope
    reservation_bytes: int
    parameter_digest: str
    created_at: float
    expires_at: float

    def as_dict(self) -> dict[str, Any]:
        """Return review material, excluding credentials and filesystem locations."""
        return {
            "plan_id": self.plan_id, "kind": self.kind, "state": "prepared",
            "parameters": parameter_document(self.parameters)[1], "scope": self.scope.as_dict(),
            "reservation_bytes": self.reservation_bytes, "parameter_digest": self.parameter_digest,
            "created_at": self.created_at, "expires_at": self.expires_at,
        }


@dataclass(frozen=True, slots=True)
class HumanReview:
    review_id: str
    plan_id: str
    principal_id: str
    parameter_digest: str
    interaction_id: str
    reviewed_at: float
    expires_at: float


@dataclass(frozen=True, slots=True)
class VerifiedResult:
    manifest_sha256: str
    file_count: int
    total_bytes: int
    coverage_gaps: tuple[str, ...] = ()
    artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        require_digest(self.manifest_sha256)
        _nonnegative_integer(self.file_count)
        _nonnegative_integer(self.total_bytes)
        if (type(self.coverage_gaps) is not tuple
                or len(self.coverage_gaps) > len(COVERAGE_GAPS)
                or any(not isinstance(item, str) or item not in COVERAGE_GAPS for item in self.coverage_gaps)
                or len(set(self.coverage_gaps)) != len(self.coverage_gaps)):
            raise OperationError("Coverage gaps must be distinct supported category codes.")
        if self.artifact_sha256 is not None:
            require_digest(self.artifact_sha256)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verification_stage": "local_output_validation",
            "manifest_sha256": self.manifest_sha256, "file_count": self.file_count,
            "total_bytes": self.total_bytes, "coverage_gaps": sorted(self.coverage_gaps),
            "artifact_sha256": self.artifact_sha256,
        }


@dataclass(frozen=True, slots=True)
class OperationSnapshot:
    operation_id: str
    principal_id: str
    plan_id: str
    kind: OperationKind
    state: OperationState
    parameter_digest: str
    output_id: str
    reservation_bytes: int
    attempt_number: int
    cancel_requested: bool
    publication_authorized: bool
    manifest_sha256: str | None
    error_code: str | None
    created_at: float
    updated_at: float
    result: VerifiedResult | None

    def as_dict(self) -> dict[str, Any]:
        """Expose bounded status without plan text, identity claims, or user paths."""
        return {
            "operation_id": self.operation_id, "plan_id": self.plan_id, "kind": self.kind,
            "state": self.state, "parameter_digest": self.parameter_digest,
            "output_id": self.output_id if self.result is not None else None,
            "attempt_number": self.attempt_number, "cancel_requested": self.cancel_requested,
            "publication_authorized": self.publication_authorized,
            "error_code": self.error_code, "created_at": self.created_at,
            "updated_at": self.updated_at, "result": self.result.as_dict() if self.result else None,
        }


@dataclass(frozen=True, slots=True)
class CancellationReceipt:
    operation: OperationSnapshot
    disposition: Literal["cancelled", "requested", "publication_committed", "already_terminal"]


@dataclass(frozen=True, slots=True)
class PublicationPermit:
    operation_id: str
    output_id: str
    attempt_number: int
    manifest_sha256: str
    authorized_at: float


def parameter_digest(document: bytes) -> str:
    return hashlib.sha256(document).hexdigest()
