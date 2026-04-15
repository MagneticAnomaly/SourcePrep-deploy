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
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

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

# Lockfile basenames (matched at any depth)
_LOCKFILE_BASENAMES: frozenset[str] = frozenset({
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Cargo.lock",
    "composer.lock",
    "Gemfile.lock",
})

# Catch-all glob for any other *.lock file
_LOCKFILE_GLOBS: list[str] = ["*.lock"]

_MEDIA_EXTS: list[str] = [
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

    if basename in _LOCKFILE_BASENAMES:
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
        self._churn_cache: dict[str, FileChurn] | None = None
        self._stats: dict[str, int] = {
            "cache_hits": 0,
            "cache_misses": 0,
            "refreshes": 0,
        }

    def stats(self) -> dict[str, int]:
        """Return a snapshot of cache stats."""
        with self._lock:
            return dict(self._stats)

    # ── Primitives ────────────────────────────────────────────────────

    def recent_churn_by_file(
        self, *, window_days: Optional[int] = None,
    ) -> Dict[str, FileChurn]:
        """Return {path: FileChurn} for every file touched in the window.

        Returns empty dict on failure (not a git repo, shallow clone,
        subprocess error, permission denied). Caches the result in
        memory for the life of the instance; the on-disk cache is
        added in Task 6.
        """
        window = window_days or self._default_window_days
        with self._lock:
            if self._churn_cache is not None:
                self._stats["cache_hits"] += 1
                return dict(self._churn_cache)
            self._stats["cache_misses"] += 1

        churn = self._compute_churn(window_days=window)

        with self._lock:
            self._churn_cache = churn
            self._stats["refreshes"] += 1
        return dict(churn)

    def file_touched_in_window(
        self, path: str, *, window_days: Optional[int] = None,
    ) -> bool:
        """True iff `path` has any commit touching it in the window."""
        churn = self.recent_churn_by_file(window_days=window_days)
        return path in churn

    def _compute_churn(
        self, *, window_days: int,
    ) -> Dict[str, FileChurn]:
        """Invoke git log and parse into a churn map."""
        from codrag.agents.shared.git_client import GitClient

        client = GitClient(self._repo_root)
        raw = client.log_numstat_since(
            since_days=window_days,
            max_commits=self._default_max_commits,
        )
        if not raw:
            return {}
        return self._parse_numstat(raw)

    @staticmethod
    def _parse_numstat(raw: str) -> Dict[str, FileChurn]:
        """Parse `git log --numstat` streamed output.

        Format per commit:
            COMMIT <sha>|<author>|<iso_date>|<subject>
            <added>\\t<removed>\\t<path>
            ...
        """
        # Accumulator: list[object] rows avoid object-typed dict casts;
        # each row is [commits, lines_added, lines_removed, first_seen, last_seen, authors].
        acc: Dict[str, list[object]] = {}

        current_author: Optional[str] = None
        current_date: Optional[datetime] = None

        for line in raw.splitlines():
            if line.startswith("COMMIT "):
                header = line[len("COMMIT "):]
                parts = header.split("|", 3)
                if len(parts) < 4:
                    continue
                _sha, author, iso_date, _subject = parts
                current_author = author
                try:
                    current_date = datetime.fromisoformat(iso_date)
                except ValueError:
                    current_date = None
                continue

            if not line.strip() or current_author is None or current_date is None:
                continue

            # numstat line: "<added>\t<removed>\t<path>"
            fields = line.split("\t")
            if len(fields) < 3:
                continue

            added_raw, removed_raw, path = fields[0], fields[1], fields[2]
            if path == "" or _is_excluded_path(path):
                continue

            try:
                added = int(added_raw) if added_raw != "-" else 0
                removed = int(removed_raw) if removed_raw != "-" else 0
            except ValueError:
                continue

            if path not in acc:
                acc[path] = [1, added, removed, current_date, current_date, {current_author}]
            else:
                row = acc[path]
                assert isinstance(row[0], int)
                assert isinstance(row[1], int)
                assert isinstance(row[2], int)
                assert isinstance(row[3], datetime)
                assert isinstance(row[4], datetime)
                assert isinstance(row[5], set)
                row[0] += 1
                row[1] += added
                row[2] += removed
                row[5].add(current_author)
                if current_date < row[3]:
                    row[3] = current_date
                if current_date > row[4]:
                    row[4] = current_date

        result: Dict[str, FileChurn] = {}
        for path, row in acc.items():
            assert isinstance(row[0], int)
            assert isinstance(row[1], int)
            assert isinstance(row[2], int)
            assert isinstance(row[3], datetime)
            assert isinstance(row[4], datetime)
            assert isinstance(row[5], set)
            result[path] = FileChurn(
                path=path,
                commits=row[0],
                lines_added=row[1],
                lines_removed=row[2],
                first_seen=row[3],
                last_seen=row[4],
                authors=len(row[5]),
            )
        return result
