"""Exercise portal HTTP contracts through in-process ASGI clients.

Inputs, gestures, and identity-provider responses are synthetic. Direct ASGI
frames additionally expose disconnect and streaming boundaries without relying
on a network socket or an authenticated external account.
"""

from contextlib import contextmanager
from dataclasses import replace
import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

try:
    import httpx
    from mcp.server.auth.provider import AccessToken
    from starlette.testclient import TestClient
    from keepmorrow.integrations.chatgpt.portal import create_portal
except ImportError:
    OPTIONAL_PORTAL_AVAILABLE = False
else:
    OPTIONAL_PORTAL_AVAILABLE = True

from keepmorrow.access import AccessDenied, Principal
from keepmorrow.application.configuration import BrowserOAuth, Resource, ServiceConfiguration
from keepmorrow.application.service import PreservationService, manifest_digest, workspace_id
from keepmorrow.catalog.service import import_exports
from tests.fixtures.chatgpt_exports import write_export_pair


@unittest.skipUnless(OPTIONAL_PORTAL_AVAILABLE, "Install optional ChatGPT dependencies to test the browser portal.")
class PortalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.principal = Principal("urn:lpx-keepmorrow:local-operator", "synthetic-owner")
        first, _ = write_export_pair(self.root)
        source = self.root / "source"
        import_exports([first], source, account_namespace="synthetic-source")
        self.generation = manifest_digest(source)
        state = self.root / "state"
        state.mkdir()
        self.operator_key = secrets.token_hex(32)
        key_path = state / "operator.key"
        descriptor = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write(self.operator_key + "\n")
        self.configuration = ServiceConfiguration(
            state, Path("legal").resolve(), "http://127.0.0.1:8765", (self.principal,),
            resources=(Resource("collection", self.generation, self.principal.principal_id, source),),
        )
        self.service = PreservationService(self.configuration)
        self.service.start_worker()
        self.addCleanup(self.service.stop_worker)
        self.app = create_portal(self.service)
        self.client = TestClient(self.app, base_url=self.configuration.public_origin)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {"Origin": self.configuration.public_origin}

    def login(self):
        response = self.client.post("/auth/operator", json={"key": self.operator_key}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        session = self.client.get("/api/session")
        self.assertEqual(session.status_code, 200, session.text)
        self.headers["X-CSRF-Token"] = session.json()["csrf"]
        return response, session.json()

    def consent(self, resource_id="collection", generation=None, actions=None):
        prepared = self.client.post("/api/consent/prepare", json={
            "resource_id": resource_id, "generation": generation or self.generation,
            "actions": actions or ["browse", "read"],
        }, headers=self.headers)
        self.assertEqual(prepared.status_code, 200, prepared.text)
        body = {**prepared.json(), "accepted_terms": True, "acknowledged_privacy": True,
                "authorized_scope": True, "eligible_content": True}
        accepted = self.client.post("/api/consent/accept", json=body, headers=self.headers)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        return prepared.json(), body

    def wait_operation(self, operation_id):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            page = self.client.get("/api/operations").json()
            operation = next(item for item in page["items"] if item["operation_id"] == operation_id)
            if operation["state"] in {"completed", "partial", "failed", "cancelled", "interrupted"}:
                self.assertIn(operation["state"], {"completed", "partial"}, operation)
                return operation
            time.sleep(0.01)
        self.fail("The synthetic operation did not complete within its test budget.")

    def test_local_login_is_cookie_only_and_sends_security_headers(self) -> None:
        refused = self.client.get("/api/session", headers={"Authorization": "Bearer model-supplied-token"})
        self.assertEqual(refused.status_code, 401)
        response, session = self.login()
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertNotIn(self.operator_key, response.text)
        self.assertEqual(session["grants"], [])
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    def test_wrong_host_origin_missing_csrf_and_bearer_only_cannot_create_acceptance(self) -> None:
        self.login()
        body = {"resource_id": "collection", "generation": self.generation, "actions": ["read"]}
        for headers in (
            {"Origin": "https://attacker.example.test", "X-CSRF-Token": self.headers["X-CSRF-Token"]},
            {"Origin": self.configuration.public_origin},
            {"Origin": self.configuration.public_origin, "X-CSRF-Token": "incorrect"},
            {"Origin": self.configuration.public_origin, "X-CSRF-Token": self.headers["X-CSRF-Token"], "Host": "attacker.example.test"},
        ):
            with self.subTest(headers=headers):
                response = self.client.post("/api/consent/prepare", json=body, headers=headers)
                self.assertEqual(response.status_code, 403)
        self.client.cookies.clear()
        response = self.client.post("/api/consent/prepare", json=body, headers={**self.headers, "Authorization": "Bearer model-token"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.service.access.list_grants(self.principal), ())

    def test_consent_requires_all_choices_exact_scope_and_single_use_human_gesture(self) -> None:
        self.login()
        prepare = self.client.post("/api/consent/prepare", json={
            "resource_id": "collection", "generation": self.generation, "actions": ["read", "browse"],
        }, headers=self.headers).json()
        base = {**prepare, "accepted_terms": True, "acknowledged_privacy": True,
                "authorized_scope": True, "eligible_content": True}
        for changes in (
            {"eligible_content": False}, {"accepted_terms": 1}, {"generation": "d" * 64},
            {"actions": ["browse", "read", "recover"]}, {"policies": {**prepare["policies"], "terms_sha256": "e" * 64}},
        ):
            with self.subTest(changes=changes):
                refused = self.client.post("/api/consent/accept", json={**base, **changes}, headers=self.headers)
                self.assertEqual(refused.status_code, 403, refused.text)
        self.assertEqual(self.service.access.list_grants(self.principal), ())
        accepted = self.client.post("/api/consent/accept", json=base, headers=self.headers)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        replay = self.client.post("/api/consent/accept", json=base, headers=self.headers)
        self.assertEqual(replay.status_code, 403, replay.text)

    def test_query_requires_current_scope_before_content_io_and_revocation_blocks_later_reads(self) -> None:
        self.login()
        body = {"kind": "browse", "collection_id": "collection", "generation": self.generation}
        with patch("keepmorrow.application.service.load_collection", side_effect=AssertionError("Unauthorized content access")):
            response = self.client.post("/api/query", json=body, headers=self.headers)
        self.assertEqual(response.status_code, 403, response.text)
        grant, _ = self.consent()
        response = self.client.post("/api/query", json=body, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["items"])
        revoked = self.client.post("/api/grants/revoke", json={"grant_id": grant["grant_id"], "grant_version": grant["grant_version"]}, headers=self.headers)
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(self.client.post("/api/query", json=body, headers=self.headers).status_code, 403)

    def test_json_limits_duplicate_keys_and_errors_do_not_echo_private_input(self) -> None:
        self.login()
        private = "private-source-name-and-query"
        for content in (b'{"kind":"read","kind":"read"}', b"{" + b" " * 65_536 + b"}", json.dumps({"unknown": private}).encode()):
            response = self.client.post("/api/query", content=content, headers={**self.headers, "Content-Type": "application/json"})
            self.assertEqual(response.status_code, 400, response.text)
            self.assertNotIn(private, response.text)
        for path, key in (("/policies/terms", "terms"), ("/policies/privacy", "privacy")):
            response = self.client.get(path)
            self.assertEqual(response.content, self.service.policy_documents[key])

    def test_upload_is_consented_length_bound_and_its_handle_is_owner_scoped(self) -> None:
        self.login()
        data = b"synthetic uploaded bytes\x00" * 20_000
        headers = {**self.headers, "Content-Type": "application/octet-stream", "X-File-Name": "chosen%20file.bin"}
        refused = self.client.post("/api/uploads", content=data, headers=headers)
        self.assertEqual(refused.status_code, 403)
        self.consent(workspace_id(self.principal), "workspace_v1", ["upload"])
        uploaded = self.client.post("/api/uploads", content=data, headers=headers)
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        receipt = uploaded.json()
        self.assertEqual(receipt["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(receipt["display_name"], "chosen file.bin")
        self.assertNotIn("owner_id", receipt)
        with self.service.uploads.open_upload(self.principal.principal_id, receipt["upload_id"]) as (_, stream):
            self.assertEqual(stream.read(), data)
        bad = self.client.post("/api/uploads", content=b"short", headers={**headers, "Content-Length": "4"})
        self.assertEqual(bad.status_code, 422, bad.text)

    def test_review_is_separate_from_preparation_and_start_and_delivery_needs_new_consent(self) -> None:
        self.login()
        self.consent(actions=["package"])
        prepared = self.client.post("/api/operations/prepare", json={
            "kind": "package", "resource_id": "collection", "generation": self.generation, "parameters": {},
        }, headers=self.headers)
        self.assertEqual(prepared.status_code, 200, prepared.text)
        plan = prepared.json()
        start_body = {"plan_id": plan["plan_id"], "idempotency_key": "http-package-once"}
        self.assertEqual(self.client.post("/api/operations/start", json=start_body, headers=self.headers).status_code, 400)
        review_data = self.client.get("/api/plans/" + plan["plan_id"]).json()
        review_body = {"parameter_digest": plan["parameter_digest"], "challenge": review_data["challenge"], "approved": True}
        reviewed = self.client.post("/api/plans/" + plan["plan_id"] + "/review", json=review_body, headers=self.headers)
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(self.client.get("/api/operations").json()["items"], [])
        self.assertEqual(self.client.post("/api/plans/" + plan["plan_id"] + "/review", json=review_body, headers=self.headers).status_code, 403)
        started = self.client.post("/api/operations/start", json=start_body, headers=self.headers)
        self.assertEqual(started.status_code, 200, started.text)
        repeated = self.client.post("/api/operations/start", json=start_body, headers=self.headers)
        self.assertEqual(repeated.json()["operation_id"], started.json()["operation_id"])
        completed = self.wait_operation(started.json()["operation_id"])
        resource, generation = completed["output_id"], completed["result"]["manifest_sha256"]
        url = "/api/downloads/" + resource + "?generation=" + generation
        self.assertEqual(self.client.get(url).status_code, 403)
        self.consent(resource, generation, ["download"])
        download = self.client.get(url)
        self.assertEqual(download.status_code, 200, download.text[:200])
        self.assertEqual(hashlib.sha256(download.content).hexdigest(), completed["result"]["artifact_sha256"])
        self.assertEqual(len(download.content), int(download.headers["content-length"]))
        self.assertFalse(self.service._io.locked())

    def test_download_context_is_closed_if_access_is_withdrawn_while_streaming(self) -> None:
        self.login()
        checks, closed = [], []
        decision = type("Decision", (), {"grant_id": "grant_test", "grant_version": 1, "acceptance_id": "acceptance_test"})()

        @contextmanager
        def synthetic_download(*args):
            try:
                yield io.BytesIO(b"a" * 200_000), 200_000
            finally:
                closed.append(True)

        def authorize(*args, **kwargs):
            checks.append(True)
            if len(checks) > 3:
                raise AccessDenied()
            return decision

        with patch.object(self.service, "download", synthetic_download), patch.object(self.service, "_require", authorize), patch.object(self.service, "_require_origin"), patch.object(self.service.resources, "resolve"):
            response = self.client.get("/api/downloads/package?generation=" + "a" * 64)
        self.assertEqual(response.status_code, 200)
        self.assertLess(len(response.content), 200_000)
        self.assertEqual(closed, [True])

    def test_package_expiry_during_delivery_stops_frames_even_with_a_live_grant(self) -> None:
        self.login()
        resolutions, closed = [], []
        decision = type("Decision", (), {"grant_id": "grant_test", "grant_version": 1, "acceptance_id": "acceptance_test"})()

        @contextmanager
        def synthetic_download(*args):
            try:
                yield io.BytesIO(b"a" * 200_000), 200_000
            finally:
                closed.append(True)

        def resource_available(*args):
            resolutions.append(True)
            if len(resolutions) > 2:
                raise AccessDenied()

        with patch.object(self.service, "download", synthetic_download), patch.object(self.service, "_require", return_value=decision), patch.object(self.service, "_require_origin"), patch.object(self.service.resources, "resolve", side_effect=resource_available):
            response = self.client.get("/api/downloads/package?generation=" + "a" * 64)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content), 64 * 1024)
        self.assertEqual(closed, [True])

    def test_logout_prevents_new_requests_and_challenges(self) -> None:
        self.login()
        prepared, _ = self.consent()
        response = self.client.post("/auth/logout", json={}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get("/api/session").status_code, 401)
        with self.service.database.transaction(immediate=False) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM km_human_challenges").fetchone()[0], 0)
            context = connection.execute("SELECT * FROM km_human_acceptance_context").fetchone()
            self.assertEqual(context["eligibility_version"], prepared["eligibility_version"])
            snapshot = {key: value for key, value in prepared.items() if key != "challenge"}
            digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(context["scope_sha256"], digest)

    def asgi_scope(self, path, *, method="GET", extra_headers=()):
        return {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": method, "scheme": "http",
            "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
            "server": ("127.0.0.1", 8765), "client": ("127.0.0.1", 40000),
            "headers": [(b"host", b"127.0.0.1:8765"),
                        (b"cookie", ("lpx_keepmorrow_session=" + self.client.cookies.get("lpx_keepmorrow_session")).encode()),
                        (b"origin", self.configuration.public_origin.encode()),
                        (b"x-csrf-token", self.headers["X-CSRF-Token"].encode()), *extra_headers],
        }

    def test_upload_disconnect_waits_for_reservation_and_staging_cleanup(self) -> None:
        self.login()
        self.consent(workspace_id(self.principal), "workspace_v1", ["upload"])
        scope = self.asgi_scope("/api/uploads", method="POST", extra_headers=(
            (b"content-type", b"application/octet-stream"), (b"content-length", b"100000"),
            (b"x-file-name", b"interrupted.bin"),
        ))
        messages = [{"type": "http.request", "body": b"first bounded chunk", "more_body": True},
                    {"type": "http.disconnect"}]
        observed = []

        async def receive():
            return messages.pop(0)

        async def send(message):
            observed.append(message)

        asyncio.run(self.app(scope, receive, send))
        self.assertEqual(observed[0]["status"], 503)
        self.assertEqual(list(self.service.uploads._objects.iterdir()), [])
        with self.service.uploads._connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uploads").fetchone()[0], 0)

    def test_download_disconnect_closes_context_after_response_started(self) -> None:
        self.login()
        closed = []
        decision = type("Decision", (), {"grant_id": "grant_test", "grant_version": 1, "acceptance_id": "acceptance_test"})()

        @contextmanager
        def synthetic_download(*args):
            try:
                yield io.BytesIO(b"a" * 200_000), 200_000
            finally:
                closed.append(True)

        scope = self.asgi_scope("/api/downloads/package")
        scope["query_string"] = b"generation=" + b"a" * 64

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.body":
                raise OSError("Synthetic client disconnect.")

        from starlette.requests import ClientDisconnect
        with patch.object(self.service, "download", synthetic_download), patch.object(self.service, "_require", return_value=decision), patch.object(self.service, "_require_origin"), patch.object(self.service.resources, "resolve"):
            with self.assertRaises(ClientDisconnect):
                asyncio.run(self.app(scope, receive, send))
        self.assertEqual(closed, [True])


@unittest.skipUnless(OPTIONAL_PORTAL_AVAILABLE, "Install optional ChatGPT dependencies to test OAuth browser routes.")
class BrowserOAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.principal = Principal("https://identity.example.test", "synthetic-owner")
        self.other = Principal(self.principal.issuer, "synthetic-other")
        self.configuration = ServiceConfiguration(
            self.root, Path("legal").resolve(), "https://keepmorrow.example.test", (self.principal, self.other), mode="oauth",
            oauth_issuer=self.principal.issuer, oauth_jwks_uri="https://identity.example.test/keys",
            browser_oauth=BrowserOAuth("browser-client", "https://identity.example.test/authorize", "https://identity.example.test/token"),
        )
        self.service = PreservationService(self.configuration)
        self.verified_tokens = []
        parent = self

        class Verifier:
            async def verify_token(self, token):
                parent.verified_tokens.append(token)
                return AccessToken(token=token, client_id="browser-client", scopes=["keepmorrow:access"],
                                   expires_at=int(time.time()) + 600, resource=parent.configuration.resource_url,
                                   subject=parent.principal.subject, claims={"iss": parent.principal.issuer})

        self.app = create_portal(self.service, Verifier())
        self.client = TestClient(self.app, base_url=self.configuration.public_origin)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_browser_flow_binds_state_pkce_client_resource_and_single_use_callback(self) -> None:
        login = self.client.get("/auth/login", follow_redirects=False)
        self.assertEqual(login.status_code, 303, login.text)
        query = parse_qs(urlsplit(login.headers["location"]).query)
        self.assertEqual(query["resource"], [self.configuration.resource_url])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertIn("Secure", login.headers["set-cookie"])
        self.assertEqual(self.client.get("/auth/callback?state=" + "a" * 64 + "&code=synthetic-code").status_code, 403)
        real_client = httpx.AsyncClient
        observed = []

        class Raw(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield json.dumps({"access_token": "synthetic-verified-token", "token_type": "Bearer"}).encode()

        def handler(request):
            self.assertEqual(str(request.url), self.configuration.browser_oauth.token_endpoint)
            fields = parse_qs(request.content.decode())
            observed.append(fields)
            import base64
            challenge = base64.urlsafe_b64encode(hashlib.sha256(fields["code_verifier"][0].encode()).digest()).rstrip(b"=").decode()
            self.assertEqual(challenge, query["code_challenge"][0])
            self.assertEqual(fields["client_id"], ["browser-client"])
            self.assertEqual(fields["redirect_uri"], [self.configuration.public_origin + "/auth/callback"])
            self.assertEqual(fields["resource"], [self.configuration.resource_url])
            return httpx.Response(200, stream=Raw())

        def outbound(**options):
            self.assertFalse(options["follow_redirects"])
            self.assertFalse(options["trust_env"])
            return real_client(transport=httpx.MockTransport(handler), **options)

        callback = "/auth/callback?state=" + query["state"][0] + "&code=synthetic-code"
        with patch("keepmorrow.integrations.chatgpt.portal.httpx.AsyncClient", side_effect=outbound):
            result = self.client.get(callback, follow_redirects=False)
            self.assertEqual(result.status_code, 303, result.text)
            self.client.cookies.set("lpx_keepmorrow_oauth_state", query["state"][0], domain="keepmorrow.example.test", path="/auth")
            self.assertEqual(self.client.get(callback, follow_redirects=False).status_code, 403)
        self.assertEqual(len(observed), 1)
        self.assertEqual(self.verified_tokens, ["synthetic-verified-token"])
        self.assertIn("HttpOnly", result.headers["set-cookie"])
        self.assertIn("Secure", result.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/session").status_code, 200)
        self.assertNotIn(b"synthetic-verified-token", self.service.database.path.read_bytes())

    def test_valid_second_identity_cannot_list_accept_or_revoke_the_first_identity_scope(self) -> None:
        grant = self.service.prepare_consent(self.principal, resource_id=workspace_id(self.principal),
                                             generation="workspace_v1", actions=["upload"])
        self.service.access.accept_grant(
            self.principal, grant_id=grant.grant_id, expected_grant_version=1,
            policies=self.service.policies, actions=["upload"], interaction_id="synthetic-owner-human",
        )
        sessions = self.app.state.human_sessions
        cookie = sessions.create(self.other.principal_id, expires_at=int(time.time()) + 600)
        self.client.cookies.set("lpx_keepmorrow_session", cookie, domain="keepmorrow.example.test", path="/")
        session = self.client.get("/api/session")
        self.assertEqual(session.status_code, 200, session.text)
        self.assertEqual(session.json()["grants"], [])
        self.assertEqual(session.json()["options"]["workspace"]["resource_id"], workspace_id(self.other))
        headers = {"Origin": self.configuration.public_origin, "X-CSRF-Token": session.json()["csrf"]}
        revoked = self.client.post("/api/grants/revoke", json={"grant_id": grant.grant_id, "grant_version": 1}, headers=headers)
        self.assertEqual(revoked.status_code, 403)
        prepare = self.client.post("/api/consent/prepare", json={"resource_id": workspace_id(self.principal),
                                  "generation": "workspace_v1", "actions": ["upload"]}, headers=headers)
        self.assertEqual(prepare.status_code, 403)
        self.service.access.require_access(self.principal, resource_id=workspace_id(self.principal), generation="workspace_v1", action="upload")


if __name__ == "__main__":
    unittest.main()
