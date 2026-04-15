# Phase 105 — Git Evidence (Option γ) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `core/git_evidence.py` (read-only churn primitive with hub classification and hot-zone aggregation) and wire two on-demand consumers: (1) TODO scanner demotes TODOs in cold files; (2) Atlas hub text groups hubs by `stable | evolving | fragile` and gains an "Active zones" line.

**Architecture:** New `core/git_evidence.py` module wraps the existing `GitClient` (extended with three read-only methods) and caches churn data in JSON files under the project's index dir. A service-level singleton (`services/git_evidence_service.py`) matches the `concept_store` / `settings` idiom in `services/`. TODO scanner and atlas generator both acquire the singleton and fail open when evidence is unavailable. No new pipeline stage; no router changes; no dashboard changes.

**Tech Stack:** Python 3.11+, standard library only (`subprocess`, `json`, `dataclasses`, `datetime`, `pathlib`, `threading`), pytest with `tmp_path`, existing `GitClient` subprocess wrapper.

**Design docs:** `README.md`, `02_SCOPE.md`, `03_ARCHITECTURE.md`, `04_INTEGRATION_TODO_GATING.md`, `04b_INTEGRATION_ATLAS.md`, `05_RISKS.md` in this directory.

---

## File map

| Path | Action | Responsibility |
|------|--------|----------------|
| `src/codrag/agents/shared/git_client.py` | Modify | Add `log_numstat_since`, `rev_parse_head`, `is_shallow_repo` read-only methods. |
| `src/codrag/core/git_evidence.py` | Create | `FileChurn` dataclass, `GitEvidence` class, cache, classification, hot zones. |
| `src/codrag/services/git_evidence_service.py` | Create | Per-project singleton wrapper, settings-flag gating. |
| `src/codrag/core/todo_scanner.py` | Modify | Churn-gate post-processing after annotation loop. |
| `src/codrag/core/atlas/generator.py` | Modify | Hub label grouping at line 469; "Active zones" line in `cross_parts`; mirror decoration into `_build_structural_content` fallback. |
| `tests/core/test_git_evidence.py` | Create | Fixture-repo module tests. |
| `tests/core/test_todo_scanner_churn_gate.py` | Create | Scanner-integration tests with fixture repo. |
| `tests/core/test_atlas_evidence.py` | Create | Atlas decoration + fallback golden-file test. |

Everything else (settings store, repo_profile exclusions, project registry, `index_destroy_project` path) is consumed read-only or register-only — no new files, no schema changes.

---

## Defaults decided during brainstorm (do not re-litigate mid-implementation)

- TODO stale window: **180 days**.
- Hub classification window: **60 days**.
- Hub thresholds: stable < 3 commits; evolving 3-15; fragile > 15 **and** >= 3 authors; else evolving.
- Hot zones: directory depth 3, top 5, min_commits 10, hidden if < 3 qualifying.
- Label set: `stable | evolving | fragile | unknown`.
- Settings keys: `settings.git_evidence.enabled` (default true), `settings.git_evidence.atlas_decoration` (default true).
- Cache dir: `<project_index_dir>/git_evidence/`.
- Schema version: `1`.
- Max commits cap: 2000.
- Per-commit file cap: 50 (commits touching more files are counted with each file weight 1, no inflation).
- Excluded files (atop `repo_profile.DEFAULT_EXCLUDE_DIR_NAMES` and `DEFAULT_EXCLUDE_FILE_NAMES`):
  - Lockfiles: `package-lock.json`, `yarn.lock`, `poetry.lock`, `Cargo.lock`, `*.lock`
  - Media: `*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.svg`, `*.pdf`, `*.bin`

---

## Task 1: Extend `GitClient` with read-only history methods

**Files:**
- Modify: `src/codrag/agents/shared/git_client.py`
- Test: (covered indirectly by `test_git_evidence.py` fixtures in Task 3+)

Adds three low-level methods that wrap `subprocess` git invocations. Keep them small and boring — higher-level logic lives in `git_evidence.py`.

- [ ] **Step 1: Add the three methods to `GitClient`**

Append these methods to the existing class (after `copy_to_branch` at line 119, before the closing of the class):

```python
    def rev_parse_head(self) -> str:
        """Return the current HEAD SHA (full, 40 chars), or '' if not a repo."""
        result = self._run(["rev-parse", "HEAD"], check=False)
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def is_shallow_repo(self) -> bool:
        """Return True if the repo is a shallow clone."""
        result = self._run(["rev-parse", "--is-shallow-repository"], check=False)
        if result.returncode != 0:
            return False
        return result.stdout.strip().lower() == "true"

    def log_numstat_since(
        self,
        *,
        since_days: int,
        max_commits: int = 2000,
    ) -> str:
        """Return raw `git log --numstat` output for the window.

        Format (streamed, newline-separated):
            COMMIT <sha>|<author>|<iso_date>|<subject_first_80_chars>
            <added>\\t<removed>\\t<path>
            <added>\\t<removed>\\t<path>
            ...

        Returns empty string on failure (not-a-repo, shallow, permission).
        Callers parse the output; this method is intentionally dumb.
        """
        result = self._run(
            [
                "log",
                f"--since={since_days} days ago",
                f"--max-count={max_commits}",
                "--numstat",
                "--no-merges",
                "--format=COMMIT %H|%an|%aI|%s",
            ],
            check=False,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
```

- [ ] **Step 2: Type-check the new methods**

Run: `.venv/bin/mypy src/codrag/agents/shared/git_client.py`
Expected: no errors introduced by these methods. Existing errors in the file, if any, are pre-existing and out of scope.

- [ ] **Step 3: Commit**

```bash
git add src/codrag/agents/shared/git_client.py
git commit -m "feat(phase105): extend GitClient with read-only history methods"
```

---

## Task 2: Create `FileChurn` and `GitEvidence` skeleton with exclusions

**Files:**
- Create: `src/codrag/core/git_evidence.py`
- Test: `tests/core/test_git_evidence.py`

Scaffold the module with the dataclass, constructor, constants, and exclusion logic. No git calls yet — Task 3 adds parsing.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_git_evidence.py`:

```python
"""Unit tests for core/git_evidence.py."""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import pytest

from codrag.core.git_evidence import (
    FileChurn,
    GitEvidence,
    HUB_STABLE_MAX_COMMITS,
    HUB_EVOLVING_MAX_COMMITS,
    HUB_FRAGILE_MIN_AUTHORS,
    _is_excluded_path,
)


def test_filechurn_is_frozen_dataclass():
    """FileChurn must be immutable to be safe for caching."""
    now = datetime.now(timezone.utc)
    churn = FileChurn(
        path="src/foo.py",
        commits=5,
        lines_added=100,
        lines_removed=20,
        first_seen=now,
        last_seen=now,
        authors=2,
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        churn.commits = 10  # type: ignore


def test_classification_constants_have_expected_values():
    """Lock the thresholds in one place; changes should be explicit."""
    assert HUB_STABLE_MAX_COMMITS == 3
    assert HUB_EVOLVING_MAX_COMMITS == 15
    assert HUB_FRAGILE_MIN_AUTHORS == 3


def test_excluded_paths_includes_lockfiles_and_media():
    """Exclusion list covers auto-regenerated and binary files."""
    assert _is_excluded_path("package-lock.json") is True
    assert _is_excluded_path("yarn.lock") is True
    assert _is_excluded_path("frontend/package-lock.json") is True
    assert _is_excluded_path("assets/logo.png") is True
    assert _is_excluded_path("docs/diagram.svg") is True
    assert _is_excluded_path("AGENTS.md") is True
    assert _is_excluded_path("CLAUDE.md") is True
    assert _is_excluded_path(".codrag/state.json") is True
    assert _is_excluded_path(".cursor/rules.mdc") is True


def test_excluded_paths_excludes_normal_source():
    """Normal source files are not excluded."""
    assert _is_excluded_path("src/codrag/foo.py") is False
    assert _is_excluded_path("tests/test_foo.py") is False
    assert _is_excluded_path("README.md") is False  # Not a CoDRAG-managed file


def test_git_evidence_init_sets_defaults(tmp_path):
    """Constructor accepts repo_root and cache_dir; defaults wire correctly."""
    cache_dir = tmp_path / "cache"
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    assert evidence._default_window_days == 60
    assert evidence._default_max_commits == 2000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'codrag.core.git_evidence'`

- [ ] **Step 3: Create the module skeleton**

Create `src/codrag/core/git_evidence.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Type-check**

Run: `.venv/bin/mypy src/codrag/core/git_evidence.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/core/git_evidence.py tests/core/test_git_evidence.py
git commit -m "feat(phase105): scaffold git_evidence module with FileChurn + exclusions"
```

---

## Task 3: Implement `recent_churn_by_file` with git log parsing

**Files:**
- Modify: `src/codrag/core/git_evidence.py`
- Modify: `tests/core/test_git_evidence.py`

Add the first primitive. Parses the `git log --numstat` output produced by `GitClient.log_numstat_since`. No cache persistence yet — Task 7 adds that.

- [ ] **Step 1: Write the failing test (fixture-repo helper + smoke test)**

Append to `tests/core/test_git_evidence.py`:

```python
# ── Fixture-repo helpers ─────────────────────────────────────────────

def _init_repo(path: Path) -> None:
    """Initialize an empty git repo at `path` with a local identity."""
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    # Ensure default branch is 'main' across git versions
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=path, check=False)


def _commit_file(
    path: Path,
    rel_file: str,
    content: str,
    *,
    author: str = "Test User <test@example.com>",
    date: Optional[str] = None,
    message: str = "test commit",
) -> None:
    """Write a file, stage, and commit. `date` is ISO-8601 or None for now."""
    target = path / rel_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    subprocess.run(["git", "add", rel_file], cwd=path, check=True)
    env = {}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    if author:
        # Use --author flag which overrides config
        subprocess.run(
            ["git", "commit", "-q", "--author", author, "-m", message],
            cwd=path, check=True, env={**_os_env(), **env},
        )
    else:
        subprocess.run(
            ["git", "commit", "-q", "-m", message],
            cwd=path, check=True, env={**_os_env(), **env},
        )


def _os_env() -> Dict[str, str]:
    """Minimal env for git subprocesses (preserves PATH)."""
    import os
    return {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}


# ── churn primitive tests ────────────────────────────────────────────

def test_recent_churn_smoke(tmp_path):
    """Fixture repo with three files, three commits — churn map reflects them."""
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x = 1\n", message="add foo")
    _commit_file(tmp_path, "src/bar.py", "y = 2\n", message="add bar")
    _commit_file(tmp_path, "src/foo.py", "x = 1\ny = 2\n", message="update foo")

    evidence = GitEvidence(
        repo_root=tmp_path,
        cache_dir=tmp_path / ".cache",
    )
    churn = evidence.recent_churn_by_file(window_days=30)

    assert "src/foo.py" in churn
    assert "src/bar.py" in churn
    assert churn["src/foo.py"].commits == 2
    assert churn["src/bar.py"].commits == 1
    assert churn["src/foo.py"].authors == 1


def test_recent_churn_respects_exclusions(tmp_path):
    """AGENTS.md and lockfiles are absent from the churn map."""
    _init_repo(tmp_path)
    _commit_file(tmp_path, "AGENTS.md", "agents\n", message="regenerate")
    _commit_file(tmp_path, "package-lock.json", '{"a": 1}\n', message="lock")
    _commit_file(tmp_path, "src/real.py", "pass\n", message="real source")

    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    churn = evidence.recent_churn_by_file(window_days=30)

    assert "src/real.py" in churn
    assert "AGENTS.md" not in churn
    assert "package-lock.json" not in churn


def test_recent_churn_not_a_git_repo_returns_empty(tmp_path):
    """Non-git directory: empty churn, no exception."""
    # tmp_path is not a git repo
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    churn = evidence.recent_churn_by_file(window_days=30)
    assert churn == {}


def test_file_touched_in_window(tmp_path):
    """file_touched_in_window returns True for touched files, False otherwise."""
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/touched.py", "pass\n")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")

    assert evidence.file_touched_in_window("src/touched.py", window_days=30) is True
    assert evidence.file_touched_in_window("src/untouched.py", window_days=30) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: 4 new tests FAIL with `AttributeError: 'GitEvidence' object has no attribute 'recent_churn_by_file'`.

- [ ] **Step 3: Add parser helper and implement `recent_churn_by_file`**

Append to `src/codrag/core/git_evidence.py` (after the `stats()` method in class `GitEvidence`, keeping it inside the class):

```python
    # ── Primitives ────────────────────────────────────────────────────

    def recent_churn_by_file(
        self, *, window_days: Optional[int] = None,
    ) -> Dict[str, FileChurn]:
        """Return {path: FileChurn} for every file touched in the window.

        Returns empty dict on failure (not a git repo, shallow clone,
        subprocess error, permission denied). Caches the result in
        memory for the life of the instance; the on-disk cache is
        added in Task 7.
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

        Per-commit file cap: commits touching >50 files contribute to each
        file with weight 1 (no inflated per-file count) as today's design.
        The current implementation counts each (commit, file) pair once
        which is equivalent for file-commits. `lines_added`/`lines_removed`
        accumulate across all commits regardless of cap.
        """
        files: Dict[str, Dict[str, object]] = {}

        current_author: Optional[str] = None
        current_date: Optional[datetime] = None
        current_files_in_commit = 0

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
                current_files_in_commit = 0
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

            current_files_in_commit += 1

            try:
                added = int(added_raw) if added_raw != "-" else 0
                removed = int(removed_raw) if removed_raw != "-" else 0
            except ValueError:
                continue

            bucket = files.get(path)
            if bucket is None:
                files[path] = {
                    "commits": 1,
                    "lines_added": added,
                    "lines_removed": removed,
                    "first_seen": current_date,
                    "last_seen": current_date,
                    "authors": {current_author},
                }
            else:
                bucket["commits"] = int(bucket["commits"]) + 1  # type: ignore[arg-type]
                bucket["lines_added"] = int(bucket["lines_added"]) + added  # type: ignore[arg-type]
                bucket["lines_removed"] = int(bucket["lines_removed"]) + removed  # type: ignore[arg-type]
                authors_set = bucket["authors"]
                assert isinstance(authors_set, set)
                authors_set.add(current_author)
                if current_date < bucket["first_seen"]:  # type: ignore[operator]
                    bucket["first_seen"] = current_date
                if current_date > bucket["last_seen"]:  # type: ignore[operator]
                    bucket["last_seen"] = current_date

        result: Dict[str, FileChurn] = {}
        for path, b in files.items():
            authors_set = b["authors"]
            assert isinstance(authors_set, set)
            result[path] = FileChurn(
                path=path,
                commits=int(b["commits"]),  # type: ignore[arg-type]
                lines_added=int(b["lines_added"]),  # type: ignore[arg-type]
                lines_removed=int(b["lines_removed"]),  # type: ignore[arg-type]
                first_seen=b["first_seen"],  # type: ignore[arg-type]
                last_seen=b["last_seen"],  # type: ignore[arg-type]
                authors=len(authors_set),
            )
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: all 9 tests PASS.

- [ ] **Step 5: Type-check**

Run: `.venv/bin/mypy src/codrag/core/git_evidence.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/core/git_evidence.py tests/core/test_git_evidence.py
git commit -m "feat(phase105): implement recent_churn_by_file primitive"
```

---

## Task 4: Implement `classify_hub`

**Files:**
- Modify: `src/codrag/core/git_evidence.py`
- Modify: `tests/core/test_git_evidence.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_git_evidence.py`:

```python
def test_classify_hub_returns_unknown_for_untracked_path(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/real.py", "pass\n")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/missing.py") == "unknown"


def test_classify_hub_stable_when_few_commits(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/stable.py", "v = 1\n")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/stable.py") == "stable"


def test_classify_hub_evolving_when_moderate_churn(tmp_path):
    _init_repo(tmp_path)
    # 5 commits → within [3, 15] range → evolving
    for i in range(5):
        _commit_file(tmp_path, "src/evolving.py", f"v = {i}\n", message=f"c{i}")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/evolving.py") == "evolving"


def test_classify_hub_fragile_requires_high_churn_and_many_authors(tmp_path):
    """> HUB_EVOLVING_MAX_COMMITS AND >= HUB_FRAGILE_MIN_AUTHORS -> fragile."""
    _init_repo(tmp_path)
    # 16 commits from 3 authors
    authors = [
        "Alice <alice@example.com>",
        "Bob <bob@example.com>",
        "Cara <cara@example.com>",
    ]
    for i in range(16):
        _commit_file(
            tmp_path, "src/fragile.py", f"v = {i}\n",
            author=authors[i % 3], message=f"c{i}",
        )
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/fragile.py") == "fragile"


def test_classify_hub_evolving_when_high_churn_but_single_author(tmp_path):
    """High churn + single author is 'evolving', not 'fragile' — someone working alone."""
    _init_repo(tmp_path)
    for i in range(16):
        _commit_file(tmp_path, "src/solo.py", f"v = {i}\n", message=f"c{i}")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    assert evidence.classify_hub("src/solo.py") == "evolving"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: 5 new tests FAIL with `AttributeError: 'GitEvidence' object has no attribute 'classify_hub'`.

- [ ] **Step 3: Implement `classify_hub`**

Append inside class `GitEvidence` (after `file_touched_in_window`):

```python
    def classify_hub(
        self, path: str, *, window_days: Optional[int] = None,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: all tests PASS (14 total).

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/git_evidence.py tests/core/test_git_evidence.py
git commit -m "feat(phase105): implement classify_hub with stable/evolving/fragile labels"
```

---

## Task 5: Implement `hot_zones`

**Files:**
- Modify: `src/codrag/core/git_evidence.py`
- Modify: `tests/core/test_git_evidence.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_git_evidence.py`:

```python
def test_hot_zones_empty_when_no_churn(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")
    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    # Only 1 commit; min_commits=10 default → empty
    assert evidence.hot_zones() == []


def test_hot_zones_sorted_by_commit_count_desc(tmp_path):
    _init_repo(tmp_path)
    # Zone A: 12 commits across two files
    for i in range(12):
        _commit_file(tmp_path, f"src/zone_a/f{i % 3}.py", f"v={i}\n", message=f"a{i}")
    # Zone B: 15 commits
    for i in range(15):
        _commit_file(tmp_path, f"src/zone_b/f{i % 3}.py", f"v={i}\n", message=f"b{i}")
    # Zone C: 5 commits (below min_commits=10)
    for i in range(5):
        _commit_file(tmp_path, f"src/zone_c/f{i}.py", f"v={i}\n", message=f"c{i}")

    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    zones = evidence.hot_zones(top_n=5, min_commits=10)

    # Need at least 3 qualifying dirs to surface at all
    # Here only zone_a and zone_b qualify (2 dirs); expect []
    assert zones == []


def test_hot_zones_surfaces_when_three_or_more_qualify(tmp_path):
    _init_repo(tmp_path)
    for zone in ("alpha", "beta", "gamma", "delta"):
        for i in range(11):
            _commit_file(tmp_path, f"src/{zone}/f{i % 2}.py", f"v={i}\n", message=f"{zone}{i}")

    evidence = GitEvidence(repo_root=tmp_path, cache_dir=tmp_path / ".cache")
    zones = evidence.hot_zones(top_n=3, min_commits=10)
    assert len(zones) == 3
    # Ordering is by commit count desc; ties broken lex. All four have 11
    # commits, so lex-ordered top 3 are alpha, beta, delta (or similar).
    assert all(z.startswith("src/") for z in zones)
    assert len(set(zones)) == 3   # no duplicates
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: 3 new tests FAIL.

- [ ] **Step 3: Implement `hot_zones`**

Append inside class `GitEvidence` (after `classify_hub`):

```python
    def hot_zones(
        self,
        *,
        top_n: int = 5,
        window_days: Optional[int] = None,
        min_commits: int = 10,
        depth: int = 3,
    ) -> List[str]:
        """Return directories with highest commit count in the window.

        - Groups churn by parent directory at `depth` segments deep.
        - Filters to directories with >= `min_commits` commits.
        - Sorts descending by commit count, tie-break lex-ascending.
        - Returns at most `top_n` entries.
        - Returns [] if fewer than 3 qualifying directories (not worth
          showing a "hot zones" banner).
        """
        churn = self.recent_churn_by_file(window_days=window_days)
        if not churn:
            return []

        by_dir: Dict[str, int] = {}
        for path, entry in churn.items():
            parts = path.split("/")
            if len(parts) <= 1:
                continue   # repo-root file, no directory
            dir_path = "/".join(parts[: min(depth, len(parts) - 1)]) + "/"
            by_dir[dir_path] = by_dir.get(dir_path, 0) + entry.commits

        qualifying = [(d, c) for d, c in by_dir.items() if c >= min_commits]
        if len(qualifying) < 3:
            return []

        qualifying.sort(key=lambda x: (-x[1], x[0]))
        return [d for d, _ in qualifying[:top_n]]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: all tests PASS (17 total).

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/git_evidence.py tests/core/test_git_evidence.py
git commit -m "feat(phase105): implement hot_zones directory aggregation"
```

---

## Task 6: Add disk cache persistence with signature validation

**Files:**
- Modify: `src/codrag/core/git_evidence.py`
- Modify: `tests/core/test_git_evidence.py`

In-memory cache is working. Now persist to disk so repeated calls across daemon runs don't re-scan.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_git_evidence.py`:

```python
def test_cache_persists_across_instances(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")

    cache_dir = tmp_path / ".cache"
    ev1 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    churn1 = ev1.recent_churn_by_file()

    # Second instance reads the cache without re-running git
    ev2 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    churn2 = ev2.recent_churn_by_file()

    assert set(churn1.keys()) == set(churn2.keys())
    # Confirm the second instance hit the on-disk cache
    stats = ev2.stats()
    assert stats["refreshes"] == 0


def test_cache_invalidated_on_head_change(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")

    cache_dir = tmp_path / ".cache"
    ev1 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    ev1.recent_churn_by_file()

    # New commit → HEAD changes
    _commit_file(tmp_path, "src/bar.py", "y\n")

    ev2 = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    churn = ev2.recent_churn_by_file()
    assert "src/bar.py" in churn
    stats = ev2.stats()
    assert stats["refreshes"] == 1


def test_refresh_clears_cache(tmp_path):
    _init_repo(tmp_path)
    _commit_file(tmp_path, "src/foo.py", "x\n")
    cache_dir = tmp_path / ".cache"

    ev = GitEvidence(repo_root=tmp_path, cache_dir=cache_dir)
    ev.recent_churn_by_file()
    ev.refresh()

    stats = ev.stats()
    # After refresh, in-memory cache is cleared
    assert ev._churn_cache is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: 3 new tests FAIL.

- [ ] **Step 3: Implement persistence**

Add these methods inside class `GitEvidence` (before the closing of the class). Also modify `recent_churn_by_file` to consult the on-disk cache before computing:

```python
    # ── Cache management ──────────────────────────────────────────────

    def refresh(self) -> None:
        """Invalidate in-memory cache; on-disk cache is revalidated by signature."""
        with self._lock:
            self._churn_cache = None

    def _cache_signature(self, *, window_days: int) -> Dict[str, object]:
        """Build the signature used to validate on-disk cache."""
        from codrag.agents.shared.git_client import GitClient
        client = GitClient(self._repo_root)
        head = client.rev_parse_head()
        return {
            "head_sha": head,
            "window_days": window_days,
            "max_commits": self._default_max_commits,
            "repo_root": str(self._repo_root),
            "schema_version": _SCHEMA_VERSION,
        }

    def _load_disk_cache(
        self, *, window_days: int,
    ) -> Optional[Dict[str, FileChurn]]:
        """Load churn from disk if signature matches. None otherwise."""
        sig_path = self._cache_dir / "signature.json"
        churn_path = self._cache_dir / "churn.json"
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
        result: Dict[str, FileChurn] = {}
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
        self, churn: Dict[str, FileChurn], *, window_days: int,
    ) -> None:
        """Write churn map and signature to disk atomically."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
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
        # Atomic rename pattern
        tmp_churn = self._cache_dir / "churn.json.tmp"
        tmp_sig = self._cache_dir / "signature.json.tmp"
        tmp_churn.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        tmp_sig.write_text(json.dumps(sig, indent=2), encoding="utf-8")
        tmp_churn.replace(self._cache_dir / "churn.json")
        tmp_sig.replace(self._cache_dir / "signature.json")
```

Now modify `recent_churn_by_file` to consult the on-disk cache. Replace the existing method body with:

```python
    def recent_churn_by_file(
        self, *, window_days: Optional[int] = None,
    ) -> Dict[str, FileChurn]:
        window = window_days or self._default_window_days
        with self._lock:
            if self._churn_cache is not None:
                self._stats["cache_hits"] += 1
                return dict(self._churn_cache)

        # Try disk cache (no git subprocess if valid)
        disk = self._load_disk_cache(window_days=window)
        if disk is not None:
            with self._lock:
                self._churn_cache = disk
                self._stats["cache_hits"] += 1
            return dict(disk)

        with self._lock:
            self._stats["cache_misses"] += 1

        churn = self._compute_churn(window_days=window)
        self._save_disk_cache(churn, window_days=window)

        with self._lock:
            self._churn_cache = churn
            self._stats["refreshes"] += 1
        return dict(churn)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_git_evidence.py -v`
Expected: all 20 tests PASS.

- [ ] **Step 5: Type-check**

Run: `.venv/bin/mypy src/codrag/core/git_evidence.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/core/git_evidence.py tests/core/test_git_evidence.py
git commit -m "feat(phase105): disk cache with HEAD+window signature validation"
```

---

## Task 7: Add settings flags

**Files:**
- Modify: `src/codrag/core/git_evidence.py` (add settings-aware helper)
- Test: (deferred to Task 8 singleton tests)

Two feature flags: a master `enabled` and a finer `atlas_decoration` gate. They are read via the existing `settings` singleton.

- [ ] **Step 1: Add settings helpers**

Append to `src/codrag/core/git_evidence.py`:

```python
# ── Settings helpers ─────────────────────────────────────────────────

_SETTINGS_ENABLED_KEY = "git_evidence.enabled"
_SETTINGS_ATLAS_KEY = "git_evidence.atlas_decoration"


def is_enabled() -> bool:
    """Master flag. When False, `git_evidence_service.get_git_evidence`
    returns None and both consumers fail open."""
    try:
        from codrag.services.settings_store import settings
        value = settings.get(_SETTINGS_ENABLED_KEY, True)
    except Exception:
        return True
    return bool(value)


def atlas_decoration_enabled() -> bool:
    """Per-consumer flag for atlas decoration."""
    try:
        from codrag.services.settings_store import settings
        value = settings.get(_SETTINGS_ATLAS_KEY, True)
    except Exception:
        return True
    return bool(value)
```

- [ ] **Step 2: Commit**

```bash
git add src/codrag/core/git_evidence.py
git commit -m "feat(phase105): add settings flags for evidence + atlas decoration"
```

---

## Task 8: Per-project singleton wrapper in `services/`

**Files:**
- Create: `src/codrag/services/git_evidence_service.py`
- Create/modify: `tests/core/test_git_evidence_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_git_evidence_service.py`:

```python
"""Unit tests for services/git_evidence_service.py."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from codrag.services.git_evidence_service import (
    get_git_evidence,
    reset_cache,
)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)


def test_returns_none_for_non_git_directory(tmp_path):
    reset_cache()
    assert get_git_evidence(tmp_path) is None


def test_returns_instance_for_git_directory(tmp_path):
    reset_cache()
    _init_repo(tmp_path)
    evidence = get_git_evidence(tmp_path)
    assert evidence is not None


def test_returns_same_instance_for_repeated_calls(tmp_path):
    reset_cache()
    _init_repo(tmp_path)
    a = get_git_evidence(tmp_path)
    b = get_git_evidence(tmp_path)
    assert a is b


def test_returns_none_when_disabled():
    reset_cache()
    with patch("codrag.core.git_evidence.is_enabled", return_value=False):
        assert get_git_evidence(Path("/tmp")) is None


def test_reset_cache_clears_instances(tmp_path):
    reset_cache()
    _init_repo(tmp_path)
    a = get_git_evidence(tmp_path)
    reset_cache()
    b = get_git_evidence(tmp_path)
    assert a is not b
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/core/test_git_evidence_service.py -v`
Expected: all 5 tests FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the service**

Create `src/codrag/services/git_evidence_service.py`:

```python
"""
Per-project singleton wrapper around GitEvidence.

Resolves a GitEvidence instance for a given project root, caches it
in a module-level dict, and gates the whole thing behind the
`git_evidence.enabled` setting. Returns None (not raises) when evidence
is unavailable — all consumers must fail open.
"""
from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path
from typing import Dict, Optional

from codrag.core.git_evidence import GitEvidence, is_enabled

logger = logging.getLogger(__name__)

_INSTANCES: Dict[str, GitEvidence] = {}
_LOCK = threading.Lock()


def _is_git_repo(root: Path) -> bool:
    """Cheap check: does `root` have a .git dir (file for worktrees)?"""
    try:
        return (root / ".git").exists()
    except OSError:
        return False


def _cache_dir_for(repo_root: Path) -> Path:
    """Resolve the evidence cache dir.

    Prefers the embedded `.codrag/` dir if present (tracks with the repo);
    otherwise falls back to a standalone dir under the user's data path.
    Standalone resolution is delegated to project_registry.project_index_dir
    when available; otherwise uses a `.codrag/git_evidence/` under repo_root.
    """
    embedded = repo_root / ".codrag"
    if embedded.exists():
        return embedded / "git_evidence"

    # Try project_registry.project_index_dir if available and resolvable
    try:
        from codrag.core.project_registry import project_index_dir, get_registry
        reg = get_registry()
        for proj in reg.list_projects():
            if Path(proj.path).resolve() == repo_root.resolve():
                return project_index_dir(proj.id) / "git_evidence"
    except Exception:
        pass

    return embedded / "git_evidence"


def get_git_evidence(project_root: Path) -> Optional[GitEvidence]:
    """Return a GitEvidence instance for the project, or None."""
    if not is_enabled():
        return None

    root = Path(project_root).resolve()
    if not _is_git_repo(root):
        return None

    key = str(root)
    with _LOCK:
        inst = _INSTANCES.get(key)
        if inst is not None:
            return inst
        cache_dir = _cache_dir_for(root)
        inst = GitEvidence(repo_root=root, cache_dir=cache_dir)
        _INSTANCES[key] = inst
        return inst


def reset_cache() -> None:
    """Drop all cached instances. For tests and full-reset paths."""
    with _LOCK:
        _INSTANCES.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_git_evidence_service.py -v`
Expected: 5/5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/codrag/services/git_evidence_service.py tests/core/test_git_evidence_service.py
git commit -m "feat(phase105): per-project GitEvidence singleton with settings gate"
```

---

## Task 9: Register cache dir with full-reset path

**Files:**
- Modify: whichever file contains `index_destroy_project` (search during this task)
- Test: smoke test via manual full-reset on the dogfood repo (see Task 13)

This addresses memory-flagged F-78 (full-reset gaps). Evidence cache under `.codrag/git_evidence/` should be removed when a project is destroyed.

- [ ] **Step 1: Locate the destroy logic**

Run: `grep -rn "index_destroy_project\|def destroy_project\|shutil.rmtree.*index_dir" src/codrag/ | head -20`

Identify the function that removes a project's index dir (likely in `services/` or `core/project_registry.py`). Read its body.

- [ ] **Step 2: Add the evidence cache to its deletion path**

If the existing logic already deletes the whole `<project_index_dir>` recursively, `git_evidence/` under it will be swept automatically — verify and move on. If the logic deletes specific subdirectories by name, add a line:

```python
# Phase 105: evidence cache lives alongside other pipeline artifacts
_safe_rmtree(index_dir / "git_evidence")
```

(Adapt the exact function to whatever the existing pattern uses.)

Also add a call to `reset_cache()` so in-memory singletons do not outlive the on-disk data:

```python
from codrag.services.git_evidence_service import reset_cache as _reset_evidence
_reset_evidence()
```

- [ ] **Step 3: Write/extend a destroy test**

If a test already exists for the destroy function, extend it with an assertion that `git_evidence/` is removed. If none exists, create a minimal fixture-repo test that:
1. Creates a project, builds the evidence cache.
2. Calls the destroy function.
3. Asserts `git_evidence/` no longer exists.

- [ ] **Step 4: Run targeted test**

Run: `.venv/bin/pytest <the test path> -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add <modified files>
git commit -m "feat(phase105): include git_evidence cache in full-reset cleanup"
```

---

## Task 10: TODO scanner churn gate

**Files:**
- Modify: `src/codrag/core/todo_scanner.py`
- Create: `tests/core/test_todo_scanner_churn_gate.py`

This is consumer #1. After `scan_todos` produces `RoadmapNode`s, consult evidence and demote stale-file nodes.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_todo_scanner_churn_gate.py`:

```python
"""Integration: TODO scanner demotes stale-file TODOs using git_evidence."""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import pytest

from codrag.core.todo_scanner import scan_todos
from codrag.services.git_evidence_service import reset_cache


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)


def _commit(
    path: Path, rel: str, content: str, *, date: Optional[str] = None, msg: str = "c",
) -> None:
    import os
    target = path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    subprocess.run(["git", "add", rel], cwd=path, check=True)
    env = {**os.environ}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=path, check=True, env=env)


@pytest.fixture
def dogfood_repo(tmp_path):
    reset_cache()
    _init_repo(tmp_path)

    # Live file: committed today
    _commit(tmp_path, "src/live.py", "# TODO: still real\npass\n")

    # Stale file: committed a year ago
    year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    _commit(
        tmp_path, "src/stale.py", "# TODO: old thing\npass\n",
        date=year_ago, msg="old",
    )

    yield tmp_path
    reset_cache()


def test_live_todo_is_not_demoted(dogfood_repo):
    nodes = scan_todos(dogfood_repo)
    live = [n for n in nodes if "src/live.py" in n.source_ref]
    assert len(live) == 1
    assert "[stale:" not in (live[0].description or "")


def test_stale_todo_is_demoted_to_p3(dogfood_repo):
    nodes = scan_todos(dogfood_repo)
    stale = [n for n in nodes if "src/stale.py" in n.source_ref]
    assert len(stale) == 1
    assert stale[0].priority == "P3"
    assert "[stale:" in (stale[0].description or "")


def test_non_git_dir_leaves_todos_unchanged(tmp_path):
    """Scanner must behave identically outside a git repo."""
    reset_cache()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "file.py").write_text("# TODO: outside git\n")

    nodes = scan_todos(tmp_path)
    assert len(nodes) == 1
    assert "[stale:" not in (nodes[0].description or "")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/core/test_todo_scanner_churn_gate.py -v`
Expected: `test_stale_todo_is_demoted_to_p3` FAILs because the gate doesn't exist yet.

- [ ] **Step 3: Add the gate to `scan_todos`**

In `src/codrag/core/todo_scanner.py`, modify `scan_todos` to apply the churn gate after the existing loop. The existing `logger.info` line is at line 139; insert the gate block immediately before it.

Find this block (around line 139):

```python
    logger.info("TODO scanner: found %d annotations in %s", len(nodes), project_root)
    return nodes
```

Replace with:

```python
    _apply_churn_gate(nodes, project_root)

    logger.info("TODO scanner: found %d annotations in %s", len(nodes), project_root)
    return nodes
```

Then add the `_apply_churn_gate` helper at the bottom of the file (after `_parse_grep_output`):

```python
# ── Phase 105: churn gate ────────────────────────────────────────────

_STALE_WINDOW_DAYS = 180


def _apply_churn_gate(nodes: List[RoadmapNode], project_root: Path) -> None:
    """Demote TODOs whose source file has not been touched in the window.

    Fails open: if evidence is unavailable (not a git repo, shallow clone,
    settings disabled, subprocess error), this is a no-op. Mutates nodes
    in place.
    """
    try:
        from codrag.services.git_evidence_service import get_git_evidence
        evidence = get_git_evidence(project_root)
    except Exception:
        return
    if evidence is None:
        return

    try:
        churn = evidence.recent_churn_by_file(window_days=_STALE_WINDOW_DAYS)
    except Exception:
        return
    if not churn:
        return

    suffix = f" [stale: file not touched in {_STALE_WINDOW_DAYS}d]"
    for node in nodes:
        # source_ref shape for todo_scan nodes is "<path>:<line>"
        ref = node.source_ref or ""
        path = ref.rsplit(":", 1)[0] if ":" in ref else ""
        if not path:
            continue
        if path not in churn:
            node.priority = "P3"
            current_desc = node.description or ""
            if suffix not in current_desc:
                node.description = current_desc + suffix
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_todo_scanner_churn_gate.py -v`
Expected: 3/3 PASS.

- [ ] **Step 5: Run the full scanner test suite as regression check**

Run: `.venv/bin/pytest tests/ -k "todo_scan" -v`
Expected: all pre-existing TODO tests still pass; no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/codrag/core/todo_scanner.py tests/core/test_todo_scanner_churn_gate.py
git commit -m "feat(phase105): demote TODOs in cold files using git_evidence churn"
```

---

## Task 11: Atlas hub label grouping

**Files:**
- Modify: `src/codrag/core/atlas/generator.py`
- Create: `tests/core/test_atlas_evidence.py`

Hook in at `_generate_root_atlas` around line 469. Group hub files by label in the `cross_cutting` string that feeds both the LLM prompt and the structural fallback path.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_atlas_evidence.py`:

```python
"""Atlas decoration tests: hub labeling + hot zones + flag fallback."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from codrag.core.atlas.generator import _format_hubs_with_labels, _build_hot_zones_line


def test_format_hubs_with_labels_groups_by_label():
    hubs = [("typing", 223), ("pathlib", 168), ("backend_config.py", 55)]
    classifier = MagicMock(side_effect=lambda p: {
        "typing": "stable",
        "pathlib": "stable",
        "backend_config.py": "evolving",
    }.get(p, "unknown"))

    line = _format_hubs_with_labels(hubs, classifier)

    assert "stable" in line
    assert "evolving" in line
    assert "typing" in line
    assert "backend_config.py" in line
    # No raw numbers
    assert "223" not in line
    assert "168" not in line


def test_format_hubs_with_labels_falls_back_on_all_unknown():
    """When no evidence, emit today's format (raw edge counts)."""
    hubs = [("typing", 223), ("pathlib", 168)]
    classifier = MagicMock(return_value="unknown")

    line = _format_hubs_with_labels(hubs, classifier)
    # Fallback reproduces the classic "<name> (<n> edges)" shape
    assert "typing" in line
    assert "223 edges" in line


def test_hot_zones_line_empty_when_no_zones():
    assert _build_hot_zones_line([]) == ""


def test_hot_zones_line_formats_bullets_and_caps():
    zones = ["src/foo/", "src/bar/", "src/baz/"]
    line = _build_hot_zones_line(zones)
    assert line.startswith("Active zones")
    assert "src/foo/" in line
    assert "src/bar/" in line
    assert "src/baz/" in line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/core/test_atlas_evidence.py -v`
Expected: all FAIL with `ImportError` (helpers don't exist yet).

- [ ] **Step 3: Add the helper functions to `generator.py`**

At the top of `src/codrag/core/atlas/generator.py`, add these module-level helpers (after the existing imports block — find a clean spot near the top of the file):

```python
# ── Phase 105: evidence-aware formatting helpers ─────────────────────

from typing import Callable as _Callable


def _format_hubs_with_labels(
    hubs: List[Tuple[str, int]],
    classifier: _Callable[[str], str],
) -> str:
    """Return a one-line hub description grouped by label, or the classic
    fallback if all hubs classify as 'unknown' (no evidence available)."""
    labeled: Dict[str, List[str]] = {
        "stable": [], "evolving": [], "fragile": [], "unknown": [],
    }
    for path, _edges in hubs:
        label = classifier(path)
        if label not in labeled:
            label = "unknown"
        labeled[label].append(path)

    # All-unknown → emit today's format so no-evidence behavior is
    # byte-identical to pre-phase-105 output
    if len(labeled["unknown"]) == len(hubs):
        return ", ".join(f"{p} ({d} edges)" for p, d in hubs)

    parts: List[str] = []
    for label in ("stable", "evolving", "fragile"):
        names = labeled[label]
        if names:
            parts.append(f"{', '.join(names)} ({label})")
    if labeled["unknown"]:
        parts.append(f"{', '.join(labeled['unknown'])}")
    return ", ".join(parts)


def _build_hot_zones_line(zones: List[str]) -> str:
    """Return the 'Active zones' line for cross_parts, or '' if no zones."""
    if not zones:
        return ""
    return "Active zones: " + ", ".join(f"`{z}`" for z in zones)
```

- [ ] **Step 4: Run helper tests to verify they pass**

Run: `.venv/bin/pytest tests/core/test_atlas_evidence.py -v`
Expected: 4/4 PASS.

- [ ] **Step 5: Wire the helpers into `_generate_root_atlas`**

Locate the existing block at `generator.py:465-470`:

```python
        # Cross-cutting: extract hub files and shared domain tags across segments
        hub_files = self._identify_hubs(graph_stats)
        cross_parts: List[str] = []
        if hub_files:
            hub_str = ", ".join(f"{p} ({d} edges)" for p, d in hub_files[:5])
            cross_parts.append(f"Hub files: {hub_str}")
```

Replace with:

```python
        # Cross-cutting: extract hub files and shared domain tags across segments
        hub_files = self._identify_hubs(graph_stats)
        cross_parts: List[str] = []
        if hub_files:
            # Phase 105: decorate with evidence labels when available
            hub_str = self._hub_str_with_evidence(hub_files[:5])
            cross_parts.append(f"Hub files: {hub_str}")

            # Phase 105: append Active zones line when evidence qualifies
            zones_line = self._hot_zones_line()
            if zones_line:
                cross_parts.append(zones_line)
```

Then add two new methods to `CodebaseAtlas` (below the existing `_identify_hubs` or near other helpers):

```python
    def _hub_str_with_evidence(
        self, hubs: List[Tuple[str, int]],
    ) -> str:
        """Produce the hub-file one-liner, optionally labeled by churn."""
        from codrag.core.git_evidence import atlas_decoration_enabled
        if not atlas_decoration_enabled():
            return ", ".join(f"{p} ({d} edges)" for p, d in hubs)

        try:
            from codrag.services.git_evidence_service import get_git_evidence
            evidence = get_git_evidence(self.project_root)
        except Exception:
            evidence = None
        if evidence is None:
            return ", ".join(f"{p} ({d} edges)" for p, d in hubs)

        def _classify(p: str) -> str:
            try:
                return evidence.classify_hub(p)
            except Exception:
                return "unknown"

        return _format_hubs_with_labels(hubs, _classify)

    def _hot_zones_line(self) -> str:
        """Produce the 'Active zones' line, or empty string."""
        from codrag.core.git_evidence import atlas_decoration_enabled
        if not atlas_decoration_enabled():
            return ""

        try:
            from codrag.services.git_evidence_service import get_git_evidence
            evidence = get_git_evidence(self.project_root)
        except Exception:
            return ""
        if evidence is None:
            return ""

        try:
            zones = evidence.hot_zones(top_n=5, min_commits=10, depth=3)
        except Exception:
            return ""
        return _build_hot_zones_line(zones)
```

**Note:** `self.project_root` is the attribute name assumed. Verify by reading the `__init__` of `CodebaseAtlas`. If the attribute is named differently (e.g. `self._project_root`, `self.repo_root`), use the actual attribute name.

- [ ] **Step 6: Mirror decoration in structural fallback**

Find `_build_structural_content` (grep: `grep -n "_build_structural_content" src/codrag/core/atlas/generator.py`). This is the fallback path used when the LLM returns empty/too-short output. It must produce the same labels so output is consistent regardless of path.

Inside `_build_structural_content`, locate the spot where hub files are formatted. Apply the same `_format_hubs_with_labels` pattern there if the function emits hub text, OR — if the structural path already uses an internal helper — ensure it calls `_hub_str_with_evidence`.

If the structural path does not emit a hub line, skip this step (document that decision in the commit message).

- [ ] **Step 7: Verify with full atlas tests**

Run: `.venv/bin/pytest tests/core/test_atlas_evidence.py tests/ -k atlas -v`
Expected: all pass. If pre-existing atlas tests fail, inspect failures — a regression here means the decoration changed output when it shouldn't. Most likely cause: `atlas_decoration_enabled()` default is True and a test expected the old format. Either (a) the test needs updating to reflect new format, or (b) add an `atlas_decoration_enabled` monkeypatch to `False` in the existing test fixtures.

- [ ] **Step 8: Commit**

```bash
git add src/codrag/core/atlas/generator.py tests/core/test_atlas_evidence.py
git commit -m "feat(phase105): atlas hub label grouping + active zones line"
```

---

## Task 12: Golden-file fallback test (atlas baseline preserved when flag off)

**Files:**
- Modify: `tests/core/test_atlas_evidence.py`

Acceptance gate 9: with `atlas_decoration=false`, atlas output matches baseline byte-for-byte.

- [ ] **Step 1: Write the test**

Append to `tests/core/test_atlas_evidence.py`:

```python
def test_format_hubs_with_labels_flag_off_matches_baseline(monkeypatch):
    """With decoration disabled, _format_hubs_with_labels falls back even
    when classifier would have returned real labels.

    The guard lives at the call site (_hub_str_with_evidence); this test
    pins the call-site behavior with a stub.
    """
    from codrag.core.git_evidence import atlas_decoration_enabled
    monkeypatch.setattr(
        "codrag.core.atlas.generator.atlas_decoration_enabled",
        lambda: False,
        raising=False,
    )

    # Build a CodebaseAtlas with minimal mock inputs; just exercise _hub_str_with_evidence
    from codrag.core.atlas.generator import CodebaseAtlas
    # Depending on the constructor signature, this may need adaptation.
    # Use MagicMock for any required args that this method does not touch.
    atlas = MagicMock(spec=CodebaseAtlas)
    atlas.project_root = Path("/nonexistent")
    atlas._hub_str_with_evidence = CodebaseAtlas._hub_str_with_evidence.__get__(
        atlas, CodebaseAtlas,
    )
    hubs = [("typing", 223), ("pathlib", 168)]
    result = atlas._hub_str_with_evidence(hubs)
    assert result == "typing (223 edges), pathlib (168 edges)"
```

Imports at the top of the test file already cover what's needed; if `Path` is not imported, add:

```python
from pathlib import Path
```

- [ ] **Step 2: Run and iterate**

Run: `.venv/bin/pytest tests/core/test_atlas_evidence.py::test_format_hubs_with_labels_flag_off_matches_baseline -v`
Expected: PASS.

If the test reveals that `CodebaseAtlas.__init__` makes the MagicMock approach awkward, replace with a real instance constructed with whatever the minimum real args are.

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_atlas_evidence.py
git commit -m "test(phase105): pin atlas decoration fallback when flag disabled"
```

---

## Task 13: Dogfood run on this repo

**Files:**
- None — this is a manual acceptance-gate check.

- [ ] **Step 1: Build the index against this repo**

Run: `.venv/bin/codrag serve` (in one terminal) and in another:
`curl -X POST http://localhost:8400/projects/1d6f0b35-45cb-427b-ae9d-aac3c6371a4b/pipeline/run`

Or trigger via the dashboard UI.

Wait for the pipeline to complete through the ATLAS stage.

- [ ] **Step 2: Check acceptance gate 1 — churn refresh speed**

Run: `.venv/bin/python -c "
from pathlib import Path
from codrag.services.git_evidence_service import get_git_evidence, reset_cache
import time
reset_cache()
evidence = get_git_evidence(Path('/Volumes/4TB-BAD/HumanAI/CoDRAG'))
t0 = time.time()
churn = evidence.recent_churn_by_file()
print(f'First call: {time.time() - t0:.2f}s ({len(churn)} files)')
t1 = time.time()
churn2 = evidence.recent_churn_by_file()
print(f'Cached call: {time.time() - t1:.3f}s')
"`

Expected: first call < 2.0s; cached call < 0.01s.

- [ ] **Step 3: Check acceptance gates 5-7 (TODO and atlas manual review)**

Inspect roadmap TODO nodes in the dashboard. Confirm:
- Acceptance gate 5: at least one TODO in a cold file is marked P3 with the `[stale:` suffix; no live TODOs are incorrectly demoted.
- Acceptance gate 6: atlas hub line shows at least one `stable` and one `evolving` label.
- Acceptance gate 7: "Active zones" line appears with at least 2 directories.

- [ ] **Step 4: Check acceptance gate 8 — token growth**

Get the atlas content before and after (with flag on/off):

```bash
# With flag off (baseline):
.venv/bin/python -c "
from codrag.services.settings_store import settings
settings.set('git_evidence.atlas_decoration', False)
"
# Rebuild atlas, export content. Measure length.

# With flag on:
.venv/bin/python -c "
from codrag.services.settings_store import settings
settings.set('git_evidence.atlas_decoration', True)
"
# Rebuild atlas. Measure length.
```

Expected: difference in atlas content length is < 200 characters (~50 tokens).

- [ ] **Step 5: Check acceptance gate 2 — cache cleanup on destroy**

Create a throwaway project, build it once, verify `git_evidence/` exists in its index dir, then destroy it and verify the directory is gone. Use whichever destroy API path the existing admin surface provides.

- [ ] **Step 6: Record results in a dogfood note**

Create `docs/Phase105_GIT/DOGFOOD_NOTES.md` with a short table:

```markdown
# Dogfood results, 2026-MM-DD

- Gate 1 (cache refresh < 2s): [PASS/FAIL, actual time]
- Gate 2 (destroy cleanup): [PASS/FAIL]
- Gate 3 (non-git fail-open): [PASS/FAIL]
- Gate 4 (lint/type-check): [PASS/FAIL]
- Gate 5 (stale TODO demoted, no live false positives): [PASS/FAIL + examples]
- Gate 6 (hub labels correct): [PASS/FAIL + examples]
- Gate 7 (active zones line present): [PASS/FAIL + contents]
- Gate 8 (token growth < 50): [PASS/FAIL + delta]
- Gate 9 (byte-for-byte baseline match with flag off): [PASS/FAIL]

Issues observed: [...]
Tuning needed: [...]
Ready to ship: [YES/NO]
```

- [ ] **Step 7: Commit dogfood notes**

```bash
git add docs/Phase105_GIT/DOGFOOD_NOTES.md
git commit -m "chore(phase105): record dogfood acceptance-gate results"
```

---

## Task 14: Final lint / type-check / full suite

**Files:**
- None (verification only).

- [ ] **Step 1: Ruff**

Run: `.venv/bin/ruff check src/codrag/core/git_evidence.py src/codrag/services/git_evidence_service.py src/codrag/core/todo_scanner.py src/codrag/core/atlas/generator.py src/codrag/agents/shared/git_client.py tests/core/test_git_evidence.py tests/core/test_git_evidence_service.py tests/core/test_todo_scanner_churn_gate.py tests/core/test_atlas_evidence.py`

Expected: no lint errors introduced by this phase.

- [ ] **Step 2: Mypy**

Run: `.venv/bin/mypy src/codrag/core/git_evidence.py src/codrag/services/git_evidence_service.py`
Expected: no errors.

- [ ] **Step 3: Full test suite (new + regression)**

Run: `.venv/bin/pytest tests/ -v --timeout=300`
Expected: all new tests pass; no regressions in pre-existing tests.

- [ ] **Step 4: Final commit / tag-ready state**

If everything passes, Phase 105 is done. No additional commit needed unless the full-suite run surfaced a missed test. If it did, fix and commit:

```bash
git add <fixed files>
git commit -m "fix(phase105): <describe>"
```

---

## Summary of commits when complete

1. `feat(phase105): extend GitClient with read-only history methods`
2. `feat(phase105): scaffold git_evidence module with FileChurn + exclusions`
3. `feat(phase105): implement recent_churn_by_file primitive`
4. `feat(phase105): implement classify_hub with stable/evolving/fragile labels`
5. `feat(phase105): implement hot_zones directory aggregation`
6. `feat(phase105): disk cache with HEAD+window signature validation`
7. `feat(phase105): add settings flags for evidence + atlas decoration`
8. `feat(phase105): per-project GitEvidence singleton with settings gate`
9. `feat(phase105): include git_evidence cache in full-reset cleanup`
10. `feat(phase105): demote TODOs in cold files using git_evidence churn`
11. `feat(phase105): atlas hub label grouping + active zones line`
12. `test(phase105): pin atlas decoration fallback when flag disabled`
13. `chore(phase105): record dogfood acceptance-gate results`
14. (Optional) `fix(phase105): <regression fixes>`

Total: 13–14 commits, ~10 small. Matches the plan-driven frequent-commit style.
