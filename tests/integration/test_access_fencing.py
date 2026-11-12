"""Prove both serialized orders of revocation and durable publication authorization."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

from keepmorrow.access import AccessDenied, AccessStore, PolicySet, Principal
from keepmorrow.persistence import SQLiteDatabase


class PublicationFencingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database = SQLiteDatabase(Path(self.temporary.name) / "control.sqlite3")
        self.database.initialize_schema("access_fencing_test", 1, (
            "CREATE TABLE test_publication_decisions (grant_id TEXT, version INTEGER, acceptance_id TEXT)",
        ))
        self.now = 1_800_000_000
        self.store = AccessStore(
            self.database, PolicySet("test-terms.1", "a" * 64, "test-privacy.1", "b" * 64),
            clock=lambda: self.now,
        )
        self.principal = Principal("https://identity.example.test", "synthetic-owner")
        self.grant = self.store.create_grant(
            self.principal, resource_id="collection", generation="c" * 64,
            actions=("recover", "download"), purpose="selected_recovery", recipient="chatgpt",
            expires_at=self.now + 3600,
        )
        self.receipt = self.store.accept_grant(
            self.principal, grant_id=self.grant.grant_id, expected_grant_version=1,
            policies=self.store.policies, actions=("recover", "download"), interaction_id="human-review",
        )

    def authorize(self, connection):
        decision = self.store.authorize_publication(
            self.principal, resource_id=self.grant.resource_id, generation=self.grant.generation,
            action="recover", grant_id=self.grant.grant_id, expected_grant_version=1,
            expected_acceptance_id=self.receipt.acceptance_id, connection=connection,
        )
        connection.execute(
            "INSERT INTO test_publication_decisions VALUES (?, ?, ?)",
            (decision.grant_id, decision.grant_version, decision.acceptance_id),
        )
        return decision

    def decisions(self):
        with self.database.transaction(immediate=False) as connection:
            return connection.execute("SELECT * FROM test_publication_decisions").fetchall()

    def test_revocation_committed_first_prevents_publication_decision(self) -> None:
        entered = threading.Event()
        finished = threading.Event()

        def publish():
            entered.set()
            try:
                with self.database.transaction() as connection:
                    self.authorize(connection)
            except AccessDenied:
                return "denied"
            finally:
                finished.set()
            return "authorized"

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.database.transaction() as connection:
                self.store.revoke_grant(self.principal, grant_id=self.grant.grant_id, connection=connection)
                pending = executor.submit(publish)
                self.assertTrue(entered.wait(timeout=5))
                self.assertFalse(finished.is_set())
            self.assertEqual(pending.result(timeout=5), "denied")
        self.assertEqual(self.decisions(), [])

    def test_authorization_committed_first_remains_a_private_decision_but_delivery_is_denied(self) -> None:
        entered = threading.Event()
        finished = threading.Event()

        def revoke():
            entered.set()
            try:
                return self.store.revoke_grant(self.principal, grant_id=self.grant.grant_id)
            finally:
                finished.set()

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.database.transaction() as connection:
                decision = self.authorize(connection)
                pending = executor.submit(revoke)
                self.assertTrue(entered.wait(timeout=5))
                self.assertFalse(finished.is_set())
            revoked = pending.result(timeout=5)
        self.assertEqual(revoked.grant_version, decision.grant_version + 1)
        recorded = self.decisions()
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["acceptance_id"], decision.acceptance_id)
        with self.assertRaises(AccessDenied):
            self.store.require_access(
                self.principal, resource_id=self.grant.resource_id, generation=self.grant.generation,
                action="download", grant_id=self.grant.grant_id, expected_grant_version=1,
            )

    def test_waiting_publication_rechecks_expiry_after_obtaining_the_write_lock(self) -> None:
        entered = threading.Event()

        def publish():
            entered.set()
            try:
                with self.database.transaction() as connection:
                    self.authorize(connection)
            except AccessDenied:
                return "denied"
            return "authorized"

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.database.transaction():
                pending = executor.submit(publish)
                self.assertTrue(entered.wait(timeout=5))
                self.now = self.grant.expires_at
            self.assertEqual(pending.result(timeout=5), "denied")
        self.assertEqual(self.decisions(), [])

    def test_uncommitted_authorization_does_not_survive_a_transaction_failure(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            with self.database.transaction() as connection:
                self.authorize(connection)
                raise RuntimeError("synthetic failure")
        self.assertEqual(self.decisions(), [])
        self.store.revoke_grant(self.principal, grant_id=self.grant.grant_id)
        with self.database.transaction() as connection:
            with self.assertRaises(AccessDenied):
                self.authorize(connection)


if __name__ == "__main__":
    unittest.main()
