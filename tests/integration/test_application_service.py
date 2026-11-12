"""Exercise intake, reviewed execution, recovery, and delivery through the service.

The fixture calls application APIs directly and records synthetic acceptance.
HTTP interaction and trusted browser gestures have separate integration tests.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid
import zipfile

from keepmorrow.access import AccessDenied, Principal
from keepmorrow.application.configuration import Resource, ServiceConfiguration
from keepmorrow.application.service import PreservationService, manifest_digest, workspace_id
from keepmorrow.catalog.service import import_exports, load_collection
from keepmorrow.operations import ImportParameters, OperationError, PackageParameters, RecoveryParameters, UnpackParameters
from tests.fixtures.chatgpt_exports import EVOLVING_ID, write_export_pair


class ApplicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.owner = Principal("urn:lpx-keepmorrow:local-operator", "synthetic-owner")
        first, self.second = write_export_pair(self.root)
        self.source = self.root / "source-collection"
        import_exports([first], self.source, account_namespace="synthetic-source")
        self.generation = manifest_digest(self.source)
        (self.root / "state").mkdir()
        configuration = ServiceConfiguration(
            self.root / "state", Path("legal").resolve(), "http://127.0.0.1:8765", (self.owner,),
            resources=(Resource("collection_a", self.generation, self.owner.principal_id, self.source),),
        )
        self.service = PreservationService(configuration)
        self.service.start_worker()
        self.addCleanup(self.service.stop_worker)

    def accept(self, resource_id: str, generation: str, actions: list[str]):
        """Persist a fixture receipt without claiming an actual human gesture."""
        grant = self.service.prepare_consent(self.owner, resource_id=resource_id, generation=generation, actions=actions)
        self.service.access.accept_grant(
            self.owner, grant_id=grant.grant_id, expected_grant_version=grant.grant_version,
            policies=self.service.policies, actions=actions, interaction_id="test_" + uuid.uuid4().hex,
        )
        return grant

    def finish(self, plan):
        """Await successful publication and resource release in this serial fixture."""
        self.service.operations.record_human_review(
            self.owner.principal_id, plan.plan_id, parameter_digest=plan.parameter_digest,
            interaction_id="review_" + uuid.uuid4().hex,
        )
        started = self.service.start(self.owner, plan.plan_id, uuid.uuid4().hex)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = self.service.status(self.owner, started["operation_id"])
            if result["state"] in {"completed", "partial", "failed", "cancelled", "interrupted"}:
                self.assertIn(result["state"], {"completed", "partial"}, result)
                # Completion precedes workspace cleanup. This isolated fixture
                # owns one operation, so a zero reservation establishes that
                # its executor has returned before the next content request.
                if self.service.operations.reserved_bytes() == 0:
                    return result
            time.sleep(0.01)
        self.fail("The bounded synthetic worker did not finish and release its reservation.")

    def test_no_content_io_before_acceptance_and_exact_generation_fencing(self) -> None:
        with patch("keepmorrow.application.service.load_collection", side_effect=AssertionError("Unexpected content read")):
            self.assertEqual(self.service.list_collections(self.owner)["items"], [])
            self.assertEqual(len(self.service.consent_options(self.owner)["resources"]), 1)
            with self.assertRaises(AccessDenied):
                self.service.query(self.owner, "collection_a", self.generation, "read", lambda item: {})
        self.accept("collection_a", self.generation, ["read", "browse"])
        self.assertEqual(len(self.service.list_collections(self.owner)["items"]), 1)
        with self.assertRaises(AccessDenied):
            self.service.query(self.owner, "collection_a", "0" * 64, "read", lambda item: {})
        other = Principal(self.owner.issuer, "another-person")
        self.assertEqual(self.service.list_collections(other)["items"], [])
        with self.assertRaises(AccessDenied):
            self.service.query(other, "collection_a", self.generation, "read", lambda item: {})

    def test_generation_replacement_is_detected_after_consent(self) -> None:
        self.accept("collection_a", self.generation, ["read"])
        manifest = self.source / "manifest.json"
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        from keepmorrow.archive.model import ArchiveError
        with self.assertRaises(ArchiveError):
            self.service.query(self.owner, "collection_a", self.generation, "read", lambda item: {})

    def test_upload_import_requires_separate_review_and_preserves_original_zip(self) -> None:
        self.accept(workspace_id(self.owner), "workspace_v1", ["upload", "import"])
        binary = io.BytesIO()
        with zipfile.ZipFile(binary, "w", zipfile.ZIP_DEFLATED) as output:
            for path in self.second.rglob("*"):
                if path.is_file():
                    output.writestr(path.relative_to(self.second).as_posix(), path.read_bytes())
        data = binary.getvalue()
        receipt = self.service.receive_upload(self.owner, io.BytesIO(data), display_name="chosen-export.zip", expected_size_bytes=len(data))
        plan = self.service.prepare(self.owner, resource_id=workspace_id(self.owner), generation="workspace_v1",
                                    parameters=ImportParameters(receipt["upload_id"], receipt["sha256"], "synthetic-source"))
        with self.assertRaises(OperationError):
            self.service.start(self.owner, plan.plan_id, "unreviewed")
        completed = self.finish(plan)
        output = self.root / "state/outputs" / completed["output_id"]
        self.assertEqual((output / "payload/captures/000001/original.zip").read_bytes(), data)
        self.assertEqual(load_collection(output).document["account_namespace"], "synthetic-source")
        # The new generation has no inherited read grant; its exact bytes must
        # appear in a new human scope decision before disclosure.
        with self.assertRaises(AccessDenied):
            self.service.query(self.owner, completed["output_id"], completed["result"]["manifest_sha256"], "read", lambda item: {})

    def test_recovery_pack_download_unpack_preserves_selection_and_gaps(self) -> None:
        grant = self.accept("collection_a", self.generation, ["recover", "package"])
        conversation = next(item for item in load_collection(self.source).document["conversations"] if item["source_id"] == EVOLVING_ID)
        plan = self.service.prepare(self.owner, resource_id="collection_a", generation=self.generation,
                                    parameters=RecoveryParameters((conversation["conversation_key"],)))
        recovered = self.finish(plan)
        selected_id, selected_generation = recovered["output_id"], recovered["result"]["manifest_sha256"]
        self.assertIn("selection_omissions", recovered["result"]["coverage_gaps"])
        self.accept(selected_id, selected_generation, ["package"])
        package_plan = self.service.prepare(self.owner, resource_id=selected_id, generation=selected_generation,
                                            parameters=PackageParameters())
        packaged = self.finish(package_plan)
        package_id, package_generation = packaged["output_id"], packaged["result"]["manifest_sha256"]
        self.assertIn("selection_omissions", packaged["result"]["coverage_gaps"])
        with self.assertRaises(AccessDenied):
            with self.service.download(self.owner, package_id, package_generation):
                self.fail("Download without its own acceptance must be unavailable.")
        self.accept(package_id, package_generation, ["download"])
        with self.service.download(self.owner, package_id, package_generation) as (stream, size):
            data = stream.read()
        self.assertEqual(len(data), size)
        self.assertEqual(hashlib.sha256(data).hexdigest(), packaged["result"]["artifact_sha256"])
        self.accept(workspace_id(self.owner), "workspace_v1", ["upload", "unpack"])
        upload = self.service.receive_upload(self.owner, io.BytesIO(data), display_name="recovery.zip", expected_size_bytes=len(data))
        unpack_plan = self.service.prepare(self.owner, resource_id=workspace_id(self.owner), generation="workspace_v1",
                                           parameters=UnpackParameters(upload["upload_id"], upload["sha256"]))
        unpacked = self.finish(unpack_plan)
        self.assertEqual(unpacked["result"]["manifest_sha256"], selected_generation)
        self.assertEqual(manifest_digest(self.source), self.generation)
        # An origin grant revoked after publication prevents further disclosure.
        self.service.access.revoke_grant(self.owner, grant_id=grant.grant_id)
        self.assertIsNone(self.service.status(self.owner, recovered["operation_id"])["result"])

    def test_revocation_during_query_prevents_result_delivery(self) -> None:
        grant = self.accept("collection_a", self.generation, ["read"])

        def revoke(collection):
            self.service.access.revoke_grant(self.owner, grant_id=grant.grant_id)
            return {"private_text": "must not escape"}

        with self.assertRaises(AccessDenied):
            self.service.query(self.owner, "collection_a", self.generation, "read", revoke)

    def test_completed_lineage_requires_explicit_parent_renewal_without_rewriting_history(self) -> None:
        original_grant = self.accept("collection_a", self.generation, ["recover"])
        conversation = load_collection(self.source).document["conversations"][0]
        plan = self.service.prepare(
            self.owner, resource_id="collection_a", generation=self.generation,
            parameters=RecoveryParameters((conversation["conversation_key"],)),
        )
        completed = self.finish(plan)
        output_id, generation = completed["output_id"], completed["result"]["manifest_sha256"]
        historical_plan = self.service.operations.get_plan(self.owner.principal_id, plan.plan_id).as_dict()
        with patch("time.time", return_value=original_grant.expires_at + 1):
            self.accept(output_id, generation, ["read"])
            with self.assertRaises(AccessDenied):
                self.service.query(self.owner, output_id, generation, "read", lambda collection: {"available": True})
            self.assertIsNone(self.service.status(self.owner, completed["operation_id"])["result"])
            renewed = self.accept("collection_a", self.generation, ["recover"])
            self.assertNotEqual(renewed.grant_id, original_grant.grant_id)
            self.assertEqual(self.service.query(
                self.owner, output_id, generation, "read", lambda collection: {"available": True},
            ), {"available": True})
            self.assertIsNotNone(self.service.status(self.owner, completed["operation_id"])["result"])
            self.assertEqual(self.service.operations.get_plan(self.owner.principal_id, plan.plan_id).as_dict(), historical_plan)
            self.assertEqual(self.service.access.get_grant(self.owner, grant_id=original_grant.grant_id), original_grant)
        self.assertEqual(manifest_digest(self.source), self.generation)
        self.assertEqual(manifest_digest(self.root / "state/outputs" / output_id), generation)

    def test_fresh_consent_cannot_rebind_an_existing_uncompleted_plan(self) -> None:
        original = self.accept("collection_a", self.generation, ["package"])
        plan = self.service.prepare(self.owner, resource_id="collection_a", generation=self.generation, parameters=PackageParameters())
        self.service.access.revoke_grant(self.owner, grant_id=original.grant_id)
        self.accept("collection_a", self.generation, ["package"])
        with self.service.database.transaction() as connection:
            with self.assertRaises(AccessDenied):
                self.service._authorize(connection, plan)


if __name__ == "__main__":
    unittest.main()
