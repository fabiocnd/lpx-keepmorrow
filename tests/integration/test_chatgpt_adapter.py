"""Exercise the legacy synthetic adapter through SDK client/server sessions.

In-memory streams and ASGI transport test protocol behavior independently of
the actual ChatGPT host or a deployed authenticated service.
"""

from contextlib import ExitStack
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from keepmorrow.catalog.service import import_exports, load_collection
from keepmorrow.consent import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
from keepmorrow.integrations.chatgpt import RegistryError, create_server, load_registry
from keepmorrow.integrations.chatgpt.registry import REGISTRY_FORMAT
from tests.fixtures.chatgpt_exports import EVOLVING_ID, write_export_pair

_HAS_MCP = importlib.util.find_spec("mcp") is not None
_ACCEPTANCE = {"terms_version": CURRENT_TERMS_VERSION, "privacy_version": CURRENT_PRIVACY_VERSION}


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.registry = self.root / "registry.json"

    def test_registry_read_does_not_resolve_or_inspect_granted_content(self) -> None:
        missing_collection = self.root / "not-created"
        self.registry.write_text(json.dumps({
            "format": REGISTRY_FORMAT, "version": 1,
            "collections": {"archive-a": str(missing_collection)},
        }), encoding="utf-8")
        with patch.object(Path, "resolve", side_effect=AssertionError("Grants must remain inert.")):
            configured = load_registry(self.registry)
        self.assertEqual(configured, {"archive-a": missing_collection})
        self.assertFalse(missing_collection.exists())

    def test_duplicate_keys_nonabsolute_paths_and_path_ids_are_rejected(self) -> None:
        documents = [
            '{"format":"lpx-keepmorrow.chatgpt-registry","version":1,"collections":{},"collections":{}}',
            json.dumps({"format": REGISTRY_FORMAT, "version": 1, "collections": {"archive-a": "relative/path"}}),
            json.dumps({"format": REGISTRY_FORMAT, "version": 1, "collections": {"../escape": str(self.root)}}),
            json.dumps({"format": REGISTRY_FORMAT, "version": True, "collections": {}}),
        ]
        for document in documents:
            with self.subTest(document=document):
                self.registry.write_text(document, encoding="utf-8")
                with self.assertRaises(RegistryError):
                    load_registry(self.registry)

    def test_registry_errors_do_not_include_private_paths(self) -> None:
        private = self.root / "unavailable-private-registry.json"
        with self.assertRaises(RegistryError) as raised:
            load_registry(private)
        self.assertNotIn(str(private), str(raised.exception))


@unittest.skipUnless(_HAS_MCP, "The optional ChatGPT development dependency is not installed.")
class ChatGPTAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        first, second = write_export_pair(self.root)
        self.collection = self.root / "private-collection-path"
        import_exports([first, second], self.collection, account_namespace="synthetic-account")
        loaded = load_collection(self.collection)
        conversation = next(item for item in loaded.document["conversations"] if item["source_id"] == EVOLVING_ID)
        self.conversation_key = conversation["conversation_key"]
        self.first_revision = conversation["revisions"][0]["revision_id"]
        self.server = create_server({"archive-a": self.collection,
                                     "archive-b": self.root / "unavailable-private-path"})

    def assert_public_result(self, result, *, error: str | None = None) -> dict:
        self.assertEqual(result.isError, error is not None)
        document = result.structuredContent
        self.assertIsInstance(document, dict)
        serialized = json.dumps(document)
        self.assertNotIn(json.dumps(str(self.root))[1:-1], serialized)
        self.assertNotIn(json.dumps(str(self.collection))[1:-1], serialized)
        self.assertNotIn("unavailable-private-path", serialized)
        if error:
            self.assertEqual(document["error_code"], error)
        else:
            self.assertEqual(document["status"], "ok")
        return document

    async def test_sdk_initialization_tool_schemas_and_loopback_configuration(self) -> None:
        from mcp.shared.memory import create_connected_server_and_client_session
        self.assertEqual(self.server.settings.host, "127.0.0.1")
        self.assertTrue(self.server.settings.stateless_http)
        self.assertTrue(self.server.settings.json_response)
        async with create_connected_server_and_client_session(self.server, read_timeout_seconds=timedelta(seconds=5)) as client:
            listing = await client.list_tools()
            self.assertEqual({item.name for item in listing.tools}, {
                "list_collections", "browse_collection", "search_collection", "read_revision", "verify_collection",
            })
            for tool in listing.tools:
                self.assertTrue(tool.annotations.readOnlyHint)
                self.assertFalse(tool.annotations.destructiveHint)
                self.assertFalse(tool.annotations.openWorldHint)
                required = tool.inputSchema["required"]
                self.assertIn("terms_version", required)
                self.assertIn("privacy_version", required)
                self.assertNotIn("path", tool.inputSchema["properties"])
                self.assertNotIn(str(self.root), json.dumps(tool.model_dump()))

    async def test_list_ids_browse_search_read_and_verify_through_sdk(self) -> None:
        from mcp.shared.memory import create_connected_server_and_client_session
        async with create_connected_server_and_client_session(self.server, read_timeout_seconds=timedelta(seconds=5)) as client:
            result = self.assert_public_result(await client.call_tool("list_collections", {**_ACCEPTANCE, "limit": 1}))
            self.assertEqual(result["data"]["items"], [{"collection_id": "archive-a"}])
            self.assertEqual(result["data"]["next_offset"], 1)
            self.assertFalse(result["data"]["content_inspected"])
            browsed = self.assert_public_result(await client.call_tool("browse_collection", {
                **_ACCEPTANCE, "collection_id": "archive-a", "limit": 1,
                "project_id": "project-aurora", "revision_limit": 1,
            }))
            self.assertEqual(browsed["data"]["total"], 1)
            entry = browsed["data"]["items"][0]
            self.assertEqual(entry["conversation_key"], self.conversation_key)
            self.assertEqual(entry["revision_count"], 2)
            self.assertEqual(entry["next_revision_offset"], 1)
            next_revision = self.assert_public_result(await client.call_tool("browse_collection", {
                **_ACCEPTANCE, "collection_id": "archive-a", "project_id": "project-aurora",
                "revision_offset": 1, "revision_limit": 1,
            }))
            self.assertNotEqual(entry["revisions"][0]["revision_id"], next_revision["data"]["items"][0]["revisions"][0]["revision_id"])
            searched = self.assert_public_result(await client.call_tool("search_collection", {
                **_ACCEPTANCE, "collection_id": "archive-a", "query": "original", "limit": 1,
            }))
            self.assertEqual(len(searched["data"]["items"]), 1)
            self.assertTrue(searched["data"]["truncated"])
            read = self.assert_public_result(await client.call_tool("read_revision", {
                **_ACCEPTANCE, "collection_id": "archive-a", "conversation_key": self.conversation_key, "limit": 1,
            }))
            self.assertEqual(read["data"]["selection_basis"], "most_recently_supplied_occurrence")
            self.assertEqual(len(read["data"]["nodes"]), 1)
            self.assertEqual(read["data"]["next_offset"], 1)
            explicit = self.assert_public_result(await client.call_tool("read_revision", {
                **_ACCEPTANCE, "collection_id": "archive-a", "conversation_key": self.conversation_key,
                "revision_id": self.first_revision, "offset": 1, "limit": 1,
            }))
            self.assertEqual(explicit["data"]["selection_basis"], "explicit_revision")
            verified = self.assert_public_result(await client.call_tool("verify_collection", {
                **_ACCEPTANCE, "collection_id": "archive-a",
            }))
            self.assertTrue(verified["data"]["verified"])
            self.assertEqual(verified["data"]["account_completeness"], "not_asserted")
            self.assertEqual(verified["data"]["summary"]["conversation_count"], 4)

    async def test_refusal_precedes_registered_content_io_for_every_tool(self) -> None:
        from mcp.shared.memory import create_connected_server_and_client_session
        calls = [
            ("list_collections", {}),
            ("browse_collection", {"collection_id": "archive-a"}),
            ("search_collection", {"collection_id": "archive-a", "query": "private content"}),
            ("read_revision", {"collection_id": "archive-a", "conversation_key": self.conversation_key}),
            ("verify_collection", {"collection_id": "archive-a"}),
        ]
        async with create_connected_server_and_client_session(self.server, read_timeout_seconds=timedelta(seconds=5)) as client:
            for name, arguments in calls:
                with self.subTest(tool=name), ExitStack() as stack:
                    for method in ("stat", "lstat", "open", "resolve", "iterdir"):
                        stack.enter_context(patch.object(Path, method, side_effect=AssertionError("Content accessed before acceptance.")))
                    loader = stack.enter_context(patch("keepmorrow.integrations.chatgpt.server.load_collection",
                                                       side_effect=AssertionError("Content accessed before acceptance.")))
                    result = await client.call_tool(name, {**arguments, **_ACCEPTANCE, "terms_version": "outdated"})
                    document = self.assert_public_result(result, error="acceptance_required")
                    self.assertNotIn("acceptance", document)
                    loader.assert_not_called()

    async def test_unknown_ids_arbitrary_paths_and_invalid_pages_do_not_read_content(self) -> None:
        from mcp.shared.memory import create_connected_server_and_client_session
        cases = [
            ("browse_collection", {"collection_id": "unregistered"}, "unknown_collection"),
            ("browse_collection", {"collection_id": str(self.collection)}, "invalid_arguments"),
            ("browse_collection", {"collection_id": "archive-a", "limit": 51}, "invalid_arguments"),
            ("browse_collection", {"collection_id": "archive-a", "offset": -1}, "invalid_arguments"),
            ("browse_collection", {"collection_id": "archive-a", "association_state": "unsupported"}, "invalid_arguments"),
            ("search_collection", {"collection_id": "archive-a", "query": " "}, "invalid_arguments"),
            ("read_revision", {"collection_id": "archive-a", "conversation_key": "not-a-digest"}, "invalid_arguments"),
        ]
        async with create_connected_server_and_client_session(self.server, read_timeout_seconds=timedelta(seconds=5)) as client:
            for tool, arguments, code in cases:
                with self.subTest(tool=tool, code=code), patch(
                    "keepmorrow.integrations.chatgpt.server.load_collection",
                    side_effect=AssertionError("Invalid requests must not inspect content."),
                ) as loader:
                    self.assert_public_result(await client.call_tool(tool, {**_ACCEPTANCE, **arguments}), error=code)
                    loader.assert_not_called()

    async def test_concurrent_requests_are_rejected_as_busy_then_succeed_after_completion(self) -> None:
        import anyio
        from mcp.shared.memory import create_connected_server_and_client_session
        entered, release = threading.Event(), threading.Event()
        loaded = load_collection(self.collection)
        results = []

        def blocked_read(path: Path):
            entered.set()
            if not release.wait(timeout=3):
                raise AssertionError("The bounded synthetic read was not released.")
            return loaded

        async with create_connected_server_and_client_session(self.server, read_timeout_seconds=timedelta(seconds=5)) as client:
            async def first_request() -> None:
                results.append(await client.call_tool("verify_collection", {
                    **_ACCEPTANCE, "collection_id": "archive-a",
                }))

            with patch("keepmorrow.integrations.chatgpt.server.load_collection", side_effect=blocked_read) as loader:
                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(first_request)
                    try:
                        self.assertTrue(await anyio.to_thread.run_sync(entered.wait, 2))
                        self.assert_public_result(await client.call_tool("verify_collection", {
                            **_ACCEPTANCE, "collection_id": "archive-a",
                        }), error="busy")
                        self.assertEqual(loader.call_count, 1)
                    finally:
                        release.set()
                self.assert_public_result(results[0])
                self.assert_public_result(await client.call_tool("verify_collection", {
                    **_ACCEPTANCE, "collection_id": "archive-a",
                }))
                self.assertEqual(loader.call_count, 2)

    async def test_handler_rejects_unhashable_association_filters_before_content_io(self) -> None:
        # Exercise the registered handler directly because SDK argument models
        # normally reject these values before the application's own boundary.
        handler = self.server._tool_manager.get_tool("browse_collection").fn
        with patch("keepmorrow.integrations.chatgpt.server.load_collection",
                   side_effect=AssertionError("Invalid filters must not inspect content.")) as loader:
            for state in ([], {}):
                with self.subTest(state=state):
                    self.assert_public_result(await handler(
                        collection_id="archive-a", association_state=state, **_ACCEPTANCE,
                    ), error="invalid_arguments")
            loader.assert_not_called()

    async def test_mcp_cancellation_does_not_release_a_running_verification_grant(self) -> None:
        import anyio
        from mcp.shared.exceptions import McpError
        from mcp.shared.memory import create_connected_server_and_client_session
        from mcp.types import ClientNotification, CancelledNotification, CancelledNotificationParams
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        cancelled = anyio.Event()
        loaded = load_collection(self.collection)
        request_ids = []

        def blocked_read(path: Path):
            request_ids.append(self.server.get_context().request_context.request_id)
            entered.set()
            try:
                if not release.wait(timeout=3):
                    raise AssertionError("The cancelled synthetic read was not released.")
                return loaded
            finally:
                finished.set()

        async with create_connected_server_and_client_session(self.server, read_timeout_seconds=timedelta(seconds=5)) as client:
            async def cancelled_request() -> None:
                try:
                    await client.call_tool("verify_collection", {**_ACCEPTANCE, "collection_id": "archive-a"})
                except McpError as error:
                    self.assertEqual(error.error.code, 0)
                    cancelled.set()

            with patch("keepmorrow.integrations.chatgpt.server.load_collection", side_effect=blocked_read) as loader:
                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(cancelled_request)
                    try:
                        self.assertTrue(await anyio.to_thread.run_sync(entered.wait, 2))
                        await client.send_notification(ClientNotification(CancelledNotification(
                            params=CancelledNotificationParams(requestId=request_ids[0], reason="Synthetic cancellation test"),
                        )))
                        with anyio.fail_after(2):
                            await cancelled.wait()
                        self.assertFalse(finished.is_set())
                        self.assert_public_result(await client.call_tool("verify_collection", {
                            **_ACCEPTANCE, "collection_id": "archive-a",
                        }), error="busy")
                        self.assertEqual(loader.call_count, 1)
                    finally:
                        release.set()
                        self.assertTrue(await anyio.to_thread.run_sync(finished.wait, 2))

    async def test_missing_and_corrupt_collections_return_sanitized_errors(self) -> None:
        from mcp.shared.memory import create_connected_server_and_client_session
        async with create_connected_server_and_client_session(self.server, read_timeout_seconds=timedelta(seconds=5)) as client:
            self.assert_public_result(await client.call_tool("verify_collection", {
                **_ACCEPTANCE, "collection_id": "archive-b",
            }), error="collection_unavailable")
            self.assert_public_result(await client.call_tool("read_revision", {
                **_ACCEPTANCE, "collection_id": "archive-a", "conversation_key": self.conversation_key,
                "revision_id": "0" * 64,
            }), error="invalid_arguments")
            path = self.collection / "payload/captures/000001/source/assets/diagram.png"
            path.write_bytes(b"x" * path.stat().st_size)
            self.assert_public_result(await client.call_tool("verify_collection", {
                **_ACCEPTANCE, "collection_id": "archive-a",
            }), error="collection_validation_failed")

    async def test_result_budget_is_explicit_and_unexpected_errors_are_sanitized(self) -> None:
        from mcp.shared.memory import create_connected_server_and_client_session
        async with create_connected_server_and_client_session(self.server, read_timeout_seconds=timedelta(seconds=5)) as client:
            with patch("keepmorrow.integrations.chatgpt.server.MAX_RESULT_BYTES", 500):
                self.assert_public_result(await client.call_tool("browse_collection", {
                    **_ACCEPTANCE, "collection_id": "archive-a",
                }), error="result_too_large")
            with patch("keepmorrow.integrations.chatgpt.server.load_collection",
                       side_effect=RuntimeError(str(self.collection))):
                with self.assertLogs("keepmorrow.integrations.chatgpt.server", level="ERROR") as logs:
                    self.assert_public_result(await client.call_tool("verify_collection", {
                        **_ACCEPTANCE, "collection_id": "archive-a",
                    }), error="internal_error")
                self.assertNotIn(str(self.root), " ".join(logs.output))

    async def test_streamable_http_asgi_transport_initializes_and_calls_tools(self) -> None:
        import httpx
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        app = self.server.streamable_http_app()
        async with self.server.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                        base_url="http://127.0.0.1:8765") as http_client:
                async with streamable_http_client("http://127.0.0.1:8765/mcp", http_client=http_client) as streams:
                    async with ClientSession(streams[0], streams[1], read_timeout_seconds=timedelta(seconds=5)) as client:
                        initialized = await client.initialize()
                        self.assertEqual(initialized.serverInfo.name, "LPX Keepmorrow Development")
                        self.assert_public_result(await client.call_tool("list_collections", _ACCEPTANCE))
                rejected = await http_client.post("/mcp", headers={"Host": "untrusted.example"}, json={})
                self.assertIn(rejected.status_code, (400, 403, 421))


if __name__ == "__main__":
    unittest.main()
