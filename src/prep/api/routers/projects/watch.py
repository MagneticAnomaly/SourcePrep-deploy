"""
Project watch, status, activity, and coverage endpoints.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from prep.api.envelope import ApiException, ok
from prep.core.feature_gate import require_feature, FeatureGateError
from prep.core.project_registry import project_index_dir
from prep.core.watcher import AutoRebuildWatcher

from .helpers import _srv, _get_project_globs
from .models import WatchRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


@router.get("/projects/{project_id}/status")
async def get_project_status(project_id: str) -> Dict[str, Any]:
    import asyncio

    srv = _srv()
    proj = srv._require_project(project_id)
    idx = srv._get_project_index(proj)

    # Offload heavy I/O (filesystem walk, trace index load) to thread pool
    # so we don't block the event loop and starve other API requests.
    loop = asyncio.get_running_loop()

    def _compute_status():
        watch = srv._get_project_watcher_status(proj)

        mtime_check = srv._check_index_staleness(proj, idx)
        watcher_stale = bool(watch.get("stale", False))
        mtime_stale = bool(mtime_check.get("is_stale", False))

        is_stale = watcher_stale or mtime_stale
        stale_since = watch.get("stale_since") or mtime_check.get("stale_since")

        obs_stats = None
        try:
            from prep.services.observation_store import observation_store
            obs_stats = observation_store.get_stats(project_id)
        except Exception:
            pass

        data = {
            "building": srv._is_project_building(proj.id),
            "stale": is_stale,
            "stale_since": stale_since,
            "stale_count": mtime_check.get("stale_count", 0),
            "index": srv._project_index_status(idx, srv._project_last_build_error.get(proj.id), project=proj),
            "trace": srv._project_trace_status(proj),
            "watch": watch,
            "sync": srv._get_project_sync_status(proj),
        }
        if obs_stats and obs_stats.get("total", 0) > 0:
            data["observations"] = obs_stats
        return data

    data = await loop.run_in_executor(None, _compute_status)
    return ok(data)


@router.post("/projects/{project_id}/watch/start")
def start_project_watch(
    project_id: str,
    debounce_ms: int = Query(5000, ge=500, le=60000),
    min_gap_ms: int = Query(2000, ge=500, le=30000),
) -> Dict[str, Any]:
    """Enable auto-rebuild watcher for a project."""
    require_feature("auto_rebuild")

    from prep.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)
    idx = _srv()._get_project_index(proj)
    
    # Stop existing watcher if any
    existing = _srv()._project_watchers.get(proj.id)
    if existing is not None:
        existing.stop()
    
    def trigger_build(paths: List[str]) -> bool:
        from prep.services.project_helpers import get_project_activity_status
        status = get_project_activity_status(proj.id)
        if status in ("locked", "inactive"):
            logger.debug("Auto-rebuild skipped for %s — project is %s", proj.id, status)
            return False

        include_globs, exclude_globs = _get_project_globs(proj, use_defaults=False)
        include_globs = include_globs or None
        exclude_globs = exclude_globs or None
        cfg = proj.config or {}
        max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)
        hard_limit_bytes = int((cfg.get("hard_limit_bytes") or 100_000_000) if isinstance(cfg, dict) else 100_000_000)
        included_paths = cfg.get("included_paths") if isinstance(cfg, dict) else None

        # Phase 48 (P48-F3+F7): When trace is enabled and pipeline is available,
        # delegate entirely to the pipeline orchestrator.  The pipeline's structural
        # stage handles trace build and knowledge stage handles embedding — avoid
        # dual-triggering the legacy build path which competes with the pipeline.
        from prep.core.feature_gate import check_feature
        trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
        trace_enabled = bool((trace_cfg or {}).get("enabled", False))

        if trace_enabled and check_feature("auto_fast_sync"):
            try:
                from prep.services.pipeline_orchestrator import pipeline_orchestrator
                # P48-F7: When deep enrichment is also auto, use run_all() so
                # deep enrichment chains automatically after fast sync.
                from prep.services.settings_store import settings as _ss
                pc = _ss.get("pipeline_config") or {}

                # Per-project auto_config is the source of truth — see
                # PipelineOrchestrator._is_fast_sync_auto for the regression
                # class this guards against. Global pipeline_config is no
                # longer consulted for the gate (it stays in sync via the
                # toggle handler for migration / first-project-default only).
                fast_auto = pipeline_orchestrator._is_fast_sync_auto(proj.id)
                if not fast_auto:
                    logger.debug("Watcher: skipped pipeline trigger for %s — fast sync is Manual", proj.id)
                    return False

                # Phase 60A: Log trigger source to pipeline file logger
                is_coverage = paths == ["__coverage_gap__"]
                trigger_source = "coverage_check" if is_coverage else "watcher_file_change"
                try:
                    from prep.services.pipeline_logger import get_pipeline_logger
                    from prep.core.project_registry import project_index_dir
                    pfl = get_pipeline_logger(project_index_dir(proj))
                    pfl.decision("trigger_source", trigger_source, {
                        "project_id": proj.id,
                        "changed_paths_count": len(paths),
                        "changed_paths_sample": paths[:5] if not is_coverage else [],
                        "fast_auto": fast_auto,
                        "deep_mode": (pc.get("deep_enrichment") or {}).get("mode", "manual"),
                    })
                except Exception:
                    pass  # Decision logging is non-fatal
                    
                # 2026-05-17 regression fix (parity with server.py
                # _startup_auto_run). Watcher triggers are always
                # incremental — file change → re-augment that file.
                # The old fork called run_all when both axes were auto,
                # which (combined with the now-fixed resume barrier
                # bug) painted as "Rebuilding All" in the UI for what
                # was actually a 1-file incremental update. Deep
                # enrichment still auto-chains via _is_deep_enrichment_auto
                # at fast-sync completion (orchestrator.py:2117), so the
                # observable end-state is identical without the rebuild
                # cosplay. The global pc.deep_enrichment.mode read above
                # is now diagnostic-only.
                started = pipeline_orchestrator.run_fast_sync(proj.id)
                logger.info(
                    "Watcher: incremental fast_sync for %s — started=%s "
                    "(deep auto-chains if per-project deepEnrichment=auto)",
                    proj.id, started,
                )
                return True
            except Exception:
                logger.warning("Pipeline trigger failed for %s, falling back to legacy", proj.id, exc_info=True)
                _srv()._start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes, hard_limit_bytes=hard_limit_bytes)
                return True
        elif trace_enabled:
            _srv()._start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes, hard_limit_bytes=hard_limit_bytes)
            return True

        # No trace — use legacy CodeIndex build path
        use_gitignore = bool(cfg.get("use_gitignore", True)) if isinstance(cfg, dict) else True
        if _srv()._has_remote_index(proj):
            return _srv()._start_project_delta_build(
                proj, paths, include_globs, exclude_globs,
                max_file_bytes, hard_limit_bytes,
                use_gitignore=use_gitignore, included_paths=included_paths,
            )
        return _srv()._start_project_build(proj, None, include_globs, exclude_globs, max_file_bytes, hard_limit_bytes, use_gitignore=use_gitignore, included_paths=included_paths)
    
    def is_building() -> bool:
        if _srv()._is_project_building(proj.id) or _srv()._is_project_trace_building(proj.id):
            return True
        # Also treat active pipeline runs as "building" so the watcher
        # waits instead of repeatedly trying to trigger builds.
        # Guard: if the pipeline claims "running" but hasn't updated in
        # >10 minutes, treat it as stale/stuck and allow the watcher to
        # proceed.  This prevents a crashed pipeline from permanently
        # blocking auto-rebuilds.
        try:
            import time as _time
            from prep.services.pipeline_orchestrator import pipeline_orchestrator as _po
            po_status = _po.status(proj.id)
            for group_key in ("fast_sync", "deep_enrichment"):
                group = po_status.get(group_key) or {}
                if group.get("is_active"):
                    started_at = group.get("started_at")
                    if started_at and (_time.time() - started_at > 600) and group.get("phase") == "running":
                        # Force-reset stale runs so the watcher can proceed
                        reset = _po.force_reset_stale_runs(proj.id)
                        if reset:
                            logger.info(
                                "Watcher: force-reset stale pipeline %s groups: %s",
                                proj.id, reset,
                            )
                        continue
                    return True
        except Exception:
            pass
        return False
    
    # Phase 74: Mark concepts stale when their anchored files change.
    def on_files_changed(paths: list[str]) -> None:
        try:
            from prep.services.concept_store import concept_store
            concept_store.mark_stale_batch(proj.id, paths, reason="file modified")
        except Exception:
            pass  # Non-fatal: concept store may not be initialized

    watcher = AutoRebuildWatcher(
        repo_root=Path(proj.path),
        index_dir=idx.index_dir,
        on_trigger_build=trigger_build,
        is_building=is_building,
        debounce_ms=debounce_ms,
        min_rebuild_gap_ms=min_gap_ms,
        project_id=proj.id,
        on_files_changed=on_files_changed,
    )
    watcher.start()
    _srv()._project_watchers[proj.id] = watcher

    # Phase 73.5: Initialize collaboration hub (before Pi so Pi can use it).
    collab_hub = None
    try:
        from prep.services.collaboration import init_collaboration, get_collaboration_hub
        if get_collaboration_hub() is None:
            from prep.services.settings_store import settings
            init_collaboration(settings.db_path)
            logger.info("Collaboration hub initialized")
        collab_hub = get_collaboration_hub()
    except Exception:
        logger.debug("Collaboration hub init failed (non-fatal)", exc_info=True)

    # Phase 66: Initialize Pi agent alongside the watcher.
    # Pi uses the same project context as the watcher.
    # Non-fatal: if Pi init fails, the watcher still works.
    try:
        from prep.services.pi_agent import init_pi_agent
        init_pi_agent(
            project_id=proj.id,
            index_dir=project_index_dir(proj),
            project_root=Path(proj.path),
            collab_hub=collab_hub,
        )
    except Exception:
        logger.debug("Pi agent initialization failed (non-fatal)", exc_info=True)

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


@router.post("/projects/{project_id}/sync/now")
async def trigger_project_sync(project_id: str) -> Dict[str, Any]:
    """Force an immediate team-index sync (Team tier)."""
    import asyncio

    require_feature("team_config")
    srv = _srv()
    proj = srv._require_project(project_id)
    syncer = srv._get_project_syncer(proj)

    # Offload the S3 round-trip to the thread pool so we don't block the
    # event loop, matching the pattern used by get_project_status above.
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, syncer.check_and_sync)
    return ok(syncer.status_dict())


@router.get("/projects/{project_id}/coverage")
def get_project_coverage(project_id: str) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    include_globs, exclude_globs = _get_project_globs(proj)

    repo_root = Path(proj.path).expanduser().resolve()
    if not repo_root.exists():
        raise ApiException(status_code=400, code="PROJECT_PATH_MISSING", message="Project path not found")

    tree = _srv()._build_coverage_tree(repo_root, include_globs, exclude_globs)
    return ok({"tree": tree})


