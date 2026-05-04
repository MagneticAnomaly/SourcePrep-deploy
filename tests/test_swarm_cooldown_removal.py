"""Phase 127 sub-phase 2: cooldown was removed; same project can re-open
swarm window immediately."""
from __future__ import annotations

import pytest


def test_swarm_window_can_reopen_immediately_after_close() -> None:
    """No cooldown — close then immediate re-open succeeds."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)

    assert s.open_swarm_window("proj-A", StageId.GROUP_REASONING, "cloud:default_ollama") is True
    s.close_swarm_window()
    # Immediate re-open by ANY project succeeds (same or different).
    assert s.open_swarm_window("proj-A", StageId.CLUSTERING, "cloud:default_ollama") is True


def test_no_swarm_cooldown_seconds_attribute() -> None:
    """Make sure the cooldown timer field is gone so future readers
    don't think it's still load-bearing."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    s = PipelineScheduler()
    assert not hasattr(s, "_swarm_cooldown_seconds"), (
        "Phase 127 removed _swarm_cooldown_seconds — see Phase 127 spec §7.4"
    )
    assert not hasattr(s, "_swarm_cooldown_until"), (
        "Phase 127 removed _swarm_cooldown_until — see Phase 127 spec §7.4"
    )


def test_open_swarm_sets_holds_on_drain_targets() -> None:
    """When swarm window opens, every other active project on the same
    node gets a soft-hold."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    # proj-X is already running on the node.
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    # proj-A opens a swarm window.
    assert s.open_swarm_window("proj-A", StageId.GROUP_REASONING, "cloud:default_ollama") is True
    # proj-X should be soft-held on this node.
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    # proj-A (the swarm owner) is NOT held.
    assert s.is_held("proj-A", "cloud:default_ollama") is False


def test_close_swarm_clears_drain_holds() -> None:
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    s.open_swarm_window("proj-A", StageId.GROUP_REASONING, "cloud:default_ollama")
    assert s.is_held("proj-X", "cloud:default_ollama") is True
    s.close_swarm_window()
    assert s.is_held("proj-X", "cloud:default_ollama") is False
