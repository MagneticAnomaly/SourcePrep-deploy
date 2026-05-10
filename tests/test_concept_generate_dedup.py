"""Phase 125c T2c.1 — tests for docs-grounding loader + cross-worker dedup.

These helpers feed the SwarmOrchestrator integration in T2c.2:
- load_or_build_docs_grounding produces what each Generate worker reads
- dedupe_swarm_outputs collapses near-duplicates emitted by different
  workers
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.concept_generate_dedup import (
    dedupe_swarm_outputs,
    load_or_build_docs_grounding,
)
from prep.core.concept_synthesizer import SynthesizedConcept


# ── load_or_build_docs_grounding ────────────────────────────────────


@pytest.fixture
def repo_with_idx(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nThe system has three layers."
    )
    (repo / "docs").mkdir()
    (repo / "docs" / "DESIGN.md").write_text(
        "# Design\n\n## Goals\n\nBe fast."
    )
    idx_dir = tmp_path / "idx"
    idx_dir.mkdir()
    return repo, idx_dir


def test_load_builds_when_file_absent(repo_with_idx):
    repo, idx_dir = repo_with_idx
    g = load_or_build_docs_grounding(
        "p1", idx_dir=idx_dir, project_root=repo, top_n=10,
    )
    assert g.selected_count >= 1
    paths = {d.path for d in g.docs}
    assert "ARCHITECTURE.md" in paths
    # Should also have written the file for next time
    assert (idx_dir / "docs_grounding.json").is_file()


def test_load_reads_existing_json(repo_with_idx):
    repo, idx_dir = repo_with_idx
    # Pre-write a docs_grounding.json with a sentinel path that the
    # builder would never have produced — proves we read from disk
    # rather than rebuilding.
    (idx_dir / "docs_grounding.json").write_text(json.dumps({
        "version": 1, "generated_at": 999.0,
        "docs": [{
            "path": "SENTINEL.md", "score": 0.99,
            "signals": ["test"], "in_link_count": 7,
            "size_bytes": 50, "excerpt": "from disk",
            "headings": ["sentinel"],
        }],
        "total_candidates_considered": 1, "selected_count": 1,
    }))
    g = load_or_build_docs_grounding(
        "p1", idx_dir=idx_dir, project_root=repo, top_n=10,
    )
    paths = {d.path for d in g.docs}
    assert paths == {"SENTINEL.md"}
    assert g.docs[0].excerpt == "from disk"


def test_load_rebuilds_when_disk_unreadable(repo_with_idx):
    repo, idx_dir = repo_with_idx
    # Write garbage JSON; loader should fall back to rebuild
    (idx_dir / "docs_grounding.json").write_text("{ not valid json")
    g = load_or_build_docs_grounding(
        "p1", idx_dir=idx_dir, project_root=repo, top_n=10,
    )
    paths = {d.path for d in g.docs}
    assert "ARCHITECTURE.md" in paths    # rebuilt from scratch


def test_load_with_rebuild_disabled_returns_empty_when_absent(repo_with_idx):
    repo, idx_dir = repo_with_idx
    g = load_or_build_docs_grounding(
        "p1", idx_dir=idx_dir, project_root=repo,
        rebuild_if_missing=False,
    )
    assert g.docs == []
    assert not (idx_dir / "docs_grounding.json").is_file()


# ── dedupe_swarm_outputs ────────────────────────────────────────────


def _concept(title: str, tier: str, anchors: tuple[str, ...]) -> SynthesizedConcept:
    return SynthesizedConcept(
        title=title,
        content=f"{title} content",
        category="technical",
        tier=tier,
        tier_pairwise="closer_to_lower",
        anchors=anchors,
    )


def test_dedupe_singleton_passes_through():
    """One concept, no clustering possible — returned as-is."""
    c = _concept("Solo concept", "T2", ("src/a.py", "src/b.py"))
    out = dedupe_swarm_outputs([c])
    assert out == [c]


def test_dedupe_empty_input_returns_empty():
    assert dedupe_swarm_outputs([]) == []


def test_dedupe_keeps_higher_tier_in_anchor_overlap_cluster():
    """Two workers emit concepts with the same anchors at different
    tiers — the higher tier wins."""
    a = _concept("License gate", "T2", ("src/llm/gate.py", "src/llm/client.py"))
    b = _concept("License gating concept", "T3",
                 ("src/llm/gate.py", "src/llm/client.py"))
    out = dedupe_swarm_outputs([a, b])
    assert len(out) == 1
    assert out[0].tier == "T3"
    assert out[0].title == "License gating concept"


def test_dedupe_keeps_separate_concepts_with_no_anchor_overlap():
    """Two unrelated concepts don't get merged."""
    a = _concept("X concept", "T2", ("src/a.py", "src/b.py"))
    b = _concept("Y concept", "T2", ("packages/ui/x.tsx", "packages/ui/y.tsx"))
    out = dedupe_swarm_outputs([a, b])
    assert len(out) == 2


def test_dedupe_three_way_cluster_collapses_to_one_winner():
    a = _concept("auth A", "T1", ("src/auth.py", "src/jwt.py"))
    b = _concept("auth B", "T2", ("src/auth.py", "src/jwt.py"))
    c = _concept("auth C", "T3", ("src/auth.py", "src/jwt.py"))
    # Each pair shares 2 anchors → all three cluster together
    out = dedupe_swarm_outputs([a, b, c])
    assert len(out) == 1
    assert out[0].tier == "T3"


def test_dedupe_breaks_tier_tie_on_anchor_count():
    a = _concept("X", "T2", ("src/a.py", "src/b.py"))
    b = _concept("X variant", "T2", ("src/a.py", "src/b.py", "src/c.py"))
    out = dedupe_swarm_outputs([a, b])
    assert len(out) == 1
    # Same tier; b has more anchors → b wins
    assert out[0].title == "X variant"


def test_dedupe_does_not_merge_distinct_concepts_on_one_shared_anchor():
    """Default min_shared_anchors=2: a single shared anchor is not
    enough to merge unless titles are similar."""
    a = _concept("auth flow", "T2", ("src/auth.py", "src/jwt.py"))
    b = _concept("ui theme", "T2", ("src/auth.py", "packages/ui/theme.ts"))
    # Share src/auth.py but only 1 anchor + dissimilar titles → keep separate
    out = dedupe_swarm_outputs([a, b])
    assert len(out) == 2
