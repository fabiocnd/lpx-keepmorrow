"""Challenge identity isolation, scoped consent, policy freshness, and metadata safety."""

from dataclasses import replace
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from keepmorrow.access import AccessDenied, AccessError, AccessStore, PolicySet, Principal
from keepmorrow.persistence import PersistenceError, SQLiteDatabase


class AccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "control.sqlite3"
        self.database = SQLiteDatabase(self.path)
        self.now = 1_800_000_000
        self.policies = PolicySet("test-terms.1", "a" * 64, "test-privacy.1", "b" * 64)
        self.store = AccessStore(self.database, self.policies, clock=lambda: self.now)
        self.owner = Principal("https://identity.example.test", "synthetic-owner")
        self.other = Principal("https://identity.example.test", "synthetic-other")

    def grant(self, principal=None, **changes):
        parameters = dict(
            resource_id="collection-a", generation="c" * 64, actions=("read", "recover", "download"),
            purpose="selected_preservation", recipient="chatgpt", expires_at=self.now + 3600,
        )
        parameters.update(changes)
        return self.store.create_grant(principal or self.owner, **parameters)

    def accept(self, grant, **changes):
        parameters = dict(
            grant_id=grant.grant_id, expected_grant_version=grant.grant_version,
            policies=self.policies, actions=("read",), interaction_id="interaction-" + grant.grant_id,
        )
        parameters.update(changes)
        return self.store.accept_grant(self.owner, **parameters)

    def require(self, grant, principal=None, **changes):
        parameters = dict(resource_id=grant.resource_id, generation=grant.generation, action="read")
        parameters.update(changes)
        return self.store.require_access(principal or self.owner, **parameters)

    def test_principal_identity_uses_exact_issuer_and_subject_not_email_or_namespace(self) -> None:
        self.assertEqual(self.owner, Principal(self.owner.issuer, self.owner.subject))
        self.assertNotEqual(self.owner.principal_id, Principal(self.owner.issuer + "/", self.owner.subject).principal_id)
        self.assertNotEqual(self.owner.principal_id, Principal(self.owner.issuer, self.owner.subject.upper()).principal_id)
        self.assertNotEqual(Principal("ab", "c").principal_id, Principal("a", "bc").principal_id)
        self.assertNotIn(self.owner.subject, self.owner.principal_id)
        for issuer, subject in (("", "owner"), ("issuer", ""), (" issuer", "owner"), ("issuer", "line\nbreak")):
            with self.subTest(issuer=issuer, subject=subject), self.assertRaises(AccessError):
                Principal(issuer, subject)

    def test_grant_creation_never_substitutes_for_human_acceptance(self) -> None:
        grant = self.grant()
        with self.assertRaises(AccessDenied):
            self.require(grant)
        self.assertEqual(self.store.list_grants(self.owner), ())
        self.assertEqual(self.store.get_grant(self.owner, grant_id=grant.grant_id), grant)

    def test_acceptance_authorizes_only_selected_actions_and_exact_generation(self) -> None:
        grant = self.grant()
        receipt = self.accept(grant)
        decision = self.require(grant)
        self.assertEqual(decision.acceptance_id, receipt.acceptance_id)
        for changes in ({"action": "recover"}, {"action": "download"}, {"generation": "d" * 64}, {"resource_id": "collection-b"}):
            with self.subTest(changes=changes), self.assertRaises(AccessDenied):
                self.require(grant, **changes)
        listed = self.store.list_grants(self.owner)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].actions, frozenset({"read"}))
        self.assertEqual(self.store.list_grants(self.owner, action="download"), ())

    def test_foreign_missing_and_unaccepted_scopes_have_identical_error_envelopes(self) -> None:
        grant = self.grant()
        self.accept(grant)
        outcomes = []
        for principal, changes in ((self.other, {}), (self.owner, {"resource_id": "missing"}), (self.owner, {"action": "recover"})):
            with self.assertRaises(AccessDenied) as result:
                self.require(grant, principal, **changes)
            outcomes.append((result.exception.code, str(result.exception)))
        self.assertEqual(len(set(outcomes)), 1)
        self.assertEqual(self.store.list_grants(self.other), ())
        with self.assertRaises(AccessDenied):
            self.store.get_grant(self.other, grant_id=grant.grant_id)
        with self.assertRaises(AccessDenied):
            self.store.revoke_grant(self.other, grant_id=grant.grant_id)
        self.assertEqual(self.require(grant).grant_version, 1)

    def test_same_subject_under_another_issuer_has_no_access(self) -> None:
        grant = self.grant()
        self.accept(grant)
        foreign = Principal("https://other-identity.example.test", self.owner.subject)
        with self.assertRaises(AccessDenied):
            self.require(grant, foreign)
        self.assertEqual(self.store.list_grants(foreign), ())

    def test_changed_policy_version_or_document_bytes_invalidates_existing_receipts(self) -> None:
        grant = self.grant()
        self.accept(grant)
        for policies in (
            replace(self.policies, terms_version="test-terms.2"),
            replace(self.policies, privacy_version="test-privacy.2"),
            replace(self.policies, terms_sha256="d" * 64),
            replace(self.policies, privacy_sha256="e" * 64),
        ):
            with self.subTest(policies=policies):
                updated = AccessStore(self.database, policies, clock=lambda: self.now)
                with self.assertRaises(AccessDenied):
                    updated.require_access(self.owner, resource_id=grant.resource_id, generation=grant.generation, action="read")
                self.assertEqual(updated.list_grants(self.owner), ())
                with self.assertRaises(AccessDenied):
                    updated.accept_grant(
                        self.owner, grant_id=grant.grant_id, expected_grant_version=1,
                        policies=self.policies, actions=("read",), interaction_id="stale-form",
                    )

    def test_new_deliberate_acceptance_can_authorize_updated_policy(self) -> None:
        grant = self.grant()
        old_receipt = self.accept(grant)
        policies = replace(self.policies, terms_sha256="f" * 64)
        updated = AccessStore(self.database, policies, clock=lambda: self.now)
        new_receipt = updated.accept_grant(
            self.owner, grant_id=grant.grant_id, expected_grant_version=1,
            policies=policies, actions=("read",), interaction_id="reviewed-new-policy",
        )
        self.assertNotEqual(old_receipt.acceptance_id, new_receipt.acceptance_id)
        decision = updated.require_access(self.owner, resource_id=grant.resource_id, generation=grant.generation, action="read")
        self.assertEqual(decision.acceptance_id, new_receipt.acceptance_id)

    def test_acceptance_and_grant_expire_at_their_exact_boundary(self) -> None:
        for shorter_acceptance in (False, True):
            with self.subTest(shorter_acceptance=shorter_acceptance):
                grant = self.grant(expires_at=self.now + 20)
                expiry = self.now + (10 if shorter_acceptance else 20)
                self.accept(grant, expires_at=expiry)
                self.now = expiry - 1
                self.require(grant, grant_id=grant.grant_id)
                self.now = expiry
                with self.assertRaises(AccessDenied):
                    self.require(grant, grant_id=grant.grant_id)

    def test_acceptance_cannot_expand_actions_expiry_or_grant_version(self) -> None:
        grant = self.grant()
        invalid = (
            {"actions": ("delete",)}, {"expected_grant_version": 2},
            {"expires_at": grant.expires_at + 1}, {"expires_at": self.now},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(AccessError):
                self.accept(grant, **changes)
        with self.assertRaises(AccessDenied):
            self.require(grant)

    def test_interaction_replay_is_rejected_without_an_additional_receipt(self) -> None:
        grant = self.grant()
        first = self.accept(grant, interaction_id="single-use-interaction")
        with self.assertRaises(AccessError):
            self.accept(grant, interaction_id="single-use-interaction")
        another = self.grant(resource_id="collection-b")
        with self.assertRaises(AccessError):
            self.accept(another, interaction_id="single-use-interaction")
        self.assertEqual(self.require(grant).acceptance_id, first.acceptance_id)
        with self.assertRaises(AccessDenied):
            self.require(another)

    def test_revocation_advances_version_and_acceptance_cannot_reactivate_scope(self) -> None:
        grant = self.grant()
        self.accept(grant)
        revoked = self.store.revoke_grant(self.owner, grant_id=grant.grant_id, expected_grant_version=1)
        self.assertEqual(revoked.grant_version, 2)
        self.assertEqual(revoked.revoked_at, self.now)
        self.assertEqual(self.store.revoke_grant(self.owner, grant_id=grant.grant_id), revoked)
        with self.assertRaises(AccessDenied):
            self.require(grant)
        with self.assertRaises(AccessDenied):
            self.accept(revoked, interaction_id="new-interaction")
        with self.assertRaises(AccessDenied):
            self.store.revoke_grant(self.owner, grant_id=grant.grant_id, expected_grant_version=1)
        self.assertEqual(self.store.list_grants(self.owner), ())

    def test_receipt_withdrawal_and_expected_receipt_fencing_are_distinct(self) -> None:
        grant = self.grant()
        first = self.accept(grant)
        second = self.accept(grant, interaction_id="second-review")
        self.store.revoke_acceptance(self.owner, acceptance_id=first.acceptance_id)
        self.store.revoke_acceptance(self.owner, acceptance_id=first.acceptance_id)
        with self.assertRaises(AccessDenied):
            self.require(grant, expected_acceptance_id=first.acceptance_id)
        self.assertEqual(self.require(grant).acceptance_id, second.acceptance_id)
        with self.assertRaises(AccessDenied):
            self.store.revoke_acceptance(self.other, acceptance_id=second.acceptance_id)

    def test_generation_fencing_rejects_a_different_grant_version_or_receipt(self) -> None:
        grant = self.grant()
        receipt = self.accept(grant)
        self.require(grant, grant_id=grant.grant_id, expected_grant_version=1, expected_acceptance_id=receipt.acceptance_id)
        with self.assertRaises(AccessDenied):
            self.require(grant, grant_id=grant.grant_id, expected_grant_version=2)
        with self.assertRaises(AccessDenied):
            self.require(grant, expected_acceptance_id="acceptance_unknown")
        with self.assertRaises(AccessError):
            self.require(grant, expected_grant_version=1)

    def test_listing_pagination_keeps_all_actions_and_does_not_cross_principals(self) -> None:
        accepted = []
        actions = tuple("action_" + str(index) for index in range(32))
        for index in range(3):
            grant = self.grant(resource_id="collection-" + str(index), actions=actions)
            self.accept(grant, actions=actions)
            accepted.append(grant.grant_id)
        self.grant(resource_id="unaccepted")
        foreign = self.grant(self.other, resource_id="foreign")
        self.store.accept_grant(
            self.other, grant_id=foreign.grant_id, expected_grant_version=1,
            policies=self.policies, actions=("read",), interaction_id="foreign-interaction",
        )
        cursor = None
        observed = []
        while page := self.store.list_grants(self.owner, limit=1, after_grant_id=cursor):
            self.assertEqual(len(page), 1)
            self.assertEqual(page[0].actions, frozenset(actions))
            observed.append(page[0].grant_id)
            cursor = page[0].grant_id
        self.assertEqual(observed, sorted(accepted))
        self.assertNotIn(foreign.grant_id, observed)

    def test_invalid_and_unbounded_inputs_fail_without_creating_grants(self) -> None:
        invalid = (
            {"resource_id": "../../private"}, {"generation": ""}, {"expires_at": True},
            {"actions": "read"}, {"actions": ("read", "read")}, {"actions": ()},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(AccessError):
                self.grant(**changes)
        consumed = []

        def unbounded():
            for index in range(1000):
                consumed.append(index)
                yield "action_" + str(index)

        with self.assertRaises(AccessError):
            self.grant(actions=unbounded())
        self.assertEqual(len(consumed), 33)
        with self.database.transaction(immediate=False) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM km_access_grants").fetchone()[0], 0)

    def test_clock_regression_does_not_accept_future_records(self) -> None:
        grant = self.grant()
        self.accept(grant)
        self.now -= 1
        with self.assertRaises(AccessDenied):
            self.require(grant)
        self.assertEqual(self.store.list_grants(self.owner), ())

    def test_shared_transaction_rolls_back_grant_and_acceptance_together(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "synthetic interruption"):
            with self.database.transaction() as connection:
                grant = self.grant(connection=connection)
                self.accept(grant, connection=connection)
                self.require(grant, connection=connection)
                raise RuntimeError("synthetic interruption")
        with self.assertRaises(AccessDenied):
            self.store.get_grant(self.owner, grant_id=grant.grant_id)
        self.assertEqual(self.store.list_grants(self.owner), ())

    def test_database_persists_only_opaque_principal_not_issuer_or_subject(self) -> None:
        grant = self.grant()
        self.accept(grant)
        data = self.path.read_bytes()
        self.assertIn(self.owner.principal_id.encode(), data)
        self.assertNotIn(self.owner.issuer.encode(), data)
        self.assertNotIn(self.owner.subject.encode(), data)

    def test_active_grant_admission_is_principal_scoped_and_retains_expired_evidence(self) -> None:
        self.store = AccessStore(self.database, self.policies, clock=lambda: self.now, max_live_grants_per_principal=2)
        first = self.grant()
        second = self.grant(resource_id="collection-b", expires_at=self.now + 1)
        with self.assertRaises(AccessError):
            self.grant(resource_id="over-limit")
        self.grant(self.other, resource_id="another-principal")
        self.store.revoke_grant(self.owner, grant_id=first.grant_id)
        self.grant(resource_id="after-revocation")
        self.now += 1
        self.grant(resource_id="after-expiry")
        self.assertEqual(self.store.get_grant(self.owner, grant_id=second.grant_id).expires_at, self.now)

    def test_publication_requires_same_database_and_an_immediate_transaction(self) -> None:
        grant = self.grant()
        self.accept(grant)

        def authorize(connection):
            return self.store.authorize_publication(
                self.owner, resource_id=grant.resource_id, generation=grant.generation,
                action="read", grant_id=grant.grant_id, expected_grant_version=1, connection=connection,
            )

        with self.database.transaction(immediate=False) as connection:
            with self.assertRaises(PersistenceError):
                authorize(connection)
        other = SQLiteDatabase(Path(self.temporary.name) / "other.sqlite3")
        with other.transaction() as connection:
            with self.assertRaises(PersistenceError):
                authorize(connection)
        raw = sqlite3.connect(self.path)
        try:
            raw.execute("BEGIN IMMEDIATE")
            with self.assertRaises(PersistenceError):
                authorize(raw)
        finally:
            raw.close()
        equivalent = SQLiteDatabase(self.path)
        with equivalent.transaction() as connection:
            self.assertEqual(authorize(connection).grant_id, grant.grant_id)


class AccessPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "control.sqlite3"
        self.database = SQLiteDatabase(self.path)

    def test_component_versions_are_independent_and_unknown_versions_preserve_existing_data(self) -> None:
        self.database.initialize_schema("first", 1, ("CREATE TABLE first_data (value TEXT NOT NULL)",))
        self.database.initialize_schema("second", 2, ("CREATE TABLE second_data (value TEXT NOT NULL)",))
        with self.database.transaction() as connection:
            connection.execute("INSERT INTO first_data VALUES ('preserved')")
        with self.assertRaises(PersistenceError) as result:
            self.database.initialize_schema("first", 2, ("DROP TABLE first_data",))
        self.assertEqual(result.exception.code, "unsupported_database_schema")
        with self.database.transaction(immediate=False) as connection:
            self.assertEqual(connection.execute("SELECT value FROM first_data").fetchone()[0], "preserved")
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_failed_schema_installation_rolls_back_every_statement(self) -> None:
        with self.assertRaises(PersistenceError):
            self.database.initialize_schema("failed", 1, (
                "CREATE TABLE partial_schema (value INTEGER)", "THIS IS NOT SQL",
            ))
        with self.database.transaction(immediate=False) as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM sqlite_schema WHERE name = 'partial_schema'").fetchone())
            self.assertIsNone(connection.execute("SELECT 1 FROM km_schema_versions WHERE component = 'failed'").fetchone())

    def test_foreign_keys_are_enabled_and_storage_errors_do_not_expose_paths_or_sql(self) -> None:
        self.database.initialize_schema("foreign_keys", 1, (
            "CREATE TABLE parent (id INTEGER PRIMARY KEY)",
            "CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))",
        ))
        with self.assertRaises(PersistenceError) as result:
            with self.database.transaction() as connection:
                self.assertIsInstance(connection.execute("SELECT 1 AS value").fetchone(), sqlite3.Row)
                connection.execute("INSERT INTO child VALUES (9001)")
        self.assertNotIn(str(self.path), str(result.exception))
        self.assertNotIn("child", str(result.exception))
        with self.database.transaction(immediate=False) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM child").fetchone()[0], 0)

    def test_unknown_database_is_never_adopted_or_overwritten(self) -> None:
        unknown = Path(self.temporary.name) / "foreign.sqlite3"
        with sqlite3.connect(unknown) as connection:
            connection.execute("CREATE TABLE other_application (value TEXT)")
        unknown.chmod(0o600)
        before = unknown.read_bytes()
        with self.assertRaises(PersistenceError):
            SQLiteDatabase(unknown)
        self.assertEqual(unknown.read_bytes(), before)

    @unittest.skipUnless(os.name == "posix", "POSIX file mode and link contract")
    def test_private_permissions_and_link_rejection(self) -> None:
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        link = Path(self.temporary.name) / "linked.sqlite3"
        link.symlink_to(self.path)
        with self.assertRaises(PersistenceError):
            SQLiteDatabase(link)
        hardlink = Path(self.temporary.name) / "hardlink.sqlite3"
        hardlink.hardlink_to(self.path)
        with self.assertRaises(PersistenceError):
            SQLiteDatabase(hardlink)
        hardlink.unlink()
        self.path.chmod(0o644)
        with self.assertRaises(PersistenceError):
            SQLiteDatabase(self.path)


if __name__ == "__main__":
    unittest.main()
