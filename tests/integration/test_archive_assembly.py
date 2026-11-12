"""Composite archives preserve bytes and reject partial or conflicting output."""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from keepmorrow.archive import ArchiveError, Limits, load_manifest, restore_archive, verify_archive
from keepmorrow.archive.assembly import assembling_archive


class ArchiveAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "empty").mkdir()
        (self.source / "nested").mkdir()
        self.binary = bytes(range(256)) * 11 + b"\x00\xff\x00"
        for extension in ("png", "jpg", "glb", "zip", "apk", "pdf"):
            (self.source / "nested" / f"artifact.{extension}").write_bytes(self.binary)
        (self.source / "zero").write_bytes(b"")
        self.destination = self.root / "assembled"

    def assert_unpublished(self) -> None:
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob(".keepmorrow-*")), [])

    def test_mixed_inputs_recover_byte_identically_with_source_relative_records(self) -> None:
        supplied_zip = self.root / "input.zip"
        supplied_zip.write_bytes(b"PK\x03\x04" + self.binary)
        with assembling_archive(self.destination) as assembly:
            manifest = assembly.add_tree(self.source, "captures/first/source")
            self.assertIsNone(assembly.manifest)
            self.assertIn("nested/artifact.png", {record.path for record in manifest.files})
            self.assertEqual(manifest.directories, ("empty", "nested"))
            stored = assembly.add_file(supplied_zip, "captures/first/original.zip")
            self.assertEqual(stored.path, "captures/first/original.zip")
            metadata = assembly.add_bytes("derived/catalog.json", b'{"version":1}\n')
            self.assertEqual(metadata.sha256, hashlib.sha256(b'{"version":1}\n').hexdigest())
            self.assertEqual(
                (assembly.payload / "captures/first/source/nested/artifact.glb").read_bytes(),
                self.binary,
            )
        self.assertEqual(assembly.payload, self.destination / "payload")
        self.assertEqual(assembly.manifest, load_manifest(self.destination))
        self.assertTrue(verify_archive(self.destination).verified)
        restored = self.root / "restored"
        restore_archive(self.destination, restored)
        self.assertTrue((restored / "captures/first/source/empty").is_dir())
        for extension in ("png", "jpg", "glb", "zip", "apk", "pdf"):
            self.assertEqual(
                (restored / "captures/first/source/nested" / f"artifact.{extension}").read_bytes(),
                self.binary,
            )
        self.assertEqual((restored / "captures/first/original.zip").read_bytes(), supplied_zip.read_bytes())
        self.assertEqual((restored / "captures/first/source/zero").read_bytes(), b"")
        with self.assertRaises(ArchiveError):
            assembly.add_bytes("after-publication", b"must not write")

    def test_generated_metadata_can_share_parent_directories(self) -> None:
        with assembling_archive(self.destination) as assembly:
            assembly.add_bytes("derived/catalog.json", b"{}")
            assembly.add_bytes("derived/reports/import.json", b"[]")
            assembly.add_bytes("derived/view.html", b"<p>Safe derived view.</p>")
        self.assertEqual(assembly.manifest.directories, ("derived", "derived/reports"))
        self.assertTrue(verify_archive(self.destination).verified)

    def test_aggregate_byte_limit_is_enforced_across_additions(self) -> None:
        with self.assertRaises(ArchiveError):
            with assembling_archive(self.destination, limits=Limits(max_total_bytes=5)) as assembly:
                assembly.add_bytes("first", b"123")
                assembly.add_bytes("second", b"456")
        self.assert_unpublished()

    def test_aggregate_entry_limit_counts_generated_parent_directories(self) -> None:
        with self.assertRaises(ArchiveError):
            with assembling_archive(self.destination, limits=Limits(max_entries=3)) as assembly:
                assembly.add_bytes("derived/first", b"1")
                assembly.add_bytes("derived/second", b"2")
                assembly.add_bytes("derived/third", b"3")
        self.assert_unpublished()

    def test_file_and_manifest_limits_fail_before_publication(self) -> None:
        for limits in (Limits(max_file_bytes=1), Limits(max_manifest_bytes=10)):
            with self.subTest(limits=limits), self.assertRaises(ArchiveError):
                with assembling_archive(self.destination, limits=limits) as assembly:
                    assembly.add_bytes("metadata", b"123")
            self.assert_unpublished()

    def test_path_collisions_poison_assembly_even_when_caller_catches_failure(self) -> None:
        for second_path in ("A.txt", "a.txt", "A.txt/nested"):
            with self.subTest(second_path=second_path), self.assertRaises(ArchiveError):
                with assembling_archive(self.destination) as assembly:
                    assembly.add_bytes("A.txt", b"original")
                    with self.assertRaises(ArchiveError):
                        assembly.add_bytes(second_path, b"replacement")
                    self.assertEqual((assembly.payload / "A.txt").read_bytes(), b"original")
            self.assert_unpublished()

    def test_unsafe_paths_and_directory_file_collisions_are_rejected(self) -> None:
        for path in ("../escaped", "/absolute", "C:/unsafe", "a/../b", "CON", "a\\b"):
            with self.subTest(path=path), self.assertRaises(ArchiveError):
                with assembling_archive(self.destination) as assembly:
                    assembly.add_bytes(path, b"never published")
            self.assert_unpublished()
        with self.assertRaises(ArchiveError):
            with assembling_archive(self.destination) as assembly:
                assembly.add_bytes("folder/file", b"preserved")
                assembly.add_bytes("folder", b"collision")
        self.assert_unpublished()

    def test_source_containment_and_reused_prefix_are_rejected(self) -> None:
        nested = self.source / "nested-destination"
        with self.assertRaises(ArchiveError):
            with assembling_archive(nested) as assembly:
                assembly.add_tree(self.source, "source")
        self.assertFalse(nested.exists())
        self.assertEqual(list(self.source.glob(".keepmorrow-*")), [])
        with self.assertRaises(ArchiveError):
            with assembling_archive(self.destination) as assembly:
                assembly.add_tree(self.source, "captures/source")
                assembly.add_tree(self.source, "captures/source")
        self.assert_unpublished()

    def test_assembly_cannot_read_its_own_payload_as_a_new_source(self) -> None:
        with self.assertRaises(ArchiveError):
            with assembling_archive(self.destination) as assembly:
                assembly.add_bytes("derived/data", b"source")
                assembly.add_file(assembly.payload / "derived/data", "copy")
        self.assert_unpublished()
        with self.assertRaises(ArchiveError):
            with assembling_archive(self.destination) as assembly:
                assembly.add_tree(assembly.payload, "recursive")
        self.assert_unpublished()

    def test_interrupted_source_copy_and_cancellation_remove_only_staging(self) -> None:
        with patch("keepmorrow.archive.assembly.copy_tree", side_effect=OSError("simulated write failure")):
            with self.assertRaises(OSError):
                with assembling_archive(self.destination) as assembly:
                    assembly.add_tree(self.source, "source")
        self.assert_unpublished()
        with self.assertRaises(KeyboardInterrupt):
            with assembling_archive(self.destination) as assembly:
                assembly.add_bytes("derived/data", b"partial")
                raise KeyboardInterrupt
        self.assert_unpublished()
        self.assertEqual((self.source / "nested/artifact.png").read_bytes(), self.binary)

    def test_existing_destination_and_publication_race_preserve_user_data(self) -> None:
        self.destination.mkdir()
        marker = self.destination / "user-owned"
        marker.write_bytes(b"original")
        with self.assertRaises(ArchiveError):
            with assembling_archive(self.destination):
                self.fail("An existing destination must be refused before yielding.")
        self.assertEqual(marker.read_bytes(), b"original")
        marker.unlink()
        self.destination.rmdir()
        with self.assertRaises(ArchiveError):
            with assembling_archive(self.destination) as assembly:
                assembly.add_bytes("derived/data", b"new")
                self.destination.mkdir()
                marker.write_bytes(b"competing output")
        self.assertIsNone(assembly.manifest)
        self.assertEqual(marker.read_bytes(), b"competing output")
        self.assertEqual(list(self.root.glob(".keepmorrow-*")), [])

    def test_untracked_writes_and_changed_preserved_bytes_prevent_publication(self) -> None:
        for action in ("unexpected", "corrupted"):
            with self.subTest(action=action), self.assertRaises(ArchiveError):
                with assembling_archive(self.destination) as assembly:
                    assembly.add_bytes("recorded", b"original")
                    path = assembly.payload / ("extra" if action == "unexpected" else "recorded")
                    path.write_bytes(b"modified")
            self.assert_unpublished()

    def test_manifest_is_deterministic_and_metadata_load_does_not_claim_integrity(self) -> None:
        manifests = []
        for name in ("first", "second"):
            destination = self.root / name
            with assembling_archive(destination) as assembly:
                assembly.add_tree(self.source, "source")
                assembly.add_bytes("derived/catalog.json", b"{}")
            manifests.append(assembly.manifest)
        self.assertEqual(*manifests)
        damaged = self.root / "first/payload/source/nested/artifact.png"
        damaged.write_bytes(b"x" * len(self.binary))
        self.assertEqual(load_manifest(self.root / "first"), manifests[0])
        self.assertFalse(verify_archive(self.root / "first").verified)


if __name__ == "__main__":
    unittest.main()
