"""Source-release gates reject unsafe paths, mutable Actions, and stale policies."""
import importlib.util
from pathlib import Path
import tempfile
import shutil
import unittest

from keepmorrow.consent import CURRENT_PRIVACY_VERSION, ConsentError, require_acceptance

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("source_release_check", ROOT / "scripts/check_public_source.py")
assert SPEC and SPEC.loader
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class SourceReleaseTests(unittest.TestCase):
    def test_regular_synthetic_source_is_allowed(self):
        self.assertIsNone(CHECK.path_problem("examples/synthetic-input/conversations.json"))
        self.assertIsNone(CHECK.path_problem(".env.example"))

    def test_private_paths_and_credentials_are_rejected(self):
        for path in ("docs/provenance/old.md", "docs/research/company-and-creator.md",
                     "local-service/data.json", ".env", ".env.production", "state.sqlite3-wal", "key.pem"):
            with self.subTest(path=path):
                self.assertIsNotNone(CHECK.path_problem(path))

    def test_traversal_and_backslash_paths_are_rejected(self):
        for path in ("../private", "/absolute", "safe/../private", "a\\b"):
            with self.subTest(path=path):
                self.assertIsNotNone(CHECK.path_problem(path))

    def test_symlinks_and_submodules_are_rejected(self):
        for mode in ("120000", "160000"):
            self.assertIsNotNone(CHECK.path_problem("safe-name", mode))

    def test_mutable_action_tags_are_rejected(self):
        self.assertTrue(CHECK.workflow_problems("      - uses: actions/checkout@v7\n"))

    def test_commit_pins_and_local_workflows_are_allowed(self):
        text = "      - uses: actions/checkout@" + "a" * 40 + "\n    uses: ./.github/workflows/ci.yml\n"
        self.assertEqual(CHECK.workflow_problems(text), [])

    def test_privileged_pr_trigger_is_rejected(self):
        self.assertTrue(CHECK.workflow_problems("on:\n  pull_request_target:\n"))

    def test_current_metadata_and_packaged_policies_agree(self):
        self.assertEqual(CHECK.metadata_problems(ROOT), [])

    def test_changed_packaged_policy_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for path in ("pyproject.toml", "LICENSE", "ui/chatgpt/package.json", "ui/chatgpt/package-lock.json",
                         "src/keepmorrow/consent.py", "legal/terms-of-use.md", "legal/privacy-notice.md",
                         "src/keepmorrow/policies/terms-of-use.md", "src/keepmorrow/policies/privacy-notice.md",
                         "ui/chatgpt/THIRD-PARTY-NOTICES.txt",
                         "src/keepmorrow/integrations/chatgpt/assets/THIRD-PARTY-NOTICES.txt"):
                (target / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, target / path)
            with (target / "src/keepmorrow/policies/terms-of-use.md").open("a") as output:
                output.write("\nUnreviewed change\n")
            self.assertTrue(any("Packaged policy differs" in p for p in CHECK.metadata_problems(target)))

    def test_previous_proprietary_terms_are_not_silently_accepted(self):
        with self.assertRaises(ConsentError):
            require_acceptance("2026-11-12-draft.3", CURRENT_PRIVACY_VERSION, "create")


class AdministrativeComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("github_configuration", ROOT / "scripts/configure_public_github.py")
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_api_added_fields_do_not_break_readback(self):
        self.assertTrue(self.module.contains({"enabled": True, "url": "synthetic"}, {"enabled": True}))

    def test_missing_or_disabled_control_is_rejected(self):
        self.assertFalse(self.module.contains({"enabled": False}, {"enabled": True}))
        self.assertFalse(self.module.contains({}, {"enabled": True}))

    def test_required_checks_cannot_be_omitted(self):
        self.assertFalse(self.module.contains(["CI required"], ["CI required", "Security required"]))
