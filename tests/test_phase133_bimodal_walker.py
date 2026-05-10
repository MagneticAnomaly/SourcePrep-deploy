"""Phase 133 — Phase 125c forward-look: walker primitive bimodal use.

The Rust walker accepts include_globs and exclude_globs from the caller.
For source indexing (today's coverage path), CLAUDE.md and
.cursor/rules/*.mdc are in DEFAULT_EXCLUDE_FILE_GLOBS — they must
NOT appear. For a hypothetical doc-discovery caller (Phase 125c), the
caller passes a different exclude set without those globs — those
files MUST appear.

Phase 133's contract: the walker primitive supports both modes.
Phase 125c (separate phase) builds the doc-discovery caller."""
from __future__ import annotations

from pathlib import Path

import pytest

import prep_engine

FIXTURE = Path(__file__).parent / "fixtures" / "walker_parity_repo"


def test_source_indexing_mode_excludes_ai_rule_files() -> None:
    """Caller passes the source-indexing exclude set → CLAUDE.md and
    .cursor/rules/*.mdc are NOT in the walker output."""
    from prep.core.repo_profile import DEFAULT_EXCLUDE_FILE_GLOBS, DEFAULT_EXCLUDE_DIR_NAMES

    excludes = list(DEFAULT_EXCLUDE_FILE_GLOBS) + [f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES]

    entries = prep_engine.walk_repo(
        str(FIXTURE),
        include_globs=["**/*.md", "**/*.mdc", "**/*.py", "**/*.yml"],
        exclude_globs=excludes,
        max_file_bytes=500_000,
    )
    paths = {e.path for e in entries}

    assert "CLAUDE.md" not in paths, (
        "source-indexing mode must exclude CLAUDE.md — it's in DEFAULT_EXCLUDE_FILE_GLOBS"
    )
    assert ".cursor/rules/sample.mdc" not in paths, (
        "source-indexing mode must exclude .cursor/rules/*.mdc"
    )


def test_doc_discovery_mode_includes_ai_rule_files() -> None:
    """Caller passes a curated exclude set without the AI-rule globs →
    CLAUDE.md and .cursor/rules/*.mdc DO appear. This is the Phase 125c
    forward-look surface; Phase 133 just proves the walker supports it."""
    # Doc-discovery exclude set: still cull build artifacts and VCS,
    # but NOT the AI-rule files.
    excludes = [
        "**/.git/**",
        "**/node_modules/**",
        "**/dist/**",
        "**/build/**",
        "**/__pycache__/**",
    ]

    entries = prep_engine.walk_repo(
        str(FIXTURE),
        include_globs=["**/*.md", "**/*.mdc", "**/*.py", "**/*.yml"],
        exclude_globs=excludes,
        max_file_bytes=500_000,
    )
    paths = {e.path for e in entries}

    assert "CLAUDE.md" in paths, (
        "doc-discovery mode must include CLAUDE.md when caller drops the AI-rule excludes"
    )
    assert ".cursor/rules/sample.mdc" in paths, (
        "doc-discovery mode must include .cursor/rules/*.mdc when caller drops them"
    )
