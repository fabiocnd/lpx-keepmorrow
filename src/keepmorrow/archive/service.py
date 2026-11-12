"""Directory archive operations with staging and explicit verification stages.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..control import temporary_parent
from .filesystem import copy_tree, destination_path, open_regular, publish_directory, safe_directory, scan_tree, stream_file
from .model import (
    MANIFEST_NAME,
    PAYLOAD_NAME,
    ArchiveError,
    Limits,
    Manifest,
    VerificationIssue,
    VerificationReport,
    parse_manifest,
)


@contextmanager
def _staging(destination: Path) -> Iterator[Path]:
    stage = Path(tempfile.mkdtemp(prefix=".keepmorrow-", dir=temporary_parent(destination.parent)))
    try:
        yield stage
        if os.path.lexists(destination):
            raise ArchiveError("The destination appeared during processing; publication was canceled.")
        # Publication never replaces a competing destination. Atomic visibility
        # still does not establish crash durability; this slice does not fsync.
        publish_directory(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _load_manifest(archive: Path, limits: Limits) -> Manifest:
    with open_regular(archive / MANIFEST_NAME) as source:
        before = os.fstat(source.fileno())
        if before.st_size > limits.max_manifest_bytes:
            raise ArchiveError("The manifest exceeds the configured byte limit.")
        # Allocate for the observed file, not the maximum allowed manifest.
        # One extra byte detects growth without accepting an unbounded read.
        data = source.read(before.st_size + 1)
        after = os.fstat(source.fileno())
        if (len(data) != before.st_size or after.st_size != before.st_size
                or after.st_mtime_ns != before.st_mtime_ns or after.st_ctime_ns != before.st_ctime_ns):
            raise ArchiveError("The manifest changed while it was being read.")
    return parse_manifest(data, limits)


def _verify(archive: Path, manifest: Manifest, limits: Limits) -> VerificationReport:
    payload = safe_directory(archive / PAYLOAD_NAME)
    actual = scan_tree(payload, limits)
    issues: list[VerificationIssue] = []
    root_names: list[str] = []
    for item in archive.iterdir():
        if len(root_names) >= limits.max_entries + 2:
            raise ArchiveError("The archive root exceeds the configured entry limit.")
        root_names.append(item.name)
    for name in sorted(root_names):
        if name not in {MANIFEST_NAME, PAYLOAD_NAME}:
            issues.append(VerificationIssue("unexpected", name))
    expected_dirs = set(manifest.directories)
    actual_dirs = set(actual.directories)
    for path in sorted(expected_dirs - actual_dirs):
        issues.append(VerificationIssue("missing_directory", path))
    for path in sorted(actual_dirs - expected_dirs):
        issues.append(VerificationIssue("unexpected_directory", path))
    expected_files = {record.path: record for record in manifest.files}
    actual_files = {state.path: state for state in actual.files}
    for path in sorted(expected_files.keys() - actual_files.keys()):
        issues.append(VerificationIssue("missing", path))
    for path in sorted(actual_files.keys() - expected_files.keys()):
        issues.append(VerificationIssue("unexpected", path))
    for path in sorted(expected_files.keys() & actual_files.keys()):
        try:
            observed = stream_file(payload, actual_files[path], limits)
            if observed != expected_files[path]:
                issues.append(VerificationIssue("changed", path))
        except (OSError, ArchiveError):
            issues.append(VerificationIssue("unreadable_or_changed_during_verification", path))
    if scan_tree(payload, limits) != actual:
        raise ArchiveError("The archive payload changed during verification.")
    return VerificationReport(len(manifest.files), sum(item.size_bytes for item in manifest.files), tuple(issues))


def verify_archive(archive: Path, *, limits: Limits | None = None) -> VerificationReport:
    """Reconcile local file bytes and inventory against a validated manifest.

    A matching self-contained manifest proves local consistency. It does not
    authenticate the publisher or detect an attacker replacing both bytes and
    hashes. Trust must come from a separately secured manifest or signature.
    """
    active_limits = limits or Limits()
    root = safe_directory(archive)
    return _verify(root, _load_manifest(root, active_limits), active_limits)


def load_manifest(archive: Path, *, limits: Limits | None = None) -> Manifest:
    """Read and validate bounded archive metadata without verifying payload bytes.

    This is useful for inventory selection after an explicit integrity check.
    It never establishes that the listed files exist or match their hashes;
    callers needing that guarantee must also invoke verify_archive.
    """
    active_limits = limits or Limits()
    root = safe_directory(archive)
    return _load_manifest(root, active_limits)


def create_archive(source: Path, destination: Path, *, limits: Limits | None = None) -> Manifest:
    """Preserve every supported supplied file and directory, then verify copies."""
    active_limits = limits or Limits()
    root = safe_directory(source)
    target = destination_path(destination, root)
    inventory = scan_tree(root, active_limits)
    with _staging(target) as stage:
        payload = stage / PAYLOAD_NAME
        payload.mkdir()
        records = copy_tree(root, payload, inventory, active_limits)
        manifest = Manifest(inventory.directories, records)
        data = manifest.to_bytes()
        parse_manifest(data, active_limits)
        (stage / MANIFEST_NAME).write_bytes(data)
        if not _verify(stage, manifest, active_limits).verified:
            raise ArchiveError("The staged archive failed local integrity verification.")
    return manifest


def restore_archive(archive: Path, destination: Path, *, limits: Limits | None = None) -> Manifest:
    """Restore verified bytes into a new directory; preserve the archive itself."""
    active_limits = limits or Limits()
    root = safe_directory(archive)
    target = destination_path(destination, root)
    manifest = _load_manifest(root, active_limits)
    if not _verify(root, manifest, active_limits).verified:
        raise ArchiveError("The archive failed verification; recovery was canceled.")
    payload = root / PAYLOAD_NAME
    inventory = scan_tree(payload, active_limits)
    with _staging(target) as stage:
        records = copy_tree(payload, stage, inventory, active_limits)
        if Manifest(inventory.directories, records) != manifest:
            raise ArchiveError("The archive changed after verification; recovery was canceled.")
        restored = scan_tree(stage, active_limits)
        restored_records = tuple(stream_file(stage, item, active_limits) for item in restored.files)
        if Manifest(restored.directories, restored_records) != manifest:
            raise ArchiveError("The staged recovery failed integrity verification.")
    return manifest

