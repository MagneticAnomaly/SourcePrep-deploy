"""Phase 135.5 — verify the central walker enforces the L1 catalog
baseline regardless of caller-supplied excludes, AND that the planning-
docs variant honors the opposite agent-dir policy."""
from __future__ import annotations

from pathlib import Path

import pytest

from prep.core.walker import walk_for_source, walk_for_planning_docs


def _make_repo(tmp_path: Path) -> Path:
    """Create a tmp repo with regular code + agent-output dirs."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("print('hi')")
    (repo / "src" / "lib.py").write_text("pass")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "memory.md").write_text("# memory")
    (repo / ".cursor").mkdir()
    (repo / ".cursor" / "rules.md").write_text("# rules")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "lodash.js").write_text("// huge")
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("# guide")
    return repo


def _paths(entries) -> set[str]:
    """Extract a set of relative paths from walker entries. Walker entries
    are PyO3 objects; their `.path` attribute is the relative file path."""
    out: set[str] = set()
    for e in entries:
        # Handle both attribute-based and dict-based entries defensively
        p = getattr(e, "path", None)
        if p is None and isinstance(e, dict):
            p = e.get("path")
        if p is None:
            continue
        out.add(str(p))
    return out


def test_walk_for_source_always_excludes_agent_dirs(tmp_path: Path) -> None:
    """Even when caller passes user_exclude_globs=None, walk_for_source
    must apply the L1 catalog (.claude/, .cursor/, node_modules/)."""
    repo = _make_repo(tmp_path)
    entries = walk_for_source(repo, include_globs=["**/*.md", "**/*.py", "**/*.js"])
    paths = _paths(entries)
    # src/ contents present
    assert any("src/main.py" in p for p in paths)
    # docs/ contents present
    assert any("docs/guide.md" in p for p in paths)
    # agent dirs absent
    assert not any(".claude/" in p for p in paths)
    assert not any(".cursor/" in p for p in paths)
    # node_modules absent
    assert not any("node_modules/" in p for p in paths)


def test_walk_for_source_with_empty_user_excludes(tmp_path: Path) -> None:
    """Empty user_exclude_globs still gets the catalog applied."""
    repo = _make_repo(tmp_path)
    entries = walk_for_source(
        repo, include_globs=["**/*.md"], user_exclude_globs=[],
    )
    paths = _paths(entries)
    assert any("docs/guide.md" in p for p in paths)
    assert not any(".claude/" in p for p in paths)


def test_walk_for_source_user_excludes_extend_catalog(tmp_path: Path) -> None:
    """User-supplied excludes are unioned with the catalog. Both apply."""
    repo = _make_repo(tmp_path)
    entries = walk_for_source(
        repo,
        include_globs=["**/*.py"],
        user_exclude_globs=["**/lib.py"],  # exclude only one file
    )
    paths = _paths(entries)
    # User exclude applied (lib.py absent)
    assert not any("lib.py" in p for p in paths)
    # Catalog still applied (no .claude/, no node_modules/)
    assert not any(".claude/" in p for p in paths)
    # main.py still present
    assert any("main.py" in p for p in paths)


def test_walk_for_planning_docs_includes_agent_dirs(tmp_path: Path) -> None:
    """The planning-docs variant deliberately INCLUDES .claude/, .cursor/."""
    repo = _make_repo(tmp_path)
    entries = walk_for_planning_docs(repo)
    paths = _paths(entries)
    # Agent dirs INCLUDED
    assert any(".claude/memory.md" in p for p in paths)
    assert any(".cursor/rules.md" in p for p in paths)
    # Regular docs still INCLUDED
    assert any("docs/guide.md" in p for p in paths)
    # node_modules still EXCLUDED (it's not an agent dir)
    assert not any("node_modules" in p for p in paths)


def test_walk_for_planning_docs_with_include_agent_dirs_false(tmp_path: Path) -> None:
    """With include_agent_dirs=False, behaves like walk_for_source."""
    repo = _make_repo(tmp_path)
    entries = walk_for_planning_docs(repo, include_agent_dirs=False)
    paths = _paths(entries)
    # No agent dirs
    assert not any(".claude/" in p for p in paths)
    assert not any(".cursor/" in p for p in paths)
    # Regular docs still present
    assert any("docs/guide.md" in p for p in paths)


def test_walk_for_planning_docs_with_extra_exclude_dir_names(tmp_path: Path) -> None:
    """Caller-supplied extra_exclude_dir_names extends the planning-docs
    exclude set without affecting the agent-dir-inclusion policy."""
    repo = _make_repo(tmp_path)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_x.md").write_text("# noise")
    (repo / "worktrees").mkdir()
    (repo / "worktrees" / "tmp.md").write_text("# noise")

    entries = walk_for_planning_docs(
        repo,
        include_agent_dirs=True,
        extra_exclude_dir_names={"tests", "worktrees"},
    )
    paths = _paths(entries)
    # Real docs still included
    assert any("docs/guide.md" in p for p in paths)
    # Agent dirs still included (policy unchanged)
    assert any(".claude/memory.md" in p for p in paths)
    # extra_exclude_dir_names applied
    assert not any("tests/test_x.md" in p for p in paths)
    assert not any("worktrees/tmp.md" in p for p in paths)
