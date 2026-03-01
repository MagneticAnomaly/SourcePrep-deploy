"""
CoDRAG Projects Router — Phase 23 Sprint 15
=============================================

**Origin:** Extracted from ``server.py`` (lines ~694–1916 in the pre-extraction file).

**Endpoints moved here:**
  Project CRUD:
    - GET    /projects
    - POST   /projects
    - GET    /projects/{id}
    - PUT    /projects/{id}
    - DELETE /projects/{id}

  Project Config:
    - PUT  /projects/{id}/path_weights
    - GET  /projects/{id}/path_weights

  Project Status & Activity:
    - GET  /projects/{id}/status
    - GET  /projects/{id}/activity
    - GET  /projects/{id}/coverage

  File Operations:
    - GET  /projects/{id}/file
    - GET  /projects/{id}/files
    - GET  /projects/{id}/roots
    - GET  /projects/{id}/detect-stack

  Watch:
    - POST /projects/{id}/watch/start
    - POST /projects/{id}/watch/stop
    - GET  /projects/{id}/watch/status

  Build & Search:
    - POST /projects/{id}/build
    - POST /projects/{id}/search
    - POST /projects/{id}/context

**Shared state accessed (from server.py):**
  - ``_require_project``          — project lookup
  - ``_get_registry``             — project registry singleton
  - ``_project_to_dict``          — project serialization
  - ``_project_index_status``     — index status dict
  - ``_project_trace_status``     — trace status dict
  - ``_get_project_index``        — per-project CodeIndex (via BuildManager)
  - ``_get_project_trace_index``  — per-project TraceIndex (via BuildManager)
  - ``_is_project_building``      — build thread check (via BuildManager)
  - ``_start_project_build``      — launch build (via BuildManager)
  - ``_start_project_trace_build``— launch trace build (via BuildManager)
  - ``_get_project_watcher``      — file watcher lookup
  - ``_get_project_watcher_status``— watcher status dict
  - ``_project_activity_payload`` — activity data
  - ``_build_coverage_tree``      — coverage tree builder
  - ``_DEFAULT_UI_CONFIG``        — config defaults
  - ``_config``                   — CLI config
  - ``_project_watchers``         — watcher dict
  - ``_project_indexes``          — index cache (via BuildManager)
  - ``_project_trace_indexes``    — trace cache (via BuildManager)
  - ``_project_build_lock``       — build lock (via BuildManager)
  - ``_project_build_threads``    — build threads (via BuildManager)
  - ``_project_last_build_result``— build results (via BuildManager)
  - ``_project_last_build_error`` — build errors (via BuildManager)
  - ``_project_trace_build_lock`` — trace lock (via BuildManager)
  - ``_project_trace_build_threads``— trace threads (via BuildManager)

**Phase 24 note (State Machines SM-1, SM-4, SM-5):**
  SM-4 (Build Orchestrator) will own the ``/build`` endpoint — it becomes
  a transition request (IDLE → QUEUED → BUILDING) rather than a direct
  thread launch.  SM-5 (AutoRebuildWatcher) will formalize the watch
  start/stop into explicit WatcherPhase transitions.  The ``/status``
  endpoint will read directly from SM-4 and SM-5 state rather than
  querying locks and threads.
"""

from __future__ import annotations

import fnmatch
import logging
import re as _re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok
from codrag.core.feature_gate import (
    License, get_license, get_feature_limit, require_feature, FeatureGateError,
)
from codrag.core.project_registry import (
    ProjectAlreadyExists, ProjectNotFound, project_index_dir,
)
from codrag.core.repo_policy import (
    load_repo_policy, policy_path_for_index, write_repo_policy,
    _normalize_path_weights,
)
from codrag.core.repo_profile import scan_for_presets, STACK_PRESETS, DEFAULT_EXCLUDE_DIR_NAMES

from codrag.core.watcher import AutoRebuildWatcher
from codrag.core import LinguaCompressor, NoopCompressor

logger = logging.getLogger(__name__)

# ── Phase 34e F: Query preprocessing (now in core/query.py, Refactor 2 GAP-3) ──
from codrag.core.query import preprocess_query as _preprocess_query  # noqa: E402


router = APIRouter(tags=["projects"])


def _srv():
    """Lazy import of server module to avoid circular imports."""
    import codrag.server as _s
    return _s


def _get_project_globs(proj, *, use_defaults: bool = True) -> Tuple[List[str], List[str]]:
    """Extract include/exclude globs from project config (Refactor 2, GAP-9).

    Eliminates repeated 6-line boilerplate across watch, coverage, file,
    and search endpoints.

    Args:
        proj: Project object with ``.config`` and ``.mode`` attributes.
        use_defaults: If True, fall back to ``_DEFAULT_UI_CONFIG`` when the
            project has no globs configured.  Set False when callers handle
            their own defaults (e.g. build/search which merge with policy).

    Returns:
        (include_globs, exclude_globs) — both guaranteed to be lists.
    """
    cfg = proj.config or {}
    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None

    if use_defaults:
        defaults = _srv()._DEFAULT_UI_CONFIG
        include_globs = list(include_raw) if isinstance(include_raw, list) else list(defaults.get("include_globs") or [])
        exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else list(defaults.get("exclude_globs") or [])
    else:
        include_globs = list(include_raw) if isinstance(include_raw, list) else []
        exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else []

    # Embedded-mode projects must always exclude their own data directory
    if getattr(proj, "mode", None) == "embedded":
        if "**/.codrag/**" not in exclude_globs:
            exclude_globs.append("**/.codrag/**")

    return include_globs, exclude_globs


# ── Pydantic models ─────────────────────────────────────────────

class BuildRequest(BaseModel):
    project_root: Optional[str] = None
    repo_root: Optional[str] = None
    roots: Optional[List[str]] = None
    include_globs: Optional[List[str]] = None
    exclude_globs: Optional[List[str]] = None
    max_file_bytes: Optional[int] = None
    hard_limit_bytes: Optional[int] = None
    use_gitignore: bool = False
    included_paths: Optional[List[str]] = None


class PolicyRequest(BaseModel):
    repo_root: Optional[str] = None
    force: bool = False


class WatchRequest(BaseModel):
    repo_root: Optional[str] = None
    debounce_ms: Optional[int] = None
    min_rebuild_gap_ms: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    k: int = 8
    min_score: float = 0.15
    score_drop_ratio: float = 0.4
    mmr_lambda: float = 0.7
    exclude_paths: List[str] = []


class ContextRequest(BaseModel):
    query: str = ""  # Phase 34 C4: optional — empty triggers ambient context mode
    k: int = 5
    max_chars: int = 12000  # Phase 34c E2: increased from 6000 — LOD compression means more files fit
    include_sources: bool = True
    include_scores: bool = False
    min_score: float = 0.15
    score_drop_ratio: float = 0.4
    mmr_lambda: float = 0.7
    exclude_paths: List[str] = []
    structured: bool = False
    trace_expand: bool = True  # Follow trace edges to include structurally related code (Phase 34: on by default)
    trace_max_chars: int = 4000  # Phase 34c B2: increased from 2000 — trace neighbors are LOD-compressed
    compression: str = "none"  # "none" | "lingua" | "lod"
    compression_level: str = "standard"  # "light" | "standard" | "aggressive"
    compression_target_chars: Optional[int] = None
    compression_timeout_s: float = 30.0
    include_atlas: bool = False  # Explicit opt-in: prepend atlas text to context. Routing (Phase 29B) handles segment selection automatically; atlas text is primarily accessed via the codrag_atlas tool.


class ChunkRequest(BaseModel):
    chunk_id: str


class AddProjectRequest(BaseModel):
    path: str
    name: Optional[str] = None
    mode: str = "standalone"
    index_path: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    path_weights: Optional[Dict[str, float]] = None
    touch: bool = True


class PathWeightsRequest(BaseModel):
    path_weights: Dict[str, float]


class IncludedPathsRequest(BaseModel):
    included_paths: List[str]


class DetectStackResponse(BaseModel):
    recommended_globs: List[str]
    detected_presets: List[str]
    all_presets: Dict[str, List[str]]


# ── Endpoints ────────────────────────────────────────────────────

# =============================================================================
# Project Endpoints
# =============================================================================

@router.get("/projects")
def list_projects() -> Dict[str, Any]:
    reg = _srv()._get_registry()
    projects: List[Dict[str, Any]] = []
    
    # We need to use project_to_dict to ensure activity_status is injected correctly
    for p in reg.list_projects():
        projects.append(_srv()._project_to_dict(p))
        
    return ok({"projects": projects, "total": len(projects)})


@router.post("/projects")
def add_project(req: AddProjectRequest) -> Dict[str, Any]:
    if req.mode not in ("standalone", "embedded", "custom"):
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message=f"Invalid mode: {req.mode}")

    # Check project count limit for current tier
    reg = _srv()._get_registry()
    existing_count = len(reg.list_projects())
    max_projects = get_feature_limit("projects_max")
    if existing_count >= max_projects:
        lic = get_license()
        raise FeatureGateError(
            feature="projects_max",
            current_tier=License._display_tier(lic.tier),
            required_tier="pro",
        )

    p = Path(str(req.path)).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ApiException(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"Path does not exist: {p}",
        )

    # Validate index_path for custom mode
    custom_index_path: Optional[str] = None
    if req.mode == "custom":
        if not req.index_path:
            raise ApiException(
                status_code=400,
                code="VALIDATION_ERROR",
                message="index_path is required for custom mode",
            )
        try:
            ip = Path(req.index_path).expanduser().resolve()
            # We don't necessarily require it to exist yet (we can create it), 
            # but maybe we should ensure parent exists or it's a valid path.
            # For now just resolving it is enough check for basic validity.
            custom_index_path = str(ip)
        except Exception as e:
            raise ApiException(
                status_code=400,
                code="VALIDATION_ERROR",
                message=f"Invalid index_path: {e}",
            )

    # Determine defaults based on tier
    lic = get_license()
    # Auto-rebuild is enabled by default for Monthly tier and above
    auto_rebuild_default = lic.tier >= 1  # Tier.MONTHLY = 1

    reg = _srv()._get_registry()
    default_cfg: Dict[str, Any] = {
        "include_globs": list(_srv()._DEFAULT_UI_CONFIG.get("include_globs") or []),
        "exclude_globs": list(_srv()._DEFAULT_UI_CONFIG.get("exclude_globs") or []),
        "max_file_bytes": int(_srv()._DEFAULT_UI_CONFIG.get("max_file_bytes") or 500_000),
        "hard_limit_bytes": int(_srv()._DEFAULT_UI_CONFIG.get("hard_limit_bytes") or 100_000_000),
        "trace": {"enabled": True},  # Cross-reference on by default for all tiers
        "auto_rebuild": {
            "enabled": auto_rebuild_default,
            "debounce_ms": 5000,
        },
    }
    
    if req.mode == "embedded":
        if "**/.codrag/**" not in default_cfg["exclude_globs"]:
            default_cfg["exclude_globs"].append("**/.codrag/**")
    
    # Store custom index path in config if applicable
    if custom_index_path:
        default_cfg["index_path"] = custom_index_path

    if (_srv()._DEFAULT_UI_CONFIG.get("auto_rebuild") or {}).get("debounce_ms") is not None:
        default_cfg["auto_rebuild"]["debounce_ms"] = int(
            (_srv()._DEFAULT_UI_CONFIG.get("auto_rebuild") or {}).get("debounce_ms")
        )

    # Auto-detect stack presets to populate include_globs
    try:
        detected = scan_for_presets(p)
        if detected:
            logger.info(f"Auto-detected stack presets for {p.name}: {detected}")
            detected_globs = []
            for preset in detected:
                detected_globs.extend(STACK_PRESETS.get(preset, []))
            
            # Merge unique into include_globs
            current_globs = set(default_cfg["include_globs"])
            for g in detected_globs:
                if g not in current_globs:
                    default_cfg["include_globs"].append(g)
                    current_globs.add(g)
    except Exception as e:
        logger.warning(f"Failed to auto-detect stack presets: {e}")

    try:
        proj = reg.add_project(path=str(p), name=req.name, mode=req.mode, config=default_cfg)
    except ProjectAlreadyExists:
        raise ApiException(
            status_code=409,
            code="PROJECT_ALREADY_EXISTS",
            message=f"A project already exists at '{p}'",
            hint="Use a different path or remove the existing project first.",
        )

    return ok({"project": _srv()._project_to_dict(proj)})


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    return ok({"project": _srv()._project_to_dict(proj)})


@router.put("/projects/{project_id}")
def update_project(project_id: str, req: UpdateProjectRequest) -> Dict[str, Any]:
    reg = _srv()._get_registry()

    # Detect activity toggle: compare old config.active with new config.active
    old_proj = _srv()._require_project(project_id)
    old_active = (old_proj.config or {}).get("active", True)
    new_active = old_active  # default: unchanged
    if req.config and "active" in req.config:
        new_active = bool(req.config["active"])

    try:
        updated = reg.update_project(
            project_id, 
            name=req.name, 
            config=req.config,
            touch=req.touch,
        )
    except ProjectNotFound:
        raise ApiException(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message=f"Project with ID '{project_id}' not found",
            hint="Add the project first or select an existing project.",
        )

    if req.path_weights is not None:
        updated = _persist_path_weights(updated, req.path_weights)

    # ── React to activity toggle ──────────────────────────────────
    if old_active and not new_active:
        # DEACTIVATED: stop watcher + cancel pipelines
        _deactivate_project(project_id)
    elif not old_active and new_active:
        # ACTIVATED: start watcher if auto mode is configured
        _activate_project(updated)

    return ok({"project": _srv()._project_to_dict(updated)})


@router.put("/projects/{project_id}/path_weights")
def update_path_weights(project_id: str, req: PathWeightsRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    updated = _persist_path_weights(proj, req.path_weights)
    return ok({"project": _srv()._project_to_dict(updated), "path_weights": updated.config.get("path_weights", {})})


@router.get("/projects/{project_id}/path_weights")
def get_path_weights(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    pw = proj.config.get("path_weights", {})
    return ok({"path_weights": pw})


def _deactivate_project(project_id: str) -> None:
    """Stop watcher and cancel all pipelines for a project being deactivated."""
    # Stop file watcher
    watcher = _srv()._project_watchers.pop(project_id, None)
    if watcher is not None:
        watcher.stop()
        logger.info("Stopped watcher for deactivated project %s", project_id)

    # Cancel both pipeline groups
    try:
        from codrag.services.pipeline_orchestrator import pipeline_orchestrator
        cancelled_fast = pipeline_orchestrator.cancel_fast_sync(project_id)
        cancelled_deep = pipeline_orchestrator.cancel_deep_enrichment(project_id)
        if cancelled_fast or cancelled_deep:
            logger.info(
                "Cancelled pipelines for deactivated project %s (fast=%s, deep=%s)",
                project_id, cancelled_fast, cancelled_deep,
            )
    except Exception as exc:
        logger.warning("Failed to cancel pipelines for %s: %s", project_id, exc)


def _activate_project(proj: Project) -> None:
    """Start watcher and trigger auto-sync for a project being activated."""
    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    trace_enabled = bool((trace_cfg or {}).get("enabled", False))
    fast_sync_auto = bool(cfg.get("fast_sync_auto", False))

    # Start watcher if fast_sync is set to auto
    if fast_sync_auto:
        try:
            start_project_watch(proj.id)
            logger.info("Started watcher for activated project %s", proj.id)
        except Exception as exc:
            logger.warning("Failed to start watcher for %s: %s", proj.id, exc)

    # Trigger fast sync if trace is enabled and auto mode
    if trace_enabled and fast_sync_auto:
        try:
            from codrag.services.pipeline_orchestrator import pipeline_orchestrator
            pipeline_orchestrator.run_fast_sync(proj.id)
            logger.info("Triggered fast sync for activated project %s", proj.id)
        except Exception as exc:
            logger.warning("Failed to trigger fast sync for %s: %s", proj.id, exc)


def _persist_path_weights(proj: Project, raw_weights: Dict[str, float]) -> Project:
    """Normalize and persist path_weights to project config AND repo_policy.json."""
    normalized = _normalize_path_weights(raw_weights)

    # Update project config in SQLite
    reg = _srv()._get_registry()
    new_config = dict(proj.config)
    new_config["path_weights"] = normalized
    updated = reg.update_project(proj.id, config=new_config)

    # Also persist to repo_policy.json on disk so next build picks it up
    idx_dir = project_index_dir(proj)
    pp = policy_path_for_index(idx_dir)
    policy = load_repo_policy(pp)
    if policy is not None:
        policy["path_weights"] = normalized
        write_repo_policy(pp, policy)

    # Hot-update the in-memory manifest so searches use new weights immediately
    idx = _srv()._project_indexes.get(proj.id)
    if idx is not None and idx._manifest:
        cfg = idx._manifest.get("config")
        if isinstance(cfg, dict):
            cfg["path_weights"] = normalized

    return updated


# ── Included Paths (Knowledge Scope) ─────────────────────────

@router.put("/projects/{project_id}/included_paths")
def update_included_paths(project_id: str, req: IncludedPathsRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    updated = _persist_included_paths(proj, req.included_paths)
    return ok({
        "project": _srv()._project_to_dict(updated),
        "included_paths": updated.config.get("included_paths", []),
    })


@router.get("/projects/{project_id}/included_paths")
def get_included_paths(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    paths = proj.config.get("included_paths", [])
    return ok({"included_paths": paths})


def _persist_included_paths(proj, paths: List[str]):
    """Persist included_paths to project config in SQLite."""
    # Deduplicate and sort for deterministic storage
    normalized = sorted(set(str(p) for p in paths if p))

    reg = _srv()._get_registry()
    new_config = dict(proj.config)
    new_config["included_paths"] = normalized
    updated = reg.update_project(proj.id, config=new_config)
    return updated


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, purge: bool = False) -> Dict[str, Any]:
    reg = _srv()._get_registry()
    try:
        reg.remove_project(project_id, purge=bool(purge))
    except ProjectNotFound:
        raise ApiException(
            status_code=404,
            code="PROJECT_NOT_FOUND",
            message=f"Project with ID '{project_id}' not found",
            hint="Add the project first or select an existing project.",
        )

    _srv()._project_indexes.pop(project_id, None)
    _srv()._project_trace_indexes.pop(project_id, None)
    with _srv()._project_build_lock:
        _srv()._project_build_threads.pop(project_id, None)
        _srv()._project_last_build_result.pop(project_id, None)
        _srv()._project_last_build_error.pop(project_id, None)
    with _srv()._project_trace_build_lock:
        _srv()._project_trace_build_threads.pop(project_id, None)

    return ok({"removed": True, "purged": bool(purge)})


@router.get("/projects/{project_id}/status")
def get_project_status(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    idx = _srv()._get_project_index(proj)

    watch = _srv()._get_project_watcher_status(proj)

    # Mtime-based staleness check — works even without the watcher (Manual mode)
    mtime_check = _srv()._check_index_staleness(proj, idx)
    watcher_stale = bool(watch.get("stale", False))
    mtime_stale = bool(mtime_check.get("is_stale", False))

    # Stale if either the watcher or the mtime check detects changes
    is_stale = watcher_stale or mtime_stale
    stale_since = watch.get("stale_since") or mtime_check.get("stale_since")

    # Phase 39: Observation stats for dashboard health panel
    obs_stats = None
    try:
        from codrag.services.observation_store import observation_store
        obs_stats = observation_store.get_stats(project_id)
    except Exception:
        pass  # Store not initialized or unavailable

    data = {
        "building": _srv()._is_project_building(proj.id),
        "stale": is_stale,
        "stale_since": stale_since,
        "stale_count": mtime_check.get("stale_count", 0),
        "index": _srv()._project_index_status(idx, _srv()._project_last_build_error.get(proj.id)),
        "trace": _srv()._project_trace_status(proj),
        "watch": watch,
        "sync": _srv()._get_project_sync_status(proj),
    }
    if obs_stats and obs_stats.get("total", 0) > 0:
        data["observations"] = obs_stats
    return ok(data)


@router.post("/projects/{project_id}/watch/start")
def start_project_watch(
    project_id: str,
    debounce_ms: int = Query(5000, ge=500, le=60000),
    min_gap_ms: int = Query(2000, ge=500, le=30000),
) -> Dict[str, Any]:
    """Enable auto-rebuild watcher for a project."""
    require_feature("auto_rebuild")
    
    from codrag.services.project_helpers import is_over_project_limit
    if is_over_project_limit():
        raise ApiException(
            status_code=403,
            code="PROJECT_LIMIT_EXCEEDED",
            message="Cannot start watcher: Project limit exceeded for current tier",
            hint="Upgrade your plan or remove projects to resume syncing."
        )

    from codrag.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)
    idx = _srv()._get_project_index(proj)
    
    # Stop existing watcher if any
    existing = _srv()._project_watchers.get(proj.id)
    if existing is not None:
        existing.stop()
    
    def trigger_build(paths: List[str]) -> bool:
        from codrag.services.project_helpers import is_over_project_limit
        if is_over_project_limit():
            logger.info("Auto-rebuild skipped for %s — project limit exceeded", proj.id)
            return False

        include_globs, exclude_globs = _get_project_globs(proj, use_defaults=False)
        # Pass None instead of [] so downstream build() applies its own policy defaults
        include_globs = include_globs or None
        exclude_globs = exclude_globs or None
        cfg = proj.config or {}
        max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)
        hard_limit_bytes = int((cfg.get("hard_limit_bytes") or 100_000_000) if isinstance(cfg, dict) else 100_000_000)
        included_paths = cfg.get("included_paths") if isinstance(cfg, dict) else None

        # Team Sync: if a remote index exists, write only changed files
        # to local_deltas/ instead of rebuilding the entire main index.
        if _srv()._has_remote_index(proj):
            started = _srv()._start_project_delta_build(
                proj, paths, include_globs, exclude_globs,
                max_file_bytes, hard_limit_bytes,
            )
        else:
            started = _srv()._start_project_build(proj, None, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, included_paths=included_paths)

        # Phase 24: If auto_fast_sync is gated and allowed, trigger
        # the pipeline orchestrator for trace stages instead of raw build.
        from codrag.core.feature_gate import check_feature
        trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
        trace_enabled = bool((trace_cfg or {}).get("enabled", False))

        if trace_enabled and check_feature("auto_fast_sync"):
            try:
                from codrag.services.pipeline_orchestrator import pipeline_orchestrator
                pipeline_orchestrator.run_fast_sync(proj.id)
            except Exception:
                # Fallback to legacy trace build
                _srv()._start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes, hard_limit_bytes=hard_limit_bytes)
        elif trace_enabled:
            _srv()._start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes, hard_limit_bytes=hard_limit_bytes)

        return started
    
    def is_building() -> bool:
        if _srv()._is_project_building(proj.id) or _srv()._is_project_trace_building(proj.id):
            return True
        # Also treat active pipeline runs as "building" so the watcher
        # waits instead of repeatedly trying to trigger builds.
        try:
            from codrag.services.pipeline_orchestrator import pipeline_orchestrator as _po
            po_status = _po.status(proj.id)
            fast_phase = (po_status.get("fast_sync") or {}).get("phase")
            deep_phase = (po_status.get("deep_enrichment") or {}).get("phase")
            if fast_phase == "running" or deep_phase == "running":
                return True
        except Exception:
            pass
        return False
    
    watcher = AutoRebuildWatcher(
        repo_root=Path(proj.path),
        index_dir=idx.index_dir,
        on_trigger_build=trigger_build,
        is_building=is_building,
        debounce_ms=debounce_ms,
        min_rebuild_gap_ms=min_gap_ms,
    )
    watcher.start()
    _srv()._project_watchers[proj.id] = watcher
    
    return ok({"enabled": True, "state": watcher.status()["state"]})


@router.post("/projects/{project_id}/watch/stop")
def stop_project_watch(project_id: str) -> Dict[str, Any]:
    """Disable auto-rebuild watcher for a project."""
    proj = _srv()._require_project(project_id)
    
    watcher = _srv()._project_watchers.pop(proj.id, None)
    if watcher is not None:
        watcher.stop()
    
    return ok({"enabled": False, "state": "disabled"})


@router.get("/projects/{project_id}/watch/status")
def get_project_watch_status(project_id: str) -> Dict[str, Any]:
    """Get watcher status for a project."""
    proj = _srv()._require_project(project_id)
    return ok(_srv()._get_project_watcher_status(proj))


@router.get("/projects/{project_id}/activity")
def get_project_activity(project_id: str, weeks: int = Query(12, ge=1, le=52)) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    data = _srv()._project_activity_payload(proj, int(weeks))
    return ok(data)


@router.get("/projects/{project_id}/coverage")
def get_project_coverage(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    include_globs, exclude_globs = _get_project_globs(proj)

    repo_root = Path(proj.path).expanduser().resolve()
    if not repo_root.exists():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    tree = _srv()._build_coverage_tree(repo_root, include_globs, exclude_globs)
    return ok({"tree": tree})


@router.get("/projects/{project_id}/file")
def get_project_file_content(project_id: str, path: str = Query(..., min_length=1)) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    include_globs, exclude_globs = _get_project_globs(proj)
    cfg = proj.config or {}
    max_file_bytes = int((cfg.get("max_file_bytes") or 400_000) if isinstance(cfg, dict) else 400_000)

    repo_root = Path(proj.path).expanduser().resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    rel_path = Path(str(path).strip().lstrip("/"))
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ApiException(
            status_code=400,
            code="INVALID_PATH",
            message="Invalid file path",
            hint="Provide a repo-root-relative path without '..' segments.",
        )

    rel_str = str(rel_path)

    def _glob_match(rel: str, pat: str) -> bool:
        rel = rel.replace("\\", "/")
        pat = str(pat or "")
        if not pat:
            return False
        if fnmatch.fnmatch(rel, pat):
            return True
        if pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:]):
            return True
        return False

    def _matches_any(rel: str, patterns: List[str]) -> bool:
        for pat in patterns:
            try:
                if _glob_match(rel, str(pat)):
                    return True
            except Exception:
                continue
        return False

    if not _matches_any(rel_str, include_globs):
        raise ApiException(
            status_code=403,
            code="FILE_NOT_INCLUDED",
            message="File is not included by project policy",
            hint="Update include_globs to allow this file.",
        )

    if _matches_any(rel_str, exclude_globs):
        raise ApiException(
            status_code=403,
            code="FILE_EXCLUDED",
            message="File is excluded by project policy",
            hint="Update exclude_globs to allow this file.",
        )

    abs_path = (repo_root / rel_path).resolve()
    # SECURITY: Prevent Path Traversal by ensuring the resolved absolute path starts with the resolved repo_root
    try:
        abs_path.relative_to(repo_root)
    except ValueError:
        raise ApiException(
            status_code=400,
            code="INVALID_PATH",
            message="Invalid file path",
            hint="Provide a repo-root-relative path.",
        )

    if not abs_path.is_relative_to(repo_root):
        raise ApiException(
            status_code=400,
            code="INVALID_PATH",
            message="Invalid file path",
            hint="Provide a repo-root-relative path.",
        )

    if not abs_path.exists() or not abs_path.is_file():
        raise ApiException(status_code=404, code="FILE_NOT_FOUND", message="File not found")

    size = abs_path.stat().st_size
    if size > max_file_bytes:
        raise ApiException(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"File exceeds max_file_bytes ({max_file_bytes} bytes)",
            hint="Increase max_file_bytes in project settings or pin a smaller file.",
            details={"max_file_bytes": max_file_bytes, "bytes": size},
        )

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_file_bytes + 1)
    except Exception:
        raise ApiException(status_code=500, code="FILE_READ_FAILED", message="Failed to read file")

    if len(content.encode("utf-8", errors="ignore")) > max_file_bytes:
        raise ApiException(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"File exceeds max_file_bytes ({max_file_bytes} bytes)",
            hint="Increase max_file_bytes in project settings or pin a smaller file.",
            details={"max_file_bytes": max_file_bytes, "bytes": size},
        )

    return ok(
        {
            "file": {
                "path": rel_str,
                "name": abs_path.name,
                "content": content,
                "bytes": int(size),
                "max_file_bytes": int(max_file_bytes),
            }
        }
    )


@router.get("/projects/{project_id}/detect-stack")
def detect_project_stack(project_id: str) -> Dict[str, Any]:
    """Analyze the project to recommend include patterns."""
    proj = _srv()._require_project(project_id)
    detected_presets = scan_for_presets(Path(proj.path))
    
    recommended_globs = []
    for preset in detected_presets:
        recommended_globs.extend(STACK_PRESETS.get(preset, []))
        
    return ok({
        "recommended_globs": sorted(list(set(recommended_globs))),
        "detected_presets": sorted(detected_presets),
        "all_presets": STACK_PRESETS,
    })


@router.get("/projects/{project_id}/roots")
def get_project_roots(project_id: str) -> Dict[str, Any]:
    """Get available root directories for a project."""
    proj = _srv()._require_project(project_id)
    project_root = Path(proj.path).expanduser().resolve()
    
    if not project_root.exists() or not project_root.is_dir():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    roots: List[str] = []
    
    # Generic discovery: list all top-level directories except ignored ones
    ignore = DEFAULT_EXCLUDE_DIR_NAMES | {".idea", ".vscode"}
    try:
        for item in sorted(project_root.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith("."):
                continue
            if item.name in ignore:
                continue
            roots.append(item.name)
    except Exception:
        pass

    return ok({"roots": roots})


@router.get("/projects/{project_id}/files")
def list_project_files(
    project_id: str,
    path: str = "",
    depth: int = 3,
) -> Dict[str, Any]:
    """List files and directories under a project path.

    Parameters
    ----------
    path : str
        Relative path within the project root (empty = project root).
    depth : int
        Maximum recursion depth (default 3, max 10).
    """
    proj = _srv()._require_project(project_id)
    project_root = Path(proj.path).expanduser().resolve()

    if not project_root.exists() or not project_root.is_dir():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    # Resolve target directory safely
    target = (project_root / path).resolve()
    # Security: ensure target is within project root
    try:
        target.relative_to(project_root)
    except ValueError:
        raise ApiException(status_code=400, code="PATH_OUTSIDE_PROJECT", message="Path is outside project root")

    if not target.exists() or not target.is_dir():
        raise ApiException(status_code=400, code="PATH_NOT_FOUND", message=f"Directory not found: {path}")

    ignore = DEFAULT_EXCLUDE_DIR_NAMES | {
              ".idea", ".vscode", ".eggs", "*.egg-info", ".DS_Store"}
    depth = min(max(depth, 1), 10)

    # Build per-file chunk count from index documents for status annotation
    idx = _srv()._get_project_index(proj)
    chunks_by_file: Dict[str, int] = {}
    if idx.is_loaded() and idx._documents:
        for doc in idx._documents:
            sp = str(doc.get("source_path") or "")
            if sp:
                chunks_by_file[sp] = chunks_by_file.get(sp, 0) + 1

    def _is_ignored(name: str) -> bool:
        if name in ignore or (name.startswith(".") and name != ".env"):
            return True
        if any(name.endswith(suf) for suf in (".egg-info", ".pyc", ".pyo")):
            return True
        return False

    def _has_visible_children(directory: Path) -> bool:
        """Check if a directory has any non-ignored children."""
        try:
            for item in directory.iterdir():
                if not _is_ignored(item.name):
                    return True
        except PermissionError:
            pass
        return False

    def _scan(directory: Path, current_depth: int, rel_prefix: str) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        try:
            items = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return entries

        for item in items:
            name = item.name
            if _is_ignored(name):
                continue

            child_rel = f"{rel_prefix}/{name}" if rel_prefix else name

            if item.is_dir():
                if current_depth < depth:
                    children = _scan(item, current_depth + 1, child_rel)
                    entries.append({
                        "name": name,
                        "type": "folder",
                        "children": children,
                    })
                else:
                    # Depth limit reached — signal whether folder has children
                    entry: Dict[str, Any] = {
                        "name": name,
                        "type": "folder",
                        "children": [],
                    }
                    if _has_visible_children(item):
                        entry["has_children"] = True
                    entries.append(entry)
            elif item.is_file():
                file_entry: Dict[str, Any] = {
                    "name": name,
                    "type": "file",
                }
                chunk_count = chunks_by_file.get(child_rel)
                if chunk_count is not None:
                    file_entry["status"] = "indexed"
                    file_entry["chunks"] = chunk_count
                entries.append(file_entry)
        return entries

    # Build the relative prefix for the scan root
    rel_prefix = path  # empty string for project root, else the subpath
    tree = _scan(target, 1, rel_prefix)
    return ok({"path": path, "tree": tree})


@router.post("/projects/{project_id}/build")
def build_project(project_id: str, full: bool = False, req: Optional[BuildRequest] = None) -> Dict[str, Any]:
    from codrag.services.project_helpers import is_over_project_limit, require_project_writable
    if is_over_project_limit():
        raise ApiException(
            status_code=403,
            code="PROJECT_LIMIT_EXCEEDED",
            message="Cannot build index: Project limit exceeded for current tier",
            hint="Upgrade your plan or remove projects to resume syncing."
        )

    proj = require_project_writable(project_id)
    include_globs, exclude_globs = _get_project_globs(proj, use_defaults=False)
    # Pass None instead of [] so downstream build() applies its own policy defaults
    include_globs = include_globs or None
    exclude_globs = exclude_globs or None
    cfg = proj.config or {}
    max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)
    hard_limit_bytes = int((cfg.get("hard_limit_bytes") or 100_000_000) if isinstance(cfg, dict) else 100_000_000)

    # Extract included_paths from request body, falling back to project config
    included_paths = req.included_paths if req and req.included_paths else None
    if not included_paths:
        included_paths = cfg.get("included_paths") if isinstance(cfg, dict) else None
    logger.info("build_project: req=%s, included_paths count=%s", req, len(included_paths) if included_paths else None)

    started = _srv()._start_project_build(
        proj, None, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes,
        included_paths=included_paths,
    )
    if not started:
        raise ApiException(status_code=409, code="BUILD_ALREADY_RUNNING", message="Build already running")

    return ok({"started": True, "building": True, "build_id": None})


@router.post("/projects/{project_id}/search")
def search_project(project_id: str, req: SearchRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    if not req.query.strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    idx = _srv()._get_project_layered_index(proj)
    if not idx.is_loaded():
        raise ApiException(
            status_code=409,
            code="INDEX_NOT_BUILT",
            message="Index has not been built yet",
            hint="Run a build first.",
        )

    results = idx.search(
        req.query, k=req.k, min_score=req.min_score,
        score_drop_ratio=req.score_drop_ratio, mmr_lambda=req.mmr_lambda,
        exclude_paths=req.exclude_paths or None,
    )
    out: List[Dict[str, Any]] = []
    for r in results:
        d = r.doc
        content = str(d.get("content") or "")
        span = d.get("span")
        if not isinstance(span, dict) or "start_line" not in span or "end_line" not in span:
            span = {"start_line": 1, "end_line": 1}
        out.append(
            {
                "chunk_id": str(d.get("id") or ""),
                "source_path": str(d.get("source_path") or ""),
                "span": span,
                "preview": content[:200],
                "score": float(r.score),
            }
        )
    return ok({"results": out})


# ── Phase 39: Observation injection ──────────────────────────────
# Append relevant observations as a [session-memory] section at the
# end of the assembled context.  Stale observations are included but
# marked so the agent knows to re-evaluate.
_OBS_MAX_CHARS = 500
_OBS_MAX_COUNT = 3


def _inject_observations(
    context_str: str,
    project_id: str,
    query: str,
) -> tuple:
    """Append relevant observations to context string.

    Returns (new_context_str, obs_meta_dict_or_None).
    """
    try:
        from codrag.services.observation_store import observation_store
        observations = observation_store.get_for_query(
            project_id, query, limit=_OBS_MAX_COUNT, include_stale=True,
        )
        if not observations:
            return context_str, None

        lines: list = []
        chars = 0
        included = 0
        stale_count = 0
        for obs in observations:
            prefix = "[STALE] " if obs.stale else ""
            cat = f"({obs.category}) " if obs.category != "note" else ""
            file_ref = f" [{obs.file_path}]" if obs.file_path else ""
            line = f"- {prefix}{cat}{obs.content}{file_ref}"
            if chars + len(line) > _OBS_MAX_CHARS:
                break
            lines.append(line)
            chars += len(line)
            included += 1
            if obs.stale:
                stale_count += 1

        if not lines:
            return context_str, None

        section = "\n\n---\n\n[session-memory]\n" + "\n".join(lines)
        meta = {"observations_injected": included, "stale": stale_count}
        return context_str + section, meta

    except Exception:
        return context_str, None


def _prepend_atlas(
    context_str: str,
    project_id: str,
    file_count: int,
    source_paths: Optional[List[str]] = None,
) -> tuple:
    """Prepend the Codebase Atlas to context if available.

    If segmented atlases exist and source_paths are provided, injects
    root atlas + relevant segment atlases. Otherwise falls back to the
    single atlas.

    Returns (new_context_str, atlas_meta_dict_or_None, atlas_chars_used).
    """
    from codrag.core.atlas import CodebaseAtlas, compute_atlas_budget
    from codrag.core.project_registry import project_index_dir
    from codrag.services.project_helpers import require_project

    budget = compute_atlas_budget(file_count)
    if budget <= 0:
        return context_str, None, 0

    try:
        project = require_project(project_id)
        idx_dir = project_index_dir(project)
        atlas = CodebaseAtlas(idx_dir)
        doc = atlas.load()
    except Exception:
        return context_str, None, 0

    if doc is None or not doc.content:
        return context_str, None, 0

    # Try segmented atlas: root + relevant segments
    segments_used: List[str] = []
    if source_paths and atlas.has_segments():
        seg_docs = atlas.select_segments(source_paths, max_segments=2)
        if seg_docs:
            # Build: root atlas (truncated to fit) + segment atlases
            root_budget = min(len(doc.content), budget // 2)
            remaining = budget - root_budget
            blocks: List[str] = [f"[ATLAS | Codebase Map]\n{doc.content[:root_budget]}"]

            for seg_doc in seg_docs:
                seg_budget = min(len(seg_doc.content), remaining)
                if seg_budget < 100:
                    break
                blocks.append(f"[ATLAS | {seg_doc.segment_name}]\n{seg_doc.content[:seg_budget]}")
                remaining -= seg_budget
                segments_used.append(seg_doc.segment_id)

            atlas_block = "\n\n".join(blocks)
            atlas_chars = len(atlas_block)

            if context_str:
                new_context = atlas_block + "\n\n---\n\n" + context_str
            else:
                new_context = atlas_block

            atlas_meta = {
                "included": True,
                "chars": atlas_chars,
                "mode": doc.mode,
                "generated_at": doc.generated_at,
                "stale": False,
                "segmented": True,
                "segments": segments_used,
            }
            return new_context, atlas_meta, atlas_chars

    # Fallback: single atlas (no segments or no source_paths)
    atlas_text = doc.content[:budget]
    atlas_block = f"[ATLAS | Codebase Map]\n{atlas_text}"
    atlas_chars = len(atlas_block)

    if context_str:
        new_context = atlas_block + "\n\n---\n\n" + context_str
    else:
        new_context = atlas_block

    atlas_meta = {
        "included": True,
        "chars": atlas_chars,
        "mode": doc.mode,
        "generated_at": doc.generated_at,
        "stale": False,
        "segmented": False,
    }

    return new_context, atlas_meta, atlas_chars


def _load_trace_nodes_for_project(proj: Any) -> List[Dict[str, Any]]:
    """Load trace_nodes.jsonl for a project. Returns empty list on any error."""
    import json
    try:
        from codrag.core.project_registry import project_index_dir
        idx_dir = project_index_dir(proj)
        nodes_path = idx_dir / "trace_nodes.jsonl"
        if not nodes_path.exists():
            return []
        nodes: List[Dict[str, Any]] = []
        with open(nodes_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    nodes.append(json.loads(line))
        return nodes
    except Exception as e:
        logger.debug("Could not load trace_nodes for LOD: %s", e)
        return []


def _apply_lod_compression(
    chunks: List[Dict[str, Any]],
    proj: Any,
    query: str,
    max_chars: int,
) -> Dict[str, Any]:
    """Apply LOD-based structural compression to structured search results.

    Each chunk's content is replaced by its file's LOD-extracted skeleton.
    The LOD level is assigned per chunk based on its search score.
    Files are deduplicated — each file appears once at its highest-fidelity LOD.
    """
    from codrag.core.lod_extractor import LODExtractor, assign_lod

    repo_root = Path(proj.path) if proj.path else Path(".")
    trace_nodes = _load_trace_nodes_for_project(proj)
    extractor = LODExtractor()
    augmented: Dict[str, Any] = {}
    try:
        from codrag.core.project_registry import project_index_dir
        extractor = LODExtractor(index_dir=project_index_dir(proj))
        augmented = extractor.load_augmented_data()
    except Exception:
        pass

    # Deduplicate: each file gets the LOD of its highest-scoring chunk
    file_lod: Dict[str, int] = {}  # source_path -> LOD
    file_score: Dict[str, float] = {}
    for ch in chunks:
        sp = ch.get("source_path") or ch.get("text", "")
        if not sp:
            continue
        score = float(ch.get("score", 0.0))
        is_expanded = bool(ch.get("trace_expanded", False))
        lod = assign_lod(score, is_trace_expanded=is_expanded)
        if sp not in file_score or score > file_score[sp]:
            file_score[sp] = score
            file_lod[sp] = lod

    parts: List[str] = []
    new_chunks: List[Dict[str, Any]] = []
    lod_distribution: Dict[str, int] = {}
    seen_paths: set = set()
    total = 0

    for ch in chunks:
        sp = ch.get("source_path") or ""
        if not sp or sp in seen_paths:
            continue
        seen_paths.add(sp)

        lod = file_lod.get(sp, 0)
        result = extractor.extract(sp, lod, trace_nodes, repo_root, augmented_data=augmented)
        content = result.content
        if not content:
            continue

        lod_key = str(result.lod)
        lod_distribution[lod_key] = lod_distribution.get(lod_key, 0) + 1

        section = ch.get("section") or ""
        header_bits = []
        if section:
            header_bits.append(section)
        header_bits.append(f"@{sp}")
        if result.lod > 0:
            header_bits.append(f"lod={result.lod}")
        header = " | ".join(header_bits)

        sep = "\n\n---\n\n" if parts else ""
        remaining = max_chars - total
        if remaining <= 0:
            break
        block = f"[{header}]\n{content}"
        if total + len(sep) + len(block) > max_chars:
            allowed = remaining - len(sep) - len(f"[{header}]\n")
            if allowed > 200:
                block = f"[{header}]\n{content[:allowed]}..."
            else:
                break

        parts.append(sep + block)
        total += len(sep) + len(block)
        new_chunks.append({
            "source_path": sp,
            "section": section,
            "score": file_score.get(sp, 0.0),
            "lod": result.lod,
            "compression_ratio": round(result.compression_ratio, 2),
            "truncated": block.endswith("..."),
        })

    context_str = "".join(parts)
    return {
        "context": context_str,
        "chunks": new_chunks,
        "total_chars": len(context_str),
        "estimated_tokens": len(context_str) // 4,
        "compression": {
            "enabled": True,
            "mode": "lod",
            "input_chars": sum(len(ch.get("text", "") or "") for ch in chunks),
            "output_chars": len(context_str),
            "lod_distribution": lod_distribution,
        },
    }


def _get_compressor(compression: str) -> "ContextCompressor":
    """Get the appropriate compressor based on the compression parameter."""
    if compression in ("lingua", "auto"):
        return LinguaCompressor()
    return NoopCompressor()


def _apply_compression(
    context_str: str,
    req: ContextRequest,
) -> Dict[str, Any]:
    """Apply compression to context string and return compression metadata."""
    if req.compression == "none":
        return {"context": context_str, "compression": None}


    compressor = _get_compressor(req.compression)
    budget = req.compression_target_chars or req.max_chars
    result = compressor.compress(
        context_str,
        query=req.query,
        budget_chars=budget,
        level=req.compression_level,
        timeout_s=req.compression_timeout_s,
    )

    compression_meta = {
        "enabled": True,
        "mode": req.compression,
        "level": req.compression_level,
        "input_chars": result.input_chars,
        "output_chars": result.output_chars,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "compression_ratio": result.compression_ratio,
        "timing_ms": round(result.timing_ms, 1),
        "error": result.error,
    }

    return {"context": result.compressed, "compression": compression_meta}


def _assemble_ambient_context(
    proj,
    project_id: str,
    idx,
    trace_idx,
    included_paths: List[str],
    max_chars: int = 6000,
) -> Dict[str, Any]:
    """Assemble context from project state without a query (Phase 34 C1/C2/C3).

    Uses included_paths + trace graph hubs + module data to build structural
    context that answers "what's in my focus area and how does it connect?"
    """
    from codrag.core.project_registry import project_index_dir

    parts: List[str] = []
    chunks: List[Dict[str, Any]] = []
    total_chars = 0

    idx_dir = project_index_dir(proj)

    # ── C2: Module-aware header ──────────────────────────────────
    # Load modules and find which ones overlap with included_paths
    modules_path = idx_dir / "trace_modules.jsonl"
    scope_modules: List[Dict[str, Any]] = []
    if modules_path.exists():
        try:
            import json as _json
            with open(modules_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        m = _json.loads(line)
                        member_files = m.get("member_files", [])
                        # Check if any member file falls under included_paths
                        for ip in included_paths:
                            prefix = ip.rstrip("/") + "/"
                            if any(mf == ip or mf.startswith(prefix) for mf in member_files):
                                scope_modules.append(m)
                                break
                    except _json.JSONDecodeError:
                        continue
        except OSError:
            pass

    if scope_modules:
        mod_header = "## Modules in scope\n"
        for m in sorted(scope_modules, key=lambda x: -x.get("file_count", 0)):
            name = m.get("name", m.get("module_id", "?"))
            summary = m.get("summary", "")
            fc = m.get("file_count", 0)
            tags = ", ".join(m.get("domain_tags", [])[:5])
            deps = ", ".join(m.get("dependencies", [])[:3])
            line = f"- **{name}** ({fc} files)"
            if summary:
                line += f": {summary}"
            if tags:
                line += f" [{tags}]"
            if deps:
                line += f" → {deps}"
            mod_header += line + "\n"
        parts.append(mod_header.strip())
        total_chars += len(parts[-1])

    # ── C1: Hub-file extraction ──────────────────────────────────
    hub_files: List[Tuple[str, int]] = []
    if trace_idx is not None and trace_idx.is_loaded():
        scope_set = set(included_paths) if included_paths else None
        hub_files = trace_idx.get_hub_files(scope_paths=scope_set, k=8)

    # Fall back to included_paths as-is if no trace or no hubs found
    if not hub_files and included_paths:
        # Use included_paths directly — pick files from the index
        indexed_docs = getattr(idx, '_documents', None) or []
        for ip in included_paths:
            prefix = ip.rstrip("/") + "/"
            for d in indexed_docs:
                sp = str(d.get("source_path") or "")
                if sp == ip or sp.startswith(prefix):
                    hub_files.append((sp, 0))
                    if len(hub_files) >= 8:
                        break
            if len(hub_files) >= 8:
                break

    if not hub_files:
        # No scope at all — fall back to global hubs from trace
        if trace_idx is not None and trace_idx.is_loaded():
            hub_files = trace_idx.get_hub_files(k=8)

    # ── C3: LOD-stratified assembly ──────────────────────────────
    # Hub files get full content (LOD 0), their neighbors get signatures
    indexed_docs = getattr(idx, '_documents', None) or []
    doc_by_path: Dict[str, List[Dict[str, Any]]] = {}
    for d in indexed_docs:
        sp = str(d.get("source_path") or "")
        if sp:
            doc_by_path.setdefault(sp, []).append(d)

    # Collect neighbor files via trace
    neighbor_files: Set[str] = set()
    hub_paths = {fp for fp, _ in hub_files}
    if trace_idx is not None and trace_idx.is_loaded():
        for fp, _ in hub_files[:5]:  # Only expand top-5 hubs to limit volume
            from codrag.core.ids import stable_file_node_id
            file_node_id = stable_file_node_id(fp)
            try:
                neighbors = trace_idx.get_neighbors(file_node_id, direction="both", max_nodes=10)
                for node in neighbors.get("in_nodes", []) + neighbors.get("out_nodes", []):
                    nfp = node.get("file_path")
                    if nfp and nfp not in hub_paths:
                        neighbor_files.add(nfp)
            except Exception:
                pass

    # Assemble hub file content (LOD 0 — full source, budget-aware)
    chars_budget = max_chars - total_chars
    hub_budget = int(chars_budget * 0.7)  # 70% for hubs
    neighbor_budget = int(chars_budget * 0.3)  # 30% for neighbors

    hub_chars = 0
    for fp, deg in hub_files:
        if hub_chars >= hub_budget:
            break
        file_docs = doc_by_path.get(fp, [])
        if not file_docs:
            continue
        # Pick the largest chunk for this file (most representative)
        best_doc = max(file_docs, key=lambda d: len(str(d.get("content") or "")))
        content = str(best_doc.get("content") or "")
        if hub_chars + len(content) > hub_budget and hub_chars > 0:
            continue
        section = str(best_doc.get("section") or "")
        header = f"[hub | in-degree:{deg} | @{fp}"
        if section:
            header += f" § {section}"
        header += "]"
        block = f"{header}\n{content}"
        parts.append(block)
        chunks.append({
            "source_path": fp,
            "section": section,
            "score": 1.0,
            "truncated": False,
            "ambient_role": "hub",
        })
        hub_chars += len(block)
        total_chars += len(block)

    # Assemble neighbor content (LOD 2-4 — signatures/names only)
    # Try LOD compression; fall back to truncated content
    neighbor_chars = 0
    lod_extractor = None
    try:
        from codrag.core.lod_extractor import LODExtractor
        lod_extractor = LODExtractor(index_dir=idx_dir)
    except Exception:
        pass

    repo_root = Path(proj.path) if proj.path else None

    for nfp in sorted(neighbor_files):
        if neighbor_chars >= neighbor_budget:
            break
        file_docs = doc_by_path.get(nfp, [])

        # Try LOD 2 (signatures + docstrings) via LODExtractor
        lod_content = None
        if lod_extractor is not None and repo_root is not None:
            try:
                # Load trace nodes for this file
                trace_nodes = []
                if trace_idx is not None and trace_idx.is_loaded():
                    from codrag.core.ids import stable_file_node_id as _sfni
                    file_nid = _sfni(nfp)
                    fnode = trace_idx.get_node(file_nid)
                    if fnode:
                        trace_nodes = [fnode]
                    # Also get symbol nodes in this file
                    for nid_key in list(getattr(trace_idx, '_nodes', {}).keys()):
                        n = trace_idx.get_node(nid_key)
                        if n and n.get("file_path") == nfp and n.get("kind") != "file":
                            trace_nodes.append(n)

                lod_result = lod_extractor.extract(nfp, lod=2, trace_nodes=trace_nodes, repo_root=repo_root)
                if lod_result and lod_result.content and not lod_result.error:
                    lod_content = lod_result.content
            except Exception:
                pass

        if lod_content:
            content = lod_content
            lod_label = "LOD 2"
        elif file_docs:
            # Fall back to first 500 chars of content
            best_doc = max(file_docs, key=lambda d: len(str(d.get("content") or "")))
            raw = str(best_doc.get("content") or "")
            content = raw[:500] + ("..." if len(raw) > 500 else "")
            lod_label = "truncated"
        else:
            continue

        if neighbor_chars + len(content) > neighbor_budget and neighbor_chars > 0:
            continue

        header = f"[neighbor | {lod_label} | @{nfp}]"
        block = f"{header}\n{content}"
        parts.append(block)
        chunks.append({
            "source_path": nfp,
            "section": "",
            "score": 0.5,
            "truncated": lod_label != "LOD 2",
            "ambient_role": "neighbor",
        })
        neighbor_chars += len(block)
        total_chars += len(block)

    context_str = "\n\n---\n\n".join(parts) if parts else "(No context available — select files in the dashboard or build the trace index.)"
    total_chars = len(context_str)

    return ok({
        "context": context_str,
        "chunks": chunks,
        "total_chars": total_chars,
        "estimated_tokens": total_chars // 4,
        "ambient": True,
        "hub_files": len(hub_files),
        "modules_in_scope": len(scope_modules),
        "neighbor_files": len(neighbor_files),
    })


@router.post("/projects/{project_id}/context")
def context_project(project_id: str, req: ContextRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)

    idx = _srv()._get_project_layered_index(proj)
    if not idx.is_loaded():
        raise ApiException(
            status_code=409,
            code="INDEX_NOT_BUILT",
            message="Index has not been built yet",
            hint="Run a build first.",
        )

    # Resolve trace index for trace expansion
    # Phase 34: trace_expand defaults to True. Gracefully degrade if
    # the feature gate blocks it (free tier) or trace isn't available.
    trace_idx = None
    if req.trace_expand:
        try:
            require_feature("mcp_trace_expand")
            cfg = proj.config or {}
            trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
            if bool((trace_cfg or {}).get("enabled", False)):
                try:
                    ti = _srv()._get_project_srv()._trace_index(proj)
                    if ti.exists():
                        if not ti.is_loaded():
                            ti.load()
                        trace_idx = ti
                except Exception:
                    pass  # Graceful: fall back to non-expanded context
        except FeatureGateError:
            pass  # Phase 34: default-on means graceful fallback for free tier

    # ── Phase 34 C4: Ambient context mode (no query) ─────────────
    if not req.query.strip():
        _included = (proj.config or {}).get("included_paths") or []
        return _assemble_ambient_context(
            proj, project_id, idx, trace_idx, _included, max_chars=req.max_chars,
        )

    # ── Phase 34e F: Query preprocessing ─────────────────────────
    req.query = _preprocess_query(req.query)

    # Resolve file count for atlas budget (from index manifest)
    _file_count = 0
    try:
        _manifest = getattr(idx, '_manifest', None) or {}
        _file_count = (_manifest.get('stats') or {}).get('files_indexed', 0)
        if _file_count == 0:
            _file_count = len(getattr(idx, '_documents', None) or [])
    except Exception:
        pass

    # ── Scope boost (Phase 34) ───────────────────────────────────
    # Load included_paths from project config and use them as a
    # query-time scope boost.  Files under selected paths get the
    # same +boost as atlas-routed files, ensuring the user's file
    # tree selections influence retrieval — not just build scoping.
    _segment_file_paths: Optional[set] = None
    _routing_meta: Optional[Dict[str, Any]] = None
    _scope_boosted_files: int = 0
    _sr6_segment_boost: float = 0.12  # SR-6: default boost; raised to 0.30 for high-confidence routing
    try:
        _included = (proj.config or {}).get("included_paths") or []
        if _included:
            _segment_file_paths = set()
            # included_paths may be files or directories — we need to
            # resolve them against indexed documents so directory entries
            # expand to all files beneath them.
            _indexed_paths = set()
            for d in (getattr(idx, '_documents', None) or []):
                sp = d.get("source_path")
                if sp:
                    _indexed_paths.add(str(sp))
            for ip in _included:
                ip_str = str(ip)
                if ip_str in _indexed_paths:
                    _segment_file_paths.add(ip_str)
                else:
                    # Treat as directory prefix
                    prefix = ip_str.rstrip("/") + "/"
                    for idxp in _indexed_paths:
                        if idxp.startswith(prefix):
                            _segment_file_paths.add(idxp)
            _scope_boosted_files = len(_segment_file_paths)
            if _scope_boosted_files:
                _routing_meta = {
                    "scope_boosted_files": _scope_boosted_files,
                }
                logger.debug("Scope boost: %d files from %d included_paths", _scope_boosted_files, len(_included))
            else:
                _segment_file_paths = None  # No matches — don't pollute boost set
    except Exception as e:
        logger.debug("Scope boost unavailable: %s", e)

    # ── Atlas routing (Phase 29B) ────────────────────────────────
    # Route query to relevant segments BEFORE search, so search()
    # can boost files in the selected segments.
    try:
        from codrag.core.atlas import CodebaseAtlas, route_query, ROUTING_SEGMENT_BOOST
        from codrag.core.project_registry import project_index_dir
        from codrag.services.project_helpers import require_project
        import numpy as np

        _proj = require_project(project_id)
        _idx_dir = project_index_dir(_proj)
        _atlas = CodebaseAtlas(_idx_dir)

        if _atlas.has_routing():
            descriptors, desc_embeddings = _atlas.load_routing()
            if descriptors and desc_embeddings is not None:
                # Embed query using the same embedder as the index
                _embed_fn = getattr(idx.embedder, "embed_query", idx.embedder.embed)
                _qvec = np.array(_embed_fn(req.query).vector, dtype=np.float32)

                selected = route_query(_qvec, desc_embeddings, descriptors)
                if selected:
                    _atlas_paths = _atlas.get_routed_file_paths(selected)
                    if _segment_file_paths is None:
                        _segment_file_paths = _atlas_paths
                    else:
                        _segment_file_paths = _segment_file_paths | _atlas_paths

                    # SR-6: High-confidence atlas routing → hard pre-filter
                    # When the top segment score is very high (>0.7), exclude
                    # files NOT in the routed segments from search results.
                    # This reduces noise from unrelated subsystems.
                    _top_routing_score = max(s for _, s in selected) if selected else 0.0
                    _sr6_prefilter = _top_routing_score > 0.7 and len(_atlas_paths) >= 5

                    _routing_meta = {
                        "routed": True,
                        "segments": [
                            {"id": d.segment_id, "name": d.name, "score": round(s, 3)}
                            for d, s in selected
                        ],
                        "boosted_files": len(_segment_file_paths),
                        "scope_boosted_files": _scope_boosted_files,
                        "prefiltered": _sr6_prefilter,
                    }

                    # SR-6: When pre-filtering is active, increase the segment
                    # boost so routed files dominate results. Non-routed files
                    # still appear if their embedding score is very high.
                    if _sr6_prefilter:
                        _sr6_segment_boost = 0.30  # 2.5x the default 0.12
    except Exception as e:
        logger.debug("Atlas routing unavailable: %s", e)

    # ── Knowledge routing (Phase 29C) ────────────────────────────
    # Search the KnowledgeIndex (trace-derived LLM descriptions) to
    # identify specific files whose *enriched descriptions* match the
    # query. These are unioned into the segment boost set, giving a
    # two-tier precision boost:
    #   Tier 1 (atlas)     → which subsystem?  (segment granularity)
    #   Tier 2 (knowledge) → which exact files? (node granularity)
    # Zero context cost — only shapes the boost set, adds no text.
    _knowledge_boosted_files: int = 0
    try:
        from codrag.server import _get_project_knowledge_index
        from codrag.services.project_helpers import require_project as _rp_know
        _know_proj = _rp_know(project_id)
        _know_idx = _get_project_knowledge_index(_know_proj)
        if _know_idx.is_loaded():
            _know_results = _know_idx.search(req.query, k=15, min_score=0.25)
            if _know_results:
                if _segment_file_paths is None:
                    _segment_file_paths = set()
                for _kr in _know_results:
                    _src = _kr["doc"].get("source_id") or ""
                    if _src.startswith("file:"):
                        _segment_file_paths.add(_src[5:])
                    elif _src.startswith("sym:"):
                        _at = _src.find("@")
                        if _at >= 0:
                            _rest = _src[_at + 1:]
                            _colon = _rest.rfind(":")
                            _segment_file_paths.add(_rest[:_colon] if _colon > 0 else _rest)
                _knowledge_boosted_files = len(_know_results)
                if _routing_meta is not None:
                    _routing_meta["knowledge_boosted_files"] = _knowledge_boosted_files
                elif _knowledge_boosted_files:
                    _routing_meta = {
                        "routed": False,
                        "knowledge_boosted_files": _knowledge_boosted_files,
                    }
    except Exception as e:
        logger.debug("Knowledge routing unavailable: %s", e)

    # Update boosted_files to total pool size after both routing tiers
    if _routing_meta is not None and _segment_file_paths:
        _routing_meta["boosted_files"] = len(_segment_file_paths)

    if not req.structured:
        ctx = idx.get_context(
            req.query,
            k=req.k,
            max_chars=req.max_chars,
            include_sources=req.include_sources,
            include_scores=req.include_scores,
            min_score=req.min_score,
            segment_file_paths=_segment_file_paths,
            segment_boost=_sr6_segment_boost,
        )

        comp = _apply_compression(ctx, req)
        resp: Dict[str, Any] = {"context": comp["context"]}
        if comp["compression"] is not None:
            resp["compression"] = comp["compression"]
        # Atlas: routing metadata (no injection) + legacy prepend fallback
        if _routing_meta:
            resp["atlas"] = _routing_meta
        elif req.include_atlas:
            new_ctx, atlas_meta, _ = _prepend_atlas(resp["context"], project_id, _file_count)
            resp["context"] = new_ctx
            if atlas_meta:
                resp["atlas"] = atlas_meta
        # Phase 39: Inject relevant observations as session-memory
        resp["context"], _obs_meta = _inject_observations(resp["context"], project_id, req.query)
        if _obs_meta:
            resp["session_memory"] = _obs_meta
        return ok(resp)

    # ── SR-2: Knowledge Index content fallback ──────────────────
    # When CodeIndex coverage is sparse (few chunks indexed), supplement
    # search with KnowledgeIndex results. The knowledge index contains
    # LLM-enriched file descriptions that can fill gaps where source
    # code chunks aren't indexed. This is additive — knowledge results
    # appear as supplementary context, not a replacement.
    _knowledge_fallback_chunks: List[Dict[str, Any]] = []
    try:
        from codrag.server import _get_project_knowledge_index
        _know_idx = _get_project_knowledge_index(proj)
        if _know_idx.is_loaded():
            _code_doc_count = len(getattr(idx, '_documents', None) or [])
            # Heuristic: if CodeIndex has fewer than 100 chunks, knowledge
            # fallback is likely valuable (sparse coverage)
            if _code_doc_count < 100:
                _know_results = _know_idx.search(req.query, k=3, min_score=0.30)
                for _kr in _know_results:
                    _kd = _kr.get("doc") if isinstance(_kr, dict) else _kr
                    if not isinstance(_kd, dict):
                        continue
                    _knowledge_fallback_chunks.append({
                        "source_path": str(_kd.get("source_path") or _kd.get("source_id") or ""),
                        "section": "knowledge-enriched",
                        "score": float(_kr.get("score", 0.0) if isinstance(_kr, dict) else 0.0),
                        "text": str(_kd.get("content") or _kd.get("text") or ""),
                        "is_knowledge_fallback": True,
                    })
    except Exception as e:
        logger.debug("SR-2 knowledge fallback unavailable: %s", e)

    # Structured context: use trace expansion if available
    if trace_idx is not None:
        # W2b: Resolve modules path for module summary injection
        _modules_path = None
        try:
            _modules_path = project_index_dir(proj) / "trace_modules.jsonl"
            if not _modules_path.exists():
                _modules_path = None
        except Exception:
            pass

        result = idx.get_context_with_trace_expansion(
            req.query,
            trace_index=trace_idx,
            k=req.k,
            max_chars=req.max_chars,
            min_score=req.min_score,
            max_additional_chars=req.trace_max_chars,
            segment_file_paths=_segment_file_paths,
            segment_boost=_sr6_segment_boost,
            modules_path=_modules_path,
        )
        # SR-2: Append knowledge fallback chunks to trace-expanded results
        if _knowledge_fallback_chunks:
            existing_chunks = result.get("chunks", [])
            existing_chunks.extend(_knowledge_fallback_chunks)
            result["chunks"] = existing_chunks

        if req.compression in ("none", "lod", "auto"):
            # Phase 34c E1: auto-LOD — structural compression is always applied
            # in the structured+trace path. "none", "lod", and "auto" all trigger it.
            lod_result = _apply_lod_compression(
                result.get("chunks", []), proj, req.query, req.max_chars
            )
            resp_data: Dict[str, Any] = {
                **lod_result,
                "trace_expanded": result.get("trace_expanded", False),
                "trace_nodes_added": result.get("trace_nodes_added", 0),
            }
        else:
            # lingua — skip LOD, apply requested compression
            context_str = str(result.get("context") or "")
            comp = _apply_compression(context_str, req)
            resp_data = {
                "context": comp["context"],
                "chunks": result.get("chunks", []),
                "total_chars": len(comp["context"]),
                "estimated_tokens": len(comp["context"]) // 4,
                "trace_expanded": result.get("trace_expanded", False),
                "trace_nodes_added": result.get("trace_nodes_added", 0),
            }
            if comp["compression"] is not None:
                resp_data["compression"] = comp["compression"]
        # Atlas: routing metadata (no injection) + legacy prepend fallback
        if _routing_meta:
            resp_data["atlas"] = _routing_meta
        elif req.include_atlas:
            new_ctx, atlas_meta, atlas_chars = _prepend_atlas(resp_data["context"], project_id, _file_count)
            resp_data["context"] = new_ctx
            resp_data["total_chars"] = len(new_ctx)
            resp_data["estimated_tokens"] = len(new_ctx) // 4
            if atlas_meta:
                resp_data["atlas"] = atlas_meta
        # Phase 39: Inject relevant observations as session-memory
        resp_data["context"], _obs_meta = _inject_observations(resp_data["context"], project_id, req.query)
        if _obs_meta:
            resp_data["session_memory"] = _obs_meta
            resp_data["total_chars"] = len(resp_data["context"])
            resp_data["estimated_tokens"] = resp_data["total_chars"] // 4
        return ok(resp_data)

    results = idx.search(
        req.query, k=req.k, min_score=req.min_score,
        score_drop_ratio=req.score_drop_ratio, mmr_lambda=req.mmr_lambda,
        exclude_paths=req.exclude_paths or None,
        segment_file_paths=_segment_file_paths,
        segment_boost=_sr6_segment_boost,
    )

    # Phase 34c E1: auto-LOD in structured path (no trace fallback)
    if req.compression in ("none", "lod", "auto"):
        raw_chunks = [
            {
                "source_path": str(r.doc.get("source_path") or ""),
                "section": str(r.doc.get("section") or ""),
                "score": float(r.score),
                "text": str(r.doc.get("content") or ""),
            }
            for r in results
        ]
        # SR-2: Append knowledge fallback chunks to non-trace results
        if _knowledge_fallback_chunks:
            raw_chunks.extend(_knowledge_fallback_chunks)
        lod_result = _apply_lod_compression(raw_chunks, proj, req.query, req.max_chars)
        resp_data: Dict[str, Any] = lod_result
        if _routing_meta:
            resp_data["atlas"] = _routing_meta
        elif req.include_atlas:
            new_ctx, atlas_meta, atlas_chars = _prepend_atlas(resp_data["context"], project_id, _file_count)
            resp_data["context"] = new_ctx
            resp_data["total_chars"] = len(new_ctx)
            resp_data["estimated_tokens"] = len(new_ctx) // 4
            if atlas_meta:
                resp_data["atlas"] = atlas_meta
        # Phase 39: Inject relevant observations as session-memory
        resp_data["context"], _obs_meta = _inject_observations(resp_data["context"], project_id, req.query)
        if _obs_meta:
            resp_data["session_memory"] = _obs_meta
            resp_data["total_chars"] = len(resp_data["context"])
            resp_data["estimated_tokens"] = resp_data["total_chars"] // 4
        return ok(resp_data)

    parts: List[str] = []
    chunks: List[Dict[str, Any]] = []
    total = 0

    for r in results:
        d = r.doc
        chunk_id = str(d.get("id") or "")
        source_path = str(d.get("source_path") or "")
        section = str(d.get("section") or "")
        span = d.get("span")
        if not isinstance(span, dict) or "start_line" not in span or "end_line" not in span:
            span = {"start_line": 1, "end_line": 1}

        header_bits: List[str] = []
        if section:
            header_bits.append(section)
        if source_path:
            header_bits.append(f"@{source_path}")
        header = " | ".join(header_bits) if header_bits else source_path

        sep = "\n\n---\n\n" if parts else ""
        remaining = int(req.max_chars) - total
        if remaining <= 0 or len(sep) >= remaining:
            break

        prefix = f"[{header}]\n" if header else ""
        allowed = remaining - len(sep)
        if len(prefix) >= allowed:
            break

        text = str(d.get("content") or "")
        if len(prefix) + len(text) > allowed:
            text_allowed = allowed - len(prefix)
            if text_allowed > 200:
                text = text[: max(0, text_allowed - 3)] + "..."
            else:
                break

        block = prefix + text
        parts.append(sep + block)
        total += len(sep) + len(block)
        chunks.append(
            {
                "chunk_id": chunk_id,
                "source_path": source_path,
                "span": span,
                "score": float(r.score),
                "text": text,
            }
        )
        if text.endswith("..."):
            break

    context_str = "".join(parts)

    comp = _apply_compression(context_str, req)
    resp_data: Dict[str, Any] = {
        "context": comp["context"],
        "chunks": chunks,
        "total_chars": len(comp["context"]),
        "estimated_tokens": len(comp["context"]) // 4,
    }
    if comp["compression"] is not None:
        resp_data["compression"] = comp["compression"]
    # Atlas: routing metadata (no injection) + legacy prepend fallback
    if _routing_meta:
        resp_data["atlas"] = _routing_meta
    elif req.include_atlas:
        new_ctx, atlas_meta, atlas_chars = _prepend_atlas(resp_data["context"], project_id, _file_count)
        resp_data["context"] = new_ctx
        resp_data["total_chars"] = len(new_ctx)
        resp_data["estimated_tokens"] = len(new_ctx) // 4
        if atlas_meta:
            resp_data["atlas"] = atlas_meta
    # Phase 39: Inject relevant observations as session-memory
    resp_data["context"], _obs_meta = _inject_observations(resp_data["context"], project_id, req.query)
    if _obs_meta:
        resp_data["session_memory"] = _obs_meta
        resp_data["total_chars"] = len(resp_data["context"])
        resp_data["estimated_tokens"] = resp_data["total_chars"] // 4
    return ok(resp_data)




@router.get("/projects/{project_id}/atlas")
def get_atlas(project_id: str) -> Dict[str, Any]:
    """Get the cached Codebase Atlas for a project."""
    from codrag.core.atlas import CodebaseAtlas
    from codrag.core.project_registry import project_index_dir

    proj = _srv()._require_project(project_id)
    idx_dir = project_index_dir(proj)
    atlas = CodebaseAtlas(idx_dir)
    doc = atlas.load()

    if doc is None:
        return ok({
            "exists": False,
            "content": None,
            "stale": True,
        })

    # For dashboard: concatenate root + all segments into one display string
    display_content, display_chars = atlas.get_display_content()

    return ok({
        "exists": True,
        "content": display_content or doc.content,
        "mode": doc.mode,
        "model": doc.model,
        "generated_at": doc.generated_at,
        "file_count": doc.file_count,
        "module_count": doc.module_count,
        "char_count": display_chars or doc.char_count,
        "stale": atlas.is_stale(),
        "segmented": atlas.has_segments(),
    })


@router.post("/projects/{project_id}/atlas/regenerate")
def regenerate_atlas(project_id: str) -> Dict[str, Any]:
    """Manually trigger Atlas regeneration."""
    from codrag.core.atlas import CodebaseAtlas
    from codrag.core.project_registry import project_index_dir

    proj = _srv()._require_project(project_id)
    idx_dir = project_index_dir(proj)

    # Try to use task-assigned LLM; fall back to structural atlas
    # Atlas synthesis is a heavy task — increase timeout to 180s
    llm_client = None
    try:
        from codrag.server import _get_llm_client_for_task
        llm_client = _get_llm_client_for_task("atlas")
        if llm_client and not llm_client.is_available():
            llm_client = None
    except Exception:
        llm_client = None

    if llm_client:
        llm_client.timeout = 180.0

    # Pass project_root for workspace detection in segmented atlas
    project_root = Path(proj.path) if proj.path else None
    atlas = CodebaseAtlas(idx_dir, llm=llm_client, project_root=project_root)

    # Try segmented generation first; falls back to single atlas internally
    root_doc, seg_docs = atlas.generate_segmented()

    # For dashboard: concatenate root + all segments into one display string
    display_content, display_chars = atlas.get_display_content()

    result: Dict[str, Any] = {
        "exists": bool(root_doc.content),
        "content": display_content or root_doc.content,
        "mode": root_doc.mode,
        "model": root_doc.model,
        "char_count": display_chars or root_doc.char_count,
        "file_count": root_doc.file_count,
        "module_count": root_doc.module_count,
        "generated_at": root_doc.generated_at,
        "stale": False,
        "segmented": bool(seg_docs),
    }
    if seg_docs:
        result["segments"] = [
            {
                "segment_id": sd.segment_id,
                "segment_name": sd.segment_name,
                "dir_path": sd.dir_path,
                "file_count": sd.file_count,
                "char_count": sd.char_count,
            }
            for sd in seg_docs
        ]
    return ok(result)



