"""Transactional operation plans, admission, fencing, and restart reconciliation.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
import uuid
from collections.abc import Callable
from typing import Any, TYPE_CHECKING

from ..persistence import SQLiteDatabase
from .model import (
    ACTIVE_STATES, FAILURE_CODES, TERMINAL_STATES,
    AuthorizationScope, CancellationReceipt, HumanReview, IdempotencyConflict,
    OperationBusy, OperationCancelled, OperationCleanupRequired, OperationError, OperationLimits,
    OperationParameters, OperationPlan, OperationSnapshot, PublicationPermit,
    StaleAttempt, VerifiedResult, canonical_document, parameter_digest,
    parse_parameters, require_digest, require_opaque_id,
)

if TYPE_CHECKING:
    from .worker import OperationAttempt, WorkerSession

Authorizer = Callable[[sqlite3.Connection, OperationPlan], None]
OutputInspector = Callable[[OperationSnapshot], VerifiedResult | None]

_SCHEMA = (
    """CREATE TABLE km_operation_plans (
        plan_id TEXT PRIMARY KEY NOT NULL,
        principal_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        canonical_json TEXT NOT NULL,
        parameter_digest TEXT NOT NULL,
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL
    )""",
    "CREATE INDEX km_operation_plan_owner ON km_operation_plans(principal_id, expires_at)",
    """CREATE TABLE km_operation_reviews (
        review_id TEXT PRIMARY KEY NOT NULL,
        plan_id TEXT NOT NULL REFERENCES km_operation_plans(plan_id),
        principal_id TEXT NOT NULL,
        parameter_digest TEXT NOT NULL,
        interaction_id TEXT NOT NULL,
        reviewed_at REAL NOT NULL,
        expires_at REAL NOT NULL,
        consumed_by TEXT,
        UNIQUE(principal_id, interaction_id)
    )""",
    "CREATE INDEX km_operation_review_plan ON km_operation_reviews(plan_id, expires_at)",
    """CREATE TABLE km_operations (
        operation_id TEXT PRIMARY KEY NOT NULL,
        principal_id TEXT NOT NULL,
        plan_id TEXT NOT NULL REFERENCES km_operation_plans(plan_id),
        review_id TEXT NOT NULL REFERENCES km_operation_reviews(review_id),
        kind TEXT NOT NULL,
        parameter_digest TEXT NOT NULL,
        idempotency_digest TEXT NOT NULL,
        output_id TEXT NOT NULL UNIQUE,
        reservation_bytes INTEGER NOT NULL CHECK(reservation_bytes >= 0),
        state TEXT NOT NULL CHECK(state IN (
            'queued', 'running', 'verifying', 'completed', 'partial',
            'cancel_requested', 'cancelled', 'interrupted', 'failed', 'expired')),
        attempt_number INTEGER NOT NULL DEFAULT 0 CHECK(attempt_number >= 0),
        cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0, 1)),
        worker_released INTEGER NOT NULL DEFAULT 1 CHECK(worker_released IN (0, 1)),
        reconciled INTEGER NOT NULL DEFAULT 1 CHECK(reconciled IN (0, 1)),
        error_code TEXT,
        result_json TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        UNIQUE(principal_id, idempotency_digest)
    )""",
    "CREATE INDEX km_operation_owner ON km_operations(principal_id, created_at, operation_id)",
    "CREATE INDEX km_operation_queue ON km_operations(state, created_at, operation_id)",
    "CREATE INDEX km_operation_reserved ON km_operations(principal_id, reservation_bytes) "
    "WHERE (state IN ('queued', 'running', 'verifying', 'cancel_requested', 'interrupted') OR worker_released = 0)",
    """CREATE TABLE km_operation_attempts (
        operation_id TEXT NOT NULL REFERENCES km_operations(operation_id),
        attempt_number INTEGER NOT NULL,
        attempt_token TEXT NOT NULL UNIQUE,
        worker_token TEXT NOT NULL,
        worker_epoch INTEGER NOT NULL,
        started_at REAL NOT NULL,
        ended_at REAL,
        publication_authorized_at REAL,
        manifest_sha256 TEXT,
        publication_resolution TEXT,
        PRIMARY KEY(operation_id, attempt_number)
    )""",
    """CREATE TABLE km_operation_worker (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        epoch INTEGER NOT NULL,
        worker_token TEXT
    )""",
    "INSERT INTO km_operation_worker(singleton, epoch, worker_token) VALUES(1, 0, NULL)",
)

_SELECT_OPERATION = """SELECT o.*, a.attempt_token, a.worker_token, a.worker_epoch,
    a.publication_authorized_at, a.manifest_sha256, a.ended_at, a.publication_resolution
    FROM km_operations AS o LEFT JOIN km_operation_attempts AS a
    ON a.operation_id = o.operation_id AND a.attempt_number = o.attempt_number"""
_PENDING_SQL = "('queued', 'running', 'verifying', 'cancel_requested', 'interrupted')"
_RESERVED_SQL = "(state IN " + _PENDING_SQL + " OR worker_released = 0)"


class OperationStore:
    """Persist reviewed intent and bounded operation state in one metadata DB.

    The authorizer is a trusted service callback, not a model argument. It must
    validate current consent and the exact scoped grant using the supplied
    SQLite connection. No callback may commit or retain that connection.
    """

    def __init__(
        self, database: SQLiteDatabase, *, limits: OperationLimits | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(database, SQLiteDatabase) or not callable(clock):
            raise OperationError("The operation store configuration is invalid.")
        self.database = database
        self.limits = limits or OperationLimits()
        if not isinstance(self.limits, OperationLimits):
            raise OperationError("The operation limits are invalid.")
        self._clock = clock
        database.initialize_schema("operations", 1, _SCHEMA)

    def _now(self) -> float:
        value = self._clock()
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise OperationError("The operation clock returned an invalid timestamp.")
        return float(value)

    def prepare(
        self, principal_id: str, parameters: OperationParameters, *,
        scope: AuthorizationScope, reservation_bytes: int, authorize: Authorizer,
    ) -> OperationPlan:
        """Record immutable intent after prior intake authorization has been met.

        This method does not read or stage input bytes. Any earlier intake is a
        separate, already authorized service action. The reservation is a
        trusted executor estimate, not a promise about available disk capacity.
        """
        document = canonical_document(principal_id, parameters, scope, reservation_bytes)
        if not 0 < reservation_bytes <= self.limits.max_operation_reserved_bytes:
            raise OperationError("The declared operation reservation is outside its limit.")
        if len(document) > self.limits.max_plan_bytes:
            raise OperationError("The operation plan exceeds its metadata byte limit.")
        if not callable(authorize):
            raise OperationError("A trusted authorization callback is required.")
        values = json.loads(document)
        with self.database.transaction() as connection:
            now = self._now()
            plan = OperationPlan(
                plan_id="plan_" + uuid.uuid4().hex, principal_id=principal_id,
                kind=values["kind"], parameters=parse_parameters(values["kind"], values["parameters"]),
                scope=scope, reservation_bytes=reservation_bytes, parameter_digest=parameter_digest(document),
                created_at=now, expires_at=now + self.limits.plan_ttl_seconds,
            )
            authorize(connection, plan)
            count = connection.execute(
                "SELECT COUNT(*) FROM km_operation_plans WHERE principal_id = ? AND expires_at > ?",
                (principal_id, now),
            ).fetchone()[0]
            if count >= self.limits.max_prepared_per_principal:
                raise OperationBusy("The principal has reached the prepared-plan limit.")
            connection.execute(
                "INSERT INTO km_operation_plans VALUES(?, ?, ?, ?, ?, ?, ?)",
                (plan.plan_id, principal_id, plan.kind, document.decode("ascii"),
                 plan.parameter_digest, now, plan.expires_at),
            )
        return plan

    def get_plan(
        self, principal_id: str, plan_id: str, *, connection: sqlite3.Connection | None = None,
    ) -> OperationPlan:
        require_opaque_id(principal_id)
        require_opaque_id(plan_id)
        if connection is None:
            with self.database.transaction(immediate=False) as current:
                return self.get_plan(principal_id, plan_id, connection=current)
        self.database.validate_connection(connection)
        return self._plan(connection, principal_id, plan_id)

    def record_human_review(
        self, principal_id: str, plan_id: str, *, parameter_digest: str, interaction_id: str,
    ) -> HumanReview:
        """Record one authenticated human gesture outside model-callable tools.

        Only a trusted interaction handler may call this method after showing
        the exact plan and checking its anti-forgery/session boundary. Python
        typing cannot authenticate a human. A model-supplied boolean, tool call,
        or text assertion is never a substitute for that boundary.
        """
        require_opaque_id(principal_id)
        require_opaque_id(plan_id)
        require_opaque_id(interaction_id)
        require_digest(parameter_digest)
        with self.database.transaction() as connection:
            now = self._now()
            plan = self._plan(connection, principal_id, plan_id)
            if plan.parameter_digest != parameter_digest or plan.expires_at <= now:
                raise OperationError("The reviewed plan changed or expired.")
            previous = connection.execute(
                "SELECT * FROM km_operation_reviews WHERE principal_id = ? AND interaction_id = ?",
                (principal_id, interaction_id),
            ).fetchone()
            if previous is not None:
                if previous["plan_id"] != plan_id or previous["parameter_digest"] != parameter_digest:
                    raise OperationError("The human interaction already identifies another review.")
                return self._review(previous)
            review = HumanReview(
                "review_" + uuid.uuid4().hex, plan_id, principal_id, parameter_digest,
                interaction_id, now, min(plan.expires_at, now + self.limits.review_ttl_seconds),
            )
            connection.execute(
                "INSERT INTO km_operation_reviews VALUES(?, ?, ?, ?, ?, ?, ?, NULL)",
                (review.review_id, plan_id, principal_id, parameter_digest, interaction_id,
                 now, review.expires_at),
            )
            return review

    def start(
        self, principal_id: str, plan_id: str, *, idempotency_key: str, authorize: Authorizer,
        admit: Authorizer | None = None,
    ) -> OperationSnapshot:
        """Enqueue once per principal/key, consuming one exact human review.

        Key replay returns the same job even after that job terminates. A new
        key is a new deliberate operation and therefore needs an unused human
        review; equal source bytes do not deduplicate capture events.
        """
        require_opaque_id(principal_id)
        require_opaque_id(plan_id)
        require_opaque_id(idempotency_key)
        if not callable(authorize):
            raise OperationError("A trusted authorization callback is required.")
        if admit is not None and not callable(admit):
            raise OperationError("The admission callback must be callable.")
        key_digest = hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()
        with self.database.transaction() as connection:
            now = self._now()
            plan = self._plan(connection, principal_id, plan_id)
            existing = connection.execute(
                _SELECT_OPERATION + " WHERE o.principal_id = ? AND o.idempotency_digest = ?",
                (principal_id, key_digest),
            ).fetchone()
            if existing is not None:
                if existing["parameter_digest"] != plan.parameter_digest:
                    raise IdempotencyConflict("The idempotency key identifies different operation parameters.")
                return self._snapshot(existing)
            review = self._available_review(connection, plan, now)
            authorize(connection, plan)
            self._check_admission(connection, plan.principal_id, plan.reservation_bytes)
            if admit is not None:
                admit(connection, plan)
            operation_id = "op_" + uuid.uuid4().hex
            connection.execute(
                """INSERT INTO km_operations(
                    operation_id, principal_id, plan_id, review_id, kind, parameter_digest,
                    idempotency_digest, output_id, reservation_bytes, state, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)""",
                (operation_id, principal_id, plan_id, review["review_id"], plan.kind,
                 plan.parameter_digest, key_digest, "output_" + uuid.uuid4().hex,
                 plan.reservation_bytes, now, now),
            )
            connection.execute(
                "UPDATE km_operation_reviews SET consumed_by = ? WHERE review_id = ?",
                (operation_id, review["review_id"]),
            )
            return self._snapshot(self._operation(connection, principal_id, operation_id))

    def get(
        self, principal_id: str, operation_id: str, *, connection: sqlite3.Connection | None = None,
    ) -> OperationSnapshot:
        require_opaque_id(principal_id)
        require_opaque_id(operation_id)
        if connection is None:
            with self.database.transaction(immediate=False) as current:
                return self.get(principal_id, operation_id, connection=current)
        self.database.validate_connection(connection)
        return self._snapshot(self._operation(connection, principal_id, operation_id))

    def reserved_bytes(self, connection: sqlite3.Connection | None = None) -> int:
        """Return declared pending/live-executor reservations, not stored output size.

        A service may add retained outputs and upload bytes in an admission
        callback using the same transaction. Completed output retention remains
        a separate storage-policy responsibility.
        """
        if connection is None:
            with self.database.transaction(immediate=False) as current:
                return self.reserved_bytes(current)
        self.database.validate_connection(connection)
        return connection.execute(
            "SELECT COALESCE(SUM(reservation_bytes), 0) FROM km_operations WHERE " + _RESERVED_SQL,
        ).fetchone()[0]

    def list(
        self, principal_id: str, *, limit: int = 50, before_operation_id: str | None = None,
    ) -> tuple[OperationSnapshot, ...]:
        """Return one bounded, principal-filtered page ordered newest first."""
        require_opaque_id(principal_id)
        if type(limit) is not int or not 1 <= limit <= self.limits.max_list_items:
            raise OperationError("The operation list limit is outside its supported range.")
        with self.database.transaction(immediate=False) as connection:
            cursor_clause = ""
            values: list[Any] = [principal_id]
            if before_operation_id is not None:
                require_opaque_id(before_operation_id)
                cursor = self._operation(connection, principal_id, before_operation_id)
                cursor_clause = " AND (o.created_at < ? OR (o.created_at = ? AND o.operation_id < ?))"
                values.extend((cursor["created_at"], cursor["created_at"], before_operation_id))
            values.append(limit)
            rows = connection.execute(
                _SELECT_OPERATION + " WHERE o.principal_id = ?" + cursor_clause
                + " ORDER BY o.created_at DESC, o.operation_id DESC LIMIT ?", values,
            ).fetchall()
            return tuple(self._snapshot(row) for row in rows)

    def request_cancel(self, principal_id: str, operation_id: str) -> CancellationReceipt:
        require_opaque_id(principal_id)
        require_opaque_id(operation_id)
        with self.database.transaction() as connection:
            now = self._now()
            row = self._operation(connection, principal_id, operation_id)
            if row["state"] in TERMINAL_STATES:
                return CancellationReceipt(self._snapshot(row), "already_terminal")
            if row["state"] == "queued" or (row["state"] == "interrupted" and row["reconciled"]):
                state, disposition = "cancelled", "cancelled"
            elif row["publication_authorized_at"] is not None:
                state, disposition = row["state"], "publication_committed"
            else:
                state, disposition = "cancel_requested", "requested"
            connection.execute(
                "UPDATE km_operations SET state = ?, cancel_requested = 1, updated_at = ? WHERE operation_id = ?",
                (state, now, operation_id),
            )
            return CancellationReceipt(
                self._snapshot(self._operation(connection, principal_id, operation_id)), disposition,
            )

    def retry(
        self, principal_id: str, operation_id: str, *, authorize: Authorizer,
    ) -> OperationSnapshot:
        """Retry only a reconciled interruption, with bounded attempts and fresh access.

        A still-valid review already consumed by this same job remains usable.
        An expired review requires a new trusted gesture on the unchanged plan.
        Failed jobs are not automatically classified as retryable.
        """
        require_opaque_id(principal_id)
        require_opaque_id(operation_id)
        if not callable(authorize):
            raise OperationError("A trusted authorization callback is required.")
        with self.database.transaction() as connection:
            now = self._now()
            row = self._operation(connection, principal_id, operation_id)
            if row["state"] != "interrupted" or not row["reconciled"] or row["cancel_requested"]:
                raise OperationError("Only a reconciled, uncancelled interruption may be retried.")
            if row["attempt_number"] >= self.limits.max_attempts:
                raise OperationError("The operation has reached its attempt limit.")
            plan = self._plan(connection, principal_id, row["plan_id"])
            if plan.expires_at <= now:
                raise OperationError("The operation plan has expired.")
            review = connection.execute(
                "SELECT * FROM km_operation_reviews WHERE review_id = ?", (row["review_id"],),
            ).fetchone()
            if review is None or review["expires_at"] <= now:
                review = self._available_review(connection, plan, now)
                connection.execute(
                    "UPDATE km_operation_reviews SET consumed_by = ? WHERE review_id = ?",
                    (operation_id, review["review_id"]),
                )
            authorize(connection, plan)
            connection.execute(
                "UPDATE km_operations SET state = 'queued', review_id = ?, error_code = NULL, updated_at = ? "
                "WHERE operation_id = ?", (review["review_id"], now, operation_id),
            )
            return self._snapshot(self._operation(connection, principal_id, operation_id))

    def acquire_worker(self) -> WorkerSession:
        from .worker import WorkerSession
        return WorkerSession.acquire(self)

    def claim(self, session: WorkerSession) -> OperationAttempt | None:
        """Reserve one attempt; the session remains occupied until its executor returns."""
        from .worker import OperationAttempt
        with session._guard:
            session._require_idle(self)
            with self.database.transaction() as connection:
                now = self._now()
                self._require_worker(connection, session)
                # A new process must reconcile old attempts before admitting any
                # work, even when an old attempt appears to have completed I/O.
                unresolved = connection.execute(
                    "SELECT 1 FROM km_operations WHERE worker_released = 0 LIMIT 1"
                ).fetchone()
                if unresolved is not None:
                    raise OperationBusy("An existing attempt requires completion or restart reconciliation.")
                while True:
                    row = connection.execute(
                        _SELECT_OPERATION + " WHERE o.state = 'queued' ORDER BY o.created_at, o.operation_id LIMIT 1"
                    ).fetchone()
                    if row is None:
                        return None
                    plan = self._plan(connection, row["principal_id"], row["plan_id"])
                    review = connection.execute(
                        "SELECT expires_at FROM km_operation_reviews WHERE review_id = ?", (row["review_id"],),
                    ).fetchone()
                    if plan.expires_at > now and review is not None and review["expires_at"] > now:
                        break
                    connection.execute(
                        "UPDATE km_operations SET state = 'expired', error_code = 'plan_expired', updated_at = ? "
                        "WHERE operation_id = ?", (now, row["operation_id"]),
                    )
                number = row["attempt_number"] + 1
                if number > self.limits.max_attempts:
                    raise OperationError("The operation has reached its attempt limit.")
                token = uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO km_operation_attempts(operation_id, attempt_number, attempt_token, "
                    "worker_token, worker_epoch, started_at) VALUES(?, ?, ?, ?, ?, ?)",
                    (row["operation_id"], number, token, session.token, session.epoch, now),
                )
                connection.execute(
                    "UPDATE km_operations SET state = 'running', attempt_number = ?, reconciled = 0, worker_released = 0, "
                    "error_code = NULL, updated_at = ? WHERE operation_id = ?",
                    (number, now, row["operation_id"]),
                )
            attempt = OperationAttempt(self, session, row["operation_id"], row["output_id"], plan, number, token)
            session._activate(attempt)
            return attempt

    def checkpoint(self, attempt: OperationAttempt, *, verifying: bool = False) -> None:
        if type(verifying) is not bool:
            raise OperationError("The verification checkpoint flag must be boolean.")
        attempt._session._require_attempt(attempt)
        with self.database.transaction(immediate=verifying) as connection:
            row = self._require_attempt(connection, attempt)
            if row["cancel_requested"] and row["publication_authorized_at"] is None:
                raise OperationCancelled("The operation was cancelled before publication authorization.")
            if row["state"] not in ACTIVE_STATES:
                raise StaleAttempt("The operation attempt is no longer active.")
            if verifying and row["state"] == "running":
                connection.execute(
                    "UPDATE km_operations SET state = 'verifying', updated_at = ? WHERE operation_id = ?",
                    (self._now(), attempt.operation_id),
                )

    def authorize_publication(
        self, attempt: OperationAttempt, authorize: Authorizer, *, manifest_sha256: str,
    ) -> PublicationPermit:
        """Commit a publication decision in the same transaction as grant validation.

        The live OS worker lock remains held through the later filesystem rename.
        A permit is valid only for this attempt and this intended output. After
        this transaction commits, cancellation/revocation cannot undo an already
        authorized private publication; disclosure is authorized separately.
        """
        require_digest(manifest_sha256)
        if not callable(authorize):
            raise OperationError("A trusted authorization callback is required.")
        attempt._session._require_attempt(attempt)
        with self.database.transaction() as connection:
            row = self._require_attempt(connection, attempt)
            if row["state"] not in ACTIVE_STATES:
                raise StaleAttempt("The operation attempt is no longer active.")
            authorized_at = row["publication_authorized_at"]
            if authorized_at is not None:
                if row["manifest_sha256"] != manifest_sha256:
                    raise OperationError("The publication decision is bound to different output bytes.")
                return PublicationPermit(
                    attempt.operation_id, attempt.output_id, attempt.attempt_number, manifest_sha256, authorized_at,
                )
            if row["cancel_requested"]:
                raise OperationCancelled("The operation was cancelled before publication authorization.")
            if row["state"] != "verifying":
                raise OperationError("Output verification must precede publication authorization.")
            authorize(connection, attempt.plan)
            authorized_at = self._now()
            connection.execute(
                "UPDATE km_operation_attempts SET publication_authorized_at = ?, manifest_sha256 = ? "
                "WHERE operation_id = ? AND attempt_number = ?",
                (authorized_at, manifest_sha256, attempt.operation_id, attempt.attempt_number),
            )
            connection.execute(
                "UPDATE km_operations SET updated_at = ? WHERE operation_id = ?",
                (authorized_at, attempt.operation_id),
            )
        return PublicationPermit(
            attempt.operation_id, attempt.output_id, attempt.attempt_number, manifest_sha256, authorized_at,
        )

    def complete(self, attempt: OperationAttempt, result: VerifiedResult) -> OperationSnapshot:
        """Record verified output after no-replacement publication has succeeded."""
        result_json = self._result_json(result)
        attempt._session._require_attempt(attempt)
        with self.database.transaction() as connection:
            row = self._require_attempt(connection, attempt)
            if (row["state"] not in ACTIVE_STATES or row["publication_authorized_at"] is None
                    or row["manifest_sha256"] != result.manifest_sha256):
                raise OperationError("Completion requires the exact authorized, verified publication.")
            self._finish_verified(connection, row, result, result_json, self._now())
            return self._snapshot(self._operation(connection, attempt.plan.principal_id, attempt.operation_id))

    def fail(self, attempt: OperationAttempt, error_code: str) -> OperationSnapshot:
        """Record a bounded category; ambiguous publication remains interrupted."""
        if not isinstance(error_code, str) or error_code not in FAILURE_CODES:
            raise OperationError("The failure category is unsupported.")
        attempt._session._require_attempt(attempt)
        with self.database.transaction() as connection:
            now = self._now()
            row = self._require_attempt(connection, attempt)
            if row["state"] not in ACTIVE_STATES:
                raise StaleAttempt("The operation attempt is no longer active.")
            if row["publication_authorized_at"] is not None or error_code in {"worker_interrupted", "cleanup_required"}:
                state = "interrupted"
            elif row["cancel_requested"] or error_code == "cancelled":
                state = "cancelled"
            else:
                state = "failed"
            connection.execute(
                "UPDATE km_operations SET state = ?, error_code = ?, updated_at = ?, reconciled = ? "
                "WHERE operation_id = ?",
                (state, error_code, now, int(state != "interrupted"), attempt.operation_id),
            )
            connection.execute(
                "UPDATE km_operation_attempts SET ended_at = ? WHERE operation_id = ? AND attempt_number = ?",
                (now, attempt.operation_id, attempt.attempt_number),
            )
            return self._snapshot(self._operation(connection, attempt.plan.principal_id, attempt.operation_id))

    def release_attempt(self, attempt: OperationAttempt) -> None:
        """Release admission only after the caller's synchronous executor returned.

        OperationWorker enforces this ordering automatically. Manual drivers are
        responsible for calling this method from the claim thread after all I/O
        has stopped, never from a cancellation or shutdown request handler.
        """
        attempt._session._require_attempt(attempt)
        with self.database.transaction() as connection:
            row = self._require_attempt(connection, attempt)
            if row["state"] not in TERMINAL_STATES | {"interrupted"}:
                raise OperationBusy("The executor must finish before its worker reservation is released.")
            connection.execute(
                "UPDATE km_operations SET worker_released = 1 WHERE operation_id = ?", (attempt.operation_id,),
            )
        attempt._session._release_returned_execution(attempt)

    def reconcile(
        self, session: WorkerSession, inspect_output: OutputInspector,
    ) -> tuple[OperationSnapshot, ...]:
        """Fence interrupted attempts, then independently inspect authorized output.

        The inspector returns None only after establishing output absence. A
        verified result must match the recorded manifest digest. Exceptions or
        mismatches leave the job interrupted and ineligible for retry; no error
        text is persisted. Long verification runs outside SQLite transactions.
        """
        if not callable(inspect_output):
            raise OperationError("A trusted output inspector is required.")
        with session._guard:
            session._require_idle(self)
            with self.database.transaction() as connection:
                now = self._now()
                self._require_worker(connection, session)
                connection.execute("UPDATE km_operations SET worker_released = 1 WHERE worker_released = 0")
                rows = connection.execute(
                    _SELECT_OPERATION
                    + " WHERE o.state IN ('running', 'verifying', 'cancel_requested', 'interrupted') "
                    "AND o.reconciled = 0 ORDER BY o.created_at, o.operation_id"
                ).fetchall()
                for row in rows:
                    connection.execute(
                        "UPDATE km_operations SET state = 'interrupted', error_code = 'worker_interrupted', "
                        "updated_at = ? WHERE operation_id = ?", (now, row["operation_id"]),
                    )
                    connection.execute(
                        "UPDATE km_operation_attempts SET ended_at = COALESCE(ended_at, ?) "
                        "WHERE operation_id = ? AND attempt_number = ?",
                        (now, row["operation_id"], row["attempt_number"]),
                    )
            results: list[OperationSnapshot] = []
            for previous in rows:
                snapshot = self.get(previous["principal_id"], previous["operation_id"])
                inspected: VerifiedResult | None = None
                failure: str | None = None
                cleanup_required = False
                if snapshot.publication_authorized:
                    try:
                        inspected = inspect_output(snapshot)
                        if inspected is not None:
                            self._result_json(inspected)
                            if inspected.manifest_sha256 != snapshot.manifest_sha256:
                                failure = "integrity_failed"
                    except OperationCleanupRequired:
                        failure = "cleanup_required"
                        cleanup_required = True
                    except Exception:
                        failure = "reconciliation_failed"
                with self.database.transaction() as connection:
                    self._require_worker(connection, session)
                    current = self._operation(connection, snapshot.principal_id, snapshot.operation_id)
                    if current["state"] not in {"interrupted", "cancel_requested"}:
                        raise OperationError("The reconciliation state changed unexpectedly.")
                    now = self._now()
                    if failure is not None:
                        connection.execute(
                            "UPDATE km_operations SET state = 'interrupted', error_code = ?, updated_at = ? "
                            "WHERE operation_id = ?", (failure, now, snapshot.operation_id),
                        )
                    elif inspected is not None:
                        self._finish_verified(connection, current, inspected, self._result_json(inspected), now)
                    else:
                        state = "cancelled" if current["cancel_requested"] else "interrupted"
                        connection.execute(
                            "UPDATE km_operations SET state = ?, reconciled = 1, updated_at = ? WHERE operation_id = ?",
                            (state, now, snapshot.operation_id),
                        )
                        connection.execute(
                            "UPDATE km_operation_attempts SET publication_resolution = 'absent' "
                            "WHERE operation_id = ? AND attempt_number = ?",
                            (snapshot.operation_id, current["attempt_number"]),
                        )
                    results.append(self._snapshot(self._operation(connection, snapshot.principal_id, snapshot.operation_id)))
                if cleanup_required:
                    raise OperationCleanupRequired("Reconciliation workspace cleanup requires operator review.")
            return tuple(results)

    def _available_review(
        self, connection: sqlite3.Connection, plan: OperationPlan, now: float,
    ) -> sqlite3.Row:
        if plan.expires_at <= now:
            raise OperationError("The operation plan has expired.")
        review = connection.execute(
            "SELECT * FROM km_operation_reviews WHERE principal_id = ? AND plan_id = ? "
            "AND parameter_digest = ? AND expires_at > ? AND consumed_by IS NULL "
            "ORDER BY reviewed_at, review_id LIMIT 1",
            (plan.principal_id, plan.plan_id, plan.parameter_digest, now),
        ).fetchone()
        if review is None:
            raise OperationError("An unused, unexpired human review of this exact plan is required.")
        return review

    def _check_admission(self, connection: sqlite3.Connection, principal_id: str, reservation: int) -> None:
        row = connection.execute(
            "SELECT COUNT(*) AS count, COALESCE(SUM(reservation_bytes), 0) AS bytes, "
            "COALESCE(SUM(CASE WHEN principal_id = ? THEN 1 ELSE 0 END), 0) AS principal_count "
            "FROM km_operations WHERE " + _RESERVED_SQL, (principal_id,),
        ).fetchone()
        if (row["count"] >= self.limits.max_pending_operations
                or row["principal_count"] >= self.limits.max_pending_per_principal
                or row["bytes"] + reservation > self.limits.max_reserved_bytes):
            raise OperationBusy("The operation queue or its declared byte budget is full.")

    def _plan(self, connection: sqlite3.Connection, principal_id: str, plan_id: str) -> OperationPlan:
        row = connection.execute(
            "SELECT * FROM km_operation_plans WHERE principal_id = ? AND plan_id = ?", (principal_id, plan_id),
        ).fetchone()
        if row is None:
            raise OperationError("The operation plan is unavailable.")
        document = self._json_document(row["canonical_json"], self.limits.max_plan_bytes)
        if (set(document) != {"version", "principal_id", "kind", "parameters", "scope", "reservation_bytes"}
                or type(document["version"]) is not int or document["version"] != 1
                or document["principal_id"] != principal_id or document["kind"] != row["kind"]
                or not isinstance(document["scope"], dict)):
            raise OperationError("The stored operation plan schema is invalid.")
        try:
            scope = AuthorizationScope(**document["scope"])
        except TypeError as error:
            raise OperationError("The stored authorization scope is invalid.") from error
        parameters = parse_parameters(row["kind"], document["parameters"])
        encoded = canonical_document(principal_id, parameters, scope, document["reservation_bytes"])
        if parameter_digest(encoded) != row["parameter_digest"] or encoded.decode("ascii") != row["canonical_json"]:
            raise OperationError("The stored operation plan digest does not match its parameters.")
        return OperationPlan(
            row["plan_id"], principal_id, row["kind"], parameters, scope, document["reservation_bytes"],
            row["parameter_digest"], row["created_at"], row["expires_at"],
        )

    @staticmethod
    def _operation(connection: sqlite3.Connection, principal_id: str, operation_id: str) -> sqlite3.Row:
        row = connection.execute(
            _SELECT_OPERATION + " WHERE o.principal_id = ? AND o.operation_id = ?", (principal_id, operation_id),
        ).fetchone()
        if row is None:
            raise OperationError("The operation is unavailable.")
        return row

    @staticmethod
    def _require_worker(connection: sqlite3.Connection, session: WorkerSession) -> None:
        session._require_open()
        row = connection.execute("SELECT * FROM km_operation_worker WHERE singleton = 1").fetchone()
        if row is None or row["epoch"] != session.epoch or row["worker_token"] != session.token:
            raise StaleAttempt("The worker no longer owns the operation journal.")

    def _require_attempt(self, connection: sqlite3.Connection, attempt: OperationAttempt) -> sqlite3.Row:
        self._require_worker(connection, attempt._session)
        row = self._operation(connection, attempt.plan.principal_id, attempt.operation_id)
        if (row["attempt_number"] != attempt.attempt_number or row["attempt_token"] != attempt._token
                or row["worker_epoch"] != attempt._session.epoch
                or row["worker_token"] != attempt._session.token):
            raise StaleAttempt("The caller does not own this operation attempt.")
        return row

    def _result_json(self, result: VerifiedResult) -> str:
        if not isinstance(result, VerifiedResult):
            raise OperationError("Completion requires a typed verified result.")
        document = json.dumps(result.as_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(document.encode("utf-8")) > self.limits.max_result_bytes:
            raise OperationError("The result exceeds its metadata byte limit.")
        return document

    def _snapshot(self, row: sqlite3.Row) -> OperationSnapshot:
        result = None
        if row["result_json"] is not None:
            value = self._json_document(row["result_json"], self.limits.max_result_bytes)
            if (set(value) != {"verification_stage", "manifest_sha256", "file_count", "total_bytes", "coverage_gaps", "artifact_sha256"}
                    or value["verification_stage"] != "local_output_validation"
                    or not isinstance(value["coverage_gaps"], list)):
                raise OperationError("The stored result schema is invalid.")
            result = VerifiedResult(
                value["manifest_sha256"], value["file_count"], value["total_bytes"],
                tuple(value["coverage_gaps"]), value["artifact_sha256"],
            )
        if (row["state"] in {"completed", "partial"}) != (result is not None):
            raise OperationError("The stored result does not match the operation state.")
        if result is not None and (
            row["publication_authorized_at"] is None or row["manifest_sha256"] != result.manifest_sha256
            or (row["state"] == "partial") != bool(result.coverage_gaps)
        ):
            raise OperationError("The stored result does not match its publication decision or coverage.")
        return OperationSnapshot(
            row["operation_id"], row["principal_id"], row["plan_id"], row["kind"], row["state"],
            row["parameter_digest"], row["output_id"], row["reservation_bytes"], row["attempt_number"],
            bool(row["cancel_requested"]),
            row["publication_authorized_at"] is not None and row["publication_resolution"] != "absent",
            row["manifest_sha256"], row["error_code"], row["created_at"], row["updated_at"], result,
        )

    @staticmethod
    def _review(row: sqlite3.Row) -> HumanReview:
        return HumanReview(
            row["review_id"], row["plan_id"], row["principal_id"], row["parameter_digest"],
            row["interaction_id"], row["reviewed_at"], row["expires_at"],
        )

    @staticmethod
    def _json_document(value: object, maximum_bytes: int) -> dict[str, Any]:
        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in pairs:
                if key in result:
                    raise OperationError("The stored journal document contains duplicate fields.")
                result[key] = item
            return result

        def reject_constant(value: str) -> None:
            raise OperationError("The stored journal document contains an invalid number.")

        if not isinstance(value, str):
            raise OperationError("The stored journal document is invalid.")
        try:
            if len(value.encode("utf-8")) > maximum_bytes:
                raise OperationError("The stored journal document exceeds its byte limit.")
            result = json.loads(value, object_pairs_hook=unique_object, parse_constant=reject_constant)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise OperationError("The stored journal document is invalid.") from error
        if not isinstance(result, dict):
            raise OperationError("The stored journal document must be an object.")
        return result

    @staticmethod
    def _finish_verified(
        connection: sqlite3.Connection, row: sqlite3.Row, result: VerifiedResult, result_json: str, now: float,
    ) -> None:
        state = "partial" if result.coverage_gaps else "completed"
        connection.execute(
            "UPDATE km_operations SET state = ?, result_json = ?, error_code = NULL, reconciled = 1, "
            "updated_at = ? WHERE operation_id = ?", (state, result_json, now, row["operation_id"]),
        )
        connection.execute(
            "UPDATE km_operation_attempts SET ended_at = ?, publication_resolution = 'verified' "
            "WHERE operation_id = ? AND attempt_number = ?", (now, row["operation_id"], row["attempt_number"]),
        )
