"""Archive contracts; validation never interprets source files as instructions.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, fields
from pathlib import PurePosixPath
from typing import Any

FORMAT = "lpx-keepmorrow.directory"
VERSION = 1
SCOPE = "explicitly_supplied_directory"
MANIFEST_NAME = "manifest.json"
PAYLOAD_NAME = "payload"
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_RESERVED_NAME = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])\Z", re.IGNORECASE)


class ArchiveError(ValueError):
    """The requested operation cannot satisfy the archive contract."""


@dataclass(frozen=True, slots=True)
class Limits:
    """Explicit resource ceilings; values are bytes unless named otherwise."""

    max_entries: int = 10_000
    max_total_bytes: int = 10 * 1024**3
    max_file_bytes: int = 2 * 1024**3
    max_manifest_bytes: int = 8 * 1024**2
    chunk_bytes: int = 1024**2

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or value <= 0:
                raise ArchiveError(f"{field.name} must be a positive integer.")
        if self.chunk_bytes > 16 * 1024**2:
            raise ArchiveError("chunk_bytes must not exceed 16 MiB.")


@dataclass(frozen=True, slots=True)
class FileRecord:
    path: str
    size_bytes: int
    sha256: str

    def as_dict(self) -> dict[str, str | int]:
        return {"path": self.path, "size_bytes": self.size_bytes, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class Manifest:
    directories: tuple[str, ...]
    files: tuple[FileRecord, ...]

    def to_bytes(self) -> bytes:
        document = {
            "format": FORMAT,
            "version": VERSION,
            "scope": SCOPE,
            "hash_algorithm": "sha256",
            "directories": list(self.directories),
            "files": [record.as_dict() for record in self.files],
        }
        return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


@dataclass(frozen=True, slots=True)
class VerificationIssue:
    category: str
    path: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    file_count: int
    total_bytes: int
    issues: tuple[VerificationIssue, ...]

    @property
    def verified(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": "local_archive_validation",
            "scope": SCOPE,
            "verified": self.verified,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "issues": [{"category": item.category, "path": item.path} for item in self.issues],
        }


def validate_relative_path(value: object) -> str:
    """Accept one portable NFC path without changing its original spelling.

    Reject unsupported names instead of silently rewriting source identity.
    Unicode case folding is used separately to detect destination collisions.
    """
    if not isinstance(value, str) or not value:
        raise ArchiveError("Archive paths must contain 1 to 4096 UTF-8 bytes.")
    try:
        encoded_length = len(value.encode("utf-8"))
    except UnicodeError as error:
        raise ArchiveError("Archive paths must contain valid Unicode scalar values.") from error
    if encoded_length > 4096:
        raise ArchiveError("Archive paths must contain 1 to 4096 UTF-8 bytes.")
    if unicodedata.normalize("NFC", value) != value:
        raise ArchiveError("Archive paths must use NFC Unicode normalization.")
    parts = value.split("/")
    if len(parts) > 64:
        raise ArchiveError("Archive paths must not exceed 64 components.")
    for part in parts:
        if part in {"", ".", ".."} or part[-1:] in {" ", "."}:
            raise ArchiveError("Archive paths contain an unsafe component.")
        if len(part.encode("utf-8")) > 240:
            raise ArchiveError("Archive path components must not exceed 240 UTF-8 bytes.")
        if any(char in '<>:"\\|?*' or unicodedata.category(char).startswith("C") for char in part):
            raise ArchiveError("Archive paths contain unsupported characters.")
        if _RESERVED_NAME.fullmatch(part.split(".", 1)[0]):
            raise ArchiveError("Archive paths contain a reserved device name.")
    return value


def validate_inventory(directories: list[str], records: list[FileRecord], limits: Limits) -> None:
    """Validate path topology and resource bounds in O(n) additional space."""
    paths = directories + [record.path for record in records]
    if len(paths) > limits.max_entries:
        raise ArchiveError("The archive exceeds the configured entry limit.")
    seen: set[str] = set()
    for path in paths:
        validate_relative_path(path)
        key = path.casefold()
        if key in seen:
            raise ArchiveError("The archive contains duplicate or case-colliding paths.")
        seen.add(key)
    directory_set = set(directories)
    for path in paths:
        parent = str(PurePosixPath(path).parent)
        if parent != "." and parent not in directory_set:
            raise ArchiveError("The archive omits a required parent directory.")
    total_bytes = 0
    for record in records:
        if type(record.size_bytes) is not int or not 0 <= record.size_bytes <= limits.max_file_bytes:
            raise ArchiveError("A file size is invalid or exceeds the configured limit.")
        if not isinstance(record.sha256, str) or _HEX_DIGEST.fullmatch(record.sha256) is None:
            raise ArchiveError("A file hash is not a lowercase SHA-256 digest.")
        total_bytes += record.size_bytes
    if total_bytes > limits.max_total_bytes:
        raise ArchiveError("The archive exceeds the configured total-byte limit.")


def parse_manifest(data: bytes, limits: Limits) -> Manifest:
    """Reject ambiguous JSON and unsupported schemas before filesystem work."""
    if len(data) > limits.max_manifest_bytes:
        raise ArchiveError("The manifest exceeds the configured byte limit.")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ArchiveError("The manifest contains duplicate JSON keys.")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ArchiveError("The manifest contains a non-finite JSON number.")

    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    except ArchiveError:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ArchiveError("The manifest is not supported UTF-8 JSON.") from error
    keys = {"format", "version", "scope", "hash_algorithm", "directories", "files"}
    if not isinstance(document, dict) or set(document) != keys:
        raise ArchiveError("The manifest fields do not match schema version 1.")
    if (document["format"] != FORMAT or type(document["version"]) is not int
            or document["version"] != VERSION or document["scope"] != SCOPE
            or document["hash_algorithm"] != "sha256"):
        raise ArchiveError("The manifest format, version, scope, or hash algorithm is unsupported.")
    directories, files = document["directories"], document["files"]
    if not isinstance(directories, list) or not isinstance(files, list):
        raise ArchiveError("Manifest directories and files must be arrays.")
    if len(directories) + len(files) > limits.max_entries:
        raise ArchiveError("The archive exceeds the configured entry limit.")
    records: list[FileRecord] = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "size_bytes", "sha256"}:
            raise ArchiveError("A manifest file record has unsupported fields.")
        records.append(FileRecord(item["path"], item["size_bytes"], item["sha256"]))
    validate_inventory(directories, records, limits)
    if directories != sorted(directories) or [item.path for item in records] != sorted(item.path for item in records):
        raise ArchiveError("Manifest entries must use canonical path order.")
    return Manifest(tuple(directories), tuple(records))

