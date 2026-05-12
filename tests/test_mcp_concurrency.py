"""
Concurrency tests for the MCP server.

Covers two fixes for the "multiple parallel `prep` calls are unstable"
dogfooding finding:

1. `tool_context` request coalescing — N concurrent identical calls fan
   into a single `_tool_context_impl` invocation. Each caller gets an
   independent (deepcopied) result so downstream mutations don't leak.

2. `_get_client` double-checked locking — N concurrent first-time calls
   produce exactly one `httpx.AsyncClient`.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from prep.mcp_server import MCPServer


@pytest.fixture
def server() -> MCPServer:
    return MCPServer(daemon_url="http://127.0.0.1:8400", project_id="proj_test")


def _ambient_response(tag: str = "default") -> Dict[str, Any]:
    return {
        "context": f"[{tag}] hub block",
        "chunks": [{"source_path": "src/main.py"}],
        "total_chars": 12,
        "estimated_tokens": 3,
        "ambient": True,
        "hub_files": 0,
        "modules_in_scope": 0,
        "neighbor_files": 0,
    }


class TestToolContextCoalescing:
    @pytest.mark.asyncio
    async def test_identical_concurrent_calls_share_one_impl(self, server: MCPServer) -> None:
        """4 concurrent identical prep calls → 1 _tool_context_impl invocation."""
        impl_calls = 0
        ready = asyncio.Event()
        release = asyncio.Event()

        original_impl = server._tool_context_impl

        async def slow_impl(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            nonlocal impl_calls
            impl_calls += 1
            ready.set()
            # Hold the impl open so followers register before the owner finishes.
            await release.wait()
            return await original_impl(*args, **kwargs)

        with patch.object(server, "_tool_context_impl", side_effect=slow_impl), \
             patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post, \
             patch.object(server, "_api_get", new_callable=AsyncMock) as mock_get, \
             patch.object(server, "_project_has_rules_file", return_value=False), \
             patch.object(server, "_check_atlas_signal", new_callable=AsyncMock):
            mock_post.return_value = _ambient_response("coalesced")
            mock_get.return_value = {}

            tasks = [asyncio.create_task(server.tool_context()) for _ in range(4)]
            await ready.wait()
            # All four tasks should now be either running or awaiting the future.
            release.set()
            results = await asyncio.gather(*tasks)

        assert impl_calls == 1, f"expected 1 impl call, got {impl_calls}"
        assert len(results) == 4
        for r in results:
            assert r["ambient"] is True
            assert "[coalesced]" in r["context"]

    @pytest.mark.asyncio
    async def test_different_keys_do_not_coalesce(self, server: MCPServer) -> None:
        """Calls with different args do not share an in-flight slot."""
        impl_calls = 0

        original_impl = server._tool_context_impl

        async def counting_impl(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            nonlocal impl_calls
            impl_calls += 1
            return await original_impl(*args, **kwargs)

        with patch.object(server, "_tool_context_impl", side_effect=counting_impl), \
             patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post, \
             patch.object(server, "_api_get", new_callable=AsyncMock) as mock_get, \
             patch.object(server, "_project_has_rules_file", return_value=False), \
             patch.object(server, "_check_atlas_signal", new_callable=AsyncMock):
            mock_post.return_value = _ambient_response()
            mock_get.return_value = {}

            await asyncio.gather(
                server.tool_context(role="security"),
                server.tool_context(role="design-engineer"),
                server.tool_context(scope="marketing"),
                server.tool_context(working_dir="src/prep/services"),
            )

        assert impl_calls == 4, f"expected 4 distinct calls, got {impl_calls}"

    @pytest.mark.asyncio
    async def test_followers_get_independent_copies(self, server: MCPServer) -> None:
        """Mutating one coalesced result must not bleed into other callers."""
        ready = asyncio.Event()
        release = asyncio.Event()

        original_impl = server._tool_context_impl

        async def slow_impl(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            ready.set()
            await release.wait()
            return await original_impl(*args, **kwargs)

        with patch.object(server, "_tool_context_impl", side_effect=slow_impl), \
             patch.object(server, "_api_post", new_callable=AsyncMock) as mock_post, \
             patch.object(server, "_api_get", new_callable=AsyncMock) as mock_get, \
             patch.object(server, "_project_has_rules_file", return_value=False), \
             patch.object(server, "_check_atlas_signal", new_callable=AsyncMock):
            mock_post.return_value = _ambient_response("shared")
            mock_get.return_value = {}

            tasks = [asyncio.create_task(server.tool_context()) for _ in range(3)]
            await ready.wait()
            release.set()
            results: List[Dict[str, Any]] = await asyncio.gather(*tasks)

        # Mutate the first result deeply; others must remain pristine.
        results[0]["context"] = "MUTATED"
        results[0].setdefault("r4_meta", {})["role_source"] = "inferred"
        assert results[1]["context"] != "MUTATED"
        assert "r4_meta" not in results[2]

    @pytest.mark.asyncio
    async def test_owner_caller_mutation_does_not_leak_to_follower(
        self, server: MCPServer
    ) -> None:
        """Regression for the realistic mid-flight mutation bug.

        `handle_tools_call` synchronously attaches r4_meta to the result
        dict between `tool_context` returning and any await. If the owner
        returns the same dict that the future stores, that mutation lands
        before the follower wakes from `await fut` and the follower's
        deepcopy includes it. The fix is to snapshot the result at
        `set_result` time so the future never references the live owner dict.
        """
        ready = asyncio.Event()
        release = asyncio.Event()

        async def slow_impl(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            ready.set()
            await release.wait()
            return _ambient_response("clean")

        async def owner_then_mutate() -> Dict[str, Any]:
            r = await server.tool_context()
            # Simulate handle_tools_call's synchronous post-return mutation.
            r["context"] = "OWNER MUTATED"
            r.setdefault("r4_meta", {})["role_source"] = "owner_only"
            return r

        with patch.object(server, "_tool_context_impl", side_effect=slow_impl):
            owner_task = asyncio.create_task(owner_then_mutate())
            # Let the owner enter tool_context and become slot owner.
            await asyncio.sleep(0)
            # Follower starts AFTER owner has registered the in-flight future.
            follower_task = asyncio.create_task(server.tool_context())
            # Let the follower enter tool_context and start awaiting fut.
            await asyncio.sleep(0)
            # Now release the impl; owner finishes, mutates, then follower wakes.
            release.set()
            owner_result, follower_result = await asyncio.gather(owner_task, follower_task)

        assert owner_result["context"] == "OWNER MUTATED"
        assert follower_result["context"] == "[clean] hub block", (
            "follower deepcopied a dict that the owner's caller had mutated"
        )
        assert "r4_meta" not in follower_result, (
            "follower inherited r4_meta that belongs only to the owner"
        )

    @pytest.mark.asyncio
    async def test_owner_failure_propagates_to_followers(self, server: MCPServer) -> None:
        """If the owner raises, all in-flight followers see the exception
        and the in-flight slot is cleared so the next call retries cleanly."""
        ready = asyncio.Event()
        release = asyncio.Event()
        attempt = 0

        async def failing_then_ok(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                ready.set()
                await release.wait()
                raise RuntimeError("daemon blew up")
            return _ambient_response("recovered")

        with patch.object(server, "_tool_context_impl", side_effect=failing_then_ok):
            tasks = [asyncio.create_task(server.tool_context()) for _ in range(3)]
            await ready.wait()
            release.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)

            assert all(isinstance(r, RuntimeError) for r in results), results
            # In-flight slot must be cleared so a retry is not stuck.
            assert server._inflight_context == {}

            # Subsequent call succeeds without coalescing onto the dead slot.
            recovered = await server.tool_context()
            assert recovered["context"] == "[recovered] hub block"


class TestGetClientLocking:
    @pytest.mark.asyncio
    async def test_close_does_not_race_with_get_client(self, server: MCPServer) -> None:
        """close() must not return a half-closed or stale client to a concurrent
        _get_client call. Both must serialize through _client_lock so the post-
        close get observes self._client is None and constructs a fresh one."""
        # Seed an existing client.
        first = await server._get_client()
        assert first is not None

        # Race close() and a concurrent get. Whatever the interleave, the
        # caller must end up with a client that is either `first` (still alive
        # because get won the race) or a freshly constructed one (close won).
        close_task = asyncio.create_task(server.close())
        get_task = asyncio.create_task(server._get_client())
        _, second = await asyncio.gather(close_task, get_task)

        assert second is not None
        # If close ran first, server._client should be the new `second`.
        # If get ran first, server._client should still be `first`.
        assert server._client is second or server._client is first

        await server.close()

    @pytest.mark.asyncio
    async def test_concurrent_first_use_creates_one_client(self, server: MCPServer) -> None:
        """Burst of concurrent _get_client calls creates exactly one AsyncClient."""
        created: List[Any] = []
        real_ctor = __import__("httpx").AsyncClient

        def tracking_ctor(*args: Any, **kwargs: Any) -> Any:
            client = real_ctor(*args, **kwargs)
            created.append(client)
            return client

        try:
            with patch("prep.mcp.server.httpx.AsyncClient", side_effect=tracking_ctor):
                clients = await asyncio.gather(*(server._get_client() for _ in range(10)))
        finally:
            await server.close()

        assert len(created) == 1, f"expected 1 client, got {len(created)}"
        assert all(c is clients[0] for c in clients)
