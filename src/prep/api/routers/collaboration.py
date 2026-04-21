"""FastAPI routes for agent collaboration data — Phase 73.5.

Exposes activity, delta, conflicts, claims, and observations-by-agent.
The MCP server calls these endpoints via HTTP proxy.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Query

from prep.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["collaboration"])


def _get_hub():
    from prep.services.collaboration import get_collaboration_hub
    hub = get_collaboration_hub()
    if hub is None:
        raise ApiException(
            503, "COLLAB_NOT_READY",
            "Collaboration hub not initialized",
        )
    return hub


def _get_obs_store():
    from prep.services.observation_store import observation_store
    return observation_store


# ── Activity ────────────────────────────────────────────────────


@router.get("/projects/{project_id}/collaboration/activity")
async def get_activity(
    project_id: str,
    limit: int = Query(50, le=200),
    since: Optional[float] = None,
):
    hub = _get_hub()
    entries = hub.activity.get_recent(
        project_id, limit=limit, since=since,
    )
    return ok({"entries": [e.to_dict() for e in entries]})


# ── Observations by agent ───────────────────────────────────────


@router.get("/projects/{project_id}/collaboration/observations")
async def get_observations_by_agent(
    project_id: str,
    created_by: str = Query(...),
    limit: int = Query(50, le=200),
    visibility: Optional[str] = None,
):
    store = _get_obs_store()
    results = store.get_by_agent(
        project_id, created_by,
        visibility_filter=visibility,
        limit=limit,
    )
    return ok({"observations": [o.to_dict() for o in results]})


# ── Structural delta ────────────────────────────────────────────


@router.get("/projects/{project_id}/collaboration/delta")
async def get_delta(
    project_id: str,
    since: Optional[float] = None,
):
    hub = _get_hub()
    if since is None:
        since = time.time() - 7 * 86400  # default: 7 days
    delta = hub.snapshots.compute_delta(project_id, since=since)
    return ok({
        "since": delta.since,
        "until": delta.until,
        "hub_changes": delta.hub_changes,
        "module_changes": delta.module_changes,
        "is_empty": delta.is_empty,
    })


# ── Conflicts ───────────────────────────────────────────────────


@router.get("/projects/{project_id}/collaboration/conflicts")
async def get_conflicts(project_id: str):
    hub = _get_hub()
    conflicts = hub.conflicts.get_active(project_id)
    return ok({"conflicts": [
        {
            "id": c.id, "file_path": c.file_path,
            "agent_a": c.agent_a,
            "agent_a_assessment": c.agent_a_assessment,
            "agent_b": c.agent_b,
            "agent_b_assessment": c.agent_b_assessment,
            "conflict_type": c.conflict_type,
            "resolution": c.resolution,
            "detected_at": c.detected_at,
        }
        for c in conflicts
    ]})


@router.post(
    "/projects/{project_id}/collaboration/conflicts/{conflict_id}/resolve",
)
async def resolve_conflict(
    project_id: str,
    conflict_id: str,
    resolution: str = Query(...),
):
    hub = _get_hub()
    result = hub.conflicts.resolve(conflict_id, resolution)
    return ok({"resolved": result})


# ── Claims ──────────────────────────────────────────────────────


@router.get("/projects/{project_id}/collaboration/claims")
async def get_claims(project_id: str):
    hub = _get_hub()
    claims = hub.claims.get_active(project_id)
    return ok({"claims": [
        {
            "id": c.id, "agent_role": c.agent_role,
            "path": c.path, "reason": c.reason,
            "claimed_at": c.claimed_at, "expires_at": c.expires_at,
        }
        for c in claims
    ]})


@router.post("/projects/{project_id}/collaboration/claims")
async def create_claim(
    project_id: str,
    agent_role: str = Query(...),
    path: str = Query(...),
    reason: str = Query(""),
):
    hub = _get_hub()
    claim_id = hub.claims.claim(project_id, agent_role, path, reason)
    return ok({"id": claim_id})


@router.delete("/projects/{project_id}/collaboration/claims/{claim_id}")
async def release_claim(project_id: str, claim_id: str):
    hub = _get_hub()
    result = hub.claims.release(claim_id)
    return ok({"released": result})


# ── Consensus ──────────────────────────────────────────────────


@router.get("/projects/{project_id}/collaboration/consensus")
async def get_consensus(
    project_id: str,
    min_agents: int = Query(2, ge=2),
    since_days: int = Query(30, ge=1, le=365),
):
    store = _get_obs_store()
    scores = store.get_consensus_scores(
        project_id, min_agents=min_agents, since_days=since_days,
    )
    return ok({"scores": scores})


# ── Push Summary ───────────────────────────────────────────────


@router.get("/projects/{project_id}/collaboration/push-summary")
async def get_push_summary(project_id: str):
    """Lightweight push summary from activity store."""
    hub = _get_hub()
    entries = hub.activity.get_recent(project_id, limit=50)
    push_entries = [
        e for e in entries
        if "push" in (e.action if hasattr(e, "action") else "").lower()
    ]
    return ok({
        "total_pushes": len(push_entries),
        "latest_push_at": push_entries[0].created_at if push_entries else None,
    })
