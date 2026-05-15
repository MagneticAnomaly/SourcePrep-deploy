"""
Phase 139 daemon-wide RSS sampler
=================================

Background thread that periodically samples the daemon's resident set
size and appends a ``daemon_memory`` event to a daemon-wide log. The
goal is to **see** memory growth as a function of time and pipeline
stage, so that the next memory incident is debuggable from telemetry
alone (no live ``sample(pid)`` needed).

The sampler is **opt-in** to avoid adding any cost in normal runs:

  PREP_RSS_TELEMETRY=1                  enable
  PREP_RSS_TELEMETRY_INTERVAL_SEC=30    sample every N seconds (default 30)
  PREP_RSS_TELEMETRY_LOG=<path>         override log file (default: daemon data dir)

Log format (JSONL, one event per line):

    {
      "ts": "2026-05-15T13:40:00+00:00",
      "event": "daemon_memory",
      "payload": {
        "rss_gb": 12.34,
        "ceiling_gb": 32.0,
        "over_ceiling": false,
        "headroom_gb": 19.66
      }
    }

The sampler is safe to call ``start()`` and ``stop()`` multiple times.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL_SEC = 30.0

_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_stop_event: Optional[threading.Event] = None


def _is_enabled() -> bool:
    raw = os.environ.get("PREP_RSS_TELEMETRY", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _interval_sec() -> float:
    raw = os.environ.get("PREP_RSS_TELEMETRY_INTERVAL_SEC", "")
    try:
        v = float(raw) if raw else _DEFAULT_INTERVAL_SEC
        return v if v > 0 else _DEFAULT_INTERVAL_SEC
    except ValueError:
        return _DEFAULT_INTERVAL_SEC


def _default_log_path() -> Path:
    """Resolve the daemon-wide RSS log location.

    Priority:
      1. PREP_RSS_TELEMETRY_LOG (absolute path)
      2. $PREP_DATA_DIR/daemon_rss.jsonl
      3. ~/.local/share/sourceprep/daemon_rss.jsonl
    """
    override = os.environ.get("PREP_RSS_TELEMETRY_LOG", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    data_dir = os.environ.get("PREP_DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir).expanduser() / "daemon_rss.jsonl"
    return Path.home() / ".local" / "share" / "sourceprep" / "daemon_rss.jsonl"


def _emit(log_path: Path) -> None:
    """Take one sample and append to *log_path*. Fail-quiet."""
    try:
        from prep.core import memory_guard
        snap = memory_guard.sample()
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "daemon_memory",
            "payload": {
                "rss_gb": round(snap.rss_gb, 3),
                "ceiling_gb": round(snap.ceiling_gb, 3),
                "over_ceiling": snap.over_ceiling,
                "headroom_gb": round(snap.headroom_gb, 3),
            },
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception as e:
        logger.debug("RSS sampler emit failed (non-fatal): %s", e)


def _loop(interval: float, log_path: Path, stop: threading.Event) -> None:
    logger.info(
        "RSS sampler started (interval=%.1fs, log=%s)",
        interval, log_path,
    )
    # Emit one immediate sample so the first interval doesn't delay the first datapoint.
    _emit(log_path)
    while not stop.wait(timeout=interval):
        _emit(log_path)
    logger.info("RSS sampler stopped")


def start() -> bool:
    """Start the sampler thread if enabled. Idempotent.

    Returns True if the sampler is now running (was started or
    already running), False if PREP_RSS_TELEMETRY is not set.
    """
    global _thread, _stop_event
    if not _is_enabled():
        logger.debug("RSS sampler not started: PREP_RSS_TELEMETRY not set")
        return False

    with _lock:
        if _thread is not None and _thread.is_alive():
            return True
        interval = _interval_sec()
        log_path = _default_log_path()
        _stop_event = threading.Event()
        _thread = threading.Thread(
            target=_loop,
            args=(interval, log_path, _stop_event),
            name="prep-rss-sampler",
            daemon=True,
        )
        _thread.start()
        return True


def stop(timeout: float = 5.0) -> None:
    """Stop the sampler thread if running. Idempotent."""
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
