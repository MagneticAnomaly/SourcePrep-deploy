"""Phase 127 sub-phase 5: priority survives daemon restart."""
from __future__ import annotations


def test_priority_persists_across_scheduler_instances() -> None:
    """Set priority on instance A, create instance B, priority is restored."""
    from prep.services.pipeline.scheduler import PipelineScheduler

    a = PipelineScheduler()
    a.set_priority("proj-persist-test", "exclusive")
    a.persist_priority_state()  # explicit save

    b = PipelineScheduler()
    b.load_priority_state()  # explicit load
    assert b.get_priority("proj-persist-test") == "exclusive"

    # Cleanup
    b.set_priority("proj-persist-test", "none")
    b.persist_priority_state()
