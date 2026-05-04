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


# ── Phase 127 T3.2: _is_blocked_by_swarm consults endpoint_set ────────


def test_is_blocked_by_swarm_blocks_secondary_endpoint() -> None:
    """A multi-endpoint swarm window must block NEW acquisitions on every
    endpoint it covers — not just the primary node_id.  Otherwise a
    project that races in after window-open on the secondary endpoint
    can acquire a slot the swarm needs."""
    s, StageId = _setup()
    s.open_swarm_window(
        "proj-A", StageId.GROUP_REASONING,
        node_id="cloud:default_ollama",
        endpoint_set={"cloud:default_ollama", "cloud:openrouter"},
    )
    # proj-B should be blocked on BOTH endpoints the swarm holds
    assert s._is_blocked_by_swarm("proj-B", "cloud:default_ollama") is True
    assert s._is_blocked_by_swarm("proj-B", "cloud:openrouter") is True
    # The swarm's own project is never blocked by its own window
    assert s._is_blocked_by_swarm("proj-A", "cloud:default_ollama") is False
    assert s._is_blocked_by_swarm("proj-A", "cloud:openrouter") is False


def test_is_blocked_by_swarm_disjoint_endpoint_not_blocked() -> None:
    """A single-endpoint swarm must not block acquisitions on disjoint
    endpoints.  Backward compat: when endpoint_set is omitted, defaults
    to {node_id}."""
    s, StageId = _setup()
    s.configure_node("cloud:groq", max_concurrent=1)
    s.open_swarm_window(
        "proj-A", StageId.GROUP_REASONING,
        node_id="cloud:default_ollama",
        endpoint_set={"cloud:default_ollama"},
    )
    # proj-B on a totally different endpoint is fine
    assert s._is_blocked_by_swarm("proj-B", "cloud:groq") is False
    # ...but still blocked on the swarm's endpoint
    assert s._is_blocked_by_swarm("proj-B", "cloud:default_ollama") is True


def test_is_blocked_by_swarm_legacy_window_without_endpoint_set() -> None:
    """Backward-compat: legacy windows whose dict was constructed without
    ``endpoint_set`` (e.g. a future code path or test helper) still gate
    correctly via the ``node_id`` fallback."""
    from prep.services.pipeline.scheduler import PipelineScheduler
    from prep.services.pipeline.stages import StageId
    s = PipelineScheduler()
    s.configure_node("cloud:default_ollama", max_concurrent=10)
    # Manually install a legacy-shaped window (no endpoint_set key)
    with s._lock:
        s._swarm_window = {
            "project_id": "proj-A",
            "stage": StageId.GROUP_REASONING,
            "node_id": "cloud:default_ollama",
            "started_at": 0.0,
            "drain_targets": {},
        }
    assert s._is_blocked_by_swarm("proj-B", "cloud:default_ollama") is True
    assert s._is_blocked_by_swarm("proj-A", "cloud:default_ollama") is False
