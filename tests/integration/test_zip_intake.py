"""Challenge ZIP intake with binary exports, ambiguous paths, and false metadata."""

from __future__ import annotations

import io
import os
import stat
import struct
import tempfile
import unittest
import warnings
import zipfile
import zlib
from pathlib import Path
from unittest.mock import patch

from keepmorrow.archive import ArchiveError, Limits
from keepmorrow.importers.zip_intake import prepared_export


class _UnseekableBytes(io.BytesIO):
    def seekable(self) -> bool:
        return False

    def seek(self, *args: object) -> int:
        raise io.UnsupportedOperation("Synthetic streaming ZIP writer.")


class ZipIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "export.zip"

    def write_zip(self, members: list[tuple[str | zipfile.ZipInfo, bytes]], *, streaming: bool = False) -> None:
        destination = _UnseekableBytes() if streaming else io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path, contents in members:
                    archive.writestr(path, contents)
        self.source.write_bytes(destination.getvalue())

    def assert_refused(self, *, limits: Limits | None = None) -> None:
        with patch("tempfile.tempdir", str(self.root)):
            with self.assertRaises(ArchiveError):
                with prepared_export(self.source, limits=limits):
                    self.fail("An invalid export reached the caller.")
        self.assertEqual(list(self.root.glob("keepmorrow-export-*")), [])

    def test_binary_files_empty_directories_and_original_zip_are_preserved(self) -> None:
        files = {
            "images/diagram.png": b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 5,
            "models/character.glb": b"glTF\x02\x00\x00\x00" + bytes(range(255, -1, -1)),
            "build/client.apk": b"PK\x03\x04\x00\x00\xffsynthetic APK payload",
            "downloads/resources.zip": b"PK\x03\x04\x00\x00\xffsynthetic nested ZIP payload",
            "documents/brief.pdf": b"%PDF-1.7\n\x00\xffsynthetic document",
            "empty-file": b"",
        }
        self.write_zip([*files.items(), ("empty-directory/", b"")])
        original = self.source.read_bytes()
        with prepared_export(self.source, limits=Limits(chunk_bytes=31)) as prepared:
            self.assertEqual(prepared.original_zip, self.source)
            self.assertTrue((prepared.directory / "empty-directory").is_dir())
            for path, expected in files.items():
                self.assertEqual((prepared.directory / path).read_bytes(), expected)
            extracted = prepared.directory
        self.assertFalse(extracted.exists())
        self.assertEqual(self.source.read_bytes(), original)

    def test_stored_and_streaming_data_descriptor_archives_are_supported(self) -> None:
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                stored = zipfile.ZipInfo("original.bin")
                stored.compress_type = zipfile.ZIP_STORED
                self.write_zip([(stored, bytes(range(256))), ("notes.txt", b"synthetic" * 500)], streaming=streaming)
                with prepared_export(self.source, limits=Limits(chunk_bytes=7)) as prepared:
                    self.assertEqual((prepared.directory / "original.bin").read_bytes(), bytes(range(256)))
                    self.assertEqual((prepared.directory / "notes.txt").read_bytes(), b"synthetic" * 500)

    def test_empty_zip_and_unicode_paths_are_supported(self) -> None:
        for members in ([], [("caf\u00e9/notes.txt", b"source bytes")]):
            with self.subTest(members=members):
                self.write_zip(members)
                with prepared_export(self.source) as prepared:
                    for path, data in members:
                        self.assertEqual((prepared.directory / path).read_bytes(), data)

    def test_unsigned_streaming_data_descriptor_is_supported_and_checked(self) -> None:
        self.write_zip([("file", b"streaming payload")], streaming=True)
        data = bytearray(self.source.read_bytes())
        descriptor = data.index(b"PK\x07\x08")
        del data[descriptor:descriptor + 4]
        end = data.rfind(b"PK\x05\x06")
        central_offset = struct.unpack_from("<I", data, end + 16)[0]
        struct.pack_into("<I", data, end + 16, central_offset - 4)
        self.source.write_bytes(data)
        with prepared_export(self.source) as prepared:
            self.assertEqual((prepared.directory / "file").read_bytes(), b"streaming payload")
        data[descriptor] ^= 0x01
        self.source.write_bytes(data)
        self.assert_refused()

    def test_directory_input_is_validated_and_not_removed(self) -> None:
        directory = self.root / "directory"
        directory.mkdir()
        (directory / "original.bin").write_bytes(b"\x00\xff")
        with prepared_export(directory) as prepared:
            self.assertEqual(prepared.directory, directory)
            self.assertIsNone(prepared.original_zip)
        self.assertEqual((directory / "original.bin").read_bytes(), b"\x00\xff")

    def test_unsafe_paths_are_rejected_without_writing_outside_extraction(self) -> None:
        for name in ("../escaped", "/absolute", "C:/drive", "nested\\file", "./file", "a//file",
                     "CON.txt", "folder./file", "cafe\u0301.txt", "a/../../escaped"):
            with self.subTest(name=name):
                self.write_zip([(name, b"must stay inside")])
                self.assert_refused()
                self.assertFalse((self.root / "escaped").exists())

    def test_case_collisions_duplicate_entries_and_file_directory_conflicts_are_rejected(self) -> None:
        for names in (("A.txt", "a.txt"), ("same", "same"), ("parent", "parent/child"),
                      ("directory/", "directory"), ("Parent/a", "parent/b"),
                      ("Stra\u00dfe.txt", "STRASSE.txt")):
            with self.subTest(names=names):
                self.write_zip([(name, b"" if name.endswith("/") else b"synthetic") for name in names])
                self.assert_refused()

    def test_nul_in_a_filename_is_not_silently_truncated(self) -> None:
        self.write_zip([("abc", b"payload")])
        self.source.write_bytes(self.source.read_bytes().replace(b"abc", b"a\x00c"))
        self.assert_refused()

    def test_symlinks_special_files_and_inconsistent_directory_metadata_are_rejected(self) -> None:
        for mode in (stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600, stat.S_IFDIR | 0o755):
            with self.subTest(mode=mode):
                info = zipfile.ZipInfo("entry")
                info.create_system = 3
                info.external_attr = mode << 16
                self.write_zip([(info, b"outside")])
                self.assert_refused()
        self.write_zip([("not-empty/", b"hidden data")])
        self.assert_refused()

    def test_encryption_and_unsupported_compression_are_rejected(self) -> None:
        for flags, compression in ((1, zipfile.ZIP_DEFLATED), (0, 99)):
            with self.subTest(flags=flags, compression=compression):
                self.write_zip([("file", b"payload")])
                data = bytearray(self.source.read_bytes())
                central = data.index(b"PK\x01\x02")
                struct.pack_into("<HH", data, 6, flags, compression)
                struct.pack_into("<HH", data, central + 8, flags, compression)
                self.source.write_bytes(data)
                self.assert_refused()

    def test_unsupported_extraction_versions_have_a_controlled_error(self) -> None:
        self.write_zip([("file", b"payload")])
        data = bytearray(self.source.read_bytes())
        central = data.index(b"PK\x01\x02")
        struct.pack_into("<H", data, 4, 100)
        struct.pack_into("<H", data, central + 6, 100)
        self.source.write_bytes(data)
        self.assert_refused()

    def test_entry_and_metadata_limits_are_enforced_before_zipfile_materializes_the_index(self) -> None:
        self.write_zip([("one", b"1"), ("two", b"2")])
        for limits in (Limits(max_entries=1), Limits(max_manifest_bytes=1)):
            with self.subTest(limits=limits):
                with patch("keepmorrow.importers.zip_intake.zipfile.ZipFile", side_effect=AssertionError("Unbounded index was constructed.")):
                    self.assert_refused(limits=limits)

    def test_false_central_directory_entry_count_is_rejected_before_zipfile(self) -> None:
        self.write_zip([("one", b"1"), ("two", b"2")])
        data = bytearray(self.source.read_bytes())
        end = data.rfind(b"PK\x05\x06")
        struct.pack_into("<HH", data, end + 8, 1, 1)
        self.source.write_bytes(data)
        with patch("keepmorrow.importers.zip_intake.zipfile.ZipFile", side_effect=AssertionError("Unbounded index was constructed.")):
            self.assert_refused()

    def test_implicit_parent_directories_count_toward_entry_limit(self) -> None:
        self.write_zip([("parent/child/file", b"bytes")])
        self.assert_refused(limits=Limits(max_entries=2))

    def test_declared_file_total_and_original_zip_limits_are_enforced(self) -> None:
        self.write_zip([("first", b"x" * 2000), ("second", b"y" * 2000)])
        for limits in (Limits(max_file_bytes=1000), Limits(max_total_bytes=3000), Limits(max_file_bytes=1)):
            with self.subTest(limits=limits):
                self.assert_refused(limits=limits)

    def test_actual_inflation_cannot_hide_behind_false_uncompressed_size(self) -> None:
        self.write_zip([("file", b"A" * 10_000)])
        data = bytearray(self.source.read_bytes())
        central = data.index(b"PK\x01\x02")
        prefix_crc = zlib.crc32(b"A")
        struct.pack_into("<I", data, 14, prefix_crc)
        struct.pack_into("<I", data, 22, 1)
        struct.pack_into("<I", data, central + 16, prefix_crc)
        struct.pack_into("<I", data, central + 24, 1)
        self.source.write_bytes(data)
        self.assert_refused()

    def test_bad_crc_truncated_records_and_trailing_data_are_rejected(self) -> None:
        info = zipfile.ZipInfo("file")
        info.compress_type = zipfile.ZIP_STORED
        self.write_zip([(info, b"preserve-me")])
        original = self.source.read_bytes()
        for changed in (original.replace(b"preserve-me", b"corrupt-me!"), original[:-1], original + b"trailing"):
            with self.subTest(changed=changed[-16:]):
                self.source.write_bytes(changed)
                self.assert_refused()

    def test_zip64_and_multipart_exports_are_explicitly_rejected(self) -> None:
        self.write_zip([("file", b"payload")])
        original = self.source.read_bytes()
        for offset, value in ((8, 0xFFFF), (4, 1)):
            with self.subTest(offset=offset):
                changed = bytearray(original)
                end = changed.rfind(b"PK\x05\x06")
                struct.pack_into("<H", changed, end + offset, value)
                if offset == 8:
                    struct.pack_into("<H", changed, end + 10, value)
                self.source.write_bytes(changed)
                self.assert_refused()

    def test_local_central_filename_mismatch_is_rejected(self) -> None:
        self.write_zip([("first", b"payload")])
        data = bytearray(self.source.read_bytes())
        data[30:35] = b"other"
        self.source.write_bytes(data)
        self.assert_refused()

    def test_source_zip_mutation_is_detected_before_context_completes(self) -> None:
        self.write_zip([("file", b"payload")])
        extracted: Path | None = None
        with self.assertRaises(ArchiveError):
            with prepared_export(self.source) as prepared:
                extracted = prepared.directory
                with self.source.open("ab") as output:
                    output.write(b"changed")
        self.assertIsNotNone(extracted)
        self.assertFalse(extracted.exists())

    def test_directory_mutation_is_detected_before_context_completes(self) -> None:
        directory = self.root / "directory"
        directory.mkdir()
        with self.assertRaises(ArchiveError):
            with prepared_export(directory):
                (directory / "late-file").write_bytes(b"changed")
        self.assertEqual((directory / "late-file").read_bytes(), b"changed")

    def test_caller_failure_or_cancellation_removes_the_scoped_extraction(self) -> None:
        self.write_zip([("file", b"payload")])
        for error in (RuntimeError("Synthetic caller failure."), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)):
                    with prepared_export(self.source) as prepared:
                        extracted = prepared.directory
                        raise error
                self.assertFalse(extracted.exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links are unavailable.")
    def test_zip_symlink_is_rejected_without_following_it(self) -> None:
        self.write_zip([("file", b"payload")])
        link = self.root / "linked.zip"
        try:
            link.symlink_to(self.source)
        except OSError:
            self.skipTest("This environment does not permit symbolic-link creation.")
        with self.assertRaises(ArchiveError):
            with prepared_export(link):
                self.fail("A symbolic link was followed.")


if __name__ == "__main__":
    unittest.main()
