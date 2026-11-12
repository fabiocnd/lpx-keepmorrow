"""Challenge review binding, principal isolation, admission, and attempt lifecycle."""

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import tempfile
import unittest

from keepmorrow.operations import (
    AssociationParameters, AuthorizationScope, IdempotencyConflict, ImportParameters,
    OperationBusy, OperationCancelled, OperationError, OperationLimits, OperationStore,
    PackageParameters, RecoveryParameters, StaleAttempt, UnpackParameters, VerifiedResult,
)
from keepmorrow.persistence import PersistenceError, SQLiteDatabase


class OperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "control.sqlite3"
        self.database = SQLiteDatabase(self.path)
        self.now = 1_800_000_000
        self.store = OperationStore(self.database, clock=lambda: self.now)
        self.scope = AuthorizationScope("collection", "generation", "grant", 1, "acceptance", "import")
        self.counter = 0

    @staticmethod
    def authorize(connection, plan) -> None:
        if not connection.in_transaction:
            raise AssertionError("Authorization must share the journal transaction.")

    def plan(self, *, parameters=None, principal="owner", scope=None, reservation=100):
        self.counter += 1
        return self.store.prepare(
            principal, parameters or ImportParameters("input", "a" * 64, "synthetic-account"),
            scope=scope or self.scope, reservation_bytes=reservation, authorize=self.authorize,
        )

    def review(self, plan, *, interaction=None):
        self.counter += 1
        return self.store.record_human_review(
            plan.principal_id, plan.plan_id, parameter_digest=plan.parameter_digest,
            interaction_id=interaction or f"human_{self.counter}",
        )

    def queued(self, plan=None, *, key=None):
        plan = plan or self.plan()
        self.review(plan)
        self.counter += 1
        return self.store.start(
            plan.principal_id, plan.plan_id, idempotency_key=key or f"request_{self.counter}",
            authorize=self.authorize,
        )

    def session(self):
        """Own and clean up attempts driven synchronously by this store fixture.

        The test thread stands in for a returned executor. Production code must
        retain ownership until its actual worker callback and cleanup unwind.
        """
        session = self.store.acquire_worker()
        self.store.reconcile(session, lambda snapshot: None)

        def close() -> None:
            if session._closed:
                return
            attempt = session._active
            if attempt is not None:
                state = self.store.get(attempt.plan.principal_id, attempt.operation_id).state
                if state in {"running", "verifying", "cancel_requested"}:
                    attempt.fail("execution_failed")
                self.store.release_attempt(attempt)
            session.close()

        self.addCleanup(close)
        return session

    def test_plan_is_immutable_and_semantically_equal_selection_has_one_digest(self) -> None:
        scope = replace(self.scope, action="recover")
        first = self.plan(parameters=RecoveryParameters(("b" * 64, "a" * 64)), scope=scope)
        second = self.plan(parameters=RecoveryParameters(("a" * 64, "b" * 64)), scope=scope)
        self.assertNotEqual(first.plan_id, second.plan_id)
        self.assertEqual(first.parameter_digest, second.parameter_digest)
        self.assertEqual(first.parameters.conversation_keys, ("a" * 64, "b" * 64))
        with self.assertRaises(FrozenInstanceError):
            first.parameters.project_id = "changed"
        with self.assertRaises(OperationError):
            self.store.record_human_review(
                "owner", first.plan_id, parameter_digest="f" * 64, interaction_id="stale_review",
            )

    def test_digest_binds_identity_generation_grant_acceptance_reservation_and_bytes(self) -> None:
        first = self.plan()
        alternatives = (
            self.plan(principal="another_owner"),
            self.plan(scope=replace(self.scope, generation="next_generation")),
            self.plan(scope=replace(self.scope, grant_version=2)),
            self.plan(scope=replace(self.scope, acceptance_id="other_acceptance")),
            self.plan(reservation=101),
            self.plan(parameters=ImportParameters("input", "b" * 64, "synthetic-account")),
        )
        for plan in alternatives:
            self.assertNotEqual(first.parameter_digest, plan.parameter_digest)

    def test_exact_operation_action_is_required(self) -> None:
        with self.assertRaises(OperationError):
            self.plan(scope=replace(self.scope, action="read"))
        for parameters, action in (
            (RecoveryParameters(("a" * 64,)), "recover"),
            (AssociationParameters("a" * 64, "association_unknown", None, "Evidence unavailable."), "associate"),
            (PackageParameters(), "package"),
            (UnpackParameters("input", "a" * 64), "unpack"),
        ):
            with self.subTest(action=action):
                plan = self.plan(parameters=parameters, scope=replace(self.scope, action=action))
                self.assertEqual(self.store.get_plan("owner", plan.plan_id), plan)

    def test_start_requires_recorded_human_review_and_not_a_model_boolean(self) -> None:
        plan = self.plan()
        with self.assertRaises(OperationError):
            self.store.start("owner", plan.plan_id, idempotency_key="request", authorize=self.authorize)
        with self.assertRaises(TypeError):
            self.store.start("owner", plan.plan_id, idempotency_key="request", authorize=self.authorize, accepted=True)
        self.assertEqual(self.store.list("owner"), ())
        self.review(plan)
        operation = self.store.start("owner", plan.plan_id, idempotency_key="request", authorize=self.authorize)
        self.assertEqual(operation.state, "queued")

    def test_same_key_same_parameters_is_idempotent_and_different_parameters_conflict(self) -> None:
        plan = self.plan()
        first = self.queued(plan, key="stable_request")
        duplicate = self.store.start("owner", plan.plan_id, idempotency_key="stable_request", authorize=self.authorize)
        self.assertEqual(first.operation_id, duplicate.operation_id)
        equivalent = self.plan()
        repeated = self.store.start("owner", equivalent.plan_id, idempotency_key="stable_request", authorize=self.authorize)
        self.assertEqual(first.operation_id, repeated.operation_id)
        changed = self.plan(parameters=ImportParameters("input", "b" * 64, "synthetic-account"))
        self.review(changed)
        with self.assertRaises(IdempotencyConflict):
            self.store.start("owner", changed.plan_id, idempotency_key="stable_request", authorize=self.authorize)
        self.assertEqual(len(self.store.list("owner")), 1)

    def test_new_deliberate_capture_preserves_event_identity_and_consumes_fresh_review(self) -> None:
        plan = self.plan()
        review = self.review(plan, interaction="one_gesture")
        first = self.store.start("owner", plan.plan_id, idempotency_key="first", authorize=self.authorize)
        self.assertEqual(self.review(plan, interaction="one_gesture"), review)
        with self.assertRaises(OperationError):
            self.store.start("owner", plan.plan_id, idempotency_key="second", authorize=self.authorize)
        self.review(plan, interaction="another_gesture")
        second = self.store.start("owner", plan.plan_id, idempotency_key="second", authorize=self.authorize)
        self.assertNotEqual(first.operation_id, second.operation_id)
        self.assertNotEqual(first.output_id, second.output_id)
        self.assertEqual(first.parameter_digest, second.parameter_digest)

    def test_human_interaction_cannot_be_rebound_to_another_plan(self) -> None:
        first, second = self.plan(), self.plan()
        self.review(first, interaction="gesture")
        with self.assertRaises(OperationError):
            self.review(second, interaction="gesture")

    def test_principal_scope_applies_to_plan_review_job_cancel_retry_and_cursor(self) -> None:
        plan = self.plan()
        operation = self.queued(plan)
        calls = (
            lambda: self.store.get_plan("foreign", plan.plan_id),
            lambda: self.store.record_human_review("foreign", plan.plan_id, parameter_digest=plan.parameter_digest, interaction_id="foreign_gesture"),
            lambda: self.store.start("foreign", plan.plan_id, idempotency_key="foreign_request", authorize=self.authorize),
            lambda: self.store.get("foreign", operation.operation_id),
            lambda: self.store.request_cancel("foreign", operation.operation_id),
            lambda: self.store.retry("foreign", operation.operation_id, authorize=self.authorize),
            lambda: self.store.list("foreign", before_operation_id=operation.operation_id),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaises(OperationError):
                call()
        self.assertEqual(self.store.list("foreign"), ())
        foreign = self.queued(self.plan(principal="foreign"), key="shared_key")
        owner = self.queued(key="shared_key")
        self.assertNotEqual(foreign.operation_id, owner.operation_id)

    def test_review_and_queued_plan_expire_at_their_exact_boundary(self) -> None:
        plan = self.plan()
        review = self.review(plan)
        self.now = review.expires_at
        with self.assertRaises(OperationError):
            self.store.start("owner", plan.plan_id, idempotency_key="expired", authorize=self.authorize)
        self.now = plan.created_at
        operation = self.queued(plan)
        session = self.session()
        self.now = review.expires_at
        self.assertIsNone(self.store.claim(session))
        self.assertEqual(self.store.get("owner", operation.operation_id).state, "expired")
        self.now = plan.expires_at
        with self.assertRaises(OperationError):
            self.review(plan)

    def test_failed_authorization_rolls_back_review_consumption_and_admission(self) -> None:
        plan = self.plan()
        self.review(plan)

        def denied(connection, current_plan):
            raise PermissionError("synthetic-secret-not-for-the-journal")

        with self.assertRaises(PermissionError):
            self.store.start("owner", plan.plan_id, idempotency_key="retry", authorize=denied)
        self.assertEqual(self.store.list("owner"), ())
        operation = self.store.start("owner", plan.plan_id, idempotency_key="retry", authorize=self.authorize)
        self.assertEqual(operation.state, "queued")

    def test_queue_count_and_reservations_are_bounded_without_consuming_rejected_review(self) -> None:
        self.store = OperationStore(self.database, limits=OperationLimits(
            max_pending_operations=2, max_pending_per_principal=2,
            max_reserved_bytes=150, max_operation_reserved_bytes=150,
        ), clock=lambda: self.now)
        first = self.queued()
        plan = self.plan()
        self.review(plan)
        with self.assertRaises(OperationBusy):
            self.store.start("owner", plan.plan_id, idempotency_key="later", authorize=self.authorize)
        self.assertEqual(self.store.reserved_bytes(), 100)
        self.store.request_cancel("owner", first.operation_id)
        self.store.start("owner", plan.plan_id, idempotency_key="later", authorize=self.authorize)
        self.assertEqual(self.store.reserved_bytes(), 100)

    def test_single_worker_admission_and_terminal_reservation_last_until_executor_returns(self) -> None:
        operation = self.queued()
        session = self.session()
        attempt = self.store.claim(session)
        with self.assertRaises(OperationBusy):
            self.store.acquire_worker()
        with self.assertRaises(OperationBusy):
            self.store.claim(session)
        with self.assertRaises(OperationBusy):
            session.close()
        attempt.fail("execution_failed")
        self.assertEqual(self.store.get("owner", operation.operation_id).state, "failed")
        self.assertEqual(self.store.reserved_bytes(), 100)
        with self.assertRaises(OperationBusy):
            session.close()
        self.store.release_attempt(attempt)
        self.assertEqual(self.store.reserved_bytes(), 0)
        session.close()

    def test_custom_admission_shares_transaction_and_does_not_repeat_on_idempotent_replay(self) -> None:
        first = self.queued()
        plan = self.plan()
        self.review(plan)
        observed = []

        def admit(connection, current_plan):
            self.database.validate_connection(connection, immediate=True)
            observed.append(self.store.reserved_bytes(connection))
            if observed[-1] + current_plan.reservation_bytes > 150:
                raise OperationBusy("Synthetic retained storage budget is full.")

        with self.assertRaises(OperationBusy):
            self.store.start("owner", plan.plan_id, idempotency_key="budget", authorize=self.authorize, admit=admit)
        self.store.request_cancel("owner", first.operation_id)
        operation = self.store.start("owner", plan.plan_id, idempotency_key="budget", authorize=self.authorize, admit=admit)
        repeated = self.store.start("owner", plan.plan_id, idempotency_key="budget", authorize=self.authorize, admit=admit)
        self.assertEqual(operation.operation_id, repeated.operation_id)
        self.assertEqual(observed, [100, 0])

    def test_cancel_active_preserves_ownership_until_acknowledged_and_released(self) -> None:
        operation = self.queued()
        session = self.session()
        attempt = self.store.claim(session)
        receipt = self.store.request_cancel("owner", operation.operation_id)
        self.assertEqual(receipt.disposition, "requested")
        self.assertEqual(receipt.operation.state, "cancel_requested")
        with self.assertRaises(OperationCancelled):
            attempt.checkpoint()
        with self.assertRaises(OperationCancelled):
            attempt.authorize_publication(self.authorize, manifest_sha256="b" * 64)
        with self.assertRaises(OperationBusy):
            self.store.release_attempt(attempt)
        attempt.fail("cancelled")
        self.assertEqual(self.store.reserved_bytes(), 100)
        self.store.release_attempt(attempt)
        self.assertEqual(self.store.reserved_bytes(), 0)
        self.assertEqual(self.store.get("owner", operation.operation_id).state, "cancelled")

    def test_authorization_requires_verification_and_binds_immutable_output_digest(self) -> None:
        self.queued()
        session = self.session()
        attempt = self.store.claim(session)
        with self.assertRaises(OperationError):
            attempt.authorize_publication(self.authorize, manifest_sha256="b" * 64)
        attempt.checkpoint(verifying=True)
        permit = attempt.authorize_publication(self.authorize, manifest_sha256="b" * 64)
        self.assertEqual(permit.output_id, attempt.output_id)
        self.assertEqual(permit, attempt.authorize_publication(self.authorize, manifest_sha256="b" * 64))
        with self.assertRaises(OperationError):
            attempt.authorize_publication(self.authorize, manifest_sha256="c" * 64)
        with self.assertRaises(OperationError):
            attempt.complete(VerifiedResult("c" * 64, 1, 10))
        completed = attempt.complete(VerifiedResult("b" * 64, 1, 10))
        self.assertEqual(completed.state, "completed")
        with self.assertRaises(StaleAttempt):
            attempt.checkpoint()
        self.store.release_attempt(attempt)
        with self.assertRaises(StaleAttempt):
            attempt.authorize_publication(self.authorize, manifest_sha256="b" * 64)

    def test_cancel_after_commit_is_explicit_and_does_not_relabel_verified_output(self) -> None:
        operation = self.queued()
        session = self.session()
        attempt = self.store.claim(session)
        attempt.checkpoint(verifying=True)
        attempt.authorize_publication(self.authorize, manifest_sha256="b" * 64)
        receipt = self.store.request_cancel("owner", operation.operation_id)
        self.assertEqual(receipt.disposition, "publication_committed")
        attempt.checkpoint()
        completed = attempt.complete(VerifiedResult("b" * 64, 1, 10, ("association_unknown",)))
        self.assertEqual(completed.state, "partial")
        self.assertTrue(completed.cancel_requested)
        self.assertIsNotNone(completed.result)
        self.store.release_attempt(attempt)
        self.assertEqual(self.store.request_cancel("owner", operation.operation_id).disposition, "already_terminal")

    def test_completion_without_publication_and_crash_as_partial_success_are_rejected(self) -> None:
        self.queued()
        session = self.session()
        attempt = self.store.claim(session)
        with self.assertRaises(OperationError):
            attempt.complete(VerifiedResult("b" * 64, 1, 10, ("incomplete_source",)))
        attempt.checkpoint(verifying=True)
        attempt.authorize_publication(self.authorize, manifest_sha256="b" * 64)
        failed = attempt.fail("execution_failed")
        self.assertEqual(failed.state, "interrupted")
        self.assertIsNone(failed.result)
        self.store.release_attempt(attempt)

    def test_status_contains_only_allowlisted_metadata_not_parameter_text_or_key(self) -> None:
        reason = "Private user explanation supplied for this exact association."
        plan = self.plan(
            parameters=AssociationParameters("a" * 64, "association_unknown", None, reason),
            scope=replace(self.scope, action="associate"),
        )
        operation = self.queued(plan, key="private_idempotency_value")
        document = json.dumps(operation.as_dict())
        for private_value in (reason, "private_idempotency_value", self.scope.acceptance_id, str(self.path)):
            self.assertNotIn(private_value, document)
        with self.database.transaction(immediate=False) as connection:
            columns = connection.execute("SELECT idempotency_digest FROM km_operations").fetchone()
        self.assertNotEqual(columns[0], "private_idempotency_value")
        with self.assertRaises(OperationError):
            VerifiedResult("a" * 64, 1, 1, ("/private/path",))

    def test_list_pages_do_not_skip_equal_timestamps_or_escape_principal(self) -> None:
        operations = [self.queued() for _ in range(3)]
        self.queued(self.plan(principal="foreign"))
        first = self.store.list("owner", limit=2)
        second = self.store.list("owner", limit=2, before_operation_id=first[-1].operation_id)
        self.assertEqual({item.operation_id for item in first + second}, {item.operation_id for item in operations})
        self.assertEqual(len(first + second), 3)
        for limit in (True, 0, 101, 1.0):
            with self.subTest(limit=limit), self.assertRaises(OperationError):
                self.store.list("owner", limit=limit)

    def test_metadata_limits_and_invalid_values_fail_before_admission(self) -> None:
        cases = (
            lambda: ImportParameters("/private/path", "a" * 64, "namespace"),
            lambda: ImportParameters("input", "wrong", "namespace"),
            lambda: ImportParameters("input", "a" * 64, "\ud800"),
            lambda: RecoveryParameters(("a" * 64,) * 2),
            lambda: RecoveryParameters(["a" * 64]),
            lambda: RecoveryParameters((), project_id="x" * 257),
            lambda: AssociationParameters("a" * 64, "association_unknown", None, "r" * 1025),
            lambda: VerifiedResult("a" * 64, True, 1),
            lambda: VerifiedResult("a" * 64, 1, -1),
            lambda: VerifiedResult("a" * 64, 1, 1, ([],)),
            lambda: OperationLimits(max_attempts=True),
            lambda: OperationLimits(max_plan_bytes=65537),
            lambda: self.plan(reservation=True),
        )
        for call in cases:
            with self.subTest(call=call), self.assertRaises(OperationError):
                call()
        self.store = OperationStore(self.database, limits=OperationLimits(max_plan_bytes=100), clock=lambda: self.now)
        with self.assertRaises(OperationError):
            self.plan()

    def test_plan_tampering_and_future_schema_versions_fail_closed(self) -> None:
        plan = self.plan()
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE km_operation_plans SET canonical_json = REPLACE(canonical_json, 'synthetic-account', 'changed-account') WHERE plan_id = ?",
                (plan.plan_id,),
            )
        with self.assertRaises(OperationError):
            self.store.get_plan("owner", plan.plan_id)
        with self.database.transaction() as connection:
            connection.execute("UPDATE km_schema_versions SET version = 2 WHERE component = 'operations'")
        with self.assertRaises(PersistenceError):
            OperationStore(self.database)


if __name__ == "__main__":
    unittest.main()
