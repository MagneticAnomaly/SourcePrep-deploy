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
