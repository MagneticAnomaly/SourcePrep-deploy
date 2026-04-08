import pytest
from codrag.core.sarif_adapters import get_adapter, get_tool_context, ToolAdapter


def test_get_adapter_known_tool():
    adapter = get_adapter("semgrep")
    assert adapter.tool_name == "semgrep"
    assert adapter.focus == "blast_radius"


def test_get_adapter_case_insensitive():
    adapter = get_adapter("Ruff")
    assert adapter.tool_name == "ruff"


def test_get_adapter_prefix_match():
    adapter = get_adapter("semgrep-oss")
    assert adapter.tool_name == "semgrep"


def test_get_adapter_unknown_tool():
    adapter = get_adapter("my-custom-linter")
    assert adapter.tool_name == "unknown"
    assert adapter.focus == "composite"


def test_get_adapter_empty_string():
    adapter = get_adapter("")
    assert adapter.tool_name == "unknown"


def test_get_tool_context_known():
    ctx = get_tool_context("ruff")
    assert "complexity" in ctx.lower() or "hub" in ctx.lower()


def test_get_tool_context_unknown():
    ctx = get_tool_context("custom")
    assert "standard" in ctx.lower() or "unknown" in ctx.lower()
