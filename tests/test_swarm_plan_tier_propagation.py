"""Phase 112 Fix 6: verify plan-tier concurrency is not silently capped.

Prior to this fix, atlas/generator.py, group_reasoning.py, and
concept_seeder.py each had an F-59-era hardcoded ceiling of 3 on top of
the plan-tier-aware budget returned by
``scheduler.full_budget_for_swarm()`` / ``batch_profiles.get_batch_concurrency()``.

F-59 (daemon hang from timeout misconfig) was resolved 2026-04-12 — the
real limit is the Ollama Cloud plan tier.  Max-plan users should get
concurrency=10, not a silently capped 3.

These tests pin the propagation: scheduler says 10 → swarm orchestrator
receives 10.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# group_reasoning
# ---------------------------------------------------------------------------


def _make_epistemic_line(node_id: str) -> str:
    return json.dumps({
        "node_id": node_id,
        "extended_summary": f"Summary for {node_id}",
        "architecture_layer": "service",
        "domain_tags": ["core"],
        "tech_debt": [],
        "epistemic_confidence": 0.8,
        "model": "test-model",
        "enriched_at": "2026-01-01T00:00:00Z",
    })


def _make_edge_line(source: str, target: str) -> str:
    return json.dumps({"source": source, "target": target, "kind": "import"})


@pytest.fixture()
def group_reasoning_index(tmp_path: Path) -> Path:
    """Four groups of three files, enough to trigger the swarm path."""
    epistemic_lines = []
    edge_lines = []
    for g in range(4):
        files = [f"file:mod{g}/f{i}.py" for i in range(3)]
        for f in files:
            epistemic_lines.append(_make_epistemic_line(f))
        edge_lines.append(_make_edge_line(files[0], files[1]))
        edge_lines.append(_make_edge_line(files[1], files[2]))
    (tmp_path / "trace_epistemic.jsonl").write_text(
        "\n".join(epistemic_lines) + "\n", encoding="utf-8",
    )
    (tmp_path / "trace_edges.jsonl").write_text(
        "\n".join(edge_lines) + "\n", encoding="utf-8",
    )
    return tmp_path


def test_group_reasoning_preserves_max_plan_concurrency(group_reasoning_index):
    """GroupReasoningEngine must not cap a scheduler-reported 10 down to 3."""
    from prep.core.group_reasoning import GroupReasoningEngine

    llm = MagicMock()
    llm.provider = "ollama"
    llm.model = "gpt-oss:120b-cloud"  # cloud-proxied — formerly triggered the cap
    engine = GroupReasoningEngine(llm=llm, index_dir=group_reasoning_index)

    captured: dict = {}

    class _StubOrchestrator:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self, items, coordinator_prompt, worker_prompt, synthesis_prompt):
            return MagicMock(worker_results={}, success=True, coordinator_tokens=0,
                             worker_tokens=0, synthesis_tokens=0)

    with patch("prep.core.group_reasoning.SwarmOrchestrator", _StubOrchestrator), \
         patch("prep.core.llm_client._is_cloud_endpoint", return_value=True), \
         patch(
             "prep.services.pipeline.scheduler.pipeline_scheduler.full_budget_for_swarm",
             return_value=10,
         ), \
         patch(
             "prep.core.group_reasoning.WorkerFactory._get_coordinator_llm_client",
             return_value=MagicMock(),
         ):
        # Build minimal epistemic/edges dict for the 3 groups.
        from prep.core.group_reasoning import EpistemicEntry

        epistemic: dict = {}
        for gid in ("g1", "g2", "g3"):
            for mem in ("a", "b", "c"):
                node_id = f"{gid}:{mem}"
                epistemic[node_id] = EpistemicEntry(
                    node_id=node_id,
                    extended_summary=f"sum {node_id}",
                    architecture_layer="service",
                    domain_tags=["core"],
                    tech_debt=[],
                    epistemic_confidence=0.8,
                )
        edges: list = []

        try:
            engine._run_swarm(
                [("g1", ["g1:a", "g1:b"]),
                 ("g2", ["g2:a", "g2:b"]),
                 ("g3", ["g3:a", "g3:b"])],
                epistemic,
                edges,
            )
        except Exception:
            pass

    assert captured.get("concurrency") == 10, (
        f"Expected concurrency=10 (Max plan), got {captured.get('concurrency')}. "
        "A hardcoded cap has been reintroduced at the call site."
    )


# ---------------------------------------------------------------------------
# concept_seeder
# ---------------------------------------------------------------------------


def test_concept_seeder_preserves_max_plan_concurrency(tmp_path):
    """seed_concepts_swarm must not cap scheduler-reported 10 down to 3."""
    from prep.core import concept_seeder as cs

    llm = MagicMock()
    llm.provider = "ollama"
    llm.model = "gpt-oss:120b-cloud"

    modules = [
        {"module_id": f"m{i}", "name": f"m{i}", "file_count": 5,
         "member_files": [f"src/m{i}/f.py"], "summary": "test", "domain_tags": [],
         "internal_dependencies": [], "external_dependencies": []}
        for i in range(5)
    ]

    captured: dict = {}

    class _StubOrchestrator:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self, items, coordinator_prompt, worker_prompt, synthesis_prompt):
            return MagicMock(worker_results={}, success=True, coordinator_tokens=0,
                             worker_tokens=0, synthesis_tokens=0)

    # concept_seeder imports SwarmOrchestrator *inside* seed_concepts_swarm,
    # so patch at its source module — the local `from` will pick up the stub.
    with patch("prep.core.swarm_orchestrator.SwarmOrchestrator", _StubOrchestrator), \
         patch.object(cs, "_load_modules_for_swarm", return_value=modules), \
         patch("prep.core.llm_client._is_cloud_endpoint", return_value=True), \
         patch.object(cs, "_get_seeder_llm", return_value=llm), \
         patch(
             "prep.services.pipeline.scheduler.pipeline_scheduler.full_budget_for_swarm",
             return_value=10,
         ), \
         patch(
             "prep.services.pipeline.scheduler.is_swarm_active_for_stage",
             return_value=True,
         ), \
         patch(
             "prep.services.pipeline.workers.WorkerFactory._get_coordinator_llm_client",
             return_value=MagicMock(),
         ), \
         patch(
             "prep.services.project_helpers.require_project",
             return_value=MagicMock(id="proj-1"),
         ), \
         patch(
             "prep.core.project_registry.project_index_dir",
             return_value=tmp_path,
         ):
        try:
            cs.seed_concepts_swarm("proj-1")
        except Exception:
            # Downstream persistence may fail in a stub — we only need the
            # orchestrator constructor to fire with the right concurrency.
            pass

    assert captured.get("concurrency") == 10, (
        f"Expected concurrency=10 (Max plan), got {captured.get('concurrency')}. "
        "A hardcoded cap has been reintroduced in concept_seeder."
    )


# ---------------------------------------------------------------------------
# atlas/generator
# ---------------------------------------------------------------------------


def test_atlas_generator_preserves_max_plan_concurrency():
    """CodebaseAtlas._run_swarm must not cap scheduler-reported 10 down to 3.

    Focused unit: we don't need to run a full atlas build — we only want to
    prove that concurrency=10 reaches the SwarmOrchestrator constructor.
    """
    from prep.core.atlas.generator import CodebaseAtlas

    llm = MagicMock()
    llm.provider = "ollama"
    llm.model = "gpt-oss:120b-cloud"

    captured: dict = {}

    class _StubOrchestrator:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self, items, coordinator_prompt, worker_prompt, synthesis_prompt):
            return MagicMock(worker_results={}, success=True, coordinator_tokens=0,
                             worker_tokens=0, synthesis_tokens=0)

    # Build a minimal CodebaseAtlas — we patch enough to short-circuit
    # everything except the concurrency-selection path in _run_swarm.
    atlas = CodebaseAtlas.__new__(CodebaseAtlas)
    atlas.llm = llm
    atlas.index_dir = Path(".")
    atlas.project_id = "proj-1"

    segments: list = [MagicMock(id=f"s{i}", name=f"seg{i}") for i in range(3)]

    with patch("prep.core.atlas.generator.SwarmOrchestrator", _StubOrchestrator), \
         patch("prep.core.atlas.generator._is_cloud_endpoint", return_value=True), \
         patch(
             "prep.services.pipeline.scheduler.pipeline_scheduler.full_budget_for_swarm",
             return_value=10,
         ), \
         patch(
             "prep.core.atlas.generator.WorkerFactory._get_coordinator_llm_client",
             return_value=MagicMock(),
         ):
        try:
            atlas._run_swarm(
                segments=segments,
                all_modules=[],
                epistemic={},
                graph_stats={},
                hub_files=[],
                progress_callback=None,
            )
        except Exception:
            # Don't care about downstream segment-assembly errors — we only
            # need the orchestrator constructor to fire with concurrency.
            pass

    assert captured.get("concurrency") == 10, (
        f"Expected concurrency=10 (Max plan), got {captured.get('concurrency')}. "
        "A hardcoded cap has been reintroduced in atlas/generator."
    )
