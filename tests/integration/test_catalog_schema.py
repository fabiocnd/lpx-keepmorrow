"""Validate emitted collection variants against the optional JSON Schema gate.

The preservation runtime has no jsonschema dependency. The SDK validation job
provides it; environments without the optional package skip this gate explicitly.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any

from keepmorrow.catalog.service import (
    associate_conversation,
    import_exports,
    load_collection,
    recover_selection,
)

if importlib.util.find_spec("jsonschema") is not None:
    from jsonschema import Draft202012Validator
else:
    Draft202012Validator = None


def _record(identifier: str, text: str, attachments: list[dict[str, str]]) -> dict[str, Any]:
    node_id = f"node-{identifier}"
    return {
        "id": identifier,
        "title": f"Synthetic {identifier} work",
        "current_node": node_id,
        "mapping": {
            node_id: {
                "id": node_id, "parent": None, "children": [],
                "message": {
                    "id": f"message-{identifier}", "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": [text]},
                    "metadata": {"attachments": attachments},
                },
            },
        },
    }


@unittest.skipIf(Draft202012Validator is None, "The optional jsonschema package is unavailable.")
class CollectionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name).resolve()
        schema_path = Path(__file__).resolve().parents[2] / "schemas" / "collection-v1.schema.json"
        cls.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema)

        source = cls.root / "source"
        (source / "images").mkdir(parents=True)
        (source / "images/diagram.png").write_bytes(b"\x89PNG\r\n\x1a\nSynthetic preservation bytes.")
        records = [
            _record("selected", "Keep these synthetic notes.", [
                {"id": "diagram", "relative_path": "images/diagram.png"},
                {"id": "whole-export", "relative_path": "conversations.json"},
            ]),
            _record("unselected", "Other synthetic notes remain outside the selection.", []),
        ]
        (source / "conversations.json").write_text(json.dumps(records), encoding="utf-8")
        original_zip = cls.root / "export.zip"
        with zipfile.ZipFile(original_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(source).as_posix())
        cls.full = cls.root / "full"
        import_exports([source, original_zip], cls.full, account_namespace="synthetic-schema-account")
        cls.document = load_collection(cls.full).document
        cls.selected_key = next(item["conversation_key"] for item in cls.document["conversations"]
                                if item["source_id"] == "selected")

    def test_schema_is_valid_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(self.schema)

    def test_full_collection_includes_valid_directory_and_raw_zip_capture_shapes(self) -> None:
        self.validator.validate(self.document)
        self.assertEqual({item["source_kind"] for item in self.document["captures"]}, {"directory", "zip"})

    def test_selected_collection_includes_explicit_whole_export_exclusions(self) -> None:
        destination = self.root / "selected"
        recover_selection(self.full, destination, conversation_keys=[self.selected_key])
        document = load_collection(destination).document
        self.validator.validate(document)
        statuses = {artifact["status"]
                    for conversation in document["conversations"]
                    for revision in conversation["revisions"]
                    for occurrence in revision["occurrences"]
                    for artifact in occurrence["artifacts"]}
        self.assertIn("excluded_by_selection", statuses)
        self.assertIn("stored", statuses)

    def test_associated_collection_has_a_valid_operator_decision(self) -> None:
        destination = self.root / "associated"
        associate_conversation(
            self.full, destination, conversation_key=self.selected_key,
            state="standalone_confirmed", project_id=None,
            reason="Synthetic schema validation of an explicit classification.",
        )
        document = load_collection(destination).document
        self.validator.validate(document)
        self.assertEqual(len(document["association_history"]), 1)

    def test_unsupported_collection_keeps_valid_zero_known_record_counts(self) -> None:
        source = self.root / "unsupported-source"
        source.mkdir()
        destination = self.root / "unsupported"
        import_exports([source], destination, account_namespace="synthetic-schema-account")
        document = load_collection(destination).document
        self.validator.validate(document)
        self.assertEqual(document["captures"][0]["status"], "unsupported")
        self.assertEqual(document["conversations"], [])


if __name__ == "__main__":
    unittest.main()
