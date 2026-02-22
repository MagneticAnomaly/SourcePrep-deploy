"""
Scenario test: codrag_hi with a real-world file selection.

Simulates the TEST repo scenario:
- docs/ with DesignPlan/ .md files (design specs, roadmaps, trust section redesign)
- src/components/ with React .tsx components (Hero, Trust, Parallax, etc.)
- Path weights: docs/ ×1.0, DesignPlan/ ×0.6, src/ ×1.0, components/ ×1.0

This test prints the full codrag_hi output so we can see what the AI model
would receive and present to the user.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock

from codrag.mcp_server import MCPServer


# -- Fixtures matching the TEST repo screenshot --------------------------------

TEST_INCLUDED_PATHS = [
    # docs/DesignPlan/ — design spec .md files
    "docs/DesignPlan/0-overall-upgrad-plan.md",
    "docs/DesignPlan/1-hero.md",
    "docs/DesignPlan/2-trust-and-brand-ethosmd",  # no .md extension (as in real repo)
    "docs/DesignPlan/3-business",                  # no .md extension
    "docs/DesignPlan/4-Updated-Trust-paralax.md",
    # docs/ — other .md files
    "docs/questions_for_designer.md",
    "docs/README.md",
    "docs/roadmap.md",
    "docs/site_roadmap.md",
    "docs/trust_section_redesign.md",
    # src/components/ — React .tsx components
    "src/components/BetaSignupForm.tsx",
    "src/components/CanvasBackground.tsx",
    "src/components/CardsSection.tsx",
    "src/components/EnhancedHero.tsx",
    "src/components/EnhancedRoadmapSection.tsx",
    "src/components/EnhancedTrustSection.tsx",
    "src/components/ParallaxController.tsx",
    "src/components/PercentageBasedFooter.tsx",
    "src/components/PercentageBasedHero.tsx",
    "src/components/PercentageBasedRoadmapSection.tsx",
    "src/components/PercentageBasedTrustSection.tsx",
    "src/components/PercentageBasedTrustSection_BAD.tsx",
    "src/components/PercentageBasedTrustSection_OLD.tsx",
    "src/components/PercentageLayoutController.tsx",
    # src/components/phases/
    "src/components/phases/FooterPhase.tsx",
    "src/components/phases/HeroPhase.tsx",
    "src/components/phases/SubwayPhase.tsx",
    "src/components/phases/ZoomPhase.tsx",
]

TEST_PATH_WEIGHTS = {
    "docs/": 1.0,
    "docs/DesignPlan/": 0.6,
    "src/": 1.0,
    "src/components/": 1.0,
}

TEST_STATUS = {
    "index": {
        "exists": True,
        "total_chunks": 32,  # 9 + 10 + 13 = 32 indexed chunks from screenshot
        "embedding_model": "nomic-embed-text-v2-moe",
        "last_build_at": "2026-02-21T12:00:00Z",
    },
    "building": False,
    "stale": False,
    "stale_count": 0,
    "trace": {
        "enabled": True,
        "total_nodes": 28,
        "total_edges": 45,
    },
    "watch": {"enabled": False},
}

TEST_COVERAGE = {
    "traced_count": 22,
    "untraced_count": 6,
    "stale_count": 0,
    "total_nodes": 28,
    "total_edges": 45,
    "building": False,
    "stale": [],  # O-7: no stale files in baseline scenario
}

TEST_HUB_FILES = {
    "hub_files": [
        {"path": "src/components/EnhancedHero.tsx", "in_degree": 6},
        {"path": "src/components/ParallaxController.tsx", "in_degree": 4},
        {"path": "src/components/PercentageBasedTrustSection.tsx", "in_degree": 3},
    ]
}

TEST_FILE_EDGES = {
    "edges": [
        {"source": "src/components/phases/HeroPhase.tsx", "target": "src/components/EnhancedHero.tsx", "kind": "imports"},
        {"source": "src/components/EnhancedHero.tsx", "target": "src/components/ParallaxController.tsx", "kind": "imports"},
        {"source": "src/components/phases/ZoomPhase.tsx", "target": "src/components/PercentageBasedTrustSection.tsx", "kind": "imports"},
    ]
}

TEST_DOC_CONTENTS = {
    "docs/DesignPlan/0-overall-upgrad-plan.md": {
        "content": "# Overall Upgrade Plan\nThis document outlines the phased redesign of the marketing site.\n## Phase 1\n..."
    },
    "docs/DesignPlan/1-hero.md": {
        "content": "# Hero Section Design\nThe hero uses a percentage-based parallax layout with scroll-driven animations.\n## Layout\n..."
    },
    "docs/DesignPlan/4-Updated-Trust-paralax.md": {
        "content": "# Updated Trust Section with Parallax\nRedesigned trust section using percentage-based positioning and scroll triggers.\n## Changes\n..."
    },
    "docs/questions_for_designer.md": {
        "content": "# Questions for Designer\nOpen questions about the visual direction and component patterns.\n## Typography\n..."
    },
    "docs/roadmap.md": {
        "content": "# Site Roadmap\nTimeline for the marketing site redesign project.\n## Q1 Goals\n..."
    },
}

TEST_PROJECTS = {
    "projects": [
        {"id": "proj_test_site", "name": "test-site", "path": "/tmp/test-site"},
    ]
}

TEST_PROJECT_DETAIL = {
    "project": {"id": "proj_test_site", "name": "test-site", "path": "/tmp/test-site"}
}


async def _mock_api_get(path):
    """Route mock API calls to TEST repo data."""
    if "/status" in path:
        return TEST_STATUS
    if "/included_paths" in path:
        return {"included_paths": TEST_INCLUDED_PATHS}
    if "/path_weights" in path:
        return {"path_weights": TEST_PATH_WEIGHTS}
    if "/trace/hub_files" in path:
        return TEST_HUB_FILES
    if "/trace/file_edges" in path:
        return TEST_FILE_EDGES
    if "/trace/coverage" in path:
        return TEST_COVERAGE
    if "/file?path=" in path:
        for fpath, content in TEST_DOC_CONTENTS.items():
            if fpath in path:
                return content
        return {}
    if path == "/projects":
        return TEST_PROJECTS
    if "/projects/" in path and "/file" not in path:
        return TEST_PROJECT_DETAIL
    return {}


@pytest.fixture
def test_server():
    server = MCPServer(daemon_url="http://127.0.0.1:8400", project_id="proj_test_site")
    server._api_get = _mock_api_get
    return server


# =============================================================================
# Scenario Tests
# =============================================================================

class TestDesignPlanComponentsScenario:
    """Test codrag_hi with the TEST repo: design .md files + components/ folder."""

    @pytest.mark.asyncio
    async def test_scenario_full_output(self, test_server, capsys):
        """Print the full codrag_hi output for visual inspection."""
        result = await test_server.tool_hi()

        # Print for visual inspection
        print("\n" + "=" * 70)
        print("codrag_hi RESPONSE — TEST REPO SCENARIO")
        print("=" * 70)
        print("\n--- _ai_note ---")
        print(result["_ai_note"])
        print("\n--- summary ---")
        print(result["summary"])
        print("\n--- file_inventory ---")
        print(json.dumps(result["file_inventory"], indent=2))
        print("\n--- diagnostics ---")
        print(json.dumps(result["diagnostics"], indent=2))
        print("=" * 70)

    @pytest.mark.asyncio
    async def test_detects_design_plan_docs(self, test_server):
        """Design plan .md files are categorized and listed."""
        result = await test_server.tool_hi()
        inv = result["file_inventory"]

        assert "docs" in inv
        # The .md files should be in docs category
        assert inv["docs"]["count"] >= 7  # at least the .md files
        assert "0-overall-upgrad-plan.md" in inv["docs"]["files"]
        assert "1-hero.md" in inv["docs"]["files"]

    @pytest.mark.asyncio
    async def test_detects_react_components(self, test_server):
        """React .tsx components are categorized as code."""
        result = await test_server.tool_hi()
        inv = result["file_inventory"]

        assert "code" in inv
        assert inv["code"]["count"] == 18  # 14 components + 4 phases
        assert "EnhancedHero.tsx" in inv["code"]["files"]
        assert "ParallaxController.tsx" in inv["code"]["files"]

    @pytest.mark.asyncio
    async def test_summary_shows_component_filenames(self, test_server):
        """Summary lists actual component filenames."""
        result = await test_server.tool_hi()

        assert "`EnhancedHero.tsx`" in result["summary"] or "EnhancedHero" in result["summary"]
        assert "components" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_summary_shows_design_doc_filenames(self, test_server):
        """Summary lists actual design doc filenames."""
        result = await test_server.tool_hi()

        assert "0-overall-upgrad-plan.md" in result["summary"] or "upgrad-plan" in result["summary"]

    @pytest.mark.asyncio
    async def test_prompts_include_design_review(self, test_server):
        """Prompts suggest reviewing design plans."""
        result = await test_server.tool_hi()
        summary_lower = result["summary"].lower()

        # Should detect design docs and suggest reviewing them
        assert "design" in summary_lower or "plan" in summary_lower

    @pytest.mark.asyncio
    async def test_prompts_include_component_review(self, test_server):
        """Prompts suggest reviewing UI components."""
        result = await test_server.tool_hi()
        summary_lower = result["summary"].lower()

        assert "component" in summary_lower or "ui" in summary_lower

    @pytest.mark.asyncio
    async def test_prompts_include_cross_cutting(self, test_server):
        """With both docs and code, prompts suggest comparing design to implementation."""
        result = await test_server.tool_hi()
        summary_lower = result["summary"].lower()

        # Should have a cross-cutting prompt since both docs and code are selected
        assert "compare" in summary_lower or "sync" in summary_lower or "implementation" in summary_lower

    @pytest.mark.asyncio
    async def test_path_weights_shown(self, test_server):
        """Path weights from the file tree are displayed."""
        result = await test_server.tool_hi()

        assert "Priority areas" in result["summary"]
        assert "0.6" in result["summary"]  # DesignPlan/ weight

    @pytest.mark.asyncio
    async def test_trace_is_background(self, test_server):
        """Trace info is present but not the lead."""
        result = await test_server.tool_hi()

        # Trace should be mentioned
        assert "28 nodes" in result["summary"]
        # But the summary should START with file info, not trace
        first_line = result["summary"].split("\n")[0]
        assert "looking at" in first_line.lower()
        assert "trace" not in first_line.lower()


class TestScenarioNewFeatures:
    """Test the Phase 32 enhancements in the TEST repo scenario."""

    @pytest.mark.asyncio
    async def test_hub_files_shown(self, test_server):
        """O-2: Hub files appear in the summary."""
        result = await test_server.tool_hi()

        assert "Most connected" in result["summary"]
        assert "EnhancedHero.tsx" in result["summary"]
        assert "6 connections" in result["summary"]
        assert "hub_files" in result["diagnostics"]

    @pytest.mark.asyncio
    async def test_file_edges_shown(self, test_server):
        """O-8: Cross-file relationships appear in the summary."""
        result = await test_server.tool_hi()

        assert "File connections" in result["summary"]
        assert "imports" in result["summary"]
        assert "file_edges" in result["diagnostics"]

    @pytest.mark.asyncio
    async def test_doc_previews_returned(self, test_server):
        """O-1: Doc content previews are included."""
        result = await test_server.tool_hi()

        assert "doc_previews" in result
        previews = result["doc_previews"]
        assert len(previews) >= 3  # at least the 3 .md files with content
        headings = [p["heading"] for p in previews]
        assert "Overall Upgrade Plan" in headings
        assert "Hero Section Design" in headings

    @pytest.mark.asyncio
    async def test_doc_preview_includes_paragraph(self, test_server):
        """O-1: Doc previews include the first paragraph."""
        result = await test_server.tool_hi()

        previews = result["doc_previews"]
        hero_preview = next((p for p in previews if p["heading"] == "Hero Section Design"), None)
        assert hero_preview is not None
        assert "parallax" in hero_preview["preview"].lower()

    @pytest.mark.asyncio
    async def test_ai_note_mentions_deeper_context(self, test_server):
        """O-5: _ai_note tells the AI to call codrag for deeper context."""
        result = await test_server.tool_hi()

        assert "DEEPER CONTEXT" in result["_ai_note"]
        assert "codrag" in result["_ai_note"]

    @pytest.mark.asyncio
    async def test_prompts_ordered_by_relevance(self, test_server):
        """O-4: With both docs and code, cross-cutting prompt is prominent."""
        result = await test_server.tool_hi()

        # Extract numbered prompts from summary
        lines = result["summary"].split("\n")
        prompt_lines = [l.strip() for l in lines if l.strip() and l.strip()[0].isdigit() and "." in l.strip()[:3]]
        assert len(prompt_lines) >= 3

        # Cross-cutting "compare" prompt should be present
        all_prompts = " ".join(prompt_lines).lower()
        assert "compare" in all_prompts or "sync" in all_prompts or "implementation" in all_prompts

    @pytest.mark.asyncio
    async def test_topics_detected_for_test_repo(self, test_server):
        """O-3: Topic detection finds animation & visuals from parallax/canvas filenames."""
        result = await test_server.tool_hi()

        topics = result.get("detected_topics", [])
        topic_names = [t["topic"] for t in topics]
        # The TEST repo has ParallaxController, CanvasBackground, etc.
        assert "animation & visuals" in topic_names
        assert "working on" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_topic_files_are_correct(self, test_server):
        """O-3: Files listed for each topic match what's selected."""
        result = await test_server.tool_hi()

        topics = result.get("detected_topics", [])
        anim_topic = next((t for t in topics if t["topic"] == "animation & visuals"), None)
        if anim_topic:
            assert any("Parallax" in f or "Canvas" in f for f in anim_topic["files"])

    @pytest.mark.asyncio
    async def test_full_output_with_enhancements(self, test_server, capsys):
        """Print the enhanced codrag_hi output for visual inspection."""
        result = await test_server.tool_hi()

        print("\n" + "=" * 70)
        print("codrag_hi ENHANCED RESPONSE — TEST REPO SCENARIO")
        print("=" * 70)
        print("\n--- summary ---")
        print(result["summary"])
        if result.get("doc_previews"):
            print("\n--- doc_previews ---")
            print(json.dumps(result["doc_previews"], indent=2))
        if result.get("detected_topics"):
            print("\n--- detected_topics ---")
            print(json.dumps(result["detected_topics"], indent=2))
        print("\n--- diagnostics (hub_files, file_edges) ---")
        diag = result["diagnostics"]
        for key in ("hub_files", "file_edges", "stale_files", "detected_topics"):
            if key in diag:
                print(f"  {key}: {json.dumps(diag[key], indent=4)}")
        print("=" * 70)
