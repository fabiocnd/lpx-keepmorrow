"""Opaque upload ownership, bounded admission, retention, and byte integrity."""

from __future__ import annotations

import hashlib
import io
import multiprocessing
from pathlib import Path
import tempfile
import threading
import unittest

from keepmorrow.transfers import TransferError, TransferLimitExceeded, UploadLimits, UploadStore, UploadUnavailable


def _receive_until_terminated(root: str, ready) -> None:
    """Expose a committed intake reservation before the parent kills this child.

    Normal exception cleanup must not run: restart recovery needs the partial
    filesystem and ledger state left by an interrupted process.
    """
    class InterruptedStream(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            ready.put(True)
            threading.Event().wait(30)
            return super().read(size)

    store = UploadStore(Path(root), limits=UploadLimits(max_upload_bytes=64, chunk_bytes=4))
    store.receive("owner-a", InterruptedStream(b"interrupted"), display_name="interrupted")


class UploadStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.now = [100.0]
        self.limits = UploadLimits(
            max_upload_bytes=64, max_owner_bytes=128, max_total_bytes=256,
            max_owner_uploads=3, max_total_uploads=6, lifetime_seconds=10, chunk_bytes=4,
        )
        self.store = UploadStore(self.root / "uploads", limits=self.limits, clock=lambda: self.now[0])

    def receive(self, data: bytes = b"\x00\xffbinary\r\n"):
        return self.store.receive("owner-a", io.BytesIO(data), display_name="../../untrusted.png")

    def test_binary_receipt_and_verified_stream_do_not_expose_storage_names(self) -> None:
        data = b"\x00\xffbinary\r\n"
        record = self.receive(data)
        self.assertEqual(record.sha256, hashlib.sha256(data).hexdigest())
        self.assertEqual(record.size_bytes, len(data))
        self.assertEqual(record.expires_at, 110)
        self.assertNotIn("path", record.as_dict())
        self.assertNotIn("untrusted", record.upload_id)
        with self.store.open_upload("owner-a", record.upload_id) as (opened, source):
            self.assertEqual(opened, record)
            self.assertEqual(source.read(), data)
        self.assertFalse((self.root / "untrusted.png").exists())

    def test_foreign_missing_and_expired_handles_share_unavailable_error(self) -> None:
        record = self.receive()
        for owner, handle in (("owner-b", record.upload_id), ("owner-a", "../../other")):
            with self.assertRaisesRegex(UploadUnavailable, "The upload is unavailable"):
                self.store.resolve(owner, handle)
        self.now[0] = record.expires_at
        with self.assertRaisesRegex(UploadUnavailable, "The upload is unavailable"):
            self.store.resolve("owner-a", record.upload_id)
        self.assertEqual(self.store.cleanup_expired(), 1)
        self.assertEqual(self.store.cleanup_expired(), 0)

    def test_declared_length_is_exact_and_failed_intake_releases_quota(self) -> None:
        for data, declared in ((b"short", 6), (b"longer", 3), (b"x" * 65, None)):
            with self.subTest(declared=declared), self.assertRaises(TransferError):
                self.store.receive("owner-a", io.BytesIO(data), display_name="input.zip", expected_size_bytes=declared)
            self.assertEqual(list((self.store.root / "objects").iterdir()), [])
        empty = self.store.receive("owner-a", io.BytesIO(b""), display_name="empty", expected_size_bytes=0)
        self.assertEqual(empty.size_bytes, 0)
        self.assertEqual(empty.sha256, hashlib.sha256(b"").hexdigest())

    def test_corrupted_staged_bytes_are_never_returned_as_verified(self) -> None:
        record = self.receive()
        with self.store.borrow_path("owner-a", record.upload_id) as path:
            selected = path
        data = selected.read_bytes()
        selected.write_bytes(b"!" + data[1:])
        with self.assertRaisesRegex(TransferError, "SHA-256"):
            with self.store.open_upload("owner-a", record.upload_id):
                self.fail("Corrupted content must not reach a consumer.")

    def test_active_pin_survives_expiry_cleanup_until_consumer_exits(self) -> None:
        record = self.receive()
        with self.store.borrow_path("owner-a", record.upload_id) as path:
            with self.assertRaisesRegex(TransferError, "in use"):
                self.store.discard("owner-a", record.upload_id)
            self.now[0] = 120
            self.assertEqual(self.store.cleanup_expired(), 0)
            self.assertTrue(path.is_file())
        self.assertEqual(self.store.cleanup_expired(), 1)
        self.assertFalse(path.exists())

    def test_cleanup_ignores_unregistered_objects_and_never_follows_links(self) -> None:
        unrelated = self.store.root / "objects" / "unrelated"
        unrelated.mkdir()
        (unrelated / "keep.txt").write_text("preserve", encoding="utf-8")
        record = self.receive()
        with self.store.borrow_path("owner-a", record.upload_id) as path:
            selected = path
        target = self.root / "original.bin"
        target.write_bytes(b"original")
        selected.unlink()
        try:
            selected.symlink_to(target)
        except OSError:
            self.skipTest("This runner does not permit symbolic links.")
        self.now[0] = 120
        with self.assertRaises(TransferError):
            self.store.cleanup_expired()
        self.assertEqual(target.read_bytes(), b"original")
        self.assertEqual((unrelated / "keep.txt").read_text(encoding="utf-8"), "preserve")

    def test_cancelled_stream_is_removed_without_consuming_completed_upload(self) -> None:
        completed = self.receive(b"keep")
        calls = 0

        def cancel() -> None:
            nonlocal calls
            calls += 1
            if calls == 4:
                raise RuntimeError("synthetic cancellation")

        with self.assertRaisesRegex(RuntimeError, "synthetic cancellation"):
            self.store.receive("owner-a", io.BytesIO(b"abcdefghijk"), display_name="cancelled", checkpoint=cancel)
        self.assertEqual(len(list((self.store.root / "objects").iterdir())), 1)
        self.assertEqual(self.store.resolve("owner-a", completed.upload_id), completed)

    def test_reservation_prevents_concurrent_over_admission(self) -> None:
        store = UploadStore(self.root / "concurrent", limits=UploadLimits(
            max_upload_bytes=8, max_owner_bytes=8, max_total_bytes=8, chunk_bytes=4,
        ))
        entered, release = threading.Event(), threading.Event()
        errors: list[BaseException] = []

        class SlowStream(io.BytesIO):
            def read(self, size: int = -1) -> bytes:
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("The synthetic stream was not released.")
                return super().read(size)

        def receive() -> None:
            try:
                store.receive("owner-a", SlowStream(b"ab"), display_name="first")
            except BaseException as error:
                errors.append(error)

        worker = threading.Thread(target=receive)
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaises(TransferLimitExceeded):
                store.receive("owner-b", io.BytesIO(b"c"), display_name="second", expected_size_bytes=1)
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        second = store.receive("owner-b", io.BytesIO(b"c"), display_name="second", expected_size_bytes=1)
        self.assertEqual(second.size_bytes, 1)

    def test_ready_upload_and_receipt_survive_store_reopen(self) -> None:
        record = self.receive()
        reopened = UploadStore(self.store.root, limits=self.limits, clock=lambda: self.now[0])
        self.assertEqual(reopened.recover_interrupted(), 0)
        self.assertEqual(reopened.resolve("owner-a", record.upload_id), record)
        with reopened.open_upload("owner-a", record.upload_id) as (_, source):
            self.assertEqual(source.read(), b"\x00\xffbinary\r\n")

    def test_restart_reclaims_an_abandoned_receiving_object_only(self) -> None:
        # Termination exercises the actual committed reservation and partial
        # filesystem state; normal exceptions already perform scoped cleanup.
        completed = self.receive(b"keep")
        context = multiprocessing.get_context("spawn")
        ready = context.Queue()
        process = context.Process(target=_receive_until_terminated, args=(str(self.store.root), ready))
        process.start()
        try:
            self.assertTrue(ready.get(timeout=10))
        finally:
            process.terminate()
            process.join(10)
            ready.close()
            ready.join_thread()
        self.assertFalse(process.is_alive())
        self.assertEqual(self.store.recover_interrupted(), 1)
        self.assertEqual(self.store.resolve("owner-a", completed.upload_id), completed)
        self.assertEqual(len(list((self.store.root / "objects").iterdir())), 1)

    def test_nonempty_unowned_directory_is_not_adopted(self) -> None:
        directory = self.root / "originals"
        directory.mkdir()
        (directory / "source.txt").write_text("preserve", encoding="utf-8")
        with self.assertRaises(TransferError):
            UploadStore(directory)
        self.assertEqual((directory / "source.txt").read_text(encoding="utf-8"), "preserve")

    def test_bad_stream_and_untrusted_metadata_fail_explicitly(self) -> None:
        for source in (io.StringIO("text"),):
            with self.assertRaises(TransferError):
                self.store.receive("owner-a", source, display_name="bad")
        for value in ("", "name\r\nInjected: value"):
            with self.assertRaises(TransferError):
                self.store.receive("owner-a", io.BytesIO(b""), display_name=value)
        self.assertEqual(list((self.store.root / "objects").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
