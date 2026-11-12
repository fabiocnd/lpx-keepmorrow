"""Recovery package round trips, independent verification, and hostile wrappers."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from keepmorrow.archive import ArchiveError, Limits, verify_archive
from keepmorrow.catalog.service import import_exports, load_collection
from keepmorrow.transfers import PackageLimits, TransferError, pack_collection, unpack_collection
from tests.fixtures.chatgpt_exports import TINY_PNG, write_export_pair


def _bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class RecoveryPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        first, second = write_export_pair(self.root)
        self.collection = self.root / "collection"
        import_exports([first, second], self.collection, account_namespace="synthetic-owner")
        self.package = self.root / "recovery.zip"
        self.recovered = self.root / "recovered"

    def assert_no_staging(self) -> None:
        self.assertEqual(list(self.root.glob(".keepmorrow-transfer-*")), [])

    def rewrite(self, transform) -> Path:
        malicious = self.root / "modified.zip"
        with zipfile.ZipFile(self.package) as source, zipfile.ZipFile(malicious, "w") as output:
            for info in source.infolist():
                updated = transform(info, source.read(info))
                if updated is not None:
                    output.writestr(*updated)
        return malicious

    def test_deterministic_binary_roundtrip_preserves_entire_archive_and_manifest_bytes(self) -> None:
        manifest = self.collection / "manifest.json"
        # Supported JSON formatting is original metadata too; packaging must
        # not silently reserialize a valid, noncanonical byte representation.
        manifest.write_bytes(json.dumps(json.loads(manifest.read_bytes()), ensure_ascii=False).encode("utf-8"))
        original = _bytes(self.collection)
        packed = pack_collection(self.collection, self.package)
        second = self.root / "same.zip"
        self.assertEqual(pack_collection(self.collection, second), packed)
        self.assertEqual(self.package.read_bytes(), second.read_bytes())
        unpacked = unpack_collection(self.package, self.recovered)
        self.assertEqual(packed, unpacked)
        self.assertEqual(_bytes(self.recovered), original)
        self.assertEqual(_bytes(self.collection), original)
        self.assertEqual(packed.sha256, hashlib.sha256(self.package.read_bytes()).hexdigest())
        self.assertEqual(packed.size_bytes, self.package.stat().st_size)
        self.assertEqual(packed.expanded_size_bytes, sum(map(len, original.values())))
        self.assertIn(TINY_PNG, original.values())
        self.assertTrue(verify_archive(self.recovered).verified)
        self.assertEqual(load_collection(self.recovered).document, load_collection(self.collection).document)
        self.assert_no_staging()

    def test_payload_limit_counts_wrapper_entries_separately(self) -> None:
        collection = load_collection(self.collection)
        count = len(collection.manifest.directories) + len(collection.manifest.files)
        limits = Limits(max_entries=count)
        package_limits = PackageLimits(max_wrapper_entries=count + 2)
        packed = pack_collection(self.collection, self.package, archive_limits=limits, limits=package_limits)
        self.assertEqual(unpack_collection(self.package, self.recovered,
                                          archive_limits=limits, limits=package_limits), packed)
        with self.assertRaises(ArchiveError):
            pack_collection(self.collection, self.root / "overflow.zip",
                            archive_limits=limits, limits=replace(package_limits, max_wrapper_entries=count + 1))

    def test_encoded_and_expanded_budgets_are_independent(self) -> None:
        packed = pack_collection(self.collection, self.package)
        for limits in (
            PackageLimits(max_encoded_bytes=packed.size_bytes - 1),
            PackageLimits(max_expanded_bytes=packed.expanded_size_bytes - 1),
        ):
            with self.subTest(limits=limits):
                with self.assertRaises(ArchiveError):
                    unpack_collection(self.package, self.recovered, limits=limits)
                self.assertFalse(self.recovered.exists())
                with self.assertRaises(ArchiveError):
                    pack_collection(self.collection, self.root / "too-large.zip", limits=limits)
                self.assertFalse((self.root / "too-large.zip").exists())
                self.assert_no_staging()

    def test_corrupt_member_is_rejected_even_with_a_valid_outer_zip_crc(self) -> None:
        pack_collection(self.collection, self.package)
        modified = self.rewrite(lambda info, data: (
            info, b"!" + data[1:] if info.filename.endswith("conversations.json") and data else data,
        ))
        with self.assertRaises(ArchiveError):
            unpack_collection(modified, self.recovered)
        self.assertFalse(self.recovered.exists())
        self.assert_no_staging()

    def test_corrupt_outer_zip_crc_is_rejected(self) -> None:
        pack_collection(self.collection, self.package)
        with zipfile.ZipFile(self.package) as archive:
            member = next(info for info in archive.infolist() if info.file_size)
            offset = member.header_offset + 30 + len(member.filename.encode("utf-8")) + len(member.extra)
        encoded = bytearray(self.package.read_bytes())
        encoded[offset] ^= 1
        self.package.write_bytes(encoded)
        with self.assertRaises(ArchiveError):
            unpack_collection(self.package, self.recovered)
        self.assertFalse(self.recovered.exists())

    def test_source_mutation_during_packaging_prevents_publication(self) -> None:
        calls = 0
        source = self.collection / "payload/report.json"

        def mutate_after_inventory() -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                source.write_bytes(b"changed source")

        with self.assertRaises(ArchiveError):
            pack_collection(self.collection, self.package, checkpoint=mutate_after_inventory)
        self.assertFalse(self.package.exists())
        self.assert_no_staging()

    def test_outer_metadata_budget_is_enforced_before_package_publication(self) -> None:
        with self.assertRaises(ArchiveError):
            pack_collection(self.collection, self.package, limits=PackageLimits(max_metadata_bytes=64))
        self.assertFalse(self.package.exists())

    def test_missing_and_unexpected_files_are_rejected(self) -> None:
        pack_collection(self.collection, self.package)
        modified = self.rewrite(lambda info, data: None if info.filename == "payload/report.json" else (info, data))
        with self.assertRaises(ArchiveError):
            unpack_collection(modified, self.recovered)
        with zipfile.ZipFile(modified, "a") as archive:
            archive.writestr("unexpected.bin", b"extra")
        with self.assertRaises(ArchiveError):
            unpack_collection(modified, self.recovered)
        self.assertFalse(self.recovered.exists())

    def test_traversal_collision_symlink_and_extra_root_fail_before_publication(self) -> None:
        pack_collection(self.collection, self.package)
        cases = [("../escaped", 0), ("payload/CATALOG.json", 0),
                 ("payload/link", (stat.S_IFLNK | 0o777) << 16), ("extra.txt", 0)]
        for index, (name, mode) in enumerate(cases):
            malicious = self.root / f"hostile-{index}.zip"
            malicious.write_bytes(self.package.read_bytes())
            info = zipfile.ZipInfo(name)
            info.external_attr = mode
            with zipfile.ZipFile(malicious, "a") as archive:
                archive.writestr(info, b"untrusted")
            with self.subTest(name=name), self.assertRaises(ArchiveError):
                unpack_collection(malicious, self.recovered)
            self.assertFalse(self.recovered.exists())
            self.assert_no_staging()
        self.assertFalse((self.root / "escaped").exists())

    def test_existing_destination_and_publication_race_are_never_overwritten(self) -> None:
        self.package.write_bytes(b"preserve-existing")
        with self.assertRaises(ArchiveError):
            pack_collection(self.collection, self.package)
        self.assertEqual(self.package.read_bytes(), b"preserve-existing")
        self.package.unlink()

        def competing_file() -> None:
            self.package.write_bytes(b"competing")

        with self.assertRaises((ArchiveError, OSError)):
            pack_collection(self.collection, self.package, before_publish=competing_file)
        self.assertEqual(self.package.read_bytes(), b"competing")
        self.package.unlink()
        pack_collection(self.collection, self.package)

        def competing_directory() -> None:
            self.recovered.mkdir()
            (self.recovered / "keep.txt").write_bytes(b"competing")

        with self.assertRaises((ArchiveError, OSError)):
            unpack_collection(self.package, self.recovered, before_publish=competing_directory)
        self.assertEqual((self.recovered / "keep.txt").read_bytes(), b"competing")
        self.assert_no_staging()

    def test_cancellation_cleans_only_temporary_outputs(self) -> None:
        original = _bytes(self.collection)
        calls = 0

        def cancel() -> None:
            nonlocal calls
            calls += 1
            if calls >= 9:
                raise RuntimeError("synthetic cancellation")

        with self.assertRaisesRegex(RuntimeError, "synthetic cancellation"):
            pack_collection(self.collection, self.package, checkpoint=cancel, limits=PackageLimits(chunk_bytes=4))
        self.assertFalse(self.package.exists())
        self.assertEqual(_bytes(self.collection), original)
        self.assert_no_staging()
        pack_collection(self.collection, self.package)
        calls = 0
        with self.assertRaisesRegex(RuntimeError, "synthetic cancellation"):
            unpack_collection(self.package, self.recovered, checkpoint=cancel, limits=PackageLimits(chunk_bytes=4))
        self.assertFalse(self.recovered.exists())
        self.assert_no_staging()

    def test_final_authorization_fence_can_refuse_publication(self) -> None:
        def refuse() -> None:
            raise PermissionError("synthetic revoked access")

        with self.assertRaises(PermissionError):
            pack_collection(self.collection, self.package, before_publish=refuse)
        self.assertFalse(self.package.exists())
        self.assert_no_staging()

    def test_noncollection_archives_and_invalid_source_bytes_are_not_packaged(self) -> None:
        catalog = self.collection / "payload/catalog.json"
        catalog.write_bytes(b"{}")
        with self.assertRaises(ArchiveError):
            pack_collection(self.collection, self.package)
        self.assertFalse(self.package.exists())

    def test_profile_refuses_unvalidated_larger_limits(self) -> None:
        with self.assertRaises(TransferError):
            PackageLimits(max_encoded_bytes=1024**3 + 1)
        with self.assertRaises(TransferError):
            PackageLimits(max_wrapper_entries=65_535)


if __name__ == "__main__":
    unittest.main()
