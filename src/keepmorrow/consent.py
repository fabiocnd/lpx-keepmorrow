"""Require current policy acceptance before a selected archive operation.

The receipt records a local declaration, not identity or legally verified assent.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

CURRENT_TERMS_VERSION = "2026-11-12-draft.2"
CURRENT_PRIVACY_VERSION = "2026-11-12-draft.2"
_SUPPORTED_OPERATIONS = frozenset({"create", "verify", "restore", "import", "catalog", "search", "read", "associate", "recover"})


class ConsentError(ValueError):
    """The requested operation lacks a supported, current acceptance declaration."""


@dataclass(frozen=True, slots=True)
class AcceptanceReceipt:
    """Nonsecret metadata for one accepted local operation; never source content."""

    terms_version: str
    privacy_version: str
    accepted_at_utc: str
    operation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "terms_version": self.terms_version,
            "privacy_version": self.privacy_version,
            "accepted_at_utc": self.accepted_at_utc,
            "operation": self.operation,
        }


def require_acceptance(
    terms_version: str | None,
    privacy_version: str | None,
    operation: str,
) -> AcceptanceReceipt:
    """Validate explicit acceptance without accessing user files or the network.

    Both versions must exactly match the current internal drafts. The declaration
    applies only to one known operation; it grants no cloud, AI, deletion, or
    publication authority. Raise ConsentError before returning any receipt when
    a declaration is absent, stale, malformed, or outside that operation scope.
    """
    if not isinstance(operation, str) or operation not in _SUPPORTED_OPERATIONS:
        raise ConsentError("Acceptance supports only documented local preservation and collection operations.")
    if not isinstance(terms_version, str) or terms_version != CURRENT_TERMS_VERSION:
        raise ConsentError(
            "Review legal/terms-of-use.md and explicitly accept the current version "
            f"with --accept-terms {CURRENT_TERMS_VERSION}."
        )
    if not isinstance(privacy_version, str) or privacy_version != CURRENT_PRIVACY_VERSION:
        raise ConsentError(
            "Review legal/privacy-notice.md and explicitly accept the current version "
            f"with --accept-privacy {CURRENT_PRIVACY_VERSION}."
        )

    # Generate the receipt only after every declaration is valid. No receipt is
    # created for a refused operation, and acceptance does not imply completion.
    return AcceptanceReceipt(
        terms_version=terms_version,
        privacy_version=privacy_version,
        accepted_at_utc=datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        operation=operation,
    )
