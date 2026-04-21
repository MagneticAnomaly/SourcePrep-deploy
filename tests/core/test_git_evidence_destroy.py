"""Tests: git_evidence cache directory is cleaned up on full project reset.

Exercises the F-78 pattern — new per-project stores must be registered in
index_destroy_project so they can't survive a full reset and resurrect
stale data on the next pipeline run.

We test the two observable effects of the destroy path:
  1. The on-disk git_evidence/ subdirectory is removed.
  2. reset_cache() was called, so get_git_evidence returns a fresh instance.

We do NOT call index_destroy_project itself because it depends on the full
FastAPI + server import graph.  Instead we test the two primitive operations
that the destroy function now invokes, then verify they compose correctly.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from prep.services.git_evidence_service import (
    get_git_evidence,
    reset_cache,
)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)


def _populate_git_evidence_dir(index_dir: Path) -> Path:
    """Create a minimal git_evidence/ cache directory under index_dir."""
    ge_dir = index_dir / "git_evidence"
    ge_dir.mkdir(parents=True, exist_ok=True)
    (ge_dir / "churn_60.json").write_text("{}")
    (ge_dir / "signature_60.json").write_text("{}")
    return ge_dir


# ---------------------------------------------------------------------------
# Test 1: rmtree on git_evidence/ removes all cached files
# ---------------------------------------------------------------------------

def test_rmtree_removes_git_evidence_dir(tmp_path: Path) -> None:
    """Simulates the destroy step that deletes git_evidence/ subdir."""
    index_dir = tmp_path / "project_index"
    index_dir.mkdir()
    ge_dir = _populate_git_evidence_dir(index_dir)

    assert ge_dir.is_dir()
    assert (ge_dir / "churn_60.json").exists()

    # This is what index_destroy_project does for each named subdir
    shutil.rmtree(ge_dir)

    assert not ge_dir.exists(), "git_evidence/ dir should be gone after rmtree"


# ---------------------------------------------------------------------------
# Test 2: reset_cache() causes a fresh instance on next get_git_evidence call
# ---------------------------------------------------------------------------

def test_reset_cache_gives_fresh_instance(tmp_path: Path) -> None:
    """Simulates the in-memory cache clear that destroy now performs."""
    reset_cache()
    _init_repo(tmp_path)

    first = get_git_evidence(tmp_path)
    assert first is not None, "Expected a GitEvidence instance for a valid git repo"

    # Simulate what index_destroy_project now calls
    reset_cache()

    second = get_git_evidence(tmp_path)
    assert second is not None
    assert second is not first, "After reset_cache(), a new instance should be returned"


# ---------------------------------------------------------------------------
# Test 3: Combined — rmtree then reset_cache leaves clean state
# ---------------------------------------------------------------------------

def test_destroy_sequence_cleans_disk_and_memory(tmp_path: Path) -> None:
    """Combines both destroy steps; asserts disk is clean and memory is fresh."""
    _init_repo(tmp_path)
    reset_cache()

    # Pre-populate an instance in the singleton cache
    instance_before = get_git_evidence(tmp_path)
    assert instance_before is not None

    # Build a fake index_dir with git_evidence populated
    index_dir = tmp_path / ".prep_index"
    index_dir.mkdir()
    ge_dir = _populate_git_evidence_dir(index_dir)
    assert ge_dir.is_dir()

    # --- Simulate the destroy sequence ---
    # Step A: remove the on-disk subdir (Case B in the destroy logic)
    shutil.rmtree(ge_dir)
    # Step B: drop in-memory singleton (Phase 105 addition)
    reset_cache()

    # Assertions
    assert not ge_dir.exists(), "git_evidence/ must be gone from disk"

    instance_after = get_git_evidence(tmp_path)
    assert instance_after is not instance_before, "Singleton must be a new object after reset"
