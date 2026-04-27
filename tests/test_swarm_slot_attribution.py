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


def test_resolver_tags_model_slot_on_llm_client(monkeypatch) -> None:
    """``_get_llm_client_for_slot`` must stamp ``_model_slot`` on every
    LLMClient it returns, so token telemetry can group active calls
    correctly across coordinator/worker/synthesizer phases.
    """
    from prep import server as server_mod

    fake_cfg = {
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
            "saved_endpoints": [
                {"id": "ep-small", "url": "http://x", "provider": "ollama"},
                {"id": "ep-large", "url": "http://x", "provider": "ollama"},
                {"id": "ep-code", "url": "http://x", "provider": "ollama"},
            ],
        },
    }
    monkeypatch.setattr(server_mod, "_load_ui_config", lambda: fake_cfg)

    small = server_mod._get_llm_client_for_slot("small")
    large = server_mod._get_llm_client_for_slot("large")
    code = server_mod._get_llm_client_for_slot("code")

    assert getattr(small, "_model_slot", None) == "small"
    assert getattr(large, "_model_slot", None) == "large"
    assert getattr(code, "_model_slot", None) == "code"


def test_swarm_split_groups_by_slot_and_role(monkeypatch) -> None:
    """Inline-test the split logic: ``running_tasks`` post-processing
    replaces a single is_swarm entry with one entry per
    (model_slot, swarm_role) seen in active telemetry.
    """
    from prep.services.token_telemetry import telemetry, _active_requests
    from prep.services.token_telemetry import ActiveLLMRequest

    # Prime active telemetry: 1 coordinator on small, 9 workers on large.
    _active_requests.clear()
    for i in range(9):
        _active_requests[1000 + i] = ActiveLLMRequest(
            project_id="proj",
            task_id="module_synthesis",
            model="kimi",
            provider="ollama",
            start_time=0.0,
            model_slot="large",
            swarm_role="worker",
        )
    _active_requests[2000] = ActiveLLMRequest(
        project_id="proj",
        task_id="module_synthesis",
        model="qwen-coordinator",
        provider="openai",
        start_time=0.0,
        model_slot="coordinator",
        swarm_role="coordinator",
    )

    try:
        # Replicate the split logic from llm.py running_tasks builder.
        rt = {
            "task_id": "module_synthesis",
            "project_id": "proj",
            "project_name": "ProjA",
            "group": "deep_enrichment",
            "stage": "module_synthesis",
            "model_slot": "large",
            "concurrent_workers": 10,
            "is_swarm": True,
            "swarm_phases": None,
        }
        running_tasks = [rt]
        expanded = []
        for r in running_tasks:
            if not r.get("is_swarm"):
                expanded.append(r)
                continue
            active = [
                req for req in telemetry.get_active_requests()
                if req.get("project_id") == r["project_id"]
                and req.get("task_id") == r.get("task_id", "")
                and req.get("swarm_role") in ("coordinator", "worker", "synthesizer")
            ]
            groups: dict = {}
            fallback_slot = r.get("model_slot")
            for req in active:
                slot = req.get("model_slot") or fallback_slot
                role = req.get("swarm_role")
                groups.setdefault((slot, role), 0)
                groups[(slot, role)] += 1
            if not groups:
                expanded.append(r)
                continue
            for (slot, role), count in groups.items():
                expanded.append({
                    **r,
                    "model_slot": slot,
                    "concurrent_workers": count,
                    "swarm_role": role,
                })

        worker_entry = next(
            e for e in expanded if e.get("swarm_role") == "worker"
        )
        coord_entry = next(
            e for e in expanded if e.get("swarm_role") == "coordinator"
        )
        assert worker_entry["model_slot"] == "large"
        assert worker_entry["concurrent_workers"] == 9
        assert coord_entry["model_slot"] == "coordinator"
        assert coord_entry["concurrent_workers"] == 1
    finally:
        _active_requests.clear()


def test_swarm_split_falls_back_when_telemetry_untagged(monkeypatch) -> None:
    """When live telemetry has no ``model_slot`` (legacy LLMClient
    instances pre-Phase-119-tag), the split uses the stage's primary
    slot as the fallback so the entry remains visible in the UI."""
    from prep.services.token_telemetry import telemetry, _active_requests
    from prep.services.token_telemetry import ActiveLLMRequest

    _active_requests.clear()
    for i in range(4):
        _active_requests[3000 + i] = ActiveLLMRequest(
            project_id="proj",
            task_id="module_synthesis",
            model="legacy-model",
            provider="ollama",
            start_time=0.0,
            model_slot=None,
            swarm_role="worker",
        )
    try:
        rt = {
            "task_id": "module_synthesis",
            "project_id": "proj",
            "project_name": "ProjA",
            "group": "deep_enrichment",
            "stage": "module_synthesis",
            "model_slot": "large",
            "concurrent_workers": 4,
            "is_swarm": True,
            "swarm_phases": None,
        }
        groups: dict = {}
        fallback_slot = rt["model_slot"]
        for req in telemetry.get_active_requests():
            if req.get("swarm_role") not in ("coordinator", "worker", "synthesizer"):
                continue
            slot = req.get("model_slot") or fallback_slot
            role = req.get("swarm_role")
            groups.setdefault((slot, role), 0)
            groups[(slot, role)] += 1
        # All 4 untagged worker calls fall back to large.
        assert groups[("large", "worker")] == 4
    finally:
        _active_requests.clear()
