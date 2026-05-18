"""
Phase 139 PR2 — embedder idle-release timer
==========================================

Periodically inspects each shared embedder's ``_last_embed_ts`` and
calls ``close_shared_embedders()`` when **all** embedders have been
idle longer than ``PREP_EMBED_IDLE_RELEASE_SEC`` (default 600 s, per
Eric's Q5 decision).

Rationale: per RESEARCH.md §1.1, ORT/CoreML do not deterministically
free memory in-process. Releasing the Python ref while the daemon is
idle won't reclaim CoreML/ANE memory until process exit, but it
*does* drop the Python session reference, encouraging next-cycle gc
and freeing tokenizer/numpy state. Cold-start cost on next call is
3-6 s — acceptable when the trigger is genuine idleness.

Knobs:

  PREP_EMBED_IDLE_RELEASE_SEC=600   idle timeout in seconds (≤0 = off)
  PREP_EMBED_IDLE_POLL_SEC=60       how often the timer wakes (default 60s)

Safe to ``start()`` / ``stop()`` multiple times. No-op when timeout ≤ 0.
"""

from __future__ import annotations

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_DEFAULT_IDLE_RELEASE_SEC = 600.0
_DEFAULT_POLL_SEC = 60.0

_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None


def _idle_release_sec() -> float:
    raw = os.environ.get("PREP_EMBED_IDLE_RELEASE_SEC", "")
    if not raw:
        return _DEFAULT_IDLE_RELEASE_SEC
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_IDLE_RELEASE_SEC


def _poll_sec() -> float:
    raw = os.environ.get("PREP_EMBED_IDLE_POLL_SEC", "")
    if not raw:
        return _DEFAULT_POLL_SEC
    try:
        v = float(raw)
        return v if v > 0 else _DEFAULT_POLL_SEC
    except ValueError:
        return _DEFAULT_POLL_SEC


def _all_embedders_idle(now: float, idle_threshold: float) -> bool:
    """True if every cached embedder has been idle ≥ *idle_threshold* seconds."""
    from prep.services.embedder_factory import _SHARED_EMBEDDERS, _SHARED_EMBEDDERS_LOCK
    with _SHARED_EMBEDDERS_LOCK:
        if not _SHARED_EMBEDDERS:
            return False  # nothing to release
        for emb in _SHARED_EMBEDDERS.values():
            last = getattr(emb, "_last_embed_ts", None)
            if last is None:
                # Embedder hasn't recorded activity yet (e.g., just constructed
                # but never called). Treat as not-yet-idle so we don't release
                # a freshly-loaded session immediately.
                return False
            if (now - last) < idle_threshold:
                return False
    return True


def _loop(stop: threading.Event, idle_threshold: float, poll: float) -> None:
    logger.info(
        "Embedder idle-release timer started (idle=%.0fs, poll=%.0fs)",
        idle_threshold, poll,
    )
    while not stop.wait(timeout=poll):
        try:
            if _all_embedders_idle(time.monotonic(), idle_threshold):
                from prep.services.embedder_factory import close_shared_embedders
                n = close_shared_embedders()
                if n:
                    logger.info(
                        "Idle-release: dropped %d embedder(s) after %.0fs of inactivity",
                        n, idle_threshold,
                    )
        except Exception as e:
            logger.debug("Idle-release tick failed (non-fatal): %s", e)
    logger.info("Embedder idle-release timer stopped")


def start() -> bool:
    """Start the idle-release timer. Idempotent. No-op when timeout ≤ 0."""
    global _thread, _stop_event
    idle = _idle_release_sec()
    if idle <= 0:
        logger.debug("Idle-release disabled (PREP_EMBED_IDLE_RELEASE_SEC ≤ 0)")
        return False

    with _lock:
        if _thread is not None and _thread.is_alive():
            return True
        _stop_event = threading.Event()
        _thread = threading.Thread(
            target=_loop,
            args=(_stop_event, idle, _poll_sec()),
            name="prep-embedder-idle-release",
            daemon=True,
        )
        _thread.start()
        return True


def stop(timeout: float = 5.0) -> None:
    """Stop the timer if running. Idempotent."""
    global _thread, _stop_event
    with _lock:
        if _stop_event is not None:
            _stop_event.set()
        thread = _thread
        _thread = None
        _stop_event = None

    if thread is not None and thread.is_alive():
        thread.join(timeout=timeout)


def is_running() -> bool:
    with _lock:
        return _thread is not None and _thread.is_alive()


__all__ = ["start", "stop", "is_running"]
