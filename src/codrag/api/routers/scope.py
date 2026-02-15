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
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scope"])


# ── Request models ───────────────────────────────────────────────

class ScopeFilesRequest(BaseModel):
    paths: List[str]


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/projects/{project_id}/scope/status")
def scope_status(project_id: str) -> Dict[str, Any]:
    """Get the Knowledge Scope pipeline status for a project."""
    from codrag.server import _require_project
    _require_project(project_id)

    from codrag.services.scope_orchestrator import scope_orchestrator
    return ok(scope_orchestrator.status(project_id))


@router.post("/projects/{project_id}/scope/add")
def scope_add_files(project_id: str, req: ScopeFilesRequest) -> Dict[str, Any]:
    """Add files to the Knowledge Scope.

    Triggers a debounced CodeIndex rebuild (Pro) or marks as stale (Free).
    """
    from codrag.server import _require_project
    _require_project(project_id)

    if not req.paths:
        raise ApiException(
            status_code=400,
            code="EMPTY_PATHS",
            message="No file paths provided",
        )

    from codrag.services.scope_orchestrator import scope_orchestrator
    scope_orchestrator.on_files_added(project_id, req.paths)
    return ok({
        "added": len(req.paths),
        "status": scope_orchestrator.status(project_id),
    })


@router.post("/projects/{project_id}/scope/remove")
def scope_remove_files(project_id: str, req: ScopeFilesRequest) -> Dict[str, Any]:
    """Remove files from the Knowledge Scope.

    Triggers a debounced CodeIndex rebuild (Pro) or marks as stale (Free).
    """
    from codrag.server import _require_project
    _require_project(project_id)

    if not req.paths:
        raise ApiException(
            status_code=400,
            code="EMPTY_PATHS",
            message="No file paths provided",
        )

    from codrag.services.scope_orchestrator import scope_orchestrator
    scope_orchestrator.on_files_removed(project_id, req.paths)
    return ok({
        "removed": len(req.paths),
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
