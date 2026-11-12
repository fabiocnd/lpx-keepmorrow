"""Scoped cooperative execution controls for deterministic preservation work.

Copyright 2026 Lopix Neural Inc. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class _Controls:
    checkpoint: Callable[[], None]
    before_publish: Callable[[Path, Path], None] | None
    temporary_root: Path | None


_ACTIVE: ContextVar[_Controls | None] = ContextVar("keepmorrow_execution_controls", default=None)


def checkpoint() -> None:
    """Cooperate with the caller without coupling algorithms to a job store.

    The caller's exception must propagate unchanged. A canceled operation is
    neither a corrupt source nor a successful partial result. Context variables
    isolate concurrent operations; a worker installs its scope in its own thread.
    """
    active = _ACTIVE.get()
    if active is not None:
        active.checkpoint()


def before_publication(stage: Path, destination: Path) -> None:
    """Fence the final rename after verification and before visible publication.

    The callback can persist an authorization decision bound to the staged
    manifest. It does not replace the filesystem's atomic no-replace primitive
    and does not promise power-loss durability.
    """
    active = _ACTIVE.get()
    if active is not None:
        active.checkpoint()
        if active.before_publish is not None:
            active.before_publish(stage, destination)


def temporary_parent(default: Path | None = None) -> Path | None:
    """Keep temporary bytes under the current operation's owned workspace.

    Standalone callers retain their existing temporary-directory policy. A
    service-selected root must be an existing private directory on the output
    filesystem; its ownership marker and cleanup belong to the service layer.
    """
    active = _ACTIVE.get()
    return active.temporary_root if active is not None and active.temporary_root is not None else default


@contextmanager
def execution_scope(
    *, checkpoint: Callable[[], None],
    before_publish: Callable[[Path, Path], None] | None = None,
    temporary_root: Path | None = None,
) -> Iterator[None]:
    """Install controls for one synchronous operation and restore its parent.

    Nested scopes inherit the parent's temporary root when no new root is
    specified, so changing a checkpoint cannot move private bytes to global
    temporary storage accidentally.
    """
    if not callable(checkpoint) or (before_publish is not None and not callable(before_publish)):
        raise TypeError("Execution controls require callable checkpoints.")
    if temporary_root is not None and (not isinstance(temporary_root, Path) or not temporary_root.is_absolute()):
        raise ValueError("An operation temporary root must be an absolute path.")
    if temporary_root is None:
        temporary_root = temporary_parent()
    token = _ACTIVE.set(_Controls(checkpoint, before_publish, temporary_root))
    try:
        checkpoint()
        yield
    finally:
        _ACTIVE.reset(token)
