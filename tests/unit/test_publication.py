"""Publication must never replace files or directories created by another writer."""

import tempfile
import unittest
from pathlib import Path

from keepmorrow.archive.filesystem import publish_directory
from keepmorrow.archive.model import ArchiveError


class PublicationTests(unittest.TestCase):
    def test_existing_empty_directory_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            stage = root / "stage"
            stage.mkdir()
            (stage / "data").write_bytes(b"preserved")
            destination = root / "destination"
            destination.mkdir()
            with self.assertRaises((ArchiveError, OSError)):
                publish_directory(stage, destination)
            self.assertEqual(list(destination.iterdir()), [])
            self.assertEqual((stage / "data").read_bytes(), b"preserved")

    def test_existing_file_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            stage = root / "stage"
            stage.mkdir()
            destination = root / "destination"
            destination.write_bytes(b"user-owned")
            with self.assertRaises((ArchiveError, OSError)):
                publish_directory(stage, destination)
            self.assertEqual(destination.read_bytes(), b"user-owned")


if __name__ == "__main__":
    unittest.main()

