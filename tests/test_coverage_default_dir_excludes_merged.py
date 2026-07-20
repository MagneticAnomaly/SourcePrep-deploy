"""Phase 133 follow-up — DEFAULT_EXCLUDE_DIR_NAMES is ALWAYS merged.

Regression guard for the leak surfaced on 2026-05-12: agent-instruction
directories (.claude/, .agents/, .cursor/, ...) were appearing in the
trace queue on projects with custom exclude_globs.

Root cause: Phase 133 swap of os.walk + dotdir-prune filter for
prep_engine.walk_repo (which walks dot-dirs unless told otherwise)
exposed that compute_trace_coverage only merged DEFAULT_EXCLUDE_DIR_NAMES
when the caller passed exclude_globs=None. A project config with 7
custom patterns (none catching .claude/**) skipped the system baseline.

Fix: always merge DEFAULT_EXCLUDE_DIR_NAMES patterns (same way Phase 89
treats DEFAULT_EXCLUDE_FILE_GLOBS). User config extends, never overrides.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.repo_profile import (
    DEFAULT_EXCLUDE_DIR_NAMES,
    DEFAULT_EXCLUDE_FILE_GLOBS,
)
from prep.core.trace.coverage import compute_trace_coverage


# ── Catalog assertions ─────────────────────────────────────────────


def test_dot_agents_is_in_default_dir_excludes():
    """The screenshot showing .agents/ in the queue (2026-05-12) caught
    that .agents was never in the catalog. Lock it in."""
    assert ".agents" in DEFAULT_EXCLUDE_DIR_NAMES


def test_known_ai_dir_excludes_present():
    """Trace pipeline excludes the well-known AI agent / tool dirs.
    Note: .github is intentionally NOT excluded — Phase 133's
    divergence #2 surfaces .github/workflows/*.yml as legit CI config
    the user may want traced."""
    for d in (".claude", ".cursor", ".windsurf",
              ".continue", ".cody", ".aider", ".agents"):
        assert d in DEFAULT_EXCLUDE_DIR_NAMES, (
            f"{d} missing from DEFAULT_EXCLUDE_DIR_NAMES — would leak "
            "into the trace queue on projects with custom exclude_globs"
        )


# ── End-to-end merge behavior ───────────────────────────────────────


@pytest.fixture
def repo_with_agent_dirs(tmp_path: Path) -> Path:
    """Synthetic repo with files in .claude/, .agents/, and a regular src/."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("def main(): pass\n")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "skills").mkdir()
    (repo / ".claude" / "settings.local.json").write_text("{}")
    (repo / ".claude" / "skills" / "prep.md").write_text("# skill")
    (repo / ".agents").mkdir()
    (repo / ".agents" / "agent_x").mkdir()
    (repo / ".agents" / "agent_x" / "SOUL.md").write_text("# soul")
    (repo / ".agents" / "agent_x" / "KNOWLEDGE.md").write_text("# k")
    # And a trace_manifest.json with one already-traced file
    idx = tmp_path / "idx"
    idx.mkdir()
    (idx / "trace_manifest.json").write_text(json.dumps({
        "hash_algo": "blake3-128",
        "file_hashes": {"src/main.py": "deadbeef" * 4},
    }))
    return repo


def test_coverage_excludes_dot_dirs_with_user_excludes_provided(repo_with_agent_dirs):
    """Even when the caller passes custom exclude_globs (mimicking project
    config), DEFAULT_EXCLUDE_DIR_NAMES patterns are still applied."""
    repo = repo_with_agent_dirs
    idx = repo.parent / "idx"

    # Custom user excludes — none of them cover .claude/** or .agents/**
    user_provided = [
        "**/node_modules/**", "**/.venv/**", "**/dist/**",
    ]
    coverage = compute_trace_coverage(
        repo_root=repo,
        index_dir=idx,
        exclude_globs=user_provided,
    )
    all_paths = {f["path"] for f in (
        coverage["traced"] + coverage["untraced"]
        + coverage["stale"] + coverage["excluded"]
    )}
    # The leaked dirs MUST NOT appear in any of the four buckets
    assert not any(p.startswith(".claude/") for p in all_paths), (
        f"Leak: .claude/ paths found in coverage: "
        f"{[p for p in all_paths if p.startswith('.claude/')]}"
    )
    assert not any(p.startswith(".agents/") for p in all_paths), (
        f"Leak: .agents/ paths found in coverage: "
        f"{[p for p in all_paths if p.startswith('.agents/')]}"
    )


def test_coverage_excludes_dot_dirs_with_no_user_excludes(repo_with_agent_dirs):
    """Sanity: same behavior when exclude_globs is None (pre-existing path)."""
    repo = repo_with_agent_dirs
    idx = repo.parent / "idx"
    coverage = compute_trace_coverage(
        repo_root=repo, index_dir=idx, exclude_globs=None,
    )
    all_paths = {f["path"] for f in (
        coverage["traced"] + coverage["untraced"]
        + coverage["stale"] + coverage["excluded"]
    )}
    assert not any(p.startswith(".claude/") for p in all_paths)
    assert not any(p.startswith(".agents/") for p in all_paths)


def test_docs_grounding_still_walks_agent_dirs():
    """The OPPOSITE policy must hold: the concept synthesizer's walker
    (docs_grounding) must still pick up .claude/ and .agents/ as planning
    material. These exclusions are trace-pipeline-only."""
    from prep.core.docs_grounding import ALLOWED_DOT_DIRS, PLANNING_FOLDERS
    assert ".agents" in ALLOWED_DOT_DIRS
    assert ".claude" in ALLOWED_DOT_DIRS
    assert ".agents" in PLANNING_FOLDERS
    assert ".claude" in PLANNING_FOLDERS
