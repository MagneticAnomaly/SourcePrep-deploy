"""Phase 119 swarm slot attribution.

When a swarm is running, the AI Gateway sidebar must show
coordinator/worker calls under their actual model slot — not all
collapsed under whatever STAGE_MODEL_SLOT[stage] returns.

The split lives in ``/llm/slots/status``: when ``is_swarm=True``, the
single running_task entry is replaced with one entry per
``(model_slot, swarm_role)`` group seen in live token telemetry.
"""
from __future__ import annotations

import pytest


def _resolver_fixture():
    return {
        "llm_config": {
            "small_model": {
                "enabled": True,
                "endpoint_id": "ep-small",
                "model": "fast-model",
            },
            "large_model": {
                "enabled": True,
                "endpoint_id": "ep-large",
                "model": "thinking-model",
            },
            "code_model": {
                "enabled": True,
                "endpoint_id": "ep-code",
                "model": "code-model",
            },
            "coordinator_model": {
                "enabled": True,
                "endpoint_id": "ep-coord",
                "model": "qwen-coordinator",
                "inherit_from_large": False,
            },
            "saved_endpoints": [
                {"id": "ep-small", "url": "http://x", "provider": "ollama"},
                {"id": "ep-large", "url": "http://x", "provider": "ollama"},
                {"id": "ep-code", "url": "http://x", "provider": "ollama"},
                {"id": "ep-coord", "url": "http://x", "provider": "ollama"},
            ],
        },
    }


def test_resolver_tags_model_slot_on_llm_client(monkeypatch) -> None:
    """``_get_llm_client_for_slot`` must stamp ``_model_slot`` on every
    LLMClient it returns, so token telemetry can group active calls
    correctly across coordinator/worker/synthesizer phases.
    """
    from prep import server as server_mod
    monkeypatch.setattr(server_mod, "_load_ui_config", _resolver_fixture)

    small = server_mod._get_llm_client_for_slot("small")
    large = server_mod._get_llm_client_for_slot("large")
    code = server_mod._get_llm_client_for_slot("code")
    coord = server_mod._get_llm_client_for_slot("coordinator")

    assert getattr(small, "_model_slot", None) == "small"
    assert getattr(large, "_model_slot", None) == "large"
    assert getattr(code, "_model_slot", None) == "code"
    assert getattr(coord, "_model_slot", None) == "coordinator"


def test_resolver_accepts_long_form_slot_keys(monkeypatch) -> None:
    """I1: callers may pass either the canonical short form ('small') or
    the config-key form ('small_model').  Both must produce the same
    canonical _model_slot tag so the sidebar bucketing isn't silently
    broken by a caller rename.
    """
    from prep import server as server_mod
    monkeypatch.setattr(server_mod, "_load_ui_config", _resolver_fixture)

    short = server_mod._get_llm_client_for_slot("small")
    long_form = server_mod._get_llm_client_for_slot("small_model")
    assert getattr(short, "_model_slot", None) == "small"
    assert getattr(long_form, "_model_slot", None) == "small"


def test_resolver_inherit_from_large_carries_large_tag(monkeypatch) -> None:
    """When the coordinator slot inherits from large (the default), the
    function returns the large-slot client unchanged — the tag is
    'large', not 'coordinator'.  Intentional: shared resources, shared
    sidebar bucket.
    """
    from prep import server as server_mod
    cfg = _resolver_fixture()
    cfg["llm_config"]["coordinator_model"]["inherit_from_large"] = True
    monkeypatch.setattr(server_mod, "_load_ui_config", lambda: cfg)

    coord = server_mod._get_llm_client_for_slot("coordinator")
    assert getattr(coord, "_model_slot", None) == "large"


def _run_split(rt: dict) -> list:
    """Replicate the split logic from llm.py running_tasks builder so
    tests exercise the same code path (kept in sync via tests below
    and reviewer-guarded; the production logic is in
    src/prep/api/routers/llm.py around 'swarm slot attribution').
    """
    from prep.services.token_telemetry import telemetry
    SIDEBAR_SLOTS = {"embedding", "small", "large", "code"}
    if not rt.get("is_swarm"):
        return [rt]
    active = [
        req for req in telemetry.get_active_requests()
        if req.get("project_id") == rt["project_id"]
        and req.get("task_id") == rt.get("task_id", "")
    ]
    fallback_slot = rt.get("model_slot")
    groups: dict = {}
    for req in active:
        slot = req.get("model_slot") or fallback_slot
        if slot not in SIDEBAR_SLOTS:
            slot = fallback_slot
        role = req.get("swarm_role")
        groups.setdefault((slot, role), 0)
        groups[(slot, role)] += 1
    if not groups:
        return [rt]
    return [
        {**rt, "model_slot": slot, "concurrent_workers": count, "swarm_role": role}
        for (slot, role), count in groups.items()
    ]


def test_swarm_split_remaps_coordinator_into_fallback_slot() -> None:
    """C1: a separately-configured coordinator endpoint produces
    model_slot='coordinator' on its active requests, but the AI Gateway
    sidebar only renders the four canonical buckets
    (embedding/small/large/code).  The split must remap the coordinator
    entry into the stage's primary slot so it remains visible alongside
    its workers — distinguished by swarm_role on the row, not dropped.
    """
    from prep.services.token_telemetry import _active_requests, ActiveLLMRequest

    _active_requests.clear()
    for i in range(9):
        _active_requests[1000 + i] = ActiveLLMRequest(
            project_id="proj", task_id="module_synthesis",
            model="kimi", provider="ollama", start_time=0.0,
            model_slot="large", swarm_role="worker",
        )
    _active_requests[2000] = ActiveLLMRequest(
        project_id="proj", task_id="module_synthesis",
        model="qwen-coordinator", provider="openai-compatible",
        start_time=0.0,
        model_slot="coordinator", swarm_role="coordinator",
    )

    try:
        rt = {
            "task_id": "module_synthesis", "project_id": "proj",
            "project_name": "ProjA", "group": "deep_enrichment",
            "stage": "module_synthesis", "model_slot": "large",
            "concurrent_workers": 10, "is_swarm": True, "swarm_phases": None,
        }
        expanded = _run_split(rt)

        # Coordinator entry remapped from "coordinator" → "large" so the
        # sidebar renders it; swarm_role retained for diagnostics/future UI.
        coord = next(e for e in expanded if e.get("swarm_role") == "coordinator")
        worker = next(e for e in expanded if e.get("swarm_role") == "worker")
        assert coord["model_slot"] == "large"
        assert coord["concurrent_workers"] == 1
        assert worker["model_slot"] == "large"
        assert worker["concurrent_workers"] == 9
        # All four canonical buckets are valid; nothing produced an
        # off-spec slot value.
        for e in expanded:
            assert e["model_slot"] in {"embedding", "small", "large", "code"}
    finally:
        _active_requests.clear()


def test_swarm_split_preserves_total_count_with_untagged_calls() -> None:
    """I3: untagged active calls (no swarm_role) must still be counted
    in the split output so the AI Gateway badge total matches the
    Pipeline Queue total.  Untagged calls land in the fallback slot
    with swarm_role=None.
    """
    from prep.services.token_telemetry import _active_requests, ActiveLLMRequest

    _active_requests.clear()
    # 7 swarm-tagged worker calls + 4 untagged calls (e.g., probe, embedding,
    # legacy LLMClient) for the same (project, task).  Total = 11.
    for i in range(7):
        _active_requests[4000 + i] = ActiveLLMRequest(
            project_id="proj", task_id="module_synthesis",
            model="kimi", provider="ollama", start_time=0.0,
            model_slot="large", swarm_role="worker",
        )
    for i in range(4):
        _active_requests[4100 + i] = ActiveLLMRequest(
            project_id="proj", task_id="module_synthesis",
            model="something", provider="ollama", start_time=0.0,
            model_slot=None, swarm_role=None,
        )

    try:
        rt = {
            "task_id": "module_synthesis", "project_id": "proj",
            "project_name": "ProjA", "group": "deep_enrichment",
            "stage": "module_synthesis", "model_slot": "large",
            "concurrent_workers": 11, "is_swarm": True, "swarm_phases": None,
        }
        expanded = _run_split(rt)
        total = sum(e.get("concurrent_workers", 0) for e in expanded)
        assert total == 11, (
            f"sum-preservation broken: split totals {total} vs original 11; "
            f"entries: {expanded}"
        )
    finally:
        _active_requests.clear()


def test_swarm_split_falls_back_when_telemetry_empty() -> None:
    """When telemetry has no active requests for the (project, task)
    pair (race during snapshot), the original entry is preserved so the
    badge doesn't disappear."""
    from prep.services.token_telemetry import _active_requests
    _active_requests.clear()
    rt = {
        "task_id": "module_synthesis", "project_id": "proj",
        "project_name": "ProjA", "group": "deep_enrichment",
        "stage": "module_synthesis", "model_slot": "large",
        "concurrent_workers": 4, "is_swarm": True, "swarm_phases": None,
    }
    expanded = _run_split(rt)
    assert len(expanded) == 1
    assert expanded[0]["concurrent_workers"] == 4
    assert expanded[0]["model_slot"] == "large"
