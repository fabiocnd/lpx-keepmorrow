"""The reviewed benchmark exception must never become a broad scanner bypass."""
import json
from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SecretScanPolicyTests(unittest.TestCase):
    def setUp(self):
        self.configuration = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
        self.rule = self.configuration["rules"][0]
        self.exception = self.rule["allowlists"][0]

    def test_default_rules_remain_enabled_and_exception_is_conjunctive(self):
        self.assertIs(self.configuration["extend"]["useDefault"], True)
        self.assertEqual(self.rule["id"], "generic-api-key")
        self.assertEqual(self.exception["condition"], "AND")
        self.assertEqual(self.exception["regexTarget"], "line")
        self.assertEqual(len(self.configuration["rules"]), 1)
        self.assertNotIn("allowlists", self.configuration)

    def test_exception_matches_only_the_recorded_source_fingerprint(self):
        filename = "benchmarks/results/2026-11-12-private-service-reference.json"
        record = json.loads((ROOT / filename).read_text())
        self.assertEqual(record["source"]["kind"], "worktree_file_sha256")
        field = "src/keepmorrow/integrations/chatgpt/" + "authentication.py"
        digest = record["source"]["files"][field]
        line = "    " + json.dumps(field) + ": " + json.dumps(digest) + ","
        expression = self.exception["regexes"][0]
        self.assertIsNotNone(re.fullmatch(expression, line))
        self.assertIsNone(re.fullmatch(expression, line.replace(digest, "c" * 64)))
        self.assertIsNone(re.fullmatch(expression, line.replace(field, "credential")))

    def test_exception_cannot_hide_findings_in_other_files(self):
        expression = self.exception["paths"][0]
        self.assertIsNotNone(re.search(expression, "benchmarks/results/2026-11-12-private-service-reference.json"))
        for path in ("src/configuration.py", "benchmarks/results/new.json", "credentials.json"):
            self.assertIsNone(re.search(expression, path))
