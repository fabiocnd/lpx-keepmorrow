"""One process-exclusive worker with cooperative, ownership-preserving shutdown.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import math
import os
import stat
import threading
import uuid
from dataclasses import dataclass, field
from typing import BinaryIO, TYPE_CHECKING
from collections.abc import Callable

from .model import (
    ACTIVE_STATES, OperationBusy, OperationCancelled, OperationCleanupRequired, OperationError, OperationPlan,
    OperationSnapshot, PublicationPermit, StaleAttempt, VerifiedResult,
)

if TYPE_CHECKING:
    from .store import Authorizer, OperationStore, OutputInspector


def _open_worker_lock(store: OperationStore) -> BinaryIO:
    """Acquire a nonblocking OS lock on a stable local sidecar.

    POSIX additionally requires owner-only permission bits. Windows uses its
    byte-range lock; directory protection remains an operator responsibility.
    Closing the stream or process exit releases the operating-system lock.
    """
    path = store.database.path.with_name(store.database.path.name + ".operations.lock")
    descriptor: int | None = None
    stream: BinaryIO | None = None
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or (os.name == "posix" and info.st_mode & 0o077)):
            raise OperationError("Worker coordination requires an ordinary owner-only lock file.")
        stream = os.fdopen(descriptor, "r+b", buffering=0)
        descriptor = None
        if os.name == "posix":
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise OperationBusy("Another process already owns the operation worker.") from error
        elif os.name == "nt":
            import msvcrt
            if info.st_size == 0:
                stream.write(b"\0")
                stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise OperationBusy("Another process already owns the operation worker.") from error
        else:
            raise OperationError("This platform has no supported exclusive worker lock.")
        return stream
    except BaseException:
        if stream is not None:
            stream.close()
        if descriptor is not None:
            os.close(descriptor)
        raise


class WorkerSession:
    """Retain process-exclusive worker ownership through execution and cleanup.

    There is no expiring lease: time alone must not admit a new worker while an
    old thread can still publish. A new epoch is allocated only after acquiring
    the process lock. Do not fork or replace the database/lock files while a
    session is open; those are operator-owned lifecycle boundaries.
    """

    def __init__(self, store: OperationStore, stream: BinaryIO, token: str, epoch: int) -> None:
        self._store = store
        self._stream = stream
        self.token = token
        self.epoch = epoch
        self._pid = os.getpid()
        self._guard = threading.RLock()
        self._active: OperationAttempt | None = None
        self._claim_thread: int | None = None
        self._closed = False

    @classmethod
    def acquire(cls, store: OperationStore) -> WorkerSession:
        """Allocate a new journal epoch only after obtaining the live process lock."""
        stream = _open_worker_lock(store)
        token = uuid.uuid4().hex
        try:
            with store.database.transaction() as connection:
                row = connection.execute("SELECT epoch FROM km_operation_worker WHERE singleton = 1").fetchone()
                if row is None or row["epoch"] >= 2**63 - 1:
                    raise OperationError("The worker ownership epoch is unavailable.")
                epoch = row["epoch"] + 1
                connection.execute(
                    "UPDATE km_operation_worker SET epoch = ?, worker_token = ? WHERE singleton = 1",
                    (epoch, token),
                )
            return cls(store, stream, token, epoch)
        except BaseException:
            stream.close()
            raise

    def _require_open(self) -> None:
        if self._closed or self._pid != os.getpid():
            raise StaleAttempt("The worker session is closed or belongs to another process.")

    def _require_idle(self, store: OperationStore) -> None:
        self._require_open()
        if self._store is not store:
            raise StaleAttempt("The worker session belongs to another operation store.")
        if self._active is not None:
            raise OperationBusy("The active executor still owns the worker reservation.")

    def _activate(self, attempt: OperationAttempt) -> None:
        self._active = attempt
        self._claim_thread = threading.get_ident()

    def _require_attempt(self, attempt: OperationAttempt) -> None:
        with self._guard:
            self._require_open()
            if self._active is not attempt or self._claim_thread != threading.get_ident():
                raise StaleAttempt("Only the owning executor thread may advance this attempt.")

    def _release_returned_execution(self, attempt: OperationAttempt) -> None:
        """Called only once the synchronous executor has unwound, even on DB failure."""
        with self._guard:
            self._require_attempt(attempt)
            self._active = None
            self._claim_thread = None

    def close(self) -> None:
        """Release an idle session; active executors must unwind before closure."""
        with self._guard:
            if self._closed:
                return
            self._require_idle(self._store)
            try:
                with self._store.database.transaction() as connection:
                    connection.execute(
                        "UPDATE km_operation_worker SET worker_token = NULL "
                        "WHERE singleton = 1 AND epoch = ? AND worker_token = ?",
                        (self.epoch, self.token),
                    )
            finally:
                # Closing is safe here because no executor owns this session.
                # A failed metadata update leaves a stale epoch to reconcile.
                self._closed = True
                self._stream.close()

    def __enter__(self) -> WorkerSession:
        self._require_open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class OperationAttempt:
    """An immutable handle usable only by its session's owning executor thread.

    Store methods enforce token, epoch, state, and publication fences. Sharing
    this object with another thread does not delegate execution authority.
    """

    _store: OperationStore = field(repr=False)
    _session: WorkerSession = field(repr=False)
    operation_id: str
    output_id: str
    plan: OperationPlan
    attempt_number: int
    _token: str = field(repr=False)

    def checkpoint(self, *, verifying: bool = False) -> None:
        self._store.checkpoint(self, verifying=verifying)

    def authorize_publication(
        self, authorize: Authorizer, *, manifest_sha256: str,
    ) -> PublicationPermit:
        return self._store.authorize_publication(self, authorize, manifest_sha256=manifest_sha256)

    def complete(self, result: VerifiedResult) -> OperationSnapshot:
        return self._store.complete(self, result)

    def fail(self, error_code: str) -> OperationSnapshot:
        return self._store.fail(self, error_code)


Executor = Callable[[OperationAttempt], None]
FailureClassifier = Callable[[Exception], str]


class OperationWorker:
    """Run one synchronous executor on a dedicated, bounded background thread.

    Status and cancellation use OperationStore directly and never wait for the
    worker slot. A shutdown timeout reports an active worker without releasing
    its lock or admitting replacement work. Exceptions are reduced to fixed
    categories; this worker does not persist or log their messages or tracebacks.
    """

    def __init__(
        self, store: OperationStore, executor: Executor, reconciler: OutputInspector, *,
        classify_failure: FailureClassifier | None = None, poll_interval_seconds: float = 0.25,
        startup: Callable[[], None] | None = None,
    ) -> None:
        if not callable(executor) or not callable(reconciler):
            raise OperationError("The worker requires trusted execution and reconciliation callbacks.")
        if (type(poll_interval_seconds) not in (float, int) or not math.isfinite(poll_interval_seconds)
                or not 0.01 <= poll_interval_seconds <= 10):
            raise OperationError("The worker poll interval is outside its supported range.")
        if classify_failure is not None and not callable(classify_failure):
            raise OperationError("The failure classifier must be callable.")
        if startup is not None and not callable(startup):
            raise OperationError("The exclusive startup callback must be callable.")
        self._store = store
        self._executor = executor
        self._reconciler = reconciler
        self._classify_failure = classify_failure
        self._startup = startup
        self._poll_interval = poll_interval_seconds
        self._guard = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._session: WorkerSession | None = None
        self._active: OperationAttempt | None = None
        self.last_error_code: str | None = None

    def start(self) -> None:
        """Acquire exclusive ownership and reconcile before starting execution."""
        with self._guard:
            if self._thread is not None:
                raise OperationBusy("This worker has already been started.")
            session = self._store.acquire_worker()
            try:
                if self._startup is not None:
                    self._startup()
                self._store.reconcile(session, self._reconciler)
                self._session = session
                thread = threading.Thread(target=self._run, name="keepmorrow-operations", daemon=False)
                self._thread = thread
                thread.start()
            except BaseException:
                self._session = None
                self._thread = None
                session.close()
                raise

    def notify(self) -> None:
        """Wake the worker after admission; polling remains a bounded fallback."""
        self._wake.set()

    def shutdown(self, *, timeout_seconds: float = 5, cancel_active: bool = False) -> bool:
        """Stop new claims and wait for cooperative worker exit.

        False means the thread is still alive; ownership is not forcibly released.
        The timeout bounds the join, not preceding cancellation or database work.
        A cancellation request cannot roll back committed publication.
        """
        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                or not 0 <= timeout_seconds <= 60 or type(cancel_active) is not bool):
            raise OperationError("The shutdown timeout or cancellation option is invalid.")
        self._stop.set()
        self._wake.set()
        with self._guard:
            thread, attempt = self._thread, self._active
        if cancel_active and attempt is not None:
            self._store.request_cancel(attempt.plan.principal_id, attempt.operation_id)
        if thread is None:
            return True
        if thread.ident == threading.get_ident():
            raise OperationError("A worker cannot join its own executor thread.")
        thread.join(timeout_seconds)
        return not thread.is_alive()

    def _run(self) -> None:
        session = self._session
        if session is None:
            self.last_error_code = "worker_unavailable"
            return
        try:
            while not self._stop.is_set():
                with self._guard:
                    if self._stop.is_set():
                        break
                    attempt = self._store.claim(session)
                    self._active = attempt
                if attempt is None:
                    self._wake.wait(self._poll_interval)
                    self._wake.clear()
                    continue
                retain_reservation = False
                try:
                    self._executor(attempt)
                    current = self._store.get(attempt.plan.principal_id, attempt.operation_id)
                    if current.state in ACTIVE_STATES:
                        attempt.fail("executor_incomplete")
                except OperationCancelled:
                    self._record_failure(attempt, "cancelled")
                except OperationCleanupRequired:
                    # Completion may already be visible. Retain the byte charge
                    # until startup recovery or operator review resolves cleanup.
                    retain_reservation = True
                    self.last_error_code = "workspace_cleanup_required"
                    self._record_failure(attempt, "cleanup_required")
                    self._stop.set()
                except Exception as error:
                    code = "execution_failed"
                    if self._classify_failure is not None:
                        try:
                            code = self._classify_failure(error)
                        except Exception:
                            code = "execution_failed"
                    self._record_failure(attempt, code)
                except BaseException:
                    self._record_failure(attempt, "worker_interrupted")
                    self._stop.set()
                finally:
                    # The callback has returned or unwound. Releasing before
                    # this point would allow concurrent I/O after cancellation.
                    if retain_reservation:
                        session._release_returned_execution(attempt)
                    else:
                        try:
                            self._store.release_attempt(attempt)
                        except Exception:
                            self.last_error_code = "journal_unavailable"
                            self._stop.set()
                            session._release_returned_execution(attempt)
                    with self._guard:
                        self._active = None
        except BaseException:
            self.last_error_code = "journal_unavailable"
        finally:
            try:
                session.close()
            except Exception:
                self.last_error_code = "journal_unavailable"

    def _record_failure(self, attempt: OperationAttempt, code: str) -> None:
        from .model import FAILURE_CODES
        try:
            current = self._store.get(attempt.plan.principal_id, attempt.operation_id)
            if current.state in ACTIVE_STATES:
                attempt.fail(code if isinstance(code, str) and code in FAILURE_CODES else "execution_failed")
        except Exception:
            self.last_error_code = "journal_unavailable"
            self._stop.set()
