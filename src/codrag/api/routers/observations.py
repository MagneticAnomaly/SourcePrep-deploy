"""
CoDRAG Observations Router — Phase 39 (Session Continuity)
============================================================

Exposes the observation store via HTTP endpoints for MCP tools
and the dashboard project health panel.

**Endpoints:**
  - POST /projects/{id}/observations          — save an observation
  - GET  /projects/{id}/observations          — list/search observations
  - GET  /projects/{id}/observations/stats    — observation statistics
  - DELETE /projects/{id}/observations        — clear all observations
  - DELETE /projects/{id}/observations/{obs_id} — delete one observation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["observations"])


# ── Request/Response Models ──────────────────────────────────────

class SaveObservationRequest(BaseModel):
    content: str
    file_path: Optional[str] = None
    symbol: Optional[str] = None
    category: Optional[str] = "note"
    created_by: Optional[str] = None


class SearchObservationsParams(BaseModel):
    query: Optional[str] = None
    file_path: Optional[str] = None
    limit: int = 10
    include_stale: bool = True


# ── Helpers ──────────────────────────────────────────────────────

def _get_store():
    """Get the observation store singleton."""
    from codrag.services.observation_store import observation_store
    return observation_store


def _require_project(project_id: str):
    """Validate project exists."""
    from codrag.services.project_helpers import require_project
    return require_project(project_id)


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/projects/{project_id}/observations")
async def save_observation(project_id: str, body: SaveObservationRequest):
    """Save an agent observation linked to a file or symbol."""
    _require_project(project_id)
    store = _get_store()

    try:
        obs_id = store.save(
            project_id=project_id,
            content=body.content,
            file_path=body.file_path,
            symbol_fqn=body.symbol,
            category=body.category or "note",
            created_by=body.created_by,
        )
    except ValueError as e:
        raise ApiException(400, "VALIDATION_ERROR", str(e))

    return ok({"id": obs_id, "saved": True})


@router.get("/projects/{project_id}/observations")
async def list_observations(
    project_id: str,
    query: Optional[str] = None,
    file_path: Optional[str] = None,
    limit: int = 10,
    include_stale: bool = True,
):
    """List or search observations for a project."""
    _require_project(project_id)
    store = _get_store()

    if file_path:
        results = store.get_for_file(project_id, file_path, include_stale=include_stale)
    elif query:
        results = store.get_for_query(
            project_id, query, limit=limit, include_stale=include_stale,
        )
    else:
        results = store.get_recent(project_id, limit=limit, include_stale=include_stale)

    return ok({
        "observations": [obs.to_dict() for obs in results],
        "count": len(results),
    })


@router.get("/projects/{project_id}/observations/stats")
async def observation_stats(project_id: str):
    """Get observation statistics for the project health panel."""
    _require_project(project_id)
    store = _get_store()
    stats = store.get_stats(project_id)
    return ok(stats)


@router.delete("/projects/{project_id}/observations")
async def clear_observations(project_id: str):
    """Clear all observations for a project."""
    _require_project(project_id)
    store = _get_store()
    deleted = store.clear_project(project_id)
    return ok({"deleted": deleted})


@router.delete("/projects/{project_id}/observations/{observation_id}")
async def delete_observation(project_id: str, observation_id: str):
    """Delete a single observation."""
    _require_project(project_id)
    store = _get_store()
    existed = store.delete(observation_id)
    if not existed:
        raise ApiException(404, "NOT_FOUND", f"Observation {observation_id} not found")
    return ok({"deleted": True})
