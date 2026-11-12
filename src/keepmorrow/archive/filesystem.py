"""Bounded file I/O for stable, user-controlled directory trees.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .model import ArchiveError, FileRecord, Limits, validate_inventory, validate_relative_path

_AT_FDCWD = -100
_RENAME_NOREPLACE = 1


@dataclass(frozen=True, slots=True)
class FileState:
    path: str
    size_bytes: int
    signature: tuple[int, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class Inventory:
    directories: tuple[str, ...]
    files: tuple[FileState, ...]


def _signature(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def safe_directory(path: Path) -> Path:
    """Reject observed symlinks in the root and its existing ancestors."""
    result = Path(os.path.abspath(path))
    for component in reversed((result, *result.parents)):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ArchiveError("The directory and its ancestors must be ordinary directories.")
    return result


def destination_path(path: Path, source: Path) -> Path:
    result = Path(os.path.abspath(path))
    safe_directory(result.parent)
    if os.path.lexists(result):
        raise ArchiveError("The destination already exists; choose a new destination.")
    if result.is_relative_to(source):
        raise ArchiveError("The destination must be outside the source directory.")
    return result


def publish_directory(stage: Path, destination: Path) -> None:
    """Publish a staged tree without replacing a competing destination.

    Python's POSIX rename may replace an empty directory. Linux therefore uses
    RENAME_NOREPLACE; Windows already rejects an existing destination. Other
    platforms fail explicitly until an equivalent primitive has been verified.
    """
    if os.name == "nt":
        stage.rename(destination)
        return
    if not sys.platform.startswith("linux"):
        raise ArchiveError("Atomic no-replace publication is unsupported on this platform.")
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise ArchiveError("This runtime does not provide atomic no-replace directory publication.")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(_AT_FDCWD, os.fsencode(stage), _AT_FDCWD, os.fsencode(destination), _RENAME_NOREPLACE) == 0:
        return
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ArchiveError("The destination already exists; publication was canceled.")
    if error in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
        raise ArchiveError("The filesystem does not support atomic no-replace publication.")
    raise OSError(error, os.strerror(error))


def scan_tree(root: Path, limits: Limits) -> Inventory:
    """Inventory without following links; metadata memory is O(entry count).

    Entries are bounded while enumerating, before the final O(n log n) sort.
    Sorting a complete unbounded scandir result would defeat the entry limit.
    """
    pending = [(root, "")]
    directories: list[str] = []
    files: list[FileState] = []
    total_bytes = 0
    while pending:
        current, prefix = pending.pop()
        if not stat.S_ISDIR(current.lstat().st_mode):
            raise ArchiveError("A directory changed type during inventory.")
        with os.scandir(current) as entries:
            for entry in entries:
                relative = f"{prefix}/{entry.name}" if prefix else entry.name
                validate_relative_path(relative)
                # Windows directory-entry metadata omits device and file IDs.
                # Fetch complete identity before comparing it with descriptor
                # metadata; otherwise an unchanged file appears to be replaced.
                info = os.stat(entry.path, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    directories.append(relative)
                    pending.append((Path(entry.path), relative))
                elif stat.S_ISREG(info.st_mode):
                    if os.name == "nt":
                        # Windows path stat may expose creation time as ctime,
                        # while fstat exposes metadata change time. Bind the
                        # no-follow path identity before recording the complete
                        # descriptor signature used by subsequent read checks.
                        with open_regular(current / entry.name) as source:
                            descriptor_info = os.fstat(source.fileno())
                        # Path stat also synthesizes execute bits from filename
                        # extensions. Keep type and read/write bits comparable.
                        if (not os.path.samestat(info, descriptor_info)
                                or (info.st_mode & ~0o111) != (descriptor_info.st_mode & ~0o111)
                                or info.st_size != descriptor_info.st_size
                                or info.st_mtime_ns != descriptor_info.st_mtime_ns):
                            raise ArchiveError("A source file changed during inventory.")
                        info = descriptor_info
                    if info.st_size > limits.max_file_bytes:
                        raise ArchiveError("A source file exceeds the configured byte limit.")
                    total_bytes += info.st_size
                    if total_bytes > limits.max_total_bytes:
                        raise ArchiveError("Source files exceed the configured total-byte limit.")
                    files.append(FileState(relative, info.st_size, _signature(info)))
                else:
                    raise ArchiveError("Symbolic links and non-regular files are unsupported.")
                if len(directories) + len(files) > limits.max_entries:
                    raise ArchiveError("The source exceeds the configured entry limit.")
    directories.sort()
    files.sort(key=lambda item: item.path)
    # The inventory validator also checks parent topology and portable collisions.
    validate_inventory(directories, [FileRecord(item.path, item.size_bytes, "0" * 64) for item in files], limits)
    return Inventory(tuple(directories), tuple(files))


def open_regular(path: Path) -> BinaryIO:
    """Open a regular file and refuse a leaf symlink on supported platforms."""
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ArchiveError("The input is not an ordinary file.")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ArchiveError("The opened input is not an ordinary file.")
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def stream_file(root: Path, state: FileState, limits: Limits, output: BinaryIO | None = None) -> FileRecord:
    """Hash and optionally copy a file with bounded memory and mutation checks."""
    digest = hashlib.sha256()
    count = 0
    with open_regular(root / state.path) as source:
        if _signature(os.fstat(source.fileno())) != state.signature:
            raise ArchiveError("A source file changed after inventory.")
        while block := source.read(limits.chunk_bytes):
            count += len(block)
            if count > limits.max_file_bytes or count > state.size_bytes:
                raise ArchiveError("A source file grew during processing.")
            digest.update(block)
            if output is not None:
                output.write(block)
        if count != state.size_bytes or _signature(os.fstat(source.fileno())) != state.signature:
            raise ArchiveError("A source file changed during processing.")
    return FileRecord(state.path, count, digest.hexdigest())


def copy_tree(source: Path, destination: Path, inventory: Inventory, limits: Limits) -> tuple[FileRecord, ...]:
    for relative in inventory.directories:
        (destination / relative).mkdir()
    records: list[FileRecord] = []
    for state in inventory.files:
        with (destination / state.path).open("xb") as output:
            records.append(stream_file(source, state, limits, output))
    if scan_tree(source, limits) != inventory:
        raise ArchiveError("The source tree changed during processing.")
    return tuple(records)

