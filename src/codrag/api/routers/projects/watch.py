"""
Project watch, status, activity, and coverage endpoints.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from codrag.api.envelope import ApiException, ok
from codrag.core.feature_gate import require_feature, FeatureGateError
from codrag.core.project_registry import project_index_dir
from codrag.core.watcher import AutoRebuildWatcher

from .helpers import _srv, _get_project_globs
from .models import WatchRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


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

    from codrag.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)
    idx = _srv()._get_project_index(proj)
    
    # Stop existing watcher if any
    existing = _srv()._project_watchers.get(proj.id)
    if existing is not None:
        existing.stop()
    
    def trigger_build(paths: List[str]) -> bool:
        from codrag.services.project_helpers import get_project_activity_status
        status = get_project_activity_status(proj.id)
        if status in ("frozen", "locked", "inactive"):
            logger.info("Auto-rebuild skipped for %s — project is %s", proj.id, status)
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


