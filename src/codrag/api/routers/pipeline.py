"""
CoDRAG Pipeline Router — Phase 24 (SM-6)
==========================================

Exposes the 8-stage pipeline orchestrator via HTTP endpoints.

**Endpoints:**
  - POST /projects/{id}/pipeline/fast     — run Fast Sync (stages 1-4)
  - POST /projects/{id}/pipeline/deep     — run Deep Enrichment (stages 5-8)
  - POST /projects/{id}/pipeline/all      — run all stages (fast → deep)
  - GET  /projects/{id}/pipeline/status   — pipeline status (8-stage, two-group)
  - POST /projects/{id}/pipeline/cancel   — cancel a running group

**Replaces:**
  The old ``/engine/status`` endpoint (7-stage model) with the new 8-stage,
  two-group model that matches the UI's ``GraphEnrichmentPipeline.tsx``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"])


# ── Request models ───────────────────────────────────────────────

class CancelRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync" or "deep_enrichment"


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/projects/{project_id}/pipeline/fast")
def pipeline_run_fast(project_id: str) -> Dict[str, Any]:
    """Run Fast Sync (stages 1-4): Structural → Catalogue → Validation → Knowledge Embedding."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_fast_sync(project_id)

    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_ALREADY_RUNNING",
            message="Fast Sync is already running for this project",
        )

    return ok({"started": True, "group": "fast_sync"})


@router.post("/projects/{project_id}/pipeline/deep")
def pipeline_run_deep(project_id: str) -> Dict[str, Any]:
    """Run Deep Enrichment (stages 5-8): Epistemic → Clustering → Deepening → Deep Knowledge."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_deep_enrichment(project_id)

    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_ALREADY_RUNNING",
            message="Deep Enrichment is already running for this project",
        )

    return ok({"started": True, "group": "deep_enrichment"})


@router.post("/projects/{project_id}/pipeline/all")
def pipeline_run_all(project_id: str) -> Dict[str, Any]:
    """Run all stages: Fast Sync (1-4) then Deep Enrichment (5-8)."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_all(project_id)

    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_ALREADY_RUNNING",
            message="Pipeline is already running for this project",
        )

    return ok({"started": True, "group": "all"})


@router.get("/projects/{project_id}/pipeline/status")
def pipeline_status(project_id: str) -> Dict[str, Any]:
    """Get the full 8-stage pipeline status (two-group model).

    Returns both group-level run status and per-stage build slot status.
    Also includes legacy per-stage data fetched from existing sources
    for backward compatibility with the current UI.
    """
    from codrag.server import _require_project
    from codrag.services.build_manager import build_manager
    from codrag.api.routers.trace import (
        augment_status_project as _augment_status,
        epistemic_status_project as _epistemic_status,
        modules_status_project as _cluster_status,
        deepening_status_project as _deepening_status,
    )

    proj = _require_project(project_id)

    # 1. Structural trace
    trace_idx = build_manager.get_project_trace_index(proj)
    trace_status = {
        "enabled": bool((proj.config.get("trace") or {}).get("enabled", False)),
        "exists": trace_idx.exists(),
        "building": build_manager.is_project_trace_building(project_id),
        "stats": trace_idx.node_count() if trace_idx.exists() and trace_idx.load() else 0,
    }

    # 2. Fast Catalogue (augmentation)
    augment_status = _augment_status(project_id)["data"]

    # 3. Validation (pass-through for now)
    validation_status = {
        "enabled": True,
        "inferred_edges": 0,
        "validated_edges": 0,
    }

    # 4 + 8. Knowledge embedding (shared by stage 4 and stage 8)
    know_idx = build_manager.get_project_knowledge_index(proj)
    knowledge_status = know_idx.status()
    knowledge_status["building"] = build_manager.is_project_knowledge_building(project_id)

    # 5. Epistemic enrichment
    epistemic_status = _epistemic_status(project_id)["data"]

    # 6. Cluster synthesis
    cluster_status = _cluster_status(project_id)["data"]

    # 7. Deepening
    deepening_status = _deepening_status(project_id)["data"]

    # Pipeline orchestrator group-level status
    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    pipeline_state = pipeline_orchestrator.status(project_id)

    return ok({
        "fast_sync": pipeline_state.get("fast_sync"),
        "deep_enrichment": pipeline_state.get("deep_enrichment"),
        "stages": {
            "structural": trace_status,
            "catalogue": augment_status,
            "validation": validation_status,
            "knowledge": knowledge_status,
            "enrichment": epistemic_status,
            "clustering": cluster_status,
            "deepening": deepening_status,
            "deep_knowledge": knowledge_status,  # Same index, re-built with richer data
        },
        "any_running": pipeline_state.get("any_running", False),
    })


@router.post("/projects/{project_id}/pipeline/cancel")
def pipeline_cancel(project_id: str, req: CancelRequest) -> Dict[str, Any]:
    """Cancel a running pipeline group."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator

    if req.group == "fast_sync":
        cancelled = pipeline_orchestrator.cancel_fast_sync(project_id)
    elif req.group == "deep_enrichment":
        cancelled = pipeline_orchestrator.cancel_deep_enrichment(project_id)
    else:
        raise ApiException(
            status_code=400,
            code="INVALID_GROUP",
            message=f"Unknown group: {req.group}. Must be 'fast_sync' or 'deep_enrichment'.",
        )

    if not cancelled:
        raise ApiException(
            status_code=409,
            code="NOT_RUNNING",
            message=f"{req.group} is not currently running",
        )

    return ok({"cancelled": True, "group": req.group})
