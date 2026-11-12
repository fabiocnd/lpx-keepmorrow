"""Challenge application publication recovery, ancestor revocation, and retention."""

from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from keepmorrow.access import AccessDenied, Principal
from keepmorrow.application.configuration import Resource, ServiceConfiguration
from keepmorrow.application.service import PreservationService, manifest_digest
from keepmorrow.catalog.service import import_exports, load_collection
from keepmorrow.operations import PackageParameters, RecoveryParameters
from tests.fixtures.chatgpt_exports import EVOLVING_ID, write_export_pair


class ApplicationOperationLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.owner = Principal("urn:lpx-keepmorrow:local-operator", "synthetic-owner")
        first, _ = write_export_pair(self.root)
        self.source = self.root / "source-collection"
        import_exports([first], self.source, account_namespace="synthetic-source")
        self.generation = manifest_digest(self.source)
        (self.root / "state").mkdir()
        self.configuration = ServiceConfiguration(
            self.root / "state", Path("legal").resolve(), "http://127.0.0.1:8765", (self.owner,),
            resources=(Resource("collection_a", self.generation, self.owner.principal_id, self.source),),
        )
        self.service = PreservationService(self.configuration)
        self.service.start_worker()
        self.addCleanup(self.service.stop_worker)

    def accept(self, resource_id, generation, actions):
        grant = self.service.prepare_consent(self.owner, resource_id=resource_id, generation=generation, actions=actions)
        self.service.access.accept_grant(
            self.owner, grant_id=grant.grant_id, expected_grant_version=grant.grant_version,
            policies=self.service.policies, actions=actions, interaction_id="gesture_" + uuid.uuid4().hex,
        )
        return grant

    def execute(self, resource_id, generation, parameters, *, expected=("completed", "partial")):
        plan = self.service.prepare(self.owner, resource_id=resource_id, generation=generation, parameters=parameters)
        self.service.operations.record_human_review(
            self.owner.principal_id, plan.plan_id, parameter_digest=plan.parameter_digest,
            interaction_id="review_" + uuid.uuid4().hex,
        )
        started = self.service.start(self.owner, plan.plan_id, uuid.uuid4().hex)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = self.service.operations.get(self.owner.principal_id, started["operation_id"])
            if result.state in {"completed", "partial", "failed", "interrupted", "cancelled"}:
                self.assertIn(result.state, expected, result.as_dict())
                return result
            time.sleep(0.01)
        self.fail("The synthetic operation did not finish within its test deadline.")

    def restart(self):
        self.assertTrue(self.service.stop_worker())
        self.service = PreservationService(self.configuration)
        self.service.start_worker()
        self.addCleanup(self.service.stop_worker)

    def test_original_grant_revocation_blocks_derived_package_delivery_and_status(self) -> None:
        origin = self.accept("collection_a", self.generation, ["recover"])
        conversation = next(
            item for item in load_collection(self.source).document["conversations"] if item["source_id"] == EVOLVING_ID
        )
        recovered = self.execute("collection_a", self.generation, RecoveryParameters((conversation["conversation_key"],)))
        self.accept(recovered.output_id, recovered.result.manifest_sha256, ["package"])
        package = self.execute(recovered.output_id, recovered.result.manifest_sha256, PackageParameters())
        self.accept(package.output_id, package.result.manifest_sha256, ["download"])
        self.service.access.revoke_grant(self.owner, grant_id=origin.grant_id)
        with self.assertRaises(AccessDenied):
            with self.service.download(self.owner, package.output_id, package.result.manifest_sha256):
                self.fail("A revoked ancestor grant must block derived delivery.")
        status = self.service.status(self.owner, package.operation_id)
        self.assertIsNone(status["result"])
        self.assertIsNone(status["output_id"])

    def test_registered_output_before_completion_is_reconciled_and_discovered_after_restart(self) -> None:
        self.accept("collection_a", self.generation, ["package"])
        original_register = self.service._register

        def interrupted_register(snapshot, result):
            original_register(snapshot, result)
            raise OSError("Synthetic process-boundary interruption after registration.")

        with patch.object(self.service, "_register", interrupted_register):
            operation = self.execute("collection_a", self.generation, PackageParameters(), expected=("interrupted",))
        self.assertTrue(operation.publication_authorized)
        self.assertIsNone(operation.result)
        self.restart()
        completed = self.service.operations.get(self.owner.principal_id, operation.operation_id)
        self.assertIn(completed.state, {"completed", "partial"})
        registered = self.service.resources.resolve(self.owner, completed.output_id, completed.result.manifest_sha256)
        self.assertEqual(registered.kind, "package")
        self.assertEqual(manifest_digest(self.source), self.generation)

    def test_expired_registered_output_is_reconciled_before_retention_removes_its_evidence(self) -> None:
        self.assertTrue(self.service.stop_worker())
        self.configuration = replace(self.configuration, retention_seconds=60)
        self.service = PreservationService(self.configuration)
        self.service.start_worker()
        self.addCleanup(self.service.stop_worker)
        self.accept("collection_a", self.generation, ["package"])
        original_register = self.service._register

        def interrupted_register(snapshot, result):
            original_register(snapshot, result)
            raise OSError("Synthetic process-boundary interruption after registration.")

        with patch.object(self.service, "_register", interrupted_register):
            operation = self.execute("collection_a", self.generation, PackageParameters(), expected=("interrupted",))
        output = self.root / "state" / "outputs" / operation.output_id
        self.assertTrue(output.exists())
        after_expiry = int(operation.created_at) + 61
        with patch("keepmorrow.application.resources.time.time", return_value=after_expiry):
            self.restart()
            completed = self.service.operations.get(self.owner.principal_id, operation.operation_id)
            self.assertIn(completed.state, {"completed", "partial"})
            self.service.maintenance()
            self.assertFalse(output.exists())
            with self.assertRaises(AccessDenied):
                self.service.resources.resolve(self.owner, completed.output_id, completed.result.manifest_sha256)
        self.assertEqual(manifest_digest(self.source), self.generation)


if __name__ == "__main__":
    unittest.main()
