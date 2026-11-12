"""Reject ambiguous manifests before they can influence filesystem operations."""

import json
import unittest

from keepmorrow.archive.model import (
    ArchiveError,
    FileRecord,
    Limits,
    Manifest,
    parse_manifest,
    validate_relative_path,
)


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid = Manifest(("notes",), (FileRecord("notes/readme.txt", 3, "a" * 64),))
        self.document = json.loads(self.valid.to_bytes())

    def parse(self, document: object, limits: Limits | None = None) -> Manifest:
        return parse_manifest(json.dumps(document).encode(), limits or Limits())

    def test_manifest_round_trip_is_canonical(self) -> None:
        self.assertEqual(parse_manifest(self.valid.to_bytes(), Limits()), self.valid)
        self.assertEqual(self.valid.to_bytes(), self.valid.to_bytes())

    def test_path_attack_matrix_is_rejected(self) -> None:
        for path in ["", "/absolute", "../escape", "a/../b", "a/./b", "a//b", "a/", "C:/file",
                     "C:\\file", "\\\\server\\share", "NUL", "con.txt", "LPT1.log", "com¹.txt",
                     "trailing.", "trailing ", "line\nbreak", "a\x00b", "a\u200bb", "e\u0301.txt",
                     "bad\ud800", "*", "x?", "a:b", "x" * 241, "/".join(["a"] * 65)]:
            with self.subTest(path=repr(path)), self.assertRaises(ArchiveError):
                validate_relative_path(path)

    def test_supported_unicode_and_dotfiles_are_unchanged(self) -> None:
        for path in [".config/settings.json", "notes/café.txt", "a-b/a_b 1.txt"]:
            self.assertEqual(validate_relative_path(path), path)

    def test_unknown_fields_and_versions_are_rejected(self) -> None:
        for value in [2, True, "1", None]:
            with self.subTest(value=value), self.assertRaises(ArchiveError):
                self.parse({**self.document, "version": value})
        with self.assertRaises(ArchiveError):
            self.parse({**self.document, "extra": "unsupported"})

    def test_file_contract_is_strict(self) -> None:
        record = self.document["files"][0]
        for replacement in [{**record, "size_bytes": True}, {**record, "size_bytes": -1},
                            {**record, "size_bytes": 3.0}, {**record, "sha256": "A" * 64},
                            {**record, "sha256": "a" * 63}, {**record, "path": 12},
                            {**record, "unknown": "field"}]:
            with self.subTest(record=replacement), self.assertRaises(ArchiveError):
                self.parse({**self.document, "files": [replacement]})

    def test_duplicate_keys_are_rejected(self) -> None:
        data = self.valid.to_bytes().replace(b'"version": 1', b'"version": 1, "version": 1')
        with self.assertRaises(ArchiveError):
            parse_manifest(data, Limits())

    def test_ambiguous_inventory_is_rejected(self) -> None:
        record = self.document["files"][0]
        for document in [
            {**self.document, "files": [record, record]},
            {**self.document, "directories": ["notes", "NOTES"]},
            {**self.document, "directories": []},
            {**self.document, "directories": ["z", "notes"]},
        ]:
            with self.subTest(document=document), self.assertRaises(ArchiveError):
                self.parse(document)

    def test_malformed_json_is_rejected(self) -> None:
        for data in [b"{", b"[]", b"null", b"\xff", b'{"x": NaN}']:
            with self.subTest(data=data), self.assertRaises(ArchiveError):
                parse_manifest(data, Limits())

    def test_manifest_and_inventory_limits_are_enforced(self) -> None:
        for limits in [Limits(max_manifest_bytes=5), Limits(max_entries=1),
                       Limits(max_file_bytes=2), Limits(max_total_bytes=2)]:
            with self.subTest(limits=limits), self.assertRaises(ArchiveError):
                parse_manifest(self.valid.to_bytes(), limits)

    def test_invalid_limits_are_rejected(self) -> None:
        for options in [{"max_entries": 0}, {"max_file_bytes": -1}, {"chunk_bytes": True},
                        {"chunk_bytes": 17 * 1024**2}]:
            with self.subTest(options=options), self.assertRaises(ArchiveError):
                Limits(**options)


if __name__ == "__main__":
    unittest.main()

