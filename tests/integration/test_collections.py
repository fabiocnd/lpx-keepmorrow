"""End-to-end preservation, revision reconciliation, and scoped recovery evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

from keepmorrow.archive import ArchiveError, Limits, restore_archive, verify_archive
from keepmorrow.catalog.model import CatalogError, CatalogLimits, effective_associations
from keepmorrow.catalog.query import browse_catalog, search_catalog
from keepmorrow.catalog.service import (
    associate_conversation, import_exports, load_collection, recover_selection,
)
from keepmorrow.importers import ImportLimits
from tests.fixtures.chatgpt_exports import (
    EVOLVING_ID, INDEPENDENT_ID, STABLE_ID, TINY_PNG, UNKNOWN_ID, write_export_pair,
)


def _file_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*")) if path.is_file()}


def _conversation(document: dict, source_id: str) -> dict:
    return next(item for item in document["conversations"] if item["source_id"] == source_id)


class CollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.first, self.second = write_export_pair(self.root)
        self.destination = self.root / "collection"
        self.namespace = "synthetic-account-1"

    def import_pair(self, destination: Path | None = None):
        return import_exports([self.first, self.second], destination or self.destination,
                              account_namespace=self.namespace)

    def make_zip(self, directory: Path, path: Path, *, wrapper: str = "") -> Path:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(directory.rglob("*")):
                if source.is_file():
                    relative = source.relative_to(directory).as_posix()
                    archive.write(source, f"{wrapper}/{relative}" if wrapper else relative)
        return path

    def assert_no_staging(self) -> None:
        self.assertEqual(list(self.root.glob(".keepmorrow-*")), [])

    def test_two_exports_preserve_identity_revisions_branches_and_binary_bytes(self) -> None:
        originals = [_file_bytes(self.first), _file_bytes(self.second)]
        result = self.import_pair()
        self.assertTrue(result.as_dict()["verified"])
        self.assertEqual(result.semantic_status, "partial")
        summary = result.summary
        for key, expected in {
            "capture_count": 2, "conversation_count": 4, "revision_count": 5,
            "occurrence_count": 6, "message_node_count": 16, "branched_revision_count": 1,
            "stored_artifact_references": 6, "unavailable_artifact_references": 4,
            "source_file_count": 10,
        }.items():
            self.assertEqual(summary[key], expected, key)
        collection = load_collection(self.destination)
        evolving = _conversation(collection.document, EVOLVING_ID)
        self.assertEqual({revision["title"] for revision in evolving["revisions"]},
                         {"Archive design", "Archive design reviewed"})
        newest = next(revision for revision in evolving["revisions"]
                      if revision["title"] == "Archive design reviewed")
        nodes = {node["id"]: node for node in newest["nodes"]}
        self.assertEqual(nodes["question"]["children_ids"], ["answer", "alternative"])
        self.assertEqual(nodes["answer"]["children_ids"], ["follow-up"])
        self.assertIsNone(nodes["root"]["message_id"])
        self.assertEqual(newest["current_node_id"], "final-answer")
        stable = _conversation(collection.document, STABLE_ID)
        self.assertEqual(len(stable["revisions"]), 1)
        self.assertEqual(len(stable["revisions"][0]["occurrences"]), 2)
        for capture, source_files in zip(collection.document["captures"], originals):
            for record in capture["files"]:
                actual = self.destination / "payload/captures" / capture["storage_id"] / "source" / record["path"]
                self.assertEqual(actual.read_bytes(), source_files[record["path"]])
                self.assertEqual(hashlib.sha256(actual.read_bytes()).hexdigest(), record["sha256"])
        self.assertEqual(_file_bytes(self.first), originals[0])
        self.assertEqual(_file_bytes(self.second), originals[1])

    def test_png_fixture_has_a_real_complete_image_payload(self) -> None:
        self.assertEqual(TINY_PNG[:8], b"\x89PNG\r\n\x1a\n")
        offset, image_data = 8, b""
        kinds = []
        while offset < len(TINY_PNG):
            length = struct.unpack_from(">I", TINY_PNG, offset)[0]
            kind = TINY_PNG[offset + 4:offset + 8]
            data = TINY_PNG[offset + 8:offset + 8 + length]
            crc = struct.unpack_from(">I", TINY_PNG, offset + 8 + length)[0]
            self.assertEqual(zlib.crc32(kind + data), crc)
            kinds.append(kind)
            if kind == b"IDAT":
                image_data += data
            offset += length + 12
        self.assertEqual(kinds, [b"IHDR", b"IDAT", b"IEND"])
        self.assertEqual(zlib.decompress(image_data), b"\x00\x20\x40\x60\xff")

    def test_zip_input_retains_original_container_and_wrapper_relationships(self) -> None:
        source_zip = self.make_zip(self.second, self.root / "second-export.zip", wrapper="export-2026")
        zip_before = source_zip.read_bytes()
        import_exports([self.first, source_zip], self.destination, account_namespace=self.namespace)
        document = load_collection(self.destination).document
        capture = document["captures"][1]
        self.assertEqual(capture["source_kind"], "zip")
        stored_zip = self.destination / "payload" / capture["original_zip"]["path"]
        self.assertEqual(stored_zip.read_bytes(), zip_before)
        self.assertEqual(source_zip.read_bytes(), zip_before)
        evolving = _conversation(document, EVOLVING_ID)
        occurrence = next(occurrence for revision in evolving["revisions"]
                          for occurrence in revision["occurrences"]
                          if occurrence["capture_id"] == capture["capture_id"])
        paths = {artifact["relative_path"] for artifact in occurrence["artifacts"] if artifact["status"] == "stored"}
        self.assertEqual(paths, {"export-2026/assets/diagram.png", "export-2026/assets/character.glb",
                                 "export-2026/assets/build.apk"})

    def test_extending_a_generation_preserves_previous_bytes_and_reuses_revisions(self) -> None:
        initial = self.root / "first-generation"
        import_exports([self.first], initial, account_namespace=self.namespace)
        first_generation = _file_bytes(initial)
        result = import_exports([self.second], self.destination, account_namespace=self.namespace, previous=initial)
        self.assertEqual(_file_bytes(initial), first_generation)
        self.assertEqual(result.summary["capture_count"], 2)
        self.assertEqual(result.summary["revision_count"], 5)
        self.assertEqual(result.summary["occurrence_count"], 6)
        before = load_collection(initial).document
        after = load_collection(self.destination).document
        self.assertEqual(_conversation(before, EVOLVING_ID)["conversation_key"],
                         _conversation(after, EVOLVING_ID)["conversation_key"])
        self.assertEqual(before["captures"][0], after["captures"][0])

    def test_account_namespaces_do_not_merge_and_previous_scope_must_match(self) -> None:
        self.import_pair()
        isolated = self.root / "other-account"
        import_exports([self.first], isolated, account_namespace="different-account")
        first_key = _conversation(load_collection(self.destination).document, EVOLVING_ID)["conversation_key"]
        other_key = _conversation(load_collection(isolated).document, EVOLVING_ID)["conversation_key"]
        self.assertNotEqual(first_key, other_key)
        rejected = self.root / "must-not-exist"
        with self.assertRaises(CatalogError):
            import_exports([self.second], rejected, account_namespace="different-account", previous=self.destination)
        self.assertFalse(rejected.exists())

    def test_repeated_identical_capture_is_recorded_without_duplicating_logical_revisions(self) -> None:
        result = import_exports([self.first, self.first], self.destination, account_namespace=self.namespace)
        self.assertEqual(result.summary["capture_count"], 2)
        self.assertEqual(result.summary["unique_source_count"], 1)
        self.assertEqual(result.summary["conversation_count"], 4)
        self.assertEqual(result.summary["revision_count"], 4)
        self.assertEqual(result.summary["occurrence_count"], 8)
        captures = load_collection(self.destination).document["captures"]
        self.assertNotEqual(captures[0]["capture_id"], captures[1]["capture_id"])

    def test_missing_and_unresolved_artifacts_remain_explicit(self) -> None:
        self.import_pair()
        document = load_collection(self.destination).document
        evolving = _conversation(document, EVOLVING_ID)
        for revision in evolving["revisions"]:
            artifacts = revision["occurrences"][0]["artifacts"]
            self.assertEqual([item["status"] for item in artifacts],
                             ["stored", "stored", "stored", "not_supplied", "unresolved"])
            self.assertIsNone(artifacts[3]["sha256"])
            self.assertIsNone(artifacts[4]["relative_path"])
        associations = effective_associations(document)
        self.assertEqual(associations[_conversation(document, UNKNOWN_ID)["conversation_key"]]["state"],
                         "association_unknown")

    def test_selective_recovery_excludes_unrelated_source_records_and_container(self) -> None:
        source_zip = self.make_zip(self.second, self.root / "second-export.zip")
        import_exports([self.first, source_zip], self.destination, account_namespace=self.namespace)
        parent_bytes = _file_bytes(self.destination)
        parent = load_collection(self.destination)
        selected = self.root / "selected"
        key = _conversation(parent.document, EVOLVING_ID)["conversation_key"]
        recover_selection(self.destination, selected, conversation_keys=[key])
        recovered = load_collection(selected)
        self.assertEqual(recovered.document["scope"], "selected_conversations")
        self.assertEqual(len(recovered.document["conversations"]), 1)
        self.assertEqual(len(recovered.document["conversations"][0]["revisions"]), 2)
        paths = {record.path for record in recovered.manifest.files}
        self.assertEqual(len(paths), 9)
        self.assertFalse(any(path.endswith("original.zip") or path.endswith("unrelated.bin")
                             or "conversations" in Path(path).name for path in paths))
        for data in _file_bytes(selected).values():
            self.assertNotIn(b"UNRELATED_CONVERSATION_MARKER", data)
            self.assertNotIn(b"UNRELATED_BINARY_MARKER", data)
        ordinary = self.root / "ordinary-files"
        restore_archive(selected, ordinary)
        for record in recovered.manifest.files:
            data = (ordinary / record.path).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), record.sha256)
        self.assertEqual(_file_bytes(self.destination), parent_bytes)

    def test_revision_and_project_filters_select_exact_scope(self) -> None:
        self.import_pair()
        document = load_collection(self.destination).document
        evolving = _conversation(document, EVOLVING_ID)
        revision = evolving["revisions"][0]
        subset = self.root / "one-revision"
        recover_selection(self.destination, subset, conversation_keys=[evolving["conversation_key"]],
                          revision_id=revision["revision_id"])
        selected = load_collection(subset).document
        self.assertEqual(selected["summary"]["revision_count"], 1)
        self.assertEqual(selected["summary"]["source_file_count"], 3)
        project_subset = self.root / "harbor-project"
        recover_selection(self.destination, project_subset, project_id="project-harbor")
        project = load_collection(project_subset).document
        self.assertEqual([item["source_id"] for item in project["conversations"]], [STABLE_ID])
        self.assertEqual(project["summary"]["source_file_count"], 0)
        with self.assertRaises(CatalogError):
            recover_selection(self.destination, self.root / "invalid-selector", project_id="project-harbor",
                              conversation_keys=[evolving["conversation_key"]])

    def test_association_decisions_preserve_source_evidence_and_prior_generations(self) -> None:
        self.import_pair()
        initial_bytes = _file_bytes(self.destination)
        document = load_collection(self.destination).document
        independent = _conversation(document, INDEPENDENT_ID)
        key = independent["conversation_key"]
        classified = self.root / "classified"
        associate_conversation(self.destination, classified, conversation_key=key,
                               state="standalone_confirmed", project_id=None,
                               reason="The operator confirms that this work is intentionally independent.")
        classified_bytes = _file_bytes(classified)
        first = load_collection(classified).document
        self.assertEqual(first["association_history"][0]["association"]["state"], "standalone_confirmed")
        self.assertEqual(effective_associations(first)[key]["state"], "standalone_confirmed")
        self.assertEqual(_conversation(first, INDEPENDENT_ID)["revisions"][0]["association"]["state"],
                         "association_unknown")
        corrected = self.root / "corrected"
        associate_conversation(classified, corrected, conversation_key=key, state="project_confirmed",
                               project_id="project-aurora", reason="The operator explicitly groups this work with Aurora.")
        second = load_collection(corrected).document
        self.assertEqual(len(second["association_history"]), 2)
        self.assertEqual(second["association_history"][1]["previous_decision_id"],
                         second["association_history"][0]["decision_id"])
        self.assertEqual(effective_associations(second)[key]["project_id"], "project-aurora")
        self.assertEqual(_file_bytes(self.destination), initial_bytes)
        self.assertEqual(_file_bytes(classified), classified_bytes)

    def test_browsing_search_and_history_are_deterministic_and_scoped(self) -> None:
        self.import_pair()
        document = load_collection(self.destination).document
        page = browse_catalog(document, limit=2)
        self.assertEqual(page["total"], 4)
        self.assertEqual(len(page["items"]), 2)
        self.assertEqual(page["next_offset"], 2)
        last = browse_catalog(document, offset=2, limit=2)
        self.assertIsNone(last["next_offset"])
        self.assertFalse({item["conversation_key"] for item in page["items"]}
                         & {item["conversation_key"] for item in last["items"]})
        self.assertEqual(browse_catalog(document, association_state="association_unknown")["total"], 2)
        results = search_catalog(document, "REVIEWED")
        self.assertEqual(len(results["items"]), 1)
        self.assertEqual(results["items"][0]["title"], "Archive design reviewed")
        self.assertEqual(search_catalog(document, ".*")["items"], [])
        evolving = _conversation(document, EVOLVING_ID)
        historical = search_catalog(document, "original bytes", conversation_key=evolving["conversation_key"])
        self.assertEqual(len({item["revision_id"] for item in historical["items"]}), 2)
        self.assertTrue(search_catalog(document, "original bytes", limit=1)["truncated"])

    def test_binary_tampering_prevents_reading_and_recovery(self) -> None:
        self.import_pair()
        document = load_collection(self.destination).document
        key = _conversation(document, EVOLVING_ID)["conversation_key"]
        target = self.destination / "payload/captures/000001/source/assets/character.glb"
        data = bytearray(target.read_bytes())
        data[-1] ^= 1
        target.write_bytes(data)
        self.assertFalse(verify_archive(self.destination).verified)
        with self.assertRaises(CatalogError):
            load_collection(self.destination)
        output = self.root / "must-not-be-recovered"
        with self.assertRaises(CatalogError):
            recover_selection(self.destination, output, conversation_keys=[key])
        self.assertFalse(output.exists())

    def test_unknown_source_format_is_preserved_with_partial_coverage(self) -> None:
        unknown = self.root / "unsupported-export"
        unknown.mkdir()
        source = b'{"future_format":true,"records":[{"uninterpreted":1}]}'
        (unknown / "other-format.json").write_bytes(source)
        result = import_exports([self.first, unknown], self.destination, account_namespace=self.namespace)
        self.assertEqual(result.semantic_status, "partial")
        document = load_collection(self.destination).document
        self.assertEqual(document["captures"][1]["status"], "unsupported")
        self.assertEqual(document["captures"][1]["issues"][0]["code"], "no_supported_documents")
        retained = self.destination / "payload/captures/000002/source/other-format.json"
        self.assertEqual(retained.read_bytes(), source)

    def test_catalog_paths_are_revalidated_even_with_a_matching_archive_manifest(self) -> None:
        self.import_pair()
        catalog_path = self.destination / "payload/catalog.json"
        catalog = json.loads(catalog_path.read_bytes())
        evolving = _conversation(catalog, EVOLVING_ID)
        evolving["revisions"][0]["occurrences"][0]["artifacts"][0]["relative_path"] = "../outside.png"
        replacement = json.dumps(catalog, sort_keys=True).encode()
        catalog_path.write_bytes(replacement)
        manifest_path = self.destination / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        record = next(item for item in manifest["files"] if item["path"] == "catalog.json")
        record.update(size_bytes=len(replacement), sha256=hashlib.sha256(replacement).hexdigest())
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertTrue(verify_archive(self.destination).verified)
        with self.assertRaises(ArchiveError):
            load_collection(self.destination)

    def test_no_clobber_and_nested_destinations_leave_existing_data_unchanged(self) -> None:
        self.destination.mkdir()
        marker = self.destination / "user-data.txt"
        marker.write_bytes(b"keep this data")
        with self.assertRaises(ArchiveError):
            self.import_pair()
        self.assertEqual(marker.read_bytes(), b"keep this data")
        nested = self.first / "new-collection"
        with self.assertRaises(ArchiveError):
            import_exports([self.first], nested, account_namespace=self.namespace)
        self.assertFalse(nested.exists())
        self.assert_no_staging()

    def test_resource_failures_and_cancellation_roll_back_the_new_generation(self) -> None:
        originals = _file_bytes(self.first)
        cases = [
            {"limits": Limits(max_file_bytes=8)},
            {"catalog_limits": CatalogLimits(max_revisions=1)},
            {"import_limits": ImportLimits(max_nodes=2)},
        ]
        for options in cases:
            with self.subTest(options=options), self.assertRaises(ArchiveError):
                import_exports([self.first], self.destination, account_namespace=self.namespace, **options)
            self.assertFalse(self.destination.exists())
            self.assert_no_staging()
        with patch("keepmorrow.catalog.service.parse_chatgpt_export", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                import_exports([self.first], self.destination, account_namespace=self.namespace)
        self.assertFalse(self.destination.exists())
        self.assertEqual(_file_bytes(self.first), originals)
        self.assert_no_staging()


if __name__ == "__main__":
    unittest.main()
