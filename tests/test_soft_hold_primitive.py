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
