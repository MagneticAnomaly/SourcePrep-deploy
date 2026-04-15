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
