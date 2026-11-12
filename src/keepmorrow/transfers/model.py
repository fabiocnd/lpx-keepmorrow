"""Bounded transfer contracts; identities and authority belong to the caller.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Callable

from ..archive.model import ArchiveError

Checkpoint = Callable[[], None]
GIB = 1024**3


class TransferError(ArchiveError):
    """A transfer cannot satisfy its ownership, lifetime, or integrity contract."""


class UploadUnavailable(TransferError):
    """The handle is unknown, expired, or unavailable to the supplied owner."""


class TransferLimitExceeded(TransferError):
    """Admission or processing would exceed a configured transfer budget."""


def _positive_integers(value: object) -> None:
    for field in fields(value):
        number = getattr(value, field.name)
        if type(number) is not int or number <= 0:
            raise TransferError(f"{field.name} must be a positive integer.")


@dataclass(frozen=True, slots=True)
class UploadLimits:
    """Reserve the declared size, or the maximum size for an unknown stream."""

    max_upload_bytes: int = GIB
    max_owner_bytes: int = 2 * GIB
    max_total_bytes: int = 4 * GIB
    max_owner_uploads: int = 8
    max_total_uploads: int = 64
    lifetime_seconds: int = 3600
    chunk_bytes: int = 1024**2

    def __post_init__(self) -> None:
        _positive_integers(self)
        if self.chunk_bytes > 16 * 1024**2:
            raise TransferError("chunk_bytes must not exceed 16 MiB.")


@dataclass(frozen=True, slots=True)
class UploadRecord:
    """Opaque receipt; display metadata never selects a storage path."""

    upload_id: str
    owner_id: str
    display_name: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: float
    expires_at: float

    def as_dict(self) -> dict[str, str | int | float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PackageLimits:
    """The initial non-ZIP64 profile caps encoded and expanded bytes at 1 GiB.

    Wrapper paths have an independent budget: manifest.json and payload/ each
    consume one entry beyond the directory archive's payload inventory.
    """

    max_encoded_bytes: int = GIB
    max_expanded_bytes: int = GIB
    max_wrapper_entries: int = 10_002
    max_metadata_bytes: int = 8 * 1024**2
    chunk_bytes: int = 1024**2

    def __post_init__(self) -> None:
        _positive_integers(self)
        if max(self.max_encoded_bytes, self.max_expanded_bytes) > GIB:
            raise TransferError("The recovery-package profile supports at most 1 GiB per byte budget.")
        if self.max_wrapper_entries >= 65_535:
            raise TransferError("The recovery-package profile requires fewer than 65,535 entries.")
        if self.chunk_bytes > 16 * 1024**2:
            raise TransferError("chunk_bytes must not exceed 16 MiB.")


@dataclass(frozen=True, slots=True)
class PackageResult:
    """Local package and collection verification, without a remote-delivery claim."""

    size_bytes: int
    sha256: str
    expanded_size_bytes: int
    file_count: int
    directory_count: int
    manifest_sha256: str
    collection_scope: str

    def as_dict(self) -> dict[str, str | int | bool]:
        return {
            **asdict(self),
            "format": "lpx-keepmorrow.recovery-zip",
            "version": 1,
            "stage": "local_package_and_collection_validation",
            "verified": True,
            "account_completeness": "not_asserted",
        }


def checkpoint_if_requested(checkpoint: Checkpoint | None) -> None:
    if checkpoint is not None:
        checkpoint()
