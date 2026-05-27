"""P127-F1 regression: stale-hold TTL sweep.

Background: open_swarm_window / set_priority(exclusive) stamp holds in
self._holds.  Their natural clear paths are close_swarm_window() /
set_priority(..., "none").  If a bug-path skips those clears, the hold
sits indefinitely and silently pauses workers on the held endpoint.

check_drain_timeouts already runs periodically (every 30s while a swarm
window is active) but only clears drain_targets — it never touches the
hold registry.

sweep_stale_holds is the safety net: it clears any non-"manual" hold
whose backing state (priority / swarm window) is gone AND whose age
exceeds drain_timeout + grace.  Both conditions are required so we
never preempt a legitimate active hold whose natural clear path is
racing with us.
"""
from __future__ import annotations

import time


def _fresh_scheduler():
    from prep.services.pipeline.scheduler import PipelineScheduler
    return PipelineScheduler()


def _age_hold(scheduler, project_id: str, endpoint_id: str, seconds_ago: float) -> None:
    """Backdate a hold's held_since.  Caller must already have created the hold."""
    from prep.services.pipeline.holds import HoldKey
    entry = scheduler._holds[HoldKey(project_id=project_id, endpoint_id=endpoint_id)]
    entry.held_since = time.time() - seconds_ago


# ── Orphan: backing state gone ─────────────────────────────────────


def test_sweep_clears_orphan_exclusive_hold_when_priority_gone() -> None:
    """Exclusive-reason hold whose set_by_project is no longer in
    exclusive mode is a candidate for sweep.  When sufficiently aged,
    sweep removes it and reports the cleared id.
    """
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="exclusive", set_by_project="proj-X")
    _age_hold(s, "proj-A", "cloud:default_ollama", seconds_ago=10_000)
    # proj-X has NO exclusive priority recorded.
    cleared = s.sweep_stale_holds()
    assert s.is_held("proj-A", "cloud:default_ollama") is False
    assert any("proj-A" in c and "exclusive" in c for c in cleared), (
        f"expected the cleared hold to be reported with project + reason, got {cleared!r}"
    )


def test_sweep_clears_orphan_swarm_hold_when_window_closed() -> None:
    """Swarm-reason hold with no active swarm window owned by
    set_by_project is orphan."""
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:openrouter", reason="swarm", set_by_project="proj-Y")
    _age_hold(s, "proj-A", "cloud:openrouter", seconds_ago=10_000)
    assert s._swarm_window is None  # baseline sanity
    cleared = s.sweep_stale_holds()
    assert s.is_held("proj-A", "cloud:openrouter") is False
    assert any("swarm" in c for c in cleared)


# ── Preserved: backing state still present ─────────────────────────


def test_sweep_preserves_active_exclusive_hold() -> None:
    """When set_by_project IS still in exclusive mode, the hold is
    backed by live state and must not be swept even if old."""
    s = _fresh_scheduler()
    # set_priority(X, exclusive) stamps holds on all OTHER active stages,
    # but here there are no other projects with active stages — so we
    # stamp the hold manually to test the sweep predicate in isolation.
    s.set_priority("proj-X", "exclusive")
    s.set_hold("proj-A", "cloud:default_ollama", reason="exclusive", set_by_project="proj-X")
    _age_hold(s, "proj-A", "cloud:default_ollama", seconds_ago=10_000)
    cleared = s.sweep_stale_holds()
    assert s.is_held("proj-A", "cloud:default_ollama") is True
    assert cleared == []


def test_sweep_preserves_active_swarm_hold() -> None:
    """When _swarm_window's owner matches set_by_project, the hold is
    backed and must not be swept."""
    s = _fresh_scheduler()
    s._swarm_window = {"project_id": "proj-Y", "node_id": "cloud:default_ollama",
                       "drain_targets": {}, "endpoint_set": {"cloud:default_ollama"},
                       "stage": "test", "started_at": time.time()}
    s.set_hold("proj-A", "cloud:default_ollama", reason="swarm", set_by_project="proj-Y")
    _age_hold(s, "proj-A", "cloud:default_ollama", seconds_ago=10_000)
    cleared = s.sweep_stale_holds()
    assert s.is_held("proj-A", "cloud:default_ollama") is True
    assert cleared == []


# ── Grace period: young orphan holds are NOT swept ────────────────


def test_sweep_respects_grace_period() -> None:
    """An orphan hold younger than (drain_timeout + grace) must NOT be
    swept — its natural clear path may still be racing with us."""
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="swarm", set_by_project="proj-Z")
    # Held for 30s — well under drain_timeout (600s) + grace (300s) = 900s.
    _age_hold(s, "proj-A", "cloud:default_ollama", seconds_ago=30)
    cleared = s.sweep_stale_holds()
    assert s.is_held("proj-A", "cloud:default_ollama") is True
    assert cleared == []


# ── Manual holds: never auto-swept ────────────────────────────────


def test_sweep_never_touches_manual_holds() -> None:
    """reason='manual' is reserved for tests/admin tooling.  Sweep must
    leave it alone even if old and unbacked."""
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="manual", set_by_project="admin")
    _age_hold(s, "proj-A", "cloud:default_ollama", seconds_ago=100_000)
    cleared = s.sweep_stale_holds()
    assert s.is_held("proj-A", "cloud:default_ollama") is True
    assert cleared == []


# ── Misc ─────────────────────────────────────────────────────────


def test_sweep_with_no_holds_returns_empty_list() -> None:
    s = _fresh_scheduler()
    cleared = s.sweep_stale_holds()
    assert cleared == []


def test_sweep_custom_grace_overrides_default() -> None:
    """grace_s kwarg shortens (or extends) the sweep threshold."""
    s = _fresh_scheduler()
    s.set_hold("proj-A", "cloud:default_ollama", reason="swarm", set_by_project="proj-Z")
    _age_hold(s, "proj-A", "cloud:default_ollama", seconds_ago=650)
    # Default grace (300s) → total 900s → 650s is NOT old enough.
    assert s.sweep_stale_holds() == []
    assert s.is_held("proj-A", "cloud:default_ollama") is True
    # grace_s=0 → total 600s → 650s IS old enough.
    cleared = s.sweep_stale_holds(grace_s=0.0)
    assert s.is_held("proj-A", "cloud:default_ollama") is False
    assert len(cleared) == 1
