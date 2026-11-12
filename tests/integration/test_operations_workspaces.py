"""Prove temporary-byte containment and ledger-plus-marker cleanup boundaries."""

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from keepmorrow.application.staging import OperationWorkspaces
from keepmorrow.archive import create_archive, verify_archive
from keepmorrow.catalog.service import import_exports
from keepmorrow.control import execution_scope, temporary_parent
from keepmorrow.importers.zip_intake import prepared_export
from keepmorrow.operations import (
    AuthorizationScope, ImportParameters, OperationBusy, OperationCleanupRequired, OperationError,
    OperationSnapshot, OperationStore, OperationWorker, VerifiedResult,
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
        self.workspaces = OperationWorkspaces(
            SQLiteDatabase(self.database.path), self.scratch, self.outputs,
        )
        self.operation = self._queued("request")

    def _queued(self, request_key: str) -> OperationSnapshot:
        plan = self.operations.prepare(
            "owner", ImportParameters("input", "a" * 64, "synthetic-account"),
            scope=AuthorizationScope("collection", "generation", "grant", 1, "acceptance", "import"),
            reservation_bytes=1024, authorize=lambda connection, plan: None,
        )
        self.operations.record_human_review(
            "owner", plan.plan_id, parameter_digest=plan.parameter_digest, interaction_id=f"gesture_{request_key}",
        )
        return self.operations.start(
            "owner", plan.plan_id, idempotency_key=request_key, authorize=lambda connection, plan: None,
        )

    def _cleanup_ownership(self) -> tuple[dict[str, str] | None, int]:
        with self.database.transaction(immediate=False) as connection:
            row = connection.execute(
                "SELECT * FROM km_operation_workspaces WHERE operation_id = ?", (self.operation.operation_id,),
            ).fetchone()
            released = connection.execute(
                "SELECT worker_released FROM km_operations WHERE operation_id = ?", (self.operation.operation_id,),
            ).fetchone()[0]
        return (dict(row) if row is not None else None), released

    @contextmanager
    def _fail_cleanup_metadata(
        self, boundary: str, error: Exception, *, persistent: bool = False,
    ) -> Iterator[list[None]]:
        """Fail cleanup while leaving operation-status transactions available."""
        transaction = self.workspaces.database.transaction
        failures: list[None] = []

        @contextmanager
        def faulty_transaction(*, immediate: bool = True):
            fail_finalize = False
            with transaction(immediate=immediate) as connection:
                fail_commit = False
                proxy = Mock(wraps=connection)

                def execute(statement, parameters=()):
                    nonlocal fail_commit, fail_finalize
                    if persistent or not failures:
                        if boundary == "read" and statement.startswith("SELECT w.* FROM km_operation_workspaces"):
                            failures.append(None)
                            raise error
                        if statement.startswith("DELETE FROM km_operation_workspaces"):
                            fail_commit = boundary == "commit"
                            fail_finalize = boundary == "finalize"
                    return connection.execute(statement, parameters)

                proxy.execute.side_effect = execute
                yield proxy
                if fail_commit:
                    # The real DELETE runs, but the surrounding transaction must
                    # roll it back when commit cannot be established.
                    failures.append(None)
                    raise error
            if fail_finalize:
                # Model a raw finalization error after the transaction commits;
                # no uncommitted ledger mutation remains to roll back.
                failures.append(None)
                raise error

        with patch.object(self.workspaces.database, "transaction", faulty_transaction):
            yield failures

    def _assert_cleanup_metadata_failure(self, boundary: str, *, complete: bool) -> None:
        ready, allow_cleanup = threading.Event(), threading.Event()
        executed: list[str] = []
        marker_bytes: list[bytes] = []
        result = VerifiedResult("b" * 64, 1, 1)
        unknown = self.scratch / "unrelated-source"
        unknown.mkdir(mode=0o700)
        (unknown / "original.bin").write_bytes(b"preserve unrelated synthetic bytes")

        def execute(attempt):
            executed.append(attempt.operation_id)
            if attempt.operation_id != self.operation.operation_id:
                attempt.fail("execution_failed")
                return
            with self.workspaces.workspace(attempt.operation_id, attempt.output_id) as owned:
                marker_bytes.append((owned / ".keepmorrow-owner.json").read_bytes())
                (owned / "partial.bin").write_bytes(b"owned temporary bytes")
                if complete:
                    attempt.checkpoint(verifying=True)
                    attempt.authorize_publication(lambda connection, plan: None, manifest_sha256=result.manifest_sha256)
                    attempt.complete(result)
                ready.set()
                if not allow_cleanup.wait(5):
                    raise AssertionError("The synthetic executor was not released for cleanup.")

        worker = OperationWorker(
            self.operations, execute, lambda snapshot: None, startup=self.workspaces.recover_interrupted,
        )
        with self._fail_cleanup_metadata(boundary, sqlite3.OperationalError("Synthetic cleanup metadata failure.")) as failures:
            worker.start()
            try:
                self.assertTrue(ready.wait(5))
                original_record, released = self._cleanup_ownership()
                self.assertIsNotNone(original_record)
                self.assertEqual(released, 0)
                following = self._queued("following_request")
                allow_cleanup.set()
                # Joining without requesting shutdown proves the cleanup failure
                # itself stops claims rather than relying on test teardown.
                thread = worker._thread
                self.assertIsNotNone(thread)
                thread.join(5)
                stopped = not thread.is_alive()
            finally:
                allow_cleanup.set()
                self.assertTrue(worker.shutdown(timeout_seconds=5))
        self.assertEqual(len(failures), 1)
        current = self.operations.get("owner", self.operation.operation_id)
        record, released = self._cleanup_ownership()
        self.assertEqual({
            "worker_stopped": stopped,
            "worker_error": worker.last_error_code,
            "state": current.state,
            "error": current.error_code,
            "worker_released": released,
            "reserved_bytes": self.operations.reserved_bytes(),
            "following_state": self.operations.get("owner", following.operation_id).state,
            "executed": executed,
        }, {
            "worker_stopped": True,
            "worker_error": "workspace_cleanup_required",
            "state": "completed" if complete else "interrupted",
            "error": None if complete else "cleanup_required",
            "worker_released": 0,
            "reserved_bytes": 2048,
            "following_state": "queued",
            "executed": [self.operation.operation_id],
        })
        self.assertEqual(current.result, result if complete else None)
        self.assertEqual(record, None if boundary == "finalize" else original_record)
        owned = self.scratch / self.operation.output_id
        if boundary == "read":
            self.assertEqual((owned / ".keepmorrow-owner.json").read_bytes(), marker_bytes[0])
            self.assertEqual((owned / "partial.bin").read_bytes(), b"owned temporary bytes")
        else:
            self.assertFalse(owned.exists())

        if boundary != "finalize":
            with self._fail_cleanup_metadata(
                boundary, sqlite3.OperationalError("Persistent synthetic cleanup metadata failure."), persistent=True,
            ) as failures:
                for _ in range(2):
                    restarted = OperationWorker(
                        self.operations, execute, lambda snapshot: None, startup=self.workspaces.recover_interrupted,
                    )
                    with self.assertRaises(OperationCleanupRequired):
                        restarted.start()
                    self.assertEqual(self._cleanup_ownership(), (original_record, 0))
                    self.assertEqual(self.operations.reserved_bytes(), 2048)
                    self.assertEqual(executed, [self.operation.operation_id])
                self.assertEqual(len(failures), 2)

        with self.operations.acquire_worker() as session:
            self.assertEqual(self.workspaces.recover_interrupted(), 0 if boundary == "finalize" else 1)
            self.assertEqual(self._cleanup_ownership(), (None, 0))
            self.assertFalse(owned.exists())
            self.operations.reconcile(session, lambda snapshot: None)
            self.assertEqual(self._cleanup_ownership(), (None, 1))
            if not complete:
                self.operations.request_cancel("owner", self.operation.operation_id)
            self.assertEqual(self.operations.reserved_bytes(), 1024)
            next_attempt = self.operations.claim(session)
            self.assertEqual(next_attempt.operation_id, following.operation_id)
            next_attempt.fail("execution_failed")
            self.operations.release_attempt(next_attempt)
        self.assertEqual(self.operations.reserved_bytes(), 0)
        self.assertEqual((unknown / "original.bin").read_bytes(), b"preserve unrelated synthetic bytes")

    def test_cleanup_ledger_read_failure_after_completion_retains_ownership_until_recovery(self) -> None:
        self._assert_cleanup_metadata_failure("read", complete=True)

    def test_cleanup_ledger_commit_failure_after_completion_retains_ownership_until_recovery(self) -> None:
        self._assert_cleanup_metadata_failure("commit", complete=True)

    def test_cleanup_ledger_read_failure_during_execution_retains_ownership_until_recovery(self) -> None:
        self._assert_cleanup_metadata_failure("read", complete=False)

    def test_cleanup_ledger_commit_failure_during_execution_retains_ownership_until_recovery(self) -> None:
        self._assert_cleanup_metadata_failure("commit", complete=False)

    def test_raw_cleanup_finalization_failure_after_commit_retains_hold_until_recovery(self) -> None:
        self._assert_cleanup_metadata_failure("finalize", complete=True)

    def test_raw_sqlite_cleanup_finalization_error_preserves_its_cause(self) -> None:
        owned = self.workspaces.create(self.operation.operation_id, self.operation.output_id)
        error = sqlite3.OperationalError("Synthetic raw transaction finalization failure.")
        with self._fail_cleanup_metadata("finalize", error):
            with self.assertRaises(OperationCleanupRequired) as observed:
                self.workspaces.discard(self.operation.operation_id, self.operation.output_id)
        self.assertIs(observed.exception.__cause__, error)
        self.assertFalse(owned.exists())
        self.assertIsNone(self._cleanup_ownership()[0])

    def test_unexpected_cleanup_programming_error_is_not_reclassified(self) -> None:
        self.workspaces.create(self.operation.operation_id, self.operation.output_id)
        for boundary in ("read", "commit"):
            with self.subTest(boundary=boundary):
                error = RuntimeError("Synthetic unexpected programming failure.")
                with self._fail_cleanup_metadata(boundary, error):
                    with self.assertRaises(RuntimeError) as observed:
                        self.workspaces.discard(self.operation.operation_id, self.operation.output_id)
                self.assertIs(observed.exception, error)

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
