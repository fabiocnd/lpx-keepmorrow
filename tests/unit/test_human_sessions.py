"""Human gestures remain session-bound, exact, single-use, and transactionally fresh."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

from keepmorrow.access import AccessDenied
from keepmorrow.integrations.chatgpt.human_sessions import HumanSessions
from keepmorrow.persistence import SQLiteDatabase


class HumanSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "metadata.sqlite3"
        self.database = SQLiteDatabase(self.path)
        self.now = 1_800_000_000
        self.sessions = HumanSessions(self.database, clock=lambda: self.now)
        self.token = self.sessions.create("principal_owner", expires_at=self.now + 900)
        self.session = self.sessions.require(self.token)

    def challenge(self):
        return self.sessions.challenge(self.session, kind="consent", object_id="grant_one", document_digest="a" * 64)

    def consume(self, token, **changes):
        arguments = dict(kind="consent", object_id="grant_one", document_digest="a" * 64)
        arguments.update(changes)
        return self.sessions.consume(self.session, token, **arguments)

    def test_cookie_and_csrf_are_distinct_and_only_cookie_digest_is_persisted(self) -> None:
        csrf = self.sessions.csrf(self.token)
        self.assertNotEqual(csrf, self.token)
        self.assertEqual(self.sessions.require(self.token, csrf=csrf), self.session)
        with self.assertRaises(AccessDenied):
            self.sessions.require(self.token, csrf=self.token)
        self.assertNotIn(self.token.encode(), self.path.read_bytes())
        self.assertNotIn(csrf.encode(), self.path.read_bytes())

    def test_challenge_is_single_use_and_bound_to_exact_scope(self) -> None:
        token = self.challenge()
        for changes in ({"kind": "review"}, {"object_id": "grant_two"}, {"document_digest": "b" * 64}):
            with self.subTest(changes=changes), self.assertRaises(AccessDenied):
                self.consume(token, **changes)
        self.assertTrue(self.consume(token).startswith("interaction_"))
        with self.assertRaises(AccessDenied):
            self.consume(token)

    def test_other_session_cannot_consume_or_reuse_a_gesture(self) -> None:
        challenge = self.challenge()
        other_token = self.sessions.create("principal_other", expires_at=self.now + 900)
        other = self.sessions.require(other_token)
        with self.assertRaises(AccessDenied):
            self.sessions.consume(other, challenge, kind="consent", object_id="grant_one", document_digest="a" * 64)
        self.consume(challenge)

    def test_logout_invalidates_session_and_outstanding_challenges(self) -> None:
        challenge = self.challenge()
        self.sessions.end(self.token)
        with self.assertRaises(AccessDenied):
            self.sessions.require(self.token)
        with self.assertRaises(AccessDenied):
            self.consume(challenge)
        with self.assertRaises(AccessDenied):
            self.challenge()

    def test_expiry_is_checked_after_waiting_for_the_write_transaction(self) -> None:
        challenge = self.challenge()
        entered = threading.Event()

        def waiting():
            entered.set()
            try:
                self.consume(challenge)
            except AccessDenied:
                return "denied"
            return "accepted"

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.database.transaction():
                future = executor.submit(waiting)
                self.assertTrue(entered.wait(5))
                self.now += 300
            self.assertEqual(future.result(5), "denied")

    def test_session_and_challenge_counts_are_bounded(self) -> None:
        for _ in range(32):
            self.challenge()
        with self.assertRaises(AccessDenied):
            self.challenge()
        self.now += 301
        self.challenge()

    def test_consumption_can_roll_back_with_the_receipt_transaction(self) -> None:
        challenge = self.challenge()
        with self.assertRaises(RuntimeError):
            with self.database.transaction() as connection:
                self.consume(challenge, connection=connection)
                raise RuntimeError("synthetic acceptance failure")
        self.consume(challenge)

    def test_malformed_tokens_always_use_the_safe_denial_contract(self) -> None:
        for token in (None, [], "", "a" * 63, "☃" * 64, "g" * 64):
            with self.subTest(kind=type(token).__name__):
                for call in (lambda: self.sessions.require(token), lambda: self.sessions.end(token), lambda: self.consume(token)):
                    with self.assertRaises(AccessDenied):
                        call()


if __name__ == "__main__":
    unittest.main()
