"""
Tests for the codrag_hi MCP tool (Phase 32).

Tests cover:
- Daemon-mode tool_hi() with mocked API responses
- Direct-mode tool_hi() with in-process CodeIndex
- Markdown summary generation (header, status, scope, health, prompts)
- Health note heuristics (stale, no index, low trace coverage, auto-rebuild)
- Prompt generation (domain-aware, fallback, no-index)
- Edge cases (empty data, all endpoints fail gracefully)
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from codrag.mcp_server import MCPServer


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def server():
    """Create an MCP server instance pinned to a test project."""
    return MCPServer(daemon_url="http://127.0.0.1:8400", project_id="proj_test")


def _make_status(
    index_exists=True,
    total_chunks=150,
    building=False,
    stale=False,
    stale_count=0,
    trace_enabled=True,
    total_nodes=50,
    total_edges=80,
    watch_enabled=False,
    built_at="2026-02-20T12:00:00Z",
):
    return {
        "index": {
            "exists": index_exists,
            "total_chunks": total_chunks,
            "embedding_model": "nomic-embed-text-v2-moe",
            "last_build_at": built_at,
        },
        "building": building,
        "stale": stale,
        "stale_count": stale_count,
        "trace": {
            "enabled": trace_enabled,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
        },
        "watch": {"enabled": watch_enabled},
    }


def _make_included_paths(paths=None):
    return {"included_paths": paths or []}


def _make_path_weights(weights=None):
    return {"path_weights": weights or {}}


def _make_coverage(traced=40, untraced=10, stale=0, nodes=50, edges=80):
    return {
        "traced_count": traced,
        "untraced_count": untraced,
        "stale_count": stale,
        "total_nodes": nodes,
        "total_edges": edges,
        "building": False,
    }


def _make_projects(current_id="proj_test", others=None):
    projects = [{"id": current_id, "name": "my-app", "path": "/tmp/my-app"}]
    for o in (others or []):
        projects.append(o)
    return {"projects": projects}


def _make_project_detail(name="my-app"):
    return {"project": {"id": "proj_test", "name": name, "path": "/tmp/my-app"}}


async def _mock_api_get_factory(
    status=None, included=None, weights=None, coverage=None, projects=None, project=None,
    hub_files=None, file_edges=None, file_contents=None,
):
    """Return a side_effect function for _api_get that routes by path."""
    status = status or _make_status()
    included = included or _make_included_paths()
    weights = weights or _make_path_weights()
    coverage = coverage or _make_coverage()
    projects = projects or _make_projects()
    project = project or _make_project_detail()
    hub_files = hub_files or {"hub_files": []}
    file_edges = file_edges or {"edges": []}
    file_contents = file_contents or {}  # path -> {"content": "..."}

    async def _mock_get(path):
        if "/status" in path:
            return status
        if "/included_paths" in path:
            return included
        if "/path_weights" in path:
            return weights
        if "/trace/hub_files" in path:
            return hub_files
        if "/trace/file_edges" in path:
            return file_edges
        if "/trace/coverage" in path:
            return coverage
        if "/file?path=" in path:
            # O-1: doc content preview
            for fpath, content in file_contents.items():
                if fpath in path:
                    return content
            return {}
        if path == "/projects":
            return projects
        if "/projects/" in path and "/status" not in path and "/included" not in path and "/path_weights" not in path and "/trace" not in path and "/file" not in path:
            return project
        return {}

    return _mock_get


# =============================================================================
# Daemon-Mode Tests
# =============================================================================

class TestToolHiDaemon:
    """Test codrag_hi in daemon mode (MCPServer)."""

    @pytest.mark.asyncio
    async def test_basic_summary_structure(self, server):
        """tool_hi returns summary and diagnostics keys."""
        mock_get = await _mock_api_get_factory()
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "summary" in result
        assert "diagnostics" in result
        assert "_ai_note" in result
        assert isinstance(result["summary"], str)
        assert isinstance(result["diagnostics"], dict)
        assert "STANDALONE" in result["_ai_note"]

    @pytest.mark.asyncio
    async def test_summary_contains_project_name(self, server):
        """Summary header includes the project name."""
        mock_get = await _mock_api_get_factory()
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "my-app" in result["summary"]
        assert result["diagnostics"]["project_name"] == "my-app"

    @pytest.mark.asyncio
    async def test_summary_shows_index_loaded(self, server):
        """Summary shows index chunk count when loaded."""
        mock_get = await _mock_api_get_factory(status=_make_status(total_chunks=847))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "847 chunks" in result["summary"]
        assert result["diagnostics"]["total_chunks"] == 847
        assert result["diagnostics"]["index_loaded"] is True

    @pytest.mark.asyncio
    async def test_summary_shows_no_index(self, server):
        """When no index exists, summary says so and suggests codrag_build."""
        mock_get = await _mock_api_get_factory(status=_make_status(index_exists=False, total_chunks=0, built_at=None))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "no index yet" in result["summary"]
        assert "codrag_build" in result["summary"]
        assert result["diagnostics"]["index_loaded"] is False

    @pytest.mark.asyncio
    async def test_summary_shows_building(self, server):
        """When index is building, summary indicates it."""
        mock_get = await _mock_api_get_factory(status=_make_status(building=True))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "building" in result["summary"].lower()
        assert result["diagnostics"]["building"] is True

    @pytest.mark.asyncio
    async def test_summary_shows_trace_active(self, server):
        """Summary shows trace stats when enabled."""
        mock_get = await _mock_api_get_factory(status=_make_status(trace_enabled=True, total_nodes=523, total_edges=641))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "code graph" in result["summary"].lower()
        assert "523 nodes" in result["summary"]
        assert result["diagnostics"]["trace_enabled"] is True

    @pytest.mark.asyncio
    async def test_health_stale_index(self, server):
        """Stale index triggers a health note."""
        mock_get = await _mock_api_get_factory(status=_make_status(stale=True, stale_count=12))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "12 file(s) changed" in result["summary"]

    @pytest.mark.asyncio
    async def test_health_stale_with_watcher(self, server):
        """Stale index with watcher on mentions auto-rebuild."""
        mock_get = await _mock_api_get_factory(
            status=_make_status(stale=True, stale_count=3, watch_enabled=True)
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "Auto-rebuild is on" in result["summary"]

    @pytest.mark.asyncio
    async def test_health_low_trace_coverage(self, server):
        """Low trace coverage (<60%) triggers a health note."""
        mock_get = await _mock_api_get_factory(
            status=_make_status(trace_enabled=True),
            coverage=_make_coverage(traced=20, untraced=80),
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "Trace coverage" in result["summary"]
        assert "20%" in result["summary"]

    @pytest.mark.asyncio
    async def test_health_nominal(self, server):
        """When everything is healthy, summary says so."""
        mock_get = await _mock_api_get_factory(
            status=_make_status(watch_enabled=True),
            coverage=_make_coverage(traced=90, untraced=10),
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "Everything looks good" in result["summary"]

    @pytest.mark.asyncio
    async def test_included_paths_shown(self, server):
        """Included paths are summarized by top directories."""
        paths = [
            "src/components/Button.tsx",
            "src/components/Modal.tsx",
            "src/api/auth.ts",
            "docs/README.md",
        ]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "4 files selected" in result["summary"]
        assert "src/" in result["summary"]
        assert result["diagnostics"]["included_paths_count"] == 4

    @pytest.mark.asyncio
    async def test_path_weights_shown(self, server):
        """Path weights are displayed in the summary."""
        mock_get = await _mock_api_get_factory(weights=_make_path_weights({"src/core/": 1.5, "docs/": 0.5}))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "Priority areas" in result["summary"]
        assert "1.5" in result["summary"]
        assert "0.5" in result["summary"]

    @pytest.mark.asyncio
    async def test_suggested_prompts_with_index(self, server):
        """Prompts are generated when index exists."""
        paths = ["src/main.py", "src/api/routes.py", "tests/test_main.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "things I can help with" in result["summary"]
        # Should have at least 3 prompts
        assert '1. ' in result["summary"]
        assert '2. ' in result["summary"]
        assert '3. ' in result["summary"]

    @pytest.mark.asyncio
    async def test_suggested_prompts_domain_aware(self, server):
        """Prompts reference detected domains (API, components, tests, etc.)."""
        paths = [
            "api/users.py",
            "api/auth.py",
            "components/App.tsx",
        ]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        # Should detect api/ and components/ top-level dirs and suggest related prompts
        assert "API" in result["summary"] or "endpoint" in result["summary"].lower()
        assert "component" in result["summary"].lower() or "UI" in result["summary"]

    @pytest.mark.asyncio
    async def test_other_projects_listed(self, server):
        """Other available projects are mentioned."""
        projects = _make_projects(others=[
            {"id": "proj_b", "name": "backend-api", "path": "/tmp/backend"},
            {"id": "proj_c", "name": "shared-lib", "path": "/tmp/shared"},
        ])
        mock_get = await _mock_api_get_factory(projects=projects)
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "backend-api" in result["summary"]
        assert "shared-lib" in result["summary"]
        assert len(result["diagnostics"]["other_projects"]) == 2

    @pytest.mark.asyncio
    async def test_diagnostics_structure(self, server):
        """Diagnostics dict has all expected keys."""
        mock_get = await _mock_api_get_factory()
        server._api_get = mock_get

        result = await server.tool_hi()
        d = result["diagnostics"]

        expected_keys = {
            "project_id", "project_name", "index_loaded", "total_chunks",
            "building", "stale", "stale_count", "trace_enabled", "trace_nodes",
            "trace_edges", "trace_coverage_pct", "watch_enabled",
            "included_paths_count", "path_weights", "other_projects",
        }
        assert expected_keys.issubset(set(d.keys()))

    @pytest.mark.asyncio
    async def test_endpoint_failure_graceful(self, server):
        """If some endpoints fail, tool_hi still returns a useful response."""
        call_count = 0

        async def _flaky_get(path):
            nonlocal call_count
            call_count += 1
            if "/included_paths" in path or "/path_weights" in path:
                raise Exception("Endpoint unavailable")
            if "/status" in path:
                return _make_status()
            if "/trace/coverage" in path:
                return _make_coverage()
            if path == "/projects":
                return _make_projects()
            return _make_project_detail()

        server._api_get = _flaky_get

        # Should not raise
        result = await server.tool_hi()

        assert "summary" in result
        assert "my-app" in result["summary"]
        # Included paths and weights should be empty/zero since those endpoints failed
        assert result["diagnostics"]["included_paths_count"] == 0

    @pytest.mark.asyncio
    async def test_summary_length_under_limit(self, server):
        """Summary should be concise (<2000 chars for token efficiency)."""
        mock_get = await _mock_api_get_factory()
        server._api_get = mock_get

        result = await server.tool_hi()

        assert len(result["summary"]) < 2000

    @pytest.mark.asyncio
    async def test_mcp_tools_call_dispatch(self, server):
        """codrag_hi is properly dispatched via handle_tools_call."""
        mock_get = await _mock_api_get_factory()
        server._api_get = mock_get

        response = await server.handle_tools_call({
            "name": "codrag_hi",
            "arguments": {},
        })

        assert response["isError"] is False
        content = json.loads(response["content"][0]["text"])
        assert "summary" in content
        assert "diagnostics" in content

    @pytest.mark.asyncio
    async def test_mcp_tools_call_with_project_override(self, server):
        """codrag_hi accepts project_id override."""
        mock_get = await _mock_api_get_factory()
        server._api_get = mock_get

        response = await server.handle_tools_call({
            "name": "codrag_hi",
            "arguments": {"project_id": "proj_test"},
        })

        assert response["isError"] is False

    @pytest.mark.asyncio
    async def test_tool_listed_in_tools_list(self, server):
        """codrag_hi appears in the tools/list response."""
        response = await server.handle_tools_list({})
        tool_names = [t["name"] for t in response["tools"]]
        assert "codrag_hi" in tool_names

    @pytest.mark.asyncio
    async def test_tool_schema_no_required_params(self, server):
        """codrag_hi tool schema has no required params."""
        response = await server.handle_tools_list({})
        hi_tool = next(t for t in response["tools"] if t["name"] == "codrag_hi")
        assert hi_tool["inputSchema"]["required"] == []


# =============================================================================
# Prompt Generation Tests
# =============================================================================

class TestPromptGeneration:
    """Test the rule-based prompt generation heuristics."""

    @pytest.mark.asyncio
    async def test_no_index_only_build_prompt(self, server):
        """When no index exists, only suggest building."""
        mock_get = await _mock_api_get_factory(
            status=_make_status(index_exists=False, total_chunks=0, built_at=None)
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "codrag_build" in result["summary"]

    @pytest.mark.asyncio
    async def test_src_dir_triggers_code_prompt(self, server):
        """Selecting code files in src/ triggers a code-aware prompt."""
        paths = ["src/main.py", "src/utils.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()
        summary_lower = result["summary"].lower()

        # New content-aware prompts: small code sets get "walk me through" or "relate"
        assert "walk me through" in summary_lower or "relate" in summary_lower or "structured" in summary_lower

    @pytest.mark.asyncio
    async def test_tests_dir_triggers_test_prompt(self, server):
        """Selecting files in tests/ triggers a test review prompt."""
        paths = ["tests/test_main.py", "tests/test_api.py", "src/main.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()
        summary_lower = result["summary"].lower()

        assert "test" in summary_lower or "covered" in summary_lower

    @pytest.mark.asyncio
    async def test_trace_enabled_graph_prompt(self, server):
        """When trace is enabled, suggest exploring connections."""
        mock_get = await _mock_api_get_factory(
            status=_make_status(trace_enabled=True, total_nodes=100, total_edges=200)
        )
        server._api_get = mock_get

        result = await server.tool_hi()
        summary_lower = result["summary"].lower()

        assert "connected" in summary_lower or "graph" in summary_lower or "trace" in summary_lower

    @pytest.mark.asyncio
    async def test_stale_index_triggers_rebuild_prompt(self, server):
        """Stale index adds a rebuild prompt to suggestions."""
        mock_get = await _mock_api_get_factory(status=_make_status(stale=True, stale_count=5))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "codrag_build" in result["summary"]

    @pytest.mark.asyncio
    async def test_min_three_prompts(self, server):
        """Always generate at least 3 prompts when index exists."""
        mock_get = await _mock_api_get_factory()
        server._api_get = mock_get

        result = await server.tool_hi()

        # Count numbered prompt lines
        prompt_lines = [l for l in result["summary"].split("\n") if l.strip().startswith(("1.", "2.", "3."))]
        assert len(prompt_lines) >= 3

    @pytest.mark.asyncio
    async def test_max_six_prompts(self, server):
        """Never generate more than 6 prompts."""
        # Create paths that trigger many domain detections
        paths = [
            "src/main.py", "api/routes.py", "components/App.tsx",
            "tests/test.py", "docs/README.md", "lib/utils.py",
        ]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            status=_make_status(stale=True, stale_count=1, trace_enabled=True),
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        prompt_lines = [
            l for l in result["summary"].split("\n")
            if l.strip() and l.strip()[0].isdigit() and '. ' in l
        ]
        assert len(prompt_lines) <= 6


# =============================================================================
# File Inventory Tests
# =============================================================================

class TestFileInventory:
    """Test file categorization and inventory in codrag_hi response."""

    @pytest.mark.asyncio
    async def test_file_inventory_in_response(self, server):
        """Response includes a file_inventory dict when files are selected."""
        paths = ["docs/DESIGN.md", "src/main.py", "tests/test_main.py", "package.json"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "file_inventory" in result
        inv = result["file_inventory"]
        assert "docs" in inv
        assert "code" in inv
        assert "tests" in inv
        assert "config" in inv

    @pytest.mark.asyncio
    async def test_docs_categorized(self, server):
        """Markdown files are categorized as docs."""
        paths = ["docs/DESIGN.md", "docs/API.md", "README.txt"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        inv = result["file_inventory"]
        assert inv["docs"]["count"] == 3
        assert "DESIGN.md" in inv["docs"]["files"]
        assert "API.md" in inv["docs"]["files"]

    @pytest.mark.asyncio
    async def test_code_categorized(self, server):
        """Code files are categorized separately from docs."""
        paths = ["src/auth.py", "src/main.ts", "lib/utils.js"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        inv = result["file_inventory"]
        assert inv["code"]["count"] == 3
        assert "auth.py" in inv["code"]["files"]

    @pytest.mark.asyncio
    async def test_tests_categorized_by_path(self, server):
        """Files under test/ or tests/ dirs are categorized as tests."""
        paths = ["tests/test_auth.py", "tests/test_api.py", "src/main.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        inv = result["file_inventory"]
        assert inv["tests"]["count"] == 2
        assert "code" in inv  # src/main.py is code

    @pytest.mark.asyncio
    async def test_summary_lists_actual_filenames(self, server):
        """Summary includes actual filenames, not just directory counts."""
        paths = ["docs/DESIGN.md", "docs/ROADMAP.md", "src/main.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "`DESIGN.md`" in result["summary"]
        assert "`ROADMAP.md`" in result["summary"]
        assert "`main.py`" in result["summary"]

    @pytest.mark.asyncio
    async def test_inventory_caps_at_max(self, server):
        """File inventory caps filenames at _MAX_LIST per category."""
        paths = [f"src/file_{i}.py" for i in range(20)]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        inv = result["file_inventory"]
        assert inv["code"]["count"] == 20
        assert len(inv["code"]["files"]) <= 10  # _MAX_LIST = 10

    @pytest.mark.asyncio
    async def test_empty_inventory_when_no_files(self, server):
        """File inventory is empty when no files are selected."""
        mock_get = await _mock_api_get_factory(included=_make_included_paths([]))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert result["file_inventory"] == {}


# =============================================================================
# Content-Aware Prompt Tests
# =============================================================================

class TestContentAwarePrompts:
    """Test that prompts adapt to selected file content."""

    @pytest.mark.asyncio
    async def test_design_docs_trigger_design_prompt(self, server):
        """Design docs in selection trigger a 'summarize design plans' prompt."""
        paths = ["docs/DESIGN_SPEC.md", "docs/ARCHITECTURE.md", "src/main.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "design" in result["summary"].lower()
        assert "next steps" in result["summary"].lower() or "plans" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_todo_docs_trigger_roadmap_prompt(self, server):
        """TODO/roadmap docs trigger a 'what should I work on' prompt."""
        paths = ["docs/TODO.md", "docs/ROADMAP.md"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "todo" in result["summary"].lower() or "roadmap" in result["summary"].lower() or "work on" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_docs_plus_code_trigger_cross_cutting_prompt(self, server):
        """When both docs and code are selected, suggest comparing them."""
        paths = ["docs/DESIGN.md", "src/auth.py", "src/users.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "design" in result["summary"].lower() or "compare" in result["summary"].lower() or "sync" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_api_code_triggers_endpoint_prompt(self, server):
        """API code files trigger endpoint-related prompts."""
        paths = ["api/users.py", "api/auth.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "api" in result["summary"].lower() or "endpoint" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_small_code_set_triggers_walkthrough(self, server):
        """Small code selections (≤10 files) get a walkthrough prompt."""
        paths = ["src/main.py", "src/config.py", "src/db.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "walk" in result["summary"].lower() or "relate" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_ai_note_emphasizes_selected_files(self, server):
        """The _ai_note tells the AI to lead with selected files."""
        paths = ["src/main.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "selected files" in result["_ai_note"].lower() or "file inventory" in result["_ai_note"].lower()
        assert "STANDALONE" in result["_ai_note"]
        assert "WITH A QUESTION" in result["_ai_note"]


# =============================================================================
# Phase 32 Enhancement Tests (O-1, O-2, O-4, O-5, O-7, O-8)
# =============================================================================

class TestO1DocPreviews:
    """O-1: Doc content previews — first heading + paragraph for .md files."""

    @pytest.mark.asyncio
    async def test_doc_previews_returned(self, server):
        """Doc previews are included when .md files are selected."""
        paths = ["docs/DESIGN.md", "docs/ROADMAP.md"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            file_contents={
                "docs/DESIGN.md": {"content": "# Architecture Overview\nThis doc describes the system architecture.\n## Components\n..."},
                "docs/ROADMAP.md": {"content": "# Q1 Roadmap\nFocus on performance and stability.\n## Milestones\n..."},
            },
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "doc_previews" in result
        assert len(result["doc_previews"]) == 2
        assert result["doc_previews"][0]["heading"] == "Architecture Overview"
        assert "system architecture" in result["doc_previews"][0]["preview"]
        assert result["doc_previews"][1]["heading"] == "Q1 Roadmap"

    @pytest.mark.asyncio
    async def test_doc_previews_skip_non_md(self, server):
        """Files without .md extension don't get previews (even if in docs category)."""
        paths = ["docs/DesignPlan/3-business", "src/main.py"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        # "3-business" has no .md extension so no preview fetch attempted
        assert result.get("doc_previews", []) == []

    @pytest.mark.asyncio
    async def test_doc_previews_graceful_on_api_error(self, server):
        """If the file API fails, previews are just empty — no crash."""
        paths = ["docs/DESIGN.md"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            file_contents={"docs/DESIGN.md": Exception("file not found")},
        )
        # Override to raise for file content
        orig = mock_get
        async def _raising_get(path):
            if "/file?path=" in path:
                raise Exception("file not found")
            return await orig(path)
        server._api_get = _raising_get

        result = await server.tool_hi()

        # Should not crash, previews just empty
        assert result.get("doc_previews", []) == []

    @pytest.mark.asyncio
    async def test_doc_previews_max_5(self, server):
        """At most 5 doc files get previewed."""
        paths = [f"docs/doc{i}.md" for i in range(10)]
        contents = {
            p: {"content": f"# Doc {i}\nContent for doc {i}."}
            for i, p in enumerate(paths)
        }
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            file_contents=contents,
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert len(result.get("doc_previews", [])) <= 5


class TestO2HubFiles:
    """O-2: Hub file identification from trace graph."""

    @pytest.mark.asyncio
    async def test_hub_files_in_summary(self, server):
        """Hub files are shown in the summary."""
        paths = ["src/auth.py", "src/models.py", "src/utils.py"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            hub_files={"hub_files": [
                {"path": "src/models.py", "in_degree": 12},
                {"path": "src/utils.py", "in_degree": 8},
            ]},
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "Most connected" in result["summary"]
        assert "models.py" in result["summary"]
        assert "12 connections" in result["summary"]

    @pytest.mark.asyncio
    async def test_hub_files_in_diagnostics(self, server):
        """Hub files appear in diagnostics."""
        paths = ["src/auth.py"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            hub_files={"hub_files": [{"path": "src/auth.py", "in_degree": 5}]},
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "hub_files" in result["diagnostics"]
        assert result["diagnostics"]["hub_files"][0]["path"] == "src/auth.py"

    @pytest.mark.asyncio
    async def test_no_hub_files_graceful(self, server):
        """When no hub files, summary doesn't mention them."""
        paths = ["src/main.py"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            hub_files={"hub_files": []},
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "Most connected" not in result["summary"]
        assert "hub_files" not in result["diagnostics"]


class TestO4SmartPromptOrdering:
    """O-4: Prompts reordered by category match to dominant selection."""

    @pytest.mark.asyncio
    async def test_doc_dominant_ordering(self, server):
        """When docs dominate the selection, doc prompts come first."""
        paths = ["docs/DESIGN.md", "docs/SPEC.md", "docs/README.md", "src/main.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        # First prompt should be doc-related
        lines = result["summary"].split("\n")
        prompt_lines = [l for l in lines if l.strip().startswith("1.")]
        assert prompt_lines
        first = prompt_lines[0].lower()
        assert any(kw in first for kw in ("doc", "design", "plan", "summarize"))

    @pytest.mark.asyncio
    async def test_test_dominant_ordering(self, server):
        """When tests dominate, test prompts are promoted."""
        paths = [
            "tests/test_auth.py", "tests/test_users.py",
            "tests/test_orders.py", "tests/test_billing.py",
            "src/main.py",
        ]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        # Test prompts should be near the top
        assert "test" in result["summary"].lower()


class TestO5AmbientContextChain:
    """O-5: _ai_note tells the AI to call codrag for deeper context."""

    @pytest.mark.asyncio
    async def test_ai_note_mentions_codrag_tool(self, server):
        """The _ai_note includes guidance about calling codrag for deeper context."""
        paths = ["src/main.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "DEEPER CONTEXT" in result["_ai_note"]
        assert "codrag" in result["_ai_note"]
        assert "hub files" in result["_ai_note"].lower() or "ambient" in result["_ai_note"].lower()


class TestO7ChangeDetection:
    """O-7: Show which specific files changed since last build."""

    @pytest.mark.asyncio
    async def test_stale_files_shown_in_summary(self, server):
        """Stale file names appear in the summary."""
        paths = ["src/auth.py", "src/models.py", "src/config.py"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            status=_make_status(stale=True, stale_count=2),
            coverage={
                "traced_count": 40, "untraced_count": 10,
                "stale_count": 2, "total_nodes": 50, "total_edges": 80,
                "building": False,
                "stale": [
                    {"path": "src/auth.py", "hash": "abc"},
                    {"path": "src/models.py", "hash": "def"},
                ],
            },
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "Changed since last build" in result["summary"]
        assert "auth.py" in result["summary"]
        assert "models.py" in result["summary"]

    @pytest.mark.asyncio
    async def test_stale_files_in_diagnostics(self, server):
        """Stale file paths appear in diagnostics."""
        paths = ["src/auth.py"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            coverage={
                "traced_count": 40, "untraced_count": 10,
                "stale_count": 1, "total_nodes": 50, "total_edges": 80,
                "building": False,
                "stale": [{"path": "src/auth.py", "hash": "abc"}],
            },
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "stale_files" in result["diagnostics"]
        assert "src/auth.py" in result["diagnostics"]["stale_files"]

    @pytest.mark.asyncio
    async def test_no_stale_files_clean(self, server):
        """When nothing is stale, no stale section appears."""
        paths = ["src/main.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "Changed since last build" not in result["summary"]
        assert "stale_files" not in result["diagnostics"]


class TestO8CrossFileRelationships:
    """O-8: Show import/call relationships between selected files."""

    @pytest.mark.asyncio
    async def test_file_edges_in_summary(self, server):
        """File connections are shown in summary for small selections."""
        paths = ["src/auth.py", "src/models.py", "src/utils.py"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            file_edges={"edges": [
                {"source": "src/auth.py", "target": "src/models.py", "kind": "imports"},
                {"source": "src/auth.py", "target": "src/utils.py", "kind": "imports"},
            ]},
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "File connections" in result["summary"]
        assert "auth.py" in result["summary"]
        assert "imports" in result["summary"]

    @pytest.mark.asyncio
    async def test_file_edges_in_diagnostics(self, server):
        """File edges appear in diagnostics."""
        paths = ["src/a.py", "src/b.py"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            file_edges={"edges": [
                {"source": "src/a.py", "target": "src/b.py", "kind": "imports"},
            ]},
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "file_edges" in result["diagnostics"]
        assert len(result["diagnostics"]["file_edges"]) == 1

    @pytest.mark.asyncio
    async def test_no_edges_when_trace_disabled(self, server):
        """No file edge query when trace is disabled."""
        paths = ["src/a.py", "src/b.py"]
        mock_get = await _mock_api_get_factory(
            included=_make_included_paths(paths),
            status=_make_status(trace_enabled=False, total_nodes=0, total_edges=0),
        )
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "File connections" not in result["summary"]


# =============================================================================
# O-3: Filename-Based Topic Detection
# =============================================================================

class TestO3TopicDetection:
    """O-3: Detect topics from filenames and surface in summary + prompts."""

    @pytest.mark.asyncio
    async def test_auth_topic_detected(self, server):
        """Auth-related filenames cluster into 'authentication' topic."""
        paths = ["src/auth/login.py", "src/auth/session.py", "src/auth/tokens.py", "src/auth/middleware.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "detected_topics" in result
        topics = result["detected_topics"]
        assert len(topics) >= 1
        assert topics[0]["topic"] == "authentication"
        assert "login" in topics[0]["keywords"] or "session" in topics[0]["keywords"]
        assert "login.py" in topics[0]["files"]

    @pytest.mark.asyncio
    async def test_ecommerce_topic_detected(self, server):
        """E-commerce filenames cluster into 'e-commerce' topic."""
        paths = ["src/CartView.tsx", "src/CheckoutPage.tsx", "src/PaymentForm.tsx", "src/OrderSummary.tsx"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        topics = result.get("detected_topics", [])
        topic_names = [t["topic"] for t in topics]
        assert "e-commerce" in topic_names

    @pytest.mark.asyncio
    async def test_ui_components_topic_detected(self, server):
        """UI component filenames cluster into 'UI components' topic."""
        paths = ["src/components/Button.tsx", "src/components/Modal.tsx", "src/components/Sidebar.tsx", "src/components/Dropdown.tsx"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        topics = result.get("detected_topics", [])
        topic_names = [t["topic"] for t in topics]
        assert "UI components" in topic_names

    @pytest.mark.asyncio
    async def test_animation_topic_detected(self, server):
        """Animation/parallax filenames cluster into 'animation & visuals' topic."""
        paths = [
            "src/components/ParallaxController.tsx",
            "src/components/CanvasBackground.tsx",
            "src/components/ScrollEffect.tsx",
        ]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        topics = result.get("detected_topics", [])
        topic_names = [t["topic"] for t in topics]
        assert "animation & visuals" in topic_names

    @pytest.mark.asyncio
    async def test_no_topic_for_unrelated_files(self, server):
        """Random filenames that don't match any cluster return no topics."""
        paths = ["src/main.py", "src/utils.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        # No topic should be detected (no 2+ keyword matches)
        assert result.get("detected_topics", []) == []

    @pytest.mark.asyncio
    async def test_topics_in_summary(self, server):
        """Detected topics appear in the conversational summary."""
        paths = ["src/auth/login.py", "src/auth/session.py", "src/auth/tokens.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "authentication" in result["summary"].lower()
        assert "working on" in result["summary"].lower()

    @pytest.mark.asyncio
    async def test_topic_aware_prompt_generated(self, server):
        """A topic-specific prompt is generated when a topic is detected."""
        paths = ["src/auth/login.py", "src/auth/session.py", "src/auth/tokens.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        summary_lower = result["summary"].lower()
        assert "auth flow" in summary_lower or "security" in summary_lower

    @pytest.mark.asyncio
    async def test_topics_in_diagnostics(self, server):
        """Detected topics are included in diagnostics."""
        paths = ["src/auth/login.py", "src/auth/session.py", "src/auth/tokens.py"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        assert "detected_topics" in result["diagnostics"]
        assert result["diagnostics"]["detected_topics"][0]["topic"] == "authentication"

    @pytest.mark.asyncio
    async def test_multiple_topics_detected(self, server):
        """Multiple topics can be detected from a mixed selection."""
        paths = [
            "src/auth/login.py", "src/auth/session.py", "src/auth/tokens.py",
            "src/api/router.py", "src/api/middleware.py", "src/api/handler.py",
        ]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        topics = result.get("detected_topics", [])
        topic_names = [t["topic"] for t in topics]
        assert "authentication" in topic_names
        assert "API layer" in topic_names

    @pytest.mark.asyncio
    async def test_camelcase_filenames_split(self, server):
        """CamelCase filenames are correctly split into stems for matching."""
        paths = ["src/LoginForm.tsx", "src/SessionManager.tsx", "src/TokenRefresh.tsx"]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        topics = result.get("detected_topics", [])
        topic_names = [t["topic"] for t in topics]
        assert "authentication" in topic_names

    @pytest.mark.asyncio
    async def test_max_5_topics(self, server):
        """At most 5 topics are returned."""
        # Construct a selection that would match many clusters
        paths = [
            "src/login.py", "src/session.py",  # auth
            "src/cart.py", "src/checkout.py",  # ecommerce
            "src/button.tsx", "src/modal.tsx",  # UI
            "src/router.py", "src/middleware.py",  # API
            "src/model.py", "src/schema.py",  # data models
            "src/deploy.sh", "src/docker.yml",  # infra
            "src/event.py", "src/listener.py",  # messaging
        ]
        mock_get = await _mock_api_get_factory(included=_make_included_paths(paths))
        server._api_get = mock_get

        result = await server.tool_hi()

        topics = result.get("detected_topics", [])
        assert len(topics) <= 5
