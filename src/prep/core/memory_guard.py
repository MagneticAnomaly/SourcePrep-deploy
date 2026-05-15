"""
Phase 139 RSS watchdog
======================

Soft memory ceiling for the daemon. Computes a per-machine ceiling
from a dynamic formula and exposes a single ``check()`` entry point
that callers (embedder, pipeline workers) can poll before doing a
memory-intensive call.

**The pattern (per RESEARCH.md §2.4):** modern Linux/macOS do not
honor ``resource.setrlimit(RLIMIT_RSS)``, and ``RLIMIT_AS`` breaks
NumPy and zlib. The defensible pattern is a psutil-driven soft
watchdog that refuses new batches rather than killing the process.

**Ceiling formula** (Phase 139 Q3, Eric 2026-05-15):

  ceiling = min( 32 GB,  max( 4 GB,  0.25 × total_RAM ) )

Examples:
  - 8 GB box   → ceiling 4 GB  (floor wins)
  - 16 GB box  → ceiling 4 GB  (floor wins)
  - 32 GB box  → ceiling 8 GB
  - 64 GB box  → ceiling 16 GB
  - 128 GB box → ceiling 32 GB (cap wins)

Override with ``PREP_DAEMON_MAX_RSS_GB`` (absolute integer GB,
takes precedence).
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_GB = 1024 ** 3
_CAP_BYTES = 32 * _GB
_FLOOR_BYTES = 4 * _GB
_FRACTION = 0.25


class MemoryCeilingExceeded(RuntimeError):
    """Raised when the daemon's RSS is over the ceiling and the caller
    has no shrink-batch retry option left."""


@dataclass(frozen=True)
class GuardSnapshot:
    """One sample of the memory guard's view of the world."""
    rss_bytes: int
    ceiling_bytes: int
    over_ceiling: bool
    total_ram_bytes: int

    @property
    def rss_gb(self) -> float:
        return self.rss_bytes / _GB

    @property
    def ceiling_gb(self) -> float:
        return self.ceiling_bytes / _GB

    @property
    def headroom_gb(self) -> float:
        return max(0.0, (self.ceiling_bytes - self.rss_bytes) / _GB)


_LOCK = threading.Lock()
_CACHED_CEILING: Optional[int] = None


def _read_env_ceiling() -> Optional[int]:
    """Read PREP_DAEMON_MAX_RSS_GB as bytes, or None if unset/invalid."""
    raw = os.environ.get("PREP_DAEMON_MAX_RSS_GB", "").strip()
    if not raw:
        return None
    try:
        gb = int(raw)
        if gb <= 0:
            return None
        return gb * _GB
    except ValueError:
        return None


def _detect_total_ram_bytes() -> int:
    """Total physical RAM in bytes, or 0 if detection fails."""
    try:
        import psutil  # type: ignore[import-untyped]
        return int(psutil.virtual_memory().total)
    except Exception:
        return 0


def compute_ceiling_bytes() -> int:
    """Compute the soft ceiling for this machine.

    Cached on first call. Environment override always wins. Result is
    in bytes.
    """
    global _CACHED_CEILING
    with _LOCK:
        if _CACHED_CEILING is not None:
            return _CACHED_CEILING

        env = _read_env_ceiling()
        if env is not None:
            _CACHED_CEILING = env
            logger.info(
                "Memory guard ceiling: %.1f GB (PREP_DAEMON_MAX_RSS_GB override)",
                env / _GB,
            )
            return env

        total = _detect_total_ram_bytes()
        if total <= 0:
            # Detection failed — use the floor as a conservative default.
            _CACHED_CEILING = _FLOOR_BYTES
            logger.warning(
                "Memory guard: could not detect total RAM; defaulting to %.1f GB ceiling",
                _FLOOR_BYTES / _GB,
            )
            return _CACHED_CEILING

        fraction = int(total * _FRACTION)
        ceiling = min(_CAP_BYTES, max(_FLOOR_BYTES, fraction))
        _CACHED_CEILING = ceiling
        logger.info(
            "Memory guard ceiling: %.1f GB (total RAM %.1f GB, formula: min(32, max(4, 25%%×total)))",
            ceiling / _GB, total / _GB,
        )
        return ceiling


def reset_for_tests() -> None:
    """Invalidate the cached ceiling so tests can re-read env vars."""
    global _CACHED_CEILING
    with _LOCK:
        _CACHED_CEILING = None


def sample() -> GuardSnapshot:
    """Take a single sample of process RSS vs the ceiling.

    Falls back to ``rss_bytes=0`` if psutil is unavailable so the
    caller can degrade to a no-op rather than crash.
    """
    rss = 0
    try:
        import psutil  # type: ignore[import-untyped]
        rss = int(psutil.Process().memory_info().rss)
    except Exception:
        logger.debug("Memory guard: psutil unavailable; sample defaults to 0", exc_info=True)

    ceiling = compute_ceiling_bytes()
    total = _detect_total_ram_bytes()
    return GuardSnapshot(
        rss_bytes=rss,
        ceiling_bytes=ceiling,
        over_ceiling=rss > ceiling,
        total_ram_bytes=total,
    )


def check(can_shrink: bool = True, op: str = "embed") -> GuardSnapshot:
    """Check current RSS against the ceiling.

    Returns the snapshot. Logs at WARNING when over the ceiling. Raises
    ``MemoryCeilingExceeded`` only when *can_shrink* is False and we
    are over — that's the signal for the caller that the smallest
    possible work unit still won't fit.

    Callers that pass *can_shrink=True* (the default) get a soft signal
    via ``snapshot.over_ceiling`` and are expected to shrink their
    batch and retry. *can_shrink=False* says "this is the smallest unit
    of work I can do; if we're over, fail loudly."
    """
    snap = sample()
    if snap.over_ceiling:
        logger.warning(
            "Memory guard tripped (%s): RSS %.2f GB > ceiling %.2f GB",
            op, snap.rss_gb, snap.ceiling_gb,
        )
        if not can_shrink:
            raise MemoryCeilingExceeded(
                f"RSS {snap.rss_gb:.2f} GB exceeds ceiling {snap.ceiling_gb:.2f} GB "
                f"with no shrink option remaining (op={op})"
            )
    return snap


__all__ = [
    "GuardSnapshot",
    "MemoryCeilingExceeded",
    "check",
    "compute_ceiling_bytes",
    "reset_for_tests",
    "sample",
]
