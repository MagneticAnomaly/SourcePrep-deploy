"""Phase 96 / F-40: regression tests for AutoRebuildWatcher._is_relevant.

Before the F-40 fix, ``_is_relevant`` used ``pathlib.Path.match()`` which
does NOT support the recursive ``**`` wildcard the way fnmatch / gitignore
do.  Patterns like ``**/.claude/**`` returned False against
``.claude/worktrees/x/y.py``, which let the watcher report changes inside
git worktrees as relevant and triggered delta builds that walked the
duplicated repo.

These tests lock in pathspec/gitwildmatch behavior so the bug can't
return.
"""
from __future__ import annotations

import pytest

from codrag.core.watcher import AutoRebuildWatcher


class TestIsRelevantPathspec:
    """F-40: directory exclude patterns must use gitwildmatch semantics."""

    INCLUDES = ["**/*.py", "**/*.md", "**/*.ts", "**/*.tsx"]
    EXCLUDES = [
        "**/.claude/**",
        "**/.git/**",
        "**/.codrag/**",
        "**/node_modules/**",
        "**/.venv/**",
        "**/*.lock",
    ]

    @pytest.mark.parametrize("path", [
        ".claude/worktrees/busy-swirles/backend_config.py",
        ".claude/worktrees/busy-swirles/AGENTS.md",
        ".claude/worktrees/foo/src/codrag/server.py",
        ".claude/skills/foo.md",
    ])
    def test_claude_subtree_excluded(self, path):
        assert AutoRebuildWatcher._is_relevant(path, self.INCLUDES, self.EXCLUDES) is False

    @pytest.mark.parametrize("path", [
        ".git/HEAD",
        ".git/objects/ab/cdef.py",
        ".codrag/atlas.json",
        ".codrag/trace_nodes.jsonl",
        ".venv/lib/python3.11/site-packages/foo.py",
        "node_modules/react/index.ts",
        "src/foo/node_modules/bar/baz.ts",
    ])
    def test_other_default_excludes(self, path):
        assert AutoRebuildWatcher._is_relevant(path, self.INCLUDES, self.EXCLUDES) is False

    @pytest.mark.parametrize("path", [
        "src/codrag/server.py",
        "docs/README.md",
        "packages/ui/src/index.ts",
        "tests/test_foo.py",
        "scripts/dev.sh",  # excluded because not in include_globs
    ])
    def test_normal_files_included(self, path):
        expected = path.endswith((".py", ".md", ".ts", ".tsx"))
        assert AutoRebuildWatcher._is_relevant(path, self.INCLUDES, self.EXCLUDES) is expected

    def test_lock_file_excluded(self):
        assert AutoRebuildWatcher._is_relevant("package-lock.json", self.INCLUDES, self.EXCLUDES) is False
        assert AutoRebuildWatcher._is_relevant("Cargo.lock", self.INCLUDES, self.EXCLUDES) is False

    def test_no_includes_returns_true_when_not_excluded(self):
        # When include_globs is empty, every non-excluded path is relevant
        assert AutoRebuildWatcher._is_relevant("foo/bar.zzz", [], self.EXCLUDES) is True
        assert AutoRebuildWatcher._is_relevant(".claude/foo.zzz", [], self.EXCLUDES) is False

    def test_no_includes_no_excludes_returns_true(self):
        assert AutoRebuildWatcher._is_relevant("anything.py", [], []) is True
