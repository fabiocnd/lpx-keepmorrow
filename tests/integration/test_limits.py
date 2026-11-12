"""Bound resource use for malformed archive roots before collecting entries."""

import tempfile
import unittest
from pathlib import Path

from keepmorrow.archive import ArchiveError, Limits, create_archive, verify_archive


class RootLimitTests(unittest.TestCase):
    def test_unexpected_archive_root_entries_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source"
            source.mkdir()
            archive = root / "archive"
            create_archive(source, archive)
            (archive / "unexpected-1").write_text("synthetic")
            (archive / "unexpected-2").write_text("synthetic")
            with self.assertRaises(ArchiveError):
                verify_archive(archive, limits=Limits(max_entries=1))


if __name__ == "__main__":
    unittest.main()

