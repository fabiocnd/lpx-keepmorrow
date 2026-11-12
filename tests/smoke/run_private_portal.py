"""Exercise a running loopback portal with an isolated synthetic identity.

Initialize a fresh service with ``--operator synthetic-pilot`` before running
this script. All content and acceptance gestures are synthetic test fixtures;
the report never establishes human acceptance, OAuth, or ChatGPT installation.
The runner uses HTTP for service state and generates all input content itself.
On Linux, ``--launch-service``
owns a child server in the command's network namespace and requires a pristine
directory created by the initializer. This harness restriction does not change
the application's separately tested Linux and Windows support.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any
import uuid
import zipfile

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY))
sys.path.insert(0, str(REPOSITORY / "src"))

import httpx

from keepmorrow.application.configuration import load_configuration
from keepmorrow.application.service import workspace_id
from keepmorrow.archive.filesystem import open_regular, safe_directory
from tests.fixtures.chatgpt_exports import (
    EVOLVING_ID, MODEL_V1, PACKAGE_BYTES, TINY_PNG, UNRELATED_BYTES, export_records,
)

MAX_RESPONSE_BYTES = 8 * 1024**2
TERMINAL_STATES = {"completed", "partial", "failed", "cancelled", "interrupted", "expired"}
JSON = dict[str, Any]


class SmokeFailure(RuntimeError):
    """A fixed diagnostic code suitable for a credential-free report."""


def require(condition: object, code: str) -> None:
    if not condition:
        raise SmokeFailure(code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_input() -> tuple[bytes, dict[str, bytes]]:
    """Build deterministic fixture bytes without accepting an input file path."""
    records, _ = export_records()
    binaries = {
        "assets/diagram.png": TINY_PNG,
        "assets/character.glb": MODEL_V1,
        "assets/build.apk": PACKAGE_BYTES,
    }
    files = {**binaries, "assets/unrelated.bin": UNRELATED_BYTES,
             "conversations.json": json.dumps(records, sort_keys=True).encode("utf-8")}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, content in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100600 << 16
            archive.writestr(entry, content)
    return output.getvalue(), binaries


class PortalSmoke:
    """Drive the published HTTP contract without direct service-state access."""

    def __init__(self, configuration_path: Path, timeout_seconds: float) -> None:
        self.configuration = load_configuration(configuration_path)
        self.configuration_path = configuration_path.absolute()
        configuration = self.configuration
        require(configuration.mode == "operator", "operator_mode_required")
        require(configuration.public_origin == f"http://127.0.0.1:{configuration.port}", "loopback_required")
        require(len(configuration.principals) == 1 and configuration.principals[0].subject == "synthetic-pilot",
                "isolated_synthetic_identity_required")
        require(configuration.resources == (), "empty_configured_resources_required")
        self.timeout_seconds = timeout_seconds
        self.stage = "preflight"
        self.checks: dict[str, bool] = {}
        self.operations: list[JSON] = []
        self.http_status_counts: dict[str, int] = {}
        self.process: subprocess.Popen[bytes] | None = None
        self.lifecycle: JSON = {"launched_by_runner": False}
        self.headers = {"Origin": configuration.public_origin}
        self.client = httpx.Client(base_url=configuration.public_origin, trust_env=False,
                                   follow_redirects=False, timeout=httpx.Timeout(10.0, connect=3.0))

    def require_pristine_launch_directory(self) -> None:
        """Refuse existing runtime state before startup maintenance can inspect it."""
        root = self.configuration.state_directory
        require(self.configuration_path == root / "service.json", "initialized_configuration_path_required")
        require(self.configuration.policy_directory == root / "policies", "initialized_policy_directory_required")
        safe_directory(root)
        require({path.name for path in root.iterdir()} == {"service.json", "operator.key", "policies"},
                "pristine_initialized_directory_required")
        safe_directory(root / "policies")
        require({path.name for path in (root / "policies").iterdir()} == {"terms-of-use.md", "privacy-notice.md"},
                "pristine_initialized_policies_required")
        for path in (self.configuration_path, root / "operator.key", root / "policies/terms-of-use.md",
                     root / "policies/privacy-notice.md"):
            with open_regular(path):
                pass

    def probe_status(self, timeout_seconds: float) -> int:
        """Read only response headers; a readiness probe must not buffer a body."""
        with self.client.stream("GET", "/api/config", timeout=httpx.Timeout(timeout_seconds)) as response:
            return response.status_code

    def launch_service(self) -> None:
        """Own a Linux child in the same namespace without changing bind policy."""
        self.stage = "service_startup"
        require(sys.platform == "linux", "linux_child_launcher_required")
        self.require_pristine_launch_directory()
        try:
            self.probe_status(0.5)
        except httpx.ConnectError:
            pass
        except httpx.HTTPError:
            raise SmokeFailure("loopback_port_probe_unavailable") from None
        else:
            raise SmokeFailure("loopback_port_already_served")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "keepmorrow.application.cli", "serve", "--configuration",
             str(self.configuration_path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.lifecycle["launched_by_runner"] = True
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            require(self.process.poll() is None, "service_startup_failed")
            remaining_seconds = deadline - time.monotonic()
            require(remaining_seconds > 0, "service_startup_deadline_exceeded")
            try:
                status = self.probe_status(min(0.5, remaining_seconds))
            except httpx.ConnectError:
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
                continue
            except httpx.HTTPError:
                raise SmokeFailure("service_readiness_probe_unavailable") from None
            require(status == 200, "service_readiness_failed")
            self.lifecycle["readiness_checked"] = True
            return
        raise SmokeFailure("service_startup_deadline_exceeded")

    def close(self) -> bool:
        """Bound owned-child cleanup and preserve sanitized reporting on failure."""
        client_closed = True
        try:
            self.client.close()
        except Exception:
            client_closed = False
            self.lifecycle["client_close_error_code"] = "http_client_close_failed"
        if self.process is None:
            return client_closed
        graceful = False
        try:
            if self.process.poll() is None:
                try:
                    self.process.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    # A concurrent natural exit is resolved by the bounded wait.
                    pass
            code = self.process.wait(timeout=10.0)
            graceful = code == 0
        except Exception:
            self.lifecycle["shutdown_error_code"] = "child_graceful_shutdown_failed"
            try:
                if self.process.poll() is None:
                    self.process.kill()
                self.process.wait(timeout=5.0)
            except Exception:
                self.lifecycle["shutdown_error_code"] = "child_stop_unconfirmed"
        self.lifecycle.update(exit_code=self.process.returncode, graceful_shutdown=graceful)
        return client_closed and graceful

    def request(self, method: str, path: str, *, expected: int = 200,
                headers: dict[str, str] | None = None, **arguments: Any) -> httpx.Response:
        # The eight-MiB ceiling also bounds an unexpectedly large error response.
        # No response body, cookie, or exception text reaches the report.
        with self.client.stream(method, path, headers={**self.headers, **(headers or {})}, **arguments) as response:
            status = str(response.status_code)
            self.http_status_counts[status] = self.http_status_counts.get(status, 0) + 1
            require(response.status_code == expected, "unexpected_http_status")
            body = bytearray()
            for block in response.iter_bytes(chunk_size=64 * 1024):
                require(len(body) + len(block) <= MAX_RESPONSE_BYTES, "response_limit_exceeded")
                body.extend(block)
            return httpx.Response(response.status_code, headers=response.headers, content=bytes(body))

    def document(self, method: str, path: str, **arguments: Any) -> JSON:
        value = self.request(method, path, **arguments).json()
        require(isinstance(value, dict), "response_object_required")
        return value

    def consent(self, resource: str, generation: str, actions: list[str]) -> JSON:
        """Exercise synthetic acceptance, refusal, and single-use replay checks."""
        prepared = self.document("POST", "/api/consent/prepare", json={
            "resource_id": resource, "generation": generation, "actions": actions,
        })
        body = {**prepared, "accepted_terms": True, "acknowledged_privacy": True,
                "authorized_scope": True, "eligible_content": True}
        self.request("POST", "/api/consent/accept", expected=403,
                     json={**body, "authorized_scope": False})
        require(self.document("POST", "/api/consent/accept", json=body)["accepted"] is True,
                "synthetic_acceptance_not_recorded")
        self.request("POST", "/api/consent/accept", expected=403, json=body)
        self.checks["explicit_scope_and_single_use_acceptance"] = True
        return prepared

    def operate(self, kind: str, resource: str, generation: str, parameters: JSON) -> JSON:
        """Review one synthetic plan, prove idempotent start, and poll its outcome."""
        self.stage = kind
        plan = self.document("POST", "/api/operations/prepare", json={
            "kind": kind, "resource_id": resource, "generation": generation, "parameters": parameters,
        })
        start = {"plan_id": plan["plan_id"], "idempotency_key": "synthetic_http_" + uuid.uuid4().hex}
        self.request("POST", "/api/operations/start", expected=400, json=start)
        self.checks["unreviewed_start_refused"] = True
        detail = self.document("GET", "/api/plans/" + plan["plan_id"])
        review = {"parameter_digest": plan["parameter_digest"], "challenge": detail["challenge"], "approved": True}
        require(self.document("POST", "/api/plans/" + plan["plan_id"] + "/review", json=review)["reviewed"] is True,
                "synthetic_review_not_recorded")
        self.request("POST", "/api/plans/" + plan["plan_id"] + "/review", expected=403, json=review)
        self.checks["review_is_single_use"] = True
        started = self.document("POST", "/api/operations/start", json=start)
        replay = self.document("POST", "/api/operations/start", json=start)
        require(replay["operation_id"] == started["operation_id"], "idempotency_changed_operation")
        self.checks["idempotent_start"] = True
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            page = self.document("GET", "/api/operations")
            operation = next(item for item in page["items"] if item["operation_id"] == started["operation_id"])
            if operation["state"] in TERMINAL_STATES:
                require(operation["state"] in {"completed", "partial"} and operation["result"] is not None,
                        "operation_did_not_complete")
                self.operations.append({"kind": kind, "state": operation["state"],
                                        "coverage_gaps": operation["result"]["coverage_gaps"]})
                return operation
            time.sleep(0.05)
        raise SmokeFailure("operation_deadline_exceeded")

    def query(self, kind: str, resource: str, generation: str, **parameters: Any) -> JSON:
        return self.document("POST", "/api/query", json={
            "kind": kind, "collection_id": resource, "generation": generation, **parameters,
        })

    def verify_download(self, payload: bytes, expected_manifest: str, selected_key: str,
                        binaries: dict[str, bytes]) -> JSON:
        """Reconcile the bounded package inventory and its exact selected bytes.

        Verification is independent of the server's success status. Every file
        must match the enclosed manifest, and the selected binary fixtures must
        also match their independently generated originals.
        """
        self.stage = "download_integrity"
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            infos = archive.infolist()
            require(len(infos) <= 100 and sum(item.file_size for item in infos) <= MAX_RESPONSE_BYTES,
                    "package_fixture_bounds_exceeded")
            require(len({item.filename for item in infos}) == len(infos), "duplicate_package_members")
            manifest_bytes = archive.read("manifest.json")
            require(digest(manifest_bytes) == expected_manifest, "enclosed_manifest_changed")
            manifest = json.loads(manifest_bytes)
            files = {"payload/" + item["path"]: item for item in manifest["files"]}
            require({item.filename for item in infos if not item.is_dir()} == {"manifest.json", *files},
                    "unexpected_package_member")
            for name, record in files.items():
                content = archive.read(name)
                require(len(content) == record["size_bytes"] and digest(content) == record["sha256"],
                        "enclosed_file_integrity_failed")
            catalog = json.loads(archive.read("payload/catalog.json"))
            require([item["conversation_key"] for item in catalog["conversations"]] == [selected_key],
                    "recovery_selection_changed")
            require(catalog["scope"] == "selected_conversations", "recovery_scope_changed")
            binary_results = []
            for name, expected in sorted(binaries.items()):
                matches = [member for member in files if member.endswith("/source/" + name)]
                require(len(matches) == 1 and archive.read(matches[0]) == expected, "binary_bytes_changed")
                binary_results.append({"fixture": name, "size_bytes": len(expected), "sha256": digest(expected)})
            require(not any(name.endswith(("/conversations.json", "/original.zip", "/unrelated.bin")) for name in files),
                    "unselected_source_in_recovery")
        self.checks.update({"download_matches_delivery_digest": True, "enclosed_manifest_and_files_verified": True,
                            "selected_conversation_only": True, "supplied_binary_and_image_bytes_preserved": True,
                            "unselected_source_files_excluded": True})
        return {"size_bytes": len(payload), "sha256": digest(payload), "manifest_sha256": expected_manifest,
                "verified_payload_files": len(files), "selected_conversations": 1, "binaries": binary_results}

    def run(self) -> JSON:
        started = time.monotonic()
        fixture, binaries = synthetic_input()
        self.request("GET", "/api/session", expected=401)
        public = self.document("GET", "/api/config")
        require(public["mode"] == "operator" and public["portal_url"] == self.configuration.public_origin + "/portal",
                "unexpected_service_identity")
        with open_regular(self.configuration.state_directory / "operator.key") as source:
            key = source.read(96).decode("ascii").strip()
        require(re.fullmatch(r"[0-9a-f]{64}", key) is not None, "invalid_local_key_file")
        login = self.request("POST", "/auth/operator", json={"key": key})
        del key
        require("HttpOnly" in login.headers["set-cookie"], "session_cookie_not_http_only")
        session = self.document("GET", "/api/session")
        require(session["grants"] == [] and session["options"]["resources"] == [], "fresh_synthetic_instance_required")
        require(self.document("GET", "/api/operations")["items"] == [], "fresh_synthetic_instance_required")
        self.headers["X-CSRF-Token"] = session["csrf"]
        self.checks["unauthenticated_access_refused"] = True
        self.stage = "upload"
        upload_headers = {"Content-Type": "application/octet-stream", "X-File-Name": "synthetic-pilot.zip"}
        self.request("POST", "/api/uploads", expected=403, headers=upload_headers, content=fixture)
        self.checks["upload_requires_prior_consent"] = True
        workspace = workspace_id(self.configuration.principals[0])
        self.consent(workspace, "workspace_v1", ["upload", "import"])
        receipt = self.document("POST", "/api/uploads", expected=201, headers=upload_headers, content=fixture)
        require(receipt["sha256"] == digest(fixture) and receipt["size_bytes"] == len(fixture), "upload_bytes_changed")
        self.checks["upload_digest_and_length_verified"] = True
        imported = self.operate("import", workspace, "workspace_v1", {
            "input_handle": receipt["upload_id"], "input_sha256": receipt["sha256"],
            "account_namespace": "synthetic-http-pilot",
        })
        collection, generation = imported["output_id"], imported["result"]["manifest_sha256"]
        self.stage = "collection_queries"
        self.request("POST", "/api/query", expected=403,
                     json={"kind": "browse", "collection_id": collection, "generation": generation})
        collection_grant = self.consent(collection, generation, ["browse", "search", "read", "verify", "recover"])
        browsing = self.query("browse", collection, generation)
        require(browsing["total"] == 4, "synthetic_inventory_changed")
        selected = next(item["conversation_key"] for item in browsing["items"] if item["source_id"] == EVOLVING_ID)
        searching = self.query("search", collection, generation, query="preservation alternatives")
        require(len(searching["items"]) == 1 and searching["items"][0]["conversation_key"] == selected,
                "synthetic_search_changed")
        require(self.query("read", collection, generation, conversation_key=selected)["total_nodes"] == 3,
                "synthetic_graph_changed")
        require(self.query("verify", collection, generation)["verified"] is True, "collection_verification_failed")
        self.checks["scoped_browse_search_read_and_verify"] = True
        recovered = self.operate("recovery", collection, generation, {"conversation_keys": [selected]})
        recovery, recovery_generation = recovered["output_id"], recovered["result"]["manifest_sha256"]
        self.consent(recovery, recovery_generation, ["package"])
        packaged = self.operate("package", recovery, recovery_generation, {})
        package, package_generation = packaged["output_id"], packaged["result"]["manifest_sha256"]
        self.stage = "download"
        download_path = "/api/downloads/" + package + "?generation=" + package_generation
        self.request("GET", download_path, expected=403)
        self.checks["download_requires_separate_consent"] = True
        self.consent(package, package_generation, ["download"])
        downloaded = self.request("GET", download_path)
        require(digest(downloaded.content) == packaged["result"]["artifact_sha256"], "delivery_digest_changed")
        require(len(downloaded.content) == int(downloaded.headers["content-length"]), "delivery_length_changed")
        delivery = self.verify_download(downloaded.content, recovery_generation, selected, binaries)
        self.stage = "revocation"
        revoked = self.document("POST", "/api/grants/revoke", json={
            "grant_id": collection_grant["grant_id"], "grant_version": collection_grant["grant_version"],
        })
        require(revoked["revoked"] is True, "revocation_not_recorded")
        self.request("POST", "/api/query", expected=403,
                     json={"kind": "browse", "collection_id": collection, "generation": generation})
        self.request("GET", download_path, expected=403)
        self.checks["revocation_blocks_source_reads_and_derived_download"] = True
        self.stage = "logout"
        require(self.document("POST", "/auth/logout", json={})["authenticated"] is False, "logout_failed")
        self.request("GET", "/api/session", expected=401)
        self.checks["logout_ends_http_session"] = True
        self.stage = "completed"
        return {"input": {"size_bytes": len(fixture), "sha256": digest(fixture), "conversations": 4},
                "delivery": delivery, "operations": self.operations, "checks": self.checks,
                "http_status_counts": self.http_status_counts,
                "elapsed_seconds": round(time.monotonic() - started, 6)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--launch-service", action="store_true",
                        help="Launch a pristine synthetic service on Linux in this command's network namespace.")
    arguments = parser.parse_args()
    report: JSON = {
        "format": "lpx-keepmorrow.synthetic-http-smoke", "schema_version": 1,
        "observed_at": datetime.now(UTC).isoformat(), "transport": "loopback_http_socket",
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "acceptance": "Synthetic test gestures only; not human or legal acceptance.",
        "live_oauth_verified": False, "chatgpt_connection_verified": False,
        "real_user_content_processed": False,
    }
    runner: PortalSmoke | None = None
    try:
        require(1 <= arguments.timeout_seconds <= 300, "invalid_deadline")
        runner = PortalSmoke(arguments.configuration, arguments.timeout_seconds)
        if arguments.launch_service:
            runner.launch_service()
        report.update(runner.run())
        report["status"] = "passed"
    except Exception as error:
        # Credential-bearing HTTP objects and their exception chains must never
        # be serialized. Keep failures reviewable through fixed stage/code pairs.
        report.update(status="failed", stage=runner.stage if runner else "configuration",
                      error_code=str(error) if isinstance(error, SmokeFailure) else "execution_unavailable")
        if runner:
            report["checks"] = runner.checks
    finally:
        if runner:
            clean_shutdown = runner.close()
            report["service_lifecycle"] = runner.lifecycle
            if not clean_shutdown and report.get("status") == "passed":
                report.update(status="failed", stage="service_shutdown", error_code="service_shutdown_failed")
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
