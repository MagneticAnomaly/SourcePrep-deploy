"""
CoDRAG Pipeline Router — Phase 24 (SM-6) + Phase 25 (Crash Protection)
=======================================================================

Exposes the 8-stage pipeline orchestrator via HTTP endpoints.

**Endpoints:**
  - POST /projects/{id}/pipeline/fast     — run Fast Sync (stages 1-4)
  - POST /projects/{id}/pipeline/deep     — run Deep Enrichment (stages 5-8)
  - POST /projects/{id}/pipeline/all      — run all stages (fast → deep)
  - GET  /projects/{id}/pipeline/status   — pipeline status (8-stage, two-group)
  - POST /projects/{id}/pipeline/cancel   — cancel a running group
  - GET  /pipeline/crashed                — all crashed runs (Phase 25)
  - POST /pipeline/resume                 — resume a crashed run (Phase 25)
  - POST /pipeline/discard                — discard a crashed run (Phase 25)

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
from codrag.core.project_registry import project_index_dir

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"])


# ── Request models ───────────────────────────────────────────────

class CancelRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync" or "deep_enrichment"


class PauseRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync" or "deep_enrichment"


class ResumeGroupRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync" or "deep_enrichment"


class SwapModelRequest(BaseModel):
    group: str = "deep_enrichment"  # "fast_sync" or "deep_enrichment"


class ResumeRequest(BaseModel):
    run_id: str


class DiscardRequest(BaseModel):
    run_id: str


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/projects/{project_id}/pipeline/fast")
def pipeline_run_fast(project_id: str) -> Dict[str, Any]:
    """Run Fast Sync (stages 1-4): Structural → Catalogue → Validation → Knowledge Embedding."""
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

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
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

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
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

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
    """Get the full 11-stage pipeline status (two-group model).

    Returns both group-level run status and per-stage build slot status.
    Also includes legacy per-stage data fetched from existing sources
    for backward compatibility with the current UI.
    """
    from codrag.server import _require_project
    from codrag.services.build_manager import build_manager
    from codrag.api.routers.trace_routes.enrichment import (
        augment_status_project as _augment_status,
        epistemic_status_project as _epistemic_status,
        modules_status_project as _cluster_status,
        deepening_status_project as _deepening_status,
    )

    proj = _require_project(project_id)
    idx_dir = project_index_dir(proj)

    # 1. Structural trace
    trace_idx = build_manager.get_project_trace_index(proj)
    trace_status = {
        "enabled": bool((proj.config.get("trace") or {}).get("enabled", False)),
        "exists": trace_idx.exists(),
        "building": build_manager.is_project_trace_building(project_id),
        "stats": trace_idx.node_count() if trace_idx.exists() and trace_idx.load() else 0,
    }

    # 2. Inferred Edges (code model)
    inferred_edges_count = 0
    try:
        inferred_path = idx_dir / "trace_inferred_edges.jsonl"
        if inferred_path.exists():
            with open(inferred_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        inferred_edges_count += 1
    except Exception:
        inferred_edges_count = 0
    inferred_edges_status = {
        "enabled": True,
        "exists": inferred_edges_count > 0,
        "edge_count": inferred_edges_count,
    }

    # 3. Fast Catalogue (augmentation)
    augment_status = _augment_status(project_id)["data"]

    # 4. Validation (pass-through for now)
    validation_status = {
        "enabled": True,
        "inferred_edges": inferred_edges_count,
        "validated_edges": inferred_edges_count,
    }

    # 4 + 8. Knowledge embedding
    know_idx = build_manager.get_project_knowledge_index(proj)
    knowledge_status = know_idx.status()
    is_know_building = build_manager.is_project_knowledge_building(project_id)
    knowledge_status["building"] = is_know_building
    knowledge_status["running"] = is_know_building

    # Phase 48 (P48-F4): Create separate deep_knowledge_status.
    # Stage 11 reuses the same KnowledgeIndex but we need to distinguish
    # whether it ran after deep enrichment (with richer data) or not.
    deep_knowledge_status = dict(knowledge_status)  # Shallow copy
    deepening_path = idx_dir / "trace_epistemic.jsonl"
    modules_path = idx_dir / "trace_modules.jsonl"
    deep_has_run = (
        deepening_path.exists() and deepening_path.stat().st_size > 0 and
        modules_path.exists() and modules_path.stat().st_size > 0
    )
    deep_knowledge_status["deep_chunks_embedded"] = (
        knowledge_status.get("chunks_embedded", 0) if deep_has_run else 0
    )

    # 5. Epistemic enrichment
    epistemic_status = _epistemic_status(project_id)["data"]

    # 6. Cluster synthesis
    cluster_status = _cluster_status(project_id)["data"]

    # 7. Deepening
    deepening_status = _deepening_status(project_id)["data"]

    atlas_status: Dict[str, Any]
    try:
        from codrag.core.atlas import CodebaseAtlas
        atlas = CodebaseAtlas(idx_dir)
        doc = atlas.load()
        if doc is None:
            atlas_status = {
                "exists": False,
                "mode": None,
                "model": None,
                "generated_at": None,
                "file_count": 0,
                "module_count": 0,
                "char_count": 0,
                "stale": True,
                "segmented": False,
                "routing": atlas.has_routing(),
            }
        else:
            atlas_status = {
                "exists": True,
                "mode": doc.mode,
                "model": doc.model,
                "generated_at": doc.generated_at,
                "file_count": doc.file_count,
                "module_count": doc.module_count,
                "char_count": doc.char_count,
                "stale": atlas.is_stale(),
                "segmented": atlas.has_segments(),
                "routing": atlas.has_routing(),
            }
    except Exception:
        atlas_status = {
            "exists": False,
            "mode": None,
            "model": None,
            "generated_at": None,
            "file_count": 0,
            "module_count": 0,
            "char_count": 0,
            "stale": True,
            "segmented": False,
            "routing": False,
        }

    # Pipeline orchestrator group-level status
    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    pipeline_state = pipeline_orchestrator.status(project_id)

    # Merge live build-slot progress into each stage's data so the UI
    # can show progress bars that update during long-running stages.
    slot_stages = pipeline_state.get("stages") or {}
    # Group reasoning status
    group_reasoning_status: Dict[str, Any] = {"enabled": False, "group_count": 0, "analyzed": 0}
    try:
        gr_path = idx_dir / "trace_group_reasoning.jsonl"
        if gr_path.exists():
            gr_count = 0
            with open(gr_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        gr_count += 1
            group_reasoning_status = {"enabled": True, "group_count": gr_count, "analyzed": gr_count}
    except Exception:
        pass

    stage_data = {
        "structural": trace_status,
        "inferred_edges": inferred_edges_status,
        "catalogue": augment_status,
        "validation": validation_status,
        "knowledge": knowledge_status,
        "enrichment": epistemic_status,
        "group_reasoning": group_reasoning_status,
        "clustering": cluster_status,
        "atlas": atlas_status,
        "deepening": deepening_status,
        "deep_knowledge": deep_knowledge_status,  # Separate status with deep_chunks_embedded field
    }
    for stage_key, slot_info in slot_stages.items():
        if stage_key in stage_data and isinstance(slot_info, dict):
            slot_progress = slot_info.get("progress")
            if slot_progress:
                stage_data[stage_key]["slot_progress"] = slot_progress
                # Flatten into top-level keys so the UI can read progress_current/progress_total directly
                stage_data[stage_key]["progress_current"] = slot_progress.get("current", 0)
                stage_data[stage_key]["progress_total"] = slot_progress.get("total", 0)
            if slot_info.get("phase"):
                stage_data[stage_key]["slot_phase"] = slot_info["phase"]

    # Phase 25: include crashed runs so the UI can show recovery banner
    crashed_runs = pipeline_orchestrator.get_crashed_runs(project_id)

    # Phase 45D: include scheduler status so the UI can show queue state
    scheduler_data = None
    try:
        from codrag.services.pipeline.scheduler import pipeline_scheduler
        scheduler_data = pipeline_scheduler.status()
    except Exception:
        pass

    return ok({
        "fast_sync": pipeline_state.get("fast_sync"),
        "deep_enrichment": pipeline_state.get("deep_enrichment"),
        "stages": stage_data,
        "any_running": pipeline_state.get("any_running", False),
        "crashed_runs": crashed_runs,
        "scheduler": scheduler_data,
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


@router.post("/projects/{project_id}/pipeline/pause")
def pipeline_pause(project_id: str, req: PauseRequest) -> Dict[str, Any]:
    """Pause a running pipeline group.

    The current stage flushes partial results to disk before stopping.
    Resume with POST /projects/{project_id}/pipeline/resume.
    """
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator

    if req.group == "fast_sync":
        paused = pipeline_orchestrator.pause_fast_sync(project_id)
    elif req.group == "deep_enrichment":
        paused = pipeline_orchestrator.pause_deep_enrichment(project_id)
    else:
        raise ApiException(
            status_code=400,
            code="INVALID_GROUP",
            message=f"Unknown group: {req.group}. Must be 'fast_sync' or 'deep_enrichment'.",
        )

    if not paused:
        raise ApiException(
            status_code=409,
            code="NOT_RUNNING",
            message=f"{req.group} is not currently running",
        )

    return ok({"paused": True, "group": req.group})


@router.post("/projects/{project_id}/pipeline/resume")
def pipeline_resume_group(project_id: str, req: ResumeGroupRequest) -> Dict[str, Any]:
    """Resume a paused pipeline group from where it left off.

    Incremental stages skip already-processed items, so resuming
    effectively continues from the exact point of the pause.
    """
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator

    resumed = pipeline_orchestrator.resume_paused(project_id, req.group)
    if not resumed:
        raise ApiException(
            status_code=409,
            code="NOT_PAUSED",
            message=f"{req.group} is not in a paused state",
        )

    return ok({"resumed": True, "group": req.group})


@router.post("/projects/{project_id}/pipeline/swap-model")
def pipeline_swap_model(project_id: str, req: SwapModelRequest) -> Dict[str, Any]:
    """Swap the LLM model mid-pipeline without losing progress.

    Pauses the current stage (flushing partial results), then immediately
    resumes.  The resumed stage re-reads LLM config, picking up any model
    or endpoint changes the user just made.  Incremental workers skip
    already-processed items, so no work is lost.
    """
    from codrag.server import _require_project
    _require_project(project_id)

    if req.group not in ("fast_sync", "deep_enrichment"):
        raise ApiException(
            status_code=400,
            code="INVALID_GROUP",
            message=f"Unknown group: {req.group}. Must be 'fast_sync' or 'deep_enrichment'.",
        )

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    result = pipeline_orchestrator.swap_model(project_id, req.group)

    if not result.get("swapped"):
        reason = result.get("reason", "unknown")
        raise ApiException(
            status_code=409,
            code="SWAP_FAILED",
            message=f"Could not swap model for {req.group}: {reason}",
        )

    return ok(result)


@router.post("/projects/{project_id}/pipeline/force-reset")
def pipeline_force_reset(project_id: str) -> Dict[str, Any]:
    """Force-reset any pipeline runs stuck in 'running' for >10 minutes.

    This is a recovery mechanism for when a worker finishes but the
    completion callback doesn't fire.  Safe to call anytime — no-ops
    if nothing is stuck.
    """
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    reset = pipeline_orchestrator.force_reset_stale_runs(project_id)

    return ok({"reset_groups": reset, "count": len(reset)})


# ── Phase 25: Crash Protection Endpoints ──────────────────────────────────

@router.get("/pipeline/crashed")
def pipeline_crashed_runs(project_id: Optional[str] = None) -> Dict[str, Any]:
    """Get all crashed pipeline runs, optionally filtered by project.

    Returns a list of crashed runs with enough info for the UI to
    offer Resume / Discard buttons.
    """
    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    runs = pipeline_orchestrator.get_crashed_runs(project_id)
    return ok({"crashed_runs": runs, "count": len(runs)})


@router.post("/pipeline/resume")
def pipeline_resume(req: ResumeRequest) -> Dict[str, Any]:
    """Resume a crashed pipeline run from where it left off."""
    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    resumed = pipeline_orchestrator.resume_crashed_run(req.run_id)
    if not resumed:
        raise ApiException(
            status_code=404,
            code="RUN_NOT_FOUND",
            message=f"No crashed run found with ID: {req.run_id}",
        )
    return ok({"resumed": True, "run_id": req.run_id})


@router.post("/pipeline/discard")
def pipeline_discard(req: DiscardRequest) -> Dict[str, Any]:
    """Discard a crashed pipeline run without resuming."""
    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    discarded = pipeline_orchestrator.discard_crashed_run(req.run_id)
    if not discarded:
        raise ApiException(
            status_code=404,
            code="RUN_NOT_FOUND",
            message=f"No crashed run found with ID: {req.run_id}",
        )
    return ok({"discarded": True, "run_id": req.run_id})


# ── Phase 26: Budget Usage Endpoint ──────────────────────────────

@router.get("/projects/{project_id}/pipeline/budget")
def pipeline_budget_usage(project_id: str) -> Dict[str, Any]:
    """Get current token budget usage for a project's deep enrichment."""
    from codrag.server import _require_project
    _require_project(project_id)

    try:
        from codrag.services.pipeline_budget import budget
        usage = budget.get_usage(project_id)
    except Exception:
        usage = {
            "tokens_used": 0,
            "max_tokens": 0,
            "window_minutes": 5,
            "remaining": -1,
            "window_resets_in": 0,
        }
    return ok(usage)
