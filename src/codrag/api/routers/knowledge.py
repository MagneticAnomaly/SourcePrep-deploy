"""
CoDRAG Knowledge Router — Phase 23 Sprint 12
===============================================

**Origin:** Extracted from ``server.py`` (lines ~3148–3253 in the original).

**Endpoints moved here:**
  - GET  /projects/{id}/knowledge/status — knowledge index status
  - POST /projects/{id}/knowledge/build  — trigger knowledge index build
  - GET  /projects/{id}/engine/status    — aggregated 7-stage pipeline status

**Shared state accessed (from server.py):**
  - ``_require_project``               — project lookup with 404
  - ``_get_project_knowledge_index``   — get/create per-project KnowledgeIndex
  - ``_is_project_knowledge_building`` — check if knowledge build thread alive
  - ``_start_project_knowledge_build`` — launch knowledge build in background
  - ``_get_project_trace_index``       — for engine status aggregation
  - ``_is_project_trace_building``     — for engine status aggregation
  - ``_get_project_index``             — for engine status (vector index)
  - ``_is_project_building``           — for engine status (vector building)
  - ``_project_augment_status``        — for engine status (catalogue stage)

**Phase 24 note (State Machines SM-4, SM-6):**
  The ``/engine/status`` endpoint is the single source of truth for the
  entire 7-stage enrichment pipeline.  When SM-6 (Pipeline Orchestrator)
  is implemented, this endpoint should read directly from the orchestrator's
  state rather than querying each stage independently.  SM-4 (Build
  Orchestrator) will own the knowledge build thread pool, replacing
  ``_start_project_knowledge_build`` with a proper ``start_build()``
  transition on the per-project BuildSlot.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

from codrag.api.envelope import ApiException, ok
from codrag.core.project_registry import project_index_dir

logger = logging.getLogger(__name__)

router = APIRouter(tags=["knowledge"])


# ── Knowledge Index ──────────────────────────────────────────────

@router.get("/projects/{project_id}/knowledge/status")
def knowledge_status_project(project_id: str) -> Dict[str, Any]:
    """Get knowledge index status."""
    from codrag.server import _require_project, _get_project_knowledge_index, _is_project_knowledge_building
    proj = _require_project(project_id)
    idx = _get_project_knowledge_index(proj)
    
    status = idx.status()
    is_building = _is_project_knowledge_building(project_id)
    status["building"] = is_building
    status["running"] = is_building  # Frontend expects 'running' field

    # Overlay pipeline build-slot progress for live progress bars
    if is_building:
        try:
            from codrag.services.build_orchestrator import build_orchestrator, BuildType, BuildPhase
            slot = build_orchestrator.status(project_id, BuildType.KNOWLEDGE)
            if slot.phase == BuildPhase.RUNNING and slot.progress_total > 0:
                status["progress_current"] = slot.progress_current
                status["progress_total"] = slot.progress_total
        except Exception:
            pass  # Non-fatal

    return ok(status)


@router.post("/projects/{project_id}/knowledge/build")
def build_knowledge_project(project_id: str) -> Dict[str, Any]:
    """Trigger knowledge index build."""
    from codrag.server import _require_project, _is_project_knowledge_building, _start_project_knowledge_build
    from codrag.services.project_helpers import is_over_project_limit
    
    if is_over_project_limit():
        raise ApiException(
            status_code=403,
            code="PROJECT_LIMIT_EXCEEDED",
            message="Cannot build knowledge index: Project limit exceeded for current tier",
            hint="Upgrade your plan or remove projects to resume syncing."
        )

    proj = _require_project(project_id)
    
    if _is_project_knowledge_building(project_id):
        raise ApiException(status_code=409, code="BUILD_ALREADY_RUNNING", message="Knowledge build already running")
        
    started = _start_project_knowledge_build(proj)
    if not started:
        raise ApiException(status_code=409, code="BUILD_ALREADY_RUNNING", message="Knowledge build already running")
        
    return ok({"started": True, "building": True})


# ── Unified Engine Status ────────────────────────────────────────

@router.get("/projects/{project_id}/engine/status")
def engine_status_project(project_id: str) -> Dict[str, Any]:
    """
    Aggregated status for the entire 7-stage Graph Engine pipeline.
    Used by the Unified Graph Engine Panel.
    """
    from codrag.server import (
        _require_project, _get_project_trace_index, _is_project_trace_building,
        _get_project_index, _is_project_building,
        _get_project_knowledge_index, _is_project_knowledge_building,
        _project_augment_status,
    )
    from codrag.api.routers.trace import (
        epistemic_status_project as _epistemic_status,
        modules_status_project as _cluster_status,
        deepening_status_project as _deepening_status,
    )

    proj = _require_project(project_id)
    idx_dir = project_index_dir(proj)
    
    # 1. Structural Trace
    trace_idx = _get_project_trace_index(proj)
    trace_status = {
        "enabled": bool((proj.config.get("trace") or {}).get("enabled", False)),
        "exists": trace_idx.exists(),
        "building": _is_project_trace_building(project_id),
        "stats": trace_idx.node_count() if trace_idx.exists() and trace_idx.load() else 0
    }

    # 2. Vector Index (Source)
    source_idx = _get_project_index(proj)
    source_status = source_idx.stats()
    source_status["building"] = _is_project_building(project_id)

    # 3. Fast Catalogue (Augmentation)
    augment_status = _project_augment_status(proj)

    # 4. Relationship Validation (Inferred Edges)
    inferred_edges = 0
    try:
        inferred_path = idx_dir / "trace_inferred_edges.jsonl"
        if inferred_path.exists():
            with open(inferred_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        inferred_edges += 1
    except Exception:
        inferred_edges = 0
    validation_status = {
        "enabled": True,
        "inferred_edges": inferred_edges,
        "validated_edges": inferred_edges,
    }

    # 5. Epistemic Enrichment
    epistemic_status = _epistemic_status(project_id)["data"]

    # 6. Cluster Synthesis
    cluster_status = _cluster_status(project_id)["data"]

    # 7. Knowledge Embedding
    know_idx = _get_project_knowledge_index(proj)
    knowledge_status = know_idx.status()
    is_know_building = _is_project_knowledge_building(project_id)
    knowledge_status["building"] = is_know_building
    knowledge_status["running"] = is_know_building

    # Deepening Loop (Cross-cutting)
    deepening_status = _deepening_status(project_id)["data"]

    return ok({
        "stages": {
            "trace": trace_status,
            "vector": source_status,
            "catalogue": augment_status,
            "validation": validation_status,
            "epistemic": epistemic_status,
            "clustering": cluster_status,
            "knowledge": knowledge_status
        },
        "deepening": deepening_status,
        "global_running": (
            trace_status["building"] or 
            source_status["building"] or 
            epistemic_status["running"] or 
            cluster_status["running"] or 
            knowledge_status["building"] or
            deepening_status["running"]
        )
    })
