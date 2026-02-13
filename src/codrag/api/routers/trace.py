"""
CoDRAG Trace & Enrichment Pipeline Router — Phase 23 Sprint 11
================================================================

**Origin:** Extracted from ``server.py`` (lines ~2217–3564).

**Endpoints moved here:**
  Trace CRUD:
    - GET  /projects/{id}/trace/status
    - POST /projects/{id}/trace/build
    - GET  /projects/{id}/trace/coverage
    - POST /projects/{id}/trace/ignore
    - GET  /projects/{id}/trace/search   (query-param style)
    - POST /projects/{id}/trace/search   (body style)
    - GET  /projects/{id}/trace/node/{node_id}
    - GET  /projects/{id}/trace/nodes/{node_id}
    - GET  /projects/{id}/trace/neighbors/{node_id}
    - GET  /projects/{id}/trace/nodes/{node_id}/neighbors

  Augmentation (Pass 1):
    - GET  /projects/{id}/augment/status
    - POST /projects/{id}/augment/run

  Deep Analysis (Pass 2):
    - GET  /projects/{id}/deep-analysis/status
    - POST /projects/{id}/deep-analysis/run
    - POST /projects/{id}/deep-analysis/cancel

  Epistemic Enrichment (Pass 2b):
    - GET  /projects/{id}/epistemic/status
    - POST /projects/{id}/epistemic/run

  Cluster/Module Synthesis (Pass 3):
    - GET  /projects/{id}/modules/status
    - POST /projects/{id}/modules/run

  Deepening Loop (Pass 4+):
    - GET  /projects/{id}/deepening/status
    - POST /projects/{id}/deepening/run

  Destroy:
    - DELETE /projects/{id}/trace/destroy
    - DELETE /projects/{id}/index/destroy

**State owned by this module:**
  - ``_deep_analysis_state``  — per-project thread tracking for deep analysis
  - ``_epistemic_state``      — per-project thread tracking for epistemic enrichment
  - ``_cluster_state``        — per-project thread tracking for cluster synthesis
  - ``_deepening_state``      — per-project thread tracking for deepening loop
  - ``TRACE_FILES``           — list of trace artifact filenames
  - ``INDEX_FILES``           — list of index artifact filenames
  - ``ALL_DATA_FILES``        — union of both

**Shared state accessed (from server.py):**
  - ``_require_project``               — project lookup with 404 handling
  - ``_project_trace_status``          — compute trace status dict
  - ``_get_project_trace_index``       — get/create per-project TraceIndex
  - ``_is_project_trace_building``     — check if trace build thread is alive
  - ``_start_project_trace_build``     — launch trace build in background
  - ``_get_project_index``             — get/create per-project CodeIndex
  - ``_is_project_building``           — check if index build thread is alive
  - ``_get_project_knowledge_index``   — get/create per-project KnowledgeIndex
  - ``_is_project_knowledge_building`` — check if knowledge build is running
  - ``_project_augment_status``        — read augmentation manifest
  - ``_load_ui_config``                — read global config for LLM slots
  - ``_get_llm_client_for_slot``       — create LLMClient from config
  - ``_get_registry``                  — project registry singleton
  - Cache dicts: ``_project_trace_indexes``, ``_project_indexes``,
    ``_project_knowledge_indexes``, ``_project_build_lock``, ``_project_build_threads``

**Phase 24 note (State Machines SM-4, SM-6):**
  This router contains the *entire* enrichment pipeline — currently managed
  with ad-hoc ``threading.Thread`` + dict state tracking.  SM-6 (Pipeline
  Orchestrator) will replace the 4 state dicts with a single
  ``PipelineOrchestrator`` owning a STAGE_DEPS DAG.  Each endpoint becomes
  a state transition request rather than a direct thread launch.
  SM-4 (Build Orchestrator) will own ``_start_project_trace_build`` and
  the build thread pool, replacing the global locks in server.py.
  The destroy endpoints will become reset transitions (→ Idle).
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok
from codrag.core.events import get_event_bus, get_progress_manager
from codrag.core.project_registry import project_index_dir
from codrag.core.trace import compute_trace_coverage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trace"])


# ── Module-level state (thread tracking) ─────────────────────────
# These were formerly globals in server.py.  Phase 24 (SM-6) will
# replace them with a PipelineOrchestrator per-project.

_deep_analysis_state: Dict[str, Dict[str, Any]] = {}
_epistemic_state: Dict[str, Dict[str, Any]] = {}
_cluster_state: Dict[str, Dict[str, Any]] = {}
_deepening_state: Dict[str, Dict[str, Any]] = {}


# ── Constants ────────────────────────────────────────────────────

TRACE_FILES = [
    "trace_manifest.json",
    "trace_nodes.jsonl",
    "trace_edges.jsonl",
    "trace_augmented.jsonl",
    "trace_augment_manifest.json",
    "trace_inferred_edges.jsonl",
    "trace_epistemic.jsonl",
    "trace_epistemic_manifest.json",
    "trace_modules.jsonl",
]

INDEX_FILES = [
    "documents.json",
    "embeddings.npy",
    "manifest.json",
    "fts.sqlite3",
    "knowledge_documents.json",
    "knowledge_embeddings.npy",
    "knowledge_manifest.json",
]

ALL_DATA_FILES = TRACE_FILES + INDEX_FILES


# ── Pydantic models ─────────────────────────────────────────────

class TraceSearchRequest(BaseModel):
    query: str
    kinds: Optional[List[str]] = None
    limit: int = 20


class TraceIgnoreRequest(BaseModel):
    action: str  # "add" | "remove"
    patterns: List[str]


class AugmentRequest(BaseModel):
    max_items: Optional[int] = None


class DeepAnalysisRequest(BaseModel):
    max_items: Optional[int] = None
    max_tokens: Optional[int] = None
    max_minutes: Optional[int] = None


class EpistemicRunRequest(BaseModel):
    max_items: Optional[int] = None


class DeepeningRunRequest(BaseModel):
    max_iterations: Optional[int] = 10
    batch_size: Optional[int] = 20


# ═════════════════════════════════════════════════════════════════
# Trace CRUD
# ═════════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/trace/status")
def trace_status_project(project_id: str) -> Dict[str, Any]:
    from codrag.server import _require_project, _project_trace_status
    proj = _require_project(project_id)
    return ok(_project_trace_status(proj))


@router.post("/projects/{project_id}/trace/build")
def build_trace_project(project_id: str) -> Dict[str, Any]:
    from codrag.server import (
        _require_project, _is_project_trace_building, _start_project_trace_build,
    )
    proj = _require_project(project_id)

    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    if not bool((trace_cfg or {}).get("enabled", False)):
        raise ApiException(
            status_code=409,
            code="TRACE_DISABLED",
            message="Trace is disabled for this project",
            hint="Enable trace in project settings and try again.",
        )

    if _is_project_trace_building(proj.id):
        raise ApiException(status_code=409, code="TRACE_BUILD_ALREADY_RUNNING", message="Trace build already running")

    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    include_globs = list(include_raw) if isinstance(include_raw, list) else None
    exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else None
    max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)

    if proj.mode == "embedded":
        if exclude_globs is None:
            exclude_globs = []
        if "**/.codrag/**" not in exclude_globs:
            exclude_globs.append("**/.codrag/**")

    started = _start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes)
    if not started:
        raise ApiException(status_code=409, code="TRACE_BUILD_ALREADY_RUNNING", message="Trace build already running")
    
    return ok({"started": True, "building": True})


@router.get("/projects/{project_id}/trace/coverage")
def trace_coverage_project(project_id: str) -> Dict[str, Any]:
    """Get trace coverage: traced, untraced, stale, and ignored files."""
    from codrag.server import _require_project, _is_project_trace_building
    proj = _require_project(project_id)

    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    if not bool((trace_cfg or {}).get("enabled", False)):
        raise ApiException(
            status_code=409,
            code="TRACE_DISABLED",
            message="Trace is disabled for this project",
            hint="Enable trace in project settings.",
        )

    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    include_globs = list(include_raw) if isinstance(include_raw, list) else None
    exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else None

    # User-configured trace ignore patterns (shown in the "Excluded" list)
    trace_ignore = (trace_cfg or {}).get("ignore_patterns", [])
    user_exclude_globs = [str(p) for p in trace_ignore] if isinstance(trace_ignore, list) else []

    max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)
    idx_dir = project_index_dir(proj)

    coverage = compute_trace_coverage(
        repo_root=Path(proj.path),
        index_dir=idx_dir,
        include_globs=include_globs,
        exclude_globs=exclude_globs,
        user_exclude_globs=user_exclude_globs,
        max_file_bytes=max_file_bytes,
    )
    coverage["building"] = _is_project_trace_building(proj.id)
    return ok(coverage)


@router.post("/projects/{project_id}/trace/ignore")
def update_trace_ignore(project_id: str, req: TraceIgnoreRequest) -> Dict[str, Any]:
    """Add or remove trace-specific ignore patterns."""
    from codrag.server import _require_project, _get_registry
    proj = _require_project(project_id)

    if req.action not in ("add", "remove"):
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="action must be 'add' or 'remove'")
    if not req.patterns:
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="patterns list is required")

    cfg = dict(proj.config or {})
    trace_cfg = dict(cfg.get("trace") or {})
    current_patterns: List[str] = list(trace_cfg.get("ignore_patterns") or [])

    if req.action == "add":
        for p in req.patterns:
            p = str(p).strip()
            if p and p not in current_patterns:
                current_patterns.append(p)
    else:
        remove_set = set(str(p).strip() for p in req.patterns)
        current_patterns = [p for p in current_patterns if p not in remove_set]

    trace_cfg["ignore_patterns"] = current_patterns
    cfg["trace"] = trace_cfg
    proj.config = cfg
    reg = _get_registry()
    reg.update(proj)

    return ok({"ignore_patterns": current_patterns})


@router.get("/projects/{project_id}/trace/search")
def search_trace_project(project_id: str, query: str, kind: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    from codrag.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)
    
    if not query.strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    if not bool((trace_cfg or {}).get("enabled", False)):
        raise ApiException(
            status_code=409,
            code="TRACE_DISABLED",
            message="Trace is disabled for this project",
            hint="Enable trace in project settings and build the trace index.",
        )
    
    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(
            status_code=409,
            code="TRACE_NOT_BUILT",
            message="Trace index has not been built yet",
            hint="Run a trace build first.",
        )
    
    if not trace_idx.is_loaded():
        trace_idx.load()
    
    results = trace_idx.search_nodes(query, kind=kind, limit=min(limit, 100))
    return ok({"nodes": results})


@router.post("/projects/{project_id}/trace/search")
def trace_search_project(project_id: str, req: TraceSearchRequest) -> Dict[str, Any]:
    from codrag.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)

    if not str(req.query or "").strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    if not bool((trace_cfg or {}).get("enabled", False)):
        raise ApiException(
            status_code=409,
            code="TRACE_DISABLED",
            message="Trace is disabled for this project",
            hint="Enable trace in project settings and build the trace index.",
        )

    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(
            status_code=409,
            code="TRACE_NOT_BUILT",
            message="Trace index has not been built yet",
            hint="Run a trace build first.",
        )

    if not trace_idx.is_loaded():
        trace_idx.load()

    hard_cap = 100
    limit = min(int(req.limit or 0) if req.limit is not None else 20, hard_cap)
    if limit <= 0:
        limit = 20

    nodes = trace_idx.search_nodes(req.query, kind=None, limit=hard_cap)
    if isinstance(req.kinds, list) and req.kinds:
        kinds = {str(k).strip() for k in req.kinds if isinstance(k, str) and k.strip()}
        if kinds:
            nodes = [n for n in nodes if str(n.get("kind") or "") in kinds]
    nodes = nodes[:limit]

    return ok({"nodes": nodes})


@router.get("/projects/{project_id}/trace/node/{node_id:path}")
@router.get("/projects/{project_id}/trace/nodes/{node_id:path}")
def get_trace_node(project_id: str, node_id: str) -> Dict[str, Any]:
    from codrag.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)

    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    if not bool((trace_cfg or {}).get("enabled", False)):
        raise ApiException(
            status_code=409,
            code="TRACE_DISABLED",
            message="Trace is disabled for this project",
            hint="Enable trace in project settings and build the trace index.",
        )
    
    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(status_code=409, code="TRACE_NOT_BUILT", message="Trace index has not been built yet")
    
    if not trace_idx.is_loaded():
        trace_idx.load()
    
    node = trace_idx.get_node(node_id)
    if node is None:
        raise ApiException(status_code=404, code="NODE_NOT_FOUND", message=f"Node not found: {node_id}")
    
    in_degree, out_degree = trace_idx.node_degree(node_id)
    return ok({"node": node, "in_degree": in_degree, "out_degree": out_degree})


@router.get("/projects/{project_id}/trace/neighbors/{node_id:path}")
@router.get("/projects/{project_id}/trace/nodes/{node_id:path}/neighbors")
def get_trace_node_neighbors(
    project_id: str,
    node_id: str,
    direction: str = "both",
    edge_kinds: Optional[List[str]] = Query(None),
    hops: int = 1,
    max_nodes: int = 25,
    max_edges: int = 50,
) -> Dict[str, Any]:
    from codrag.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)

    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    if not bool((trace_cfg or {}).get("enabled", False)):
        raise ApiException(
            status_code=409,
            code="TRACE_DISABLED",
            message="Trace is disabled for this project",
            hint="Enable trace in project settings and build the trace index.",
        )
    
    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(status_code=409, code="TRACE_NOT_BUILT", message="Trace index has not been built yet")
    
    if not trace_idx.is_loaded():
        trace_idx.load()
    
    node = trace_idx.get_node(node_id)
    if node is None:
        raise ApiException(status_code=404, code="NODE_NOT_FOUND", message=f"Node not found: {node_id}")
    
    edge_kinds_list: Optional[List[str]] = None
    if edge_kinds:
        cleaned: List[str] = []
        for v in edge_kinds:
            for part in str(v).split(","):
                p = part.strip()
                if p:
                    cleaned.append(p)
        edge_kinds_list = cleaned or None

    if edge_kinds_list is None:
        edge_kinds_list = ["imports"]

    neighbors = trace_idx.get_neighbors(
        node_id,
        direction=direction,
        edge_kinds=edge_kinds_list,
        max_nodes=min(max_nodes, 100),
    )

    edges: List[Dict[str, Any]] = []
    seen_edges: set[str] = set()
    for e in list(neighbors.get("in_edges") or []) + list(neighbors.get("out_edges") or []):
        eid = str(e.get("id") or "")
        if eid and eid in seen_edges:
            continue
        if eid:
            seen_edges.add(eid)
        edges.append(e)

    max_edges_cap = 200
    edges = edges[: min(int(max_edges), max_edges_cap)] if int(max_edges) > 0 else edges[:50]

    nodes_out: List[Dict[str, Any]] = []
    seen_nodes: set[str] = set()
    for n in [node] + list(neighbors.get("in_nodes") or []) + list(neighbors.get("out_nodes") or []):
        nid = str((n or {}).get("id") or "")
        if not nid or nid in seen_nodes:
            continue
        seen_nodes.add(nid)
        nodes_out.append(n)

    return ok({"nodes": nodes_out, "edges": edges})


# ═════════════════════════════════════════════════════════════════
# Augmentation (Pass 1)
# ═════════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/augment/status")
def augment_status_project(project_id: str) -> Dict[str, Any]:
    """Get augmentation status for a project."""
    from codrag.server import _require_project, _project_augment_status
    proj = _require_project(project_id)
    return ok(_project_augment_status(proj))


@router.post("/projects/{project_id}/augment/run")
def augment_run_project(project_id: str, req: AugmentRequest) -> Dict[str, Any]:
    """Run LLM augmentation on trace nodes (Phase 1, Step 2)."""
    from codrag.server import _require_project, _get_llm_client_for_slot
    proj = _require_project(project_id)

    llm_client = _get_llm_client_for_slot("small")
    if not llm_client:
        raise ApiException(
            status_code=409,
            code="NO_SMALL_MODEL",
            message="No small model configured",
            hint="Configure a Small Model in AI Models settings.",
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
    from codrag.server import _require_project, _get_llm_client_for_slot, _load_ui_config
    proj = _require_project(project_id)

    # Prevent double-run
    state = _deep_analysis_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        raise ApiException(
            status_code=409,
            code="ALREADY_RUNNING",
            message="Deep analysis is already running for this project",
        )

    llm_client = _get_llm_client_for_slot("large")
    if not llm_client:
        # Fall back to fast/small model if no large model configured
        llm_client = _get_llm_client_for_slot("small")
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
    from codrag.server import _require_project
    _require_project(project_id)
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

    if not epistemic_path.exists():
        result: Dict[str, Any] = {
            "enabled": False,
            "enriched_nodes": 0,
            "total_file_nodes": 0,
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
            "avg_confidence": round(total_conf / count, 3) if count else 0.0,
        }

    # Inject live running state
    state = _epistemic_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        result["running"] = True
        result["progress_current"] = state.get("current", 0)
        result["progress_total"] = state.get("total", 0)
    else:
        result["running"] = False

    return ok(result)


@router.post("/projects/{project_id}/epistemic/run")
def epistemic_run_project(project_id: str, req: EpistemicRunRequest) -> Dict[str, Any]:
    """Run epistemic enrichment (Pass 2) using the large model."""
    from codrag.server import _require_project, _get_llm_client_for_slot
    proj = _require_project(project_id)

    state = _epistemic_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        raise ApiException(status_code=409, code="ALREADY_RUNNING", message="Epistemic enrichment already running")

    llm_client = _get_llm_client_for_slot("large")
    if not llm_client:
        llm_client = _get_llm_client_for_slot("small")
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
        result: Dict[str, Any] = {"enabled": False, "module_count": 0, "total_files_clustered": 0}
    else:
        count = 0
        total_files = 0
        with open(modules_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        d = json.loads(line)
                        count += 1
                        total_files += int(d.get("file_count", 0))
                    except Exception:
                        pass
        result = {"enabled": True, "module_count": count, "total_files_clustered": total_files}

    state = _cluster_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        result["running"] = True
    else:
        result["running"] = False

    return ok(result)


@router.post("/projects/{project_id}/modules/run")
def modules_run_project(project_id: str) -> Dict[str, Any]:
    """Run cluster synthesis (Pass 3) using the large model."""
    from codrag.server import _require_project, _get_llm_client_for_slot
    proj = _require_project(project_id)

    state = _cluster_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        raise ApiException(status_code=409, code="ALREADY_RUNNING", message="Cluster synthesis already running")

    llm_client = _get_llm_client_for_slot("large")
    if not llm_client:
        llm_client = _get_llm_client_for_slot("small")
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

    # Compute epistemic scores to get convergence info
    result: Dict[str, Any] = {"running": False}
    try:
        from codrag.core import EpistemicEnricher, LLMClient
        enricher = EpistemicEnricher(
            llm=LLMClient("http://localhost:11434", "none"),
            repo_root=Path(proj.path),
            index_dir=idx_dir,
        )
        scores = enricher.compute_all_scores()
        if scores:
            composites = [s.composite for s in scores.values()]
            settled = sum(1 for c in composites if c >= 0.95)
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

    return ok(result)


@router.post("/projects/{project_id}/deepening/run")
def deepening_run_project(project_id: str, req: DeepeningRunRequest) -> Dict[str, Any]:
    """Run continuous deepening loop (Pass 4+)."""
    from codrag.server import _require_project, _get_llm_client_for_slot
    proj = _require_project(project_id)

    state = _deepening_state.get(project_id)
    if state and state.get("thread") and state["thread"].is_alive():
        raise ApiException(status_code=409, code="ALREADY_RUNNING", message="Deepening loop already running")

    llm_client = _get_llm_client_for_slot("large")
    if not llm_client:
        llm_client = _get_llm_client_for_slot("small")
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
        _require_project, _is_project_trace_building, _project_trace_indexes,
    )
    proj = _require_project(project_id)

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

    logger.info(
        "Destroyed trace graph for %s: deleted %d files, %d errors",
        project_id, len(deleted), len(errors),
    )
    return ok({"deleted": deleted, "errors": errors})


@router.delete("/projects/{project_id}/index/destroy")
def index_destroy_project(project_id: str) -> Dict[str, Any]:
    """Permanently delete ALL project data: embeddings, trace graph,
    knowledge index — full reset to a blank project.

    Removes everything produced by building, tracing, augmenting,
    enriching, clustering, and knowledge embedding.
    """
    from codrag.server import (
        _require_project, _is_project_trace_building, _is_project_building,
        _project_build_lock, _project_build_threads,
        _project_indexes, _project_trace_indexes, _project_knowledge_indexes,
    )
    proj = _require_project(project_id)

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
    return ok({"deleted": deleted, "errors": errors})
