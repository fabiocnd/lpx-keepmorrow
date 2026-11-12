"""SQLite transactions with explicit ownership and component schema versions.

The database belongs on an operator-controlled local filesystem. It contains
control metadata, never bearer credentials or preserved conversation bodies.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import os
from pathlib import Path
import re
import sqlite3
import stat

_APPLICATION_ID = 0x4B4D5257
_COMPONENT = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class PersistenceError(RuntimeError):
    """A bounded storage error that is safe to expose without a filesystem path."""

    def __init__(self, message: str, *, code: str = "metadata_storage_unavailable") -> None:
        super().__init__(message)
        self.code = code


class _TransactionConnection(sqlite3.Connection):
    database_path: Path
    immediate_transaction: bool


class SQLiteDatabase:
    """Own short transactions on one private, local SQLite metadata database.

    The parent directory must already exist and have no symbolic-link ancestor.
    New files use mode 0600 on POSIX; existing files must already be owner-only.
    The containing directory and its ancestors must not be attacker-writable.
    SQLite cannot provide path-race isolation against a hostile filesystem owner.

    Every transaction gets its own connection. BEGIN IMMEDIATE serializes writes
    and publication decisions against revocation; file copying must remain
    outside that transaction. A five-second busy timeout is the default bound.
    """

    def __init__(self, path: Path, *, busy_timeout_ms: int = 5000) -> None:
        if (not isinstance(path, Path) or type(busy_timeout_ms) is not int
                or not 1 <= busy_timeout_ms <= 60_000):
            raise PersistenceError("Invalid metadata database configuration.", code="invalid_database_configuration")
        self._path = Path(os.path.abspath(path))
        self._busy_timeout_ms = busy_timeout_ms
        try:
            for parent in reversed((self._path.parent, *self._path.parent.parents)):
                info = parent.lstat()
                if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                    raise PersistenceError("Metadata storage requires ordinary directories.")
            try:
                descriptor = os.open(
                    self._path,
                    os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
            except FileExistsError:
                pass
            else:
                os.close(descriptor)
            self._file_identity = self._validate_file()
            with self.transaction() as connection:
                application_id = connection.execute("PRAGMA application_id").fetchone()[0]
                if application_id not in (0, _APPLICATION_ID):
                    raise PersistenceError("The database belongs to an unsupported application.", code="unsupported_database_schema")
                if application_id == 0:
                    existing = connection.execute(
                        "SELECT 1 FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
                    ).fetchone()
                    if existing is not None:
                        raise PersistenceError("An unrecognized database cannot be adopted.", code="unsupported_database_schema")
                    connection.execute(f"PRAGMA application_id = {_APPLICATION_ID}")
                    connection.execute(
                        "CREATE TABLE km_schema_versions ("
                        "component TEXT PRIMARY KEY NOT NULL, "
                        "version INTEGER NOT NULL CHECK(version >= 1))"
                    )
                elif connection.execute(
                    "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'km_schema_versions'"
                ).fetchone() is None:
                    raise PersistenceError("The metadata schema registry is unavailable.", code="unsupported_database_schema")
        except PersistenceError:
            raise
        except (OSError, ValueError) as error:
            raise PersistenceError("The metadata database could not be initialized.") from error

    @property
    def path(self) -> Path:
        """Return the operator-selected absolute path, never a model-facing ID."""
        return self._path

    def _validate_file(self) -> tuple[int, int]:
        info = self._path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
            raise PersistenceError("Metadata storage requires an ordinary, unlinked file.")
        if os.name == "posix" and info.st_mode & 0o077:
            raise PersistenceError("Metadata storage requires owner-only file permissions.")
        for suffix in ("-journal", "-wal", "-shm"):
            companion = Path(str(self._path) + suffix)
            try:
                companion_info = companion.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(companion_info.st_mode) or companion_info.st_nlink > 1:
                raise PersistenceError("Metadata storage has an unsupported companion file.")
        return info.st_dev, info.st_ino

    def _connect(self) -> _TransactionConnection:
        connection: _TransactionConnection | None = None
        try:
            if self._validate_file() != self._file_identity:
                raise PersistenceError("The metadata database changed identity.")
            connection = sqlite3.connect(
                self._path,
                timeout=self._busy_timeout_ms / 1000,
                isolation_level=None,
                factory=_TransactionConnection,
            )
            connection.database_path = self._path
            connection.immediate_transaction = False
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
            # This setting governs SQLite commits. It does not synchronize
            # separately published payload files or establish host durability.
            connection.execute("PRAGMA synchronous = FULL")
            # SQL is application-owned, but a tampered schema must not turn
            # ordinary data access into evaluation of unsafe schema expressions.
            connection.execute("PRAGMA trusted_schema = OFF")
            return connection
        except PersistenceError:
            if connection is not None:
                connection.close()
            raise
        except (OSError, sqlite3.Error) as error:
            if connection is not None:
                connection.close()
            raise PersistenceError("The metadata database could not be opened.") from error

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        """Commit on success, roll back on every exception, and always close.

        The caller must not commit, roll back, or keep the connection after this
        context. With immediate=False, SQLite begins a deferred transaction and
        establishes its snapshot on the first read. This mode is not an enforced
        read-only connection and cannot authorize a durable publication decision.
        """
        if type(immediate) is not bool:
            raise PersistenceError("Invalid transaction mode.", code="invalid_database_configuration")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            connection.immediate_transaction = immediate
            yield connection
            connection.commit()
        except BaseException as error:
            if connection.in_transaction:
                connection.rollback()
            if isinstance(error, sqlite3.Error):
                raise PersistenceError("The metadata transaction could not be completed.") from error
            raise
        finally:
            connection.close()

    def validate_connection(self, connection: sqlite3.Connection, *, immediate: bool = False) -> None:
        """Require an active transaction issued by this database abstraction.

        Connections from another SQLiteDatabase instance for the same path are
        valid. An independently opened sqlite3 connection is not a supported
        authorization boundary because its transaction mode is unverifiable.
        """
        try:
            valid = (
                isinstance(connection, _TransactionConnection)
                and connection.database_path == self._path
                and connection.in_transaction
                and (not immediate or connection.immediate_transaction)
            )
        except sqlite3.Error:
            valid = False
        if not valid:
            raise PersistenceError("An active transaction from the same metadata database is required.", code="metadata_transaction_required")

    def initialize_schema(self, component: str, version: int, statements: Sequence[str]) -> None:
        """Install a component's first schema or require an exact existing version.

        Each statement must be a single, application-owned SQL statement. This
        API deliberately does not migrate existing schemas: migrations require
        a separate backup-aware contract and must never silently reinterpret
        another version. Initialization is serialized across service processes.
        """
        if (not isinstance(component, str) or _COMPONENT.fullmatch(component) is None
                or type(version) is not int or not 1 <= version <= 2**31 - 1
                or isinstance(statements, (str, bytes)) or not isinstance(statements, Sequence)
                or not statements or any(not isinstance(value, str) or not value.strip() for value in statements)):
            raise PersistenceError("Invalid component schema configuration.", code="invalid_database_configuration")
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT version FROM km_schema_versions WHERE component = ?", (component,)
            ).fetchone()
            if existing is not None:
                if existing["version"] != version:
                    raise PersistenceError("The component schema version is unsupported.", code="unsupported_database_schema")
                return
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO km_schema_versions (component, version) VALUES (?, ?)", (component, version)
            )
