"""Phase 127 sub-phase 2: boost projects skip ahead in the queue."""
from __future__ import annotations


def _setup_scheduler():
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    return s, StageId


def test_boost_skips_ahead_of_normal() -> None:
    """Two normals queued first, then a boost; boost runs first."""
    s, StageId = _setup_scheduler()
    # Normal projects fill the queue first.
    s.enqueue("proj-N1", StageId.ENRICHMENT, "cloud:default_ollama")
    s.enqueue("proj-N2", StageId.ENRICHMENT, "cloud:default_ollama")
    # Boost project arrives last.
    s.set_priority("proj-B", "boost")
    s.enqueue("proj-B", StageId.ENRICHMENT, "cloud:default_ollama")

    next_entry = s.dequeue_next("cloud:default_ollama")
    assert next_entry is not None
    assert next_entry.project_id == "proj-B"


def test_fifo_within_same_tier() -> None:
    """Two normals queued in order; FIFO within the normal tier."""
    s, StageId = _setup_scheduler()
    s.enqueue("proj-N1", StageId.ENRICHMENT, "cloud:default_ollama")
    s.enqueue("proj-N2", StageId.ENRICHMENT, "cloud:default_ollama")
    next_entry = s.dequeue_next("cloud:default_ollama")
    assert next_entry.project_id == "proj-N1"


def test_boost_fifo_within_boost_tier() -> None:
    s, StageId = _setup_scheduler()
    s.set_priority("proj-B1", "boost")
    s.set_priority("proj-B2", "boost")
    s.enqueue("proj-B1", StageId.ENRICHMENT, "cloud:default_ollama")
    s.enqueue("proj-B2", StageId.ENRICHMENT, "cloud:default_ollama")
    next_entry = s.dequeue_next("cloud:default_ollama")
    assert next_entry.project_id == "proj-B1"


def test_release_honors_boost_priority() -> None:
    """release() returns the next queue entry by boost-weighted FIFO,
    not raw popleft.  This is the production code path; the standalone
    dequeue_next must agree with release()'s behavior."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=1)

    # proj-X is the active stage (will be released).
    s.acquire("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    # Queue normal project first, then boost.
    s.enqueue("proj-N", StageId.ENRICHMENT, "cloud:default_ollama")
    s.set_priority("proj-B", "boost")
    s.enqueue("proj-B", StageId.ENRICHMENT, "cloud:default_ollama")

    # Release proj-X.  Boost project should be returned next.
    next_entry = s.release("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    assert next_entry is not None
    assert next_entry.project_id == "proj-B"


def test_dequeue_next_skips_swarm_blocked_projects() -> None:
    """A project currently held by an open swarm window for another
    project should be skipped in dequeue_next."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    # Open a swarm window for proj-S.
    s.open_swarm_window("proj-S", StageId.GROUP_REASONING, "cloud:default_ollama")
    # proj-X queues; it should be considered blocked-by-swarm.
    s.enqueue("proj-X", StageId.ENRICHMENT, "cloud:default_ollama")
    # dequeue_next returns None (only candidate is swarm-blocked).
    assert s.dequeue_next("cloud:default_ollama") is None
    # Close the window; now proj-X is dequeue-able.
    s.close_swarm_window()
    next_entry = s.dequeue_next("cloud:default_ollama")
    assert next_entry is not None
    assert next_entry.project_id == "proj-X"
