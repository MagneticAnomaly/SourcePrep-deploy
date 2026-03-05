"""
CoDRAG Pipeline Cancellation Token — Cooperative Cancel/Pause
=============================================================

Provides a thread-safe token that pipeline workers check periodically
to support graceful pause and cancel operations.

When a worker detects cancellation, it flushes partial results to disk
before raising ``PipelinePausedError`` or ``PipelineCancelledError``.
Because all LLM-heavy stages (augmenter, epistemic, inferred edges,
group reasoning, clustering) write incremental results, restarting
the same stage after a pause will skip already-processed items.

Usage in a core class::

    def run(self, ..., cancel_token=None):
        for item in work_items:
            if cancel_token and cancel_token.is_cancelled:
                self._flush_partial_results()
                cancel_token.raise_if_cancelled()
            # ... do work ...
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import Optional


class CancelReason(str, Enum):
    """Why the token was triggered."""
    CANCEL = "cancel"
    PAUSE = "pause"


class PipelineCancelledError(Exception):
    """Raised when a pipeline stage is cancelled by the user."""
    pass


class PipelinePausedError(Exception):
    """Raised when a pipeline stage is paused by the user.

    Unlike cancel, a paused stage is expected to be resumed.
    Partial results have already been flushed to disk.
    """
    pass


class CancellationToken:
    """Thread-safe cooperative cancellation/pause token.

    Workers should check ``is_cancelled`` periodically (e.g. once per
    item in their main loop) and flush partial results before calling
    ``raise_if_cancelled()``.

    The orchestrator sets the token via ``cancel()`` or ``pause()``.
    """

    def __init__(self) -> None:
        self._event = threading.Event()
        self._reason: Optional[CancelReason] = None
        self._lock = threading.Lock()

    def cancel(self) -> None:
        """Signal cancellation (destructive stop)."""
        with self._lock:
            self._reason = CancelReason.CANCEL
        self._event.set()

    def pause(self) -> None:
        """Signal pause (graceful stop with resume intent)."""
        with self._lock:
            self._reason = CancelReason.PAUSE
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancel or pause has been requested."""
        return self._event.is_set()

    @property
    def reason(self) -> Optional[CancelReason]:
        """The reason for cancellation (cancel or pause)."""
        with self._lock:
            return self._reason

    @property
    def is_pause(self) -> bool:
        """True if this is a pause (not a hard cancel)."""
        with self._lock:
            return self._reason == CancelReason.PAUSE

    def raise_if_cancelled(self) -> None:
        """Raise the appropriate exception if cancelled/paused.

        Call this AFTER flushing partial results to disk.
        """
        if not self._event.is_set():
            return
        with self._lock:
            if self._reason == CancelReason.PAUSE:
                raise PipelinePausedError("Pipeline paused by user")
            else:
                raise PipelineCancelledError("Pipeline cancelled by user")

    def reset(self) -> None:
        """Reset the token for reuse (e.g. after resume)."""
        self._event.clear()
        with self._lock:
            self._reason = None
