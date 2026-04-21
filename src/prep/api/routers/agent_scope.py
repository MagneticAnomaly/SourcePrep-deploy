"""
Agent Scope Router — Phase 67 (Agent Knowledge Scopes)
=======================================================

Exposes the AgentScopeManager via HTTP endpoints for the dashboard
AgentScopePanel.

**Endpoints:**
  - GET  /projects/{id}/agent-scope/roles     — list configured roles
  - GET  /projects/{id}/agent-scope/{role}     — get scope for a role
  - POST /projects/{id}/agent-scope/{role}/set — replace entire scope
  - POST /projects/{id}/agent-scope/{role}/add — add paths to scope
  - POST /projects/{id}/agent-scope/{role}/remove — remove paths
  - DELETE /projects/{id}/agent-scope/{role}   — delete role scope
  - GET  /projects/{id}/agent-scope            — get all scopes
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel

from prep.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent-scope"])


# ── Request models ───────────────────────────────────────────────

class AgentScopePathsRequest(BaseModel):
    paths: List[str]


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/projects/{project_id}/agent-scope")
def get_all_agent_scopes(project_id: str) -> Dict[str, Any]:
    """Get all configured agent scopes for a project."""
    from prep.server import _require_project
    _require_project(project_id)

    from prep.core.agent_scope_manager import agent_scope_manager
    scopes = agent_scope_manager.get_all_agent_scopes(project_id)
    roles = agent_scope_manager.list_agent_roles(project_id)
    return ok({
        "roles": roles,
        "scopes": scopes,
    })


@router.get("/projects/{project_id}/agent-scope/roles")
def list_agent_roles(project_id: str) -> Dict[str, Any]:
    """List all roles that have a configured scope."""
    from prep.server import _require_project
    _require_project(project_id)

    from prep.core.agent_scope_manager import agent_scope_manager
    roles = agent_scope_manager.list_agent_roles(project_id)
    return ok({"roles": roles})


@router.get("/projects/{project_id}/agent-scope/{role}")
def get_agent_scope(project_id: str, role: str) -> Dict[str, Any]:
    """Get the file scope for a specific agent role."""
    from prep.server import _require_project
    _require_project(project_id)

    from prep.core.agent_scope_manager import agent_scope_manager
    paths = agent_scope_manager.get_agent_scope(project_id, role)
    return ok({
        "role": role,
        "paths": paths,
        "count": len(paths),
    })


@router.post("/projects/{project_id}/agent-scope/{role}/set")
def set_agent_scope(
    project_id: str, role: str, req: AgentScopePathsRequest
) -> Dict[str, Any]:
    """Replace the entire scope for an agent role."""
    from prep.server import _require_project
    _require_project(project_id)

    if not role.strip():
        raise ApiException(
            status_code=400,
            code="INVALID_ROLE",
            message="Role name cannot be empty",
        )

    from prep.core.agent_scope_manager import agent_scope_manager
    paths = agent_scope_manager.set_agent_scope(project_id, role, req.paths)
    return ok({
        "role": role,
        "paths": paths,
        "count": len(paths),
    })


@router.post("/projects/{project_id}/agent-scope/{role}/add")
def add_agent_paths(
    project_id: str, role: str, req: AgentScopePathsRequest
) -> Dict[str, Any]:
    """Add paths to an agent's scope."""
    from prep.server import _require_project
    _require_project(project_id)

    if not req.paths:
        raise ApiException(
            status_code=400,
            code="EMPTY_PATHS",
            message="No file paths provided",
        )

    from prep.core.agent_scope_manager import agent_scope_manager
    paths = agent_scope_manager.add_agent_paths(project_id, role, req.paths)
    return ok({
        "role": role,
        "paths": paths,
        "count": len(paths),
        "added": len(req.paths),
    })


@router.post("/projects/{project_id}/agent-scope/{role}/remove")
def remove_agent_paths(
    project_id: str, role: str, req: AgentScopePathsRequest
) -> Dict[str, Any]:
    """Remove paths from an agent's scope."""
    from prep.server import _require_project
    _require_project(project_id)

    if not req.paths:
        raise ApiException(
            status_code=400,
            code="EMPTY_PATHS",
            message="No file paths provided",
        )

    from prep.core.agent_scope_manager import agent_scope_manager
    paths = agent_scope_manager.remove_agent_paths(project_id, role, req.paths)
    return ok({
        "role": role,
        "paths": paths,
        "count": len(paths),
        "removed": len(req.paths),
    })


@router.delete("/projects/{project_id}/agent-scope/{role}")
def delete_agent_scope(project_id: str, role: str) -> Dict[str, Any]:
    """Delete the entire scope for an agent role."""
    from prep.server import _require_project
    _require_project(project_id)

    from prep.core.agent_scope_manager import agent_scope_manager
    deleted = agent_scope_manager.delete_agent_scope(project_id, role)
    return ok({
        "role": role,
        "deleted": deleted,
    })


# ── Phase 67: Auto-Populate ──────────────────────────────────────

class AutoPopulateRequest(BaseModel):
    """Optional tuning parameters for auto-populate."""
    min_score: float = 0.25
    max_files: int = 80
    apply: bool = True  # If True, persist the result directly as the new scope


@router.post("/projects/{project_id}/agent-scope/{role}/auto-populate")
def auto_populate_agent_scope(
    project_id: str, role: str, req: AutoPopulateRequest = AutoPopulateRequest()
) -> Dict[str, Any]:
    """Use Prep's role projection engine to intelligently select files for
    an agent's knowledge scope.

    This performs a deep search across the entire code graph, scoring every
    file against the resolved RoleVector for the given role string. Files
    above `min_score` are returned (capped at `max_files`).

    If `apply=True` (default), the resulting paths are immediately saved
    as the agent's scope, replacing any existing selection.

    **Flow:**
      1. Resolve role string → RoleVector via role_resolver
      2. Score every file via role_projection._python_scoring (or Rust FFI)
      3. Filter by min_score threshold and cap at max_files
      4. Optionally persist via agent_scope_manager.set_agent_scope
      5. Return recommended paths + scores for UI display
    """
    import time
    from pathlib import Path
    from prep.server import _require_project
    from prep.core.project_registry import project_index_dir

    t0 = time.time()
    project = _require_project(project_id)
    idx_dir = Path(project_index_dir(project))

    # 1. Resolve role → RoleVector
    from prep.core.atlas.role_resolver import resolve_role
    role_vector = resolve_role(role)

    # 2. Score all files using the existing projection engine
    from prep.core.atlas.role_projection import _python_scoring, _try_rust_scoring
    scored = _try_rust_scoring(role_vector, idx_dir)
    if scored is None:
        scored = _python_scoring(role_vector, idx_dir)

    if scored is None:
        raise ApiException(
            status_code=404,
            code="NO_GRAPH_DATA",
            message="No trace data available. Build the graph first.",
        )

    # 3. Filter by threshold + cap
    selected = [
        (fp, entry, score)
        for fp, entry, score in scored
        if score >= req.min_score
    ][:req.max_files]

    recommended_paths = [fp for fp, _, _ in selected]
    scored_details = [
        {
            "path": fp,
            "score": round(score, 4),
            "layer": entry.get("architecture_layer", "unknown"),
            "tags": entry.get("domain_tags", [])[:4],
        }
        for fp, entry, score in selected
    ]

    # 4. Optionally persist
    if req.apply and recommended_paths:
        from prep.core.agent_scope_manager import agent_scope_manager
        agent_scope_manager.set_agent_scope(project_id, role, recommended_paths)

    elapsed_ms = round((time.time() - t0) * 1000)
    logger.info(
        "[AutoPopulate] Role '%s' → %d files selected (%.0fms, threshold=%.2f)",
        role, len(recommended_paths), elapsed_ms, req.min_score,
    )

    return ok({
        "role": role,
        "resolved_as": role_vector.display_name,
        "recommended_paths": recommended_paths,
        "scored": scored_details,
        "count": len(recommended_paths),
        "total_scored": len(scored),
        "applied": req.apply,
        "elapsed_ms": elapsed_ms,
    })
