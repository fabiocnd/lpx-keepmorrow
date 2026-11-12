"""Deterministic recovery ZIPs around the unchanged directory-archive contract.

The wrapper is an interchange container, not a native ChatGPT restoration
format. Both directions verify collection semantics and authoritative bytes.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import BinaryIO

from ..archive.filesystem import (
    FileState, Inventory, destination_path, open_regular, publish_directory,
    safe_directory, scan_tree,
)
from ..archive.model import FileRecord, Limits, Manifest, parse_manifest
from ..catalog.model import CatalogLimits
from ..catalog.service import LoadedCollection, load_collection
from ..control import temporary_parent
from ..importers.zip_intake import prepared_export
from .model import (
    Checkpoint, PackageLimits, PackageResult, TransferError, TransferLimitExceeded,
    checkpoint_if_requested,
)


def _signature(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _check_binding(source: BinaryIO, path: Path, initial: os.stat_result) -> None:
    observed = os.fstat(source.fileno())
    binding = path.lstat()
    if (_signature(observed) != _signature(initial) or not stat.S_ISREG(binding.st_mode)
            or not os.path.samestat(observed, binding) or binding.st_size != observed.st_size
            or binding.st_mtime_ns != observed.st_mtime_ns
            or (binding.st_mode & ~0o111) != (observed.st_mode & ~0o111)):
        raise TransferError("The package source changed during processing.")


def _budgets(package: PackageLimits, archive: Limits | None) -> tuple[Limits, Limits]:
    """Keep payload and wrapper limits independent while enforcing both profiles.

    The wrapper accounts for manifest.json and payload/ in addition to the
    archive inventory. Encoded-container allowance does not increase the
    permitted aggregate expanded size.
    """
    original = archive or Limits()
    payload = replace(
        original, max_total_bytes=min(original.max_total_bytes, package.max_expanded_bytes),
        max_file_bytes=min(original.max_file_bytes, package.max_expanded_bytes),
        chunk_bytes=package.chunk_bytes,
    )
    wrapper = Limits(
        max_entries=min(package.max_wrapper_entries, original.max_entries + 2),
        max_total_bytes=package.max_expanded_bytes,
        max_file_bytes=max(package.max_encoded_bytes, package.max_expanded_bytes),
        max_manifest_bytes=package.max_metadata_bytes,
        chunk_bytes=package.chunk_bytes,
    )
    return payload, wrapper


def _manifest_bytes(root: Path, manifest: Manifest, limits: Limits) -> bytes:
    path = root / "manifest.json"
    with open_regular(path) as source:
        initial = os.fstat(source.fileno())
        if initial.st_size > limits.max_manifest_bytes:
            raise TransferLimitExceeded("The collection manifest exceeds its byte budget.")
        data = source.read(initial.st_size + 1)
        _check_binding(source, path, initial)
    if len(data) != initial.st_size or parse_manifest(data, limits) != manifest:
        raise TransferError("The collection manifest changed after verification.")
    return data


def _inventory(root: Path, manifest: Manifest, wrapper_limits: Limits) -> Inventory:
    actual = scan_tree(root, wrapper_limits)
    directories = tuple(sorted(["payload", *("payload/" + path for path in manifest.directories)]))
    files = {"manifest.json", *("payload/" + item.path for item in manifest.files)}
    if actual.directories != directories or {item.path for item in actual.files} != files:
        raise TransferError("The recovery wrapper must contain only manifest.json and its declared payload.")
    return actual


def _expected_files(manifest: Manifest, manifest_bytes: bytes) -> dict[str, FileRecord]:
    expected = {"payload/" + item.path: FileRecord("payload/" + item.path, item.size_bytes, item.sha256)
                for item in manifest.files}
    expected["manifest.json"] = FileRecord(
        "manifest.json", len(manifest_bytes), hashlib.sha256(manifest_bytes).hexdigest(),
    )
    return expected


def _copy_verified(
    root: Path, state: FileState, output: BinaryIO, expected: FileRecord,
    limits: Limits, checkpoint: Checkpoint | None,
) -> None:
    count, digest = 0, hashlib.sha256()
    path = root / state.path
    with open_regular(path) as source:
        initial = os.fstat(source.fileno())
        if _signature(initial) != state.signature or initial.st_size != expected.size_bytes:
            raise TransferError("A package source changed after inventory.")
        while True:
            checkpoint_if_requested(checkpoint)
            block = source.read(limits.chunk_bytes)
            if not block:
                break
            count += len(block)
            if count > expected.size_bytes:
                raise TransferError("A package source grew during processing.")
            output.write(block)
            digest.update(block)
        _check_binding(source, path, initial)
    if count != expected.size_bytes or digest.hexdigest() != expected.sha256:
        raise TransferError("A package source failed SHA-256 or byte-count verification.")


def _stream_digest(
    source: BinaryIO, maximum_bytes: int, chunk_bytes: int, checkpoint: Checkpoint | None,
) -> tuple[int, str]:
    count, digest = 0, hashlib.sha256()
    while True:
        checkpoint_if_requested(checkpoint)
        block = source.read(chunk_bytes)
        if not block:
            break
        count += len(block)
        if count > maximum_bytes:
            raise TransferLimitExceeded("The encoded recovery package exceeds its byte budget.")
        digest.update(block)
    return count, digest.hexdigest()


class _BoundedOutput:
    """Enforce the encoded limit before ZIP headers or content reach disk.

    ZIP seeks back to update local headers. Charge the highest written offset,
    not the sum of writes, so those bounded metadata updates are not double billed.
    """

    def __init__(self, output: BinaryIO, maximum_bytes: int, checkpoint: Checkpoint | None) -> None:
        self.output = output
        self.maximum_bytes = maximum_bytes
        self.checkpoint = checkpoint

    def write(self, data: bytes) -> int:
        checkpoint_if_requested(self.checkpoint)
        if self.output.tell() + len(data) > self.maximum_bytes:
            raise TransferLimitExceeded("The encoded recovery package exceeds its byte budget.")
        return self.output.write(data)

    def tell(self) -> int:
        return self.output.tell()

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        return self.output.seek(offset, whence)

    def flush(self) -> None:
        self.output.flush()


def _zip_info(path: str, *, directory: bool, size_bytes: int = 0) -> zipfile.ZipInfo:
    """Fix container metadata so source timestamps and host modes cannot vary it."""
    info = zipfile.ZipInfo(path + "/" if directory else path, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = ((stat.S_IFDIR | 0o700) << 16) | 0x10 if directory else (stat.S_IFREG | 0o600) << 16
    info.file_size = size_bytes
    return info


def _result(
    collection: LoadedCollection, manifest_bytes: bytes, encoded: tuple[int, str],
) -> PackageResult:
    return PackageResult(
        size_bytes=encoded[0], sha256=encoded[1],
        expanded_size_bytes=len(manifest_bytes) + sum(item.size_bytes for item in collection.manifest.files),
        file_count=len(collection.manifest.files), directory_count=len(collection.manifest.directories),
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        collection_scope=collection.document["scope"],
    )


def pack_collection(
    source: Path, destination: Path, *, limits: PackageLimits | None = None,
    archive_limits: Limits | None = None, catalog_limits: CatalogLimits | None = None,
    checkpoint: Checkpoint | None = None, before_publish: Checkpoint | None = None,
) -> PackageResult:
    """Verify a collection and publish one deterministic ZIP without replacement.

    Preserve manifest bytes exactly. Stored members use canonical ordering and
    fixed metadata; no compression, wall clock, or model influences the bytes.
    Independently extract and validate the staged package before publication.
    ``before_publish`` is the caller's final journal/authorization fence.
    These verification passes require temporary space for both the encoded ZIP
    and its extraction. Byte buffers are bounded, but inventory and decoded
    catalog metadata have separate memory costs. The caller supplies authority;
    producing a local package does not establish delivery or recipient consent.
    """
    package = limits or PackageLimits()
    payload_limits, wrapper_limits = _budgets(package, archive_limits)
    root = safe_directory(source)
    target = destination_path(destination, root)
    checkpoint_if_requested(checkpoint)
    collection = load_collection(root, limits=payload_limits, catalog_limits=catalog_limits)
    manifest_data = _manifest_bytes(root, collection.manifest, payload_limits)
    inventory = _inventory(root, collection.manifest, wrapper_limits)
    central_bytes = sum(46 + len((path + "/").encode("utf-8")) for path in inventory.directories)
    central_bytes += sum(46 + len(item.path.encode("utf-8")) for item in inventory.files)
    if central_bytes > package.max_metadata_bytes:
        raise TransferLimitExceeded("The package central directory exceeds its metadata budget.")
    expected = _expected_files(collection.manifest, manifest_data)
    with tempfile.TemporaryDirectory(prefix=".keepmorrow-transfer-", dir=temporary_parent(target.parent)) as temporary:
        staged = Path(temporary) / "recovery.zip"
        descriptor = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        with os.fdopen(descriptor, "wb") as output:
            bounded = _BoundedOutput(output, package.max_encoded_bytes, checkpoint)
            with zipfile.ZipFile(bounded, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
                for directory in inventory.directories:
                    archive.writestr(_zip_info(directory, directory=True), b"")
                for state in inventory.files:
                    with archive.open(_zip_info(state.path, directory=False, size_bytes=state.size_bytes), "w") as member:
                        _copy_verified(root, state, member, expected[state.path], wrapper_limits, checkpoint)
        checkpoint_if_requested(checkpoint)
        with prepared_export(staged, limits=wrapper_limits) as extracted:
            checked = load_collection(extracted.directory, limits=payload_limits, catalog_limits=catalog_limits)
            if (checked.manifest != collection.manifest
                    or _manifest_bytes(extracted.directory, checked.manifest, payload_limits) != manifest_data):
                raise TransferError("The staged package did not preserve the collection manifest.")
            _inventory(extracted.directory, checked.manifest, wrapper_limits)
        with open_regular(staged) as input_file:
            initial = os.fstat(input_file.fileno())
            encoded = _stream_digest(input_file, package.max_encoded_bytes, package.chunk_bytes, checkpoint)
            _check_binding(input_file, staged, initial)
        if scan_tree(root, wrapper_limits) != inventory:
            raise TransferError("The source collection changed during packaging.")
        result = _result(collection, manifest_data, encoded)
        checkpoint_if_requested(checkpoint)
        checkpoint_if_requested(before_publish)
        publish_directory(staged, target)
        return result


def unpack_collection(
    package_path: Path, destination: Path, *, limits: PackageLimits | None = None,
    archive_limits: Limits | None = None, catalog_limits: CatalogLimits | None = None,
    checkpoint: Checkpoint | None = None, before_publish: Checkpoint | None = None,
) -> PackageResult:
    """Extract into a new archive directory and verify bytes plus catalog semantics.

    The guarded ZIP intake rejects traversal, links, collisions, unsupported
    features, CRC failures, and declared/actual expansion overflow. Its temporary
    extraction is copied into a private stage, preserving original manifest
    bytes. The default stage shares the destination filesystem; an execution
    scope that overrides temporary storage must preserve that requirement.
    Publication follows source revalidation and the caller's final fence.
    The input package stays unchanged, and the destination must not exist.
    """
    package = limits or PackageLimits()
    payload_limits, wrapper_limits = _budgets(package, archive_limits)
    selected = Path(os.path.abspath(package_path))
    safe_directory(selected.parent)
    target = Path(os.path.abspath(destination))
    safe_directory(target.parent)
    if os.path.lexists(target):
        raise TransferError("The destination already exists; choose a new destination.")
    checkpoint_if_requested(checkpoint)
    with tempfile.TemporaryDirectory(prefix=".keepmorrow-transfer-", dir=temporary_parent(target.parent)) as temporary:
        staged = Path(temporary) / "collection"
        staged.mkdir(mode=0o700)
        with open_regular(selected) as input_file:
            initial = os.fstat(input_file.fileno())
            if initial.st_size > package.max_encoded_bytes:
                raise TransferLimitExceeded("The encoded recovery package exceeds its byte budget.")
            encoded = _stream_digest(input_file, package.max_encoded_bytes, package.chunk_bytes, checkpoint)
            _check_binding(input_file, selected, initial)
            with prepared_export(selected, limits=wrapper_limits) as extracted:
                checkpoint_if_requested(checkpoint)
                collection = load_collection(extracted.directory, limits=payload_limits, catalog_limits=catalog_limits)
                manifest_data = _manifest_bytes(extracted.directory, collection.manifest, payload_limits)
                inventory = _inventory(extracted.directory, collection.manifest, wrapper_limits)
                expected = _expected_files(collection.manifest, manifest_data)
                for directory in inventory.directories:
                    checkpoint_if_requested(checkpoint)
                    (staged / directory).mkdir()
                for state in inventory.files:
                    with (staged / state.path).open("xb") as output:
                        _copy_verified(extracted.directory, state, output, expected[state.path], wrapper_limits, checkpoint)
                checked = load_collection(staged, limits=payload_limits, catalog_limits=catalog_limits)
                if (checked.manifest != collection.manifest
                        or _manifest_bytes(staged, checked.manifest, payload_limits) != manifest_data):
                    raise TransferError("The staged collection did not preserve the supplied manifest.")
                if scan_tree(extracted.directory, wrapper_limits) != inventory:
                    raise TransferError("The extracted package changed during verification.")
            _check_binding(input_file, selected, initial)
        result = _result(collection, manifest_data, encoded)
        checkpoint_if_requested(checkpoint)
        checkpoint_if_requested(before_publish)
        publish_directory(staged, target)
        return result
