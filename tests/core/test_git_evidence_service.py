"""Unit tests for services/git_evidence_service.py."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

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
