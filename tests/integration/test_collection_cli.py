"""CLI consent boundaries and user-visible outcomes for collection operations."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from keepmorrow.catalog.model import CatalogError, CatalogLimits
from keepmorrow.catalog.service import import_exports, load_collection
from keepmorrow.cli import main
from keepmorrow.consent import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
from tests.fixtures.chatgpt_exports import EVOLVING_ID, INDEPENDENT_ID, write_export_pair


class CollectionCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.acceptance = ["--accept-terms", CURRENT_TERMS_VERSION,
                           "--accept-privacy", CURRENT_PRIVACY_VERSION]

    def invoke(self, arguments: list[str], *, accepted: bool = True) -> tuple[int, dict, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main([*arguments, *(self.acceptance if accepted else [])])
        output, error = stdout.getvalue(), stderr.getvalue()
        document = json.loads(output or error)
        return status, document, output, error

    def test_every_collection_command_refuses_before_paths_or_services_are_touched(self) -> None:
        source = self.root / "private-source-that-must-not-be-inspected"
        destination = self.root / "must-not-be-created"
        key = "a" * 64
        commands = [
            ["import", str(source), "--destination", str(destination), "--account-namespace", "account"],
            ["catalog", str(source)],
            ["search", str(source), "private search text"],
            ["read", str(source), key],
            ["associate", str(source), str(destination), "--conversation-key", key,
             "--state", "standalone_confirmed", "--reason", "Private operator reason."],
            ["recover", str(source), str(destination), "--conversation-key", key],
            ["verify", str(source), "--collection"],
        ]
        declarations = [
            [], ["--accept-terms", CURRENT_TERMS_VERSION],
            ["--accept-privacy", CURRENT_PRIVACY_VERSION],
            ["--accept-terms", "2026-11-12-draft.1", "--accept-privacy", CURRENT_PRIVACY_VERSION],
            ["--accept-terms", CURRENT_TERMS_VERSION, "--accept-privacy", "2026-11-12-draft.1"],
            ["--accept-terms", "latest", "--accept-privacy", CURRENT_PRIVACY_VERSION],
            ["--accept-terms", CURRENT_TERMS_VERSION + " ", "--accept-privacy", CURRENT_PRIVACY_VERSION],
        ]
        services = ("create_archive", "restore_archive", "verify_archive", "import_exports",
                    "load_collection", "associate_conversation", "recover_selection",
                    "browse_catalog", "search_catalog", "read_revision")
        for command in commands:
            for declaration in declarations:
                with self.subTest(operation=command[0], declaration=declaration):
                    with contextlib.ExitStack() as stack:
                        for name in ("stat", "lstat", "open", "iterdir", "resolve", "exists", "read_bytes", "read_text"):
                            stack.enter_context(patch.object(
                                Path, name, side_effect=AssertionError("A selected path was inspected before acceptance.")
                            ))
                        for name in services:
                            stack.enter_context(patch(
                                f"keepmorrow.cli.{name}",
                                side_effect=AssertionError("A service was invoked before acceptance."),
                            ))
                        status, document, stdout, stderr = self.invoke([*command, *declaration], accepted=False)
                    self.assertEqual(status, 2)
                    self.assertEqual(stdout, "")
                    self.assertEqual(document["error_code"], "acceptance_required")
                    self.assertNotIn("acceptance", document)
                    self.assertNotIn(str(source), stderr)
                    self.assertNotIn("private search text", stderr)
                    self.assertNotIn("Private operator reason.", stderr)
        self.assertFalse(destination.exists())

    def test_real_cli_import_browse_search_read_associate_and_recover(self) -> None:
        first, second = write_export_pair(self.root)
        archive = self.root / "collection"
        status, imported, stdout, stderr = self.invoke([
            "import", str(first), str(second), "--destination", str(archive),
            "--account-namespace", "synthetic-account",
        ])
        self.assertEqual(status, 3)
        self.assertEqual(stderr, "")
        self.assertTrue(imported["verified"])
        self.assertEqual(imported["semantic_status"], "partial")
        self.assertEqual(imported["summary"]["conversation_count"], 4)
        self.assertEqual(imported["acceptance"]["operation"], "import")
        self.assertEqual(imported["acceptance"]["terms_version"], CURRENT_TERMS_VERSION)
        self.assertEqual(imported["acceptance"]["privacy_version"], CURRENT_PRIVACY_VERSION)
        self.assertNotIn("UNRELATED_CONVERSATION_MARKER", stdout)
        self.assertNotIn("Compare preservation alternatives.", stdout)
        self.assertNotIn("mapping", stdout)

        status, catalog, stdout, _ = self.invoke(["catalog", str(archive), "--limit", "4"])
        self.assertEqual(status, 0)
        self.assertEqual(catalog["result"]["total"], 4)
        self.assertEqual(catalog["acceptance"]["operation"], "catalog")
        self.assertNotIn("UNRELATED_CONVERSATION_MARKER", stdout)
        key = next(item["conversation_key"] for item in catalog["result"]["items"]
                   if item["source_id"] == EVOLVING_ID)
        independent_key = next(item["conversation_key"] for item in catalog["result"]["items"]
                               if item["source_id"] == INDEPENDENT_ID)
        status, search, stdout, _ = self.invoke([
            "search", str(archive), "original bytes", "--conversation-key", key,
        ])
        self.assertEqual(status, 0)
        self.assertEqual(search["acceptance"]["operation"], "search")
        self.assertEqual(len(search["result"]["items"]), 2)
        self.assertIn("Keep original bytes and evidence.", stdout)

        status, read, _, _ = self.invoke(["read", str(archive), key, "--limit", "2"])
        self.assertEqual(status, 0)
        self.assertEqual(read["acceptance"]["operation"], "read")
        self.assertEqual(read["result"]["title"], "Archive design reviewed")
        self.assertEqual(read["result"]["selection_basis"], "most_recently_supplied_occurrence")
        self.assertEqual(len(read["result"]["nodes"]), 2)
        self.assertEqual(read["result"]["next_offset"], 2)

        classified = self.root / "classified"
        status, association, stdout, _ = self.invoke([
            "associate", str(archive), str(classified), "--conversation-key", independent_key,
            "--state", "standalone_confirmed", "--reason", "Confirmed as intentionally independent.",
        ])
        self.assertEqual(status, 3)
        self.assertEqual(association["acceptance"]["operation"], "associate")
        self.assertEqual(association["summary"]["association_decision_count"], 1)
        self.assertNotIn("Confirmed as intentionally independent.", stdout)
        selected = self.root / "selected"
        status, recovered, stdout, _ = self.invoke([
            "recover", str(classified), str(selected), "--conversation-key", key,
        ])
        self.assertEqual(status, 3)
        self.assertTrue(recovered["verified"])
        self.assertEqual(recovered["acceptance"]["operation"], "recover")
        self.assertEqual(recovered["summary"]["conversation_count"], 1)
        self.assertNotIn("UNRELATED_CONVERSATION_MARKER", stdout)
        self.assertEqual(len(load_collection(selected).document["conversations"]), 1)
        status, verified, stdout, _ = self.invoke(["verify", str(archive), "--collection"])
        self.assertEqual(status, 0)
        self.assertTrue(verified["verified"])
        self.assertEqual(verified["acceptance"]["operation"], "verify")
        self.assertNotIn("UNRELATED_CONVERSATION_MARKER", stdout)

    def test_complete_and_unsupported_imports_have_distinct_statuses_with_archives(self) -> None:
        empty = self.root / "recognized-empty"
        empty.mkdir()
        (empty / "conversations.json").write_bytes(b"[]")
        complete_archive = self.root / "complete-archive"
        status, document, _, _ = self.invoke([
            "import", str(empty), "--destination", str(complete_archive), "--account-namespace", "account",
        ])
        self.assertEqual(status, 0)
        self.assertEqual(document["semantic_status"], "complete")
        self.assertEqual(document["summary"]["conversation_count"], 0)
        unsupported = self.root / "unsupported"
        unsupported.mkdir()
        (unsupported / "opaque.bin").write_bytes(b"\x00\xff\x80")
        unsupported_archive = self.root / "unsupported-archive"
        status, document, _, _ = self.invoke([
            "import", str(unsupported), "--destination", str(unsupported_archive), "--account-namespace", "account",
        ])
        self.assertEqual(status, 3)
        self.assertEqual(document["semantic_status"], "unsupported")
        self.assertTrue(unsupported_archive.exists())
        self.assertEqual((unsupported_archive / "payload/captures/000001/source/opaque.bin").read_bytes(), b"\x00\xff\x80")

    def test_accepted_invalid_operation_and_cancellation_report_no_success(self) -> None:
        missing = self.root / "missing-archive"
        status, document, stdout, _ = self.invoke(["catalog", str(missing)])
        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(document["acceptance"]["operation"], "catalog")
        self.assertNotIn("verified", document)
        output = self.root / "not-created"
        with patch("keepmorrow.cli.import_exports", side_effect=KeyboardInterrupt):
            status, document, stdout, _ = self.invoke([
                "import", str(missing), "--destination", str(output), "--account-namespace", "account",
            ])
        self.assertEqual(status, 130)
        self.assertEqual(stdout, "")
        self.assertEqual(document["error_code"], "cancelled")
        self.assertEqual(document["acceptance"]["operation"], "import")
        self.assertNotIn("verified", document)
        self.assertFalse(output.exists())

    def test_large_reference_metadata_cannot_bypass_the_catalog_byte_budget(self) -> None:
        first, _ = write_export_pair(self.root)
        source = first / "conversations.json"
        records = json.loads(source.read_bytes())
        records[0]["mapping"]["question"]["message"]["metadata"]["attachments"] = [
            {"id": f"reference-{index}", "name": "n" * 1024,
             "url": f"https://example.invalid/{index}"}
            for index in range(200)
        ]
        source.write_text(json.dumps(records), encoding="utf-8")
        original = source.read_bytes()
        destination = self.root / "over-budget"
        with self.assertRaises(CatalogError):
            import_exports([first], destination, account_namespace="account",
                           catalog_limits=CatalogLimits(max_catalog_bytes=64 * 1024))
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.root.glob(".keepmorrow-*")), [])
        self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
