"""
Read-only git history evidence for Prep (Phase 105).

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

from prep.core.repo_profile import (
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


# ── Internal accumulator for _parse_numstat ──────────────────────────

@dataclass
class _ChurnRow:
    commits: int
    lines_added: int
    lines_removed: int
    first_seen: datetime
    last_seen: datetime
    authors: set[str]


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
        self._churn_caches: dict[int, dict[str, FileChurn]] = {}
        self._stats: dict[str, int] = {
            "cache_hits": 0,
            "cache_misses": 0,
            "refreshes": 0,
        }

    def stats(self) -> dict[str, int]:
        """Return a snapshot of cache stats."""
        with self._lock:
            return dict(self._stats)

    # ── Cache management ──────────────────────────────────────────────

    def refresh(self) -> None:
        """Invalidate in-memory caches for every window.

        On-disk cache is revalidated lazily by signature on next call.
        """
        with self._lock:
            self._churn_caches.clear()

    def _cache_signature(self, *, window_days: int) -> dict[str, object]:
        """Build the signature used to validate on-disk cache."""
        from prep.agents.shared.git_client import GitClient
        client = GitClient(self._repo_root)
        head = client.rev_parse_head()
        return {
            "head_sha": head,
            "window_days": window_days,
            "max_commits": self._default_max_commits,
            "repo_root": str(self._repo_root),
            "schema_version": _SCHEMA_VERSION,
        }

    def _disk_cache_paths(self, *, window_days: int) -> tuple[Path, Path]:
        """Return (signature_path, churn_path) for the given window."""
        sig_path = self._cache_dir / f"signature_{window_days}.json"
        churn_path = self._cache_dir / f"churn_{window_days}.json"
        return sig_path, churn_path

    def _load_disk_cache(
        self, *, window_days: int,
    ) -> dict[str, FileChurn] | None:
        """Load churn from disk if signature matches. None otherwise."""
        sig_path, churn_path = self._disk_cache_paths(window_days=window_days)
        if not sig_path.exists() or not churn_path.exists():
            return None
        try:
            on_disk_sig = json.loads(sig_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        expected_sig = self._cache_signature(window_days=window_days)
        if on_disk_sig != expected_sig:
            return None
        try:
            raw = json.loads(churn_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        result: dict[str, FileChurn] = {}
        for path, d in raw.items():
            try:
                result[path] = FileChurn(
                    path=path,
                    commits=int(d["commits"]),
                    lines_added=int(d["lines_added"]),
                    lines_removed=int(d["lines_removed"]),
                    first_seen=datetime.fromisoformat(d["first_seen"]),
                    last_seen=datetime.fromisoformat(d["last_seen"]),
                    authors=int(d["authors"]),
                )
            except (KeyError, ValueError, TypeError):
                return None   # corrupt; force rebuild
        return result

    def _save_disk_cache(
        self, churn: dict[str, FileChurn], *, window_days: int,
    ) -> None:
        """Write churn map and signature to disk atomically."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        sig_path, churn_path = self._disk_cache_paths(window_days=window_days)
        sig = self._cache_signature(window_days=window_days)
        serializable = {
            path: {
                "commits": c.commits,
                "lines_added": c.lines_added,
                "lines_removed": c.lines_removed,
                "first_seen": c.first_seen.isoformat(),
                "last_seen": c.last_seen.isoformat(),
                "authors": c.authors,
            }
            for path, c in churn.items()
        }
        tmp_churn = churn_path.with_suffix(".json.tmp")
        tmp_sig = sig_path.with_suffix(".json.tmp")
        tmp_churn.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        tmp_sig.write_text(json.dumps(sig, indent=2), encoding="utf-8")
        tmp_churn.replace(churn_path)
        tmp_sig.replace(sig_path)

    # ── Primitives ────────────────────────────────────────────────────

    def recent_churn_by_file(
        self, *, window_days: int | None = None,
    ) -> dict[str, FileChurn]:
        """Return {path: FileChurn} for every file touched in the window.

        In-memory cache is keyed by window_days so multiple consumers
        (e.g. TODO scanner at 180d, atlas at 60d) can share a single
        GitEvidence instance without colliding.

        Returns empty dict on failure (not a git repo, shallow clone,
        subprocess error, permission denied).
        """
        window = window_days if window_days is not None else self._default_window_days

        with self._lock:
            cached = self._churn_caches.get(window)
            if cached is not None:
                self._stats["cache_hits"] += 1
                return dict(cached)

        # Try disk cache (no git subprocess if valid)
        disk = self._load_disk_cache(window_days=window)
        if disk is not None:
            with self._lock:
                self._churn_caches[window] = disk
                self._stats["cache_hits"] += 1
            return dict(disk)

        with self._lock:
            self._stats["cache_misses"] += 1

        churn = self._compute_churn(window_days=window)
        # Only persist non-empty results to avoid caching failure states
        if churn:
            try:
                self._save_disk_cache(churn, window_days=window)
            except OSError as e:
                logger.warning(
                    "git_evidence: failed to write disk cache for window=%d: %s",
                    window, e,
                )

        with self._lock:
            self._churn_caches[window] = churn
            self._stats["refreshes"] += 1
        return dict(churn)

    def file_touched_in_window(
        self, path: str, *, window_days: int | None = None,
    ) -> bool:
        """True iff `path` has any commit touching it in the window."""
        churn = self.recent_churn_by_file(window_days=window_days)
        return path in churn

    def classify_hub(
        self, path: str, *, window_days: int | None = None,
    ) -> HubLabel:
        """Label a hub file based on churn in the window.

        Returns one of: 'stable' | 'evolving' | 'fragile' | 'unknown'.
        """
        churn = self.recent_churn_by_file(window_days=window_days)
        entry = churn.get(path)
        if entry is None:
            return "unknown"
        if entry.commits < HUB_STABLE_MAX_COMMITS:
            return "stable"
        if entry.commits <= HUB_EVOLVING_MAX_COMMITS:
            return "evolving"
        # commits > HUB_EVOLVING_MAX_COMMITS
        if entry.authors >= HUB_FRAGILE_MIN_AUTHORS:
            return "fragile"
        return "evolving"  # high churn, single/few authors → just evolving

    def hot_zones(
        self,
        *,
        top_n: int = 5,
        window_days: int | None = None,
        min_commits: int = 10,
        depth: int = 3,
    ) -> list[str]:
        """Return directories with highest commit count in the window.

        - Groups churn by parent directory at `depth` segments deep.
        - Filters to directories with >= `min_commits` commits.
        - Filters out directories that no longer exist on disk
          (a directory rename leaves the old path in `git log` history
          forever; without this filter the atlas keeps surfacing
          ghost paths from a pre-rename source directory long after the rename).
        - Sorts descending by commit count, tie-break lex-ascending.
        - Returns at most `top_n` entries.
        - Returns [] if fewer than 3 qualifying directories (not worth
          showing a "hot zones" banner).
        """
        churn = self.recent_churn_by_file(window_days=window_days)
        if not churn:
            return []

        by_dir: dict[str, int] = {}
        for path, entry in churn.items():
            parts = path.split("/")
            if len(parts) <= 1:
                continue   # repo-root file, no directory
            dir_path = "/".join(parts[: min(depth, len(parts) - 1)]) + "/"
            by_dir[dir_path] = by_dir.get(dir_path, 0) + entry.commits

        qualifying = [(d, c) for d, c in by_dir.items() if c >= min_commits]

        # Filter out directories that have since been removed or renamed
        # (or left behind as empty husks after a rename — a pre-rename
        # source directory in this repo's history is the canonical example,
        # with the real code now living under its post-rename path).
        # A directory is "active" only if
        # it currently contains at least one file. `dir_path` carries a
        # trailing slash; rstrip before resolving.
        def _has_any_file(dir_path: str) -> bool:
            full = self._repo_root / dir_path.rstrip("/")
            if not full.is_dir():
                return False
            try:
                return any(p.is_file() for p in full.rglob("*"))
            except OSError:
                return False
        qualifying = [(d, c) for d, c in qualifying if _has_any_file(d)]

        if len(qualifying) < 3:
            return []

        qualifying.sort(key=lambda x: (-x[1], x[0]))
        return [d for d, _ in qualifying[:top_n]]

    def _compute_churn(
        self, *, window_days: int,
    ) -> dict[str, FileChurn]:
        """Invoke git log and parse into a churn map."""
        from prep.agents.shared.git_client import GitClient

        client = GitClient(self._repo_root)
        raw = client.log_numstat_since(
            since_days=window_days,
            max_commits=self._default_max_commits,
        )
        if not raw:
            return {}
        return self._parse_numstat(raw)

    @staticmethod
    def _parse_numstat(raw: str) -> dict[str, FileChurn]:
        """Parse `git log --numstat` streamed output.

        Format per commit:
            COMMIT <sha>|<author>|<iso_date>|<subject>
            <added>\\t<removed>\\t<path>
            ...
        """
        files: dict[str, _ChurnRow] = {}

        current_author: str | None = None
        current_date: datetime | None = None

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

            row = files.get(path)
            if row is None:
                files[path] = _ChurnRow(
                    commits=1,
                    lines_added=added,
                    lines_removed=removed,
                    first_seen=current_date,
                    last_seen=current_date,
                    authors={current_author},
                )
            else:
                row.commits += 1
                row.lines_added += added
                row.lines_removed += removed
                row.authors.add(current_author)
                if current_date < row.first_seen:
                    row.first_seen = current_date
                if current_date > row.last_seen:
                    row.last_seen = current_date

        result: dict[str, FileChurn] = {}
        for path, row in files.items():
            result[path] = FileChurn(
                path=path,
                commits=row.commits,
                lines_added=row.lines_added,
                lines_removed=row.lines_removed,
                first_seen=row.first_seen,
                last_seen=row.last_seen,
                authors=len(row.authors),
            )
        return result


# ── Settings helpers ─────────────────────────────────────────────────

_SETTINGS_ENABLED_KEY = "git_evidence.enabled"
_SETTINGS_ATLAS_KEY = "git_evidence.atlas_decoration"


def is_enabled() -> bool:
    """Master flag. When False, consumers must fail open (no evidence).

    Reads `settings.git_evidence.enabled` (default True). Any exception
    from the settings store is treated as "enabled" so settings outages
    never block evidence usage.
    """
    try:
        from prep.services.settings_store import settings
        value = settings.get(_SETTINGS_ENABLED_KEY, True)
    except Exception:
        return True
    return bool(value)


def atlas_decoration_enabled() -> bool:
    """Per-consumer flag for atlas hub labels + hot-zone line.

    Reads `settings.git_evidence.atlas_decoration` (default True).
    Independent of `is_enabled()` so atlas decoration can be turned
    off without disabling TODO churn gating.
    """
    try:
        from prep.services.settings_store import settings
        value = settings.get(_SETTINGS_ATLAS_KEY, True)
    except Exception:
        return True
    return bool(value)
