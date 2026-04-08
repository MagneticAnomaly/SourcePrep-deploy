"""
Queue API Router — Phase 75 Task 2
====================================

Aggregated cross-project pipeline queue state.

Endpoints:
  - GET  /system/pipeline-queue          — queue state (runs + scheduler)
  - POST /system/pipeline-queue/priority — set project priority
  - POST /system/pipeline-queue/purge-ghosts — manual ghost lock purge
"""
from __future__ import annotations

import logging
import time
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ok
from codrag.core.events import get_event_bus
from codrag.services.pipeline.ghost_guard import purge_ghost_locks
from codrag.services.pipeline.scheduler import pipeline_scheduler
from codrag.services.pipeline_orchestrator import pipeline_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system/pipeline-queue", tags=["queue"])

# Phase ordering for sort: lower = higher priority in output
_PHASE_ORDER = {
    "running": 0,
    "pausing": 0,  # treat as running
    "recovering": 0,
    "paused": 1,
    "queued": 2,
    "failed": 3,
    "cancelling": 3,
    "cancelled": 3,
}

# States to exclude from queue display
_EXCLUDED_STATES = {"completed", "idle"}


# ── Request models ──────────────────────────────────────────────


class PriorityRequest(BaseModel):
    project_id: str
    level: Literal["none", "boost", "exclusive"]


# ── Helpers ─────────────────────────────────────────────────────


def _resolve_project_name(project_id: str) -> str:
    """Look up a project name from the registry. Returns ID on failure."""
    try:
        from codrag.core.project_registry import ProjectRegistry
        proj = ProjectRegistry().get_project(project_id)
        if proj:
            return proj.name
    except Exception:
        pass
    return project_id


def _build_queue_item(
    project_id: str,
    group: str,
    phase: str,
    current_stage: str | None,
    started_at: float | None,
    wait_seconds: float | None,
) -> dict[str, Any]:
    """Construct a single queue item dict."""
    now = time.time()
    elapsed = round(now - started_at, 1) if started_at else None

    priority = pipeline_scheduler.get_priority(project_id)
    workers, node_id = pipeline_scheduler.concurrent_workers_for_project(
        project_id, stage=current_stage,
    )

    # Phase 82: Determine swarm mode from actual model capability,
    # not just stage name.
    is_swarm = False
    if current_stage:
        try:
            from codrag.services.pipeline.scheduler import SWARM_CAPABLE_STAGES, is_swarm_active_for_stage
            from codrag.services.pipeline._model_resolution import resolve_model_for_stage
            if current_stage in SWARM_CAPABLE_STAGES:
                resolved = resolve_model_for_stage(project_id, current_stage)
                if resolved:
                    is_swarm = is_swarm_active_for_stage(current_stage, *resolved)
        except Exception:
            pass

    return {
        "project_id": project_id,
        "project_name": _resolve_project_name(project_id),
        "group": group,
        "phase": phase,
        "current_stage": current_stage,
        "started_at": started_at,
        "elapsed_seconds": elapsed,
        "wait_seconds": wait_seconds,
        "priority": priority,
        "compute_node": node_id,
        "concurrent_workers": workers,
        "is_swarm": is_swarm,
    }


def _sort_key(item: dict[str, Any]) -> int:
    return _PHASE_ORDER.get(item["phase"], 99)


# ── Endpoints ───────────────────────────────────────────────────


@router.get("")
def get_queue() -> dict[str, Any]:
    """Aggregated cross-project queue state.

    Merges orchestrator run metadata with scheduler slots/queues.
    Purges ghost locks on every read.
    """
    ghost_count = purge_ghost_locks()
    sched_status = pipeline_scheduler.status()

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()  # (project_id, group) already emitted

    # 1. Active runs from orchestrator state machines
    for (pid, group), sm in pipeline_orchestrator._runs.items():
        state_val = sm.state.value
        if state_val in _EXCLUDED_STATES:
            continue
        seen.add((pid, group))
        items.append(
            _build_queue_item(
                project_id=pid,
                group=group,
                phase=state_val,
                current_stage=sm.current_stage,
                started_at=sm.started_at,
                wait_seconds=None,
            )
        )

    # 2. Queued entries from scheduler (not already in orchestrator)
    nodes = sched_status.get("nodes", {})
    for _node_id, node_info in nodes.items():
        for entry in node_info.get("queued", []):
            qpid = entry["project_id"]
            # Queued entries don't have a group in scheduler; use stage to infer
            qgroup = "queued"
            key = (qpid, qgroup)
            if key not in seen:
                seen.add(key)
                items.append(
                    _build_queue_item(
                        project_id=qpid,
                        group=entry.get("stage", "unknown"),
                        phase="queued",
                        current_stage=entry.get("stage"),
                        started_at=None,
                        wait_seconds=entry.get("waiting_seconds"),
                    )
                )

    # Sort: running first, then paused, then queued, then failed
    items.sort(key=_sort_key)

    # Build node summary
    node_summary: dict[str, Any] = {}
    for nid, node_info in nodes.items():
        node_summary[nid] = {
            "max_concurrent": node_info.get("max_concurrent", 1),
            "current_load": node_info.get("current_load", 0),
            "active": node_info.get("active", {}),
            "queued": node_info.get("queued", []),
        }

    return ok({
        "queue": items,
        "nodes": node_summary,
        "ghost_locks_purged": ghost_count,
    })


@router.post("/priority")
def set_priority(req: PriorityRequest) -> dict[str, Any]:
    """Set pipeline priority for a project."""
    pipeline_scheduler.set_priority(req.project_id, req.level)

    # Persist to project config
    try:
        from codrag.core.project_registry import ProjectRegistry
        registry = ProjectRegistry()
        proj = registry.get_project(req.project_id)
        if proj:
            cfg = proj.config if isinstance(proj.config, dict) else {}
            cfg["priority_level"] = req.level
            registry.update_project(req.project_id, config=cfg)
    except Exception:
        logger.debug("Could not persist priority to project config", exc_info=True)

    # Emit SSE event
    get_event_bus().emit("queue_changed", {
        "reason": "priority_changed",
        "project_id": req.project_id,
        "level": req.level,
    })

    return ok({"project_id": req.project_id, "level": req.level})


@router.post("/purge-ghosts")
def purge_ghosts() -> dict[str, Any]:
    """Manual ghost lock purge."""
    purged = purge_ghost_locks()
    return ok({"purged": purged})
