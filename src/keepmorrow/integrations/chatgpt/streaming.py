"""Bounded bridges between asynchronous HTTP bodies and synchronous preservation I/O.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
import queue
import threading
from typing import Any, BinaryIO

import anyio
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from ...transfers import TransferError

CHUNK_BYTES = 64 * 1024


class _QueuedReader:
    """Return at most one bounded frame; cancellation never pretends to be EOF."""

    def __init__(self, checkpoint: Callable[[], None]) -> None:
        self.frames: queue.Queue[bytes | None] = queue.Queue(maxsize=4)
        self.aborted = threading.Event()
        self.checkpoint = checkpoint
        self.pending = b""

    def read(self, size: int) -> bytes:
        if type(size) is not int or size <= 0:
            raise TransferError("The upload reader requires a bounded read size.")
        while True:
            if self.aborted.is_set():
                raise TransferError("The upload was interrupted before completion.")
            if self.pending:
                block, self.pending = self.pending[:size], self.pending[size:]
                self.checkpoint()
                return block
            try:
                frame = self.frames.get(timeout=0.1)
            except queue.Empty:
                continue
            if frame is None:
                self.checkpoint()
                return b""
            self.pending = frame


async def receive_stream(
    request: Request,
    receiver: Callable[[BinaryIO], dict[str, Any]],
    *,
    expected_size_bytes: int,
    checkpoint: Callable[[], None],
) -> dict[str, Any]:
    """Feed a reserved upload through a four-frame queue with backpressure.

    The synchronous receiver reserves storage before reading. Application queue
    memory is bounded to four 64 KiB frames plus one producer and reader frame;
    the ASGI server owns its own incoming message buffer. A disconnect signals
    failure and waits for receiver cleanup before releasing the request's slot.
    """
    source = _QueuedReader(checkpoint)
    worker = asyncio.create_task(asyncio.to_thread(receiver, source))

    async def enqueue(frame: bytes | None) -> None:
        while True:
            if worker.done():
                await worker
                raise TransferError("The upload receiver stopped before its input ended.")
            try:
                source.frames.put_nowait(frame)
                return
            except queue.Full:
                # Yield without occupying another executor thread merely to
                # wait for queue capacity. The consumer remains the only worker.
                await asyncio.sleep(0.001)

    try:
        count = 0
        async for message in request.stream():
            count += len(message)
            if count > expected_size_bytes:
                raise TransferError("The upload exceeds its declared byte count.")
            for offset in range(0, len(message), CHUNK_BYTES):
                await enqueue(message[offset:offset + CHUNK_BYTES])
        if count != expected_size_bytes:
            raise TransferError("The upload does not match its declared byte count.")
        await enqueue(None)
        return await asyncio.shield(worker)
    except BaseException:
        source.aborted.set()
        # Cancelling a to_thread future does not stop its thread. Keep the task
        # live and await its cleanup so its reservation cannot be reused early.
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if worker.done() and not worker.cancelled():
            worker.exception()
        raise


class VerifiedDownloadResponse(StreamingResponse):
    """Close an entered download context even if response startup is cancelled."""

    def __init__(
        self,
        context: AbstractContextManager[tuple[BinaryIO, int]],
        stream: BinaryIO,
        size_bytes: int,
        checkpoint: Callable[[], None],
    ) -> None:
        self._context = context

        async def chunks():
            while True:
                try:
                    await run_in_threadpool(checkpoint)
                    block = await run_in_threadpool(stream.read, CHUNK_BYTES)
                    if not block:
                        return
                    # A revocation during disk I/O prevents the pending frame
                    # from being disclosed. Bytes already sent are not recalled.
                    await run_in_threadpool(checkpoint)
                except Exception:
                    return
                yield block

        super().__init__(chunks(), media_type="application/zip", headers={
            "Content-Length": str(size_bytes),
            "Content-Disposition": 'attachment; filename="keepmorrow-package.zip"',
            "Cache-Control": "no-store",
        })

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                await run_in_threadpool(self._context.__exit__, None, None, None)
