"""Cancellation and publication fencing preserve original bytes and destinations."""

import tempfile
import unittest
from pathlib import Path

from keepmorrow.archive.service import create_archive, verify_archive
from keepmorrow.archive.model import Limits
from keepmorrow.control import execution_scope


class _Canceled(RuntimeError):
    pass


class ExecutionControlTests(unittest.TestCase):
    def test_cancel_during_copy_removes_only_owned_stage(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            content = bytes(range(256)) * 64
            (source / "binary.bin").write_bytes(content)
            calls = 0

            def cancel() -> None:
                nonlocal calls
                calls += 1
                if calls == 8:
                    raise _Canceled()

            with self.assertRaises(_Canceled):
                with execution_scope(checkpoint=cancel):
                    create_archive(source, root / "output", limits=Limits(chunk_bytes=1024))
            self.assertEqual((source / "binary.bin").read_bytes(), content)
            self.assertEqual({item.name for item in root.iterdir()}, {"source"})
            create_archive(source, root / "output")
            self.assertTrue(verify_archive(root / "output").verified)

    def test_publication_guard_observes_verified_stage_and_can_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            (source / "record.txt").write_bytes(b"unchanged")
            observed = []

            def refuse(stage: Path, destination: Path) -> None:
                observed.append((verify_archive(stage).verified, destination.name))
                raise _Canceled()

            with self.assertRaises(_Canceled):
                with execution_scope(checkpoint=lambda: None, before_publish=refuse):
                    create_archive(source, root / "output")
            self.assertEqual(observed, [(True, "output")])
            self.assertEqual({item.name for item in root.iterdir()}, {"source"})


if __name__ == "__main__":
    unittest.main()
