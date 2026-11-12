"""Reject malformed persisted catalogs before queries, extension, or recovery."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from keepmorrow.archive import ArchiveError
from keepmorrow.catalog.model import CatalogLimits, content_digest, json_bytes, parse_collection
from keepmorrow.catalog.service import import_exports, load_collection, recover_selection


_UNSELECTED_TEXT = "SYNTHETIC_UNSELECTED_CONVERSATION_BODY_82b"


def _conversation(identifier: str, title: str, text: str, *, source_attachment: bool = False) -> dict[str, Any]:
    root_id, leaf_id = f"root-{identifier}", f"leaf-{identifier}"
    attachments = [{"id": f"binary-{identifier}", "name": "binary.bin", "relative_path": "binary.bin"}]
    if source_attachment:
        attachments.append({"id": "export-reference", "relative_path": "conversations.json"})
    return {
        "id": identifier, "title": title, "current_node": leaf_id,
        "mapping": {
            root_id: {"id": root_id, "parent": None, "children": [leaf_id], "message": None},
            leaf_id: {
                "id": leaf_id, "parent": root_id, "children": [],
                "message": {"id": f"message-{identifier}", "author": {"role": "user"},
                            "content": {"content_type": "text", "parts": [text]},
                            "metadata": {"attachments": attachments}},
            },
        },
    }


class PersistedCatalogValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name).resolve()
        source = cls.root / "source"
        source.mkdir()
        (source / "binary.bin").write_bytes(b"\x80")
        records = [
            _conversation("visible", "Visible work", "Preserve these selected notes.", source_attachment=True),
            _conversation("unselected", "Unselected work", _UNSELECTED_TEXT),
        ]
        (source / "conversations.json").write_bytes(json.dumps(records).encode("utf-8"))
        cls.archive = cls.root / "collection"
        import_exports([source], cls.archive, account_namespace="synthetic-account")
        loaded = load_collection(cls.archive)
        cls.document = loaded.document
        cls.manifest = loaded.manifest

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def copy_document(self) -> dict[str, Any]:
        return copy.deepcopy(self.document)

    def assert_rejected(self, document: dict[str, Any], *, limits: CatalogLimits | None = None) -> None:
        with self.assertRaises(ArchiveError):
            parse_collection(json_bytes(document), self.manifest, limits or CatalogLimits())

    def test_unhashable_enum_and_reference_values_raise_controlled_errors(self) -> None:
        paths = (
            ("scope",),
            ("captures", 0, "source_kind"),
            ("captures", 0, "status"),
            ("conversations", 0, "revisions", 0, "association", "state"),
            ("conversations", 0, "revisions", 0, "occurrences", 0, "artifacts", 0, "status"),
            ("conversations", 0, "revisions", 0, "occurrences", 0, "artifacts", 0, "node_id"),
        )
        for path in paths:
            for malformed in ([], {}):
                with self.subTest(path=path, malformed=malformed):
                    document = self.copy_document()
                    target = document
                    for component in path[:-1]:
                        target = target[component]
                    target[path[-1]] = malformed
                    self.assert_rejected(document)

    def test_required_fields_and_parser_versions_fail_before_downstream_use(self) -> None:
        for field in ("parser", "summary", "source_documents"):
            with self.subTest(field=field):
                document = self.copy_document()
                document["captures"][0].pop(field)
                self.assert_rejected(document)
        document = self.copy_document()
        document["conversations"][0]["revisions"][0]["nodes"][0].pop("parent_id")
        self.assert_rejected(document)
        document = self.copy_document()
        document["captures"][0]["parser"]["version"] = 999
        self.assert_rejected(document)

    def test_file_sizes_require_exact_integers_instead_of_equal_booleans_or_floats(self) -> None:
        for malformed in (True, 1.0):
            with self.subTest(malformed=malformed):
                document = self.copy_document()
                next(item for item in document["captures"][0]["files"] if item["path"] == "binary.bin")["size_bytes"] = malformed
                self.assert_rejected(document)
                document = self.copy_document()
                artifact = document["conversations"][0]["revisions"][0]["occurrences"][0]["artifacts"][0]
                self.assertEqual(artifact["relative_path"], "binary.bin")
                artifact["size_bytes"] = malformed
                self.assert_rejected(document)

    def test_namespaced_logical_identity_cannot_be_silently_relabelled(self) -> None:
        for field, replacement in (("source_id", "different-source"), ("conversation_key", "0" * 64)):
            with self.subTest(field=field):
                document = self.copy_document()
                document["conversations"][0][field] = replacement
                self.assert_rejected(document)
        document = self.copy_document()
        document["account_namespace"] = "different-account"
        self.assert_rejected(document)

    def test_source_document_inventory_and_record_counts_must_agree(self) -> None:
        corruptions = (("sha256", "0" * 64), ("size_bytes", 1), ("path", "missing.json"),
                       ("status", []), ("status", "future-profile"),
                       ("record_count", -1), ("accepted_records", True),
                       ("rejected_records", 999))
        for field, value in corruptions:
            with self.subTest(field=field, value=value):
                document = self.copy_document()
                document["captures"][0]["source_documents"][0][field] = value
                self.assert_rejected(document)

    def test_occurrence_provenance_cannot_point_to_a_binary_or_absent_record(self) -> None:
        for field, replacement in (("source_path", "binary.bin"), ("record_index", 999),
                                   ("record_index", True), ("record_sha256", "0" * 64)):
            with self.subTest(field=field):
                document = self.copy_document()
                occurrence = document["conversations"][0]["revisions"][0]["occurrences"][0]
                occurrence["provenance"][field] = replacement
                self.assert_rejected(document)

    def test_semantic_budgets_apply_across_logical_conversations(self) -> None:
        for limits in (CatalogLimits(max_nodes=3), CatalogLimits(max_revisions=1),
                       CatalogLimits(max_occurrences=1), CatalogLimits(max_artifacts=2)):
            with self.subTest(limits=limits):
                self.assert_rejected(self.copy_document(), limits=limits)

    def test_message_cycles_and_missing_graph_references_are_rejected(self) -> None:
        document = self.copy_document()
        nodes = document["conversations"][0]["revisions"][0]["nodes"]
        root = next(item for item in nodes if item["parent_id"] is None)
        leaf = next(item for item in nodes if item["parent_id"] is not None)
        root["parent_id"] = leaf["id"]
        leaf["children_ids"] = [root["id"]]
        self.assert_rejected(document)
        document = self.copy_document()
        document["conversations"][0]["revisions"][0]["nodes"][0]["children_ids"] = ["absent-node"]
        self.assert_rejected(document)

    def test_nonfinite_exponent_and_duplicate_keys_are_rejected(self) -> None:
        data = json_bytes(self.document)
        for invalid in (b'{"extra":1e999,' + data[1:], b'{"format":"duplicate",' + data[1:]):
            with self.subTest(invalid=invalid[:40]), self.assertRaises(ArchiveError):
                parse_collection(invalid, self.manifest, CatalogLimits())

    def test_association_sequence_must_be_an_integer(self) -> None:
        document = self.copy_document()
        decision = {
            "sequence": True, "conversation_key": document["conversations"][0]["conversation_key"],
            "association": {"state": "standalone_confirmed", "project_id": None,
                            "evidence": {"kind": "explicit_local_operator_decision"}},
            "reason": "Synthetic classification decision.", "previous_decision_id": None,
        }
        decision["decision_id"] = content_digest(decision)
        document["association_history"] = [decision]
        self.assert_rejected(document)

    def test_selection_excludes_whole_export_documents_even_when_referenced_as_artifacts(self) -> None:
        selected = next(item for item in self.document["conversations"] if item["source_id"] == "visible")
        destination = self.root / "selection"
        recover_selection(self.archive, destination, conversation_keys=[selected["conversation_key"]])
        loaded = load_collection(destination)
        self.assertEqual([item["source_id"] for item in loaded.document["conversations"]], ["visible"])
        self.assertTrue(any(item.path.endswith("/binary.bin") for item in loaded.manifest.files))
        self.assertFalse(any(item.path.endswith("/conversations.json") for item in loaded.manifest.files))
        for record in loaded.manifest.files:
            with self.subTest(path=record.path):
                self.assertNotIn(_UNSELECTED_TEXT.encode(), (destination / "payload" / record.path).read_bytes())


if __name__ == "__main__":
    unittest.main()
