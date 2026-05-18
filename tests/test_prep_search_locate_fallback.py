"""Phase 136 Part 04 regression — prep_search auto-falls-back from
LOCATE to EXPLAIN when the symbol search returns zero hits on a
multi-token (descriptive natural-language) query.

Pre-Phase-136 dogfood evidence:
- 2026-05-09 ``"where is the file watcher debounce"`` → NODE_NOT_FOUND
- 2026-05-13 ``"where is the prep no-arg ambient context budget..."`` → 0 hits
- 2026-05-18 ``"where is the concepts module coverage"`` → 0 hits

The intent classifier is rule-based and intentionally cheap; when
its LOCATE rule fires on a multi-word description, the user gets
"No symbols found matching: ..." instead of the real semantic
answer.  Auto-fallback recovers without changing the classifier.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from prep.mcp.server import MCPServer


@pytest.fixture
def server() -> MCPServer:
    return MCPServer(daemon_url="http://127.0.0.1:8400", project_id="proj_test")


class TestLocateAutoFallback:
    """When LOCATE returns zero hits on a multi-token query, prep_search
    must transparently retry as EXPLAIN (semantic search)."""

    @pytest.mark.asyncio
    async def test_zero_hit_multi_token_falls_back_to_explain(self, server):
        # The dispatcher wraps results in the MCP envelope
        # ({"content": [...], "isError": ...}), so assert on the
        # underlying tool invocations + rendered text content.
        empty_locate = {"count": 0, "nodes": [], "_to_markdown": "No symbols found"}
        explain_result = {
            "count": 3,
            "_to_markdown": "## Semantic results\n- handler @ src/x.py:42",
        }
        with patch.object(
            server, "tool_trace_search", new=AsyncMock(return_value=empty_locate),
        ) as trace_mock, patch.object(
            server, "tool_search", new=AsyncMock(return_value=explain_result),
        ) as search_mock:
            result = await server.handle_tools_call({
                "name": "prep_search",
                "arguments": {"query": "where is the file watcher debounce"},
            })

        # Both paths called: LOCATE first, then EXPLAIN as fallback
        trace_mock.assert_called_once()
        search_mock.assert_called_once()
        # The fallback's content should be visible in the final response text.
        rendered = " ".join(c.get("text", "") for c in result.get("content", []))
        assert "Semantic results" in rendered, (
            "Fallback EXPLAIN content must appear in the wrapped response — "
            f"got {rendered!r}"
        )

    @pytest.mark.asyncio
    async def test_zero_hit_single_token_does_not_fall_back(self, server):
        # "where is augmenter" → rewrite strips "where is" → "augmenter"
        # → single token → no fallback (might just be an unindexed symbol).
        empty_locate = {"count": 0, "nodes": []}
        with patch.object(
            server, "tool_trace_search", new=AsyncMock(return_value=empty_locate),
        ) as trace_mock, patch.object(
            server, "tool_search", new=AsyncMock(),
        ) as search_mock:
            await server.handle_tools_call({
                "name": "prep_search",
                "arguments": {"query": "where is augmenter"},
            })

        trace_mock.assert_called_once()
        search_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_hit_results_skip_fallback(self, server):
        good_locate = {
            "count": 2,
            "nodes": [{"name": "Foo", "kind": "function"}],
        }
        with patch.object(
            server, "tool_trace_search", new=AsyncMock(return_value=good_locate),
        ) as trace_mock, patch.object(
            server, "tool_search", new=AsyncMock(),
        ) as search_mock:
            await server.handle_tools_call({
                "name": "prep_search",
                "arguments": {"query": "where is the deep reasoning engine"},
            })

        trace_mock.assert_called_once()
        search_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_explicit_symbol_type_skips_fallback(self, server):
        # type="symbol" is an explicit user signal — don't override it.
        empty_locate = {"count": 0, "nodes": []}
        with patch.object(
            server, "tool_trace_search", new=AsyncMock(return_value=empty_locate),
        ), patch.object(
            server, "tool_search", new=AsyncMock(),
        ) as search_mock:
            await server.handle_tools_call({
                "name": "prep_search",
                "arguments": {
                    "query": "where is the file watcher debounce",
                    "type": "symbol",
                },
            })

        search_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_explicit_intent_override_skips_fallback(self, server):
        empty_locate = {"count": 0, "nodes": []}
        with patch.object(
            server, "tool_trace_search", new=AsyncMock(return_value=empty_locate),
        ), patch.object(
            server, "tool_search", new=AsyncMock(),
        ) as search_mock:
            await server.handle_tools_call({
                "name": "prep_search",
                "arguments": {
                    "query": "where is the file watcher debounce",
                    "intent": "locate",
                },
            })

        search_mock.assert_not_called()
