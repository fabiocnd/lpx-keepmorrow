"""Owned generation metadata without opening preserved content during listing.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import nullcontext
from pathlib import Path
import time
import sqlite3

from ..access.models import AccessDenied, Principal, validate_token
from ..persistence import SQLiteDatabase
from .configuration import Resource


class ResourceRegistry:
    """Resolve operator registrations and immutable operation outputs separately.

    The database records opaque managed output IDs. External paths remain in
    operator-owned configuration. Neither listing nor resolving establishes
    integrity; the application verifies a generation after obtaining consent.
    """

    def __init__(self, database: SQLiteDatabase, output_root: Path, configured: Iterable[Resource]) -> None:
        self.database = database
        self.output_root = output_root
        self._configured = {item.resource_id: item for item in configured}
        database.initialize_schema("resources", 1, [
            "CREATE TABLE km_resources (resource_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, "
            "generation TEXT NOT NULL, kind TEXT NOT NULL, operation_id TEXT NOT NULL UNIQUE, "
            "created_at INTEGER NOT NULL, expires_at INTEGER, stored_bytes INTEGER NOT NULL CHECK(stored_bytes >= 0))",
            "CREATE INDEX km_resources_owner ON km_resources(principal_id, resource_id)",
        ])

    def register_output(
        self, principal_id: str, *, output_id: str, generation: str, kind: str,
        operation_id: str, expires_at: int | None, stored_bytes: int,
    ) -> Resource:
        resource = Resource(output_id, generation, principal_id, self.output_root / output_id, kind)
        validate_token(operation_id)
        if type(stored_bytes) is not int or not 0 <= stored_bytes <= 2**63 - 1:
            raise AccessDenied()
        if output_id in self._configured:
            raise AccessDenied()
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM km_resources WHERE resource_id = ?", (output_id,)).fetchone()
            expected = (principal_id, generation, kind, operation_id, expires_at, stored_bytes)
            if row is None:
                connection.execute(
                    "INSERT INTO km_resources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (output_id, *expected[:4], int(time.time()), expires_at, stored_bytes),
                )
            elif tuple(row[name] for name in ("principal_id", "generation", "kind", "operation_id", "expires_at", "stored_bytes")) != expected:
                raise AccessDenied()
        return resource

    def resolve(self, principal: Principal, resource_id: str, generation: str) -> Resource:
        validate_token(resource_id)
        configured = self._configured.get(resource_id)
        if configured is not None:
            if configured.principal_id != principal.principal_id or configured.generation != generation:
                raise AccessDenied()
            return configured
        with self.database.transaction(immediate=False) as connection:
            row = connection.execute(
                "SELECT * FROM km_resources WHERE resource_id = ? AND principal_id = ? AND generation = ?",
                (resource_id, principal.principal_id, generation),
            ).fetchone()
        if row is None or (row["expires_at"] is not None and int(time.time()) >= row["expires_at"]):
            raise AccessDenied()
        return Resource(resource_id, generation, principal.principal_id, self.output_root / resource_id, row["kind"])

    def list_owned(self, principal: Principal, *, offset: int = 0, limit: int = 50) -> list[dict[str, object]]:
        if type(offset) is not int or not 0 <= offset <= 100_000 or type(limit) is not int or not 1 <= limit <= 50:
            raise AccessDenied()
        # At most 256 configured entries are admitted. SQL applies the managed
        # output bound before materializing rows; source titles are never read.
        configured = [
            {"resource_id": item.resource_id, "generation": item.generation, "kind": item.kind}
            for item in self._configured.values() if item.principal_id == principal.principal_id
        ]
        configured.sort(key=lambda item: str(item["resource_id"]))
        if offset < len(configured):
            result = configured[offset:offset + limit]
            remaining = limit - len(result)
            managed_offset = 0
        else:
            result, remaining, managed_offset = [], limit, offset - len(configured)
        if remaining:
            with self.database.transaction(immediate=False) as connection:
                rows = connection.execute(
                    "SELECT resource_id, generation, kind FROM km_resources WHERE principal_id = ? "
                    "AND (expires_at IS NULL OR expires_at > ?) ORDER BY resource_id LIMIT ? OFFSET ?",
                    (principal.principal_id, int(time.time()), remaining, managed_offset),
                ).fetchall()
            result.extend(dict(row) for row in rows)
        return result

    def origin_operation(self, resource_id: str, connection: sqlite3.Connection | None = None) -> str | None:
        if connection is not None:
            self.database.validate_connection(connection)
        with (nullcontext(connection) if connection is not None else self.database.transaction(immediate=False)) as current:
            row = current.execute("SELECT operation_id FROM km_resources WHERE resource_id = ?", (resource_id,)).fetchone()
        return row["operation_id"] if row else None

    def stored_bytes(self, connection: sqlite3.Connection) -> int:
        self.database.validate_connection(connection)
        return connection.execute("SELECT COALESCE(SUM(stored_bytes), 0) FROM km_resources").fetchone()[0]

    def expired_packages(self, *, limit: int = 20) -> list[dict[str, object]]:
        with self.database.transaction(immediate=False) as connection:
            rows = connection.execute(
                "SELECT resource_id, generation FROM km_resources WHERE kind = 'package' "
                "AND expires_at <= ? AND stored_bytes > 0 LIMIT ?", (int(time.time()), limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_removed(self, resource_id: str, generation: str) -> None:
        with self.database.transaction() as connection:
            connection.execute("UPDATE km_resources SET stored_bytes = 0 WHERE resource_id = ? AND generation = ? "
                               "AND kind = 'package' AND expires_at <= ?", (resource_id, generation, int(time.time())))
