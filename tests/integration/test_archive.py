"""Exercise byte preservation, corruption detection, and safe failure paths."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from keepmorrow.archive import ArchiveError, Limits, create_archive, restore_archive, verify_archive
from keepmorrow.cli import main
from keepmorrow.consent import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "notes").mkdir()
        (self.source / "empty").mkdir()
        self.data = bytes(range(256)) * 1024 + b"\x00\xff\r\n"
        (self.source / "notes" / "data.bin").write_bytes(self.data)
        (self.source / "empty-file").write_bytes(b"")
        self.archive = self.root / "archive"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_round_trip_preserves_bytes_and_empty_directories(self) -> None:
        created = create_archive(self.source, self.archive, limits=Limits(chunk_bytes=31))
        report = verify_archive(self.archive)
        restored = self.root / "restored"
        recovered = restore_archive(self.archive, restored)
        self.assertTrue(report.verified)
        self.assertEqual(created, recovered)
        self.assertEqual((restored / "notes/data.bin").read_bytes(), self.data)
        self.assertEqual((self.source / "notes/data.bin").read_bytes(), self.data)
        self.assertTrue((restored / "empty").is_dir())
        self.assertEqual((restored / "empty-file").read_bytes(), b"")

    def test_repeated_snapshots_have_identical_manifests(self) -> None:
        create_archive(self.source, self.archive)
        second = self.root / "second"
        create_archive(self.source, second)
        self.assertEqual((self.archive / "manifest.json").read_bytes(), (second / "manifest.json").read_bytes())

    def test_corruption_is_reported_and_recovery_is_canceled(self) -> None:
        create_archive(self.source, self.archive)
        (self.archive / "payload/notes/data.bin").write_bytes(b"corrupt")
        report = verify_archive(self.archive)
        self.assertFalse(report.verified)
        self.assertIn(("changed", "notes/data.bin"), [(item.category, item.path) for item in report.issues])
        target = self.root / "restore"
        with self.assertRaises(ArchiveError):
            restore_archive(self.archive, target)
        self.assertFalse(target.exists())

    def test_missing_and_unexpected_entries_are_distinct(self) -> None:
        create_archive(self.source, self.archive)
        (self.archive / "payload/empty-file").unlink()
        (self.archive / "payload/unexpected").write_text("extra")
        (self.archive / "payload/empty").rmdir()
        (self.archive / "extra-root.txt").write_text("extra")
        issues = {(item.category, item.path) for item in verify_archive(self.archive).issues}
        self.assertIn(("missing", "empty-file"), issues)
        self.assertIn(("unexpected", "unexpected"), issues)
        self.assertIn(("missing_directory", "empty"), issues)
        self.assertIn(("unexpected", "extra-root.txt"), issues)

    def test_same_size_corruption_is_detected(self) -> None:
        create_archive(self.source, self.archive)
        file = self.archive / "payload/notes/data.bin"
        file.write_bytes(b"x" * len(self.data))
        self.assertFalse(verify_archive(self.archive).verified)

    def test_existing_destination_is_never_changed(self) -> None:
        self.archive.mkdir()
        marker = self.archive / "user-data"
        marker.write_text("keep")
        with self.assertRaises(ArchiveError):
            create_archive(self.source, self.archive)
        self.assertEqual(marker.read_text(), "keep")

    def test_existing_restore_destination_is_rejected(self) -> None:
        create_archive(self.source, self.archive)
        target = self.root / "restored"
        target.mkdir()
        with self.assertRaises(ArchiveError):
            restore_archive(self.archive, target)

    def test_nested_destination_is_rejected(self) -> None:
        with self.assertRaises(ArchiveError):
            create_archive(self.source, self.source / "archive")

    def test_empty_source_is_supported(self) -> None:
        empty = self.root / "empty-source"
        empty.mkdir()
        manifest = create_archive(empty, self.archive)
        self.assertEqual(manifest.files, ())
        self.assertTrue(verify_archive(self.archive).verified)

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links are unavailable.")
    def test_source_symlink_is_rejected_without_dereferencing(self) -> None:
        (self.source / "link").symlink_to(self.root / "never-read")
        with self.assertRaises(ArchiveError):
            create_archive(self.source, self.archive)
        self.assertFalse(self.archive.exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links are unavailable.")
    def test_symlink_ancestor_is_rejected(self) -> None:
        link = self.root / "linked-root"
        link.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ArchiveError):
            create_archive(link, self.archive)

    @unittest.skipUnless(hasattr(os, "symlink"), "Symbolic links are unavailable.")
    def test_manifest_symlink_is_rejected(self) -> None:
        create_archive(self.source, self.archive)
        manifest = self.archive / "manifest.json"
        original = self.root / "original-manifest.json"
        manifest.rename(original)
        manifest.symlink_to(original)
        with self.assertRaises(ArchiveError):
            verify_archive(self.archive)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Named pipes are unavailable.")
    def test_nonregular_file_is_rejected_without_blocking(self) -> None:
        os.mkfifo(self.source / "pipe")
        with self.assertRaises(ArchiveError):
            create_archive(self.source, self.archive)

    def test_portable_filename_collision_is_rejected(self) -> None:
        (self.source / "A.txt").write_text("first")
        other = self.source / "a.txt"
        if other.exists():
            self.skipTest("Filesystem is case insensitive.")
        other.write_text("second")
        with self.assertRaises(ArchiveError):
            create_archive(self.source, self.archive)

    def test_resource_limits_fail_before_publication(self) -> None:
        for limits in [Limits(max_entries=1), Limits(max_file_bytes=1), Limits(max_total_bytes=1),
                       Limits(max_manifest_bytes=10)]:
            with self.subTest(limits=limits), self.assertRaises(ArchiveError):
                create_archive(self.source, self.archive, limits=limits)
            self.assertFalse(self.archive.exists())
            self.assertEqual(list(self.root.glob(".keepmorrow-*")), [])

    def test_interrupted_copy_removes_staging_output(self) -> None:
        with patch("keepmorrow.archive.service.copy_tree", side_effect=OSError("simulated write failure")):
            with self.assertRaises(OSError):
                create_archive(self.source, self.archive)
        self.assertFalse(self.archive.exists())
        self.assertEqual(list(self.root.glob(".keepmorrow-*")), [])

    def test_manifest_path_traversal_cannot_write_outside_recovery(self) -> None:
        create_archive(self.source, self.archive)
        path = self.archive / "manifest.json"
        document = json.loads(path.read_bytes())
        document["files"][0]["path"] = "../escaped"
        path.write_text(json.dumps(document))
        with self.assertRaises(ArchiveError):
            restore_archive(self.archive, self.root / "restored")
        self.assertFalse((self.root / "escaped").exists())

    def test_synthetic_fixture_is_preserved_without_semantic_claims(self) -> None:
        fixture = Path(__file__).resolve().parents[2] / "examples" / "synthetic-input"
        if not fixture.exists():
            fixture = Path(__file__).resolve().parents[2].parent / "examples" / "synthetic-input"
        manifest = create_archive(fixture, self.archive)
        self.assertEqual(len(manifest.files), 2)
        restore_archive(self.archive, self.root / "fixture-restored")
        self.assertEqual((fixture / "catalog.json").read_bytes(),
                         (self.root / "fixture-restored/catalog.json").read_bytes())

    def test_cli_returns_machine_readable_status_and_nonzero_on_corruption(self) -> None:
        acceptance = ["--accept-terms", CURRENT_TERMS_VERSION,
                      "--accept-privacy", CURRENT_PRIVACY_VERSION]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["create", str(self.source), str(self.archive), *acceptance])
        self.assertEqual(status, 0)
        status_document = json.loads(output.getvalue())
        self.assertTrue(status_document["verified"])
        self.assertEqual(status_document["acceptance"]["operation"], "create")
        (self.archive / "payload/empty-file").write_text("changed")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["verify", str(self.archive), *acceptance]), 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["create", str(self.source), str(self.archive), *acceptance]), 2)


if __name__ == "__main__":
    unittest.main()

