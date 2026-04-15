"""Unit tests for core/git_evidence.py."""
from __future__ import annotations

import dataclasses
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import pytest

from codrag.core.git_evidence import (
    HUB_EVOLVING_MAX_COMMITS,
    HUB_FRAGILE_MIN_AUTHORS,
    HUB_STABLE_MAX_COMMITS,
    FileChurn,
    GitEvidence,
    _is_excluded_path,
)


def test_filechurn_is_frozen_dataclass():
    """FileChurn must be immutable to be safe for caching."""
    now = datetime.now(UTC)
    churn = FileChurn(
        path="src/foo.py",
        commits=5,
        lines_added=100,
        lines_removed=20,
        first_seen=now,
        last_seen=now,
        authors=2,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
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

    # Nested monorepo lockfiles (regression guard for fnmatch depth)
    assert _is_excluded_path("packages/ui/package-lock.json") is True
    assert _is_excluded_path("packages/vscode/yarn.lock") is True
    assert _is_excluded_path("services/billing/deep/nested/poetry.lock") is True


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
    env = {**os.environ}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", "commit", "-q", "--author", author, "-m", message],
        cwd=path, check=True, env=env,
    )


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
