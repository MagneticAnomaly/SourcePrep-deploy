"""
CoDRAG Pipeline Router — Phase 24 (SM-6) + Phase 25 (Crash Protection) + Phase 76 (Rebuild) + Phase 96 (3×5)
=============================================================================================================

Exposes the 15-stage pipeline orchestrator via HTTP endpoints.

**Endpoints:**
  - POST /projects/{id}/pipeline/fast      — run Fast Sync (stages 1-5)
  - POST /projects/{id}/pipeline/deep      — run Deep Enrichment (stages 6-10)
  - POST /projects/{id}/pipeline/finalize  — run Finalize (stages 11-15)
  - POST /projects/{id}/pipeline/all       — run all stages (fast → deep → finalize)
  - POST /projects/{id}/pipeline/rebuild   — rebuild all stages from scratch (Phase 76)
  - GET  /projects/{id}/pipeline/status    — pipeline status (15-stage, three-group)
  - POST /projects/{id}/pipeline/cancel    — cancel a running group
  - GET  /pipeline/crashed                 — all crashed runs (Phase 25)
  - POST /pipeline/resume                  — resume a crashed run (Phase 25)
  - POST /pipeline/discard                 — discard a crashed run (Phase 25)

**Replaces:**
  The old ``/engine/status`` endpoint (7-stage model) with the new 15-stage,
  three-group model that matches the UI's ``GraphEnrichmentPipeline.tsx``.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok
from codrag.core.project_registry import project_index_dir

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"])

# Phase 60D-3: Dedicated thread pool for status endpoints.
# The default thread pool gets exhausted by long-running LLM workers
# (30+ minutes each), leaving no threads for status endpoints.
# This 4-thread pool ensures status & coverage endpoints can always respond.
_status_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pipeline-status")

# F-57: Per-project result cache for _build_status.
#
# _build_status reads multiple files from disk (trace_nodes.jsonl,
# augmentation manifests, knowledge documents, etc.) on every call.
# When the dashboard toggles between N projects, it fires N parallel
# /pipeline/status requests, each doing its own disk reads. On the
# USB drive the I/O contention with concurrent swarm LLM workers
# saturates the drive and all 4 _status_executor threads block.
#
# Fix: cache the result per project_id with a 2s TTL. The data is
# already somewhat stale (manifests are only written at stage
# transitions), so serving a 2s-stale cache is fine for the dashboard.
import threading as _threading
import time as _time

_status_cache: dict[str, tuple[float, dict]] = {}
_status_cache_lock = _threading.Lock()
_STATUS_CACHE_TTL = 3.0  # seconds
# Per-project "in-flight" flags prevent multiple executor threads from
# computing _build_status for the same project simultaneously.  Without
# this, toggling between N projects fires N parallel _build_status calls,
# each doing its own disk I/O, which saturates the USB drive and wedges
# the daemon.  With dedup, at most 1 thread per project is doing I/O;
# other callers get the stale cache (or wait for the single in-flight
# computation to finish if no cache exists at all).
_status_inflight: dict[str, bool] = {}
_STATUS_STALE_TTL = 30.0  # serve stale cache for up to 30s if a refresh is in-flight


# ── Request models ───────────────────────────────────────────────

class CancelRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync", "deep_enrichment", or "finalize"


class PauseRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync", "deep_enrichment", or "finalize"


class ResumeGroupRequest(BaseModel):
    group: str = "fast_sync"  # "fast_sync", "deep_enrichment", or "finalize"


class SwapModelRequest(BaseModel):
    group: str = "deep_enrichment"  # "fast_sync", "deep_enrichment", or "finalize"


class ResumeRequest(BaseModel):
    run_id: str


class DiscardRequest(BaseModel):
    run_id: str


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/projects/{project_id}/pipeline/fast")
def pipeline_run_fast(project_id: str) -> dict[str, Any]:
    """Run Fast Sync (stages 1-4): Structural → Catalogue → Validation → Knowledge Embedding."""
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_fast_sync(project_id)

    if not started:
        # Check if we skipped due to incomplete deep enrichment.
        #
        # F-47: a CANCELLED deep_enrichment run still has current_stage set
        # (it's just frozen at wherever it was killed) but is_active=False
        # and phase='cancelled'. Without checking the phase, the gate would
        # report "deep enrichment is still in progress" forever and refuse
        # every subsequent fast_sync until the daemon was restarted. The
        # phase guard treats cancelled / failed / completed as "done with
        # this run, fast_sync may proceed".
        status = pipeline_orchestrator.status(project_id)
        deep_run = status.get("deep_enrichment")
        deep_phase = deep_run.get("phase") if deep_run else None
        deep_finished = deep_phase in ("cancelled", "failed", "completed", None)
        if (
            deep_run
            and not deep_finished
            and (
                deep_run.get("is_active")
                or (deep_run.get("current_stage") and deep_run.get("current_stage") != "deep_knowledge")
            )
        ):
            raise ApiException(
                status_code=409,
                code="PIPELINE_INCOMPLETE",
                message="Deep enrichment is still in progress or paused. Please let the pipeline finish before processing new/stale items.",
            )

        raise ApiException(
            status_code=409,
            code="PIPELINE_UP_TO_DATE",
            message="Fast Sync is already up-to-date (no stale or new files detected) or is already running",
        )

    return ok({"started": True, "group": "fast_sync"})


@router.post("/projects/{project_id}/pipeline/deep")
def pipeline_run_deep(project_id: str) -> dict[str, Any]:
    """Run Deep Enrichment (stages 5-8): Epistemic → Clustering → Deepening → Deep Knowledge."""
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_deep_enrichment(project_id)

    if not started:
        # Diagnose WHY it didn't start
        status = pipeline_orchestrator.status(project_id)
        deep_run = status.get("deep_enrichment")

        # Case 1: Already running
        if deep_run and deep_run.get("is_active"):
            current = deep_run.get("current_stage", "unknown")
            raise ApiException(
                status_code=409,
                code="PIPELINE_ALREADY_RUNNING",
                message=f"Deep Enrichment is already running (currently at {current})",
            )

        # Case 2: Another group is running
        fast_run = status.get("fast_sync")
        if fast_run and fast_run.get("is_active"):
            raise ApiException(
                status_code=409,
                code="PIPELINE_BUSY",
                message="Cannot start Deep Enrichment — Fast Sync is currently running. Wait for it to finish.",
            )

        # Case 3: All stages detected as complete
        raise ApiException(
            status_code=409,
            code="PIPELINE_UP_TO_DATE",
            message=(
                "Deep Enrichment detected all stages as complete. "
                "If stages appear incomplete in the UI, try 'Force Reset' then 'Run' again."
            ),
        )

    return ok({"started": True, "group": "deep_enrichment"})


@router.post("/projects/{project_id}/pipeline/finalize")
def pipeline_run_finalize(project_id: str) -> dict[str, Any]:
    """Run Finalize group (stages 11-15): Atlas, Rules, Concepts, Audit, Antibodies."""
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_finalize(project_id)

    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_UP_TO_DATE",
            message="Finalize is already up-to-date or is already running",
        )

    return ok({"started": True, "group": "finalize"})


@router.post("/projects/{project_id}/pipeline/stages/{stage_id}/run")
def pipeline_run_single_stage(
    project_id: str,
    stage_id: str,
    force: bool = False,
) -> dict[str, Any]:
    """Run a single finalize stage (stages 11-15) through the orchestrator.

    Rejects sync/enrich stages (they must use the group endpoints).
    Returns 409 when another group is active or the orchestrator
    otherwise declines.
    """
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    from codrag.services.pipeline_orchestrator import (
        FINALIZE_STAGES,
        StageId,
        pipeline_orchestrator,
    )

    # Resolve stage_id string → StageId enum, reject unknowns + non-finalize.
    try:
        sid = StageId(stage_id)
    except ValueError as exc:
        raise ApiException(
            status_code=400,
            code="INVALID_STAGE_ID",
            message=f"Unknown stage_id '{stage_id}'.",
        ) from exc
    if sid not in FINALIZE_STAGES:
        raise ApiException(
            status_code=400,
            code="INVALID_STAGE_ID",
            message=(
                f"Stage '{stage_id}' is not a finalize stage. "
                "Use /pipeline/fast or /pipeline/deep for sync/enrich stages."
            ),
        )

    started = pipeline_orchestrator.run_single_stage(
        project_id, sid, force=force,
    )
    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_GROUP_ACTIVE",
            message=(
                f"Cannot run '{stage_id}' solo: another pipeline group is "
                "active, the stage is up-to-date, or the project is inactive."
            ),
        )

    return ok({"started": True, "group": sid.value})


@router.post("/projects/{project_id}/pipeline/all")
def pipeline_run_all(project_id: str) -> dict[str, Any]:
    """Run all 15 stages: Sync (1-5) → Enrich (6-10) → Finalize (11-15).

    Phase 96E: chains all three groups end-to-end. fast_sync and
    deep_enrichment chain via explicit_run_all, and deep_enrichment
    chains to finalize via _chain_finalize.
    """
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


@router.post("/projects/{project_id}/pipeline/rebuild")
def pipeline_rebuild(project_id: str) -> dict[str, Any]:
    """Rebuild all pipeline stages from scratch (zero-downtime).

    Each stage rebuilds its output completely, writing to a temp file
    and atomically swapping it into the live index directory.  The
    existing data remains available until the new data is ready.

    Phase 76: This is the non-destructive alternative to Reset Graph +
    re-run.  It does NOT delete anything first — it overwrites in place.
    """
    from codrag.services.project_helpers import require_project_writable
    require_project_writable(project_id)

    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    started = pipeline_orchestrator.run_all(project_id, force_from_start=True)

    if not started:
        raise ApiException(
            status_code=409,
            code="PIPELINE_ALREADY_RUNNING",
            message="Pipeline is already running for this project",
        )

    return ok({"started": True, "group": "all", "mode": "rebuild"})


@router.get("/projects/{project_id}/pipeline/status")
async def pipeline_status(project_id: str) -> dict[str, Any]:
    """Get the full 15-stage pipeline status (three-group model).

    Returns both group-level run status and per-stage build slot status.
    Also includes legacy per-stage data fetched from existing sources
    for backward compatibility with the current UI.

    Phase 60D-3: Runs in a dedicated thread pool to avoid being blocked
    when LLM workers occupy all slots in the default thread pool.
    """
    import asyncio

    def _build_status():
        import json as _json

        from codrag.server import _require_project
        from codrag.services.build_manager import build_manager

        proj = _require_project(project_id)
        idx_dir = project_index_dir(proj)

        def _fast_line_count(path) -> int:
            """Count lines in a JSONL file without loading it."""
            if not path.exists():
                return 0
            try:
                with open(path, "rb") as f:
                    return sum(1 for _ in f)
            except Exception:
                return 0

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
                with open(inferred_path, encoding="utf-8") as f:
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

        # 3. Fast Catalogue (augmentation) — read directly from file
        # Phase 60D-5: Replaced _augment_status() call to avoid lock contention
        augment_status: dict[str, Any]
        try:
            from codrag.server import _project_augment_status
            augment_status = _project_augment_status(proj)
        except Exception:
            augment_status = {"enabled": False, "total_nodes": 0, "augmented_nodes": 0}

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

        # F-76: If runtime state reports 0 chunks but the manifest records a
        # historical run (daemon just restarted mid-rebuild, KnowledgeIndex
        # hasn't reloaded from disk yet), fall back to the manifest so the UI
        # keeps showing green instead of resetting to grey.
        if knowledge_status.get("chunks_embedded", 0) == 0:
            know_manifest = idx_dir / "knowledge_manifest.json"
            if know_manifest.exists():
                try:
                    km = _json.loads(know_manifest.read_text(encoding="utf-8"))
                    hist_total = int(
                        (km.get("quality") or {}).get("total_items")
                        or km.get("count")
                        or 0
                    )
                    if hist_total > 0:
                        knowledge_status["enabled"] = True
                        knowledge_status["chunks_embedded"] = hist_total
                        knowledge_status["from_manifest"] = True
                except Exception:
                    pass

        # Phase 48 (P48-F4): Create separate deep_knowledge_status.
        deep_knowledge_status = dict(knowledge_status)
        deepening_path = idx_dir / "trace_epistemic.jsonl"
        modules_path = idx_dir / "trace_modules.jsonl"
        deep_has_run = (
            deepening_path.exists() and deepening_path.stat().st_size > 0 and
            modules_path.exists() and modules_path.stat().st_size > 0
        )
        deep_knowledge_status["deep_chunks_embedded"] = (
            knowledge_status.get("chunks_embedded", 0) if deep_has_run else 0
        )
        # F-76: Also fall back to deep_knowledge_manifest for deep stage.
        if deep_knowledge_status["deep_chunks_embedded"] == 0 and deep_has_run:
            dk_manifest = idx_dir / "deep_knowledge_manifest.json"
            if dk_manifest.exists():
                try:
                    dm = _json.loads(dk_manifest.read_text(encoding="utf-8"))
                    hist_total = int(
                        (dm.get("quality") or {}).get("total_items") or 0
                    )
                    if hist_total > 0:
                        deep_knowledge_status["deep_chunks_embedded"] = hist_total
                        deep_knowledge_status["from_manifest"] = True
                except Exception:
                    pass

        # 5. Epistemic enrichment — read directly from files
        # Phase 60D-5: Inline read avoids pipeline_orchestrator.status() lock
        epistemic_path = idx_dir / "trace_epistemic.jsonl"
        enriched_count = _fast_line_count(epistemic_path)
        total_file_nodes = _fast_line_count(idx_dir / "trace_nodes.jsonl")
        epistemic_status: dict[str, Any] = {
            "enabled": enriched_count > 0,
            "enriched_nodes": enriched_count,
            "total_file_nodes": total_file_nodes,
            "total_nodes": total_file_nodes,
            "avg_confidence": 0.0,
            "running": False,
        }
        # Try to get confidence from manifest
        ep_manifest = idx_dir / "trace_epistemic_manifest.json"
        if ep_manifest.exists():
            try:
                data = _json.loads(ep_manifest.read_text(encoding="utf-8"))
                quality = data.get("quality", {})
                if quality.get("processed", 0) > 0:
                    epistemic_status["enriched_nodes"] = quality["processed"]
                epistemic_status["avg_confidence"] = quality.get("avg_confidence", 0.0)
                # F-76: Surface incremental_baseline so the two-tone progress
                # bar renders correctly after a daemon restart or page refresh
                # (live slot progress_baseline is gone by then).
                inc_base = data.get("incremental_baseline")
                if isinstance(inc_base, int) and inc_base > 0:
                    epistemic_status["incremental_baseline"] = inc_base
            except Exception:
                pass

        # 6. Cluster synthesis — read directly from files
        modules_count = _fast_line_count(modules_path)
        cluster_status: dict[str, Any] = {
            "enabled": modules_count > 0,
            "module_count": modules_count,
            "total_files_clustered": modules_count,
            "running": False,
        }

        # 7. Deepening — read directly from files
        deepening_status: dict[str, Any] = {"running": False, "total_scored": 0}
        if deep_has_run:
            deepening_manifest = idx_dir / "deepening_manifest.json"
            if deepening_manifest.exists():
                try:
                    data = _json.loads(deepening_manifest.read_text(encoding="utf-8"))
                    quality = data.get("quality", {})
                    total_items = quality.get("total_items", 0)
                    processed = quality.get("processed", 0)
                    deepening_status["total_scored"] = total_items
                    deepening_status["settled_count"] = processed
                    deepening_status["avg_score"] = quality.get("avg_confidence", 0.0)
                    # Phase 72: Compute settled_ratio for the UI's computeDeepeningState
                    deepening_status["settled_ratio"] = (
                        processed / total_items if total_items > 0 else 0.0
                    )
                except Exception:
                    pass

        atlas_status: dict[str, Any]
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

        # Rules status
        rules_status: dict[str, Any] = {"generated": False, "stale": False}
        try:
            from pathlib import Path as _Path
            agents_md = _Path(proj.path) / "AGENTS.md"
            rules_status["generated"] = agents_md.exists()
        except Exception:
            pass

        # Concepts status
        concepts_status: dict[str, Any] = {"seeded": False, "count": 0}
        try:
            from codrag.services.concept_store import concept_store
            cstats = concept_store.get_stats(project_id)
            concepts_status = {"seeded": cstats["total"] > 0, "count": cstats["total"]}
        except Exception:
            pass

        # Audit status
        audit_status: dict[str, Any] = {"exists": False, "finding_count": 0}
        try:
            audit_path = idx_dir / "audit_findings.json"
            if audit_path.exists():
                adata = _json.loads(audit_path.read_text())
                audit_status = {
                    "exists": True,
                    "finding_count": len(adata.get("findings", [])),
                }
        except Exception:
            pass

        # Antibodies status
        antibodies_status: dict[str, Any] = {"count": 0}
        try:
            from codrag.services.antibody_store import antibody_store
            ab_list = antibody_store.list_antibodies(project_id)
            antibodies_status = {"count": len(ab_list)}
        except Exception:
            pass

        # Pipeline orchestrator group-level status
        from codrag.services.pipeline_orchestrator import pipeline_orchestrator
        pipeline_state = pipeline_orchestrator.status(project_id)

        # Merge live build-slot progress into each stage's data so the UI
        # can show progress bars that update during long-running stages.
        slot_stages = pipeline_state.get("stages") or {}
        # Group reasoning status
        group_reasoning_status: dict[str, Any] = {"enabled": False, "group_count": 0, "analyzed": 0}
        try:
            gr_path = idx_dir / "trace_group_reasoning.jsonl"
            if gr_path.exists():
                gr_count = 0
                with open(gr_path, encoding="utf-8") as f:
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
            "rules": rules_status,
            "concepts": concepts_status,
            "audit": audit_status,
            "antibodies": antibodies_status,
        }
        for stage_key, slot_info in slot_stages.items():
            if stage_key in stage_data and isinstance(slot_info, dict):
                slot_progress = slot_info.get("progress")
                if slot_progress:
                    stage_data[stage_key]["slot_progress"] = slot_progress
                    # Flatten into top-level keys so the UI can read progress_current/progress_total directly
                    stage_data[stage_key]["progress_current"] = slot_progress.get("current", 0)
                    stage_data[stage_key]["progress_total"] = slot_progress.get("total", 0)
                    stage_data[stage_key]["progress_baseline"] = slot_progress.get("baseline", 0)
                if slot_info.get("phase"):
                    stage_data[stage_key]["slot_phase"] = slot_info["phase"]

        # Phase 72 Stage 4: Merge stage snapshots from state machine.
        # Snapshots provide live data during active runs (updated by workers).
        # When a snapshot has data, it takes precedence for running/progress fields
        # since it's fresher than the disk reads above.
        stage_snapshots = pipeline_state.get("stage_snapshots") or {}
        for snap_key, snap_data in stage_snapshots.items():
            if snap_key in stage_data and isinstance(snap_data, dict):
                # Only merge running/progress fields from snapshots
                if snap_data.get("running"):
                    stage_data[snap_key]["running"] = True
                for k in ("progress_current", "progress_total", "progress_baseline"):
                    if snap_data.get(k, 0) > 0:
                        stage_data[snap_key][k] = snap_data[k]
                # Merge item counts if snapshot has them (from completion)
                if snap_data.get("item_count", 0) > 0:
                    stage_data[snap_key]["snapshot_item_count"] = snap_data["item_count"]
                if snap_data.get("avg_confidence", 0) > 0:
                    stage_data[snap_key]["snapshot_avg_confidence"] = snap_data["avg_confidence"]

        # F-66: Read incremental_baseline from manifests for completed stages.
        # When the page refreshes, the in-memory slot progress (with baseline)
        # is gone. The manifest persists the baseline so 2-tone bars survive.
        from codrag.services.pipeline.stages import STAGE_MANIFEST_FILE as _SMF
        from codrag.services.pipeline.stages import StageId as _StageId
        _stage_id_values = {s.value for s in _StageId}
        for stage_key, stage_info in stage_data.items():
            if not isinstance(stage_info, dict):
                continue
            if stage_info.get("progress_baseline", 0) > 0:
                continue  # Already have baseline from live slot progress
            if stage_key not in _stage_id_values:
                continue
            manifest_file = _SMF.get(_StageId(stage_key))
            if not manifest_file:
                continue
            mpath = idx_dir / manifest_file
            if mpath.exists():
                try:
                    mdata = _json.loads(mpath.read_text(encoding="utf-8"))
                    baseline = mdata.get("incremental_baseline", 0)
                    if baseline and baseline > 0:
                        stage_info["progress_baseline"] = baseline
                        sp = stage_info.get("slot_progress")
                        if sp and isinstance(sp, dict):
                            sp["baseline"] = baseline
                except Exception:
                    pass

        # Phase 25: include crashed runs so the UI can show recovery banner
        crashed_runs = pipeline_orchestrator.get_crashed_runs(project_id)

        # Phase 45D: include scheduler status so the UI can show queue state
        scheduler_data = None
        try:
            from codrag.services.pipeline.scheduler import pipeline_scheduler
            scheduler_data = pipeline_scheduler.status()
        except Exception:
            pass

        # Phase 66: Pi agent status
        agent_data = None
        try:
            from codrag.services.agent_gate import get_agent_gate
            from codrag.services.pi_agent import get_pi_agent
            pi = get_pi_agent()
            gate = get_agent_gate()
            agent_data = {
                **(pi.status() if pi else {"enabled": False}),
                "gate": gate.status(),
            }
        except Exception:
            pass

        return ok({
            "fast_sync": pipeline_state.get("fast_sync"),
            "deep_enrichment": pipeline_state.get("deep_enrichment"),
            "finalize": pipeline_state.get("finalize"),
            "stages": stage_data,
            "any_running": pipeline_state.get("any_running", False),
            "crashed_runs": crashed_runs,
            "scheduler": scheduler_data,
            "agent": agent_data,
        })

    # F-57: stale-while-refresh cache with per-project dedup.
    #
    # _build_status reads multiple files from the USB drive. When the
    # dashboard toggles between N projects while swarm workers are doing
    # heavy I/O, all 4 _status_executor threads block on disk reads and
    # the daemon appears hung.
    #
    # Strategy:
    #   1. If cache is fresh (< TTL), return it instantly (no executor)
    #   2. If cache is stale but a refresh is already in-flight for this
    #      project, return the stale cache instead of queuing another I/O
    #   3. Only ONE thread per project enters _build_status at a time
    now = _time.time()
    with _status_cache_lock:
        cached = _status_cache.get(project_id)
        if cached:
            ts, result = cached
            age = now - ts
            if age < _STATUS_CACHE_TTL:
                return result  # fresh enough
            # Stale cache available + refresh already in-flight for this
            # project: return whatever we have instead of queuing another
            # I/O thread.  No age limit — ANY stale data is better than
            # hanging for 30s while the USB drive is saturated by swarm
            # workers.  The dashboard polls every few seconds so a fresh
            # result will arrive as soon as the single in-flight refresh
            # completes.
            if _status_inflight.get(project_id):
                return result  # serve stale — refresh is already running

    # Mark this project as in-flight so other callers get the stale cache
    with _status_cache_lock:
        _status_inflight[project_id] = True

    try:
        loop = asyncio.get_running_loop()
        # Timeout: if _build_status blocks on USB I/O for >10s, give up
        # and return whatever stale cache we have.  The next poll cycle
        # will retry.  This prevents a single slow disk read from wedging
        # the entire status endpoint.
        try:
            # F-70: Reduced from 10s to 2s. During active cloud model calls,
            # the executor threads are blocked and the 10s timeout caused the
            # dashboard to appear frozen for long periods. With 2s, stale cache
            # is returned quickly and SSE events provide real-time updates.
            result = await asyncio.wait_for(
                loop.run_in_executor(_status_executor, _build_status),
                timeout=2.0,
            )
        except TimeoutError:
            with _status_cache_lock:
                stale = _status_cache.get(project_id)
                if stale:
                    return stale[1]
            # No cache at all — return a minimal stub so the dashboard
            # doesn't crash. The next poll will retry.
            return ok({
                "fast_sync": None,
                "deep_enrichment": None,
                "finalize": None,
                "stages": {},
                "any_running": True,  # assume running if we can't tell
                "crashed_runs": [],
            })
        with _status_cache_lock:
            _status_cache[project_id] = (_time.time(), result)
        return result
    finally:
        with _status_cache_lock:
            _status_inflight.pop(project_id, None)


@router.post("/projects/{project_id}/pipeline/cancel")
def pipeline_cancel(project_id: str, req: CancelRequest) -> dict[str, Any]:
    """Cancel a running pipeline group."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.pipeline_orchestrator import FINALIZE_STAGES, pipeline_orchestrator

    # Phase 105a (C2): Solo finalize-stage runs register under the stage's own
    # value as the group key (e.g. "atlas", "concepts"). Extend the allowed set
    # beyond the three canonical group names so cancel reaches those runs.
    _solo_finalize_values = {s.value for s in FINALIZE_STAGES}

    if req.group == "fast_sync":
        cancelled = pipeline_orchestrator.cancel_fast_sync(project_id)
    elif req.group == "deep_enrichment":
        cancelled = pipeline_orchestrator.cancel_deep_enrichment(project_id)
    elif req.group == "finalize":
        cancelled = pipeline_orchestrator.cancel_finalize(project_id)
    elif req.group in _solo_finalize_values:
        # Solo run — delegate to the internal group cancel using the raw stage name.
        cancelled = pipeline_orchestrator._cancel_group(project_id, req.group)
    else:
        raise ApiException(
            status_code=400,
            code="INVALID_GROUP",
            message=(
                f"Unknown group: {req.group}. Must be 'fast_sync', 'deep_enrichment', "
                f"'finalize', or a finalize stage name ({', '.join(sorted(_solo_finalize_values))})."
            ),
        )

    if not cancelled:
        raise ApiException(
            status_code=409,
            code="NOT_RUNNING",
            message=f"{req.group} is not currently running",
        )

    return ok({"cancelled": True, "group": req.group})


@router.post("/projects/{project_id}/pipeline/pause")
def pipeline_pause(project_id: str, req: PauseRequest) -> dict[str, Any]:
    """Pause a running pipeline group.

    The current stage flushes partial results to disk before stopping.
    Resume with POST /projects/{project_id}/pipeline/resume.
    """
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.pipeline_orchestrator import FINALIZE_STAGES, pipeline_orchestrator

    # Phase 105a (C2): Solo finalize-stage runs register under the stage's own
    # value as the group key (e.g. "atlas", "concepts"). Extend the allowed set
    # beyond the three canonical group names so pause reaches those runs.
    _solo_finalize_values = {s.value for s in FINALIZE_STAGES}

    if req.group == "fast_sync":
        paused = pipeline_orchestrator.pause_fast_sync(project_id)
    elif req.group == "deep_enrichment":
        paused = pipeline_orchestrator.pause_deep_enrichment(project_id)
    elif req.group == "finalize":
        paused = pipeline_orchestrator.pause_finalize(project_id)
    elif req.group in _solo_finalize_values:
        # Solo run — delegate to the internal group pause using the raw stage name.
        paused = pipeline_orchestrator._pause_group(project_id, req.group)
    else:
        raise ApiException(
            status_code=400,
            code="INVALID_GROUP",
            message=(
                f"Unknown group: {req.group}. Must be 'fast_sync', 'deep_enrichment', "
                f"'finalize', or a finalize stage name ({', '.join(sorted(_solo_finalize_values))})."
            ),
        )

    if not paused:
        raise ApiException(
            status_code=409,
            code="NOT_RUNNING",
            message=f"{req.group} is not currently running",
        )

    return ok({"paused": True, "group": req.group})


@router.post("/projects/{project_id}/pipeline/resume")
def pipeline_resume_group(project_id: str, req: ResumeGroupRequest) -> dict[str, Any]:
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
def pipeline_swap_model(project_id: str, req: SwapModelRequest) -> dict[str, Any]:
    """Swap the LLM model mid-pipeline without losing progress.

    Pauses the current stage (flushing partial results), then immediately
    resumes.  The resumed stage re-reads LLM config, picking up any model
    or endpoint changes the user just made.  Incremental workers skip
    already-processed items, so no work is lost.
    """
    from codrag.server import _require_project
    _require_project(project_id)

    if req.group not in ("fast_sync", "deep_enrichment", "finalize"):
        raise ApiException(
            status_code=400,
            code="INVALID_GROUP",
            message=f"Unknown group: {req.group}. Must be 'fast_sync', 'deep_enrichment', or 'finalize'.",
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
def pipeline_force_reset(project_id: str) -> dict[str, Any]:
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
def pipeline_crashed_runs(project_id: str | None = None) -> dict[str, Any]:
    """Get all crashed pipeline runs, optionally filtered by project.

    Returns a list of crashed runs with enough info for the UI to
    offer Resume / Discard buttons.
    """
    from codrag.services.pipeline_orchestrator import pipeline_orchestrator
    runs = pipeline_orchestrator.get_crashed_runs(project_id)
    return ok({"crashed_runs": runs, "count": len(runs)})


@router.post("/pipeline/resume")
def pipeline_resume(req: ResumeRequest) -> dict[str, Any]:
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
def pipeline_discard(req: DiscardRequest) -> dict[str, Any]:
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
def pipeline_budget_usage(project_id: str) -> dict[str, Any]:
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
