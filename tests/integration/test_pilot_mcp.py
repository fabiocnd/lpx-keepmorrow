"""Exercise MCP authorization through an in-process ASGI transport.

Fixed synthetic bearer tokens isolate SDK middleware and resource permissions.
Cryptographic verification is tested separately; no live OAuth issuer or actual
ChatGPT account participates in these protocol sessions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from keepmorrow.access import Principal
from keepmorrow.application.configuration import BrowserOAuth, Resource, ServiceConfiguration
from keepmorrow.application.service import PreservationService, manifest_digest
from keepmorrow.catalog.service import import_exports, load_collection
from tests.fixtures.chatgpt_exports import EVOLVING_ID, write_export_pair

_HAS_MCP = importlib.util.find_spec("mcp") is not None


@unittest.skipUnless(_HAS_MCP, "The optional authenticated ChatGPT dependencies are not installed.")
class PilotMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        from mcp.server.auth.provider import AccessToken
        from keepmorrow.integrations.chatgpt.pilot_server import create_pilot_server
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.owner = Principal("https://issuer.example", "synthetic-owner")
        self.other = Principal(self.owner.issuer, "synthetic-other")
        first, second = write_export_pair(self.root)
        source = self.root / "private-source-location"
        import_exports([first, second], source, account_namespace="synthetic-source")
        self.generation = manifest_digest(source)
        self.conversation = next(item for item in load_collection(source).document["conversations"] if item["source_id"] == EVOLVING_ID)
        (self.root / "state").mkdir()
        configuration = ServiceConfiguration(
            self.root / "state", Path("legal").resolve(), "https://keepmorrow.example", (self.owner, self.other),
            resources=(Resource("collection_a", self.generation, self.owner.principal_id, source),),
            mode="oauth", oauth_issuer=self.owner.issuer, oauth_jwks_uri=self.owner.issuer + "/jwks",
            browser_oauth=BrowserOAuth("synthetic-browser-client", self.owner.issuer + "/authorize", self.owner.issuer + "/token"),
        )
        self.service = PreservationService(configuration)
        owner, other = self.owner, self.other

        class SyntheticVerifier:
            async def verify_token(self, token):
                identity = {"synthetic-owner-token": owner, "synthetic-other-token": other}.get(token)
                if identity is None:
                    return None
                return AccessToken(token=token, client_id="synthetic-client", scopes=["keepmorrow:access"],
                                   expires_at=int(time.time()) + 3600, subject=identity.subject,
                                   resource="https://keepmorrow.example/mcp", claims={"iss": identity.issuer})

        self.verifier = SyntheticVerifier()
        self.server = create_pilot_server(self.service, self.verifier, ui_html="<!doctype html><p>Synthetic companion</p>")
        self.app = self.server.streamable_http_app()

    def accept(self, actions):
        grant = self.service.prepare_consent(self.owner, resource_id="collection_a", generation=self.generation, actions=actions)
        self.service.access.accept_grant(self.owner, grant_id=grant.grant_id, expected_grant_version=grant.grant_version,
                                         policies=self.service.policies, actions=actions,
                                         interaction_id="test_" + uuid.uuid4().hex)
        return grant

    @asynccontextmanager
    async def client(self, token="synthetic-owner-token"):
        import httpx
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        from keepmorrow.integrations.chatgpt.pilot_server import create_pilot_server
        server = create_pilot_server(self.service, self.verifier, ui_html="<!doctype html><p>Synthetic companion</p>")
        app = server.streamable_http_app()
        async with server.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                          headers={"Authorization": "Bearer " + token}) as http_client:
                async with streamable_http_client("https://keepmorrow.example/mcp", http_client=http_client) as streams:
                    async with ClientSession(streams[0], streams[1]) as client:
                        await client.initialize()
                        yield client

    def response(self, result, error=None):
        self.assertEqual(result.isError, error is not None)
        document = result.structuredContent
        self.assertNotIn(str(self.root), json.dumps(document))
        self.assertNotIn("synthetic-owner-token", json.dumps(document))
        if error:
            self.assertEqual(document["error_code"], error)
        return document.get("data")

    async def test_http_requires_auth_and_advertises_exact_resource_metadata(self) -> None:
        import httpx
        async with self.server.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="https://keepmorrow.example") as client:
                response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
                self.assertEqual(response.status_code, 401)
                self.assertIn("resource_metadata", response.headers["www-authenticate"])
                metadata = await client.get("/.well-known/oauth-protected-resource/mcp")
                self.assertEqual(metadata.status_code, 200)
                self.assertEqual(metadata.json()["resource"], "https://keepmorrow.example/mcp")
                self.assertEqual(metadata.json()["authorization_servers"], [self.owner.issuer])

    async def test_tool_surface_cannot_create_human_acceptance_or_review(self) -> None:
        async with self.client() as client:
            tools = (await client.list_tools()).tools
            names = {item.name for item in tools}
            self.assertEqual(len(names), 16)
            self.assertFalse(any("accept" in name or "review" in name for name in names))
            for item in tools:
                self.assertNotIn("terms_version", item.inputSchema.get("properties", {}))
                self.assertNotIn("path", item.inputSchema.get("properties", {}))
            self.response(await client.call_tool("access_status", {}))
            with patch("keepmorrow.application.service.load_collection", side_effect=AssertionError("Consent boundary bypass")):
                self.response(await client.call_tool("browse_collection", {"collection_id": "collection_a", "generation": self.generation}), "access_denied")

    async def test_preservation_failures_use_validation_category_without_private_details(self) -> None:
        from keepmorrow.archive.model import ArchiveError
        self.accept(["verify"])
        async with self.client() as client:
            with patch.object(self.service, "_load", side_effect=ArchiveError("Private source path must not be disclosed.")):
                result = await client.call_tool("verify_collection", {"collection_id": "collection_a", "generation": self.generation})
            self.response(result, "validation_failed")
            self.assertNotIn("Private source path", json.dumps(result.structuredContent))

    async def test_identity_generation_and_revocation_control_actual_content(self) -> None:
        grant = self.accept(["browse", "read", "verify"])
        async with self.client() as client:
            listed = self.response(await client.call_tool("list_collections", {}))
            self.assertEqual(listed["items"], [{"collection_id": "collection_a", "generation": self.generation}])
            data = self.response(await client.call_tool("browse_collection", {"collection_id": "collection_a", "generation": self.generation, "limit": 1}))
            self.assertEqual(len(data["items"]), 1)
            self.response(await client.call_tool("read_revision", {"collection_id": "collection_a", "generation": self.generation,
                                                                  "conversation_key": self.conversation["conversation_key"],
                                                                  "revision_id": self.conversation["revisions"][0]["revision_id"]}))
            self.service.access.revoke_grant(self.owner, grant_id=grant.grant_id)
            self.response(await client.call_tool("verify_collection", {"collection_id": "collection_a", "generation": self.generation}), "access_denied")
        async with self.client("synthetic-other-token") as client:
            self.assertEqual(self.response(await client.call_tool("list_collections", {}))["items"], [])
            self.response(await client.call_tool("browse_collection", {"collection_id": "collection_a", "generation": self.generation}), "access_denied")

    async def test_planned_operation_requires_trusted_review_and_is_idempotent(self) -> None:
        self.accept(["recover"])
        self.service.start_worker()
        self.addCleanup(self.service.stop_worker)
        async with self.client() as client:
            plan = self.response(await client.call_tool("prepare_recovery", {
                "collection_id": "collection_a", "generation": self.generation,
                "conversation_keys": [self.conversation["conversation_key"]],
            }))
            args = {"plan_id": plan["plan_id"], "idempotency_key": "synthetic-request"}
            self.response(await client.call_tool("start_operation", args), "invalid_request")
            self.service.operations.record_human_review(self.owner.principal_id, plan["plan_id"],
                                                        parameter_digest=plan["parameter_digest"], interaction_id="synthetic_gesture")
            first = self.response(await client.call_tool("start_operation", args))
            second = self.response(await client.call_tool("start_operation", args))
            self.assertEqual(first["operation_id"], second["operation_id"])

    async def test_ui_resource_is_separate_and_unexpected_errors_are_sanitized(self) -> None:
        from keepmorrow.integrations.chatgpt.pilot_server import UI_RESOURCE
        self.accept(["verify"])
        async with self.client() as client:
            tools = (await client.list_tools()).tools
            rendered = [item for item in tools if item.meta and "ui" in item.meta]
            self.assertEqual([item.name for item in rendered], ["render_keepmorrow"])
            resource = await client.read_resource(UI_RESOURCE)
            self.assertEqual(resource.contents[0].mimeType, "text/html;profile=mcp-app")
            with patch("keepmorrow.application.service.load_collection", side_effect=RuntimeError(str(self.root))):
                self.response(await client.call_tool("verify_collection", {"collection_id": "collection_a", "generation": self.generation}), "unavailable")


if __name__ == "__main__":
    unittest.main()
