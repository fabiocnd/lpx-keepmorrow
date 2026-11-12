"""Browser sessions and single-use gestures, independent of MCP tool arguments.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from contextlib import nullcontext
import hashlib
import hmac
import secrets
import re
import sqlite3
import time

from ...access.models import AccessDenied, validate_token
from ...persistence import SQLiteDatabase


@dataclass(frozen=True, slots=True)
class HumanSession:
    """Validated session metadata; ``session_id`` is a digest, not a cookie."""

    session_id: str
    principal_id: str
    expires_at: int


class HumanSessions:
    """Store only session digests and short-lived decision challenges.

    Browser authentication creates sessions. A bearer token alone cannot invoke
    consent or review routes. CSRF values are domain-separated hashes of the
    opaque cookie; disclosing one does not disclose that cookie.
    """

    def __init__(self, database: SQLiteDatabase, *, clock: Callable[[], float] = time.time) -> None:
        self.database, self.clock = database, clock
        database.initialize_schema("human_sessions", 1, [
            "CREATE TABLE km_human_sessions (session_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL, "
            "expires_at INTEGER NOT NULL)",
            "CREATE TABLE km_human_challenges (challenge_id TEXT PRIMARY KEY, session_id TEXT NOT NULL "
            "REFERENCES km_human_sessions(session_id) ON DELETE CASCADE, kind TEXT NOT NULL, "
            "object_id TEXT NOT NULL, document_digest TEXT NOT NULL, expires_at INTEGER NOT NULL, "
            "consumed_at INTEGER)",
            "CREATE INDEX km_human_challenges_session ON km_human_challenges(session_id)",
        ])
        database.initialize_schema("human_acceptance_context", 1, [
            "CREATE TABLE km_human_acceptance_context ("
            "acceptance_id TEXT PRIMARY KEY REFERENCES km_access_acceptances(acceptance_id), "
            "interaction_id TEXT UNIQUE NOT NULL, scope_sha256 TEXT NOT NULL CHECK(length(scope_sha256) = 64), "
            "eligibility_version TEXT NOT NULL)",
        ])

    @staticmethod
    def _digest(token: str) -> str:
        if not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{64}", token) is None:
            raise AccessDenied()
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    @staticmethod
    def csrf(token: str) -> str:
        """Derive the mutation challenge without exposing the session cookie."""
        HumanSessions._digest(token)
        return hashlib.sha256(b"lpx-keepmorrow.csrf.v1\x00" + token.encode("ascii")).hexdigest()

    def create(self, principal_id: str, *, expires_at: int) -> str:
        """Return one opaque cookie and retain only its digest and owner.

        The session expires no later than the supplied authentication deadline
        or fifteen minutes from creation. Expired sessions are removed before
        applying the global admission cap.
        """
        validate_token(principal_id)
        if type(expires_at) is not int:
            raise AccessDenied()
        token = secrets.token_hex(32)
        with self.database.transaction() as connection:
            now = int(self.clock())
            if expires_at <= now:
                raise AccessDenied()
            connection.execute("DELETE FROM km_human_sessions WHERE expires_at <= ?", (now,))
            count = connection.execute("SELECT COUNT(*) FROM km_human_sessions").fetchone()[0]
            if count >= 100:
                raise AccessDenied()
            connection.execute("INSERT INTO km_human_sessions VALUES (?, ?, ?)",
                               (self._digest(token), principal_id, min(expires_at, now + 900)))
        return token

    def require(self, token: str, *, csrf: str | None = None) -> HumanSession:
        """Resolve a live cookie and optionally verify its mutation challenge.

        Route handlers decide whether CSRF is mandatory. This check establishes
        browser identity, not permission to read content or approve an operation.
        """
        try:
            digest = self._digest(token)
            if csrf is not None and not hmac.compare_digest(self.csrf(token), csrf):
                raise AccessDenied()
        except (UnicodeError, TypeError):
            raise AccessDenied() from None
        with self.database.transaction(immediate=False) as connection:
            row = connection.execute("SELECT * FROM km_human_sessions WHERE session_id = ?", (digest,)).fetchone()
        if row is None or int(self.clock()) >= row["expires_at"]:
            raise AccessDenied()
        return HumanSession(row["session_id"], row["principal_id"], row["expires_at"])

    def challenge(self, session: HumanSession, *, kind: str, object_id: str, document_digest: str) -> str:
        """Bind a short-lived gesture to the live session and exact document.

        Revalidate the session within the insertion transaction so a stale
        in-memory session cannot create a challenge after logout or expiration.
        """
        for value in (kind, object_id, document_digest):
            validate_token(value)
        token = secrets.token_hex(32)
        with self.database.transaction() as connection:
            now = int(self.clock())
            current = connection.execute(
                "SELECT principal_id, expires_at FROM km_human_sessions WHERE session_id = ?",
                (session.session_id,),
            ).fetchone()
            if (current is None or current["principal_id"] != session.principal_id
                    or current["expires_at"] <= now or current["expires_at"] != session.expires_at):
                raise AccessDenied()
            connection.execute("DELETE FROM km_human_challenges WHERE expires_at <= ?", (now,))
            count = connection.execute("SELECT COUNT(*) FROM km_human_challenges WHERE session_id = ?",
                                       (session.session_id,)).fetchone()[0]
            if count >= 32 or session.expires_at <= now:
                raise AccessDenied()
            connection.execute("INSERT INTO km_human_challenges VALUES (?, ?, ?, ?, ?, ?, NULL)",
                               (self._digest(token), session.session_id, kind, object_id,
                                document_digest, min(session.expires_at, now + 300)))
        return token

    def consume(
        self, session: HumanSession, token: str, *, kind: str, object_id: str,
        document_digest: str, connection: sqlite3.Connection | None = None,
    ) -> str:
        """Consume one exact gesture, optionally with the acceptance transaction.

        Matching and consumption share a write transaction. A supplied connection
        must belong to this database and retain the caller's transaction so a
        failed acceptance can roll back challenge consumption with its receipt.
        """
        digest = self._digest(token)
        for value in (kind, object_id, document_digest):
            validate_token(value)
        if connection is not None:
            self.database.validate_connection(connection, immediate=True)
        with (nullcontext(connection) if connection is not None else self.database.transaction()) as current_connection:
            now = int(self.clock())
            current = current_connection.execute(
                "SELECT principal_id, expires_at FROM km_human_sessions WHERE session_id = ?",
                (session.session_id,),
            ).fetchone()
            if (current is None or current["principal_id"] != session.principal_id
                    or current["expires_at"] <= now or current["expires_at"] != session.expires_at):
                raise AccessDenied()
            changed = current_connection.execute(
                "UPDATE km_human_challenges SET consumed_at = ? WHERE challenge_id = ? AND session_id = ? "
                "AND kind = ? AND object_id = ? AND document_digest = ? AND expires_at > ? AND consumed_at IS NULL",
                (now, digest, session.session_id, kind, object_id, document_digest, now),
            ).rowcount
            if changed != 1 or session.expires_at <= now:
                raise AccessDenied()
        return "interaction_" + digest

    def end(self, token: str) -> None:
        """Remove a browser session and its ephemeral challenges.

        Durable grants and acceptance evidence have separate lifetimes; signing
        out does not rewrite those records or imply scope revocation.
        """
        with self.database.transaction() as connection:
            connection.execute("DELETE FROM km_human_sessions WHERE session_id = ?", (self._digest(token),))

    def record_acceptance_context(
        self, session: HumanSession, *, acceptance_id: str, interaction_id: str,
        scope_sha256: str, eligibility_version: str, connection: sqlite3.Connection,
    ) -> None:
        """Retain the displayed declaration digest after ephemeral challenge cleanup.

        Call after accept_grant in the same transaction as challenge consumption.
        The insert joins the consumed gesture to its exact owner's new receipt;
        arbitrary acceptance IDs cannot manufacture additional human evidence.
        """
        self.database.validate_connection(connection, immediate=True)
        for value in (acceptance_id, interaction_id, eligibility_version):
            validate_token(value)
        if not isinstance(scope_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", scope_sha256) is None:
            raise AccessDenied()
        if not interaction_id.startswith("interaction_"):
            raise AccessDenied()
        changed = connection.execute(
            "INSERT INTO km_human_acceptance_context (acceptance_id, interaction_id, scope_sha256, eligibility_version) "
            "SELECT a.acceptance_id, a.interaction_id, c.document_digest, ? "
            "FROM km_access_acceptances AS a JOIN km_human_challenges AS c "
            "ON c.object_id = a.grant_id AND c.kind = 'consent' "
            "WHERE a.acceptance_id = ? AND a.interaction_id = ? AND a.principal_id = ? "
            "AND c.challenge_id = ? AND c.session_id = ? AND c.document_digest = ? AND c.consumed_at IS NOT NULL",
            (eligibility_version, acceptance_id, interaction_id, session.principal_id,
             interaction_id.removeprefix("interaction_"), session.session_id, scope_sha256),
        ).rowcount
        if changed != 1:
            raise AccessDenied()
