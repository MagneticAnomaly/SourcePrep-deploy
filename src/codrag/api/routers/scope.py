"""
CoDRAG Scope Router — Phase 24 (SM-8: Knowledge Scope Pipeline)
================================================================

Exposes the scope orchestrator via HTTP endpoints for the FolderTree panel.

**Endpoints:**
  - GET  /projects/{id}/scope/status    — scope pipeline status
  - POST /projects/{id}/scope/add       — add files to knowledge scope
  - POST /projects/{id}/scope/remove    — remove files from knowledge scope
  - POST /projects/{id}/scope/rebuild   — manually trigger scope rebuild (Free tier)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scope"])

_registered_projects: set = set()


def _ensure_build_fn_registered(project_id: str) -> None:
    """Lazily register a CodeIndex build function for the scope orchestrator."""
    if project_id in _registered_projects:
        return

    from codrag.services.scope_orchestrator import scope_orchestrator
    from codrag.services.build_manager import build_manager
    from codrag.services.project_helpers import require_project

    def _build_fn(added, removed, changed) -> bool:
        try:
            project = require_project(project_id)
            cfg = project.config or {}
            included_paths = cfg.get("included_paths") or None
            started = build_manager.start_project_build(
                project,
                None,
                cfg.get("include_globs") or None,
                cfg.get("exclude_globs") or None,
                int(cfg.get("max_file_bytes") or 500_000),
                int(cfg.get("hard_limit_bytes") or 100_000_000),
                included_paths=included_paths,
            )
            logger.info("Scope build for %s: started=%s (included_paths=%d)",
                        project_id, started, len(included_paths) if included_paths else 0)
            if not started:
                return False

            # Wait for the build thread to actually finish so the scope
            # orchestrator doesn't transition to IDLE while still building.
            # The build runs in build_manager's thread; poll until done.
            timeout = 600  # 10 minutes max
            start_t = time.monotonic()
            while build_manager.is_project_building(project_id):
                if time.monotonic() - start_t > timeout:
                    logger.warning("Scope build for %s timed out after %ds", project_id, timeout)
                    return False
                time.sleep(0.5)

            # Check if the build succeeded (no error recorded)
            last_err = build_manager.last_build_error.get(project_id)
            if last_err:
                logger.error("Scope build for %s finished with error: %s", project_id, last_err)
                return False

            return True
        except Exception as e:
            logger.error("Scope build failed for %s: %s", project_id, e)
            return False

    scope_orchestrator.register_build_fn(project_id, _build_fn)
    _registered_projects.add(project_id)


# ── Request models ───────────────────────────────────────────────

class ScopeFilesRequest(BaseModel):
    paths: List[str]


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/projects/{project_id}/scope/status")
def scope_status(project_id: str) -> Dict[str, Any]:
    """Get the Knowledge Scope pipeline status for a project."""
    from codrag.server import _require_project
    proj = _require_project(project_id)

    from codrag.services.scope_orchestrator import scope_orchestrator
    status = scope_orchestrator.status(project_id)
    # Include the persisted included_paths so MCP tools can read them
    status["included_paths"] = list(proj.config.get("included_paths", []))
    return ok(status)


@router.post("/projects/{project_id}/scope/add")
def scope_add_files(project_id: str, req: ScopeFilesRequest) -> Dict[str, Any]:
    """Add files to the Knowledge Scope.

    Persists the updated included_paths set to project config (SQLite),
    then triggers a debounced CodeIndex rebuild (Pro) or marks as stale (Free).
    """
    from codrag.server import _require_project, _get_registry
    proj = _require_project(project_id)

    if not req.paths:
        raise ApiException(
            status_code=400,
            code="EMPTY_PATHS",
            message="No file paths provided",
        )

    # Atomic RMW to avoid racing with concurrent /trace/ignore or
    # /included_paths writers that would overwrite our field.
    def _apply_add(cfg):
        current = set(cfg.get("included_paths", []))
        for p in req.paths:
            if p:
                current.add(p)
                prefix = p + "/"
                current = {x for x in current if not x.startswith(prefix) or x == p}
        return {**cfg, "included_paths": sorted(current)}
    _get_registry().mutate_config(project_id, _apply_add)
    # Re-read for response
    current = set((_get_registry().get_project(project_id).config or {}).get("included_paths", []))

    from codrag.services.scope_orchestrator import scope_orchestrator
    _ensure_build_fn_registered(project_id)
    scope_orchestrator.on_files_added(project_id, req.paths)
    return ok({
        "added": len(req.paths),
        "included_paths": sorted(current),
        "status": scope_orchestrator.status(project_id),
    })


@router.post("/projects/{project_id}/scope/remove")
def scope_remove_files(project_id: str, req: ScopeFilesRequest) -> Dict[str, Any]:
    """Remove files from the Knowledge Scope.

    Persists the updated included_paths set to project config (SQLite),
    then triggers a debounced CodeIndex rebuild (Pro) or marks as stale (Free).
    """
    from codrag.server import _require_project, _get_registry
    proj = _require_project(project_id)

    if not req.paths:
        raise ApiException(
            status_code=400,
            code="EMPTY_PATHS",
            message="No file paths provided",
        )

    # Atomic RMW to avoid racing with concurrent /trace/ignore or
    # /included_paths writers that would overwrite our field.
    def _apply_remove(cfg):
        current = set(cfg.get("included_paths", []))
        for p in req.paths:
            current.discard(p)
            prefix = p + "/"
            current = {x for x in current if not x.startswith(prefix)}
        return {**cfg, "included_paths": sorted(current)}
    _get_registry().mutate_config(project_id, _apply_remove)
    # Re-read for response
    current = set((_get_registry().get_project(project_id).config or {}).get("included_paths", []))

    from codrag.services.scope_orchestrator import scope_orchestrator
    _ensure_build_fn_registered(project_id)
    scope_orchestrator.on_files_removed(project_id, req.paths)
    return ok({
        "removed": len(req.paths),
        "included_paths": sorted(current),
        "status": scope_orchestrator.status(project_id),
    })


@router.post("/projects/{project_id}/scope/rebuild")
def scope_trigger_rebuild(project_id: str) -> Dict[str, Any]:
    """Manually trigger a Knowledge Scope rebuild.

    Used by Free-tier users who see a "stale" indicator and click Rebuild.
    Also useful for Pro users who want to force a rebuild immediately.
    """
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.scope_orchestrator import scope_orchestrator
    started = scope_orchestrator.trigger_rebuild(project_id)

    if not started:
        status = scope_orchestrator.status(project_id)
        if status["state"] == "building":
            raise ApiException(
                status_code=409,
                code="SCOPE_ALREADY_BUILDING",
                message="Scope rebuild is already in progress",
            )
        raise ApiException(
            status_code=409,
            code="NO_PENDING_CHANGES",
            message="No pending scope changes to rebuild",
        )

    return ok({
        "started": True,
        "status": scope_orchestrator.status(project_id),
    })
