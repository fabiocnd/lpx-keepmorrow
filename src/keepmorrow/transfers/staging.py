"""Bounded upload staging with durable ownership and quota reservations.

The service supplies an authenticated, stable owner identifier. This module
does not authenticate a caller or establish that intake consent was accepted.
Storage roots and ancestors must be dedicated to the service and remain stable.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import sqlite3
import stat
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Callable, Iterator

from ..archive.filesystem import open_regular, safe_directory
from .model import (
    Checkpoint, TransferError, TransferLimitExceeded, UploadLimits,
    UploadRecord, UploadUnavailable, checkpoint_if_requested,
)

_HANDLE = re.compile(r"u_[0-9a-f]{32}\Z")
_MEDIA_TYPE = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+\Z")
_STORE_MARKER = b"LPX Keepmorrow owned upload store version 1\n"
_MARKER_NAME = ".keepmorrow-upload"
_PAYLOAD_NAME = "payload.bin"


def _text(value: object, label: str, maximum_bytes: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TransferError(f"The {label} must be a nonempty string.")
    try:
        if len(value.encode("utf-8")) > maximum_bytes:
            raise TransferError(f"The {label} exceeds its byte limit.")
    except UnicodeError as error:
        raise TransferError(f"The {label} contains unsupported Unicode.") from error
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise TransferError(f"The {label} contains control characters.")
    return value


def _signature(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _check_file(source: BinaryIO, path: Path, initial: os.stat_result) -> None:
    observed = os.fstat(source.fileno())
    binding = path.lstat()
    if (_signature(observed) != _signature(initial) or not stat.S_ISREG(binding.st_mode)
            or not os.path.samestat(binding, observed) or binding.st_size != observed.st_size
            or binding.st_mtime_ns != observed.st_mtime_ns
            or (binding.st_mode & ~0o111) != (observed.st_mode & ~0o111)):
        raise TransferError("The staged upload changed during access.")


class UploadStore:
    """Keep bounded streams under opaque handles until expiry or explicit release.

    SQLite transactions reserve byte/count budgets before the first payload
    write. Reservations include receiving, ready, pinned, and pending-deletion
    objects. Pins prevent cleanup from racing an active consumer. A service
    restart must call ``recover_interrupted`` before accepting new requests;
    that maintenance operation requires exclusive ownership of the store.

    Payload I/O uses O(chunk_bytes) memory; metadata occupies O(upload count).
    SQLite durability does not establish payload survival after a power loss.
    """

    def __init__(
        self, root: Path, *, limits: UploadLimits | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.limits = limits or UploadLimits()
        self._clock = clock
        selected = Path(os.path.abspath(root))
        safe_directory(selected.parent)
        if not os.path.lexists(selected):
            selected.mkdir(mode=0o700)
        self.root = safe_directory(selected)
        marker = self.root / ".keepmorrow-store"
        if not os.path.lexists(marker):
            if any(self.root.iterdir()):
                raise TransferError("An upload store must begin in a new or empty dedicated directory.")
            with marker.open("xb") as output:
                output.write(_STORE_MARKER)
        with open_regular(marker) as source:
            if source.read(len(_STORE_MARKER) + 1) != _STORE_MARKER:
                raise TransferError("The upload-store version or ownership marker is unsupported.")
        self._objects = self.root / "objects"
        if not os.path.lexists(self._objects):
            self._objects.mkdir(mode=0o700)
        safe_directory(self._objects)
        self._database = self.root / "uploads.sqlite3"
        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS uploads (
                    upload_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT,
                    reserved_bytes INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('receiving', 'ready', 'deleting')),
                    pins INTEGER NOT NULL DEFAULT 0 CHECK(pins >= 0)
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS uploads_owner ON uploads(owner_id)")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        safe_directory(self.root)
        safe_directory(self._objects)
        for suffix in ("", "-wal", "-shm", "-journal"):
            candidate = Path(str(self._database) + suffix)
            if os.path.lexists(candidate) and not stat.S_ISREG(candidate.lstat().st_mode):
                raise TransferError("Upload metadata must use ordinary service-owned files.")
        connection = sqlite3.connect(self._database, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _now(self) -> float:
        value = self._clock()
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise TransferError("The upload clock must return finite, nonnegative Unix seconds.")
        return float(value)

    @staticmethod
    def _record(row: sqlite3.Row) -> UploadRecord:
        return UploadRecord(**{name: row[name] for name in (
            "upload_id", "owner_id", "display_name", "media_type", "size_bytes",
            "sha256", "created_at", "expires_at",
        )})

    def _available(self, connection: sqlite3.Connection, owner_id: str, upload_id: str) -> sqlite3.Row:
        _text(owner_id, "owner identifier", 512)
        if not isinstance(upload_id, str) or _HANDLE.fullmatch(upload_id) is None:
            raise UploadUnavailable("The upload is unavailable.")
        row = connection.execute(
            "SELECT * FROM uploads WHERE upload_id = ? AND owner_id = ? AND state = 'ready'",
            (upload_id, owner_id),
        ).fetchone()
        # Use the same category for a foreign, absent, expired, or unfinished
        # handle; metadata lookups must not disclose another owner's objects.
        if row is None or self._now() >= row["expires_at"]:
            raise UploadUnavailable("The upload is unavailable.")
        return row

    def receive(
        self, owner_id: str, source: BinaryIO, *, display_name: str,
        media_type: str = "application/octet-stream", expected_size_bytes: int | None = None,
        checkpoint: Checkpoint | None = None,
    ) -> UploadRecord:
        """Stage exactly the bytes read, rejecting a mismatched declared length.

        The caller must authorize intake before invoking this method. The
        supplied stream remains open. Admission reserves capacity before any
        payload write; the receipt is available only after length, lifetime,
        and caller checkpoints pass. Failure cleanup targets this attempt's
        owned object and retains ambiguous state rather than deleting unrelated
        paths. Cleanup errors can propagate in place of the original failure.
        """
        _text(owner_id, "owner identifier", 512)
        _text(display_name, "display name", 512)
        _text(media_type, "media type", 128)
        if _MEDIA_TYPE.fullmatch(media_type) is None:
            raise TransferError("The media type must contain a supported type and subtype.")
        if expected_size_bytes is not None and (
                type(expected_size_bytes) is not int or not 0 <= expected_size_bytes <= self.limits.max_upload_bytes):
            raise TransferLimitExceeded("The declared upload length exceeds its supported byte budget.")
        reservation = self.limits.max_upload_bytes if expected_size_bytes is None else expected_size_bytes
        created_at = self._now()
        upload_id = "u_" + uuid.uuid4().hex
        checkpoint_if_requested(checkpoint)
        with self._connection() as connection:
            totals = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(reserved_bytes), 0) FROM uploads",
            ).fetchone()
            owned = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(reserved_bytes), 0) FROM uploads WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
            if (totals[0] >= self.limits.max_total_uploads
                    or owned[0] >= self.limits.max_owner_uploads
                    or totals[1] + reservation > self.limits.max_total_bytes
                    or owned[1] + reservation > self.limits.max_owner_bytes):
                raise TransferLimitExceeded("The upload cannot be admitted within the current storage quota.")
            connection.execute(
                "INSERT INTO uploads VALUES (?, ?, ?, ?, 0, NULL, ?, ?, ?, 'receiving', 0)",
                (upload_id, owner_id, display_name, media_type, reservation,
                 created_at, created_at + self.limits.lifetime_seconds),
            )
        directory = self._objects / upload_id
        created_directory = False
        try:
            directory.mkdir(mode=0o700)
            created_directory = True
            with (directory / _MARKER_NAME).open("xb") as marker:
                marker.write((upload_id + "\n").encode("ascii"))
            digest = hashlib.sha256()
            count = 0
            descriptor = os.open(directory / _PAYLOAD_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                 | getattr(os, "O_BINARY", 0), 0o600)
            with os.fdopen(descriptor, "wb") as output:
                while True:
                    checkpoint_if_requested(checkpoint)
                    if self._now() >= created_at + self.limits.lifetime_seconds:
                        raise UploadUnavailable("The upload expired before intake completed.")
                    block = source.read(self.limits.chunk_bytes)
                    if not isinstance(block, bytes):
                        raise TransferError("An upload source must return binary byte blocks.")
                    if len(block) > self.limits.chunk_bytes:
                        raise TransferError("The upload source violated its bounded-read contract.")
                    if not block:
                        break
                    count += len(block)
                    if count > reservation:
                        raise TransferLimitExceeded("The upload exceeds its declared or configured byte budget.")
                    output.write(block)
                    digest.update(block)
            if expected_size_bytes is not None and count != expected_size_bytes:
                raise TransferError("The upload byte count does not match its declared length.")
            checkpoint_if_requested(checkpoint)
            with self._connection() as connection:
                if self._now() >= created_at + self.limits.lifetime_seconds:
                    raise UploadUnavailable("The upload expired before intake completed.")
                changed = connection.execute(
                    "UPDATE uploads SET state = 'ready', size_bytes = ?, sha256 = ?, reserved_bytes = ? "
                    "WHERE upload_id = ? AND state = 'receiving'",
                    (count, digest.hexdigest(), count, upload_id),
                ).rowcount
                if changed != 1:
                    raise TransferError("The upload reservation is no longer available.")
            return self.resolve(owner_id, upload_id)
        except BaseException:
            if created_directory:
                self._remove(upload_id, include_receiving=True)
            else:
                # A preexisting path was never created by this reservation.
                # Release the ledger row without inspecting or deleting it.
                with self._connection() as connection:
                    connection.execute("DELETE FROM uploads WHERE upload_id = ?", (upload_id,))
            raise

    def resolve(self, owner_id: str, upload_id: str) -> UploadRecord:
        """Return unexpired owned metadata without reading or pinning the payload.

        A receipt is not a promise of later availability. Open the upload to
        pin it against cleanup and verify its bytes before consumption.
        """
        with self._connection() as connection:
            return self._record(self._available(connection, owner_id, upload_id))

    @contextmanager
    def open_upload(
        self, owner_id: str, upload_id: str, *, checkpoint: Checkpoint | None = None,
    ) -> Iterator[tuple[UploadRecord, BinaryIO]]:
        """Pin, verify, and rewind an upload for one authorized consumer.

        Expiry prevents new consumers. An active consumer retains its pin until
        it exits and must separately enforce live consent and stream expiry at
        its delivery boundary. Already transmitted bytes cannot be recalled.
        The yielded stream starts at offset zero and is closed on context exit.
        Caller work may fail the final mutation check even after consuming bytes.
        """
        with self._connection() as connection:
            record = self._record(self._available(connection, owner_id, upload_id))
            connection.execute("UPDATE uploads SET pins = pins + 1 WHERE upload_id = ?", (upload_id,))
        try:
            directory = safe_directory(self._objects / upload_id)
            self._check_marker(directory, upload_id)
            path = directory / _PAYLOAD_NAME
            with open_regular(path) as source:
                initial = os.fstat(source.fileno())
                if initial.st_size != record.size_bytes:
                    raise TransferError("The staged upload failed byte-count verification.")
                count, digest = 0, hashlib.sha256()
                while block := source.read(self.limits.chunk_bytes):
                    checkpoint_if_requested(checkpoint)
                    count += len(block)
                    if count > record.size_bytes:
                        raise TransferError("The staged upload changed during verification.")
                    digest.update(block)
                _check_file(source, path, initial)
                if count != record.size_bytes or digest.hexdigest() != record.sha256:
                    raise TransferError("The staged upload failed SHA-256 verification.")
                checkpoint_if_requested(checkpoint)
                if self._now() >= record.expires_at:
                    raise UploadUnavailable("The upload expired during verification.")
                source.seek(0)
                yield record, source
                _check_file(source, path, initial)
        finally:
            with self._connection() as connection:
                changed = connection.execute(
                    "UPDATE uploads SET pins = pins - 1 WHERE upload_id = ? AND pins > 0", (upload_id,),
                ).rowcount
                if changed != 1:
                    raise TransferError("An active upload pin was invalidated outside its lifecycle.")

    @contextmanager
    def borrow_path(
        self, owner_id: str, upload_id: str, *, checkpoint: Checkpoint | None = None,
    ) -> Iterator[Path]:
        """Borrow a verified, pinned path for trusted local work within this scope.

        Do not retain or disclose the path after context exit. This method does
        not extend expiry or replace the consumer's ongoing authorization checks.
        """
        with self.open_upload(owner_id, upload_id, checkpoint=checkpoint):
            yield self._objects / upload_id / _PAYLOAD_NAME

    @staticmethod
    def _check_marker(directory: Path, upload_id: str) -> None:
        expected = (upload_id + "\n").encode("ascii")
        with open_regular(directory / _MARKER_NAME) as marker:
            if marker.read(len(expected) + 1) != expected:
                raise TransferError("The upload directory has no valid ownership marker.")

    def _remove(self, upload_id: str, *, include_receiving: bool = False) -> bool:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM uploads WHERE upload_id = ?", (upload_id,)).fetchone()
            if row is None or row["pins"] or (row["state"] == "receiving" and not include_receiving):
                return False
            connection.execute("UPDATE uploads SET state = 'deleting' WHERE upload_id = ?", (upload_id,))
            # Keep the metadata transaction open while deleting at most two
            # owned files. Concurrent maintenance cannot claim the same object,
            # and a consumer cannot pin it between lookup and removal.
            directory = self._objects / upload_id
            if os.path.lexists(directory):
                safe_directory(directory)
                children: list[Path] = []
                for child in directory.iterdir():
                    if len(children) >= 2 or child.name not in {_MARKER_NAME, _PAYLOAD_NAME}:
                        raise TransferError("Cleanup refused an upload directory containing unexpected files.")
                    children.append(child)
                if children:
                    self._check_marker(directory, upload_id)
                for name in (_PAYLOAD_NAME, _MARKER_NAME):
                    child = directory / name
                    if os.path.lexists(child):
                        if not stat.S_ISREG(child.lstat().st_mode):
                            raise TransferError("Cleanup refused a non-regular upload object.")
                        child.unlink()
                directory.rmdir()
            connection.execute("DELETE FROM uploads WHERE upload_id = ? AND state = 'deleting'", (upload_id,))
        return True

    def discard(self, owner_id: str, upload_id: str) -> None:
        """Remove a ready, unexpired, unpinned upload belonging to the caller.

        Foreign or expired handles reveal no metadata. Expired objects belong
        to maintenance, and ownership ambiguity prevents destructive cleanup.
        """
        with self._connection() as connection:
            row = self._available(connection, owner_id, upload_id)
            if row["pins"]:
                raise TransferError("The upload is in use and cannot be discarded.")
            connection.execute("UPDATE uploads SET state = 'deleting' WHERE upload_id = ?", (upload_id,))
        self._remove(upload_id)

    def cleanup_expired(self) -> int:
        """Remove expired ready objects and retry owned pending deletions.

        Live pins and receiving uploads remain reserved. Return the number of
        ledger objects removed; filesystem or ownership failures propagate.
        """
        now = self._now()
        with self._connection() as connection:
            handles = [row[0] for row in connection.execute(
                "SELECT upload_id FROM uploads WHERE pins = 0 AND "
                "(state = 'deleting' OR (state = 'ready' AND expires_at <= ?))", (now,),
            )]
        return sum(self._remove(handle) for handle in handles)

    def recover_interrupted(self) -> int:
        """Reconcile abandoned uploads before any worker or stream is admitted.

        The operator must ensure no other process or thread uses this store.
        Calling this maintenance method during service operation is unsupported.
        Ready payloads survive restart; their bytes are checked on next access.
        """
        with self._connection() as connection:
            connection.execute("UPDATE uploads SET pins = 0")
            abandoned = [row[0] for row in connection.execute(
                "SELECT upload_id FROM uploads WHERE state IN ('receiving', 'deleting')",
            )]
        removed = sum(self._remove(handle, include_receiving=True) for handle in abandoned)
        return removed + self.cleanup_expired()
