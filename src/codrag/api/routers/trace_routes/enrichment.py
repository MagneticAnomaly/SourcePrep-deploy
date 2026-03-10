"""
Trace enrichment pipeline endpoints — augment, deep-analysis, epistemic,
modules, deepening, destroy.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from codrag.api.envelope import ApiException, ok
from codrag.core.events import get_event_bus, get_progress_manager
from codrag.core.project_registry import project_index_dir

from .shared import (
    _deep_analysis_state,
    _epistemic_state,
    _cluster_state,
    _deepening_state,
    TRACE_FILES,
    INDEX_FILES,
    ALL_DATA_FILES,
    AugmentRequest,
    DeepAnalysisRequest,
    EpistemicRunRequest,
    DeepeningRunRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trace"])


@router.get("/projects/{project_id}/augment/status")
def augment_status_project(project_id: str) -> Dict[str, Any]:
    """Get augmentation status for a project.
    
    When augmentation is actively running, includes live progress from
    the build slot so the UI can show a real progress bar.
    """
    from codrag.server import _require_project, _project_augment_status
    proj = _require_project(project_id)
    status = _project_augment_status(proj)

    # Overlay live build-slot progress when the catalogue stage is running.
    # The manifest-based augmented_nodes only updates on completion, so
    # the UI would otherwise see 0% for the entire run.
    try:
        from codrag.services.build_orchestrator import build_orchestrator, BuildType, BuildPhase
        slot = build_orchestrator.status(project_id, BuildType.AUGMENT)
        if slot.phase == BuildPhase.RUNNING and slot.progress_total > 0:
            status["enabled"] = True
            status["augmented_nodes"] = slot.progress_current
            status["total_nodes"] = slot.progress_total
    except Exception:
        pass  # Non-fatal: fall back to manifest data

    return ok(status)


@router.post("/projects/{project_id}/augment/run")
def augment_run_project(project_id: str, req: AugmentRequest) -> Dict[str, Any]:
    """Run LLM augmentation on trace nodes (Phase 1, Step 2)."""
    from codrag.server import _require_project_writable, _get_llm_client_for_task
    proj = _require_project_writable(project_id)

    llm_client = _get_llm_client_for_task("augmentation")
    if not llm_client:
        raise ApiException(
            status_code=409,
            code="NO_SMALL_MODEL",
            message="No model configured for augmentation",
            hint="Configure a model in AI Models settings.",
        )

    if not llm_client.is_available():
        raise ApiException(
            status_code=503,
            code="MODEL_UNAVAILABLE",
            message=f"Small model endpoint not reachable: {llm_client.endpoint_url}",
        )

    idx_dir = project_index_dir(proj)
    from codrag.core import TraceAugmenter

    augmenter = TraceAugmenter(
        index_dir=idx_dir,
        repo_root=proj.path,
        llm_client=llm_client,
    )

    bus = get_event_bus()
    pm = get_progress_manager()
    task_id = f"augment_{project_id}"

    def progress_cb(phase: str, current: int, total: int):
        pm.update(task_id, f"Augmenting: {phase}", current, total)

    pm.update(task_id, "Starting augmentation...", 0, 1)

    def _run():
        try:
            result = augmenter.run(
                progress_callback=progress_cb,
                max_items=req.max_items,
            )
            pm.update(task_id, f"Augmentation complete: {result.augmented} nodes", 1, 1)
            bus.emit("task", {"task_id": task_id, "status": "completed"})
        except Exception as e:
            logger.error("Augmentation failed: %s", e)
            pm.update(task_id, f"Augmentation failed: {e}", 0, 1)
            bus.emit("task", {"task_id": task_id, "status": "failed"})

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return ok({"started": True, "task_id": task_id})


# ═════════════════════════════════════════════════════════════════
# Deep Analysis (Pass 2)
# ═════════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/deep-analysis/status")
def deep_analysis_status_project(project_id: str, full: bool = False) -> Dict[str, Any]:
    """Get deep analysis status for a project.

    By default returns fast manifest-only status.
    Pass ?full=true to recompute live queue stats (slower — reads all trace files).
    """
    from codrag.server import _require_project, _load_ui_config
    proj = _require_project(project_id)
    idx_dir = project_index_dir(proj)

    ui_cfg = _load_ui_config()
    schedule_cfg = ui_cfg.get("deep_analysis") or {}

    from codrag.core import DeepAnalysisOrchestrator, DeepAnalysisSchedule
    schedule = DeepAnalysisSchedule.from_dict(schedule_cfg)
    orchestrator = DeepAnalysisOrchestrator(
        index_dir=idx_dir,
        repo_root=proj.path,
        schedule=schedule,
    )
    result = orchestrator.status(include_queue=full)

    # Inject live running state
    state = _deep_analysis_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        result["running"] = True
        result["progress_current"] = state.get("current", 0)
        result["progress_total"] = state.get("total", 0)
        pct = (state.get("current", 0) / state["total"] * 100) if state.get("total", 0) > 0 else 0
        result["progress_pct"] = round(pct, 1)
    else:
        result["running"] = False

    return ok(result)


@router.post("/projects/{project_id}/deep-analysis/run")
def deep_analysis_run_project(project_id: str, req: DeepAnalysisRequest) -> Dict[str, Any]:
    """Run deep analysis validation (Phase 2, Step 4). Uses Tier 0 evidence only."""
    from codrag.server import _require_project_writable, _get_llm_client_for_task, _load_ui_config
    proj = _require_project_writable(project_id)

    # Prevent double-run
    state = _deep_analysis_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        raise ApiException(
            status_code=409,
            code="ALREADY_RUNNING",
            message="Deep analysis is already running for this project",
        )

    llm_client = _get_llm_client_for_task("enrichment")
    if not llm_client:
        raise ApiException(
            status_code=409,
            code="NO_MODEL",
            message="No model configured for deep analysis",
            hint="Configure a model in AI Models settings.",
        )

    if not llm_client.is_available():
        raise ApiException(
            status_code=503,
            code="MODEL_UNAVAILABLE",
            message=f"Large model endpoint not reachable: {llm_client.endpoint_url}",
        )

    idx_dir = project_index_dir(proj)
    ui_cfg = _load_ui_config()
    schedule_cfg = ui_cfg.get("deep_analysis") or {}

    from codrag.core import DeepAnalysisOrchestrator, DeepAnalysisSchedule
    schedule = DeepAnalysisSchedule.from_dict(schedule_cfg)

    # Apply request overrides
    if req.max_items is not None:
        schedule.budget_max_items = req.max_items
    if req.max_tokens is not None:
        schedule.budget_max_tokens = req.max_tokens
    if req.max_minutes is not None:
        schedule.budget_max_minutes = req.max_minutes

    orchestrator = DeepAnalysisOrchestrator(
        index_dir=idx_dir,
        repo_root=proj.path,
        schedule=schedule,
    )

    bus = get_event_bus()
    pm = get_progress_manager()
    task_id = f"deep_analysis_{project_id}"

    # Set up cancel flag and running state
    cancel_event = threading.Event()
    run_state: Dict[str, Any] = {"thread": None, "cancel": cancel_event, "current": 0, "total": 0}
    _deep_analysis_state[project_id] = run_state

    def progress_cb(phase: str, current: int, total: int):
        run_state["current"] = current
        run_state["total"] = total
        pm.update(task_id, f"Deep analysis: {phase}", current, total)

    pm.update(task_id, "Starting deep analysis (Tier 0 evidence)...", 0, 1)

    def _run():
        try:
            result = orchestrator.run(
                llm_client=llm_client,
                progress_callback=progress_cb,
                cancel_event=cancel_event,
            )
            msg = (
                f"Deep analysis complete: {result.items_validated} validated "
                f"({result.items_confirmed} confirmed, {result.items_corrected} corrected, "
                f"{result.items_rejected} rejected)"
            )
            pm.update(task_id, msg, 1, 1)
            bus.emit("task", {"task_id": task_id, "status": "completed"})
        except Exception as e:
            logger.error("Deep analysis failed: %s", e)
            pm.update(task_id, f"Deep analysis failed: {e}", 0, 1)
            bus.emit("task", {"task_id": task_id, "status": "failed"})
        finally:
            # Clean up state so status() reports running=False
            if _deep_analysis_state.get(project_id) is run_state:
                _deep_analysis_state.pop(project_id, None)

    t = threading.Thread(target=_run, daemon=True)
    run_state["thread"] = t
    t.start()
    return ok({"started": True, "task_id": task_id})


@router.post("/projects/{project_id}/deep-analysis/cancel")
def deep_analysis_cancel_project(project_id: str) -> Dict[str, Any]:
    """Cancel a running deep analysis."""
    from codrag.server import _require_project_writable
    _require_project_writable(project_id)
    state = _deep_analysis_state.get(project_id)
    if not state or not state.get("thread") or not state["thread"].is_alive():
        raise ApiException(
            status_code=409,
            code="NOT_RUNNING",
            message="No deep analysis is currently running for this project",
        )
    state["cancel"].set()
    logger.info("Deep analysis cancel requested for project %s", project_id)
    return ok({"cancelled": True})


# ═════════════════════════════════════════════════════════════════
# Epistemic Enrichment (Pass 2b)
# ═════════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/epistemic/status")
def epistemic_status_project(project_id: str) -> Dict[str, Any]:
    """Get epistemic enrichment status for a project."""
    from codrag.server import _require_project
    proj = _require_project(project_id)
    idx_dir = project_index_dir(proj)
    epistemic_path = idx_dir / "trace_epistemic.jsonl"

    # Count file nodes from trace_nodes.jsonl — epistemic only enriches
    # file nodes, so total_file_nodes is the correct denominator (not total nodes).
    total_file_nodes = 0
    nodes_path = idx_dir / "trace_nodes.jsonl"
    if nodes_path.exists():
        try:
            with open(nodes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            nd = json.loads(line)
                            if nd.get("kind") == "file":
                                total_file_nodes += 1
                        except Exception:
                            pass
        except Exception:
            pass

    if not epistemic_path.exists():
        result: Dict[str, Any] = {
            "enabled": False,
            "enriched_nodes": 0,
            "total_file_nodes": total_file_nodes,
            "avg_confidence": 0.0,
        }
    else:
        count = 0
        total_conf = 0.0
        with open(epistemic_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        d = json.loads(line)
                        count += 1
                        total_conf += float(d.get("epistemic_confidence", 0.0))
                    except Exception:
                        pass
        result = {
            "enabled": True,
            "enriched_nodes": count,
            "total_file_nodes": total_file_nodes,
            "avg_confidence": round(total_conf / count, 3) if count else 0.0,
        }

    # Inject live running state — check legacy threads first
    state = _epistemic_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        result["running"] = True
        result["progress_current"] = state.get("current", 0)
        result["progress_total"] = state.get("total", 0)
    else:
        result["running"] = False

    # Two running signals:
    # - "running": True only when Stage 5 (Epistemic) specifically is active
    #   (used by computeEpistemicState for the stage row icon)
    # - "pipeline_running": True when ANY deep enrichment stage (5-8) is active
    #   (used by DeepCoverageBar to keep the bar spinning)
    result["pipeline_running"] = False

    try:
        from codrag.services.pipeline_orchestrator import pipeline_orchestrator
        pipe_status = pipeline_orchestrator.status(project_id)
        deep_run = pipe_status.get("deep_enrichment")

        if deep_run and deep_run.get("phase") == "running":
            # The overall deep pipeline is running
            result["pipeline_running"] = True
            current_stage = deep_run.get("current_stage")

            # Only mark Stage 5 as "running" if we are specifically on that stage
            if current_stage == "enrichment":
                result["running"] = True
                stages = pipe_status.get("stages", {})
                slot = stages.get("enrichment") or {}
                prog = slot.get("progress")
                if prog:
                    result["progress_current"] = prog.get("current", 0)
                    result["progress_total"] = prog.get("total", 0)

    except Exception:
        # Fallback to just checking the single slot if pipeline check fails
        try:
            from codrag.services.build_orchestrator import build_orchestrator, BuildType, BuildPhase
            slot = build_orchestrator.status(project_id, BuildType.EPISTEMIC)
            if slot.phase == BuildPhase.RUNNING:
                result["running"] = True
                result["pipeline_running"] = True
                if slot.progress_total > 0:
                    result["progress_current"] = slot.progress_current
                    result["progress_total"] = slot.progress_total
        except Exception:
            pass

    return ok(result)


@router.post("/projects/{project_id}/epistemic/run")
def epistemic_run_project(project_id: str, req: EpistemicRunRequest) -> Dict[str, Any]:
    """Run epistemic enrichment (Pass 2) using the large model."""
    from codrag.server import _require_project_writable, _get_llm_client_for_task
    proj = _require_project_writable(project_id)

    state = _epistemic_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        raise ApiException(status_code=409, code="ALREADY_RUNNING", message="Epistemic enrichment already running")

    llm_client = _get_llm_client_for_task("enrichment")
    if not llm_client:
        raise ApiException(status_code=409, code="NO_MODEL", message="No model configured", hint="Configure a model in AI Models settings.")
    if not llm_client.is_available():
        raise ApiException(status_code=503, code="MODEL_UNAVAILABLE", message=f"Model endpoint not reachable: {llm_client.endpoint_url}")

    idx_dir = project_index_dir(proj)
    from codrag.core import EpistemicEnricher

    enricher = EpistemicEnricher(
        llm=llm_client,
        repo_root=Path(proj.path),
        index_dir=idx_dir,
    )

    bus = get_event_bus()
    pm = get_progress_manager()
    task_id = f"epistemic_{project_id}"
    run_state: Dict[str, Any] = {"thread": None, "current": 0, "total": 0}
    _epistemic_state[project_id] = run_state

    def progress_cb(phase: str, current: int, total: int):
        run_state["current"] = current
        run_state["total"] = total
        pm.update(task_id, f"Epistemic enrichment: {phase}", current, total)

    pm.update(task_id, "Starting epistemic enrichment (14b)...", 0, 1)

    def _run():
        try:
            result = enricher.run(progress_callback=progress_cb, max_items=req.max_items)
            pm.update(task_id, f"Epistemic enrichment complete: {result.get('enriched_this_run', 0)} nodes", 1, 1)
            bus.emit("task", {"task_id": task_id, "status": "completed"})
        except Exception as e:
            logger.error("Epistemic enrichment failed: %s", e)
            pm.update(task_id, f"Epistemic enrichment failed: {e}", 0, 1)
            bus.emit("task", {"task_id": task_id, "status": "failed"})
        finally:
            if _epistemic_state.get(project_id) is run_state:
                _epistemic_state.pop(project_id, None)

    t = threading.Thread(target=_run, daemon=True)
    run_state["thread"] = t
    t.start()
    return ok({"started": True, "task_id": task_id})


# ═════════════════════════════════════════════════════════════════
# Cluster / Module Synthesis (Pass 3)
# ═════════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/modules/status")
def modules_status_project(project_id: str) -> Dict[str, Any]:
    """Get cluster/module synthesis status for a project."""
    from codrag.server import _require_project
    proj = _require_project(project_id)
    idx_dir = project_index_dir(proj)
    modules_path = idx_dir / "trace_modules.jsonl"

    if not modules_path.exists():
        result: Dict[str, Any] = {"enabled": False, "module_count": 0, "total_files_clustered": 0, "last_run_at": None}
    else:
        count = 0
        total_files = 0
        last_run = None
        with open(modules_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        d = json.loads(line)
                        count += 1
                        total_files += int(d.get("file_count", 0))
                        syn_at = d.get("synthesized_at")
                        if syn_at and (not last_run or syn_at > last_run):
                            last_run = syn_at
                    except Exception:
                        pass
        result = {"enabled": True, "module_count": count, "total_files_clustered": total_files, "last_run_at": last_run}

    state = _cluster_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        result["running"] = True
    else:
        result["running"] = False

    # Overlay pipeline build-slot progress (pipeline-managed runs)
    try:
        from codrag.services.build_orchestrator import build_orchestrator, BuildType, BuildPhase
        slot = build_orchestrator.status(project_id, BuildType.CLUSTER)
        if slot.phase == BuildPhase.RUNNING:
            result["running"] = True
            if slot.progress_total > 0:
                result["progress_current"] = slot.progress_current
                result["progress_total"] = slot.progress_total
    except Exception:
        pass  # Non-fatal

    return ok(result)


@router.post("/projects/{project_id}/modules/run")
def modules_run_project(project_id: str) -> Dict[str, Any]:
    """Run cluster synthesis (Pass 3) using the large model."""
    from codrag.server import _require_project_writable, _get_llm_client_for_task
    proj = _require_project_writable(project_id)

    state = _cluster_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        raise ApiException(status_code=409, code="ALREADY_RUNNING", message="Cluster synthesis already running")

    llm_client = _get_llm_client_for_task("clustering")
    if not llm_client:
        raise ApiException(status_code=409, code="NO_MODEL", message="No model configured")
    if not llm_client.is_available():
        raise ApiException(status_code=503, code="MODEL_UNAVAILABLE", message=f"Model endpoint not reachable: {llm_client.endpoint_url}")

    idx_dir = project_index_dir(proj)
    from codrag.core import ClusterSynthesizer

    synthesizer = ClusterSynthesizer(llm=llm_client, index_dir=idx_dir)

    bus = get_event_bus()
    pm = get_progress_manager()
    task_id = f"cluster_{project_id}"
    run_state: Dict[str, Any] = {"thread": None}
    _cluster_state[project_id] = run_state

    pm.update(task_id, "Starting cluster synthesis...", 0, 1)

    def _run():
        try:
            result = synthesizer.run()
            pm.update(task_id, f"Cluster synthesis complete: {result.get('synthesized', 0)} modules", 1, 1)
            bus.emit("task", {"task_id": task_id, "status": "completed"})
        except Exception as e:
            logger.error("Cluster synthesis failed: %s", e)
            pm.update(task_id, f"Cluster synthesis failed: {e}", 0, 1)
            bus.emit("task", {"task_id": task_id, "status": "failed"})
        finally:
            if _cluster_state.get(project_id) is run_state:
                _cluster_state.pop(project_id, None)

    t = threading.Thread(target=_run, daemon=True)
    run_state["thread"] = t
    t.start()
    return ok({"started": True, "task_id": task_id})


# ═════════════════════════════════════════════════════════════════
# Deepening Loop (Pass 4+)
# ═════════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/deepening/status")
def deepening_status_project(project_id: str) -> Dict[str, Any]:
    """Get deepening loop status for a project."""
    from codrag.server import _require_project
    proj = _require_project(project_id)
    idx_dir = project_index_dir(proj)

    # Compute epistemic scores to get convergence info — but only if
    # clustering has produced modules.  Without modules, deepening hasn't
    # meaningfully run and showing epistemic scores here is misleading.
    result: Dict[str, Any] = {"running": False}
    modules_path = idx_dir / "trace_modules.jsonl"
    modules_exist = modules_path.exists() and modules_path.stat().st_size > 0
    try:
        from codrag.core import EpistemicEnricher, LLMClient
        enricher = EpistemicEnricher(
            llm=LLMClient("http://localhost:11434", "none"),
            repo_root=Path(proj.path),
            index_dir=idx_dir,
        )
        scores = enricher.compute_all_scores() if modules_exist else {}
        if scores:
            composites = [s.composite for s in scores.values()]
            # Must match DeepeningLoop.settled_threshold (0.60)
            settled = sum(1 for c in composites if c >= 0.60)
            result["total_scored"] = len(composites)
            result["settled_count"] = settled
            result["settled_ratio"] = round(settled / len(composites), 3) if composites else 0.0
            result["avg_score"] = round(sum(composites) / len(composites), 3)
            result["min_score"] = round(min(composites), 3)
            result["max_score"] = round(max(composites), 3)
        else:
            result["total_scored"] = 0
            result["settled_count"] = 0
            result["settled_ratio"] = 0.0
            result["avg_score"] = 0.0
    except Exception:
        result["total_scored"] = 0

    state = _deepening_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        result["running"] = True
        result["iteration"] = state.get("iteration", 0)
        result["max_iterations"] = state.get("max_iterations", 10)
    else:
        result["running"] = False

    # Overlay pipeline build-slot progress (pipeline-managed runs)
    try:
        from codrag.services.build_orchestrator import build_orchestrator, BuildType, BuildPhase
        slot = build_orchestrator.status(project_id, BuildType.DEEPENING)
        if slot.phase == BuildPhase.RUNNING:
            result["running"] = True
            if slot.progress_total > 0:
                result["progress_current"] = slot.progress_current
                result["progress_total"] = slot.progress_total
                result["iteration"] = slot.progress_current
                result["max_iterations"] = slot.progress_total
    except Exception:
        pass  # Non-fatal

    return ok(result)


@router.post("/projects/{project_id}/deepening/run")
def deepening_run_project(project_id: str, req: DeepeningRunRequest) -> Dict[str, Any]:
    """Run continuous deepening loop (Pass 4+)."""
    from codrag.server import _require_project_writable, _get_llm_client_for_task
    proj = _require_project_writable(project_id)

    state = _deepening_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        raise ApiException(status_code=409, code="ALREADY_RUNNING", message="Deepening loop already running")

    llm_client = _get_llm_client_for_task("deepening")
    if not llm_client:
        raise ApiException(status_code=409, code="NO_MODEL", message="No model configured")
    if not llm_client.is_available():
        raise ApiException(status_code=503, code="MODEL_UNAVAILABLE", message=f"Model endpoint not reachable: {llm_client.endpoint_url}")

    idx_dir = project_index_dir(proj)
    from codrag.core import EpistemicEnricher, DeepeningLoop

    enricher = EpistemicEnricher(
        llm=llm_client,
        repo_root=Path(proj.path),
        index_dir=idx_dir,
    )

    loop = DeepeningLoop(
        enricher=enricher,
        index_dir=idx_dir,
        max_iterations=req.max_iterations or 10,
        batch_size=req.batch_size or 20,
    )

    bus = get_event_bus()
    pm = get_progress_manager()
    task_id = f"deepening_{project_id}"
    run_state: Dict[str, Any] = {"thread": None, "iteration": 0, "max_iterations": req.max_iterations or 10}
    _deepening_state[project_id] = run_state

    pm.update(task_id, "Starting deepening loop...", 0, 1)

    def progress_cb(phase: str, current: int, total: int):
        run_state["iteration"] = current
        pm.update(task_id, f"Deepening: {phase}", current, total)

    def _run():
        try:
            result = loop.run(progress_callback=progress_cb)
            conv = result.convergence or {}
            reason = conv.get("reason", "unknown")
            pm.update(task_id, f"Deepening complete: {result.iterations} iterations, {reason}", 1, 1)
            bus.emit("task", {"task_id": task_id, "status": "completed"})
        except Exception as e:
            logger.error("Deepening loop failed: %s", e)
            pm.update(task_id, f"Deepening failed: {e}", 0, 1)
            bus.emit("task", {"task_id": task_id, "status": "failed"})
        finally:
            if _deepening_state.get(project_id) is run_state:
                _deepening_state.pop(project_id, None)

    t = threading.Thread(target=_run, daemon=True)
    run_state["thread"] = t
    t.start()
    return ok({"started": True, "task_id": task_id})


# ═════════════════════════════════════════════════════════════════
# Destroy (Graph & Index reset)
# ═════════════════════════════════════════════════════════════════

@router.delete("/projects/{project_id}/trace/destroy")
def trace_destroy_project(project_id: str) -> Dict[str, Any]:
    """Permanently delete all trace graph data for a project.

    Removes: structural graph, augmentation, inferred edges,
    epistemic enrichment, cluster modules — everything produced
    by the multi-pass pipeline.
    """
    from codrag.server import (
        _require_project_writable, _is_project_trace_building, _project_trace_indexes,
    )
    proj = _require_project_writable(project_id)

    # Refuse if any pipeline stage is currently running
    if _is_project_trace_building(project_id):
        raise ApiException(status_code=409, code="PIPELINE_RUNNING", message="Cannot destroy graph while trace build is running")

    for state_map, label in [
        (_deep_analysis_state, "deep analysis"),
        (_epistemic_state, "epistemic enrichment"),
        (_cluster_state, "cluster synthesis"),
        (_deepening_state, "deepening loop"),
    ]:
        state = state_map.get(project_id)
        if state and state.get("thread") and state["thread"].is_alive():
            raise ApiException(
                status_code=409,
                code="PIPELINE_RUNNING",
                message=f"Cannot destroy graph while {label} is running",
            )

    idx_dir = project_index_dir(proj)

    # Backup before delete when debug mode is on
    backup_path = _backup_files_if_debug(idx_dir, TRACE_FILES, "graph_reset")

    deleted: list[str] = []
    errors: list[str] = []

    for fname in TRACE_FILES:
        fp = idx_dir / fname
        if fp.exists():
            try:
                fp.unlink()
                deleted.append(fname)
            except Exception as e:
                errors.append(f"{fname}: {e}")

    # Clear in-memory caches
    _project_trace_indexes.pop(project_id, None)

    # Clear pipeline orchestrator state (cached file loggers, run history)
    try:
        from codrag.services.pipeline_orchestrator import pipeline_orchestrator
        pipeline_orchestrator.clear_project(project_id)
    except Exception:
        pass

    logger.info(
        "Destroyed trace graph for %s: deleted %d files, %d errors",
        project_id, len(deleted), len(errors),
    )
    result: Dict[str, Any] = {"deleted": deleted, "errors": errors}
    if backup_path:
        result["backup"] = backup_path
    return ok(result)


# ── Selective Reset (Developer Tools — Phase 47) ─────────────────

ATLAS_FILES = [
    "atlas.json",
    "atlas_prev.json",
    "atlas_segments_manifest.json",
    "atlas_routing.json",
    "atlas_routing_embeddings.npy",
]

GROUP_REASONING_FILES = [
    "trace_group_reasoning.jsonl",
]

DEEP_ENRICHMENT_FILES = [
    # Deep Reasoning (Epistemic)
    "trace_epistemic.jsonl",
    "trace_epistemic_manifest.json",
    # Group Reasoning
    "trace_group_reasoning.jsonl",
    # Module Synthesis
    "trace_modules.jsonl",
    # Atlas Building
    "atlas.json",
    "atlas_prev.json",
    "atlas_segments_manifest.json",
    "atlas_routing.json",
    "atlas_routing_embeddings.npy",
    # NOTE: Knowledge Embedding files (knowledge_documents.json, knowledge_embeddings.npy,
    # knowledge_manifest.json) are intentionally NOT deleted here because they are shared
    # with Fast Sync stage 5. The Deep Knowledge Embedding stage will rebuild them
    # automatically from the new enrichment data when it runs.
]


def _backup_files_if_debug(idx_dir, file_list: list, label: str) -> Optional[str]:
    """If developer_debug_mode is enabled, copy affected files to a timestamped backup dir.

    Returns the backup directory path (relative) if created, None otherwise.
    """
    import shutil
    from datetime import datetime
    try:
        from codrag.server import _load_ui_config
        ui_cfg = _load_ui_config()
        debug_on = ui_cfg.get("developer_debug_mode", False)
        logger.info("_backup_files_if_debug: developer_debug_mode=%s", debug_on)
        if not debug_on:
            return None
    except Exception as e:
        logger.warning("_backup_files_if_debug: failed to read config: %s", e)
        return None

    # Check if any files actually exist to backup
    existing = [idx_dir / f for f in file_list if (idx_dir / f).exists()]
    if not existing:
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = idx_dir / "backups" / f"{label.replace(' ', '_')}_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for fp in existing:
        try:
            shutil.copy2(fp, backup_dir / fp.name)
        except Exception as e:
            logger.warning("Backup failed for %s: %s", fp.name, e)

    logger.info("Debug backup: saved %d files to %s", len(existing), backup_dir.relative_to(idx_dir))
    return str(backup_dir.relative_to(idx_dir))


def _selective_delete(project_id: str, file_list: list, label: str) -> Dict[str, Any]:
    """Delete specific files for a project. Shared helper for selective resets.
    
    Uses _require_project (not _require_project_writable) so developer tools
    can reset data on inactive projects too.
    """
    from codrag.server import (
        _require_project, _is_project_trace_building, _project_trace_indexes,
    )
    proj = _require_project(project_id)

    if _is_project_trace_building(project_id):
        raise ApiException(status_code=409, code="PIPELINE_RUNNING", message=f"Cannot reset {label} while pipeline is running")

    for state_map, state_label in [
        (_deep_analysis_state, "deep analysis"),
        (_epistemic_state, "epistemic enrichment"),
        (_cluster_state, "cluster synthesis"),
        (_deepening_state, "deepening loop"),
    ]:
        state = state_map.get(project_id)
        if state and state.get("thread") and state["thread"].is_alive():
            raise ApiException(status_code=409, code="PIPELINE_RUNNING", message=f"Cannot reset {label} while {state_label} is running")

    idx_dir = project_index_dir(proj)

    # Backup before delete when debug mode is on
    backup_path = _backup_files_if_debug(idx_dir, file_list, label)

    deleted: list[str] = []
    errors: list[str] = []

    for fname in file_list:
        fp = idx_dir / fname
        if fp.exists():
            try:
                fp.unlink()
                deleted.append(fname)
            except Exception as e:
                errors.append(f"{fname}: {e}")

    # Invalidate in-memory trace cache so next load picks up the change
    _project_trace_indexes.pop(project_id, None)

    logger.info("Selective reset (%s) for %s: deleted %d files, %d errors", label, project_id, len(deleted), len(errors))
    result: Dict[str, Any] = {"deleted": deleted, "errors": errors}
    if backup_path:
        result["backup"] = backup_path
    return ok(result)


@router.delete("/projects/{project_id}/atlas/destroy")
def atlas_destroy(project_id: str) -> Dict[str, Any]:
    """Delete only the atlas data for a project."""
    return _selective_delete(project_id, ATLAS_FILES, "atlas")


@router.delete("/projects/{project_id}/group-reasoning/destroy")
def group_reasoning_destroy(project_id: str) -> Dict[str, Any]:
    """Delete only group reasoning data for a project."""
    return _selective_delete(project_id, GROUP_REASONING_FILES, "group reasoning")


@router.delete("/projects/{project_id}/deep-enrichment/destroy")
def deep_enrichment_destroy(project_id: str) -> Dict[str, Any]:
    """Delete all 6 deep enrichment stages for a project.

    Removes: epistemic, group reasoning, modules, atlas, and knowledge embedding.
    Preserves: structural graph, augmentation, inferred edges (fast sync stages).
    """
    return _selective_delete(project_id, DEEP_ENRICHMENT_FILES, "deep enrichment")


@router.delete("/projects/{project_id}/index/destroy")
def index_destroy_project(project_id: str) -> Dict[str, Any]:
    """Permanently delete ALL project data: embeddings, trace graph,
    knowledge index — full reset to a blank project.

    Removes everything produced by building, tracing, augmenting,
    enriching, clustering, and knowledge embedding.
    """
    from codrag.server import (
        _require_project_writable, _is_project_trace_building, _is_project_building,
        _project_build_lock, _project_build_threads,
        _project_indexes, _project_trace_indexes, _project_knowledge_indexes,
    )
    proj = _require_project_writable(project_id)

    # Refuse if anything is running
    if _is_project_trace_building(project_id):
        raise ApiException(status_code=409, code="PIPELINE_RUNNING", message="Cannot reset while trace build is running")

    # Check if a code-index build is running
    with _project_build_lock:
        thread = _project_build_threads.get(project_id)
        if thread and thread.is_alive():
            raise ApiException(status_code=409, code="PIPELINE_RUNNING", message="Cannot reset while index build is running")

    for state_map, label in [
        (_deep_analysis_state, "deep analysis"),
        (_epistemic_state, "epistemic enrichment"),
        (_cluster_state, "cluster synthesis"),
        (_deepening_state, "deepening loop"),
    ]:
        state = state_map.get(project_id)
        if state and state.get("thread") and state["thread"].is_alive():
            raise ApiException(
                status_code=409,
                code="PIPELINE_RUNNING",
                message=f"Cannot reset while {label} is running",
            )

    idx_dir = project_index_dir(proj)

    # Backup before delete when debug mode is on
    backup_path = _backup_files_if_debug(idx_dir, ALL_DATA_FILES, "full_reset")

    deleted: list[str] = []
    errors: list[str] = []

    for fname in ALL_DATA_FILES:
        fp = idx_dir / fname
        if fp.exists():
            try:
                fp.unlink()
                deleted.append(fname)
            except Exception as e:
                errors.append(f"{fname}: {e}")

    # Clear all in-memory caches
    _project_indexes.pop(project_id, None)
    _project_trace_indexes.pop(project_id, None)
    _project_knowledge_indexes.pop(project_id, None)

    logger.info(
        "Full reset for %s: deleted %d files, %d errors",
        project_id, len(deleted), len(errors),
    )
    result: Dict[str, Any] = {"deleted": deleted, "errors": errors}
    if backup_path:
        result["backup"] = backup_path
    return ok(result)
