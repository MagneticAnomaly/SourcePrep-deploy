"""
Stress test for SwarmOrchestrator timeout and stall-detection paths.

Exercises ALL timeout behaviors with real Ollama cloud calls and
synthetic slow/stuck workers.  Max 7 concurrent workers per env constraint.

Run:
    .venv/bin/pytest tests/test_swarm_stress.py -v -s --timeout=300

Requires: Ollama running locally with kimi-k2.5:cloud available.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest
import requests

from codrag.core.swarm_orchestrator import (
    CoordinatorPlan,
    SwarmOrchestrator,
    SwarmResult,
    WorkerAssignment,
    WorkItem,
    WorkerResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434"
CLOUD_MODEL = "kimi-k2.5:cloud"


def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def cloud_model_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        return CLOUD_MODEL in models
    except Exception:
        return False


requires_ollama = pytest.mark.skipif(
    not ollama_available(), reason="Ollama not running on localhost:11434"
)
requires_cloud = pytest.mark.skipif(
    not cloud_model_available(), reason=f"Cloud model {CLOUD_MODEL} not available"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_items(n: int) -> List[WorkItem]:
    return [
        WorkItem(
            id=f"stress:{i}",
            summary=f"Stress test item {i}",
            full_context=json.dumps({"item": i}),
        )
        for i in range(n)
    ]


def _quick_worker(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
    """Worker that returns instantly."""
    return json.dumps({
        "item_id": item.id,
        "analysis": f"Quick result for {item.id}",
        "confidence": 0.9,
    })


def _slow_worker(delay_s: float):
    """Factory: returns a worker that sleeps before responding."""
    def worker(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
        time.sleep(delay_s)
        return json.dumps({
            "item_id": item.id,
            "analysis": f"Slow result for {item.id} (waited {delay_s}s)",
            "confidence": 0.7,
        })
    return worker


def _stuck_worker(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
    """Worker that blocks forever (simulates a hung cloud request)."""
    threading.Event().wait()  # blocks indefinitely
    return None  # unreachable


def _mixed_worker(stuck_ids: set):
    """Factory: some items complete fast, some block forever."""
    def worker(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
        if item.id in stuck_ids:
            threading.Event().wait()
            return None
        return json.dumps({
            "item_id": item.id,
            "analysis": f"Result for {item.id}",
            "confidence": 0.8,
        })
    return worker


def _make_mock_llm(**overrides):
    """Create a mock LLMClient for non-cloud tests."""
    llm = MagicMock()
    llm.model = overrides.get("model", "test-model")
    llm.provider = overrides.get("provider", "ollama")
    llm.timeout = overrides.get("timeout", 60.0)
    llm._thread_local = threading.local()

    def fake_generate(**kwargs):
        return '{"assignments": []}', 10
    llm.generate.side_effect = fake_generate
    return llm


# ---------------------------------------------------------------------------
# Test Suite A: Pure unit tests (no Ollama needed)
# ---------------------------------------------------------------------------

class TestStallDetection:
    """Verify the wait(FIRST_COMPLETED) stall detection works."""

    def test_all_workers_complete_fast(self) -> None:
        """Happy path: 7 items, all complete instantly."""
        items = _make_items(7)
        llm = _make_mock_llm()
        orch = SwarmOrchestrator(
            llm=llm, concurrency=7,
            worker_timeout_s=5.0, max_wall_time_s=30.0,
        )
        result = orch.execute(
            items=items,
            coordinator_prompt="Coord:\n{group_summaries}",
            worker_fn=_quick_worker,
            synthesis_prompt="Synth:\n{worker_outputs}",
        )
        assert result is not None
        assert result.stats.workers_succeeded == 7
        assert result.stats.workers_failed == 0

    def test_stall_detection_fires(self) -> None:
        """Stall: all workers block forever, stall timeout fires."""
        items = _make_items(3)
        llm = _make_mock_llm()
        orch = SwarmOrchestrator(
            llm=llm, concurrency=3,
            worker_timeout_s=2.0,  # short stall timeout
            max_wall_time_s=30.0,
        )
        t0 = time.monotonic()
        result = orch.execute(
            items=items,
            coordinator_prompt="Coord:\n{group_summaries}",
            worker_fn=_stuck_worker,
            synthesis_prompt="Synth:\n{worker_outputs}",
        )
        elapsed = time.monotonic() - t0
        assert result is not None
        # No workers should have succeeded
        assert result.stats.workers_succeeded == 0
        # Should have aborted within stall_timeout + buffer
        assert elapsed < 8.0, f"Took {elapsed:.1f}s — stall detection didn't fire"

    def test_wall_time_cap_fires(self) -> None:
        """Wall-time: slow workers exceed overall cap."""
        items = _make_items(5)
        llm = _make_mock_llm()
        orch = SwarmOrchestrator(
            llm=llm, concurrency=2,
            worker_timeout_s=30.0,  # stall timeout is generous
            max_wall_time_s=3.0,    # but overall cap is tight
        )
        # Workers take 2s each; with concurrency=2, that's ~6s for 5 items.
        # Wall cap at 3s should abort after ~2 batches (4 workers).
        t0 = time.monotonic()
        result = orch.execute(
            items=items,
            coordinator_prompt="Coord:\n{group_summaries}",
            worker_fn=_slow_worker(2.0),
            synthesis_prompt="Synth:\n{worker_outputs}",
        )
        elapsed = time.monotonic() - t0
        assert result is not None
        # Should have some results but not all 5
        assert 0 < result.stats.workers_succeeded < 5, (
            f"Expected partial results, got {result.stats.workers_succeeded}/5"
        )
        assert elapsed < 8.0, f"Wall-time cap didn't fire: {elapsed:.1f}s"

    def test_partial_results_with_mixed_workers(self) -> None:
        """Some workers complete, some are stuck — get partial results."""
        items = _make_items(5)
        stuck = {"stress:2", "stress:4"}
        llm = _make_mock_llm()
        orch = SwarmOrchestrator(
            llm=llm, concurrency=5,
            worker_timeout_s=3.0,
            max_wall_time_s=30.0,
        )
        t0 = time.monotonic()
        result = orch.execute(
            items=items,
            coordinator_prompt="Coord:\n{group_summaries}",
            worker_fn=_mixed_worker(stuck),
            synthesis_prompt="Synth:\n{worker_outputs}",
        )
        elapsed = time.monotonic() - t0
        assert result is not None
        # 3 fast workers should complete, 2 stuck ones cause stall detection
        assert result.stats.workers_succeeded == 3
        # Should abort within stall_timeout after the last fast worker
        assert elapsed < 10.0, f"Took {elapsed:.1f}s"

    def test_progress_callback_called(self) -> None:
        """Progress callback fires for each completed worker."""
        items = _make_items(4)
        llm = _make_mock_llm()
        calls = []

        def progress_fn(done: int, total: int) -> None:
            calls.append((done, total))

        orch = SwarmOrchestrator(
            llm=llm, concurrency=4,
            worker_timeout_s=5.0, max_wall_time_s=30.0,
        )
        result = orch.execute(
            items=items,
            coordinator_prompt="Coord:\n{group_summaries}",
            worker_fn=_quick_worker,
            synthesis_prompt="Synth:\n{worker_outputs}",
            progress_fn=progress_fn,
        )
        assert len(calls) == 4
        assert calls[-1] == (4, 4)


class TestZombieSessionCleanup:
    """Verify that coordinator timeout captures and closes the zombie Session."""

    def test_zombie_session_captured_on_timeout(self) -> None:
        """When coordinator times out, the zombie's Session should be closed."""
        from codrag.core.llm_client import LLMClient
        import requests as _requests

        # Use a REAL LLMClient (not a mock) so _session / _thread_local work.
        llm = LLMClient(
            endpoint_url="http://localhost:99999",  # unreachable
            model="test-zombie",
            provider="ollama",
            timeout=60.0,
        )

        closed_sessions = []

        # Monkey-patch _session to track closure and block in generate.
        real_session = _requests.Session()
        original_close = real_session.close

        def tracking_close():
            closed_sessions.append(True)
            original_close()

        real_session.close = tracking_close

        # Override the _session property to always return our tracked session
        # on any thread.
        llm._thread_local = threading.local()
        original_session_getter = type(llm)._session.fget

        def patched_session(self):
            s = getattr(self._thread_local, 'session', None)
            if s is None:
                self._thread_local.session = real_session
            return self._thread_local.session

        type(llm)._session = property(patched_session)

        # Override generate to block
        original_generate = llm.generate

        def slow_generate(**kwargs):
            time.sleep(10)
            return '{"result": "too late"}', 0

        llm.generate = slow_generate

        try:
            orch = SwarmOrchestrator(
                llm=llm, concurrency=1,
                coordinator_timeout_s=1.0,
            )
            text, tokens = orch._llm_call_with_timeout(
                prompt="test", system="test",
                temperature=0.5, timeout_s=1.0, phase="test-coord",
            )
            assert text is None
            assert tokens == 0
            # The zombie thread should have captured the session,
            # and the timeout handler should have closed it.
            time.sleep(0.5)
            assert len(closed_sessions) > 0, "Zombie session was not closed"
        finally:
            # Restore
            type(llm)._session = property(original_session_getter)


class TestDaemonConditions:
    """Simulate the exact daemon threading: asyncio loop + build thread + swarm."""

    def test_asyncio_nesting(self) -> None:
        """Swarm works when called from Thread inside asyncio event loop."""
        items = _make_items(4)
        llm = _make_mock_llm()
        result_holder = [None]

        def build_thread():
            orch = SwarmOrchestrator(
                llm=llm, concurrency=4,
                worker_timeout_s=5.0, max_wall_time_s=30.0,
            )
            result_holder[0] = orch.execute(
                items=items,
                coordinator_prompt="Coord:\n{group_summaries}",
                worker_fn=_quick_worker,
                synthesis_prompt="Synth:\n{worker_outputs}",
            )

        async def run_async():
            t = threading.Thread(target=build_thread, daemon=True)
            t.start()
            t.join(timeout=15)
            assert not t.is_alive(), "Build thread hung"

        asyncio.run(run_async())
        assert result_holder[0] is not None
        assert result_holder[0].stats.workers_succeeded == 4

    def test_asyncio_nesting_with_stall(self) -> None:
        """Stall detection works inside asyncio + Thread nesting."""
        items = _make_items(3)
        llm = _make_mock_llm()
        result_holder = [None]

        def build_thread():
            orch = SwarmOrchestrator(
                llm=llm, concurrency=3,
                worker_timeout_s=2.0,
                max_wall_time_s=30.0,
            )
            result_holder[0] = orch.execute(
                items=items,
                coordinator_prompt="Coord:\n{group_summaries}",
                worker_fn=_stuck_worker,
                synthesis_prompt="Synth:\n{worker_outputs}",
            )

        async def run_async():
            t = threading.Thread(target=build_thread, daemon=True)
            t.start()
            t.join(timeout=15)
            assert not t.is_alive(), "Build thread hung despite stall timeout"

        t0 = time.monotonic()
        asyncio.run(run_async())
        elapsed = time.monotonic() - t0
        assert elapsed < 10.0
        assert result_holder[0] is not None
        assert result_holder[0].stats.workers_succeeded == 0


# ---------------------------------------------------------------------------
# Test Suite B: Live Ollama cloud tests (real HTTP, real latency)
# ---------------------------------------------------------------------------

@requires_ollama
@requires_cloud
class TestLiveCloud:
    """Live tests against Ollama cloud — real HTTP requests, real timeouts."""

    def _make_live_llm(self, timeout: float = 120.0):
        from codrag.core.llm_client import LLMClient
        return LLMClient(
            endpoint_url=OLLAMA_URL,
            model=CLOUD_MODEL,
            provider="ollama",
            timeout=timeout,
        )

    def _live_worker(self, item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
        """Worker that makes a real cloud LLM call."""
        llm = self._make_live_llm(timeout=60.0)
        prompt = (
            f"Analyze this code module briefly. Item: {item.id}\n"
            f"Context: {item.full_context[:200]}\n"
            f"Angle: {assignment.analysis_angle}\n\n"
            "Respond with JSON: "
            '{"item_id": "...", "summary": "...", "confidence": 0.8}'
        )
        text, tokens = llm.generate(
            prompt=prompt,
            json_mode=True,
            temperature=0.4,
            think=False,
            num_predict=200,
        )
        return text

    def test_live_7_workers_complete(self) -> None:
        """7 workers all complete with real cloud calls (think=False, small)."""
        items = _make_items(7)
        llm = self._make_live_llm()
        orch = SwarmOrchestrator(
            llm=llm, concurrency=7,
            coordinator_timeout_s=10.0,
            synthesis_timeout_s=30.0,
            worker_timeout_s=60.0,
            max_wall_time_s=120.0,
        )
        t0 = time.monotonic()
        result = orch.execute(
            items=items,
            coordinator_prompt=(
                "Plan analysis for these items:\n{group_summaries}\n\n"
                'Respond JSON: {"assignments": [{"item_id": "...", '
                '"analysis_angle": "...", "priority_concerns": []}]}'
            ),
            worker_fn=self._live_worker,
            synthesis_prompt=(
                "Synthesize:\n{worker_outputs}\n\n"
                'Respond JSON: {"summary": "...", "patterns": []}'
            ),
        )
        elapsed = time.monotonic() - t0
        assert result is not None
        logger.info(
            "Live 7-worker test: %d/%d succeeded in %.1fs",
            result.stats.workers_succeeded, 7, elapsed,
        )
        # At least some should succeed (cloud may be slow)
        assert result.stats.workers_succeeded >= 3, (
            f"Only {result.stats.workers_succeeded}/7 succeeded"
        )

    def test_live_stall_detection_with_think(self) -> None:
        """Think=True workers with tight stall timeout — should abort cleanly."""
        items = _make_items(3)
        llm = self._make_live_llm(timeout=120.0)

        def think_worker(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
            inner_llm = self._make_live_llm(timeout=120.0)
            text, _ = inner_llm.generate(
                prompt=(
                    f"Deep analysis of {item.id}: {item.full_context[:100]}\n"
                    'Respond JSON: {"item_id": "...", "deep_analysis": "..."}'
                ),
                json_mode=True,
                temperature=0.6,
                think=True,
                num_predict=4096,  # large budget = slow
            )
            return text

        orch = SwarmOrchestrator(
            llm=llm, concurrency=3,
            coordinator_timeout_s=5.0,
            worker_timeout_s=15.0,  # tight stall timeout
            max_wall_time_s=90.0,
        )
        t0 = time.monotonic()
        result = orch.execute(
            items=items,
            coordinator_prompt="Plan:\n{group_summaries}\nJSON: "
                '{"assignments": []}',
            worker_fn=think_worker,
            synthesis_prompt="Synth:\n{worker_outputs}\nJSON: {}",
        )
        elapsed = time.monotonic() - t0
        assert result is not None
        logger.info(
            "Live think test: %d/%d succeeded in %.1fs (stall_timeout=15s)",
            result.stats.workers_succeeded, 3, elapsed,
        )
        # With 15s stall timeout, may get 0-3 depending on cloud speed.
        # The important thing is that it RETURNED, not hung.
        assert elapsed < 120.0, f"Took {elapsed:.1f}s — something is wrong"

    def test_live_daemon_thread_nesting(self) -> None:
        """Full daemon simulation: asyncio + Thread + swarm with live cloud."""
        items = _make_items(5)
        result_holder = [None]
        error_holder = [None]

        def build_thread():
            try:
                llm = self._make_live_llm(timeout=60.0)
                orch = SwarmOrchestrator(
                    llm=llm, concurrency=5,
                    coordinator_timeout_s=10.0,
                    worker_timeout_s=45.0,
                    max_wall_time_s=90.0,
                )
                result_holder[0] = orch.execute(
                    items=items,
                    coordinator_prompt=(
                        "Plan:\n{group_summaries}\n"
                        'JSON: {"assignments": []}'
                    ),
                    worker_fn=self._live_worker,
                    synthesis_prompt=(
                        "Synth:\n{worker_outputs}\n"
                        'JSON: {"summary": "done"}'
                    ),
                )
            except Exception as e:
                error_holder[0] = e

        async def run_async():
            t = threading.Thread(target=build_thread, daemon=True)
            t.start()
            # Wait with overall timeout
            for _ in range(24):  # 24 * 5s = 120s max
                await asyncio.sleep(5)
                if not t.is_alive():
                    break
            if t.is_alive():
                pytest.fail("Build thread still alive after 120s")

        t0 = time.monotonic()
        asyncio.run(run_async())
        elapsed = time.monotonic() - t0

        if error_holder[0]:
            pytest.fail(f"Build thread raised: {error_holder[0]}")

        result = result_holder[0]
        assert result is not None, "No result returned"
        logger.info(
            "Live daemon test: %d/%d succeeded in %.1fs, wall=%.1fs",
            result.stats.workers_succeeded, 5, elapsed,
            result.stats.wall_clock_seconds,
        )

    def test_thread_cleanup_after_abort(self) -> None:
        """After stall abort, verify zombie threads don't accumulate."""
        initial_threads = threading.active_count()
        items = _make_items(3)
        llm = self._make_live_llm(timeout=30.0)

        orch = SwarmOrchestrator(
            llm=llm, concurrency=3,
            coordinator_timeout_s=5.0,
            worker_timeout_s=3.0,  # very tight
            max_wall_time_s=60.0,
        )

        def think_heavy_worker(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
            inner_llm = self._make_live_llm(timeout=30.0)
            text, _ = inner_llm.generate(
                prompt=f"Deep analysis of {item.id}\nJSON: " + '{"result": "ok"}',
                json_mode=True, think=True, num_predict=4096,
            )
            return text

        result = orch.execute(
            items=items,
            coordinator_prompt="Plan:\n{group_summaries}\nJSON: " + '{"assignments": []}',
            worker_fn=think_heavy_worker,
            synthesis_prompt="Synth:\n{worker_outputs}\nJSON: {}",
        )

        # Wait for zombie threads to clean up (HTTP timeout)
        time.sleep(2)
        final_threads = threading.active_count()
        leaked = final_threads - initial_threads
        logger.info(
            "Thread cleanup: initial=%d, final=%d, leaked=%d",
            initial_threads, final_threads, leaked,
        )
        # Allow some slack — zombie threads may persist briefly
        assert leaked <= 5, (
            f"Thread leak: {leaked} threads remain "
            f"(initial={initial_threads}, final={final_threads})"
        )
