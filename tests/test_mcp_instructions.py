"""Tests for client-aware MCP server instructions."""
from codrag.mcp.server import MCPServer


def _make_server(client_name="unknown"):
    """Create a minimal MCPServer instance for testing."""
    s = MCPServer.__new__(MCPServer)
    s._client_name = client_name
    s._client_version = ""
    s._initialize_roots = []
    s._codrag_called = False
    s._rules_atlas_hash_cache = {}
    return s


def test_instructions_short_for_claude():
    """Claude Code clients should get compact instructions."""
    server = _make_server("claude-code")
    instructions = server._build_instructions()
    assert len(instructions) < 300
    assert "codrag" in instructions.lower()
    assert "read-only" in instructions.lower() or "auto-approve" in instructions.lower()


def test_instructions_verbose_for_unknown():
    """Unknown clients should get the full instructions."""
    server = _make_server("unknown")
    instructions = server._build_instructions()
    assert "codrag_search" in instructions
    assert "codrag_impact" in instructions
    assert "codrag_audit" in instructions


def test_instructions_verbose_for_cursor():
    """Cursor gets verbose instructions (its rules file may not exist)."""
    server = _make_server("cursor")
    instructions = server._build_instructions()
    assert "codrag_search" in instructions


def test_instructions_short_for_gemini():
    """Gemini CLI gets compact instructions (it reads GEMINI.md)."""
    server = _make_server("gemini")
    instructions = server._build_instructions()
    assert len(instructions) < 300
