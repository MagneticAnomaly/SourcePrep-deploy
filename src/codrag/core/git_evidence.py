"""
Read-only git history evidence for CoDRAG (Phase 105).

Produces file-level churn data, hub classification labels, and hot-zone
directory lists. Consumed on-demand by:
  - core/todo_scanner.py (churn gate for stale TODOs)
  - core/atlas/generator.py (hub label grouping, "Active zones" line)

All methods are side-effect-free except for a JSON cache under the
project index directory. Fails open on not-a-repo, shallow clone,
missing git binary, or subprocess errors.
"""
from __future__ import annotations

import fnmatch
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from codrag.core.repo_profile import (
    DEFAULT_EXCLUDE_DIR_NAMES,
    DEFAULT_EXCLUDE_FILE_NAMES,
)

logger = logging.getLogger(__name__)

# ── Public label type ────────────────────────────────────────────────

HubLabel = str  # "stable" | "evolving" | "fragile" | "unknown"

# ── Classification thresholds (tunable) ──────────────────────────────

HUB_STABLE_MAX_COMMITS: int = 3
HUB_EVOLVING_MAX_COMMITS: int = 15
HUB_FRAGILE_MIN_AUTHORS: int = 3

# ── Exclusions ───────────────────────────────────────────────────────

_LOCKFILE_GLOBS: List[str] = [
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Cargo.lock",
    "*.lock",
    "*/package-lock.json",
    "*/yarn.lock",
    "*/poetry.lock",
    "*/Cargo.lock",
]

_MEDIA_EXTS: List[str] = [
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf",
    ".bin", ".ico", ".webp", ".mp4", ".mov",
]

_SCHEMA_VERSION: int = 1


def _is_excluded_path(rel_posix: str) -> bool:
    """Return True if the path should be absent from churn analysis.

    Accepts POSIX-style repo-relative paths.
    """
    # Directory-level exclusions (any path segment)
    parts = rel_posix.split("/")
    for part in parts:
        if part in DEFAULT_EXCLUDE_DIR_NAMES:
            return True

    # File-level exclusions
    basename = parts[-1] if parts else rel_posix
    if basename in DEFAULT_EXCLUDE_FILE_NAMES:
        return True

    # Lockfile globs
    for glob in _LOCKFILE_GLOBS:
        if fnmatch.fnmatch(rel_posix, glob):
            return True

    # Media extensions
    for ext in _MEDIA_EXTS:
        if rel_posix.lower().endswith(ext):
            return True

    return False


# ── Data class ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class FileChurn:
    """Churn data for a single file over a window."""
    path: str                 # repo-relative POSIX
    commits: int              # commits touching this file in window
    lines_added: int
    lines_removed: int
    first_seen: datetime      # first commit in window
    last_seen: datetime       # most recent commit in window
    authors: int              # distinct authors in window


# ── Main class (stubbed; Task 3 adds loading) ────────────────────────

class GitEvidence:
    """Read-only git-history evidence cache."""

    def __init__(
        self,
        repo_root: Path,
        *,
        cache_dir: Path,
        default_window_days: int = 60,
        default_max_commits: int = 2000,
    ) -> None:
        self._repo_root = Path(repo_root).resolve()
        self._cache_dir = Path(cache_dir)
        self._default_window_days = default_window_days
        self._default_max_commits = default_max_commits
        self._lock = threading.Lock()
        self._churn_cache: Optional[Dict[str, FileChurn]] = None
        self._stats: Dict[str, int] = {
            "cache_hits": 0,
            "cache_misses": 0,
            "refreshes": 0,
        }

    def stats(self) -> Dict[str, int]:
        """Return a snapshot of cache stats."""
        with self._lock:
            return dict(self._stats)
