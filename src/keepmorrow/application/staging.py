"""Ledger-owned operation workspaces with conservative restart cleanup.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import uuid

from ..archive.filesystem import open_regular, safe_directory
from ..archive.model import ArchiveError
from ..operations.model import OperationBusy, OperationCleanupRequired, OperationError, require_opaque_id
from ..persistence import SQLiteDatabase

_MARKER = ".keepmorrow-owner.json"
_MAX_WORKSPACES = 1024


class OperationWorkspaces:
    """Own only exact journal-identified directories, never arbitrary source paths.

    Cleanup requires both a persisted ownership record and its exact private
    marker. Missing or conflicting markers fail closed. The caller must invoke
    recover_interrupted only under exclusive worker ownership before accepting
    requests; the database check additionally refuses a live current attempt.
    Stable, operator-controlled directory ancestors remain a prerequisite.
    """

    def __init__(self, database: SQLiteDatabase, scratch_root: Path, output_root: Path) -> None:
        self.database = database
        self.scratch_root = self._private_directory(scratch_root)
        output = self._private_directory(output_root)
        if (self.scratch_root == output or self.scratch_root.is_relative_to(output)
                or output.is_relative_to(self.scratch_root)
                or self.scratch_root.stat().st_dev != output.stat().st_dev):
            raise OperationError("Operation workspaces and outputs require separate directories on one filesystem.")
        database.initialize_schema("operation_workspaces", 1, [
            "CREATE TABLE km_operation_workspaces ("
            "operation_id TEXT PRIMARY KEY NOT NULL REFERENCES km_operations(operation_id), "
            "output_id TEXT UNIQUE NOT NULL, ownership_token TEXT NOT NULL)",
        ])

    @staticmethod
    def _private_directory(path: Path) -> Path:
        if not isinstance(path, Path) or not path.is_absolute():
            raise OperationError("Workspace roots require absolute operator-selected paths.")
        root = safe_directory(path)
        if os.name == "posix" and root.stat().st_mode & 0o077:
            raise OperationError("Workspace roots require owner-only permissions.")
        return root

    @staticmethod
    def _marker_bytes(row: sqlite3.Row | dict[str, str]) -> bytes:
        return json.dumps({
            "format": "lpx-keepmorrow.operation-workspace", "version": 1,
            "operation_id": row["operation_id"], "output_id": row["output_id"],
            "ownership_token": row["ownership_token"],
        }, sort_keys=True, separators=(",", ":")).encode("ascii")

    def create(self, operation_id: str, output_id: str) -> Path:
        """Create one private workspace after recording its journal binding.

        Metadata and directory creation are separate steps. An interrupted or
        ambiguous setup retains evidence for startup recovery or operator review.
        """
        require_opaque_id(operation_id)
        require_opaque_id(output_id)
        directory = self.scratch_root / output_id
        record = {
            "operation_id": operation_id, "output_id": output_id, "ownership_token": uuid.uuid4().hex,
        }
        with self.database.transaction() as connection:
            operation = connection.execute(
                "SELECT output_id FROM km_operations WHERE operation_id = ?", (operation_id,),
            ).fetchone()
            if operation is None or operation["output_id"] != output_id:
                raise OperationError("The workspace does not identify a recorded operation output.")
            existing = connection.execute(
                "SELECT 1 FROM km_operation_workspaces WHERE operation_id = ? OR output_id = ?",
                (operation_id, output_id),
            ).fetchone()
            if existing is not None:
                raise OperationCleanupRequired("The operation workspace requires completion or startup recovery.")
            if os.path.lexists(directory):
                raise OperationCleanupRequired("An unrecognized directory occupies the operation workspace.")
            connection.execute(
                "INSERT INTO km_operation_workspaces VALUES(?, ?, ?)",
                (operation_id, output_id, record["ownership_token"]),
            )
        created_identity: tuple[int, int] | None = None
        try:
            directory.mkdir(mode=0o700)
            identity = directory.lstat()
            created_identity = identity.st_dev, identity.st_ino
            descriptor = os.open(
                directory / _MARKER, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600,
            )
            with os.fdopen(descriptor, "wb") as marker:
                marker.write(self._marker_bytes(record))
            return directory
        except OSError as error:
            # This call has not exposed the directory to an executor yet. Only
            # the directory identity created by this call can be rolled back.
            if created_identity is not None:
                try:
                    current = directory.lstat()
                    if (current.st_dev, current.st_ino) == created_identity and stat.S_ISDIR(current.st_mode):
                        shutil.rmtree(directory)
                except OSError:
                    pass
            if not os.path.lexists(directory):
                with self.database.transaction() as connection:
                    connection.execute(
                        "DELETE FROM km_operation_workspaces WHERE operation_id = ? AND ownership_token = ?",
                        (operation_id, record["ownership_token"]),
                    )
            if os.path.lexists(directory):
                raise OperationCleanupRequired("The operation workspace requires ownership review before reuse.") from error
            raise OperationError("The operation workspace could not be created safely.") from error

    @contextmanager
    def workspace(self, operation_id: str, output_id: str) -> Iterator[Path]:
        """Retain ownership through execution, verification, and handled cleanup.

        Classified filesystem and ownership failures propagate as
        OperationCleanupRequired, causing the worker to retain its reservation.
        Metadata transaction errors propagate separately.
        """
        directory = self.create(operation_id, output_id)
        try:
            yield directory
        finally:
            self.discard(operation_id, output_id)

    def discard(self, operation_id: str, output_id: str) -> None:
        """Delete only a matching owned workspace after its I/O has stopped."""
        require_opaque_id(operation_id)
        require_opaque_id(output_id)
        with self.database.transaction(immediate=False) as connection:
            row = connection.execute(
                "SELECT w.* FROM km_operation_workspaces AS w JOIN km_operations AS o "
                "ON o.operation_id = w.operation_id AND o.output_id = w.output_id "
                "WHERE w.operation_id = ? AND w.output_id = ?", (operation_id, output_id),
            ).fetchone()
        if row is None:
            raise OperationCleanupRequired("The operation workspace has no matching ownership record.")
        directory = self.scratch_root / output_id
        try:
            if os.path.lexists(directory):
                self._private_directory(directory)
                with open_regular(directory / _MARKER) as marker:
                    value = marker.read(1025)
                if value != self._marker_bytes(row):
                    raise OperationCleanupRequired("The operation workspace ownership marker does not match.")
                shutil.rmtree(directory)
        except (OSError, ArchiveError, OperationError) as error:
            raise OperationCleanupRequired("The operation workspace could not be removed safely.") from error
        with self.database.transaction() as connection:
            connection.execute(
                "DELETE FROM km_operation_workspaces WHERE operation_id = ? AND ownership_token = ?",
                (operation_id, row["ownership_token"]),
            )

    def recover_interrupted(self) -> int:
        """Remove proven orphan workspaces before any new application admission.

        A crash between directory creation and marker creation requires operator
        review. A crash before directory creation is safely reconciled as absent.
        Unknown directories are neither enumerated nor deleted by this method.
        """
        with self.database.transaction(immediate=False) as connection:
            worker = connection.execute("SELECT worker_token FROM km_operation_worker WHERE singleton = 1").fetchone()
            if worker is None or worker["worker_token"] is None:
                raise OperationError("Workspace recovery requires exclusive worker startup ownership.")
            active = connection.execute(
                "SELECT 1 FROM km_operations AS o JOIN km_operation_attempts AS a "
                "ON a.operation_id = o.operation_id AND a.attempt_number = o.attempt_number "
                "JOIN km_operation_worker AS w ON w.epoch = a.worker_epoch AND w.worker_token = a.worker_token "
                "WHERE o.worker_released = 0 LIMIT 1"
            ).fetchone()
            if active is not None:
                raise OperationBusy("A live executor still owns operation workspaces.")
            rows = connection.execute(
                "SELECT operation_id, output_id FROM km_operation_workspaces ORDER BY operation_id LIMIT ?",
                (_MAX_WORKSPACES + 1,),
            ).fetchall()
        if len(rows) > _MAX_WORKSPACES:
            raise OperationError("The workspace recovery set exceeds its supported bound.")
        for row in rows:
            self.discard(row["operation_id"], row["output_id"])
        return len(rows)
