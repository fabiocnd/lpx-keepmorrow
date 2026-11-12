"""Prove temporary-byte containment and ledger-plus-marker cleanup boundaries."""

import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from keepmorrow.application.staging import OperationWorkspaces
from keepmorrow.archive import create_archive, verify_archive
from keepmorrow.catalog.service import import_exports
from keepmorrow.control import execution_scope, temporary_parent
from keepmorrow.importers.zip_intake import prepared_export
from keepmorrow.operations import (
    AuthorizationScope, ImportParameters, OperationBusy, OperationError, OperationStore,
    OperationWorker, VerifiedResult,
)
from keepmorrow.persistence import SQLiteDatabase
from keepmorrow.transfers import pack_collection, unpack_collection
from tests.fixtures.chatgpt_exports import write_export_pair


class OperationWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.scratch, self.outputs = self.root / "scratch", self.root / "outputs"
        self.scratch.mkdir(mode=0o700)
        self.outputs.mkdir(mode=0o700)
        self.database = SQLiteDatabase(self.root / "control.sqlite3")
        self.operations = OperationStore(self.database)
        self.workspaces = OperationWorkspaces(self.database, self.scratch, self.outputs)
        plan = self.operations.prepare(
            "owner", ImportParameters("input", "a" * 64, "synthetic-account"),
            scope=AuthorizationScope("collection", "generation", "grant", 1, "acceptance", "import"),
            reservation_bytes=1024, authorize=lambda connection, plan: None,
        )
        self.operations.record_human_review(
            "owner", plan.plan_id, parameter_digest=plan.parameter_digest, interaction_id="gesture",
        )
        self.operation = self.operations.start(
            "owner", plan.plan_id, idempotency_key="request", authorize=lambda connection, plan: None,
        )

    def test_core_zip_and_transfer_stages_remain_inside_the_owned_workspace(self) -> None:
        first, _ = write_export_pair(self.root)
        collection = self.root / "source-collection"
        import_exports([first], collection, account_namespace="synthetic-source")
        source = self.root / "plain-source"
        source.mkdir()
        (source / "synthetic.bin").write_bytes(bytes(range(256)))
        archive = self.outputs / "plain-archive"
        package, unpacked = self.outputs / "package.zip", self.outputs / "unpacked"
        observed_stages = []
        with self.workspaces.workspace(self.operation.operation_id, self.operation.output_id) as owned:
            def before_publish(stage, destination):
                self.assertTrue(stage.is_relative_to(owned))
                observed_stages.append(stage)

            with execution_scope(checkpoint=lambda: None, before_publish=before_publish, temporary_root=owned):
                create_archive(source, archive)
                packed = pack_collection(collection, package)
                with prepared_export(package) as selected:
                    self.assertTrue(selected.directory.is_relative_to(owned))
                restored = unpack_collection(package, unpacked)
                with execution_scope(checkpoint=lambda: None):
                    self.assertEqual(temporary_parent(), owned)
        self.assertGreaterEqual(len(observed_stages), 3)
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertEqual(packed.manifest_sha256, restored.manifest_sha256)
        self.assertTrue(verify_archive(archive).verified)
        self.assertTrue(verify_archive(unpacked).verified)
        self.assertIsNone(temporary_parent())

    def test_handled_cancellation_removes_only_its_workspace(self) -> None:
        unrelated = self.scratch / "unrelated-source"
        unrelated.mkdir(mode=0o700)
        source = unrelated / "original.bin"
        source.write_bytes(b"original synthetic source")
        with self.assertRaises(KeyboardInterrupt):
            with self.workspaces.workspace(self.operation.operation_id, self.operation.output_id) as owned:
                (owned / "partial.bin").write_bytes(b"incomplete synthetic output")
                raise KeyboardInterrupt()
        self.assertEqual(source.read_bytes(), b"original synthetic source")
        self.assertFalse((self.scratch / self.operation.output_id).exists())

    def test_restart_cleanup_uses_exact_record_and_marker_and_ignores_unknown_directories(self) -> None:
        owned = self.workspaces.create(self.operation.operation_id, self.operation.output_id)
        (owned / "partial.bin").write_bytes(b"partial synthetic bytes")
        unknown = self.scratch / "unknown-directory"
        unknown.mkdir(mode=0o700)
        (unknown / "original.bin").write_bytes(b"preserve this source")
        with self.operations.acquire_worker():
            self.assertEqual(self.workspaces.recover_interrupted(), 1)
            self.assertEqual(self.workspaces.recover_interrupted(), 0)
        self.assertFalse(owned.exists())
        self.assertEqual((unknown / "original.bin").read_bytes(), b"preserve this source")

    def test_mismatched_or_missing_ownership_marker_blocks_cleanup(self) -> None:
        owned = self.workspaces.create(self.operation.operation_id, self.operation.output_id)
        marker = owned / ".keepmorrow-owner.json"
        marker.write_bytes(b"not the recorded marker")
        with self.operations.acquire_worker():
            with self.assertRaises(OperationError):
                self.workspaces.recover_interrupted()
        self.assertTrue(owned.exists())
        marker.unlink()
        with self.operations.acquire_worker():
            with self.assertRaises((OperationError, ValueError)):
                self.workspaces.recover_interrupted()
        self.assertTrue(owned.exists())

    def test_absent_directory_reconciles_record_without_deleting_another_path(self) -> None:
        owned = self.workspaces.create(self.operation.operation_id, self.operation.output_id)
        shutil.rmtree(owned)
        with self.operations.acquire_worker():
            self.assertEqual(self.workspaces.recover_interrupted(), 1)
        with self.workspaces.workspace(self.operation.operation_id, self.operation.output_id) as recreated:
            self.assertEqual(recreated, owned)

    def test_cleanup_requires_startup_ownership_and_cannot_interrupt_a_live_attempt(self) -> None:
        self.workspaces.create(self.operation.operation_id, self.operation.output_id)
        with self.assertRaises(OperationError):
            self.workspaces.recover_interrupted()
        with self.operations.acquire_worker() as session:
            attempt = self.operations.claim(session)
            try:
                with self.assertRaises(OperationBusy):
                    self.workspaces.recover_interrupted()
            finally:
                attempt.fail("execution_failed")
                self.operations.release_attempt(attempt)
            self.assertEqual(self.workspaces.recover_interrupted(), 1)

    def test_workspace_cannot_select_an_unrecorded_output_or_replace_existing_content(self) -> None:
        with self.assertRaises(OperationError):
            self.workspaces.create(self.operation.operation_id, "different_output")
        occupied = self.scratch / self.operation.output_id
        occupied.mkdir(mode=0o700)
        (occupied / "original.bin").write_bytes(b"do not adopt this directory")
        with self.assertRaises(OperationError):
            self.workspaces.create(self.operation.operation_id, self.operation.output_id)
        with self.operations.acquire_worker():
            self.assertEqual(self.workspaces.recover_interrupted(), 0)
        self.assertTrue((occupied / "original.bin").exists())

    def test_different_output_filesystem_is_rejected_before_staging(self) -> None:
        original_stat = Path.stat

        def different_device(path, *args, **kwargs):
            information = original_stat(path, *args, **kwargs)
            if path == self.outputs:
                values = list(information)
                values[2] = information.st_dev + 1
                return os.stat_result(values)
            return information

        with patch.object(Path, "stat", different_device):
            with self.assertRaises(OperationError):
                OperationWorkspaces(self.database, self.scratch, self.outputs)

    def test_cleanup_failure_after_completion_retains_capacity_and_stops_the_worker(self) -> None:
        completed = threading.Event()
        original_marker = []

        def execute(attempt):
            with self.workspaces.workspace(attempt.operation_id, attempt.output_id) as owned:
                marker = owned / ".keepmorrow-owner.json"
                original_marker.append(marker.read_bytes())
                (owned / "unremoved.bin").write_bytes(b"private temporary bytes")
                marker.write_bytes(b"synthetic ownership mismatch")
                attempt.checkpoint(verifying=True)
                attempt.authorize_publication(lambda connection, plan: None, manifest_sha256="b" * 64)
                attempt.complete(VerifiedResult("b" * 64, 1, 1))
                completed.set()

        worker = OperationWorker(
            self.operations, execute, lambda snapshot: None, startup=self.workspaces.recover_interrupted,
        )
        worker.start()
        try:
            self.assertTrue(completed.wait(5))
        finally:
            self.assertTrue(worker.shutdown(timeout_seconds=5))
        self.assertEqual(worker.last_error_code, "workspace_cleanup_required")
        self.assertEqual(self.operations.get("owner", self.operation.operation_id).state, "completed")
        self.assertEqual(self.operations.reserved_bytes(), 1024)
        owned = self.scratch / self.operation.output_id
        self.assertTrue((owned / "unremoved.bin").exists())
        with self.operations.acquire_worker() as session:
            with self.assertRaises(OperationError):
                self.workspaces.recover_interrupted()
            self.assertEqual(self.operations.reserved_bytes(), 1024)
            # Synthetic operator repair restores known evidence; production code
            # must never manufacture a marker to make an unknown path deletable.
            (owned / ".keepmorrow-owner.json").write_bytes(original_marker[0])
            self.workspaces.recover_interrupted()
            self.operations.reconcile(session, lambda snapshot: None)
        self.assertEqual(self.operations.reserved_bytes(), 0)


if __name__ == "__main__":
    unittest.main()
