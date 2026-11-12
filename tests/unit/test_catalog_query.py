"""Bounded literal queries preserve history, Unicode, and pagination semantics."""

from __future__ import annotations

import copy
import unittest

from keepmorrow.catalog.model import CatalogError, CatalogLimits, json_bytes
from keepmorrow.catalog.query import browse_catalog, read_revision, search_catalog

KEY = "a" * 64
OTHER_KEY = "b" * 64
FIRST_REVISION = "1" * 64
SECOND_REVISION = "2" * 64


def _revision(identifier: str, title: str, capture: str, text: str) -> dict:
    return {
        "revision_id": identifier, "title": title,
        "association": {"state": "association_unknown", "project_id": None, "evidence": {"kind": "source"}},
        "nodes": [{"id": "node-1", "parent_id": None, "children_ids": [], "message_id": "message-1",
                   "role": "user", "content_type": "text", "text": text}],
        "occurrences": [{"capture_id": capture, "provenance": {"record_index": 0}, "artifacts": []}],
    }


def _document() -> dict:
    return {
        "captures": [{"capture_id": "capture-first"}, {"capture_id": "capture-second"}],
        "association_history": [],
        "conversations": [
            {"conversation_key": KEY, "source_id": "conversation-one", "revisions": [
                _revision(FIRST_REVISION, "Earlier title", "capture-first", "Straße, CAFÉ, coração, 東京. Literal [a-z]+ marker."),
                _revision(SECOND_REVISION, "Reviewed title", "capture-second", "Later evidence remains searchable."),
            ]},
            {"conversation_key": OTHER_KEY, "source_id": "conversation-two", "revisions": [
                _revision("3" * 64, "Independent title", "capture-first", "Separate conversation content."),
            ]},
        ],
    }


class CatalogQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = _document()

    def test_unicode_casefolding_is_literal_and_does_not_modify_source(self) -> None:
        original = copy.deepcopy(self.document)
        for query in ("STRASSE", "café", "CORAÇÃO", "東京", "[a-z]+"):
            with self.subTest(query=query):
                result = search_catalog(self.document, query)
                self.assertEqual(len(result["items"]), 1)
                self.assertEqual(result["items"][0]["revision_id"], FIRST_REVISION)
        self.assertEqual(search_catalog(self.document, ".*")["items"], [])
        self.assertEqual(self.document, original)

    def test_latest_revision_uses_supplied_occurrences_and_explicit_history_remains_readable(self) -> None:
        latest = read_revision(self.document, KEY)
        self.assertEqual(latest["revision_id"], SECOND_REVISION)
        self.assertEqual(latest["selection_basis"], "most_recently_supplied_occurrence")
        historical = read_revision(self.document, KEY, revision_id=FIRST_REVISION)
        self.assertEqual(historical["revision_id"], FIRST_REVISION)
        self.assertEqual(historical["selection_basis"], "explicit_revision")
        self.document["captures"].append({"capture_id": "capture-third"})
        self.document["conversations"][0]["revisions"][0]["occurrences"].append(
            {"capture_id": "capture-third", "provenance": {"record_index": 0}, "artifacts": []}
        )
        self.assertEqual(read_revision(self.document, KEY)["revision_id"], FIRST_REVISION)

    def test_read_pagination_is_bounded_and_reports_text_and_edge_omissions(self) -> None:
        revision = self.document["conversations"][0]["revisions"][1]
        revision["title"] = "t" * 600
        children = [f"child-{index:03d}" for index in range(40)]
        revision["nodes"] = [
            {"id": "hub", "parent_id": None, "children_ids": children,
             "message_id": "hub-message", "role": "user", "content_type": "text", "text": "é" * 5000},
            *({"id": child, "parent_id": "hub", "children_ids": [],
               "message_id": f"{child}-message", "role": "assistant", "content_type": "text", "text": child}
              for child in children),
        ]
        first = read_revision(self.document, KEY, limit=1)
        self.assertEqual(len(first["title"]), 512)
        self.assertTrue(first["title_truncated"])
        self.assertEqual(first["next_offset"], 1)
        self.assertEqual(first["total_nodes"], 41)
        self.assertEqual(len(first["nodes"][0]["text"]), 4096)
        self.assertTrue(first["nodes"][0]["text_truncated"])
        self.assertEqual(first["nodes"][0]["child_count"], 40)
        self.assertEqual(len(first["nodes"][0]["children_ids"]), 32)
        self.assertTrue(first["nodes"][0]["children_truncated"])
        self.assertLessEqual(len(json_bytes(first)), CatalogLimits().max_response_bytes)
        last = read_revision(self.document, KEY, offset=40, limit=1)
        self.assertEqual(last["nodes"][0]["id"], "child-039")
        self.assertIsNone(last["next_offset"])
        self.assertEqual(len(revision["nodes"][0]["text"]), 5000)

    def test_revision_identifier_and_browse_history_lists_are_explicitly_bounded(self) -> None:
        revisions = self.document["conversations"][0]["revisions"]
        template = revisions[0]
        revisions[:] = [copy.deepcopy(template) for _ in range(201)]
        for index, revision in enumerate(revisions):
            revision["revision_id"] = f"{index:064x}"
        read = read_revision(self.document, KEY, revision_id=revisions[0]["revision_id"])
        self.assertEqual(len(read["revision_ids"]), 200)
        self.assertTrue(read["revision_ids_truncated"])
        entry = browse_catalog(self.document, limit=1)["items"][0]
        self.assertEqual(entry["revision_count"], 201)
        self.assertEqual(len(entry["revisions"]), 20)
        self.assertTrue(entry["revisions_truncated"])

    def test_browse_pagination_and_classification_filters_do_not_repeat_items(self) -> None:
        self.document["conversations"][1]["revisions"][0]["association"] = {
            "state": "project_confirmed", "project_id": "project-harbor", "evidence": {"kind": "source"}
        }
        first = browse_catalog(self.document, limit=1)
        second = browse_catalog(self.document, offset=first["next_offset"], limit=1)
        self.assertEqual(first["total"], 2)
        self.assertNotEqual(first["items"][0]["conversation_key"], second["items"][0]["conversation_key"])
        self.assertIsNone(second["next_offset"])
        filtered = browse_catalog(self.document, project_id="project-harbor")
        self.assertEqual([item["conversation_key"] for item in filtered["items"]], [OTHER_KEY])
        self.assertEqual(browse_catalog(self.document, association_state="association_unknown")["total"], 1)

    def test_response_budget_never_returns_an_empty_page_with_a_continuation(self) -> None:
        tiny = CatalogLimits(max_response_bytes=32)
        operations = [
            lambda: browse_catalog(self.document, limits=tiny),
            lambda: search_catalog(self.document, "evidence", limits=tiny),
            lambda: read_revision(self.document, KEY, limits=tiny),
        ]
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(CatalogError):
                operation()

    def test_budget_limited_browse_pages_make_progress_without_losing_records(self) -> None:
        template = self.document["conversations"][0]
        self.document["conversations"] = [copy.deepcopy(template) for _ in range(20)]
        for index, conversation in enumerate(self.document["conversations"]):
            conversation["conversation_key"] = f"{index:064x}"
            conversation["source_id"] = f"source-{index}"
        limits = CatalogLimits(max_response_bytes=4000)
        offset, collected = 0, []
        for _ in range(20):
            page = browse_catalog(self.document, offset=offset, limit=20, limits=limits)
            self.assertLessEqual(len(json_bytes(page)), limits.max_response_bytes)
            collected.extend(item["conversation_key"] for item in page["items"])
            if page["next_offset"] is None:
                break
            self.assertTrue(page["items"])
            self.assertGreater(page["next_offset"], offset)
            offset = page["next_offset"]
        self.assertEqual(collected, [item["conversation_key"] for item in self.document["conversations"]])

    def test_empty_results_and_terminal_pages_still_obey_the_response_budget(self) -> None:
        tiny = CatalogLimits(max_response_bytes=1)
        operations = [
            lambda: browse_catalog(self.document, offset=2, limits=tiny),
            lambda: search_catalog(self.document, "absent text", limits=tiny),
            lambda: read_revision(self.document, KEY, offset=1, limits=tiny),
        ]
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(CatalogError):
                operation()

    def test_unknown_keys_and_malformed_filters_raise_controlled_errors(self) -> None:
        for key in ("missing", None, [], {}):
            with self.subTest(key=key), self.assertRaises(CatalogError):
                read_revision(self.document, key)
        with self.assertRaises(CatalogError):
            read_revision(self.document, KEY, revision_id="missing")
        with self.assertRaises(CatalogError):
            search_catalog(self.document, "evidence", conversation_key="missing")
        for value in ([], {}, True, 1, ""):
            with self.subTest(project_id=value), self.assertRaises(CatalogError):
                browse_catalog(self.document, project_id=value)
        for value in ([], {}, True, "unsupported"):
            with self.subTest(association_state=value), self.assertRaises(CatalogError):
                browse_catalog(self.document, association_state=value)

    def test_invalid_pagination_and_query_sizes_are_rejected(self) -> None:
        for options in ({"offset": -1}, {"offset": True}, {"limit": 0}, {"limit": True}, {"limit": 201}):
            with self.subTest(options=options), self.assertRaises(CatalogError):
                browse_catalog(self.document, **options)
            with self.subTest(options=options), self.assertRaises(CatalogError):
                read_revision(self.document, KEY, **options)
        for query in (None, True, [], "", " ", "x" * 1025):
            with self.subTest(query=query), self.assertRaises(CatalogError):
                search_catalog(self.document, query)


if __name__ == "__main__":
    unittest.main()
