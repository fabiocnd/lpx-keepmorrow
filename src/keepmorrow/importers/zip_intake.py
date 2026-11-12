"""Prepare explicitly selected directory or ZIP exports without changing sources.

The ZIP profile accepts single-disk, non-ZIP64 stored/deflated archives. It
validates bounded central-directory metadata before ``zipfile`` materializes
entry objects, then validates local records and streams decompression itself.
This avoids treating a declared uncompressed size as proof of the actual size.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import os
import stat
import struct
import tempfile
import zipfile
import zlib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterator

from ..control import checkpoint, temporary_parent

from ..archive.filesystem import open_regular, safe_directory, scan_tree
from ..archive.model import ArchiveError, Limits, validate_relative_path

_END = struct.Struct("<4s4H2IH")
_CENTRAL = struct.Struct("<4s6H3I5H2I")
_LOCAL = struct.Struct("<4s5H3I2H")
_END_SIGNATURE = b"PK\x05\x06"
_CENTRAL_SIGNATURE = b"PK\x01\x02"
_LOCAL_SIGNATURE = b"PK\x03\x04"
_DESCRIPTOR_SIGNATURE = 0x08074B50
_SUPPORTED_FLAGS = 0x080E  # UTF-8, data descriptor, and deflate level hints.


@dataclass(frozen=True, slots=True)
class PreparedExport:
    """A scoped extraction and, for ZIP input, the unchanged original ZIP path."""

    directory: Path
    original_zip: Path | None


@dataclass(frozen=True, slots=True)
class _EndRecord:
    entry_count: int
    central_offset: int
    central_bytes: int


@dataclass(frozen=True, slots=True)
class _Member:
    info: zipfile.ZipInfo
    path: str
    is_directory: bool
    data_offset: int
    record_end: int


def _read_exact(source: BinaryIO, size_bytes: int) -> bytes:
    data = source.read(size_bytes)
    if len(data) != size_bytes:
        raise ArchiveError("The ZIP contains a truncated record.")
    return data


def _signature(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _check_source(source: BinaryIO, path: Path, expected: os.stat_result) -> None:
    observed = os.fstat(source.fileno())
    path_info = path.lstat()
    safe_directory(path.parent)
    if (_signature(observed) != _signature(expected)
            or not stat.S_ISREG(path_info.st_mode)
            or not os.path.samestat(path_info, observed)
            or path_info.st_size != observed.st_size
            or path_info.st_mtime_ns != observed.st_mtime_ns
            or (path_info.st_mode & ~0o111) != (observed.st_mode & ~0o111)):
        raise ArchiveError("The source ZIP changed during processing.")


def _check_extra_fields(data: bytes) -> None:
    offset = 0
    while offset < len(data):
        if len(data) - offset < 4:
            raise ArchiveError("The ZIP contains malformed extra-field metadata.")
        field_id, field_bytes = struct.unpack_from("<HH", data, offset)
        offset += 4
        if field_id == 0x0001:
            raise ArchiveError("ZIP64 exports are not supported by this intake profile.")
        if field_bytes > len(data) - offset:
            raise ArchiveError("The ZIP contains malformed extra-field metadata.")
        offset += field_bytes


def _preflight_directory(source: BinaryIO, size_bytes: int, limits: Limits) -> _EndRecord:
    """Bound metadata allocation before constructing ZipFile's complete index."""
    if size_bytes < _END.size:
        raise ArchiveError("The input is not a supported ZIP export.")
    tail_offset = max(0, size_bytes - (_END.size + 65535))
    source.seek(tail_offset)
    tail = _read_exact(source, size_bytes - tail_offset)
    candidate = tail.rfind(_END_SIGNATURE)
    fields: tuple[object, ...] | None = None
    end_offset = 0
    while candidate >= 0:
        if candidate + _END.size <= len(tail):
            possible = _END.unpack_from(tail, candidate)
            if candidate + _END.size + possible[7] == len(tail):
                fields = possible
                end_offset = tail_offset + candidate
                break
        candidate = tail.rfind(_END_SIGNATURE, 0, candidate)
    if fields is None:
        raise ArchiveError("The ZIP end record is absent, truncated, or has trailing data.")
    _, disk_number, directory_disk, disk_count, total_count, central_bytes, central_offset, _ = fields
    if (disk_number != 0 or directory_disk != 0 or disk_count != total_count):
        raise ArchiveError("Multipart ZIP exports are unsupported.")
    if (total_count == 0xFFFF or central_bytes == 0xFFFFFFFF or central_offset == 0xFFFFFFFF):
        raise ArchiveError("ZIP64 exports are not supported by this intake profile.")
    if end_offset >= 20:
        source.seek(end_offset - 20)
        if source.read(4) == b"PK\x06\x07":
            raise ArchiveError("ZIP64 exports are not supported by this intake profile.")
    if central_offset + central_bytes != end_offset:
        raise ArchiveError("The ZIP central-directory bounds are inconsistent.")
    if total_count > limits.max_entries:
        raise ArchiveError("The ZIP exceeds the configured entry limit.")
    if central_bytes > limits.max_manifest_bytes:
        raise ArchiveError("The ZIP central directory exceeds the configured metadata-byte limit.")
    source.seek(central_offset)
    remaining = central_bytes
    observed_count = 0
    while remaining:
        checkpoint()
        if remaining < _CENTRAL.size or observed_count >= limits.max_entries:
            raise ArchiveError("The ZIP central directory is malformed or exceeds entry limits.")
        header = _CENTRAL.unpack(_read_exact(source, _CENTRAL.size))
        if header[0] != _CENTRAL_SIGNATURE:
            raise ArchiveError("The ZIP central directory contains an unsupported record.")
        name_bytes, extra_bytes, comment_bytes = header[10:13]
        record_bytes = _CENTRAL.size + name_bytes + extra_bytes + comment_bytes
        if record_bytes > remaining:
            raise ArchiveError("The ZIP central directory contains a truncated entry.")
        if header[8] == 0xFFFFFFFF or header[9] == 0xFFFFFFFF or header[16] == 0xFFFFFFFF:
            raise ArchiveError("ZIP64 exports are not supported by this intake profile.")
        if header[13] != 0:
            raise ArchiveError("Multipart ZIP exports are unsupported.")
        source.seek(name_bytes, os.SEEK_CUR)
        _check_extra_fields(_read_exact(source, extra_bytes))
        source.seek(comment_bytes, os.SEEK_CUR)
        observed_count += 1
        remaining -= record_bytes
    if observed_count != total_count:
        raise ArchiveError("The ZIP central-directory entry count is inconsistent.")
    return _EndRecord(total_count, central_offset, central_bytes)


def _local_record(source: BinaryIO, info: zipfile.ZipInfo, central_offset: int) -> tuple[int, int]:
    if info.header_offset < 0 or info.header_offset + _LOCAL.size > central_offset:
        raise ArchiveError("A ZIP local record is outside the payload bounds.")
    source.seek(info.header_offset)
    header = _LOCAL.unpack(_read_exact(source, _LOCAL.size))
    if header[0] != _LOCAL_SIGNATURE or header[1] > 20:
        raise ArchiveError("A ZIP local record has an unsupported format.")
    if header[2] != info.flag_bits or header[3] != info.compress_type:
        raise ArchiveError("ZIP local and central metadata disagree.")
    name_bytes, extra_bytes = header[9:11]
    if name_bytes > 4097 or source.tell() + name_bytes + extra_bytes > central_offset:
        raise ArchiveError("A ZIP local name or extra field exceeds its bounds.")
    encoding = "utf-8" if info.flag_bits & 0x0800 else "cp437"
    if _read_exact(source, name_bytes) != info.orig_filename.encode(encoding):
        raise ArchiveError("ZIP local and central filenames disagree.")
    _check_extra_fields(_read_exact(source, extra_bytes))
    data_offset = source.tell()
    record_end = data_offset + info.compress_size
    if record_end > central_offset:
        raise ArchiveError("A ZIP member overlaps the central directory.")
    if info.flag_bits & 0x0008:
        if (header[6] not in (0, info.CRC) or header[7] not in (0, info.compress_size)
                or header[8] not in (0, info.file_size)):
            raise ArchiveError("ZIP local and central metadata disagree.")
        source.seek(record_end)
        if record_end + 12 > central_offset:
            raise ArchiveError("A ZIP data descriptor is truncated.")
        descriptor = struct.unpack("<III", _read_exact(source, 12))
        if descriptor[0] == _DESCRIPTOR_SIGNATURE:
            if record_end + 16 > central_offset:
                raise ArchiveError("A ZIP data descriptor is truncated.")
            descriptor = (descriptor[1], descriptor[2], struct.unpack("<I", _read_exact(source, 4))[0])
            record_end += 16
        else:
            record_end += 12
        if descriptor != (info.CRC, info.compress_size, info.file_size):
            raise ArchiveError("ZIP data descriptor and central metadata disagree.")
    elif header[6:9] != (info.CRC, info.compress_size, info.file_size):
        raise ArchiveError("ZIP local and central metadata disagree.")
    return data_offset, record_end


def _plan_members(
    source: BinaryIO, entries: list[zipfile.ZipInfo], end: _EndRecord, limits: Limits,
) -> tuple[tuple[str, ...], tuple[_Member, ...]]:
    declared: set[str] = set()
    paths: dict[str, bool] = {}
    folded_paths: dict[str, str] = {}
    members: list[_Member] = []
    total_bytes = 0
    for info in entries:
        checkpoint()
        if (info.filename != info.orig_filename or info.flag_bits & ~_SUPPORTED_FLAGS
                or info.extract_version > 20):
            raise ArchiveError("The ZIP uses unsupported names, flags, encryption, or extraction features.")
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ArchiveError("Only stored and deflated ZIP members are supported.")
        if info.compress_type == zipfile.ZIP_STORED and info.compress_size != info.file_size:
            raise ArchiveError("A stored ZIP member has inconsistent byte sizes.")
        is_directory = info.is_dir()
        relative = validate_relative_path(info.filename[:-1] if is_directory else info.filename)
        mode_type = stat.S_IFMT(info.external_attr >> 16)
        expected_type = stat.S_IFDIR if is_directory else stat.S_IFREG
        if mode_type not in (0, expected_type) or (info.external_attr & 0x10 and not is_directory):
            raise ArchiveError("ZIP symbolic links, special files, and inconsistent file types are unsupported.")
        if is_directory and info.file_size != 0:
            raise ArchiveError("A ZIP directory contains unexpected file data.")
        if info.file_size > limits.max_file_bytes:
            raise ArchiveError("A ZIP member exceeds the configured file-byte limit.")
        total_bytes += info.file_size
        if total_bytes > limits.max_total_bytes:
            raise ArchiveError("The ZIP exceeds the configured expanded-byte limit.")
        if relative in declared:
            raise ArchiveError("The ZIP contains duplicate paths.")
        declared.add(relative)
        components = [relative, *(str(parent) for parent in PurePosixPath(relative).parents if str(parent) != ".")]
        for index, path in enumerate(components):
            directory = is_directory if index == 0 else True
            key = path.casefold()
            if key in folded_paths and folded_paths[key] != path:
                raise ArchiveError("The ZIP contains case-colliding paths.")
            folded_paths[key] = path
            if path in paths and paths[path] != directory:
                raise ArchiveError("The ZIP contains a file/directory path conflict.")
            paths[path] = directory
            if len(paths) > limits.max_entries:
                raise ArchiveError("The ZIP exceeds the configured entry limit including parent directories.")
        data_offset, record_end = _local_record(source, info, end.central_offset)
        members.append(_Member(info, relative, is_directory, data_offset, record_end))
    physical = sorted(members, key=lambda item: item.info.header_offset)
    previous_end = 0
    if physical and physical[0].info.header_offset != 0:
        raise ArchiveError("Prefixed or self-extracting ZIP exports are unsupported.")
    if not physical and end.central_offset != 0:
        raise ArchiveError("An empty ZIP contains unsupported prefixed data.")
    for member in physical:
        checkpoint()
        if member.info.header_offset < previous_end:
            raise ArchiveError("ZIP members overlap one another.")
        previous_end = member.record_end
    directories = tuple(sorted(path for path, is_directory in paths.items() if is_directory))
    return directories, tuple(sorted(members, key=lambda item: item.path))


def _extract_member(source: BinaryIO, member: _Member, output: BinaryIO | None, limits: Limits) -> int:
    """Bound actual inflation and reject streams hidden by false size metadata."""
    info = member.info
    source.seek(member.data_offset)
    remaining = info.compress_size
    count = 0
    crc = 0
    inflater = zlib.decompressobj(-zlib.MAX_WBITS) if info.compress_type == zipfile.ZIP_DEFLATED else None

    def consume(block: bytes) -> None:
        nonlocal count, crc
        count += len(block)
        if count > info.file_size or count > limits.max_file_bytes:
            raise ArchiveError("A ZIP member expands beyond its declared or configured byte limit.")
        crc = zlib.crc32(block, crc)
        if output is not None:
            output.write(block)

    while remaining:
        checkpoint()
        block = _read_exact(source, min(limits.chunk_bytes, remaining))
        remaining -= len(block)
        if inflater is None:
            consume(block)
            continue
        pending = block
        while pending:
            checkpoint()
            previous_length = len(pending)
            expanded = inflater.decompress(pending, min(limits.chunk_bytes, info.file_size - count + 1))
            consume(expanded)
            if inflater.unused_data:
                raise ArchiveError("A ZIP member contains trailing compressed-stream data.")
            pending = inflater.unconsumed_tail
            if pending and len(pending) == previous_length and not expanded:
                raise ArchiveError("A ZIP compressed stream made no progress.")
    if inflater is not None:
        # A small output budget can leave expanded bytes inside zlib after its
        # compressed input is consumed. Drain those bytes under the same budget
        # before deciding whether the stream reached its actual end marker.
        while not inflater.eof:
            checkpoint()
            expanded = inflater.decompress(b"", min(limits.chunk_bytes, info.file_size - count + 1))
            consume(expanded)
            if not expanded:
                break
        if not inflater.eof:
            raise ArchiveError("A ZIP compressed stream is truncated.")
    if count != info.file_size or crc != info.CRC:
        raise ArchiveError("A ZIP member failed byte-count or CRC verification.")
    return count


@contextmanager
def prepared_export(source: Path, *, limits: Limits | None = None) -> Iterator[PreparedExport]:
    """Yield a validated directory or temporary ZIP extraction for local intake.

    Limits bound the original ZIP as one file, expanded payload bytes, paths,
    entries including implicit directories, and central metadata bytes (using
    ``max_manifest_bytes``). Payload buffers use O(chunk_bytes); metadata uses
    O(central-directory bytes + entry/path count). Extracted files consume their
    full expanded size on disk. ZIP64, multipart, encryption, symlinks, special
    files, and compression methods other than stored/deflate fail explicitly.

    Preserve ``original_zip`` while inside the context, then finish publishing
    only after context exit has rechecked source identity and timestamps. The
    temporary directory is removed on normal completion and exceptions, including
    cancellation. A hard process kill can leave temporary files. Like the archive
    core, this API assumes stable, user-controlled directory ancestors.
    """
    active_limits = limits or Limits()
    selected = Path(os.path.abspath(source))
    safe_directory(selected.parent)
    if stat.S_ISDIR(selected.lstat().st_mode):
        root = safe_directory(selected)
        initial = scan_tree(root, active_limits)
        yield PreparedExport(root, None)
        if scan_tree(root, active_limits) != initial:
            raise ArchiveError("The selected export directory changed during processing.")
        return
    with open_regular(selected) as input_file:
        initial = os.fstat(input_file.fileno())
        if initial.st_size > active_limits.max_file_bytes:
            raise ArchiveError("The source ZIP exceeds the configured file-byte limit.")
        _check_source(input_file, selected, initial)
        with tempfile.TemporaryDirectory(prefix="keepmorrow-export-", dir=temporary_parent()) as temporary:
            directory = Path(temporary)
            try:
                end = _preflight_directory(input_file, initial.st_size, active_limits)
                with zipfile.ZipFile(input_file, mode="r") as archive:
                    entries = archive.infolist()
                    if len(entries) != end.entry_count:
                        raise ArchiveError("The ZIP index changed or has inconsistent entry counts.")
                    directories, members = _plan_members(input_file, entries, end, active_limits)
                    for path in directories:
                        checkpoint()
                        (directory / path).mkdir()
                    actual_bytes = 0
                    for member in members:
                        checkpoint()
                        if member.is_directory:
                            actual_bytes += _extract_member(input_file, member, None, active_limits)
                        else:
                            with (directory / member.path).open("xb") as output:
                                actual_bytes += _extract_member(input_file, member, output, active_limits)
                        if actual_bytes > active_limits.max_total_bytes:
                            raise ArchiveError("The ZIP exceeds the configured expanded-byte limit.")
            except (zipfile.BadZipFile, zipfile.LargeZipFile, UnicodeError, struct.error,
                    zlib.error, NotImplementedError) as error:
                raise ArchiveError("The input is not a valid supported ZIP export.") from error
            _check_source(input_file, selected, initial)
            yield PreparedExport(directory, selected)
            _check_source(input_file, selected, initial)
