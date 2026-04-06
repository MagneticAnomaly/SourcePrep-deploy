"""
Tests for the CoDRAG MCP server.

Tests cover:
- MCP protocol handling (initialize, tools/list, tools/call)
- Tool implementations (status, build, search, context)
- Error handling (daemon unavailable, invalid params)
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from codrag.mcp_server import (
    MCPServer,
    TOOLS,
    MCP_PROTOCOL_VERSION,
    JSONRPC_VERSION,
    BuildInProgressError,
    DaemonUnavailableError,
    InvalidParamsError,
    MethodNotFoundError,
    ProjectSelectionAmbiguousError,
    MAX_CONTEXT_K,
    MAX_CONTEXT_CHARS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def server():
    """Create an MCP server instance."""
    return MCPServer(daemon_url="http://127.0.0.1:8400", project_id="proj_test")


@pytest.fixture
def mock_status_response():
    """Mock response from /projects/{project_id}/status."""
    return {
        "index": {
            "exists": True,
            "total_chunks": 150,
            "embedding_model": "nomic-embed-text",
            "last_build_at": "2026-02-01T08:00:00Z",
        },
        "building": False,
        "watch": {"enabled": True},
    }


@pytest.fixture
def mock_search_response():
    """Mock response from /projects/{project_id}/search."""
    return {
        "results": [
            {
                "chunk_id": "chunk_1",
                "source_path": "src/main.py",
                "span": {"start_line": 1, "end_line": 2},
                "preview": "def main():\n    print('hello')",
                "score": 0.85,
            },
            {
                "chunk_id": "chunk_2",
                "source_path": "README.md",
                "span": {"start_line": 1, "end_line": 3},
                "preview": "# Installation\n\npip install codrag",
                "score": 0.72,
            },
        ],
    }


@pytest.fixture
def mock_context_response():
    """Mock response from /projects/{project_id}/context."""
    return {
        "context": "[src/main.py | def main]\ndef main():\n    print('hello')",
        "chunks": [{"chunk_id": "chunk_1", "source_path": "src/main.py", "score": 0.85}],
        "total_chars": 50,
        "estimated_tokens": 12,
    }


# =============================================================================
# Protocol Tests
# =============================================================================

class TestMCPProtocol:
    """Test MCP protocol handling."""

    @pytest.mark.asyncio
    async def test_initialize(self, server):
        """Test initialize request returns correct capabilities."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        
        response = await server.handle_request(request)
        
        assert response["jsonrpc"] == JSONRPC_VERSION
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == MCP_PROTOCOL_VERSION
        assert "tools" in response["result"]["capabilities"]
        assert response["result"]["serverInfo"]["name"] == "codrag"

    @pytest.mark.asyncio
    async def test_tools_list(self, server):
        """Test tools/list returns all tools."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        
        response = await server.handle_request(request)
        
        assert response["id"] == 2
        tools = response["result"]["tools"]
        assert len(tools) == 5  # Phase 50: consolidated from 16 to 5
        
        tool_names = {t["name"] for t in tools}
        assert tool_names == {"codrag", "codrag_search", "codrag_impact", "codrag_audit", "codrag_observe"}

    @pytest.mark.asyncio
    async def test_ping(self, server):
        """Test ping request."""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "ping",
            "params": {},
        }
        
        response = await server.handle_request(request)
        
        assert response["id"] == 3
        assert response["result"] == {}

    @pytest.mark.asyncio
    async def test_unknown_method(self, server):
        """Test unknown method returns error."""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "unknown/method",
            "params": {},
        }
        
        response = await server.handle_request(request)
        
        assert response["id"] == 4
        assert "error" in response
        assert response["error"]["code"] == -32601  # METHOD_NOT_FOUND

    @pytest.mark.asyncio
    async def test_notification_no_response(self, server):
        """Test notifications (no id) don't get responses."""
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        
        response = await server.handle_request(request)
        
        assert response is None


# =============================================================================
# Tool Tests
# =============================================================================

class TestToolStatus:
    """Test codrag_status tool."""

    @pytest.mark.asyncio
    async def test_status_success(self, server, mock_status_response):
        """Test successful status call."""
        with patch.object(server, "_api_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_status_response
            
            result = await server.tool_status()
            
            assert result["project_id"] == server.project_id
            assert result["daemon"] == "running"
            assert result["index_loaded"] is True
            assert result["total_documents"] == 150
            assert result["building"] is False
            mock_get.assert_called_once_with(f"/projects/{server.project_id}/status")

    @pytest.mark.asyncio
    async def test_status_daemon_unavailable(self, server):
        """Test status when daemon is unavailable."""
        with patch.object(server, "_api_get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = DaemonUnavailableError("Cannot connect")
            
            with pytest.raises(DaemonUnavailableError):
                await server.tool_status()

    @pytest.mark.asyncio
    async def test_status_project_selection_ambiguous_raises(self):
        """Test status without project selection raises PROJECT_SELECTION_AMBIGUOUS."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400", project_id=None, auto_detect=False)
        with patch.object(srv, "_api_get", new_callable=AsyncMock) as mock_get, \
             patch("codrag.mcp_server.Path") as mock_path:
            # CWD must not match any project path
            mock_path.cwd.return_value.resolve.return_value = MagicMock(__str__=lambda s: "/nowhere")
            mock_path.cwd.return_value.__str__ = lambda s: "/nowhere"
            mock_get.return_value = {
                "projects": [
                    {"id": "p1", "name": "A", "path": "/tmp/a"},
                    {"id": "p2", "name": "B", "path": "/tmp/b"},
                ]
            }

            with pytest.raises(ProjectSelectionAmbiguousError) as e:
                await srv.tool_status()
            assert "PROJECT_SELECTION_AMBIGUOUS" in str(e.value)
            assert "project_id" in str(e.value)  # Hint mentions tool-level param


class TestToolBuild:
    """Test codrag_build tool."""

    @pytest.mark.asyncio
    async def test_build_started(self, server):
        """Test build starts successfully."""
        with patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"started": True}
            
            result = await server.tool_build()
            
            assert result["status"] == "started"
            mock_post.assert_called_once_with(f"/projects/{server.project_id}/build", {})

    @pytest.mark.asyncio
    async def test_build_already_in_progress(self, server):
        """Test build when already building."""
        with patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = BuildInProgressError("BUILD_ALREADY_RUNNING: Build already running")
            
            result = await server.tool_build()
            
            assert result["status"] == "already_building"


class TestToolSearch:
    """Test codrag_search tool (query-based context with trace + routing)."""

    @pytest.mark.asyncio
    async def test_search_success(self, server, mock_context_response):
        """Test successful query-based context retrieval."""
        with patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_context_response

            result = await server.tool_search(query="test query")

            assert "context" in result
            assert result["chunks_used"] == 1
            assert result["total_chars"] == 50
            mock_post.assert_called_once_with(
                f"/projects/{server.project_id}/context",
                {
                    "query": "test query",
                    "k": 5,
                    "max_chars": 12000,
                    "include_sources": True,
                    "include_scores": False,
                    "structured": True,
                    "trace_expand": True,
                },
            )

    @pytest.mark.asyncio
    async def test_search_empty_query(self, server):
        """Test search with empty query raises error."""
        with pytest.raises(InvalidParamsError):
            await server.tool_search(query="")

    @pytest.mark.asyncio
    async def test_search_whitespace_query(self, server):
        """Test search with whitespace-only query raises error."""
        with pytest.raises(InvalidParamsError):
            await server.tool_search(query="   ")

    @pytest.mark.asyncio
    async def test_search_max_chars_too_large(self, server):
        """Test search rejects pathological max_chars values."""
        with pytest.raises(InvalidParamsError) as e:
            await server.tool_search(query="test", max_chars=MAX_CONTEXT_CHARS + 1)
        assert f"max {MAX_CONTEXT_CHARS}" in str(e.value)


class TestToolContext:
    """Test codrag tool (ambient context assembly, no query)."""

    @pytest.mark.asyncio
    async def test_ambient_context_success(self, server):
        """Test ambient context retrieval (no query)."""
        ambient_response = {
            "context": "[hub | in-degree:5 | @src/main.py]\ndef main(): ...",
            "chunks": [{"source_path": "src/main.py", "ambient_role": "hub"}],
            "total_chars": 50,
            "estimated_tokens": 12,
            "ambient": True,
            "hub_files": 1,
            "modules_in_scope": 0,
            "neighbor_files": 0,
        }
        with patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post, \
             patch.object(server, "_project_has_rules_file", return_value=False):
            mock_post.return_value = ambient_response

            result = await server.tool_context()

            assert "context" in result
            assert result["ambient"] is True
            assert result["hub_files"] == 1
            # ISSUE-6: include_atlas=True when no rules file exists
            mock_post.assert_called_once_with(
                f"/projects/{server.project_id}/context",
                {"query": "", "max_chars": 12000, "include_atlas": True},
            )

    @pytest.mark.asyncio
    async def test_ambient_context_max_chars_too_large(self, server):
        """Test ambient context rejects pathological max_chars values."""
        with pytest.raises(InvalidParamsError) as e:
            await server.tool_context(max_chars=MAX_CONTEXT_CHARS + 1)
        assert f"max {MAX_CONTEXT_CHARS}" in str(e.value)


# =============================================================================
# Integration Tests (tools/call)
# =============================================================================

class TestToolsCall:
    """Test tools/call endpoint."""

    @pytest.mark.asyncio
    async def test_call_status_alias(self, server):
        """Test calling legacy codrag_status routes to codrag (ambient context) via alias."""
        ambient_response = {
            "context": "test context",
            "total_chars": 100,
            "estimated_tokens": 25,
            "ambient": True,
            "hub_files": 0,
            "modules_in_scope": 0,
            "neighbor_files": 0,
        }
        with patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = ambient_response
            
            request = {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "codrag_status",
                    "arguments": {},
                },
            }
            
            response = await server.handle_request(request)
            
            assert response["id"] == 10
            result = response["result"]
            assert result["isError"] is False
            assert len(result["content"]) == 1
            assert result["content"][0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_call_search(self, server, mock_context_response):
        """Test calling search tool via MCP protocol (now uses /context endpoint)."""
        with patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_context_response
            
            request = {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "codrag_search",
                    "arguments": {"query": "find main function"},
                },
            }
            
            response = await server.handle_request(request)
            
            assert response["result"]["isError"] is False
            # Phase 50: search results now return markdown via _to_markdown
            text = response["result"]["content"][0]["text"]
            assert isinstance(text, str)
            assert len(text) > 0
            mock_post.assert_called_once_with(
                f"/projects/{server.project_id}/context",
                {
                    "query": "find main function",
                    "k": 5,
                    "max_chars": 12000,
                    "include_sources": True,
                    "include_scores": False,
                    "structured": True,
                    "trace_expand": True,
                },
            )

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, server):
        """Test calling unknown tool returns error."""
        request = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {},
            },
        }
        
        response = await server.handle_request(request)
        
        assert "error" in response
        assert response["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_call_daemon_error_returns_tool_error(self, server):
        """Test daemon error returns isError=True, not protocol error."""
        with patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = DaemonUnavailableError("Cannot connect")
            
            request = {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {
                    "name": "codrag",
                    "arguments": {},
                },
            }
            
            response = await server.handle_request(request)
            
            # Should return result with isError=True, not a protocol error
            assert "result" in response
            assert response["result"]["isError"] is True
            assert "Cannot connect" in response["result"]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_call_search_k_too_large_returns_tool_error(self, server):
        request = {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "codrag_search",
                "arguments": {"query": "find", "k": MAX_CONTEXT_K + 1},
            },
        }

        response = await server.handle_request(request)
        assert response["result"]["isError"] is True
        assert f"max {MAX_CONTEXT_K}" in response["result"]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_call_context_max_chars_too_large_returns_tool_error(self, server):
        request = {
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {
                "name": "codrag",
                "arguments": {"max_chars": MAX_CONTEXT_CHARS + 1},
            },
        }

        response = await server.handle_request(request)
        assert response["result"]["isError"] is True
        assert f"max {MAX_CONTEXT_CHARS}" in response["result"]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_call_status_project_selection_ambiguous_returns_tool_error(self):
        srv = MCPServer(daemon_url="http://127.0.0.1:8400", project_id=None, auto_detect=False)
        with patch.object(srv, "_api_get", new_callable=AsyncMock) as mock_get, \
             patch("codrag.mcp_server.Path") as mock_path:
            mock_path.cwd.return_value.resolve.return_value = MagicMock(__str__=lambda s: "/nowhere")
            mock_path.cwd.return_value.__str__ = lambda s: "/nowhere"
            mock_get.return_value = {
                "projects": [
                    {"id": "p1", "name": "A", "path": "/tmp/a"},
                    {"id": "p2", "name": "B", "path": "/tmp/b"},
                ]
            }

            request = {
                "jsonrpc": "2.0",
                "id": 16,
                "method": "tools/call",
                "params": {"name": "codrag_status", "arguments": {}},
            }

            response = await srv.handle_request(request)
            assert response["result"]["isError"] is True
            assert "PROJECT_SELECTION_AMBIGUOUS" in response["result"]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_call_status_with_project_id_override(self):
        """Test that passing project_id in tool args bypasses auto-detect."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400", project_id=None)
        ambient_response = {
            "context": "test context",
            "total_chars": 100,
            "estimated_tokens": 25,
            "ambient": True,
            "hub_files": 0,
            "modules_in_scope": 0,
            "neighbor_files": 0,
        }
        with patch.object(srv, "_api_post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = ambient_response

            request = {
                "jsonrpc": "2.0",
                "id": 17,
                "method": "tools/call",
                "params": {
                    "name": "codrag",
                    "arguments": {"project_id": "proj_override"},
                },
            }

            response = await srv.handle_request(request)
            assert response["result"]["isError"] is False
            # Verify the override project_id was used in the API call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "/projects/proj_override/context" in call_args[0][0]


# =============================================================================
# Tool Schema Tests
# =============================================================================

class TestToolSchemas:
    """Test tool definitions match expected schemas."""

    def test_all_tools_have_required_fields(self):
        """Test all tools have name, description, inputSchema."""
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_all_tools_have_project_id(self):
        """Test all tools expose optional project_id parameter."""
        for tool in TOOLS:
            props = tool["inputSchema"].get("properties", {})
            assert "project_id" in props, f"Tool '{tool['name']}' missing project_id"
            assert props["project_id"]["type"] == "string"
            # project_id must NOT be required
            assert "project_id" not in tool["inputSchema"].get("required", [])

    def test_search_requires_query(self):
        """Test search tool requires query parameter."""
        search_tool = next(t for t in TOOLS if t["name"] == "codrag_search")
        assert "query" in search_tool["inputSchema"]["required"]

    def test_context_no_required_params(self):
        """Test codrag (ambient) tool has no required parameters."""
        context_tool = next(t for t in TOOLS if t["name"] == "codrag")
        assert context_tool["inputSchema"]["required"] == []
        assert "query" not in context_tool["inputSchema"]["properties"]

    def test_audit_no_required_params(self):
        """Test codrag_audit has no required parameters."""
        audit_tool = next(t for t in TOOLS if t["name"] == "codrag_audit")
        assert audit_tool["inputSchema"]["required"] == []

    def test_observe_no_required_params(self):
        """Test codrag_observe has no required parameters."""
        observe_tool = next(t for t in TOOLS if t["name"] == "codrag_observe")
        assert observe_tool["inputSchema"]["required"] == []

    def test_annotations_on_tools(self):
        """Test all tools have annotations (MCP spec 2025-06-18)."""
        for tool in TOOLS:
            assert "annotations" in tool, f"Tool '{tool['name']}' missing annotations"
            assert "readOnlyHint" in tool["annotations"]


# =============================================================================
# Multi-Project Routing Tests
# =============================================================================

@pytest.fixture(autouse=True)
def mock_pointer_and_signal():
    """Mock the pointer and signal checks by default to not interfere with any routing tests."""
    with patch("codrag.core.project_registry.read_codrag_pointer", return_value=None), \
         patch("codrag.core.project_registry.read_active_project_signal", return_value=None):
        yield

class TestProjectRouting:
    """Test multi-project routing mechanisms."""

    def test_uri_to_path_file_uri(self):
        """Test file:// URI conversion."""
        assert MCPServer._uri_to_path("file:///Users/alice/projects/app") == "/Users/alice/projects/app"
        assert MCPServer._uri_to_path("file:///tmp/test") == "/tmp/test"

    def test_uri_to_path_bare_path(self):
        """Test bare absolute path passthrough."""
        assert MCPServer._uri_to_path("/Users/alice/projects/app") == "/Users/alice/projects/app"

    def test_uri_to_path_invalid(self):
        """Test invalid URIs return None."""
        assert MCPServer._uri_to_path("") is None
        assert MCPServer._uri_to_path("https://example.com") is None
        assert MCPServer._uri_to_path("relative/path") is None

    def test_best_project_match_exact(self):
        """Test exact path match."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400")
        projects = [
            {"id": "p1", "path": "/Users/alice/frontend"},
            {"id": "p2", "path": "/Users/alice/backend"},
        ]
        assert srv._best_project_match(projects, ["/Users/alice/frontend"]) == "p1"
        assert srv._best_project_match(projects, ["/Users/alice/backend"]) == "p2"

    def test_best_project_match_subdirectory(self):
        """Test CWD inside project directory."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400")
        projects = [
            {"id": "p1", "path": "/Users/alice/frontend"},
            {"id": "p2", "path": "/Users/alice/backend"},
        ]
        assert srv._best_project_match(projects, ["/Users/alice/frontend/src/components"]) == "p1"

    def test_best_project_match_longest_prefix(self):
        """Test most-specific (longest) path wins."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400")
        projects = [
            {"id": "p_parent", "path": "/Users/alice/monorepo"},
            {"id": "p_child", "path": "/Users/alice/monorepo/packages/app"},
        ]
        assert srv._best_project_match(
            projects, ["/Users/alice/monorepo/packages/app/src"]
        ) == "p_child"

    def test_best_project_match_no_match(self):
        """Test no match returns None."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400")
        projects = [{"id": "p1", "path": "/Users/alice/frontend"}]
        assert srv._best_project_match(projects, ["/Users/bob/other"]) is None

    def test_best_project_match_ambiguous(self):
        """Test same-length prefix tie returns None (ambiguous)."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400")
        # Two projects with same-length paths, CWD is parent of both
        projects = [
            {"id": "p1", "path": "/a/b"},
            {"id": "p2", "path": "/a/c"},
        ]
        # CWD "/a" doesn't match either (not a prefix of /a/b or /a/c)
        assert srv._best_project_match(projects, ["/a"]) is None

    @pytest.mark.asyncio
    async def test_initialize_extracts_roots(self):
        """Test initialize handler extracts workspace roots."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400")
        await srv.handle_initialize({
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "test"},
            "roots": [
                {"uri": "file:///Users/alice/projects/app", "name": "app"},
            ],
        })
        assert srv._initialize_roots == ["/Users/alice/projects/app"]

    @pytest.mark.asyncio
    async def test_initialize_extracts_workspace_folders(self):
        """Test initialize handler extracts LSP-style workspaceFolders."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400")
        await srv.handle_initialize({
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "test"},
            "workspaceFolders": [
                {"uri": "file:///Users/alice/projects/app", "name": "app"},
                {"uri": "file:///Users/alice/projects/lib", "name": "lib"},
            ],
        })
        assert len(srv._initialize_roots) == 2
        assert "/Users/alice/projects/app" in srv._initialize_roots
        assert "/Users/alice/projects/lib" in srv._initialize_roots

    @pytest.mark.asyncio
    async def test_resolve_uses_initialize_roots(self):
        """Test project resolution uses initialize roots over CWD."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400")
        srv._initialize_roots = ["/Users/alice/frontend"]

        with patch.object(srv, "_api_get", new_callable=AsyncMock) as mock_get, \
             patch("codrag.mcp_server.Path") as mock_path:
            # CWD is somewhere unrelated
            mock_path.cwd.return_value.resolve.return_value = MagicMock(__str__=lambda s: "/nowhere")
            mock_path.cwd.return_value.__str__ = lambda s: "/nowhere"
            mock_get.return_value = {
                "projects": [
                    {"id": "p1", "name": "Frontend", "path": "/Users/alice/frontend"},
                    {"id": "p2", "name": "Backend", "path": "/Users/alice/backend"},
                ]
            }

            result = await srv._resolve_project_id()
            assert result == "p1"

    @pytest.mark.asyncio
    async def test_resolve_override_takes_priority(self):
        """Test tool-level override bypasses all other detection."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400", project_id="pinned_proj")
        # Override should win over pinned project
        result = await srv._resolve_project_id(override="override_proj")
        assert result == "override_proj"

    @pytest.mark.asyncio
    async def test_resolve_pinned_takes_priority_over_auto(self):
        """Test CLI-pinned project bypasses auto-detection."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400", project_id="pinned_proj")
        result = await srv._resolve_project_id()
        assert result == "pinned_proj"

    @pytest.mark.asyncio
    async def test_resolve_cwd_always_attempted(self):
        """Test CWD matching works even without --auto flag."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400", project_id=None, auto_detect=False)

        with patch.object(srv, "_api_get", new_callable=AsyncMock) as mock_get, \
             patch("codrag.mcp.server.Path") as mock_path:
            mock_cwd = MagicMock()
            mock_cwd.resolve.return_value = "/Users/alice/frontend/src"
            mock_path.cwd.return_value = mock_cwd
            
            mock_get.return_value = {
                "projects": [
                    {"id": "p1", "name": "Frontend", "path": "/Users/alice/frontend"},
                    {"id": "p2", "name": "Backend", "path": "/Users/alice/backend"},
                ]
            }

            result = await srv._resolve_project_id()
            assert result == "p1"

    @pytest.mark.asyncio
    async def test_resolve_single_project_shortcut(self):
        """Test single project is used automatically when CWD doesn't match."""
        srv = MCPServer(daemon_url="http://127.0.0.1:8400", project_id=None)

        with patch.object(srv, "_api_get", new_callable=AsyncMock) as mock_get, \
             patch("codrag.mcp_server.Path") as mock_path:
            mock_path.cwd.return_value.resolve.return_value = MagicMock(__str__=lambda s: "/nowhere")
            mock_path.cwd.return_value.__str__ = lambda s: "/nowhere"
            mock_get.return_value = {
                "projects": [{"id": "only_one", "name": "Solo", "path": "/some/path"}]
            }

            result = await srv._resolve_project_id()
            assert result == "only_one"


# =============================================================================
# Tool Annotation Tests
# =============================================================================

from codrag.mcp_tools import TOOLS as MCP_TOOLS


def test_all_tools_have_title():
    """Every production tool must have a title annotation for UI display."""
    for tool in MCP_TOOLS:
        annotations = tool.get("annotations", {})
        assert "title" in annotations, f"Tool {tool['name']} missing 'title' annotation"
        assert isinstance(annotations["title"], str)
        assert len(annotations["title"]) > 0


def test_all_tools_have_destructive_hint():
    """Every tool must declare destructiveHint (none are destructive)."""
    for tool in MCP_TOOLS:
        annotations = tool.get("annotations", {})
        assert "destructiveHint" in annotations, f"Tool {tool['name']} missing 'destructiveHint'"
        assert annotations["destructiveHint"] is False, f"Tool {tool['name']} should not be destructive"


def test_readonly_tools_have_idempotent_hint():
    """Read-only tools should declare idempotentHint=True."""
    readonly_tools = [t for t in MCP_TOOLS if t.get("annotations", {}).get("readOnlyHint")]
    for tool in readonly_tools:
        annotations = tool.get("annotations", {})
        assert annotations.get("idempotentHint") is True, (
            f"Read-only tool {tool['name']} should be idempotent"
        )


# =============================================================================
# Resource tests
# =============================================================================


def test_resources_list_has_all_types():
    """Resource list should include all 7 resource types."""
    import asyncio

    server = MCPServer(daemon_url="http://127.0.0.1:8400", project_id="test-project")
    server._resolve_project_id = AsyncMock(return_value="test-project")

    result = asyncio.get_event_loop().run_until_complete(
        server.handle_resources_list({})
    )
    resource_names = {r["name"] for r in result["resources"]}
    expected = {
        "Codebase Atlas",
        "Codebase Structure",
        "Module Map",
        "Audit Findings",
        "Concepts",
        "Focus Areas",
        "Index Health",
    }
    assert expected.issubset(resource_names), f"Missing: {expected - resource_names}"


def test_resources_have_audience_annotations():
    """All resources should have audience annotations."""
    import asyncio

    server = MCPServer(daemon_url="http://127.0.0.1:8400", project_id="test-project")
    server._resolve_project_id = AsyncMock(return_value="test-project")

    result = asyncio.get_event_loop().run_until_complete(
        server.handle_resources_list({})
    )
    for resource in result["resources"]:
        annotations = resource.get("annotations", {})
        assert "audience" in annotations, f"Resource {resource['name']} missing audience annotation"
        assert isinstance(annotations["audience"], list)


def test_prompts_list_has_all_prompts():
    """Prompt list should include onboard, review, plan, investigate, health."""
    import asyncio

    server = MCPServer.__new__(MCPServer)
    server._client_name = "claude-code"
    server._client_version = ""
    server._codrag_called = False
    server._pinned_project = None
    server._initialize_roots = []
    server._notification_callback = None
    server._last_atlas_signal = {}

    result = asyncio.get_event_loop().run_until_complete(
        server.handle_prompts_list({})
    )
    prompt_names = {p["name"] for p in result["prompts"]}
    expected = {"codrag-onboard", "codrag-review", "codrag-plan", "codrag-investigate", "codrag-health"}
    assert expected.issubset(prompt_names), f"Missing: {expected - prompt_names}"


def test_prompt_onboard_returns_messages():
    """The onboard prompt should return structured messages."""
    import asyncio

    server = MCPServer.__new__(MCPServer)
    server._client_name = "claude-code"
    server._client_version = ""
    server._codrag_called = False
    server._pinned_project = None
    server._initialize_roots = []
    server._notification_callback = None
    server._last_atlas_signal = {}

    result = asyncio.get_event_loop().run_until_complete(
        server.handle_prompts_get({"name": "codrag-onboard", "arguments": {}})
    )
    assert "messages" in result
    assert len(result["messages"]) > 0
    assert result["messages"][0]["role"] == "user"


def test_prompt_investigate_uses_query():
    """The investigate prompt should use the query argument."""
    import asyncio

    server = MCPServer.__new__(MCPServer)
    server._client_name = "claude-code"
    server._client_version = ""
    server._codrag_called = False
    server._pinned_project = None
    server._initialize_roots = []
    server._notification_callback = None
    server._last_atlas_signal = {}

    result = asyncio.get_event_loop().run_until_complete(
        server.handle_prompts_get({
            "name": "codrag-investigate",
            "arguments": {"query": "authentication flow"},
        })
    )
    assert "authentication flow" in result["messages"][0]["content"]["text"]


def test_prompt_analyze_backward_compat():
    """The old codrag-analyze prompt should redirect to codrag-onboard."""
    import asyncio

    server = MCPServer.__new__(MCPServer)
    server._client_name = "claude-code"
    server._client_version = ""
    server._codrag_called = False
    server._pinned_project = None
    server._initialize_roots = []
    server._notification_callback = None
    server._last_atlas_signal = {}

    result = asyncio.get_event_loop().run_until_complete(
        server.handle_prompts_get({"name": "codrag-analyze", "arguments": {}})
    )
    assert "messages" in result
    # Should get the onboard prompt content
    assert "Orient" in result["messages"][0]["content"]["text"]
