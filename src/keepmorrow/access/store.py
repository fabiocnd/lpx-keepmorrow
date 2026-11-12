"""Persistent grants and independently recorded human acceptance.

This module is an internal capability boundary, not an authenticated HTTP API.
Only trusted server code may create grants or record a verified human action.
Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
import sqlite3
import time
from uuid import uuid4

from ..persistence import SQLiteDatabase
from .models import (
    MAX_ACTIONS,
    AccessDecision,
    AccessDenied,
    AccessError,
    AuthorizedGrant,
    Grant,
    HumanAcceptance,
    PolicySet,
    Principal,
    validate_action,
    validate_actions,
    validate_timestamp,
    validate_token,
    validate_version,
)

_SCHEMA = (
    """CREATE TABLE km_access_grants (
        grant_id TEXT PRIMARY KEY NOT NULL,
        principal_id TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        generation TEXT NOT NULL,
        purpose TEXT NOT NULL,
        recipient TEXT NOT NULL,
        grant_version INTEGER NOT NULL CHECK(grant_version >= 1),
        created_at INTEGER NOT NULL CHECK(created_at >= 0),
        expires_at INTEGER NOT NULL CHECK(expires_at > created_at),
        revoked_at INTEGER CHECK(revoked_at >= created_at)
    )""",
    """CREATE INDEX km_access_grants_scope ON km_access_grants
        (principal_id, resource_id, generation, grant_id)""",
    """CREATE INDEX km_access_grants_owner ON km_access_grants
        (principal_id, grant_id)""",
    """CREATE TABLE km_access_grant_actions (
        grant_id TEXT NOT NULL REFERENCES km_access_grants(grant_id),
        action TEXT NOT NULL,
        PRIMARY KEY (grant_id, action)
    )""",
    """CREATE TABLE km_access_acceptances (
        acceptance_id TEXT PRIMARY KEY NOT NULL,
        grant_id TEXT NOT NULL REFERENCES km_access_grants(grant_id),
        principal_id TEXT NOT NULL,
        grant_version INTEGER NOT NULL CHECK(grant_version >= 1),
        terms_version TEXT NOT NULL,
        terms_sha256 TEXT NOT NULL CHECK(length(terms_sha256) = 64),
        privacy_version TEXT NOT NULL,
        privacy_sha256 TEXT NOT NULL CHECK(length(privacy_sha256) = 64),
        interaction_id TEXT UNIQUE NOT NULL,
        accepted_at INTEGER NOT NULL CHECK(accepted_at >= 0),
        expires_at INTEGER NOT NULL CHECK(expires_at > accepted_at),
        revoked_at INTEGER CHECK(revoked_at >= accepted_at)
    )""",
    """CREATE INDEX km_access_acceptances_grant ON km_access_acceptances
        (grant_id, principal_id, grant_version, accepted_at)""",
    """CREATE TABLE km_access_acceptance_actions (
        acceptance_id TEXT NOT NULL REFERENCES km_access_acceptances(acceptance_id),
        action TEXT NOT NULL,
        PRIMARY KEY (acceptance_id, action)
    )""",
)

_CURRENT_ACCEPTANCE = """
    a.principal_id = g.principal_id AND a.grant_version = g.grant_version
    AND a.revoked_at IS NULL AND a.accepted_at <= ? AND a.expires_at > ?
    AND a.terms_version = ? AND a.terms_sha256 = ?
    AND a.privacy_version = ? AND a.privacy_sha256 = ?
"""


def _utc_seconds() -> int:
    return int(time.time())


class AccessStore:
    """Authorize exact scopes without inspecting collection or artifact content.

    All workers for a database must use the same current PolicySet. Replacing
    those policies requires constructing a store with the new immutable value;
    existing receipts remain evidence but cannot authorize the changed policy.

    Grant creation establishes administrative permission only. accept_grant is
    reserved for the authenticated, CSRF-protected human interaction boundary.
    Never expose that method as a model tool or use a model-supplied Boolean as
    evidence that the interaction occurred.

    A supplied connection joins the caller's active transaction on this database.
    Otherwise, each method owns and closes its transaction. This distinction
    allows grant checks and publication decisions to share one commit boundary.
    """

    def __init__(
        self,
        database: SQLiteDatabase,
        policies: PolicySet,
        *,
        clock: Callable[[], int] = _utc_seconds,
        max_live_grants_per_principal: int = 256,
    ) -> None:
        if not isinstance(database, SQLiteDatabase) or not isinstance(policies, PolicySet) or not callable(clock):
            raise AccessError("Invalid access-store configuration.")
        self.database = database
        if type(max_live_grants_per_principal) is not int or not 1 <= max_live_grants_per_principal <= 1024:
            raise AccessError("The active grant limit is outside the supported range.")
        self.max_live_grants_per_principal = max_live_grants_per_principal
        self._policies = policies
        self._clock = clock
        database.initialize_schema("access", 1, _SCHEMA)

    @property
    def policies(self) -> PolicySet:
        return self._policies

    def _now(self) -> int:
        return validate_timestamp(self._clock())

    @staticmethod
    def _principal(principal: Principal) -> str:
        if not isinstance(principal, Principal):
            raise AccessError("A principal from the authenticated boundary is required.")
        return principal.principal_id

    def _policy_parameters(self, now: int) -> tuple[int, int, str, str, str, str]:
        return (
            now, now, self.policies.terms_version, self.policies.terms_sha256,
            self.policies.privacy_version, self.policies.privacy_sha256,
        )

    @contextmanager
    def _connection(
        self, connection: sqlite3.Connection | None, *, write: bool = False
    ) -> Iterator[sqlite3.Connection]:
        if connection is not None:
            self.database.validate_connection(connection, immediate=write)
            yield connection
        else:
            with self.database.transaction(immediate=write) as owned:
                yield owned

    @staticmethod
    def _grant(connection: sqlite3.Connection, row: sqlite3.Row) -> Grant:
        actions = frozenset(value[0] for value in connection.execute(
            "SELECT action FROM km_access_grant_actions WHERE grant_id = ? ORDER BY action",
            (row["grant_id"],),
        ))
        return Grant(
            grant_id=row["grant_id"], principal_id=row["principal_id"],
            resource_id=row["resource_id"], generation=row["generation"], actions=actions,
            purpose=row["purpose"], recipient=row["recipient"], grant_version=row["grant_version"],
            created_at=row["created_at"], expires_at=row["expires_at"], revoked_at=row["revoked_at"],
        )

    def create_grant(
        self,
        principal: Principal,
        *,
        resource_id: str,
        generation: str,
        actions: Iterable[str],
        purpose: str,
        recipient: str,
        expires_at: int,
        connection: sqlite3.Connection | None = None,
    ) -> Grant:
        """Create a new administrative scope without creating human acceptance.

        The caller owns resource eligibility and the server's purpose/recipient
        vocabulary. These bounded identifiers must never be paths, credentials,
        or arbitrary source content. Changing scope creates a new grant; this
        API does not silently broaden or reactivate an existing grant.
        """
        principal_id = self._principal(principal)
        for value in (resource_id, generation, purpose, recipient):
            validate_token(value)
        permitted = validate_actions(actions)
        validate_timestamp(expires_at)
        with self._connection(connection, write=True) as current:
            now = self._now()
            if expires_at <= now:
                raise AccessError("A grant must have a future expiry.")
            active = current.execute(
                "SELECT COUNT(*) FROM km_access_grants WHERE principal_id = ? "
                "AND revoked_at IS NULL AND expires_at > ?", (principal_id, now),
            ).fetchone()[0]
            if active >= self.max_live_grants_per_principal:
                raise AccessError("The principal has reached the active grant limit.")
            grant = Grant(
                grant_id="grant_" + uuid4().hex, principal_id=principal_id,
                resource_id=resource_id, generation=generation, actions=permitted,
                purpose=purpose, recipient=recipient, grant_version=1,
                created_at=now, expires_at=expires_at, revoked_at=None,
            )
            current.execute(
                """INSERT INTO km_access_grants
                    (grant_id, principal_id, resource_id, generation, purpose, recipient,
                     grant_version, created_at, expires_at, revoked_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                (grant.grant_id, principal_id, resource_id, generation, purpose, recipient, 1, now, expires_at),
            )
            current.executemany(
                "INSERT INTO km_access_grant_actions (grant_id, action) VALUES (?, ?)",
                ((grant.grant_id, action) for action in sorted(permitted)),
            )
            return grant

    def get_grant(
        self, principal: Principal, *, grant_id: str, connection: sqlite3.Connection | None = None
    ) -> Grant:
        """Return the owner's metadata for consent presentation, including expiry.

        This does not authorize source access. An unknown or foreign grant has
        the same error outcome and exposes no resource existence information.
        """
        principal_id = self._principal(principal)
        validate_token(grant_id)
        with self._connection(connection) as current:
            row = current.execute(
                "SELECT * FROM km_access_grants WHERE grant_id = ? AND principal_id = ?",
                (grant_id, principal_id),
            ).fetchone()
            if row is None:
                raise AccessDenied()
            return self._grant(current, row)

    def accept_grant(
        self,
        principal: Principal,
        *,
        grant_id: str,
        expected_grant_version: int,
        policies: PolicySet,
        actions: Iterable[str],
        interaction_id: str,
        expires_at: int | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> HumanAcceptance:
        """Record a separately verified human action for a selected scope.

        The trusted HTTP boundary must first authenticate the requester, validate
        the session and CSRF challenge, display these exact policy bytes and scope,
        and verify the deliberate submission. interaction_id is that boundary's
        single-use opaque interaction reference, not proof by itself. This
        method enforces replay, scope, version, expiry, and policy consistency;
        it cannot authenticate a browser or infer a person's intent.
        """
        self._principal(principal)
        validate_token(grant_id)
        validate_version(expected_grant_version)
        validate_token(interaction_id)
        selected = validate_actions(actions)
        if not isinstance(policies, PolicySet) or policies != self.policies:
            raise AccessDenied()
        if expires_at is not None:
            validate_timestamp(expires_at)
        with self._connection(connection, write=True) as current:
            now = self._now()
            grant = self.get_grant(principal, grant_id=grant_id, connection=current)
            if (grant.revoked_at is not None or not grant.created_at <= now < grant.expires_at
                    or grant.grant_version != expected_grant_version or not selected <= grant.actions):
                raise AccessDenied()
            expiry = grant.expires_at if expires_at is None else expires_at
            if not now < expiry <= grant.expires_at:
                raise AccessError("Acceptance expiry must fit within the selected grant.")
            receipt = HumanAcceptance(
                acceptance_id="acceptance_" + uuid4().hex, principal_id=principal.principal_id,
                grant_id=grant.grant_id, grant_version=grant.grant_version,
                resource_id=grant.resource_id, generation=grant.generation, actions=selected,
                purpose=grant.purpose, recipient=grant.recipient, policies=policies,
                interaction_id=interaction_id, accepted_at=now, expires_at=expiry, revoked_at=None,
            )
            try:
                current.execute(
                    """INSERT INTO km_access_acceptances
                        (acceptance_id, grant_id, principal_id, grant_version, terms_version,
                         terms_sha256, privacy_version, privacy_sha256, interaction_id,
                         accepted_at, expires_at, revoked_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                    (receipt.acceptance_id, grant_id, principal.principal_id, grant.grant_version,
                     policies.terms_version, policies.terms_sha256, policies.privacy_version,
                     policies.privacy_sha256, interaction_id, now, expiry),
                )
            except sqlite3.IntegrityError as error:
                raise AccessError("The acceptance interaction is no longer available.") from error
            current.executemany(
                "INSERT INTO km_access_acceptance_actions (acceptance_id, action) VALUES (?, ?)",
                ((receipt.acceptance_id, action) for action in sorted(selected)),
            )
            return receipt

    def require_access(
        self,
        principal: Principal,
        *,
        resource_id: str,
        generation: str,
        action: str,
        grant_id: str | None = None,
        expected_grant_version: int | None = None,
        expected_acceptance_id: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> AccessDecision:
        """Require a live, currently accepted grant for one exact action.

        The result is a point-in-time decision. Later content delivery requires
        another check. To fence a journal publication against revocation, call
        authorize_publication inside the journal's BEGIN IMMEDIATE transaction
        and persist the decision before that same transaction commits.
        """
        principal_id = self._principal(principal)
        validate_token(resource_id)
        validate_token(generation)
        validate_action(action)
        conditions: list[str] = []
        extra: list[str | int] = []
        if grant_id is not None:
            validate_token(grant_id)
            conditions.append("g.grant_id = ?")
            extra.append(grant_id)
        if expected_grant_version is not None:
            validate_version(expected_grant_version)
            if grant_id is None:
                raise AccessError("Grant-version fencing requires an explicit grant.")
            conditions.append("g.grant_version = ?")
            extra.append(expected_grant_version)
        if expected_acceptance_id is not None:
            validate_token(expected_acceptance_id)
            conditions.append("a.acceptance_id = ?")
            extra.append(expected_acceptance_id)
        with self._connection(connection) as current:
            now = self._now()
            row = current.execute(
                """SELECT g.grant_id, g.grant_version, a.acceptance_id
                    FROM km_access_grants AS g
                    JOIN km_access_grant_actions AS ga ON ga.grant_id = g.grant_id
                    JOIN km_access_acceptances AS a ON a.grant_id = g.grant_id
                    JOIN km_access_acceptance_actions AS aa
                      ON aa.acceptance_id = a.acceptance_id AND aa.action = ga.action
                    WHERE g.principal_id = ? AND g.resource_id = ? AND g.generation = ?
                      AND ga.action = ? AND g.revoked_at IS NULL
                      AND g.created_at <= ? AND g.expires_at > ? AND """
                + _CURRENT_ACCEPTANCE
                + (" AND " + " AND ".join(conditions) if conditions else "")
                + " ORDER BY a.accepted_at DESC, a.acceptance_id LIMIT 1",
                (principal_id, resource_id, generation, action, now, now,
                 *self._policy_parameters(now), *extra),
            ).fetchone()
            if row is None:
                raise AccessDenied()
            return AccessDecision(
                grant_id=row["grant_id"], grant_version=row["grant_version"],
                acceptance_id=row["acceptance_id"], principal_id=principal_id,
                resource_id=resource_id, generation=generation, action=action, authorized_at=now,
            )

    def authorize_publication(
        self,
        principal: Principal,
        *,
        resource_id: str,
        generation: str,
        action: str,
        grant_id: str,
        expected_grant_version: int,
        connection: sqlite3.Connection,
        expected_acceptance_id: str | None = None,
    ) -> AccessDecision:
        """Fence a durable decision against revocation in the caller's write transaction.

        A revocation committed first prevents authorization. If this transaction
        commits the journal decision first, private publication may complete;
        revocation still prevents a new delivery. This method neither publishes
        files nor makes an independently committed decision durable for a job.
        """
        self.database.validate_connection(connection, immediate=True)
        return self.require_access(
            principal, resource_id=resource_id, generation=generation, action=action,
            grant_id=grant_id, expected_grant_version=expected_grant_version,
            expected_acceptance_id=expected_acceptance_id, connection=connection,
        )

    def list_grants(
        self,
        principal: Principal,
        *,
        action: str | None = None,
        limit: int = 100,
        after_grant_id: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> tuple[AuthorizedGrant, ...]:
        """List only current accepted scopes, ordered by grant ID, without content I/O.

        At most 100 grants and 32 actions per grant enter application memory.
        Cursor filtering is always subordinate to principal filtering. When
        action is supplied, the returned action sets contain only that action.
        Expired, stale, unaccepted, and revoked scopes are omitted.
        """
        principal_id = self._principal(principal)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise AccessError("The grant-list limit must be between 1 and 100.")
        conditions: list[str] = []
        extra: list[str] = []
        if action is not None:
            validate_action(action)
            conditions.append("aa.action = ?")
            extra.append(action)
        if after_grant_id is not None:
            validate_token(after_grant_id)
            conditions.append("g.grant_id > ?")
            extra.append(after_grant_id)
        with self._connection(connection) as current:
            now = self._now()
            rows = current.execute(
                """SELECT DISTINCT g.grant_id, g.grant_version, g.resource_id,
                           g.generation, g.purpose, g.recipient, g.expires_at, aa.action
                    FROM km_access_grants AS g
                    JOIN km_access_acceptances AS a ON a.grant_id = g.grant_id
                    JOIN km_access_acceptance_actions AS aa ON aa.acceptance_id = a.acceptance_id
                    JOIN km_access_grant_actions AS ga ON ga.grant_id = g.grant_id AND ga.action = aa.action
                    WHERE g.principal_id = ? AND g.revoked_at IS NULL
                      AND g.created_at <= ? AND g.expires_at > ? AND """
                + _CURRENT_ACCEPTANCE
                + (" AND " + " AND ".join(conditions) if conditions else "")
                + " ORDER BY g.grant_id, aa.action LIMIT ?",
                (principal_id, now, now, *self._policy_parameters(now), *extra, limit * MAX_ACTIONS),
            )
            grouped: dict[str, tuple[sqlite3.Row, set[str]]] = {}
            for row in rows:
                identifier = row["grant_id"]
                if identifier not in grouped:
                    if len(grouped) == limit:
                        break
                    grouped[identifier] = row, set()
                grouped[identifier][1].add(row["action"])
            return tuple(
                AuthorizedGrant(
                    grant_id=row["grant_id"], grant_version=row["grant_version"],
                    resource_id=row["resource_id"], generation=row["generation"], actions=frozenset(actions),
                    purpose=row["purpose"], recipient=row["recipient"], expires_at=row["expires_at"],
                )
                for row, actions in grouped.values()
            )

    def revoke_grant(
        self,
        principal: Principal,
        *,
        grant_id: str,
        expected_grant_version: int | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> Grant:
        """Revoke the owner's grant and all its receipts in one write transaction.

        The first revocation advances its version. Repeating a revocation without
        an expected version is idempotent. Scope cannot be restored through a
        new acceptance; renewed permission requires a new administrative grant.
        Historical records remain retained; this method does not delete content.
        """
        self._principal(principal)
        validate_token(grant_id)
        if expected_grant_version is not None:
            validate_version(expected_grant_version)
        with self._connection(connection, write=True) as current:
            grant = self.get_grant(principal, grant_id=grant_id, connection=current)
            if expected_grant_version is not None and grant.grant_version != expected_grant_version:
                raise AccessDenied()
            if grant.revoked_at is None:
                now = self._now()
                if now < grant.created_at:
                    raise AccessError("The current clock precedes the grant record.")
                current.execute(
                    """UPDATE km_access_grants SET revoked_at = ?, grant_version = grant_version + 1
                        WHERE grant_id = ? AND principal_id = ?""",
                    (now, grant_id, principal.principal_id),
                )
                current.execute(
                    """UPDATE km_access_acceptances SET revoked_at = MAX(accepted_at, ?)
                        WHERE grant_id = ? AND revoked_at IS NULL""", (now, grant_id),
                )
            return self.get_grant(principal, grant_id=grant_id, connection=current)

    def revoke_acceptance(
        self, principal: Principal, *, acceptance_id: str, connection: sqlite3.Connection | None = None
    ) -> None:
        """Withdraw one receipt while retaining its historical metadata.

        Other current receipts can still authorize overlapping actions. Revoking
        the administrative grant withdraws every receipt attached to that grant.
        """
        principal_id = self._principal(principal)
        validate_token(acceptance_id)
        with self._connection(connection, write=True) as current:
            row = current.execute(
                """SELECT accepted_at, revoked_at FROM km_access_acceptances
                    WHERE acceptance_id = ? AND principal_id = ?""", (acceptance_id, principal_id),
            ).fetchone()
            if row is None:
                raise AccessDenied()
            if row["revoked_at"] is None:
                now = self._now()
                if now < row["accepted_at"]:
                    raise AccessError("The current clock precedes the acceptance record.")
                current.execute(
                    "UPDATE km_access_acceptances SET revoked_at = ? WHERE acceptance_id = ?",
                    (now, acceptance_id),
                )
