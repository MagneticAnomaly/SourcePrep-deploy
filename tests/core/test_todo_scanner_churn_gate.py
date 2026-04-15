"""Integration: TODO scanner demotes stale-file TODOs using git_evidence."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from codrag.core.todo_scanner import scan_todos
from codrag.services.git_evidence_service import reset_cache


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)


def _commit(
    path: Path, rel: str, content: str, *, date: str | None = None, msg: str = "c",
) -> None:
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
    live = [n for n in nodes if "src/live.py" in (n.source_ref or "")]
    assert len(live) == 1
    assert "[stale:" not in (live[0].description or "")


def test_stale_todo_is_demoted_to_p3(dogfood_repo):
    nodes = scan_todos(dogfood_repo)
    stale = [n for n in nodes if "src/stale.py" in (n.source_ref or "")]
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
