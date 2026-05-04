"""Phase 127 sub-phase 3: endpoint-disjoint exception."""
from __future__ import annotations


def _setup():
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    s.configure_node("cloud:openrouter", max_concurrent=1)
    return s, StageId


def test_swarm_only_holds_projects_on_conflicting_endpoints() -> None:
    """proj-A swarms using only Ollama Cloud.  proj-X is on OpenRouter.
    proj-X should NOT be held — endpoints disjoint."""
    s, StageId = _setup()
    s.acquire("proj-X", StageId.CONCEPTS, "cloud:openrouter")
    s.open_swarm_window(
        "proj-A", StageId.GROUP_REASONING,
        node_id="cloud:default_ollama",
        endpoint_set={"cloud:default_ollama"},
    )
    assert s.is_held("proj-X", "cloud:openrouter") is False


def test_swarm_with_multi_endpoint_holds_all_intersecting() -> None:
    """proj-A swarms using BOTH Ollama Cloud and OpenRouter.  proj-X is
    on OpenRouter; proj-Y is on Ollama Cloud.  Both held."""
    s, StageId = _setup()
    s.acquire("proj-X", StageId.CONCEPTS, "cloud:openrouter")
    s.acquire("proj-Y", StageId.CATALOGUE, "cloud:default_ollama")
    s.open_swarm_window(
        "proj-A", StageId.GROUP_REASONING,
        node_id="cloud:default_ollama",
        endpoint_set={"cloud:default_ollama", "cloud:openrouter"},
    )
    assert s.is_held("proj-X", "cloud:openrouter") is True
    assert s.is_held("proj-Y", "cloud:default_ollama") is True
