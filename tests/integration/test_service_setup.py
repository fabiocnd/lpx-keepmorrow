"""Installed setup boundaries and the combined portal/MCP application."""

from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from keepmorrow.application.cli import main
from keepmorrow.access import Principal
from keepmorrow.application.configuration import ConfigurationError, ServiceConfiguration, load_configuration


class ServiceSetupTests(unittest.TestCase):
    def test_configuration_rejects_storage_that_cannot_admit_one_operation(self) -> None:
        root = Path.cwd() / "synthetic-configuration-only"
        configuration = ServiceConfiguration(
            root, root / "policies", "http://127.0.0.1:8765",
            (Principal("urn:lpx-keepmorrow:local-operator", "synthetic-owner"),),
        )
        for limits in ({"max_storage_bytes": 1024**3}, {"max_upload_bytes": 1024**3}):
            with self.subTest(limits=limits), self.assertRaises(ConfigurationError):
                replace(configuration, **limits)
        largest_upload = replace(configuration, max_upload_bytes=1024**3, max_storage_bytes=6 * 1024**3)
        self.assertEqual(largest_upload.upload_pool_bytes, 4 * 1024**3)

    def test_initialization_is_private_no_clobber_and_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve() / "service"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(main(["init", str(root)]), 0)
            result = json.loads(stdout.getvalue())
            key = (root / "operator.key").read_text().strip()
            self.assertEqual(len(key), 64)
            self.assertNotIn(key, stdout.getvalue())
            self.assertFalse(result["content_processed"])
            self.assertFalse(result["mcp_enabled"])
            configuration = load_configuration(root / "service.json")
            self.assertEqual(configuration.resources, ())
            if os.name == "posix":
                self.assertEqual((root / "operator.key").stat().st_mode & 0o777, 0o600)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["init", str(root)]), 2)
            self.assertEqual((root / "operator.key").read_text().strip(), key)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["check", "--configuration", str(root / "service.json")]), 0)

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "Optional private service dependencies are not installed.")
    def test_combined_local_application_has_portal_and_no_mcp(self) -> None:
        from starlette.testclient import TestClient
        from keepmorrow.integrations.chatgpt.application import create_application
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve() / "service"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["init", str(root)]), 0)
            app = create_application(load_configuration(root / "service.json"))
            with TestClient(app, base_url="http://127.0.0.1:8765") as client:
                self.assertEqual(client.get("/").status_code, 200)
                self.assertIn("LPX Keepmorrow", client.get("/").text)
                self.assertEqual(client.get("/assets/portal.js").status_code, 200)
                self.assertEqual(client.get("/api/config").json()["mode"], "operator")
                self.assertEqual(client.post("/mcp", headers={"Origin": "http://127.0.0.1:8765"}).status_code, 404)
                self.assertEqual(client.get("/api/session").status_code, 401)

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "Optional private service dependencies are not installed.")
    def test_combined_oauth_application_keeps_sdk_authentication_middleware(self) -> None:
        from starlette.testclient import TestClient
        from keepmorrow.application.configuration import BrowserOAuth, ServiceConfiguration
        from keepmorrow.access import Principal
        from keepmorrow.integrations.chatgpt.application import create_application
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            principal = Principal("https://issuer.example", "synthetic-owner")
            configuration = ServiceConfiguration(root, Path("legal").resolve(), "https://keepmorrow.example", (principal,),
                mode="oauth", oauth_issuer=principal.issuer, oauth_jwks_uri=principal.issuer + "/jwks",
                browser_oauth=BrowserOAuth("browser-client", principal.issuer + "/authorize", principal.issuer + "/token"))
            with TestClient(create_application(configuration), base_url=configuration.public_origin) as client:
                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.post("/mcp").status_code, 401)
                metadata = client.get("/.well-known/oauth-protected-resource/mcp")
                self.assertEqual(metadata.status_code, 200)
                self.assertEqual(metadata.json()["resource"], configuration.resource_url)


if __name__ == "__main__":
    unittest.main()
