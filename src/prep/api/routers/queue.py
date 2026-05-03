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

from prep.api.envelope import ok
from prep.core.events import get_event_bus
from prep.services.pipeline.ghost_guard import purge_ghost_locks
from prep.services.pipeline.scheduler import pipeline_scheduler
from prep.services.pipeline_orchestrator import pipeline_orchestrator

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
# Phase 96D: cancelled and failed are also terminal — they should clear from
# the active queue instead of lingering as "Pending" entries.
_EXCLUDED_STATES = {"completed", "idle", "cancelled", "failed"}


# ── Request models ──────────────────────────────────────────────


class PriorityRequest(BaseModel):
    project_id: str
    level: Literal["none", "boost", "exclusive"]


# ── Helpers ─────────────────────────────────────────────────────


def _resolve_project_name(project_id: str) -> str:
    """Look up a project name from the registry. Returns ID on failure."""
    try:
        from prep.core.project_registry import ProjectRegistry
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

    # Phase 119 Swarm Authority: tie the badge to runtime evidence —
    # the scheduler's swarm window — not to a static capability check.
    # Without this, concurrent independent LLM calls to a swarm-capable
    # model on a swarm-capable stage would all be labeled "Swarming"
    # even though the orchestrator never opened a swarm window.
    is_swarm = False
    if current_stage:
        try:
            from prep.services.token_telemetry import telemetry
            window = pipeline_scheduler.get_swarm_window()
            window_stage = window and getattr(window.get("stage"), "value", window.get("stage"))
            window_matches = (
                window is not None
                and window.get("project_id") == project_id
                and window_stage == current_stage
            )
            # Phase 119+ correction: two complementary signals.
            # (a) scheduler swarm window matches — bureaucratic auth.
            # (b) any live call tagged with swarm_role — runtime truth
            #     that covers the brief gap between SwarmOrchestrator
            #     phase transitions where the window may not yet be
            #     opened/closed in the scheduler. Defensive belt-and-
            #     suspenders; both signals usually agree.
            role_tagged = sum(
                1 for r in telemetry.get_active_requests()
                if r.get("project_id") == project_id and r.get("swarm_role")
            )
            is_swarm = window_matches or role_tagged > 0
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
async def get_queue() -> dict[str, Any]:
    """Aggregated cross-project queue state.

    Merges orchestrator run metadata with scheduler slots/queues.
    Purges ghost locks on every read.

    F-62: Made async with timeout.  The synchronous version blocked
    when swarm workers held locks that ``purge_ghost_locks()`` or
    ``pipeline_scheduler.concurrent_workers_for_project()`` also
    needed.  Now runs in a thread with a 3s timeout — if it can't
    build the queue state in time, returns an empty queue rather
    than hanging the frontend polling loop.
    """
    import asyncio

    def _build_queue():
        return _build_queue_sync()

    try:
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, _build_queue),
            timeout=3.0,
        )
    except (asyncio.TimeoutError, Exception):
        logger.debug("Pipeline queue timed out — returning empty", exc_info=True)
        return ok({"queue": [], "scheduler": {}, "ghost_locks_purged": 0})


def _build_queue_sync() -> dict[str, Any]:
    """Synchronous queue builder — extracted for timeout wrapper."""
    ghost_count = purge_ghost_locks()
    sched_status = pipeline_scheduler.status()

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()  # (project_id, group) already emitted

    # 1. Active runs from orchestrator state machines
    for (pid, group), sm in pipeline_orchestrator._runs.items():
        # Self-heal: PAUSED runs with every stage already complete are
        # effectively done. Promote them to COMPLETED before we read the
        # phase so the queue and the pipeline panel agree on the state. Without
        # this, the panel's client-side settled-override and the queue's raw
        # phase read can disagree (panel says "done", queue shows "Paused").
        sm.reconcile_if_settled()
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

    # 1b. Active tasks tracked by ProgressManager (build threads outside
    # the pipeline orchestrator: index_build, trace_build, knowledge_build,
    # delta_build). The queue is the single source of truth for "what's
    # the daemon doing right now" — if work is running, it appears here so
    # the user can see and cancel it. Without this, a stuck index build
    # silently blocked /full-reset with "Cannot reset while index build is
    # running" while the queue panel showed "No active pipelines."
    from prep.core.events import get_progress_manager
    for entry in get_progress_manager().list_active():
        pid = entry.get("project_id")
        if not pid:
            continue
        ttype = entry.get("type") or "task"
        key = (pid, ttype)
        if key in seen:
            continue
        seen.add(key)
        phase = "cancelling" if entry.get("cancel_requested") else "running"
        items.append(
            _build_queue_item(
                project_id=pid,
                group=ttype,
                phase=phase,
                current_stage=ttype,
                started_at=entry.get("started_at"),
                wait_seconds=None,
            )
        )

    # 2. Queued entries from scheduler (not already in orchestrator)
    # Phase 93: Track which project_ids have orchestrator entries so we
    # can skip scheduler duplicates. The orchestrator state machine already
    # represents the queued stage — adding the scheduler's raw queue entry
    # for the same project creates confusing duplicates in the UI.
    seen_pids: set[str] = {pid for pid, _ in seen}

    nodes = sched_status.get("nodes", {})
    for _node_id, node_info in nodes.items():
        for entry in node_info.get("queued", []):
            qpid = entry["project_id"]
            if qpid in seen_pids:
                continue  # Already represented by an orchestrator entry
            # Queued entries don't have a group in scheduler; use stage to infer
            key = (qpid, entry.get("stage", "queued"))
            if key not in seen:
                seen.add(key)
                seen_pids.add(qpid)
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
            "in_flight_requests": node_info.get("in_flight_requests", 0),
            "current_limit": node_info.get("current_limit", node_info.get("max_concurrent", 1)),
            "discovered_ceiling": node_info.get("discovered_ceiling"),
            "locked_until": node_info.get("locked_until"),
            "aimd_mode": node_info.get("aimd_mode"),
            "state": node_info.get("state", "probing"),
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
        from prep.core.project_registry import ProjectRegistry
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
