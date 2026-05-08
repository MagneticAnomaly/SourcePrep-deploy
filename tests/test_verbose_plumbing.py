"""
End-to-end plumbing tests for the `verbose=true` opt-out introduced in
docs/Phase82_MCP-Dogfooding/17_Followup_2026-05-08.md (FIX-16-1).

The formatter cap is already covered by `tests/test_module_tiers_cap.py`.
These tests verify that an agent calling `prep(verbose=true)` actually
reaches the formatter — which requires the param to flow through:

    MCP tool schema -> tool_context() -> /context POST payload ->
    ContextRequest -> _assemble_ambient_context -> _format_module_tiers
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from prep.api.routers.projects.models import ContextRequest
from prep.mcp_server import MCPServer


# --- ContextRequest schema ------------------------------------------------------

def test_context_request_accepts_verbose_true():
    req = ContextRequest(verbose=True)
    assert req.verbose is True


def test_context_request_verbose_defaults_false():
    req = ContextRequest()
    assert req.verbose is False


# --- tool_context propagates verbose into the API payload -----------------------

@pytest.fixture
def server():
    return MCPServer(daemon_url="http://127.0.0.1:8400", project_id="proj_test")


@pytest.mark.asyncio
async def test_tool_context_propagates_verbose_true(server):
    """When the agent calls prep(verbose=true), the /context POST payload
    must include verbose=true so the assembler skips the firehose cap."""
    ambient_response = {
        "context": "stub",
        "total_chars": 0,
        "estimated_tokens": 0,
        "ambient": True,
        "hub_files": 0,
        "modules_in_scope": 0,
        "neighbor_files": 0,
    }
    with patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post, \
         patch.object(server, "_project_has_rules_file", return_value=False):
        mock_post.return_value = ambient_response
        await server.tool_context(verbose=True)

        # First positional arg is the path; second is the payload dict
        assert mock_post.call_args is not None
        path_arg = mock_post.call_args[0][0]
        payload = mock_post.call_args[0][1]
        assert path_arg == f"/projects/{server.project_id}/context"
        assert payload.get("verbose") is True


@pytest.mark.asyncio
async def test_tool_context_default_does_not_set_verbose(server):
    """Default call (no verbose arg) keeps the bounded behavior — payload
    either omits verbose or sets it to False."""
    ambient_response = {
        "context": "stub",
        "total_chars": 0,
        "estimated_tokens": 0,
        "ambient": True,
        "hub_files": 0,
        "modules_in_scope": 0,
        "neighbor_files": 0,
    }
    with patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post, \
         patch.object(server, "_project_has_rules_file", return_value=False):
        mock_post.return_value = ambient_response
        await server.tool_context()

        payload = mock_post.call_args[0][1]
        # Either absent or explicitly False — both mean "use the cap"
        assert payload.get("verbose", False) is False


# --- _assemble_ambient_context forwards verbose to _format_module_tiers ---------

def test_assembler_signature_accepts_verbose():
    """The assembler must expose a `verbose` parameter so the endpoint can
    forward it. We verify the signature directly rather than driving the
    assembler — the latter requires a fully-formed Project + index dir +
    tracegraph that aren't worth fixturing for a single one-line forward.
    """
    import inspect

    from prep.api.routers.projects.search import _assemble_ambient_context

    sig = inspect.signature(_assemble_ambient_context)
    assert "verbose" in sig.parameters
    assert sig.parameters["verbose"].default is False


def test_endpoint_forwards_req_verbose_to_assembler():
    """Source-level guard: the /context endpoint must pass req.verbose to
    `_assemble_ambient_context`. Catches accidental drops during refactor."""
    import inspect

    from prep.api.routers.projects.search import context_project

    src = inspect.getsource(context_project)
    # Two call sites must both forward verbose: the main path and the
    # KnowledgeIndex fallback path.
    assert src.count("verbose=req.verbose") >= 2, (
        "context_project should forward req.verbose to both _assemble_ambient_context "
        "and the KnowledgeIndex-fallback _format_module_tiers call."
    )
