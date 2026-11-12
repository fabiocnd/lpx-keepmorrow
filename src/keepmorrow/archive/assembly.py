"""Compose a verified archive without a second payload copy for packaging.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Iterator

from .filesystem import FileState, copy_tree, open_regular, safe_directory, scan_tree, stream_file
from .model import (
    MANIFEST_NAME,
    PAYLOAD_NAME,
    ArchiveError,
    FileRecord,
    Limits,
    Manifest,
    parse_manifest,
    validate_relative_path,
)
from .service import _staging, _verify


class ArchiveAssembly:
    """Write trusted application output into one private archive staging tree.

    Use :func:`assembling_archive` to own this object's lifetime. Source bytes
    are copied and hashed together, then independently verified before atomic
    publication. The exposed payload permits reading preserved inputs before
    deriving metadata; callers must write only through the add methods.

    A failed add operation invalidates the entire assembly, even if its caller
    catches the exception. This prevents an incomplete copy from becoming a
    successful archive. Instances are neither concurrent writers nor resumable
    jobs. Payload I/O is O(B); metadata uses O(N + P) memory, where P is path size.
    """

    def __init__(self, payload: Path, destination: Path, limits: Limits) -> None:
        self._payload = payload
        self._destination = destination
        self._limits = limits
        self._directories: set[str] = set()
        self._files: dict[str, FileRecord] = {}
        self._names: dict[str, tuple[str, bool]] = {}
        self._total_bytes = 0
        self._active = True
        self._failed = False
        self._manifest: Manifest | None = None

    @property
    def payload(self) -> Path:
        """Return the staged payload, or its final path after publication."""
        return self._payload

    @property
    def manifest(self) -> Manifest | None:
        """Return the committed manifest only after successful context exit."""
        return self._manifest

    def _require_active(self) -> None:
        if not self._active or self._failed:
            raise ArchiveError("The archive assembly is closed or has already failed.")

    def _check_source(self, source: Path, *, directory: bool) -> None:
        if source.is_relative_to(self._payload.parent):
            raise ArchiveError("An assembly cannot consume its own staging tree.")
        if directory and self._destination.is_relative_to(source):
            raise ArchiveError("The destination must be outside every source directory.")

    def _plan(
        self,
        directories: tuple[str, ...],
        files: tuple[tuple[str, int], ...],
    ) -> tuple[str, ...]:
        """Validate only new paths; repeated small additions stay linear in N.

        Existing directories can be shared as parents. Files and differently
        spelled case-fold equivalents cannot be shared or overwritten. Ancestor
        work is bounded by the portable path contract's 64-component limit.
        """
        planned: dict[str, tuple[str, bool]] = {}

        def register(path: str, is_directory: bool) -> None:
            validate_relative_path(path)
            key = path.casefold()
            prior = planned.get(key) or self._names.get(key)
            if prior is not None:
                if prior != (path, True) or not is_directory:
                    raise ArchiveError("Assembly paths overlap or collide across platforms.")
                return
            planned[key] = (path, is_directory)
            if len(self._names) + len(planned) > self._limits.max_entries:
                raise ArchiveError("The assembled archive exceeds the configured entry limit.")

        for path, is_directory in (
            *((path, True) for path in directories),
            *((path, False) for path, _ in files),
        ):
            # Validate before PurePosixPath can collapse unsupported components.
            validate_relative_path(path)
            for parent in reversed(PurePosixPath(path).parents):
                if str(parent) != ".":
                    register(str(parent), True)
            register(path, is_directory)

        added_bytes = 0
        for _, size_bytes in files:
            if type(size_bytes) is not int or not 0 <= size_bytes <= self._limits.max_file_bytes:
                raise ArchiveError("An assembly file exceeds the configured byte limit.")
            added_bytes += size_bytes
            if self._total_bytes + added_bytes > self._limits.max_total_bytes:
                raise ArchiveError("The assembled archive exceeds the configured total-byte limit.")
        return tuple(sorted(path for path, is_directory in planned.values() if is_directory))

    def _record(self, directories: tuple[str, ...], records: tuple[FileRecord, ...]) -> None:
        for path in directories:
            self._directories.add(path)
            self._names[path.casefold()] = (path, True)
        for record in records:
            self._files[record.path] = record
            self._names[record.path.casefold()] = (record.path, False)
            self._total_bytes += record.size_bytes

    def add_tree(self, source: Path, prefix: str) -> Manifest:
        """Copy a directory once beneath a new prefix; return source-relative records.

        Prefix parents may already exist, but the prefix itself must be new.
        Source directory bytes and empty directories are preserved. The source
        must remain stable throughout copying, as required by the archive core.
        """
        self._require_active()
        try:
            validate_relative_path(prefix)
            if prefix.casefold() in self._names:
                raise ArchiveError("Each supplied tree requires a new archive prefix.")
            root = safe_directory(source)
            self._check_source(root, directory=True)
            inventory = scan_tree(root, self._limits)
            prefixed_directories = (prefix, *(f"{prefix}/{path}" for path in inventory.directories))
            planned_directories = self._plan(
                prefixed_directories,
                tuple((f"{prefix}/{item.path}", item.size_bytes) for item in inventory.files),
            )
            for path in planned_directories:
                if path == prefix or not path.startswith(prefix + "/"):
                    (self._payload / path).mkdir()
            records = copy_tree(root, self._payload / prefix, inventory, self._limits)
            self._record(
                planned_directories,
                tuple(FileRecord(f"{prefix}/{item.path}", item.size_bytes, item.sha256) for item in records),
            )
            return Manifest(inventory.directories, records)
        except BaseException:
            self._failed = True
            raise

    def add_file(self, source: Path, path: str) -> FileRecord:
        """Copy one regular file with a bounded buffer into a new archive path.

        Individual file inputs may share a parent with the destination. Their
        parent directories are validated, but unrelated siblings are not read.
        """
        self._require_active()
        try:
            root = safe_directory(source.parent)
            selected = root / source.name
            self._check_source(selected, directory=False)
            with open_regular(selected) as stream:
                info = os.fstat(stream.fileno())
            state = FileState(
                selected.name,
                info.st_size,
                (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns),
            )
            directories = self._plan((), ((path, state.size_bytes),))
            for directory in directories:
                (self._payload / directory).mkdir()
            with (self._payload / path).open("xb") as output:
                copied = stream_file(root, state, self._limits, output)
            record = FileRecord(path, copied.size_bytes, copied.sha256)
            self._record(directories, (record,))
            return record
        except BaseException:
            self._failed = True
            raise

    def add_bytes(self, path: str, data: bytes) -> FileRecord:
        """Write already-materialized application metadata under archive limits.

        Large source files belong in add_file or add_tree. This method does not
        claim to bound memory already allocated by its caller.
        """
        self._require_active()
        try:
            if not isinstance(data, bytes):
                raise ArchiveError("Generated archive content must be immutable bytes.")
            directories = self._plan((), ((path, len(data)),))
            for directory in directories:
                (self._payload / directory).mkdir()
            with (self._payload / path).open("xb") as output:
                if output.write(data) != len(data):
                    raise ArchiveError("The generated archive file was not fully written.")
            record = FileRecord(path, len(data), hashlib.sha256(data).hexdigest())
            self._record(directories, (record,))
            return record
        except BaseException:
            self._failed = True
            raise

    def _seal(self, stage: Path) -> Manifest:
        self._require_active()
        self._active = False
        manifest = Manifest(
            tuple(sorted(self._directories)),
            tuple(self._files[path] for path in sorted(self._files)),
        )
        data = manifest.to_bytes()
        parse_manifest(data, self._limits)
        with (stage / MANIFEST_NAME).open("xb") as output:
            output.write(data)
        if not _verify(stage, manifest, self._limits).verified:
            raise ArchiveError("The assembled archive failed local integrity verification.")
        return manifest


@contextmanager
def assembling_archive(destination: Path, *, limits: Limits | None = None) -> Iterator[ArchiveAssembly]:
    """Publish one verified composite archive without replacing existing data.

    Each successful addition writes source bytes once. Context exit performs a
    separate verification read, canonical manifest validation, and the same
    atomic no-replace publication used by ordinary archive creation. Failures,
    including cancellation, remove only this operation's staging directory.
    This is an atomic visibility boundary, not fsync-based crash durability.
    """
    active_limits = limits or Limits()
    target = Path(os.path.abspath(destination))
    safe_directory(target.parent)
    if os.path.lexists(target):
        raise ArchiveError("The destination already exists; choose a new destination.")
    assembly: ArchiveAssembly | None = None
    try:
        with _staging(target) as stage:
            payload = stage / PAYLOAD_NAME
            payload.mkdir()
            assembly = ArchiveAssembly(payload, target, active_limits)
            yield assembly
            manifest = assembly._seal(stage)
        assembly._payload = target / PAYLOAD_NAME
        assembly._manifest = manifest
    finally:
        if assembly is not None:
            assembly._active = False
