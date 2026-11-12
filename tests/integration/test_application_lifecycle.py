"""Failed application startup cannot leave a live worker holding its process lock."""

import importlib.util
import os
from pathlib import Path
import tempfile
import traceback
import unittest
from unittest.mock import patch

from keepmorrow.access import Principal
from keepmorrow.application.configuration import ServiceConfiguration


@unittest.skipUnless(importlib.util.find_spec("mcp"), "Optional private service dependencies are not installed.")
class ApplicationLifecycleTests(unittest.TestCase):
    def test_maintenance_failure_during_startup_stops_worker_and_releases_lock(self) -> None:
        from starlette.testclient import TestClient
        from keepmorrow.integrations.chatgpt.application import create_application

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            descriptor = os.open(root / "operator.key", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write("a" * 64 + "\n")
            configuration = ServiceConfiguration(
                root, Path("legal").resolve(), "http://127.0.0.1:8765",
                (Principal("urn:lpx-keepmorrow:local-operator", "synthetic-owner"),),
            )
            app = create_application(configuration)
            service = app.state.preservation_service
            try:
                private_diagnostic = f"Synthetic startup failure while inspecting {root / 'private-state.db'}."
                with patch.object(service, "maintenance", side_effect=RuntimeError(private_diagnostic)):
                    try:
                        with TestClient(app, base_url=configuration.public_origin):
                            self.fail("A failed startup must not accept application requests.")
                    except RuntimeError as error:
                        self.assertEqual(str(error), "Keepmorrow could not start safely. Operator review is required.")
                        self.assertTrue(error.__suppress_context__)
                        diagnostic = "".join(traceback.format_exception(error))
                        self.assertNotIn(str(root), diagnostic)
                        self.assertNotIn(private_diagnostic, diagnostic)
                    else:
                        self.fail("A failed startup must surface a sanitized diagnostic.")
                self.assertFalse(service.worker._thread.is_alive())
                with service.operations.acquire_worker():
                    pass
            finally:
                service.stop_worker()


if __name__ == "__main__":
    unittest.main()
