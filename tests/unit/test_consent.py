"""Acceptance is explicit, current, operation-scoped, and checked before I/O."""

import contextlib
from datetime import datetime
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from keepmorrow.archive import ArchiveError
from keepmorrow.cli import main
from keepmorrow.consent import (
    CURRENT_PRIVACY_VERSION,
    CURRENT_TERMS_VERSION,
    ConsentError,
    require_acceptance,
)


class AcceptanceTests(unittest.TestCase):
    def test_current_versions_produce_only_nonsecret_operation_metadata(self) -> None:
        for operation in ("create", "verify", "restore"):
            with self.subTest(operation=operation):
                receipt = require_acceptance(
                    CURRENT_TERMS_VERSION, CURRENT_PRIVACY_VERSION, operation
                )
                document = receipt.as_dict()
                self.assertEqual(
                    set(document),
                    {"terms_version", "privacy_version", "accepted_at_utc", "operation"},
                )
                self.assertEqual(document["operation"], operation)
                timestamp = datetime.fromisoformat(document["accepted_at_utc"])
                self.assertIsNotNone(timestamp.utcoffset())
                self.assertEqual(timestamp.utcoffset().total_seconds(), 0)

    def test_missing_stale_and_malformed_declarations_are_refused(self) -> None:
        invalid_versions = (None, "", "2026-11-11-draft.1", "latest", True, [])
        for version in invalid_versions:
            for terms, privacy in (
                (version, CURRENT_PRIVACY_VERSION),
                (CURRENT_TERMS_VERSION, version),
            ):
                with self.subTest(terms=terms, privacy=privacy):
                    with patch("keepmorrow.consent.datetime") as clock:
                        with self.assertRaises(ConsentError):
                            require_acceptance(terms, privacy, "create")
                        clock.now.assert_not_called()

    def test_version_matching_does_not_silently_normalize_user_input(self) -> None:
        for terms, privacy in (
            (CURRENT_TERMS_VERSION + " ", CURRENT_PRIVACY_VERSION),
            (CURRENT_TERMS_VERSION, " " + CURRENT_PRIVACY_VERSION),
            (CURRENT_TERMS_VERSION.upper(), CURRENT_PRIVACY_VERSION),
        ):
            with self.subTest(terms=terms, privacy=privacy), self.assertRaises(ConsentError):
                require_acceptance(terms, privacy, "verify")

    def test_acceptance_does_not_authorize_unknown_or_broader_operations(self) -> None:
        for operation in ("", "delete", "upload", "cloud", "ai", "publish", "CREATE", None, []):
            with self.subTest(operation=operation), self.assertRaises(ConsentError):
                require_acceptance(CURRENT_TERMS_VERSION, CURRENT_PRIVACY_VERSION, operation)


class CliAcceptanceTests(unittest.TestCase):
    def test_refusal_precedes_filesystem_access_for_every_operation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing_source = root / "source-that-does-not-exist"
            destination = root / "must-not-be-created"
            declarations = (
                [],
                ["--accept-terms", CURRENT_TERMS_VERSION],
                ["--accept-privacy", CURRENT_PRIVACY_VERSION],
                ["--accept-terms", "2026-11-11-draft.1",
                 "--accept-privacy", CURRENT_PRIVACY_VERSION],
                ["--accept-terms", CURRENT_TERMS_VERSION,
                 "--accept-privacy", "2026-11-11-draft.1"],
            )
            for operation in ("create", "verify", "restore"):
                paths = [str(missing_source)]
                if operation != "verify":
                    paths.append(str(destination))
                for declaration in declarations:
                    with self.subTest(operation=operation, declaration=declaration):
                        stdout, stderr = io.StringIO(), io.StringIO()
                        with contextlib.ExitStack() as stack:
                            for method in ("stat", "lstat", "open", "iterdir"):
                                stack.enter_context(patch.object(
                                    Path, method,
                                    side_effect=AssertionError("Selected paths must remain untouched."),
                                ))
                            for service in ("create_archive", "verify_archive", "restore_archive"):
                                stack.enter_context(patch(
                                    f"keepmorrow.cli.{service}",
                                    side_effect=AssertionError("Archive service ran before acceptance."),
                                ))
                            stack.enter_context(contextlib.redirect_stdout(stdout))
                            stack.enter_context(contextlib.redirect_stderr(stderr))
                            status = main([operation, *paths, *declaration])
                        self.assertEqual(status, 2)
                        self.assertEqual(stdout.getvalue(), "")
                        document = json.loads(stderr.getvalue())
                        self.assertEqual(document["error_code"], "acceptance_required")
                        self.assertNotIn("acceptance", document)
                        self.assertNotIn(str(missing_source), stderr.getvalue())
                        self.assertFalse(destination.exists())

    def test_accepted_service_failure_keeps_acceptance_distinct_from_completion(self) -> None:
        stderr = io.StringIO()
        with patch("keepmorrow.cli.verify_archive", side_effect=ArchiveError("Invalid archive.")):
            with contextlib.redirect_stderr(stderr):
                status = main([
                    "verify", "selected-archive",
                    "--accept-terms", CURRENT_TERMS_VERSION,
                    "--accept-privacy", CURRENT_PRIVACY_VERSION,
                ])
        self.assertEqual(status, 2)
        document = json.loads(stderr.getvalue())
        self.assertEqual(document["error"], "Invalid archive.")
        self.assertEqual(document["acceptance"]["operation"], "verify")
        self.assertNotIn("verified", document)


if __name__ == "__main__":
    unittest.main()
