"""
Smoke test for MCP Direct Mode.

Uses FakeEmbedder so no Ollama dependency is required.
Run with: pytest tests/test_mcp_direct_smoke.py -v
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from codrag.core import FakeEmbedder
from codrag.mcp_direct import DirectMCPServer


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    """Create a minimal test repository."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Create some test files
    (repo / "main.py").write_text(
        'def main() -> str:\n    """Return hello world."""\n    return "hello world"\n\nif __name__ == "__main__":\n    print(main())\n'
    )
    (repo / "README.md").write_text(
        "# Test Repo\n\nThis is a minimal test repository for smoke testing.\n"
    )
    (repo / "utils.py").write_text(
        'def add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b\n'
    )

    return repo


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    """Provide a FakeEmbedder for testing."""
    return FakeEmbedder(model="test-embed", dim=384)


@pytest.mark.asyncio
async def test_mcp_direct_status_before_build(mini_repo: Path, fake_embedder: FakeEmbedder):
    """Status should show empty index before build."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    status = await server.tool_status()

    assert status["daemon"] == "direct_mode"
    assert status["repo_root"] == str(mini_repo)
    assert status["total_documents"] == 0
    assert status["index_loaded"] is False
    assert status["building"] is False


@pytest.mark.asyncio
async def test_mcp_direct_build(mini_repo: Path, fake_embedder: FakeEmbedder):
    """Build should complete and populate the index."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    # Trigger build
    build_result = await server.tool_build()
    assert build_result["status"] == "started"

    # Wait for build to complete (polling)
    for _ in range(30):
        await asyncio.sleep(0.1)
        status = await server.tool_status()
        if not status["building"] and status["index_loaded"]:
            break

    # Verify build completed
    status = await server.tool_status()
    assert status["index_loaded"] is True
    assert status["total_documents"] > 0
    assert status["building"] is False


@pytest.mark.asyncio
async def test_mcp_direct_search(mini_repo: Path, fake_embedder: FakeEmbedder):
    """Search should return results after build."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    # Build first
    await server.tool_build()
    for _ in range(30):
        await asyncio.sleep(0.1)
        status = await server.tool_status()
        if not status["building"] and status["index_loaded"]:
            break

    # Search
    result = await server.tool_search("hello world")

    assert result["query"] == "hello world"
    assert result["count"] > 0
    assert len(result["results"]) > 0
    # Check that results have expected fields
    first = result["results"][0]
    assert "path" in first
    assert "score" in first
    assert "content" in first


@pytest.mark.asyncio
async def test_mcp_direct_context(mini_repo: Path, fake_embedder: FakeEmbedder):
    """Context assembly should return formatted context after build."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    # Ensure init + build
    await server._ensure_init()
    await server.tool_build()
    for _ in range(30):
        await asyncio.sleep(0.1)
        status = await server.tool_status()
        if not status["building"] and status["index_loaded"]:
            break

    # Verify index is loaded
    assert server._index is not None
    assert server._index.is_loaded()

    # Get context - use low min_score since FakeEmbedder produces low similarity scores
    # (real embedders like nomic-embed-text produce higher scores for semantic matches)
    result = server._index.get_context_structured("explain the main function", k=5, min_score=0.0)

    assert "context" in result
    assert len(result["context"]) > 0
    assert len(result["chunks"]) > 0
    assert result["total_chars"] > 0


@pytest.mark.asyncio
async def test_mcp_direct_search_before_build(mini_repo: Path, fake_embedder: FakeEmbedder):
    """Search before build should return empty results with error hint."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    result = await server.tool_search("hello")

    assert result["count"] == 0
    assert "error" in result or len(result["results"]) == 0


@pytest.mark.asyncio
async def test_mcp_direct_protocol_initialize(mini_repo: Path, fake_embedder: FakeEmbedder):
    """MCP initialize should return protocol version and capabilities."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    result = await server.handle_initialize({})

    assert result["protocolVersion"] == "2024-11-05"
    assert "capabilities" in result
    assert "tools" in result["capabilities"]
    assert "serverInfo" in result
    assert result["serverInfo"]["name"] == "codrag-direct"


@pytest.mark.asyncio
async def test_mcp_direct_protocol_tools_list(mini_repo: Path, fake_embedder: FakeEmbedder):
    """MCP tools/list should return available tools."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    result = await server.handle_tools_list({})

    assert "tools" in result
    tools = result["tools"]
    tool_names = {t["name"] for t in tools}
    assert "codrag_status" in tool_names
    assert "codrag_build" in tool_names
    assert "codrag_search" in tool_names
    assert "codrag" in tool_names


@pytest.mark.asyncio
async def test_mcp_direct_protocol_tools_call(mini_repo: Path, fake_embedder: FakeEmbedder):
    """MCP tools/call should invoke the correct tool."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    result = await server.handle_tools_call(
        {
            "name": "codrag_status",
            "arguments": {},
        }
    )

    assert result["isError"] is False
    assert "content" in result
    assert len(result["content"]) > 0
    assert result["content"][0]["type"] == "text"


@pytest.mark.asyncio
async def test_mcp_direct_handle_request(mini_repo: Path, fake_embedder: FakeEmbedder):
    """Full JSON-RPC request handling should work."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    response = await server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
    )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert response["result"]["protocolVersion"] == "2024-11-05"


@pytest.mark.asyncio
async def test_mcp_direct_unknown_method(mini_repo: Path, fake_embedder: FakeEmbedder):
    """Unknown method should return error."""
    server = DirectMCPServer(repo_root=mini_repo, embedder=fake_embedder)

    response = await server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "unknown/method",
            "params": {},
        }
    )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    assert "error" in response
    assert response["error"]["code"] == -32601  # METHOD_NOT_FOUND
