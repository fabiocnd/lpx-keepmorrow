"""Challenge source identity, graph fidelity, media evidence, and parser budgets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from keepmorrow.archive.model import FileRecord
from keepmorrow.importers import ImportFailure, ImportLimits, parse_chatgpt_export


def conversation(identifier: str = "conversation-1", title: str = "Preservation design") -> dict:
    return {
        "id": identifier, "title": title, "current_node": "answer-a",
        "mapping": {
            "root": {"id": "root", "parent": None, "children": ["question"], "message": None},
            "question": {
                "id": "question", "parent": "root", "children": ["answer-a", "answer-b"],
                "message": {"id": "message-q", "author": {"role": "user"},
                            "content": {"content_type": "text", "parts": ["Preserve both alternatives."]}},
            },
            "answer-a": {
                "id": "answer-a", "parent": "question", "children": [],
                "message": {"id": "message-a", "author": {"role": "assistant"},
                            "content": {"content_type": "text", "parts": ["Keep original bytes."]}},
            },
            "answer-b": {
                "id": "answer-b", "parent": "question", "children": [],
                "message": {"id": "message-b", "author": {"role": "assistant"},
                            "content": {"content_type": "text", "parts": ["Retain branch evidence."]}},
            },
        },
        "future_metadata": {"source_language": "en-US", "unknown_flag": True},
    }


class ChatGPTImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inventory: dict[str, FileRecord] = {}

    def write_bytes(self, path: str, data: bytes) -> None:
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        self.inventory[path] = FileRecord(path, len(data), hashlib.sha256(data).hexdigest())

    def write_json(self, value: object, path: str = "conversations.json") -> None:
        self.write_bytes(path, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def parse(self, *, namespace: str = "synthetic-account", capture: str = "capture-1",
              limits: ImportLimits | None = None) -> dict:
        result = parse_chatgpt_export(self.root, tuple(self.inventory.values()),
                                     account_namespace=namespace, capture_id=capture, limits=limits)
        return result.as_dict()

    def test_branches_null_roots_and_source_bytes_remain_intact(self) -> None:
        source = conversation()
        self.write_json([source])
        before = (self.root / "conversations.json").read_bytes()
        result = self.parse()
        self.assertEqual(result["status"], "complete")
        record = result["conversations"][0]
        nodes = {node["id"]: node for node in record["nodes"]}
        self.assertEqual(nodes["question"]["children_ids"], ["answer-a", "answer-b"])
        self.assertIsNone(nodes["root"]["message_id"])
        self.assertEqual(record["current_node_id"], "answer-a")
        self.assertEqual(record["association"]["state"], "association_unknown")
        self.assertEqual(record["provenance"]["source_path"], "conversations.json")
        self.assertEqual(record["provenance"]["record_index"], 0)
        self.assertEqual((self.root / "conversations.json").read_bytes(), before)

    def test_namespace_and_source_id_establish_identity_not_title(self) -> None:
        first = conversation()
        self.write_json([first])
        original = self.parse()["conversations"][0]
        self.assertNotEqual(original["conversation_key"],
                            self.parse(namespace="other-account")["conversations"][0]["conversation_key"])
        first["title"] = "Renamed discussion"
        self.write_json([first, conversation("different-source", "Renamed discussion")])
        renamed, unrelated = self.parse(capture="capture-2")["conversations"]
        self.assertEqual(original["conversation_key"], renamed["conversation_key"])
        self.assertNotEqual(original["revision_id"], renamed["revision_id"])
        self.assertNotEqual(renamed["conversation_key"], unrelated["conversation_key"])

    def test_unknown_source_fields_change_revision_but_whitespace_does_not(self) -> None:
        record = conversation()
        self.write_json([record])
        revision = self.parse()["conversations"][0]["revision_id"]
        self.write_bytes("conversations.json", json.dumps([record], indent=4).encode())
        self.assertEqual(revision, self.parse()["conversations"][0]["revision_id"])
        record["future_metadata"]["unknown_flag"] = False
        self.write_json([record])
        self.assertNotEqual(revision, self.parse()["conversations"][0]["revision_id"])

    def test_numbered_files_and_duplicate_occurrences_keep_provenance(self) -> None:
        self.write_json([conversation()], "conversations-1.json")
        self.write_json([conversation()], "conversations_2.json")
        result = self.parse()
        self.assertEqual(result["summary"]["accepted_records"], 2)
        self.assertEqual({item["provenance"]["source_path"] for item in result["conversations"]},
                         {"conversations-1.json", "conversations_2.json"})
        self.assertIn("duplicate_record_occurrence", {issue["code"] for issue in result["issues"]})

    def test_conflicting_ids_and_malformed_records_have_item_level_outcomes(self) -> None:
        conflicting = conversation()
        conflicting["conversation_id"] = "different-id"
        self.write_json([conflicting, {"title": "Missing identity"}, 3, conversation("good")])
        result = self.parse()
        self.assertEqual(result["summary"]["accepted_records"], 1)
        self.assertEqual(result["summary"]["rejected_records"], 3)
        self.assertEqual(result["source_documents"][0]["record_count"], 4)
        self.assertEqual({item["record_index"] for item in result["issues"]}, {0, 1, 2})
        self.assertEqual(result["status"], "partial")

    def test_null_or_missing_project_is_unknown_and_gizmo_is_not_a_project(self) -> None:
        records = [conversation(str(index)) for index in range(4)]
        records[0]["project_id"] = None
        records[1]["gizmo_id"] = "custom-gpt-identifier"
        records[2]["project_id"] = "project-aurora"
        records[3]["project_id"] = {"invalid": True}
        self.write_json(records)
        result = self.parse()
        associations = [record["association"] for record in result["conversations"]]
        self.assertEqual([item["state"] for item in associations],
                         ["association_unknown", "association_unknown", "project_confirmed", "association_unknown"])
        self.assertEqual(associations[2]["project_id"], "project-aurora")

    def test_explicit_artifact_paths_bind_bytes_without_filename_guessing(self) -> None:
        record = conversation()
        message = record["mapping"]["question"]["message"]
        message["metadata"] = {"attachments": [
            {"id": "model", "name": "model.glb", "relative_path": "assets/model.glb"},
            {"id": "missing", "name": "missing.png", "relative_path": "assets/missing.png"},
            {"id": "unresolved", "name": "model.glb"},
            {"url": "https://example.invalid/image.png", "name": "remote.png"},
        ]}
        message["content"] = {"content_type": "multimodal_text", "parts": [
            "Inspect this image.",
            {"content_type": "image_asset_pointer", "asset_pointer": "file-service://image-1",
             "relative_path": "assets/diagram.png"},
        ]}
        self.write_json([record])
        self.write_bytes("assets/model.glb", b"glTF\x00\xff\x01binary-model")
        self.write_bytes("assets/diagram.png", b"\x89PNG\r\n\x1a\nsynthetic-image")
        self.write_bytes("assets/unassociated.apk", b"PK\x03\x04synthetic-package")
        with patch("socket.socket", side_effect=AssertionError("Import must not open a network connection.")):
            result = self.parse()
        artifacts = result["conversations"][0]["artifacts"]
        self.assertEqual([item["status"] for item in artifacts],
                         ["stored", "stored", "not_supplied", "unresolved", "external_reference"])
        self.assertEqual(artifacts[0]["sha256"], self.inventory["assets/diagram.png"].sha256)
        self.assertEqual(artifacts[1]["sha256"], self.inventory["assets/model.glb"].sha256)
        self.assertIn("assets/unassociated.apk", {item["path"] for item in result["files"]})

    def test_unsafe_artifact_paths_are_reported_without_following_them(self) -> None:
        record = conversation()
        record["mapping"]["question"]["message"]["metadata"] = {"attachments": [
            {"relative_path": "../outside.png"}, {"relative_path": "/absolute.png"},
            {"relative_path": "C:/outside.png"}, {"relative_path": "assets\\image.png"},
        ]}
        self.write_json([record])
        result = self.parse()
        self.assertEqual({item["status"] for item in result["conversations"][0]["artifacts"]},
                         {"unsupported_reference"})
        self.assertEqual({item["code"] for item in result["issues"]}, {"unsafe_artifact_path"})

    def test_single_wrapper_directory_is_supported_but_multiple_roots_are_ambiguous(self) -> None:
        record = conversation()
        record["mapping"]["question"]["message"]["metadata"] = {
            "attachments": [{"relative_path": "assets/file.bin"}]
        }
        self.write_json([record], "export-2026/conversations.json")
        self.write_bytes("export-2026/assets/file.bin", b"\x00\xff")
        result = self.parse()
        artifact = result["conversations"][0]["artifacts"][0]
        self.assertEqual(artifact["relative_path"], "export-2026/assets/file.bin")
        self.assertEqual(artifact["status"], "stored")
        self.write_json([conversation()], "second/conversations.json")
        ambiguous = self.parse()
        self.assertEqual(ambiguous["status"], "unsupported")
        self.assertEqual(ambiguous["conversations"], [])
        self.assertEqual(ambiguous["issues"][0]["code"], "ambiguous_export_roots")

    def test_graph_failures_do_not_silently_flatten_or_drop_edges(self) -> None:
        invalid: list[tuple[str, dict]] = []
        record = conversation()
        record["mapping"]["answer-a"]["parent"] = "absent"
        invalid.append(("dangling_parent", record))
        record = conversation()
        record["mapping"]["question"]["children"].append("absent")
        invalid.append(("dangling_child", record))
        record = conversation()
        record["mapping"]["question"]["children"].remove("answer-b")
        invalid.append(("inconsistent_edge", record))
        record = conversation()
        record["mapping"]["question"]["children"].append("answer-a")
        invalid.append(("duplicate_edge", record))
        record = conversation()
        record["mapping"]["root"]["parent"] = "answer-a"
        record["mapping"]["answer-a"]["children"] = ["root"]
        invalid.append(("cyclic_graph", record))
        for code, value in invalid:
            with self.subTest(code=code):
                self.write_json([value])
                result = self.parse()
                self.assertEqual(result["summary"]["rejected_records"], 1)
                self.assertIn(code, {item["code"] for item in result["issues"]})

    def test_unknown_content_is_retained_in_original_and_reported(self) -> None:
        record = conversation()
        record["mapping"]["answer-a"]["message"]["content"]["parts"].append(
            {"content_type": "future_video_format", "payload": {"unknown": True}}
        )
        self.write_json([record])
        result = self.parse()
        self.assertEqual(result["summary"]["accepted_records"], 1)
        self.assertIn("unsupported_content_part", {item["code"] for item in result["issues"]})

    def test_ambiguous_json_nonfinite_numbers_and_surrogates_are_malformed(self) -> None:
        for raw in (b'[{"id":"a","id":"b"}]', b'[NaN]', b'[Infinity]', b'[1e999]',
                    b'["\\ud800"]', b'[{"\\udfff":0}]', b'\xff', b'['):
            with self.subTest(raw=raw):
                self.write_bytes("conversations.json", raw)
                result = self.parse()
                self.assertEqual(result["source_documents"][0]["status"], "malformed")
                self.assertEqual(result["issues"][0]["code"], "malformed_json")
                json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")

    def test_unsupported_and_empty_inputs_are_distinct(self) -> None:
        self.write_json([conversation()], "arbitrary.json")
        self.assertEqual(self.parse()["status"], "unsupported")
        self.write_json([])
        empty = self.parse()
        self.assertEqual(empty["status"], "complete")
        self.assertEqual(empty["summary"]["source_records"], 0)
        self.write_json({"conversations": []})
        self.assertEqual(self.parse()["source_documents"][0]["status"], "unsupported")

    def test_resource_limits_fail_instead_of_returning_truncated_success(self) -> None:
        self.write_json([conversation()])
        for limits in (ImportLimits(max_json_file_bytes=8), ImportLimits(max_json_total_bytes=8),
                       ImportLimits(max_nodes=2), ImportLimits(max_edges=2),
                       ImportLimits(max_text_bytes=4), ImportLimits(max_json_tokens=8),
                       ImportLimits(max_json_depth=2)):
            with self.subTest(limits=limits), self.assertRaises(ImportFailure):
                self.parse(limits=limits)
        self.write_json([conversation(), conversation("second")])
        with self.assertRaises(ImportFailure):
            self.parse(limits=ImportLimits(max_conversations=1))
        self.write_json([None, None])
        with self.assertRaises(ImportFailure):
            self.parse(limits=ImportLimits(max_issues=1))

    def test_source_tampering_and_invalid_inventory_fail_closed(self) -> None:
        self.write_json([conversation()])
        path = self.root / "conversations.json"
        data = path.read_bytes()
        path.write_bytes(data.replace(b"original", b"modified"))
        with self.assertRaises(ImportFailure):
            self.parse()
        self.write_json([conversation()])
        record = self.inventory["conversations.json"]
        with self.assertRaises(ImportFailure):
            parse_chatgpt_export(self.root, (record, record), account_namespace="account", capture_id="one")
        escaped = FileRecord("../outside.json", 0, "0" * 64)
        with self.assertRaises(ImportFailure):
            parse_chatgpt_export(self.root, (escaped,), account_namespace="account", capture_id="one")

    def test_configuration_and_namespace_reject_ambiguous_values(self) -> None:
        for value in (True, 0, -1, "5"):
            with self.subTest(value=value), self.assertRaises(ImportFailure):
                ImportLimits(max_nodes=value)
        with self.assertRaises(ImportFailure):
            ImportLimits(max_json_depth=129)
        self.write_json([conversation()])
        for namespace in ("", " ", "account\nother", "\ud800"):
            with self.subTest(namespace=repr(namespace)), self.assertRaises(ImportFailure):
                self.parse(namespace=namespace)


if __name__ == "__main__":
    unittest.main()
