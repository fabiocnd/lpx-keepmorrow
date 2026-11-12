"""Portable views preserve evidence while source content remains passive text."""

from copy import deepcopy
from html.parser import HTMLParser
import unittest

from keepmorrow.archive import ArchiveError
from keepmorrow.catalog.views import render_collection


class ParsedView(HTMLParser):
    def __init__(self, content: bytes) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, dict[str, str | None]]] = []
        self.text: list[str] = []
        self.feed(content.decode("utf-8"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        self.text.append(data)

    @property
    def links(self) -> list[dict[str, str | None]]:
        return [attrs for tag, attrs in self.elements if tag == "a"]


def example_collection() -> dict:
    capture_id = "a" * 64
    return {
        "format": "lpx-keepmorrow.collection",
        "version": 1,
        "provider": "chatgpt",
        "account_namespace": "synthetic-account",
        "captures": [{
            "capture_id": capture_id,
            "storage_id": "000001",
            "source_kind": "directory",
            "files": [
                {"path": "conversations.json", "size_bytes": 1024, "sha256": "b" * 64},
                {"path": "assets/diagram #1 100%.png", "size_bytes": 32, "sha256": "c" * 64},
                {"path": "notes.html", "size_bytes": 10, "sha256": "d" * 64},
                {"path": "image.svg", "size_bytes": 12, "sha256": "e" * 64},
            ],
            "issues": [{"code": "artifact_not_supplied", "record_index": 0}],
            "summary": {"recognized": 1, "unresolved": 1},
        }],
        "conversations": [{
            "conversation_key": "f" * 64,
            "source_id": "conversation-1",
            "revisions": [{
                "revision_id": "0" * 64,
                "title": "Preservation alternatives",
                "association": {
                    "state": "association_unknown",
                    "project_id": None,
                    "evidence": {"kind": "insufficient_source_metadata"},
                },
                "current_node_id": "answer-b",
                "nodes": [
                    {"id": "root", "parent_id": None, "children_ids": ["question"],
                     "message_id": None, "role": None, "text": "", "content_type": None},
                    {"id": "question", "parent_id": "root", "children_ids": ["answer-a", "answer-b"],
                     "message_id": "message-1", "role": "user", "text": "Compare both approaches.",
                     "content_type": "text"},
                    {"id": "answer-a", "parent_id": "question", "children_ids": [],
                     "message_id": "message-2", "role": "assistant", "text": "Preserve original bytes.",
                     "content_type": "text"},
                    {"id": "answer-b", "parent_id": "question", "children_ids": [],
                     "message_id": "message-3", "role": "assistant", "text": "Keep derived views separate.",
                     "content_type": "text"},
                ],
                "occurrences": [{
                    "capture_id": capture_id,
                    "provenance": {"source_path": "conversations.json", "record_index": 0,
                                   "record_sha256": "0" * 64},
                    "artifacts": [
                        {"reference_id": "artifact-1", "node_id": "answer-a", "kind": "image",
                         "source_reference": "assets/diagram #1 100%.png",
                         "relative_path": "assets/diagram #1 100%.png", "status": "stored",
                         "size_bytes": 32, "sha256": "c" * 64, "original_name": "diagram.png",
                         "media_type": "image/png"},
                        {"reference_id": "artifact-2", "node_id": "answer-b", "kind": "attachment",
                         "source_reference": "missing-model.glb", "relative_path": "missing-model.glb",
                         "status": "not_supplied", "size_bytes": None, "sha256": None,
                         "original_name": "missing-model.glb", "media_type": "model/gltf-binary"},
                        {"reference_id": "artifact-3", "node_id": "answer-b", "kind": "attachment",
                         "source_reference": "https://example.invalid/private", "relative_path": None,
                         "status": "external_reference", "size_bytes": None, "sha256": None,
                         "original_name": "remote-file", "media_type": None},
                    ],
                }],
            }],
        }],
    }


class CatalogViewTests(unittest.TestCase):
    def test_renders_revisions_graph_provenance_and_missing_artifacts(self) -> None:
        view = ParsedView(render_collection(example_collection()))
        text = " ".join(view.text)
        for expected in (
            "Derived collection view", "Preservation alternatives", "Unknown association",
            "root", "question", "answer-a", "answer-b", "Parent node", "Child nodes",
            "artifact_not_supplied", "not_supplied", "external_reference", "missing-model.glb",
            "Source record", "Record index", "Record SHA-256", "Supplied files",
            "Lopix Neural Inc.", "Fabio de Sousa Lopes",
        ):
            self.assertIn(expected, text)
        self.assertIn("does not recreate native ChatGPT", text)
        self.assertGreater(sum(tag == "details" for tag, _ in view.elements), 5)

    def test_downloads_use_exact_inventory_paths_and_quoted_uri_segments(self) -> None:
        view = ParsedView(render_collection(example_collection()))
        paths = [attrs["href"] for attrs in view.links]
        expected = "captures/000001/source/assets/diagram%20%231%20100%25.png"
        self.assertEqual(paths.count(expected), 2)
        self.assertNotIn("captures/000001/source/missing-model.glb", paths)
        for attrs in view.links:
            self.assertTrue(attrs["href"].startswith("captures/000001/source/"))
            self.assertIn("download", attrs)
            self.assertNotIn("target", attrs)

    def test_source_markup_and_url_schemes_never_become_active_html(self) -> None:
        document = example_collection()
        payload = '</pre><script>fetch("https://example.invalid")</script><img src=x onerror=alert(1)>'
        revision = document["conversations"][0]["revisions"][0]
        revision["title"] = payload
        revision["nodes"][1]["text"] = payload
        revision["nodes"][1]["role"] = '\" onclick=\"alert(1)'
        revision["association"]["evidence"] = {"note": payload}
        revision["occurrences"][0]["artifacts"][0]["original_name"] = payload
        revision["occurrences"][0]["artifacts"][0]["source_reference"] = "javascript:alert(1)"
        document["account_namespace"] = payload
        document["association_history"] = [{"note": payload}]
        view = ParsedView(render_collection(document))
        self.assertIn(payload, " ".join(view.text))
        forbidden = {"script", "img", "svg", "iframe", "object", "embed", "base", "form"}
        self.assertFalse(forbidden & {tag for tag, _ in view.elements})
        for _, attributes in view.elements:
            self.assertFalse(any(name.startswith("on") for name in attributes))
            self.assertNotIn("src", attributes)
        self.assertFalse(any(attrs["href"].startswith(("https:", "javascript:", "data:")) for attrs in view.links))

    def test_csp_blocks_scripts_remote_resources_forms_and_base_rewriting(self) -> None:
        view = ParsedView(render_collection(example_collection()))
        policies = [attrs["content"] for tag, attrs in view.elements
                    if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy"]
        self.assertEqual(len(policies), 1)
        for directive in (
            "default-src 'none'", "script-src 'none'", "style-src 'unsafe-inline'",
            "connect-src 'none'", "base-uri 'none'", "form-action 'none'", "frame-src 'none'",
        ):
            self.assertIn(directive, policies[0])
        html_links = [attrs for attrs in view.links if attrs["href"].endswith((".html", ".svg"))]
        self.assertEqual(len(html_links), 2)
        self.assertTrue(all("download" in attrs for attrs in html_links))

    def test_untrusted_inventory_paths_or_storage_ids_cannot_escape_package(self) -> None:
        for storage_id in ("../other", "https://example.invalid", "000001/../000002"):
            document = example_collection()
            document["captures"][0]["storage_id"] = storage_id
            with self.subTest(storage_id=storage_id):
                view = ParsedView(render_collection(document))
                self.assertEqual(view.links, [])
        document = example_collection()
        for path in ("../../outside", "/absolute", "C:/drive", "a\\b", "https://example.invalid"):
            document["captures"][0]["files"].append({"path": path, "size_bytes": 1, "sha256": "1" * 64})
        view = ParsedView(render_collection(document))
        self.assertTrue(all(attrs["href"].startswith("captures/000001/source/") for attrs in view.links))
        self.assertTrue(all(".." not in attrs["href"] for attrs in view.links))

    def test_ambiguous_capture_identity_does_not_create_artifact_associations(self) -> None:
        document = example_collection()
        duplicate = deepcopy(document["captures"][0])
        duplicate["storage_id"] = "000002"
        document["captures"].append(duplicate)
        view = ParsedView(render_collection(document))
        for storage_id in ("000001", "000002"):
            path = f"captures/{storage_id}/source/assets/diagram%20%231%20100%25.png"
            self.assertEqual([attrs["href"] for attrs in view.links].count(path), 1)
        self.assertIn("no matching supplied file", " ".join(view.text))

    def test_selection_scope_is_visible_and_rendering_does_not_mutate_input(self) -> None:
        document = example_collection()
        document["format"] = "lpx-keepmorrow.selection"
        document["scope"] = {"conversation_keys": ["f" * 64], "complete_account": False}
        original = deepcopy(document)
        content = render_collection(document)
        self.assertEqual(content, render_collection(document))
        self.assertEqual(document, original)
        text = " ".join(ParsedView(content).text)
        self.assertIn("Selected preserved work", text)
        self.assertIn("selected records", text)
        self.assertIn("Declared scope", text)

    def test_selection_scope_uses_the_shared_collection_format(self) -> None:
        document = example_collection()
        document["scope"] = "selected_conversations"
        self.assertIn("Selected preserved work", " ".join(ParsedView(render_collection(document)).text))

    def test_empty_supported_catalog_reports_absence_without_completeness_claim(self) -> None:
        view = ParsedView(render_collection({"captures": [], "conversations": []}))
        text = " ".join(view.text)
        self.assertIn("No supported conversations were indexed", text)
        self.assertIn("No captures are listed", text)
        self.assertEqual(view.links, [])
        with self.assertRaises(ArchiveError):
            render_collection([])


if __name__ == "__main__":
    unittest.main()
