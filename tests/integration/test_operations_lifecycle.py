"""Exercise real process interruption, exclusive ownership, and access races."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from keepmorrow.access import AccessDenied, AccessStore, PolicySet, Principal
from keepmorrow.archive import verify_archive
from keepmorrow.operations import (
    AuthorizationScope, ImportParameters, OperationBusy, OperationCleanupRequired, OperationError,
    OperationLimits, OperationStore, OperationWorker, StaleAttempt, VerifiedResult,
)
from keepmorrow.persistence import SQLiteDatabase


_INTERRUPTED_PROCESS = """
import hashlib
import os
from pathlib import Path
import sys
from keepmorrow.archive import create_archive
from keepmorrow.operations import OperationStore, VerifiedResult
from keepmorrow.persistence import SQLiteDatabase
root, mode = Path(sys.argv[1]), sys.argv[2]
store = OperationStore(SQLiteDatabase(root / 'control.sqlite3'), clock=lambda: 1800000000)
session = store.acquire_worker()
store.reconcile(session, lambda snapshot: None)
attempt = store.claim(session)
if mode == 'before_authorization':
    os._exit(73)
stage = root / 'staged'
manifest = create_archive(root / 'source', stage)
digest = hashlib.sha256((stage / 'manifest.json').read_bytes()).hexdigest()
attempt.checkpoint(verifying=True)
attempt.authorize_publication(lambda connection, plan: None, manifest_sha256=digest)
if mode == 'authorized':
    os._exit(74)
destination = root / 'outputs' / attempt.output_id
if destination.exists():
    raise RuntimeError('The synthetic destination must not exist.')
os.rename(stage, destination)
if mode == 'published':
    os._exit(75)
attempt.complete(VerifiedResult(digest, len(manifest.files), sum(item.size_bytes for item in manifest.files)))
os._exit(76)
"""


class OperationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "outputs").mkdir()
        (self.root / "source").mkdir()
        (self.root / "source" / "synthetic.bin").write_bytes(bytes(range(256)) * 3)
        self.database = SQLiteDatabase(self.root / "control.sqlite3")
        self.now = 1_800_000_000
        self.store = OperationStore(self.database, clock=lambda: self.now)
        self.scope = AuthorizationScope("collection", "generation", "grant", 1, "acceptance", "import")
        self.counter = 0

    @staticmethod
    def authorize(connection, plan) -> None:
        if not connection.in_transaction:
            raise AssertionError("Authorization must use the journal transaction.")

    def queued(self):
        self.counter += 1
        plan = self.store.prepare(
            "owner", ImportParameters("input", "a" * 64, "synthetic-account"), scope=self.scope,
            reservation_bytes=100, authorize=self.authorize,
        )
        self.store.record_human_review(
            "owner", plan.plan_id, parameter_digest=plan.parameter_digest, interaction_id=f"gesture_{self.counter}",
        )
        return self.store.start("owner", plan.plan_id, idempotency_key=f"request_{self.counter}", authorize=self.authorize)

    def inspect_output(self, snapshot):
        output = self.root / "outputs" / snapshot.output_id
        if not output.exists():
            return None
        report = verify_archive(output)
        if not report.verified:
            raise OperationError("Synthetic verification detected unexpected bytes.")
        digest = hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()
        return VerifiedResult(digest, report.file_count, report.total_bytes)

    def interrupt_process(self, mode, expected_code):
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
        result = subprocess.run(
            [sys.executable, "-c", _INTERRUPTED_PROCESS, str(self.root), mode],
            env=environment, capture_output=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, expected_code, result.stderr.decode("utf-8", errors="replace"))
        return OperationStore(SQLiteDatabase(self.root / "control.sqlite3"), clock=lambda: self.now)

    def wait_state(self, operation_id, states, timeout=5):
        deadline = time.monotonic() + timeout
        wake = threading.Event()
        while time.monotonic() < deadline:
            result = self.store.get("owner", operation_id)
            if result.state in states:
                return result
            wake.wait(0.01)
        self.fail("The synthetic operation did not reach its expected terminal state.")

    def test_restart_before_authorization_cannot_report_success_and_requires_reconciliation(self) -> None:
        operation = self.queued()
        restarted = self.interrupt_process("before_authorization", 73)
        with restarted.acquire_worker() as session:
            with self.assertRaises(OperationBusy):
                restarted.claim(session)
            reconciled = restarted.reconcile(session, self.inspect_output)
            self.assertEqual(reconciled[0].state, "interrupted")
            self.assertIsNone(reconciled[0].result)
            self.assertFalse(reconciled[0].publication_authorized)
            same = restarted.start("owner", operation.plan_id, idempotency_key="request_1", authorize=self.authorize)
            self.assertEqual(same.operation_id, operation.operation_id)
            restarted.retry("owner", operation.operation_id, authorize=self.authorize)
            attempt = restarted.claim(session)
            self.assertEqual(attempt.attempt_number, 2)
            self.assertEqual(attempt.output_id, operation.output_id)
            attempt.fail("execution_failed")
            restarted.release_attempt(attempt)

    def test_authorized_but_absent_output_is_not_success_and_can_be_cancelled_after_reconciliation(self) -> None:
        operation = self.queued()
        restarted = self.interrupt_process("authorized", 74)
        with restarted.acquire_worker() as session:
            result = restarted.reconcile(session, self.inspect_output)[0]
            self.assertEqual(result.state, "interrupted")
            self.assertFalse(result.publication_authorized)
            self.assertIsNone(result.result)
            cancelled = restarted.request_cancel("owner", operation.operation_id)
            self.assertEqual(cancelled.disposition, "cancelled")
            self.assertEqual(cancelled.operation.state, "cancelled")

    def test_restart_reconciles_published_verified_bytes_without_republishing(self) -> None:
        operation = self.queued()
        restarted = self.interrupt_process("published", 75)
        destination = self.root / "outputs" / operation.output_id
        before = (destination / "manifest.json").read_bytes()
        self.assertEqual(restarted.get("owner", operation.operation_id).state, "verifying")
        with restarted.acquire_worker() as session:
            reconciled = restarted.reconcile(session, self.inspect_output)[0]
            self.assertEqual(reconciled.state, "completed")
            self.assertEqual(reconciled.result.total_bytes, 768)
            self.assertIsNone(restarted.claim(session))
            self.assertEqual(restarted.reconcile(session, self.inspect_output), ())
        self.assertEqual((destination / "manifest.json").read_bytes(), before)
        self.assertEqual(restarted.reserved_bytes(), 0)

    def test_restart_after_status_commit_releases_only_the_dead_executor_hold(self) -> None:
        operation = self.queued()
        restarted = self.interrupt_process("completed", 76)
        self.assertEqual(restarted.get("owner", operation.operation_id).state, "completed")
        self.assertEqual(restarted.reserved_bytes(), 100)
        with restarted.acquire_worker() as session:
            self.assertEqual(restarted.reconcile(session, self.inspect_output), ())
        self.assertEqual(restarted.reserved_bytes(), 0)

    def test_corrupt_output_remains_interrupted_and_is_ineligible_for_retry(self) -> None:
        operation = self.queued()
        restarted = self.interrupt_process("published", 75)
        destination = self.root / "outputs" / operation.output_id
        (destination / "payload" / "synthetic.bin").write_bytes(b"corrupt synthetic bytes")
        with restarted.acquire_worker() as session:
            reconciled = restarted.reconcile(session, self.inspect_output)[0]
            self.assertEqual(reconciled.state, "interrupted")
            self.assertEqual(reconciled.error_code, "reconciliation_failed")
            self.assertIsNone(reconciled.result)
            with self.assertRaises(OperationError):
                restarted.retry("owner", operation.operation_id, authorize=self.authorize)
        self.assertEqual(restarted.reserved_bytes(), 100)

    def test_valid_but_different_publication_manifest_is_not_reconciled_as_success(self) -> None:
        operation = self.queued()
        restarted = self.interrupt_process("published", 75)
        with restarted.acquire_worker() as session:
            result = restarted.reconcile(session, lambda snapshot: VerifiedResult("f" * 64, 1, 768))[0]
            self.assertEqual(result.state, "interrupted")
            self.assertEqual(result.error_code, "integrity_failed")
            self.assertIsNone(result.result)

    def test_reconciliation_cleanup_ambiguity_stops_startup_without_losing_reservation(self) -> None:
        operation = self.queued()
        restarted = self.interrupt_process("published", 75)

        def inspect(snapshot):
            raise OperationCleanupRequired("Synthetic temporary ownership mismatch.")

        worker = OperationWorker(restarted, lambda attempt: self.fail("No work may be admitted."), inspect)
        with self.assertRaises(OperationCleanupRequired):
            worker.start()
        result = restarted.get("owner", operation.operation_id)
        self.assertEqual(result.state, "interrupted")
        self.assertEqual(result.error_code, "cleanup_required")
        self.assertEqual(restarted.reserved_bytes(), 100)
        with restarted.acquire_worker():
            pass

    def test_retry_budget_and_old_attempt_fences_survive_reconciliation(self) -> None:
        self.store = OperationStore(self.database, limits=OperationLimits(max_attempts=2), clock=lambda: self.now)
        operation = self.queued()
        with self.store.acquire_worker() as session:
            first = self.store.claim(session)
            first.fail("worker_interrupted")
            self.store.release_attempt(first)
            self.store.reconcile(session, self.inspect_output)
            self.store.retry("owner", operation.operation_id, authorize=self.authorize)
            second = self.store.claim(session)
            self.assertEqual(second.attempt_number, 2)
            with self.assertRaises(StaleAttempt):
                first.authorize_publication(self.authorize, manifest_sha256="b" * 64)
            with self.assertRaises(StaleAttempt):
                first.complete(VerifiedResult("b" * 64, 1, 1))
            second.fail("worker_interrupted")
            self.store.release_attempt(second)
            self.store.reconcile(session, self.inspect_output)
            with self.assertRaises(OperationError):
                self.store.retry("owner", operation.operation_id, authorize=self.authorize)

    def test_process_lock_excludes_another_live_process(self) -> None:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
        program = """
from pathlib import Path
import sys
from keepmorrow.operations import OperationStore, OperationBusy
from keepmorrow.persistence import SQLiteDatabase
store = OperationStore(SQLiteDatabase(Path(sys.argv[1])))
try:
    session = store.acquire_worker()
except OperationBusy:
    sys.exit(0)
session.close()
sys.exit(1)
"""
        with self.store.acquire_worker():
            result = subprocess.run(
                [sys.executable, "-c", program, str(self.database.path)], env=environment,
                capture_output=True, timeout=10, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))

    def test_shutdown_timeout_and_cancellation_do_not_release_live_executor_resources(self) -> None:
        operation = self.queued()
        entered, release = threading.Event(), threading.Event()

        def execute(attempt):
            entered.set()
            if not release.wait(5):
                raise AssertionError("The synthetic executor was not released.")
            attempt.checkpoint()

        worker = OperationWorker(self.store, execute, self.inspect_output)
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertFalse(worker.shutdown(timeout_seconds=0, cancel_active=True))
            self.assertEqual(self.store.get("owner", operation.operation_id).state, "cancel_requested")
            self.assertEqual(self.store.reserved_bytes(), 100)
            with self.assertRaises(OperationBusy):
                self.store.acquire_worker()
        finally:
            release.set()
            self.assertTrue(worker.shutdown(timeout_seconds=5))
        self.assertEqual(self.store.get("owner", operation.operation_id).state, "cancelled")
        self.assertEqual(self.store.reserved_bytes(), 0)
        with self.store.acquire_worker():
            pass

    def test_completed_status_does_not_release_callback_resources_early(self) -> None:
        operation = self.queued()
        completed, release = threading.Event(), threading.Event()

        def execute(attempt):
            attempt.checkpoint(verifying=True)
            attempt.authorize_publication(self.authorize, manifest_sha256="b" * 64)
            attempt.complete(VerifiedResult("b" * 64, 1, 10))
            completed.set()
            if not release.wait(5):
                raise AssertionError("The synthetic post-publication cleanup was not released.")

        worker = OperationWorker(self.store, execute, self.inspect_output)
        worker.start()
        try:
            self.assertTrue(completed.wait(5))
            self.assertEqual(self.store.get("owner", operation.operation_id).state, "completed")
            self.assertEqual(self.store.reserved_bytes(), 100)
            self.assertFalse(worker.shutdown(timeout_seconds=0))
            with self.assertRaises(OperationBusy):
                self.store.acquire_worker()
        finally:
            release.set()
            self.assertTrue(worker.shutdown(timeout_seconds=5))
        self.assertEqual(self.store.reserved_bytes(), 0)

    def test_exclusive_startup_runs_before_execution_and_failure_text_is_not_recorded(self) -> None:
        operation = self.queued()
        started = threading.Event()

        def startup():
            with self.assertRaises(OperationBusy):
                self.store.acquire_worker()
            started.set()

        def execute(attempt):
            self.assertTrue(started.is_set())
            raise OSError("/private/user/path contains a synthetic secret")

        worker = OperationWorker(self.store, execute, self.inspect_output, startup=startup)
        worker.start()
        try:
            result = self.wait_state(operation.operation_id, {"failed"})
            self.assertEqual(result.error_code, "execution_failed")
            self.assertNotIn("private", str(result.as_dict()))
            self.assertNotIn("secret", str(result.as_dict()))
        finally:
            self.assertTrue(worker.shutdown(timeout_seconds=5))

    def test_concurrent_idempotent_starts_consume_only_one_review(self) -> None:
        plan = self.store.prepare(
            "owner", ImportParameters("input", "a" * 64, "synthetic-account"), scope=self.scope,
            reservation_bytes=100, authorize=self.authorize,
        )
        self.store.record_human_review(
            "owner", plan.plan_id, parameter_digest=plan.parameter_digest, interaction_id="gesture",
        )
        barrier = threading.Barrier(3)

        def start():
            barrier.wait(timeout=5)
            return self.store.start("owner", plan.plan_id, idempotency_key="concurrent_request", authorize=self.authorize)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(start) for _ in range(2)]
            barrier.wait(timeout=5)
            results = [future.result(timeout=5) for future in futures]
        self.assertEqual(len({item.operation_id for item in results}), 1)
        self.assertEqual(len(self.store.list("owner")), 1)

    def test_review_expiry_is_checked_after_waiting_for_database_writer(self) -> None:
        plan = self.store.prepare(
            "owner", ImportParameters("input", "a" * 64, "synthetic-account"), scope=self.scope,
            reservation_bytes=100, authorize=self.authorize,
        )
        review = self.store.record_human_review(
            "owner", plan.plan_id, parameter_digest=plan.parameter_digest, interaction_id="expiring",
        )
        entered = threading.Event()

        def start():
            entered.set()
            return self.store.start("owner", plan.plan_id, idempotency_key="expiring", authorize=self.authorize)

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.database.transaction():
                future = executor.submit(start)
                self.assertTrue(entered.wait(5))
                self.now = review.expires_at
            with self.assertRaises(OperationError):
                future.result(timeout=5)
        self.assertEqual(self.store.list("owner"), ())


class PublicationAccessRaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.database = SQLiteDatabase(self.root / "control.sqlite3")
        self.now = 1_800_000_000
        self.owner = Principal("https://identity.example.test", "synthetic-owner")
        self.policies = PolicySet("test-terms.1", "a" * 64, "test-privacy.1", "b" * 64)
        self.access = AccessStore(self.database, self.policies, clock=lambda: self.now)
        self.store = OperationStore(self.database, clock=lambda: self.now)
        self.grant = self.access.create_grant(
            self.owner, resource_id="collection", generation="generation", actions=("import", "download"),
            purpose="selected_preservation", recipient="chatgpt", expires_at=self.now + 3600,
        )
        self.acceptance = self.access.accept_grant(
            self.owner, grant_id=self.grant.grant_id, expected_grant_version=1, policies=self.policies,
            actions=("import", "download"), interaction_id="human_acceptance",
        )
        scope = AuthorizationScope(
            "collection", "generation", self.grant.grant_id, 1, self.acceptance.acceptance_id, "import",
        )
        plan = self.store.prepare(
            self.owner.principal_id, ImportParameters("input", "a" * 64, "synthetic-account"),
            scope=scope, reservation_bytes=100, authorize=self.authorize,
        )
        self.store.record_human_review(
            self.owner.principal_id, plan.plan_id, parameter_digest=plan.parameter_digest, interaction_id="human_review",
        )
        self.operation = self.store.start(
            self.owner.principal_id, plan.plan_id, idempotency_key="request", authorize=self.authorize,
        )

    def authorize(self, connection, plan):
        scope = plan.scope
        self.access.authorize_publication(
            self.owner, resource_id=scope.resource_id, generation=scope.generation, action=scope.action,
            grant_id=scope.grant_id, expected_grant_version=scope.grant_version,
            expected_acceptance_id=scope.acceptance_id, connection=connection,
        )

    def test_revocation_committed_first_prevents_the_journal_publication_decision(self) -> None:
        ready, proceed = threading.Event(), threading.Event()

        def execute(attempt):
            attempt.checkpoint(verifying=True)
            ready.set()
            if not proceed.wait(5):
                raise AssertionError("The synthetic revocation was not released.")
            attempt.authorize_publication(self.authorize, manifest_sha256="c" * 64)
            self.fail("Publication was authorized after revocation committed.")

        worker = OperationWorker(
            self.store, execute, lambda snapshot: None,
            classify_failure=lambda error: "authorization_denied" if isinstance(error, AccessDenied) else "execution_failed",
        )
        worker.start()
        try:
            self.assertTrue(ready.wait(5))
            self.access.revoke_grant(self.owner, grant_id=self.grant.grant_id)
            proceed.set()
            self.assertTrue(worker.shutdown(timeout_seconds=5))
        finally:
            proceed.set()
            worker.shutdown(timeout_seconds=5)
        result = self.store.get(self.owner.principal_id, self.operation.operation_id)
        self.assertFalse(result.publication_authorized)
        self.assertEqual(result.state, "failed")
        self.assertEqual(result.error_code, "authorization_denied")

    def test_publication_decision_committed_first_allows_private_finish_but_not_delivery(self) -> None:
        authorizing, release_transaction = threading.Event(), threading.Event()
        revoke_started, revoked = threading.Event(), threading.Event()
        private_output = self.root / "private-output"

        def authorize(connection, plan):
            self.authorize(connection, plan)
            authorizing.set()
            if not release_transaction.wait(5):
                raise AssertionError("The synthetic authorization transaction was not released.")

        def execute(attempt):
            attempt.checkpoint(verifying=True)
            attempt.authorize_publication(authorize, manifest_sha256="c" * 64)
            if not revoked.wait(5):
                raise AssertionError("The synthetic revocation did not finish.")
            # The committed decision precedes this private synthetic publication;
            # a later revoke still prevents any new authenticated delivery.
            private_output.write_bytes(b"synthetic verified output")
            attempt.complete(VerifiedResult("c" * 64, 1, 25))

        def revoke():
            revoke_started.set()
            self.access.revoke_grant(self.owner, grant_id=self.grant.grant_id)
            revoked.set()

        worker = OperationWorker(self.store, execute, lambda snapshot: None)
        worker.start()
        try:
            self.assertTrue(authorizing.wait(5))
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(revoke)
                self.assertTrue(revoke_started.wait(5))
                self.assertFalse(revoked.wait(0.05))
                release_transaction.set()
                future.result(timeout=5)
            self.assertTrue(worker.shutdown(timeout_seconds=5))
        finally:
            release_transaction.set()
            revoked.set()
            worker.shutdown(timeout_seconds=5)
        result = self.store.get(self.owner.principal_id, self.operation.operation_id)
        self.assertTrue(result.publication_authorized)
        self.assertEqual(result.state, "completed")
        self.assertTrue(private_output.exists())
        with self.assertRaises(AccessDenied):
            self.access.require_access(self.owner, resource_id="collection", generation="generation", action="download")


if __name__ == "__main__":
    unittest.main()
