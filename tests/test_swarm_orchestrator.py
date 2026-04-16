"""Tests for SwarmOrchestrator — three-phase swarm executor."""

import json
import logging
from unittest.mock import MagicMock

from codrag.core.swarm_orchestrator import (
    CoordinatorPlan,
    SwarmOrchestrator,
    SwarmResult,
    WorkerAssignment,
    WorkerResult,
    WorkItem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_items(n: int) -> list[WorkItem]:
    return [
        WorkItem(
            id=f"group:{i}",
            summary=f"Group {i}: files about module_{i}",
            full_context=f"Full details for group {i}...",
        )
        for i in range(n)
    ]


def _mock_coordinator_response(items: list[WorkItem]) -> str:
    assignments = [
        {
            "item_id": item.id,
            "analysis_angle": f"Focus on coupling in {item.id}",
            "priority_concerns": ["data flow", "error handling"],
        }
        for item in items
    ]
    return json.dumps({"assignments": assignments})


def _mock_worker_response(item_id: str) -> str:
    return json.dumps(
        {
            "pattern": "Request Pipeline",
            "data_flow": "A calls B calls C",
            "coupling_risks": ["tight coupling via shared state"],
            "blast_radius": ["file_a.py", "file_b.py"],
            "architectural_insight": "Well-structured but tightly coupled.",
            "confidence": 0.8,
        }
    )


def _mock_synthesis_response() -> str:
    return json.dumps(
        {
            "cross_group_patterns": ["Multiple groups use Repository Pattern"],
            "shared_coupling_risks": ["Shared config dependency"],
            "data_flow_chains": ["group:0 → group:1 via events"],
            "systemic_risks": ["Config coupling in 3 groups"],
            "architectural_coherence": "Mostly consistent, some drift in data layer.",
            "key_insight": "Event bus is an implicit dependency across all groups.",
        }
    )


# ---------------------------------------------------------------------------
# TestCoordinatorPhase
# ---------------------------------------------------------------------------

class TestCoordinatorPhase:
    def test_coordinator_produces_plan(self) -> None:
        items = _make_items(3)
        llm = MagicMock()
        llm.generate.return_value = (_mock_coordinator_response(items), 100)

        orch = SwarmOrchestrator(llm=llm, concurrency=4)
        plan, tokens = orch._coordinate(items, "Analyze these groups:\n{group_summaries}")

        assert plan is not None
        assert len(plan.assignments) == 3
        for i, a in enumerate(plan.assignments):
            assert a.item_id == f"group:{i}"
            assert "coupling" in a.analysis_angle
            assert "data flow" in a.priority_concerns

    def test_coordinator_failure_returns_none(self) -> None:
        items = _make_items(2)
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("LLM unavailable")

        orch = SwarmOrchestrator(llm=llm)
        plan, _ = orch._coordinate(items, "prompt {group_summaries}")
        assert plan is None

    def test_coordinator_bad_json_returns_none(self) -> None:
        items = _make_items(2)
        llm = MagicMock()
        llm.generate.return_value = ("this is not json at all!!!", 50)

        orch = SwarmOrchestrator(llm=llm)
        plan, _ = orch._coordinate(items, "prompt {group_summaries}")
        assert plan is None


# ---------------------------------------------------------------------------
# TestFanOutPhase
# ---------------------------------------------------------------------------

class TestFanOutPhase:
    def _make_plan(self, items: list[WorkItem]) -> CoordinatorPlan:
        return CoordinatorPlan(
            assignments=[
                WorkerAssignment(
                    item_id=item.id,
                    analysis_angle=f"Analyze {item.id}",
                    priority_concerns=["coupling"],
                )
                for item in items
            ]
        )

    def test_fan_out_runs_all_workers(self) -> None:
        items = _make_items(4)
        plan = self._make_plan(items)
        llm = MagicMock()

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=llm, concurrency=4)
        results = orch._fan_out(items, plan, worker_fn)

        assert len(results) == 4
        assert all(r.success for r in results)
        assert all(r.parsed is not None for r in results)
        assert all(r.parsed["pattern"] == "Request Pipeline" for r in results)

    def test_fan_out_handles_worker_failure(self) -> None:
        items = _make_items(4)
        plan = self._make_plan(items)
        llm = MagicMock()

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
            if item.id == "group:2":
                raise RuntimeError("Worker exploded")
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=llm, concurrency=4)
        results = orch._fan_out(items, plan, worker_fn)

        assert len(results) == 4
        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        assert len(succeeded) == 3
        assert len(failed) == 1
        assert failed[0].item_id == "group:2"

    def test_fan_out_missing_assignment_uses_generic(self) -> None:
        items = _make_items(2)
        # Plan only has assignment for the first item
        plan = CoordinatorPlan(
            assignments=[
                WorkerAssignment(
                    item_id="group:0",
                    analysis_angle="Analyze group:0",
                    priority_concerns=["coupling"],
                )
            ]
        )
        llm = MagicMock()

        received_assignments: list[WorkerAssignment] = []

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
            received_assignments.append(assignment)
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=llm, concurrency=4)
        results = orch._fan_out(items, plan, worker_fn)

        assert len(results) == 2
        # Find the assignment for group:1 (the missing one)
        group1_assignment = [a for a in received_assignments if a.item_id == "group:1"]
        assert len(group1_assignment) == 1
        assert "standard architectural analysis" in group1_assignment[0].analysis_angle.lower()

    def test_fan_out_reports_progress(self) -> None:
        items = _make_items(3)
        plan = self._make_plan(items)
        llm = MagicMock()

        progress_calls: list[tuple[int, int]] = []

        def progress_fn(done: int, total: int) -> None:
            progress_calls.append((done, total))

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=llm, concurrency=4)
        orch._fan_out(items, plan, worker_fn, progress_fn=progress_fn)

        assert len(progress_calls) == 3
        assert all(t == 3 for _, t in progress_calls)
        done_values = sorted(d for d, _ in progress_calls)
        assert done_values == [1, 2, 3]


# ---------------------------------------------------------------------------
# TestSynthesisPhase
# ---------------------------------------------------------------------------

class TestSynthesisPhase:
    def test_synthesis_produces_cross_group_insights(self) -> None:
        llm = MagicMock()
        llm.generate.return_value = (_mock_synthesis_response(), 200)

        worker_results = [
            WorkerResult(
                item_id=f"group:{i}",
                raw_output=_mock_worker_response(f"group:{i}"),
                parsed=json.loads(_mock_worker_response(f"group:{i}")),
                success=True,
            )
            for i in range(3)
        ]

        orch = SwarmOrchestrator(llm=llm)
        result, tokens = orch._synthesize(worker_results, "Synthesize:\n{worker_outputs}")

        assert result is not None
        assert "cross_group_patterns" in result
        assert "key_insight" in result
        assert "Event bus" in result["key_insight"]

    def test_synthesis_failure_returns_none(self) -> None:
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("LLM down")

        worker_results = [
            WorkerResult(item_id="group:0", raw_output="stuff", success=True)
        ]

        orch = SwarmOrchestrator(llm=llm)
        result, _ = orch._synthesize(worker_results, "Synthesize:\n{worker_outputs}")
        assert result is None

    def test_synthesis_skipped_when_no_successful_workers(self) -> None:
        llm = MagicMock()

        worker_results = [
            WorkerResult(item_id="group:0", raw_output="", success=False),
            WorkerResult(item_id="group:1", raw_output="", success=False),
        ]

        orch = SwarmOrchestrator(llm=llm)
        result, _ = orch._synthesize(worker_results, "Synthesize:\n{worker_outputs}")

        assert result is None
        llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# TestFullExecution
# ---------------------------------------------------------------------------

class TestFullExecution:
    def test_full_swarm_happy_path(self) -> None:
        items = _make_items(4)
        llm = MagicMock()

        # First call = coordinator, second call = synthesis
        llm.generate.side_effect = [
            (_mock_coordinator_response(items), 150),
            (_mock_synthesis_response(), 200),
        ]

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=llm, concurrency=4)
        result = orch.execute(
            items=items,
            coordinator_prompt="Coordinate:\n{group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synthesize:\n{worker_outputs}",
        )

        assert result is not None
        assert isinstance(result, SwarmResult)
        assert result.coordinator_plan is not None
        assert len(result.coordinator_plan.assignments) == 4
        assert len(result.worker_results) == 4
        assert all(r.success for r in result.worker_results)
        assert result.synthesis is not None
        assert "cross_group_patterns" in result.synthesis
        assert result.stats.total_items == 4
        assert result.stats.workers_succeeded == 4
        assert result.stats.workers_failed == 0
        assert result.stats.coordinator_tokens == 150
        assert result.stats.synthesis_tokens == 200
        assert result.stats.wall_clock_seconds > 0

    def test_coordinator_failure_falls_through_to_fanout(self) -> None:
        """When the coordinator AND synthesis fail, fan-out still runs
        with default assignments.  execute() returns None only for empty
        item lists."""
        items = _make_items(2)
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("LLM always fails")

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
            return _mock_worker_response(item.id)

        orch = SwarmOrchestrator(llm=llm, concurrency=4)
        result = orch.execute(
            items=items,
            coordinator_prompt="Coordinate:\n{group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synthesize:\n{worker_outputs}",
        )

        assert result is not None
        assert result.coordinator_plan is not None
        assert len(result.coordinator_plan.assignments) == 0  # empty fallback
        assert result.stats.workers_succeeded == 2  # workers ran with defaults
        assert result.synthesis is None  # synthesis also failed


# ---------------------------------------------------------------------------
# TestDualLLMConstructor
# ---------------------------------------------------------------------------


def test_decoupled_constructor_uses_distinct_clients() -> None:
    coord = MagicMock(name="coordinator_llm")
    worker = MagicMock(name="worker_llm")
    orch = SwarmOrchestrator(coordinator_llm=coord, worker_llm=worker, concurrency=3)
    assert orch.coordinator_llm is coord
    assert orch.worker_llm is worker


def test_inherit_fallback_when_coordinator_none() -> None:
    worker = MagicMock(name="worker_llm")
    orch = SwarmOrchestrator(coordinator_llm=None, worker_llm=worker)
    assert orch.coordinator_llm is worker  # inherited


def test_coordinator_none_fallback_routes_planning_through_worker() -> None:
    """Phase 112 fix 5: when coordinator_llm=None falls back to worker_llm,
    the Planning phase must route through the worker client (not crash)."""
    from codrag.core.swarm_orchestrator import WorkItem
    worker = MagicMock(name="worker_llm")
    worker.generate.return_value = ('{"assignments":[]}', 42)
    orch = SwarmOrchestrator(
        coordinator_llm=None,
        worker_llm=worker,
        coordinator_timeout_s=5,
        synthesis_timeout_s=5,
        worker_timeout_s=5,
        max_wall_time_s=15,
    )
    plan, _tokens = orch._coordinate(
        items=[WorkItem(id="x", summary="s", full_context="c")],
        coordinator_prompt="{group_summaries}",
    )
    # worker.generate IS the coordinator after the None fallback.
    assert worker.generate.called
    assert orch.coordinator_llm is worker


def test_legacy_single_llm_constructor_still_works() -> None:
    """Backward compatibility: `llm=` kwarg maps to both."""
    legacy = MagicMock(name="legacy_llm")
    orch = SwarmOrchestrator(llm=legacy, concurrency=3)
    assert orch.coordinator_llm is legacy
    assert orch.worker_llm is legacy


def test_coordinator_calls_use_coordinator_llm_only():
    from codrag.core.swarm_orchestrator import SwarmOrchestrator, WorkItem
    coord = MagicMock(name="coord")
    coord.generate.return_value = ('{"assignments":[]}', 100)
    worker = MagicMock(name="worker")
    worker.generate.return_value = ('{"result":"ok"}', 200)

    orch = SwarmOrchestrator(
        coordinator_llm=coord, worker_llm=worker,
        coordinator_timeout_s=5, synthesis_timeout_s=5,
        worker_timeout_s=5, max_wall_time_s=15,
    )
    plan, _tokens = orch._coordinate(
        items=[WorkItem(id="x", summary="s", full_context="c")],
        coordinator_prompt="{group_summaries}",
    )
    # coord.generate must have been called; worker.generate must NOT.
    assert coord.generate.called
    assert not worker.generate.called


# ---------------------------------------------------------------------------
# TestSwarmMetricsEmission  §9 observability
# ---------------------------------------------------------------------------


def test_swarm_emits_metrics_log_line(caplog) -> None:
    """SwarmResult-finalize emits the [Swarm-Metrics] log line for §9 observability."""
    items = _make_items(2)
    llm = MagicMock()
    llm.generate.side_effect = [
        (_mock_coordinator_response(items), 50),
        (_mock_synthesis_response(), 80),
    ]

    def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
        return _mock_worker_response(item.id)

    orch = SwarmOrchestrator(llm=llm, concurrency=2)

    with caplog.at_level(logging.INFO, logger="codrag.core.swarm_orchestrator"):
        result = orch.execute(
            items=items,
            coordinator_prompt="Coordinate:\n{group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synthesize:\n{worker_outputs}",
        )

    assert result is not None

    # Either record_swarm_metrics was called (if it exists in token_telemetry)
    # OR the structured log line was emitted.
    assert any(
        "[Swarm-Metrics]" in rec.message or "swarm_run" in rec.message
        for rec in caplog.records
    ), f"Expected [Swarm-Metrics] log line; got: {[r.message for r in caplog.records]}"


def test_swarm_metrics_contains_all_five_fields(caplog) -> None:
    """The [Swarm-Metrics] log line includes all five §9 metric fields."""
    items = _make_items(3)
    llm = MagicMock()
    llm.generate.side_effect = [
        (_mock_coordinator_response(items), 60),
        (_mock_synthesis_response(), 90),
    ]

    def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str:
        if item.id == "group:1":
            raise RuntimeError("intentional failure")
        return _mock_worker_response(item.id)

    orch = SwarmOrchestrator(llm=llm, concurrency=3)

    with caplog.at_level(logging.INFO, logger="codrag.core.swarm_orchestrator"):
        result = orch.execute(
            items=items,
            coordinator_prompt="Coordinate:\n{group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synthesize:\n{worker_outputs}",
        )

    assert result is not None
    # Find the metrics log record
    metrics_records = [
        r for r in caplog.records
        if "[Swarm-Metrics]" in r.message or "swarm_run" in r.message
    ]
    assert metrics_records, "No [Swarm-Metrics] record found"
    msg = metrics_records[0].message
    # All five metric fields must appear in the message
    for field in ("coord_valid", "synth_valid", "workers_succeeded", "workers_failed", "wall_clock_s"):
        assert field in msg, f"Missing field '{field}' in metrics message: {msg}"
