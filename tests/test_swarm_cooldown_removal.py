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
