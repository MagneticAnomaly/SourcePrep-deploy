"""Tests for mtime-based index staleness detection (Phase 24).

Verifies that ``check_index_staleness`` correctly detects when scoped
files have been modified after the last index build, independent of
the AutoRebuildWatcher.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Minimal stubs so we can test the staleness logic without FastAPI / full deps
# ---------------------------------------------------------------------------

class _FakeCodeIndex:
    """Minimal CodeIndex stub that returns configurable stats."""

    def __init__(self, built_at: Optional[str] = None, loaded: bool = True):
        self._built_at = built_at
        self._loaded = loaded

    def stats(self) -> Dict[str, Any]:
        return {"built_at": self._built_at, "loaded": self._loaded}


class _FakeProject:
    """Minimal Project stub."""

    def __init__(self, project_id: str, path: str, config: Optional[Dict[str, Any]] = None):
        self.id = project_id
        self.path = path
        self.config = config or {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo_dir(tmp_path: Path) -> Path:
    """Create a minimal repo with a few files."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text("# Hello")
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_build_yet_is_not_stale(repo_dir: Path):
    """If the index has never been built, staleness should be False."""
    from prep.services.project_helpers import check_index_staleness, invalidate_stale_cache

    proj = _FakeProject("test1", str(repo_dir), {"include_globs": ["**/*.py", "**/*.md"]})
    idx = _FakeCodeIndex(built_at=None, loaded=False)

    result = check_index_staleness(proj, idx)
    assert result["is_stale"] is False
    assert result["stale_count"] == 0

    # Cleanup cache
    invalidate_stale_cache("test1")


def test_fresh_after_build(repo_dir: Path):
    """Files that existed before built_at should NOT be stale."""
    from prep.services.project_helpers import check_index_staleness, invalidate_stale_cache

    # Set file mtimes to the past
    past = time.time() - 60
    for f in repo_dir.rglob("*"):
        if f.is_file():
            import os
            os.utime(f, (past, past))

    # built_at is "now" (after the files were last modified)
    built_at = datetime.now(timezone.utc).isoformat()

    proj = _FakeProject("test2", str(repo_dir), {"include_globs": ["**/*.py", "**/*.md"]})
    idx = _FakeCodeIndex(built_at=built_at, loaded=True)

    result = check_index_staleness(proj, idx)
    assert result["is_stale"] is False
    assert result["stale_count"] == 0

    invalidate_stale_cache("test2")


def test_stale_after_file_edit(repo_dir: Path):
    """Editing a file after built_at should make the index stale."""
    from prep.services.project_helpers import check_index_staleness, invalidate_stale_cache

    # Set files to the past
    past = time.time() - 60
    for f in repo_dir.rglob("*"):
        if f.is_file():
            import os
            os.utime(f, (past, past))

    # Build "happened" 30 seconds ago
    built_at = datetime.fromtimestamp(time.time() - 30, tz=timezone.utc).isoformat()

    proj = _FakeProject("test3", str(repo_dir), {"include_globs": ["**/*.py", "**/*.md"]})
    idx = _FakeCodeIndex(built_at=built_at, loaded=True)

    # Verify fresh first
    result = check_index_staleness(proj, idx)
    assert result["is_stale"] is False
    invalidate_stale_cache("test3")

    # Now edit a file (touch it with current mtime)
    md_file = repo_dir / "docs" / "readme.md"
    md_file.write_text("# Hello — updated!")

    result = check_index_staleness(proj, idx)
    assert result["is_stale"] is True
    assert result["stale_count"] >= 1
    assert result["stale_since"] is not None

    invalidate_stale_cache("test3")


def test_excluded_files_not_counted(repo_dir: Path):
    """Files matching exclude_globs should not trigger staleness."""
    from prep.services.project_helpers import check_index_staleness, invalidate_stale_cache

    # Set files to the past
    past = time.time() - 60
    for f in repo_dir.rglob("*"):
        if f.is_file():
            import os
            os.utime(f, (past, past))

    built_at = datetime.fromtimestamp(time.time() - 30, tz=timezone.utc).isoformat()

    # Exclude .md files
    proj = _FakeProject("test4", str(repo_dir), {
        "include_globs": ["**/*.py", "**/*.md"],
        "exclude_globs": ["**/*.md"],
    })
    idx = _FakeCodeIndex(built_at=built_at, loaded=True)

    # Edit the .md file (excluded)
    (repo_dir / "docs" / "readme.md").write_text("# Excluded change")

    result = check_index_staleness(proj, idx)
    assert result["is_stale"] is False
    assert result["stale_count"] == 0

    invalidate_stale_cache("test4")


def test_dotfiles_not_counted(repo_dir: Path):
    """Dotfiles and dot-directories should be ignored."""
    from prep.services.project_helpers import check_index_staleness, invalidate_stale_cache

    # Set files to the past
    past = time.time() - 60
    for f in repo_dir.rglob("*"):
        if f.is_file():
            import os
            os.utime(f, (past, past))

    built_at = datetime.fromtimestamp(time.time() - 30, tz=timezone.utc).isoformat()

    # Create a dotfile and dot-directory
    (repo_dir / ".env").write_text("SECRET=123")
    dot_dir = repo_dir / ".vscode"
    dot_dir.mkdir()
    (dot_dir / "settings.json").write_text("{}")

    proj = _FakeProject("test5", str(repo_dir), {"include_globs": ["**/*.py", "**/*.md"]})
    idx = _FakeCodeIndex(built_at=built_at, loaded=True)

    result = check_index_staleness(proj, idx)
    # The .env and .vscode files should be ignored (pruned dot-dirs)
    assert result["is_stale"] is False
    assert result["stale_count"] == 0

    invalidate_stale_cache("test5")


def test_trace_manifest_finished_at_detects_stale(repo_dir: Path, monkeypatch):
    """Trace-enabled projects must read the build time from the v2.0 trace
    manifest, which uses ``finished_at`` (not ``built_at``).

    Regression: the staleness reader only looked for ``built_at``; the v2.0
    trace_manifest.json stores ``started_at``/``finished_at`` instead, so
    ``built_at`` was always None and the check short-circuited to
    ``stale_count: 0`` for every trace-enabled project — the mtime walk
    never ran.  Discovered dogfooding SkyPath-Restart (8 edited source
    files showing 0 stale).
    """
    import prep.core.project_registry as _pr
    from prep.services.project_helpers import check_index_staleness, invalidate_stale_cache

    # Index dir holds the trace manifest; point project_index_dir at it.
    idx_dir = repo_dir / ".sourceprep"
    idx_dir.mkdir()
    monkeypatch.setattr(_pr, "project_index_dir", lambda project: idx_dir)

    # All source files predate the build.
    past = time.time() - 60
    import os
    for f in repo_dir.rglob("*"):
        if f.is_file():
            os.utime(f, (past, past))

    # v2.0 manifest: finished_at only, NO built_at key.
    finished_at = datetime.fromtimestamp(time.time() - 30, tz=timezone.utc).isoformat()
    (idx_dir / "trace_manifest.json").write_text(json.dumps({
        "format_version": "2.0",
        "started_at": finished_at,
        "finished_at": finished_at,
    }))

    proj = _FakeProject("test_trace", str(repo_dir), {
        "include_globs": ["**/*.py", "**/*.md"],
        "trace": {"enabled": True},
    })
    idx = _FakeCodeIndex(built_at=None, loaded=True)

    # Fresh first.
    result = check_index_staleness(proj, idx)
    assert result["is_stale"] is False
    invalidate_stale_cache("test_trace")

    # Edit a tracked file after the build.
    (repo_dir / "src" / "main.py").write_text("print('changed')")

    result = check_index_staleness(proj, idx)
    assert result["is_stale"] is True
    assert result["stale_count"] >= 1
    assert result["stale_since"] is not None

    invalidate_stale_cache("test_trace")


def test_cache_returns_same_result(repo_dir: Path):
    """Subsequent calls within TTL should return cached result."""
    from prep.services.project_helpers import check_index_staleness, invalidate_stale_cache

    past = time.time() - 60
    for f in repo_dir.rglob("*"):
        if f.is_file():
            import os
            os.utime(f, (past, past))

    built_at = datetime.fromtimestamp(time.time() - 30, tz=timezone.utc).isoformat()
    proj = _FakeProject("test6", str(repo_dir), {"include_globs": ["**/*.py", "**/*.md"]})
    idx = _FakeCodeIndex(built_at=built_at, loaded=True)

    # First call - should scan
    r1 = check_index_staleness(proj, idx)
    assert r1["is_stale"] is False

    # Edit a file
    (repo_dir / "src" / "main.py").write_text("print('changed')")

    # Second call within cache TTL - should still return cached (not stale)
    r2 = check_index_staleness(proj, idx)
    assert r2["is_stale"] is False  # Still cached

    # Invalidate cache and re-check
    invalidate_stale_cache("test6")
    r3 = check_index_staleness(proj, idx)
    assert r3["is_stale"] is True  # Now detects the change

    invalidate_stale_cache("test6")
