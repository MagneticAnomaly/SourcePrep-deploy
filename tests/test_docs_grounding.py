"""Tests for the planning/design doc auto-discovery (Phase 125c T1).

The discoverer scores `.md` files in a repo by four layered signals
and writes the top-N to `docs_grounding.json` for the Generate swarm
to consume as rich grounding.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from prep.core.docs_grounding import (
    PLANNING_FILENAMES,
    PLANNING_FOLDERS,
    DiscoveredDoc,
    DocsGrounding,
    _extract_excerpt,
    _extract_headings,
    _is_phase_or_sprint_folder,
    build_docs_grounding,
    discover_planning_docs,
    score_doc,
    write_docs_grounding,
)


# ── score_doc — pure scoring function ───────────────────────────────


def test_score_doc_zero_signals_returns_zero():
    score, signals = score_doc(
        rel_path="random/notes.md",
        in_link_count=0,
        in_link_max=10,
        folder_md_ratio=0.1,
    )
    assert score == 0.0
    assert signals == []


def test_score_doc_high_in_link_rank_only():
    score, signals = score_doc(
        rel_path="random/foo.md",
        in_link_count=8,
        in_link_max=10,
        folder_md_ratio=0.1,
    )
    assert 0.35 < score < 0.45  # 0.8 * 0.5 weight
    assert "in_link_rank" in signals


def test_score_doc_convention_filename_only():
    score, signals = score_doc(
        rel_path="src/some/dir/ARCHITECTURE.md",
        in_link_count=0,
        in_link_max=10,
        folder_md_ratio=0.0,
    )
    assert 0.20 < score < 0.30
    assert "convention_match" in signals


def test_score_doc_hidden_agent_dir_only():
    # `.cursor/random.md` is in an allowlisted hidden dir but NOT in a
    # known planning folder (PLANNING_FOLDERS has `.cursor/rules`, not
    # plain `.cursor/`), so only the hidden_agent_dir signal should fire.
    score, signals = score_doc(
        rel_path=".cursor/random.md",
        in_link_count=0,
        in_link_max=10,
        folder_md_ratio=0.0,
    )
    assert 0.05 < score < 0.15
    assert "hidden_agent_dir" in signals
    assert "folder_concentration" not in signals


def test_score_doc_folder_concentration_only():
    score, signals = score_doc(
        rel_path="docs/random_note.md",
        in_link_count=0,
        in_link_max=10,
        folder_md_ratio=0.85,
    )
    assert 0.10 < score < 0.20
    assert "folder_concentration" in signals


def test_score_doc_caps_at_one():
    score, signals = score_doc(
        rel_path=".cursor/rules/ARCHITECTURE.md",
        in_link_count=10,
        in_link_max=10,
        folder_md_ratio=1.0,
    )
    assert score == 1.0
    assert set(signals) >= {
        "in_link_rank", "convention_match",
        "folder_concentration", "hidden_agent_dir",
    }


def test_score_doc_phase_folder_pattern_matches_convention():
    score, signals = score_doc(
        rel_path="docs/Phase125c_QualityCheckedConceptSwarm/README.md",
        in_link_count=0,
        in_link_max=10,
        folder_md_ratio=0.0,
    )
    assert "convention_match" in signals  # phase pattern via _is_phase_or_sprint_folder
    assert score > 0.0


# ── discover_planning_docs — file system walk ───────────────────────


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Build a tiny synthetic repo with planning + non-planning files."""
    (tmp_path / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nThis project is a daemon...\n\n## Components\n\nSee src/.\n"
    )
    (tmp_path / "README.md").write_text("# Readme\n\nQuickstart")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main(): pass")
    (tmp_path / "src" / "notes.md").write_text("# Notes\n\nInformal jottings.")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DESIGN.md").write_text(
        "# Design\n\n## Goals\n\nFast.\n"
    )
    (tmp_path / "docs" / "Phase125c_Foo").mkdir()
    (tmp_path / "docs" / "Phase125c_Foo" / "README.md").write_text("# Phase 125c\n\nPlan.")
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "rules").mkdir()
    (tmp_path / ".cursor" / "rules" / "prep.mdc").write_text("# rules")
    (tmp_path / ".cursor" / "rules" / "agents.md").write_text("# Agents\n\nRules.")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "should_be_ignored.md").write_text("# garbage")
    (tmp_path / ".sourceprep").mkdir()
    (tmp_path / ".sourceprep" / "internal.md").write_text("# internal")
    return tmp_path


def test_discover_finds_planning_docs(repo):
    docs = discover_planning_docs(repo, top_n=10)
    paths = {d.path for d in docs}
    # Should find the obvious planning docs
    assert "ARCHITECTURE.md" in paths
    assert "docs/DESIGN.md" in paths
    assert "docs/Phase125c_Foo/README.md" in paths
    # Should find the .cursor/rules .md (allowlisted hidden dir)
    assert ".cursor/rules/agents.md" in paths


def test_discover_excludes_generated_dirs(repo):
    docs = discover_planning_docs(repo, top_n=50)
    paths = {d.path for d in docs}
    assert "node_modules/should_be_ignored.md" not in paths
    assert ".sourceprep/internal.md" not in paths


def test_discover_excludes_non_md_files(repo):
    docs = discover_planning_docs(repo, top_n=50)
    paths = {d.path for d in docs}
    assert not any(p.endswith(".py") for p in paths)
    assert not any(p.endswith(".mdc") for p in paths)


def test_discover_excludes_other_dot_dirs(repo, tmp_path):
    # .git should not be walked
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "should_skip.md").write_text("# git internal")
    docs = discover_planning_docs(repo, top_n=50)
    paths = {d.path for d in docs}
    assert ".git/should_skip.md" not in paths


def test_discover_uses_in_link_signal(repo):
    in_link_map = {
        "src/notes.md": ["src/main.py", "src/main.py", "src/main.py"],
        "ARCHITECTURE.md": ["src/main.py"],
    }
    docs = discover_planning_docs(repo, in_link_map=in_link_map, top_n=10)
    # src/notes.md should now appear thanks to in-link signal even
    # though its filename isn't a convention match
    paths = {d.path for d in docs}
    assert "src/notes.md" in paths


def test_discover_top_n_limits_results(repo):
    docs = discover_planning_docs(repo, top_n=2)
    assert len(docs) <= 2
    # Top 2 should be the highest scorers
    scores = [d.score for d in docs]
    assert scores == sorted(scores, reverse=True)


# ── _is_phase_or_sprint_folder ──────────────────────────────────────


def test_phase_folder_pattern_matches():
    assert _is_phase_or_sprint_folder("docs/Phase125c_Foo")
    assert _is_phase_or_sprint_folder("docs/Phase01_Bar")
    assert _is_phase_or_sprint_folder("Sprint5_Whatever")
    assert _is_phase_or_sprint_folder("docs/Phase125c_QualityCheckedConceptSwarm")


def test_phase_folder_pattern_rejects_unrelated():
    assert not _is_phase_or_sprint_folder("docs/random")
    assert not _is_phase_or_sprint_folder("PhaseTransitions")  # no number
    assert not _is_phase_or_sprint_folder("docs/notes")


# ── _extract_excerpt + _extract_headings ────────────────────────────


def test_extract_excerpt_truncates_on_paragraph_boundary():
    paragraphs = [f"Paragraph number {i} with some text content here." for i in range(20)]
    body = "\n\n".join(paragraphs)
    excerpt = _extract_excerpt(body, max_chars=150)
    # Should include the first paragraph at minimum
    assert "Paragraph number 0" in excerpt
    # Should NOT include all 20 paragraphs (full body is ~1k chars)
    assert "Paragraph number 19" not in excerpt
    # Should end at a paragraph boundary (no trailing partial sentence)
    assert excerpt.rstrip().endswith(".")


def test_extract_excerpt_strips_yaml_frontmatter():
    body = "---\nname: foo\ndescription: bar\n---\n\nReal content here."
    excerpt = _extract_excerpt(body, max_chars=200)
    assert "name: foo" not in excerpt
    assert "Real content here" in excerpt


def test_extract_headings_collects_all_levels():
    body = "# Top\n\nbody\n\n## Sub\n\nbody\n\n### Deep\n\nbody"
    headings = _extract_headings(body)
    assert headings == ("Top", "Sub", "Deep")


def test_extract_headings_strips_hash_and_whitespace():
    body = "#  Spaced\n\n##\tTabbed"
    headings = _extract_headings(body)
    assert headings == ("Spaced", "Tabbed")


# ── build_docs_grounding + write_docs_grounding ─────────────────────


def test_build_docs_grounding_reads_atlas_markdown_links(repo, tmp_path):
    idx_dir = tmp_path / "idx"
    idx_dir.mkdir()
    # Build a minimal atlas_markdown_links.json
    (idx_dir / "atlas_markdown_links.json").write_text(json.dumps({
        "md_to_files": {
            "ARCHITECTURE.md": ["src/main.py", "src/main.py", "src/main.py"],
            "docs/DESIGN.md": ["src/main.py"],
        }
    }))
    grounding = build_docs_grounding(
        "proj-1", project_root=repo, idx_dir=idx_dir, top_n=10,
    )
    assert grounding.selected_count == len(grounding.docs)
    assert grounding.total_candidates_considered >= len(grounding.docs)
    # ARCHITECTURE.md should be present and have in_link_count=3
    arch = next((d for d in grounding.docs if d.path == "ARCHITECTURE.md"), None)
    assert arch is not None
    assert arch.in_link_count == 3
    assert arch.score > 0.0


def test_build_docs_grounding_handles_missing_atlas_links(repo, tmp_path):
    idx_dir = tmp_path / "idx"
    idx_dir.mkdir()
    # No atlas_markdown_links.json — discovery still works on convention/folder signals
    grounding = build_docs_grounding(
        "proj-1", project_root=repo, idx_dir=idx_dir, top_n=10,
    )
    assert grounding.selected_count >= 1
    # All in_link_count fields should be 0
    assert all(d.in_link_count == 0 for d in grounding.docs)


def test_write_docs_grounding_emits_valid_json(repo, tmp_path):
    idx_dir = tmp_path / "idx"
    idx_dir.mkdir()
    grounding = DocsGrounding(
        version=1, generated_at=1234.5,
        docs=[
            DiscoveredDoc(
                path="ARCHITECTURE.md", score=0.5,
                signals=("convention_match",),
                in_link_count=2, size_bytes=100,
                excerpt="...", headings=("Top",),
            ),
        ],
        total_candidates_considered=1, selected_count=1,
    )
    write_docs_grounding(grounding, idx_dir)
    out = json.loads((idx_dir / "docs_grounding.json").read_text())
    assert out["version"] == 1
    assert out["docs"][0]["path"] == "ARCHITECTURE.md"
    assert out["docs"][0]["signals"] == ["convention_match"]


# ── PLANNING_FILENAMES / PLANNING_FOLDERS catalog sanity ────────────


def test_planning_filenames_catalog_contains_expected():
    assert "ARCHITECTURE" in PLANNING_FILENAMES
    assert "DESIGN" in PLANNING_FILENAMES
    assert "AGENTS" in PLANNING_FILENAMES
    assert "CLAUDE" in PLANNING_FILENAMES
    assert "ROADMAP" in PLANNING_FILENAMES


def test_planning_folders_catalog_contains_expected():
    assert "docs/adr" in PLANNING_FOLDERS
    assert ".cursor/rules" in PLANNING_FOLDERS
    assert "rfcs" in PLANNING_FOLDERS
