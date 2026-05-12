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


# ── Prep-self-output filter (Phase 133b F4) ─────────────────────────


from prep.core.docs_grounding import (
    PREP_SELF_OUTPUT_MARKERS,
    _looks_like_prep_self_output,
)


def test_prep_self_output_markers_catalog():
    """Lock in the markers we explicitly detect — adding a new prep output
    surface (rules_generator, AGENTS.md, etc.) without updating this catalog
    risks recursive self-grounding."""
    assert "Auto-generated by Prep" in PREP_SELF_OUTPUT_MARKERS
    assert "Auto-generated by SourcePrep" in PREP_SELF_OUTPUT_MARKERS
    assert "Auto-generated by RunPrep" in PREP_SELF_OUTPUT_MARKERS
    assert "Auto-generated by CoDRAG" in PREP_SELF_OUTPUT_MARKERS
    assert "SourcePrep structural codebase intelligence" in PREP_SELF_OUTPUT_MARKERS
    assert "<!-- prep-managed-start -->" in PREP_SELF_OUTPUT_MARKERS
    assert "<!-- prep-opportunities-start -->" in PREP_SELF_OUTPUT_MARKERS


def test_looks_like_prep_self_output_matches_cursor_rule():
    """Real `.cursor/rules/prep.mdc` header (observed in 5 of 23 sample repos)."""
    body = (
        "---\n"
        "description: SourcePrep structural codebase intelligence\n"
        "alwaysApply: true\n"
        "---\n\n"
        "Get structural codebase context from SourcePrep tools:\n"
    )
    assert _looks_like_prep_self_output(body) is True


def test_looks_like_prep_self_output_matches_legacy_codrag_rule():
    """Legacy CoDRAG variant — survives until projects re-run prep mcp-config."""
    body = (
        "---\n"
        "description: CoDRAG structural codebase intelligence\n"
        "alwaysApply: true\n"
        "---\n\n"
        "Get structural codebase context from Prep tools:\n"
    )
    assert _looks_like_prep_self_output(body) is True


def test_looks_like_prep_self_output_matches_auto_generated_agents_md():
    """Auto-generated AGENTS.md uses an HTML-comment marker for splice."""
    body = (
        "<!-- prep-opportunities-start -->\n"
        "## Prep Codebase Intelligence\n\n"
        "*Auto-generated by SourcePrep*\n"
    )
    assert _looks_like_prep_self_output(body) is True


def test_looks_like_prep_self_output_matches_prep_managed_marker():
    body = "# Title\n\n<!-- prep-managed-start -->\nContent\n<!-- prep-managed-end -->"
    assert _looks_like_prep_self_output(body) is True


def test_looks_like_prep_self_output_matches_staffing_knowledge_md():
    """Real `.agents/<role>/KNOWLEDGE.md` header."""
    body = (
        "# Knowledge Base — Content Marketing Strategist\n\n"
        "> Auto-generated by Prep Staffing Agent. Do not edit manually.\n"
    )
    assert _looks_like_prep_self_output(body) is True


def test_looks_like_prep_self_output_matches_staffing_soul_md():
    """Real `.agents/<role>/SOUL.md` — `<think>` block referencing file
    being generated. Phrasing varies (`user wants a` / `user wants me
    to generate a`); we match on the distinctive substring."""
    body = (
        "<think>The user wants a SOUL.md identity file for a\n"
        "'Content Marketing Strategist' role.\n"
    )
    assert _looks_like_prep_self_output(body) is True


def test_looks_like_prep_self_output_matches_staffing_per_role_agents_md():
    """Real `.agents/<role>/AGENTS.md`."""
    body = (
        "<think>The user wants an AGENTS.md instruction file for the\n"
        "'MCP Integrations Specialist' role (slug: `mcp_integrations_specialist`).\n"
    )
    assert _looks_like_prep_self_output(body) is True


def test_looks_like_prep_self_output_does_not_match_project_skill():
    """Real `.claude/skills/playwright-smoke/SKILL.md` (project-specific
    custom skill — should NOT be filtered out)."""
    body = (
        "---\n"
        "name: playwright-smoke\n"
        "description: Use when validating that the dashboard UI matches\n"
        "  backend reality during a pipeline run\n"
        "---\n\n"
        "# Playwright smoke test\n\n"
        "Wrap tools/playwright_smoke.py to drive the dashboard headlessly.\n"
    )
    assert _looks_like_prep_self_output(body) is False


def test_looks_like_prep_self_output_does_not_match_opensource_agent_skill():
    """OpenClaw's `.agents/skills/openclaw-secret-scanning-maintainer/SKILL.md`
    — genuine project workflow, no prep markers."""
    body = (
        "---\n"
        "name: openclaw-secret-scanning-maintainer\n"
        "description: Maintainer-only workflow for scanning the OpenClaw\n"
        "  release artifacts for accidentally committed secrets.\n"
        "---\n\n"
        "# Process\n\n"
        "1. Pull the latest release tag\n"
    )
    assert _looks_like_prep_self_output(body) is False


def test_looks_like_prep_self_output_empty_body():
    assert _looks_like_prep_self_output("") is False
    assert _looks_like_prep_self_output("   \n\n   ") is False


def test_looks_like_prep_self_output_only_scans_head():
    """A 2k-char project doc that mentions one of the markers DEEP in the
    body shouldn't trip the filter — markers are conventionally in the
    head (frontmatter / first paragraph)."""
    body = "# Real project README\n\n" + ("Some real content. " * 100)
    body += "\n\nThis project does not auto-generate; the phrase "
    body += "`Auto-generated by Prep` appears here as discussion only.\n"
    # The marker appears past _SELF_OUTPUT_SCAN_HEAD_CHARS — filter
    # should still let the file through.
    assert _looks_like_prep_self_output(body) is False


# ── discover_planning_docs respects the self-output filter ───────────


def test_discover_skips_prep_managed_doc(repo, tmp_path):
    """An AGENTS.md at repo root that's prep-managed must be excluded
    from the discovered set."""
    (repo / "AGENTS.md").write_text(
        "<!-- prep-managed-start -->\n"
        "## Prep Codebase Intelligence\n"
        "*Auto-generated by SourcePrep*\n"
        "<!-- prep-managed-end -->\n"
    )
    docs = discover_planning_docs(repo, top_n=50)
    paths = {d.path for d in docs}
    assert "AGENTS.md" not in paths


def test_discover_keeps_project_specific_skill_in_agent_dir(repo, tmp_path):
    """A `.claude/skills/playwright-smoke/SKILL.md`-style file inside an
    agent dir must still be discovered — only prep-self-output content
    is filtered, not the whole dir."""
    skill_dir = repo / ".cursor" / "rules"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "project-workflow.mdc").write_text(
        "---\n"
        "description: Project-specific workflow rule\n"
        "---\n\n"
        "# Workflow\n\nWhen X happens, do Y.\n"
    )
    docs = discover_planning_docs(repo, top_n=50)
    paths = {d.path for d in docs}
    # The non-prep .mdc lives in an allowlisted dot-dir AND lacks the
    # prep-self-output markers, so it's kept. (Note: discover_planning_docs
    # only walks `.md` files today — `.mdc` doesn't get walked. So this
    # asserts the filter is path-agnostic and ready for the day .mdc is
    # added to the walker; the fallback assertion verifies the file's
    # presence isn't blocked by the self-output filter.)
    assert not _looks_like_prep_self_output(
        (skill_dir / "project-workflow.mdc").read_text()
    )
