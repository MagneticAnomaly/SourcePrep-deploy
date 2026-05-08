"""Phase 127 sub-phase 1: soft-hold primitive correctness."""
from __future__ import annotations


def _fresh_scheduler():
    """Return a fresh PipelineScheduler instance for testing.

    The scheduler is a singleton in production; these unit tests
    construct a private instance to keep state isolated.
    """
    from prep.services.pipeline.scheduler import PipelineScheduler
    return PipelineScheduler()


def test_no_holds_by_default() -> None:
    s = _fresh_scheduler()
    assert s.is_held("any-project", "any-endpoint") is False
    assert s.list_holds() == []


def test_set_hold_then_is_held() -> None:
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="exclusive", set_by_project="proj-B")
    assert s.is_held("proj-A", "cloud:default_ollama") is True
    # Other (project, endpoint) pairs are NOT held.
    assert s.is_held("proj-A", "cloud:openrouter") is False
    assert s.is_held("proj-B", "cloud:default_ollama") is False


def test_clear_hold_specific() -> None:
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="swarm", set_by_project="proj-B")
    s.clear_hold("proj-A", "cloud:default_ollama")
    assert s.is_held("proj-A", "cloud:default_ollama") is False


def test_clear_holds_by_setter_project() -> None:
    """When a swarm window closes, all holds it set should clear in one call."""
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="swarm", set_by_project="proj-B")
    s.set_hold("proj-A", "cloud:openrouter", reason="swarm", set_by_project="proj-B")
    s.set_hold("proj-C", "cloud:default_ollama", reason="exclusive", set_by_project="proj-D")
    # Clear only proj-B's holds.
    s.clear_holds_set_by("proj-B")
    assert s.is_held("proj-A", "cloud:default_ollama") is False
    assert s.is_held("proj-A", "cloud:openrouter") is False
    # Unrelated hold (set by proj-D) untouched.
    assert s.is_held("proj-C", "cloud:default_ollama") is True


def test_list_holds_returns_entries() -> None:
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="exclusive", set_by_project="proj-B")
    holds = s.list_holds()
    assert len(holds) == 1
    h = holds[0]
    assert h["project_id"] == "proj-A"
    assert h["endpoint_id"] == "cloud:default_ollama"
    assert h["reason"] == "exclusive"
    assert h["set_by_project"] == "proj-B"
    assert isinstance(h["held_since"], float)


def test_set_hold_overwrites_prior_setter() -> None:
    """Re-setting an existing hold replaces ownership.

    Documented behavior per set_hold docstring.  Important because a
    later clear_holds_set_by(prior) will NOT clear the re-set entry.
    """
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="swarm", set_by_project="proj-B")
    s.set_hold("proj-A", "cloud:default_ollama", reason="exclusive", set_by_project="proj-D")
    # Clearing by the original setter has no effect now.
    s.clear_holds_set_by("proj-B")
    assert s.is_held("proj-A", "cloud:default_ollama") is True
    # Clearing by the new setter does clear it.
    s.clear_holds_set_by("proj-D")
    assert s.is_held("proj-A", "cloud:default_ollama") is False


def test_clear_hold_of_nonexistent_is_noop() -> None:
    s = _fresh_scheduler()
    # Should not raise.
    s.clear_hold("proj-A", "cloud:default_ollama")
    assert s.is_held("proj-A", "cloud:default_ollama") is False


def test_clear_holds_set_by_no_match_is_noop() -> None:
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="swarm", set_by_project="proj-B")
    # Clearing by a setter that has no holds is a no-op.
    s.clear_holds_set_by("proj-NONEXISTENT")
    assert s.is_held("proj-A", "cloud:default_ollama") is True


def test_should_dispatch_returns_true_when_not_held() -> None:
    from prep.services.pipeline.workers import _should_dispatch_or_pause
    # No hold → dispatch immediately, no pause.
    assert _should_dispatch_or_pause(
        project_id="proj-A",
        endpoint_id="cloud:default_ollama",
        poll_interval_s=0.01,
        max_wait_s=0.05,
    ) is True


def test_should_dispatch_polls_then_returns_when_cleared() -> None:
    """When a hold is set then cleared mid-poll, the helper resumes."""
    import threading
    import time
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.workers import _should_dispatch_or_pause

    pipeline_scheduler.set_hold(
        "proj-A", "cloud:default_ollama", reason="manual", set_by_project="test",
    )

    def _clear_after_delay():
        time.sleep(0.05)
        pipeline_scheduler.clear_hold("proj-A", "cloud:default_ollama")

    threading.Thread(target=_clear_after_delay, daemon=True).start()
    try:
        result = _should_dispatch_or_pause(
            project_id="proj-A",
            endpoint_id="cloud:default_ollama",
            poll_interval_s=0.01,
            max_wait_s=1.0,
        )
        assert result is True
    finally:
        # Defensive: clear in case the daemon thread didn't get there.
        pipeline_scheduler.clear_hold("proj-A", "cloud:default_ollama")


def test_should_dispatch_returns_false_after_max_wait() -> None:
    """If hold never clears within max_wait_s, helper returns False."""
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.workers import _should_dispatch_or_pause

    pipeline_scheduler.set_hold(
        "proj-B", "cloud:default_ollama", reason="manual", set_by_project="test",
    )
    try:
        result = _should_dispatch_or_pause(
            project_id="proj-B",
            endpoint_id="cloud:default_ollama",
            poll_interval_s=0.01,
            max_wait_s=0.05,
        )
        assert result is False
    finally:
        pipeline_scheduler.clear_hold("proj-B", "cloud:default_ollama")


def test_exclusive_sets_holds_on_other_active_projects() -> None:
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.acquire("proj-Y", StageId.ENRICHMENT, "cloud:default_ollama")
    # User clicks Exclusive on a NEW project (not currently active).
    s.set_priority("proj-A", "exclusive")
    # Both other projects soft-held.
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    assert s.is_held("proj-Y", "cloud:default_ollama") is True
    # The exclusive project itself is not held.
    assert s.is_held("proj-A", "cloud:default_ollama") is False


def test_lifting_exclusive_clears_holds() -> None:
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.set_priority("proj-A", "exclusive")
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    s.set_priority("proj-A", "none")
    assert s.is_held("proj-X", "cloud:default_ollama") is False


def test_exclusive_to_boost_clears_holds() -> None:
    """Demoting from exclusive to boost must release exclusive holds."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.set_priority("proj-A", "exclusive")
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    s.set_priority("proj-A", "boost")
    assert s.is_held("proj-X", "cloud:default_ollama") is False


def test_exclusive_re_stamp_drops_stale_when_active_changes() -> None:
    """Re-stamping exclusive after active_stages changes drops stale holds."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.set_priority("proj-A", "exclusive")
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    # proj-X drains, proj-Y starts.
    s.release("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.acquire("proj-Y", StageId.ENRICHMENT, "cloud:default_ollama")
    # Re-stamp exclusive on proj-A.
    s.set_priority("proj-A", "exclusive")
    # Stale hold on proj-X should be gone; new hold on proj-Y in place.
    assert s.is_held("proj-X", "cloud:default_ollama") is False
    assert s.is_held("proj-Y", "cloud:default_ollama") is True


def test_new_exclusive_clears_demoted_projects_holds() -> None:
    """Setting a new project exclusive demotes prior exclusive AND clears its holds."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    # proj-A goes exclusive — holds proj-X.
    s.set_priority("proj-A", "exclusive")
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    # proj-B goes exclusive — proj-A demoted to boost; A's holds gone.
    s.acquire("proj-Y", StageId.ENRICHMENT, "cloud:default_ollama")
    s.set_priority("proj-B", "exclusive")
    # proj-X is now held by B (still active), not A.
    held = s.list_holds()
    a_holds = [h for h in held if h["set_by_project"] == "proj-A"]
    b_holds = [h for h in held if h["set_by_project"] == "proj-B"]
    assert a_holds == [], f"proj-A's holds should be cleared on demotion, got {a_holds}"
    assert len(b_holds) > 0, "proj-B should now hold the others"


def test_clear_all_priorities_clears_all_exclusive_holds() -> None:
    """clear_all_priorities() removes every exclusive-reason hold."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.set_priority("proj-A", "exclusive")
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    s.clear_all_priorities()
    assert s.is_held("proj-X", "cloud:default_ollama") is False


def test_epistemic_enricher_pauses_on_hold(monkeypatch) -> None:
    """When soft-held, EpistemicEnricher should NOT dispatch a new
    LLM call; it should pause and re-poll.

    This test verifies the helper works in the worker pattern.  The
    enricher integration is verified by the regression suite.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.workers import _should_dispatch_or_pause

    pipeline_scheduler.set_hold(
        "proj-pause-test", "cloud:default_ollama",
        reason="manual", set_by_project="test",
    )
    dispatched: list[bool] = []

    def fake_dispatch():
        ok = _should_dispatch_or_pause(
            project_id="proj-pause-test",
            endpoint_id="cloud:default_ollama",
            poll_interval_s=0.01,
            max_wait_s=0.1,
        )
        dispatched.append(ok)

    try:
        fake_dispatch()
        assert dispatched == [False], "dispatcher should have returned False (held)"

        pipeline_scheduler.clear_hold("proj-pause-test", "cloud:default_ollama")
        fake_dispatch()
        assert dispatched == [False, True], "dispatcher should have returned True after clear"
    finally:
        # Defensive: ensure no hold leaks to other tests on assertion failure.
        pipeline_scheduler.clear_hold("proj-pause-test", "cloud:default_ollama")


def test_epistemic_enricher_integration_pauses_on_hold(tmp_path) -> None:
    """End-to-end: construct the REAL EpistemicEnricher with a project_id,
    set a soft-hold matching the LLM's resolved scheduler node id, and
    verify:

      1. ``_hold_paused()`` returns True (delegation through
         ``hold_paused_for_llm`` works).
      2. ``_call_and_parse`` raises :class:`HoldPausedError` instead of
         returning ``None`` (so callers don't count the pause as a
         permanent failure that could trip a circuit breaker).
      3. The fake LLM's ``generate`` was never called.

    This catches the regression I-2 flagged: the prior unit test only
    exercised ``_should_dispatch_or_pause`` directly; the enricher's
    own resolver delegation and the new exception-based signaling were
    untested.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.holds import HoldPausedError
    from prep.core.epistemic_enrichment import EpistemicEnricher

    class FakeLLM:
        model = "fake-model"
        provider = "ollama"
        endpoint_id = "test-endpoint"
        endpoint_url = "http://localhost:11434"
        generate_calls = 0

        def _resolve_scheduler_node_id(self):
            return "cloud:test-endpoint"

        def generate(self, *args, **kwargs):
            FakeLLM.generate_calls += 1
            return ("text", {})

    fake = FakeLLM()
    enricher = EpistemicEnricher(
        llm=fake,
        repo_root=tmp_path,
        index_dir=tmp_path,
        project_id="proj-integration-test",
    )

    pipeline_scheduler.set_hold(
        "proj-integration-test", "cloud:test-endpoint",
        reason="manual", set_by_project="test",
    )
    try:
        # 1. Real class sees the hold via the resolver delegation.
        assert enricher._hold_paused() is True

        # 2. _call_and_parse raises HoldPausedError instead of returning None.
        try:
            enricher._call_and_parse(
                node_id="file:dummy.py",
                file_path="dummy.py",
                prompt="(short prompt — under 200k char guard)",
            )
        except HoldPausedError as hpe:
            assert hpe.project_id == "proj-integration-test"
            assert hpe.endpoint_id == "cloud:test-endpoint"
        else:
            assert False, "expected HoldPausedError when held"

        # 3. The LLM was never called.
        assert FakeLLM.generate_calls == 0, (
            f"LLM should not be called when held, got {FakeLLM.generate_calls} calls"
        )
    finally:
        pipeline_scheduler.clear_hold(
            "proj-integration-test", "cloud:test-endpoint",
        )


def test_augmenter_integration_pauses_on_hold(tmp_path) -> None:
    """End-to-end: construct the REAL TraceAugmenter with a project_id,
    set a soft-hold matching the LLM's resolved scheduler node id, and
    verify:

      1. ``_hold_paused()`` returns True (delegation through
         ``hold_paused_for_llm`` works).
      2. ``_llm_generate_with_retry`` raises :class:`HoldPausedError`
         instead of going through the retry loop (so a held endpoint
         doesn't burn retries against itself).
      3. The fake LLM's ``generate`` was never called.

    Mirrors the T2.5 epistemic-enricher pattern: the helper unit test
    only exercises the resolver; the integration test validates the
    real class's delegation and the new exception-based signaling.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.holds import HoldPausedError
    from prep.core.augmenter import TraceAugmenter

    class FakeLLM:
        model = "fake-model"
        provider = "ollama"
        endpoint_id = "test-endpoint"
        endpoint_url = "http://localhost:11434"
        timeout = 30.0
        generate_calls = 0

        def _resolve_scheduler_node_id(self):
            return "cloud:test-endpoint"

        def generate(self, *args, **kwargs):
            FakeLLM.generate_calls += 1
            return ("text", {})

    fake = FakeLLM()
    augmenter = TraceAugmenter(
        index_dir=tmp_path,
        repo_root=tmp_path,
        llm_client=fake,
        project_id="proj-aug-integration",
    )

    pipeline_scheduler.set_hold(
        "proj-aug-integration", "cloud:test-endpoint",
        reason="manual", set_by_project="test",
    )
    try:
        # 1. Real class sees the hold via the resolver delegation.
        assert augmenter._hold_paused() is True

        # 2. _llm_generate_with_retry raises HoldPausedError instead of
        #    retrying or returning normally.
        try:
            augmenter._llm_generate_with_retry(
                prompt="(short prompt)",
                system="test-system",
                label="test",
            )
        except HoldPausedError as hpe:
            assert hpe.project_id == "proj-aug-integration"
            assert hpe.endpoint_id == "cloud:test-endpoint"
        else:
            assert False, "expected HoldPausedError when held"

        # 3. The LLM was never called.
        assert FakeLLM.generate_calls == 0, (
            f"LLM should not be called when held, got {FakeLLM.generate_calls} calls"
        )
    finally:
        pipeline_scheduler.clear_hold(
            "proj-aug-integration", "cloud:test-endpoint",
        )


def test_swarm_orchestrator_pauses_at_phase_boundary(tmp_path) -> None:
    """End-to-end: SwarmOrchestrator with a soft-hold set should never
    dispatch the coordinator/fanout/synthesis LLM calls and should
    return a ``paused=True`` SwarmResult.

    Mirrors T2.5/T2.6 pattern: the helper unit test only exercises the
    resolver; the integration test validates the real class's
    delegation, the new exception-based signaling at phase boundaries,
    and the pause flag on SwarmResult.
    """
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.services.pipeline.holds import HoldPausedError
    from prep.core.swarm_orchestrator import (
        SwarmOrchestrator,
        WorkItem,
    )

    class FakeLLM:
        model = "fake-model"
        provider = "ollama"
        endpoint_id = "test-endpoint"
        endpoint_url = "http://localhost:11434"
        timeout = 30.0
        generate_calls = 0

        def _resolve_scheduler_node_id(self):
            return "cloud:test-endpoint"

        @property
        def _session(self):
            return None

        @property
        def _thread_local(self):
            class _TL:
                session = None
            return _TL()

        def generate(self, *args, **kwargs):
            FakeLLM.generate_calls += 1
            return ("text", 0)

    fake = FakeLLM()
    orch = SwarmOrchestrator(
        worker_llm=fake,
        coordinator_llm=fake,
        concurrency=1,
        project_id="proj-swarm-integration",
    )

    pipeline_scheduler.set_hold(
        "proj-swarm-integration", "cloud:test-endpoint",
        reason="manual", set_by_project="test",
    )
    try:
        # 1. Real orchestrator sees the hold via the resolver delegation.
        assert orch._hold_paused() is True

        # 2. _raise_hold_paused() raises HoldPausedError with the right
        #    project/endpoint pair.
        try:
            orch._raise_hold_paused()
        except HoldPausedError as hpe:
            assert hpe.project_id == "proj-swarm-integration"
            assert hpe.endpoint_id == "cloud:test-endpoint"
        else:
            assert False, "expected HoldPausedError when held"

        # 3. execute() catches the boundary HoldPausedError and returns
        #    a paused=True SwarmResult without dispatching any LLM call.
        items = [WorkItem(id="w1", summary="x", full_context="y")]

        def worker_fn(_item, _assignment):
            return None

        result = orch.execute(
            items=items,
            coordinator_prompt="(coord)",
            worker_fn=worker_fn,
            synthesis_prompt="(synth)",
            enable_event_log=False,
        )
        assert result is not None, "expected SwarmResult, not None"
        assert result.paused is True, (
            f"expected result.paused=True, got {result.paused}"
        )
        assert result.pause_info is not None
        assert result.pause_info["project_id"] == "proj-swarm-integration"
        assert result.pause_info["endpoint_id"] == "cloud:test-endpoint"
        # No LLM calls should have been dispatched.
        assert FakeLLM.generate_calls == 0, (
            f"LLM should not be called when held at the pre-coord boundary, "
            f"got {FakeLLM.generate_calls} calls"
        )
        # No synthesis when paused before coord.
        assert result.synthesis is None
    finally:
        pipeline_scheduler.clear_hold(
            "proj-swarm-integration", "cloud:test-endpoint",
        )


def test_swarm_orchestrator_paused_mid_fanout_salvages_partials() -> None:
    """When a hold is set mid-fanout, the swarm pauses at the next phase
    boundary (fanout→synth) and returns ``paused=True`` with salvaged
    worker results.

    The pre-coord-boundary test (above) only proves we don't dispatch
    against an already-held endpoint.  This case proves the salvage
    path: workers complete, the hold appears mid-flight, the
    fanout→synth boundary check raises HoldPausedError, and
    ``execute()`` returns the partial worker_results without invoking
    synthesis.
    """
    import json as _json
    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.core.swarm_orchestrator import SwarmOrchestrator, WorkItem

    project_id = "proj-swarm-mid-fanout"
    endpoint_resolved = "cloud:test-endpoint-mid"

    coord_calls = {"n": 0}
    synth_calls = {"n": 0}
    worker_calls = {"n": 0}

    def _coord_response(items):
        return _json.dumps({
            "assignments": [
                {
                    "item_id": it.id,
                    "analysis_angle": "default",
                    "priority_concerns": [],
                }
                for it in items
            ]
        })

    class FakeLLM:
        model = "fake-mid"
        provider = "ollama"
        endpoint_id = "test-endpoint-mid"
        endpoint_url = "http://localhost:11434"
        timeout = 30.0
        # The orchestrator's _llm_call_with_timeout helper touches
        # ``_session`` and reads ``_thread_local.session`` for zombie
        # cleanup; provide both so the call path doesn't AttributeError.
        _items_for_coord: list = []

        def _resolve_scheduler_node_id(self):
            return endpoint_resolved

        @property
        def _session(self):
            return None

        @property
        def _thread_local(self):
            class _TL:
                session = None
            return _TL()

        def generate(self, *args, **kwargs):
            # Distinguish coord vs synth by the system prompt content.
            system = kwargs.get("system", "")
            if "synthesizing" in system:
                synth_calls["n"] += 1
                return ('{"key_insight": "should not reach here"}', 0)
            else:
                coord_calls["n"] += 1
                return (_coord_response(FakeLLM._items_for_coord), 0)

    fake_coord = FakeLLM()
    fake_worker = FakeLLM()

    # Build 4 items so we get at least 2 worker calls before the hold
    # latches (concurrency=1 forces strict serial worker execution).
    items = [
        WorkItem(id=f"w{i}", summary=f"item {i}", full_context=f"ctx {i}")
        for i in range(4)
    ]
    FakeLLM._items_for_coord = items

    orch = SwarmOrchestrator(
        worker_llm=fake_worker,
        coordinator_llm=fake_coord,
        concurrency=1,
        project_id=project_id,
    )

    def worker_fn(item, assignment):
        worker_calls["n"] += 1
        # On the second worker call, set the hold.  The remaining
        # workers may still execute (they're already-submitted futures
        # in the fan-out pool), but the post-fanout boundary check in
        # execute() will detect the hold and raise HoldPausedError
        # before synthesis runs.
        if worker_calls["n"] == 2:
            pipeline_scheduler.set_hold(
                project_id, endpoint_resolved,
                reason="exclusive", set_by_project="proj-other",
            )
        # Return a parseable JSON worker output so the result is marked
        # successful (so we can assert salvage actually returned data).
        return _json.dumps({"finding": f"ok-{item.id}"})

    try:
        result = orch.execute(
            items=items,
            coordinator_prompt="Coordinate:\n{group_summaries}",
            worker_fn=worker_fn,
            synthesis_prompt="Synthesize:\n{worker_outputs}",
            enable_event_log=False,
        )

        assert result is not None, "expected SwarmResult, not None"
        # Pause must be signaled — the fanout→synth boundary saw the hold.
        assert result.paused is True, (
            f"expected result.paused=True after mid-fanout hold, got {result.paused}"
        )
        assert result.pause_info is not None
        assert result.pause_info["project_id"] == project_id
        assert result.pause_info["endpoint_id"] == endpoint_resolved

        # Salvage: at least one worker DID run before the hold latched.
        assert worker_calls["n"] >= 1, (
            f"expected at least one worker to run before pause, got {worker_calls['n']}"
        )
        # Salvaged worker results are preserved on the SwarmResult.
        assert result.worker_results, "expected salvaged worker_results, got empty list"
        assert any(r.success for r in result.worker_results), (
            "expected at least one successful worker_result in salvage"
        )

        # Synthesis must NOT have run — the hold caught us at fanout→synth.
        assert synth_calls["n"] == 0, (
            f"synthesis should not have been dispatched after mid-fanout hold, "
            f"got {synth_calls['n']} synth calls"
        )
        assert result.synthesis is None, (
            "expected result.synthesis=None when paused at fanout→synth boundary"
        )
    finally:
        pipeline_scheduler.clear_hold(project_id, endpoint_resolved)


def test_augmenter_run_returns_paused_when_held_at_preflight(tmp_path) -> None:
    """End-to-end: TraceAugmenter.run() with a hold set BEFORE work
    starts returns ``paused=True`` without invoking the LLM.

    Drives the pre-flight bypass at augmenter.py:~L1720: the run() loads
    trace nodes, computes the work set, then checks ``_hold_paused()``.
    When held, it skips the pre-flight LLM probe, populates
    ``result.paused`` / ``result.pause_info`` with the resolved
    (project, endpoint) tuple, and returns cleanly.

    Reviewer-flagged gap: the existing T2.6 integration test only
    exercised ``_llm_generate_with_retry`` directly; the run()
    pre-flight bypass and the AugmentResult.paused signaling had no
    end-to-end coverage.
    """
    import json

    from prep.services.pipeline.scheduler import pipeline_scheduler
    from prep.core.augmenter import TraceAugmenter

    # Build a minimal index_dir + repo_root with one trace node so the
    # run() reaches the pre-flight check (early-returns when nodes==[]).
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "main.py").write_text('def hello():\n    pass\n')

    nodes = [
        {
            "id": "node-file-1",
            "kind": "file",
            "name": "main.py",
            "file_path": "main.py",
            "span": None,
            "language": "python",
            "metadata": {},
        },
    ]
    with open(index_dir / "trace_nodes.jsonl", "w") as f:
        for n in nodes:
            f.write(json.dumps(n) + "\n")
    with open(index_dir / "trace_edges.jsonl", "w") as f:
        pass  # empty edges file
    with open(index_dir / "trace_manifest.json", "w") as f:
        json.dump(
            {
                "version": "1.0",
                "built_at": "2025-02-11T00:00:00Z",
                "counts": {"nodes": len(nodes), "edges": 0},
            },
            f,
        )

    class FakeLLM:
        model = "fake-model"
        provider = "ollama"
        endpoint_id = "test-endpoint"
        endpoint_url = "http://localhost:11434"
        timeout = 30.0
        generate_calls = 0

        def _resolve_scheduler_node_id(self):
            return "cloud:test-endpoint"

        def generate(self, *args, **kwargs):
            FakeLLM.generate_calls += 1
            return ("text", 100)

    fake = FakeLLM()
    augmenter = TraceAugmenter(
        index_dir=index_dir,
        repo_root=repo_root,
        llm_client=fake,
        project_id="proj-aug-run-test",
    )

    pipeline_scheduler.set_hold(
        "proj-aug-run-test", "cloud:test-endpoint",
        reason="manual", set_by_project="test",
    )
    try:
        result = augmenter.run()
        assert result.paused is True, (
            f"expected result.paused=True, got {result.paused}"
        )
        assert result.pause_info is not None, "expected pause_info populated"
        assert result.pause_info["project_id"] == "proj-aug-run-test"
        assert result.pause_info["endpoint_id"] == "cloud:test-endpoint"
        # Pre-flight LLM probe must NOT have been dispatched.
        assert FakeLLM.generate_calls == 0, (
            f"LLM should not be called when held at pre-flight, "
            f"got {FakeLLM.generate_calls} calls"
        )
    finally:
        pipeline_scheduler.clear_hold(
            "proj-aug-run-test", "cloud:test-endpoint",
        )


def test_swarm_orchestrator_honors_cancel_token_pre_coord() -> None:
    """Phase 127 (P127-F9): when cancel_token is set BEFORE execute() runs,
    the swarm raises PipelinePausedError at the pre-coord boundary without
    dispatching any LLM call.

    Mirrors the soft-hold pre-coord pattern: same boundary, different
    exception type.  The PipelinePausedError must propagate so the
    worker dispatcher (build_orchestrator._run_worker) can transition
    the slot to inactive — that's the contract that lets the orchestrator's
    _pause_group wait-loop see slot.is_active flip false.
    """
    from prep.core.swarm_orchestrator import SwarmOrchestrator, WorkItem
    from prep.services.cancellation import CancellationToken, PipelinePausedError

    class FakeLLM:
        model = "fake-cancel"
        provider = "ollama"
        endpoint_id = "test-cancel"
        endpoint_url = "http://localhost:11434"
        timeout = 30.0
        generate_calls = 0

        def _resolve_scheduler_node_id(self):
            return "cloud:test-cancel"

        @property
        def _session(self):
            return None

        @property
        def _thread_local(self):
            class _TL:
                session = None
            return _TL()

        def generate(self, *args, **kwargs):
            FakeLLM.generate_calls += 1
            return ("text", 0)

    fake = FakeLLM()
    orch = SwarmOrchestrator(
        worker_llm=fake,
        coordinator_llm=fake,
        concurrency=1,
        project_id=None,  # no project_id so soft-hold is a no-op
    )

    token = CancellationToken()
    token.pause()

    items = [WorkItem(id="w1", summary="x", full_context="y")]

    def worker_fn(_item, _assignment):
        return None

    raised = False
    try:
        orch.execute(
            items=items,
            coordinator_prompt="(coord)",
            worker_fn=worker_fn,
            synthesis_prompt="(synth)",
            enable_event_log=False,
            cancel_token=token,
        )
    except PipelinePausedError:
        raised = True

    assert raised, "expected PipelinePausedError to propagate from execute()"
    # No LLM calls — pre-coord boundary check fired.
    assert FakeLLM.generate_calls == 0, (
        f"LLM should not be called when cancel_token is set, "
        f"got {FakeLLM.generate_calls} calls"
    )


def test_swarm_orchestrator_honors_cancel_token_mid_fanout() -> None:
    """Phase 127 (P127-F9): when cancel_token is set DURING fanout, the
    swarm shuts the pool down (no new workers dispatch) and raises
    PipelinePausedError without invoking synthesis.

    Salvage path: workers that already started complete naturally (Python
    can't safely cancel a thread mid-HTTP-request); not-yet-started
    futures are cancelled via cancel_futures=True; synth is skipped.

    To make the test deterministic, the cancel is set BEFORE any worker
    runs (gating it via a threading.Event); the test then verifies that
    even though many work items were submitted, fanout raises
    PipelinePausedError before synthesis, because the cancel is detected
    at the top of the wait-loop on the very first iteration.
    """
    import json as _json
    import threading as _threading

    from prep.core.swarm_orchestrator import SwarmOrchestrator, WorkItem
    from prep.services.cancellation import CancellationToken, PipelinePausedError

    synth_calls = {"n": 0}
    worker_calls = {"n": 0}
    worker_lock = _threading.Lock()
    # Gate that holds the first worker until we set the cancel.  Once
    # the first worker is admitted into worker_fn, it has already been
    # dispatched as a future — so this exercises "cancel raised between
    # the first and second worker dispatch".
    proceed_event = _threading.Event()
    started_event = _threading.Event()

    def _coord_response(items):
        return _json.dumps({
            "assignments": [
                {
                    "item_id": it.id,
                    "analysis_angle": "default",
                    "priority_concerns": [],
                }
                for it in items
            ]
        })

    class FakeLLM:
        model = "fake-cancel-mid"
        provider = "ollama"
        endpoint_id = "test-cancel-mid"
        endpoint_url = "http://localhost:11434"
        timeout = 30.0
        _items_for_coord: list = []

        def _resolve_scheduler_node_id(self):
            return "cloud:test-cancel-mid"

        @property
        def _session(self):
            return None

        @property
        def _thread_local(self):
            class _TL:
                session = None
            return _TL()

        def generate(self, *args, **kwargs):
            system = kwargs.get("system", "")
            if "synthesizing" in system:
                synth_calls["n"] += 1
                return ('{"key_insight": "should not reach here"}', 0)
            else:
                return (_coord_response(FakeLLM._items_for_coord), 0)

    fake_coord = FakeLLM()
    fake_worker = FakeLLM()

    items = [
        WorkItem(id=f"w{i}", summary=f"item {i}", full_context=f"ctx {i}")
        for i in range(4)
    ]
    FakeLLM._items_for_coord = items

    orch = SwarmOrchestrator(
        worker_llm=fake_worker,
        coordinator_llm=fake_coord,
        concurrency=1,  # serial workers so the cancel latches deterministically
        project_id=None,
    )

    token = CancellationToken()

    def worker_fn(item, assignment):
        with worker_lock:
            worker_calls["n"] += 1
            n = worker_calls["n"]
        if n == 1:
            # Signal we've started the first worker, then wait for the
            # main thread to set the cancel before returning a result.
            started_event.set()
            proceed_event.wait(timeout=2.0)
        return _json.dumps({"finding": f"ok-{item.id}"})

    # Run execute() in a thread so the main thread can set the cancel
    # after the first worker is actively running.
    raised_exc: list = []

    def _run():
        try:
            orch.execute(
                items=items,
                coordinator_prompt="Coordinate:\n{group_summaries}",
                worker_fn=worker_fn,
                synthesis_prompt="Synthesize:\n{worker_outputs}",
                enable_event_log=False,
                cancel_token=token,
            )
        except BaseException as e:
            raised_exc.append(e)

    t = _threading.Thread(target=_run, daemon=True)
    t.start()
    # Wait for the first worker to actually be running.
    assert started_event.wait(timeout=5.0), (
        "first worker never started within 5s — test setup broken"
    )
    # Set the cancel while the first worker is paused.
    token.pause()
    # Let the first worker complete.
    proceed_event.set()
    # Wait for execute() to return.
    t.join(timeout=10.0)
    assert not t.is_alive(), "execute() did not return within 10s"

    # PipelinePausedError must propagate.
    assert raised_exc, "expected an exception to propagate"
    assert isinstance(raised_exc[0], PipelinePausedError), (
        f"expected PipelinePausedError, got {type(raised_exc[0]).__name__}: "
        f"{raised_exc[0]}"
    )

    # The first worker did run (it was already dispatched).
    assert worker_calls["n"] >= 1, (
        f"expected at least one worker to run before cancel, got {worker_calls['n']}"
    )
    # Critically: not all 4 workers ran.  cancel_futures + the
    # post-batch cancel check stopped dispatch.
    assert worker_calls["n"] < 4, (
        f"expected fanout to stop dispatching new workers after cancel, "
        f"got {worker_calls['n']} (all 4 workers completed despite cancel)"
    )
    # Synthesis must NOT have run — the boundary check after fanout
    # fires when cancel propagates.
    assert synth_calls["n"] == 0, (
        f"synthesis should not have been dispatched after cancel, "
        f"got {synth_calls['n']} synth calls"
    )
