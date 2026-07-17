"""Phase 96F follow-up: SwarmOrchestrator coordinator/synthesis timeout.

Verifies that a slow LLM call doesn't block the entire swarm. Coordinator
timeout falls back to default assignments; synthesis timeout returns None
so callers can fall back to merging raw worker outputs.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from prep.core.swarm_orchestrator import (
    SwarmOrchestrator,
    WorkItem,
    WorkerAssignment,
)


def _make_items(n: int) -> list[WorkItem]:
    return [
        WorkItem(id=f"item-{i}", summary=f"Summary {i}", full_context=f"ctx-{i}")
        for i in range(n)
    ]


class TestCoordinatorTimeout:
    """Coordinator hangs → fall back to default assignments, fan-out continues."""

    def test_default_timeouts_set(self):
        llm = MagicMock()
        orch = SwarmOrchestrator(llm=llm)
        assert orch.coordinator_timeout_s == 120.0
        assert orch.synthesis_timeout_s == 180.0

    def test_custom_timeouts_set(self):
        llm = MagicMock()
        orch = SwarmOrchestrator(
            llm=llm,
            coordinator_timeout_s=30.0,
            synthesis_timeout_s=60.0,
        )
        assert orch.coordinator_timeout_s == 30.0
        assert orch.synthesis_timeout_s == 60.0

    def test_coordinator_timeout_returns_none_plan(self):
        """When the LLM call exceeds timeout, _coordinate returns None."""
        llm = MagicMock()

        def slow_generate(**kwargs):
            time.sleep(2.0)  # exceeds the 0.1s timeout
            return ('{"assignments": []}', 0)

        llm.generate.side_effect = slow_generate

        orch = SwarmOrchestrator(
            llm=llm,
            coordinator_timeout_s=0.1,
            synthesis_timeout_s=0.1,
        )
        plan, tokens = orch._coordinate(_make_items(3), "prompt {group_summaries}")
        assert plan is None
        assert tokens == 0

    def test_execute_continues_with_default_assignments_on_coord_timeout(self):
        """When coordinator times out, execute() still runs the fan-out."""
        llm = MagicMock()

        # Coordinator: slow → timeout
        # Worker calls: pass through to worker_fn
        # Synthesis: fast empty (no successful workers parsed → None anyway)
        call_count = {"coord": 0, "synth": 0}

        def slow_generate(**kwargs):
            # Differentiate coordinator (uses COORDINATOR_SYSTEM) vs synth
            sys_msg = kwargs.get("system", "")
            if "planning" in sys_msg.lower():
                call_count["coord"] += 1
                time.sleep(2.0)  # exceed timeout
            else:
                call_count["synth"] += 1
                return ('{"summary": "ok"}', 5)
            return ('{"assignments": []}', 0)

        llm.generate.side_effect = slow_generate

        orch = SwarmOrchestrator(
            llm=llm,
            coordinator_timeout_s=0.1,
            synthesis_timeout_s=10.0,
        )

        worker_calls: list[str] = []

        def worker_fn(item, assignment):
            worker_calls.append(item.id)
            # Return parseable JSON so the synthesis path is exercised
            return f'{{"item_id": "{item.id}", "ok": true}}'

        result = orch.execute(
            items=_make_items(3),
            coordinator_prompt="Test {group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synth {worker_outputs}",
        )

        # Result is NOT None (the old code returned None on coordinator failure)
        assert result is not None
        # All 3 workers ran despite coordinator timeout
        assert sorted(worker_calls) == ["item-0", "item-1", "item-2"]
        # All 3 succeeded
        assert sum(1 for r in result.worker_results if r.success) == 3
        # Coordinator was attempted
        assert call_count["coord"] >= 1

    def test_synthesis_timeout_returns_none_synthesis(self):
        """Synthesis hang → swarm result has synthesis=None, callers fall back."""
        llm = MagicMock()

        def slow_synth(**kwargs):
            sys_msg = kwargs.get("system", "")
            if "planning" in sys_msg.lower():
                # Coordinator: fast success
                return (
                    '{"assignments": [{"item_id": "item-0", '
                    '"analysis_angle": "test", "priority_concerns": []}]}',
                    10,
                )
            # Synthesis: slow → timeout
            time.sleep(2.0)
            return ('{"summary": "should not see this"}', 0)

        llm.generate.side_effect = slow_synth

        orch = SwarmOrchestrator(
            llm=llm,
            coordinator_timeout_s=10.0,
            synthesis_timeout_s=0.1,
        )

        def worker_fn(item, assignment):
            return f'{{"item_id": "{item.id}", "ok": true}}'

        result = orch.execute(
            items=_make_items(1),
            coordinator_prompt="Test {group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synth {worker_outputs}",
        )

        # Result returned, fan-out succeeded, synthesis is None
        assert result is not None
        assert sum(1 for r in result.worker_results if r.success) == 1
        assert result.synthesis is None

    def test_empty_items_returns_none(self):
        """Empty items list short-circuits to None."""
        llm = MagicMock()
        orch = SwarmOrchestrator(llm=llm)
        result = orch.execute(
            items=[],
            coordinator_prompt="x",
            worker_fn=lambda i, a: None,
            synthesis_prompt="x",
        )
        assert result is None

    def test_coordinator_exception_falls_back_to_default(self):
        """Coordinator raising an exception → default assignments, fan-out runs."""
        llm = MagicMock()

        def raising_generate(**kwargs):
            sys_msg = kwargs.get("system", "")
            if "planning" in sys_msg.lower():
                raise RuntimeError("LLM exploded")
            return ('{"summary": "ok"}', 5)

        llm.generate.side_effect = raising_generate

        orch = SwarmOrchestrator(
            llm=llm,
            coordinator_timeout_s=10.0,
            synthesis_timeout_s=10.0,
        )

        worker_calls: list[str] = []

        def worker_fn(item, assignment):
            worker_calls.append(item.id)
            return f'{{"item_id": "{item.id}"}}'

        result = orch.execute(
            items=_make_items(2),
            coordinator_prompt="Test {group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synth {worker_outputs}",
        )

        assert result is not None
        assert len(worker_calls) == 2


class TestSwarmThinkFalse:
    """Phase 96F follow-up (F-29): coordinator and synthesis LLM calls
    must pass think=False so reasoning models don't consume their
    response budget on chain-of-thought."""

    def test_coordinator_passes_think_false(self):
        llm = MagicMock()
        llm.generate.return_value = (
            '{"assignments": [{"item_id": "item-0", '
            '"analysis_angle": "test", "priority_concerns": []}]}',
            10,
        )

        orch = SwarmOrchestrator(
            llm=llm,
            coordinator_timeout_s=10.0,
            synthesis_timeout_s=10.0,
        )

        plan, _tokens = orch._coordinate(_make_items(1), "prompt {group_summaries}")
        assert plan is not None

        # Verify llm.generate was called with think=False
        call_kwargs = llm.generate.call_args.kwargs
        assert call_kwargs.get("think") is False, (
            f"Coordinator must pass think=False, got {call_kwargs.get('think')}"
        )

    def test_synthesis_passes_think_false(self):
        llm = MagicMock()
        llm.generate.return_value = ('{"summary": "ok"}', 5)

        orch = SwarmOrchestrator(
            llm=llm,
            coordinator_timeout_s=10.0,
            synthesis_timeout_s=10.0,
        )

        # Build a fake worker_results list with one successful entry
        from prep.core.swarm_orchestrator import WorkerResult
        results = [
            WorkerResult(
                item_id="item-0",
                raw_output='{"x": 1}',
                parsed={"x": 1},
                success=True,
            ),
        ]

        result, _tokens, _, _, _ = orch._synthesize(results, "prompt {worker_outputs}")
        assert result is not None

        # Verify llm.generate was called with think=False
        call_kwargs = llm.generate.call_args.kwargs
        assert call_kwargs.get("think") is False, (
            f"Synthesis must pass think=False, got {call_kwargs.get('think')}"
        )
