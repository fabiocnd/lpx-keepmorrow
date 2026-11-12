"""Reject excessive JSON work without misreading quoted structural characters."""

import json
import unittest

from keepmorrow.archive import ArchiveError
from keepmorrow.formats import check_json_budget


class JsonBudgetTests(unittest.TestCase):
    def test_quoted_braces_backslashes_and_escaped_quotes_do_not_increase_depth(self) -> None:
        document = {"source": "[" * 500 + '{"quoted": "\\\\"}' + "]" * 500}
        data = json.dumps(document).encode("utf-8")
        check_json_budget(data, max_bytes=len(data), max_depth=1, max_tokens=5)
        self.assertEqual(json.loads(data), document)

    def test_actual_container_depth_is_bounded_before_decoding(self) -> None:
        data = b'{"nested":[[[0]]]}'
        check_json_budget(data, max_bytes=len(data), max_depth=4, max_tokens=20)
        with self.assertRaises(ArchiveError):
            check_json_budget(data, max_bytes=len(data), max_depth=3, max_tokens=20)

    def test_many_small_values_cannot_bypass_the_object_allocation_budget(self) -> None:
        data = b"[0,0,0,0]"
        check_json_budget(data, max_bytes=len(data), max_depth=1, max_tokens=9)
        with self.assertRaises(ArchiveError):
            check_json_budget(data, max_bytes=len(data), max_depth=1, max_tokens=8)

    def test_whitespace_and_atomic_literals_have_consistent_token_accounting(self) -> None:
        data = b"[ \n true, null, -1.25e+10 \t ]"
        check_json_budget(data, max_bytes=len(data), max_depth=1, max_tokens=7)
        with self.assertRaises(ArchiveError):
            check_json_budget(data, max_bytes=len(data), max_depth=1, max_tokens=6)

    def test_input_size_and_invalid_resource_contracts_fail_closed(self) -> None:
        with self.assertRaises(ArchiveError):
            check_json_budget(b"[0]", max_bytes=2, max_depth=1, max_tokens=3)
        for name in ("max_bytes", "max_depth", "max_tokens"):
            for invalid in (0, -1, True, 1.0, "10", None):
                limits = {"max_bytes": 10, "max_depth": 2, "max_tokens": 10}
                limits[name] = invalid
                with self.subTest(name=name, invalid=invalid), self.assertRaises(ArchiveError):
                    check_json_budget(b"{}", **limits)
        with self.assertRaises(ArchiveError):
            check_json_budget(bytearray(b"{}"), max_bytes=2, max_depth=1, max_tokens=2)


if __name__ == "__main__":
    unittest.main()
