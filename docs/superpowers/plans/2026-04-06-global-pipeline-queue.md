# Global Pipeline Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-project pipeline queue with ghost lock auto-healing, a system-level API, and a sidebar UI widget.

**Architecture:** New `ghost_guard.py` module cross-checks scheduler locks against build orchestrator threads. New `queue.py` router aggregates scheduler + orchestrator state into a unified API. New `SidebarPipelineQueue.tsx` renders the queue in the sidebar with controls. The orchestrator emits `queue_changed` SSE events on state transitions. All new logic lives in dedicated files — the orchestrator gets ~5 added lines.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript (frontend), existing SSE event bus

**Spec:** `docs/superpowers/specs/2026-04-06-global-pipeline-queue-design.md`

---

### Task 1: Ghost Guard Module

**Files:**
- Create: `src/prep/services/pipeline/ghost_guard.py`
- Test: `tests/test_ghost_guard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ghost_guard.py
"""Tests for the ghost lock cross-check guard."""
import pytest
from unittest.mock import MagicMock, patch


def test_purge_ghost_locks_cleans_orphaned_lock():
    """If scheduler says project holds a lock but no build threads are alive, purge it."""
    mock_scheduler = MagicMock()
    mock_scheduler.status.return_value = {
        "nodes": {
            "local:default_ollama": {
                "max_concurrent": 1,
                "current_load": 1,
                "active": {"proj-dead": "catalogue"},
                "queued": [],
            }
        },
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }

    mock_build_orch = MagicMock()
    mock_build_orch.is_any_active.return_value = False  # no threads alive

    mock_event_bus = MagicMock()

    from prep.services.pipeline.ghost_guard import purge_ghost_locks

    count = purge_ghost_locks(
        scheduler=mock_scheduler,
        build_orchestrator=mock_build_orch,
        event_bus=mock_event_bus,
    )

    assert count == 1
    mock_scheduler.clean_locks.assert_called_once_with("proj-dead")
    mock_event_bus.emit.assert_called_once()
    call_args = mock_event_bus.emit.call_args
    assert call_args[0][0] == "queue_changed"
    assert call_args[0][1]["reason"] == "ghost_purged"


def test_purge_ghost_locks_no_op_when_threads_alive():
    """If build threads are alive for a locked project, do nothing."""
    mock_scheduler = MagicMock()
    mock_scheduler.status.return_value = {
        "nodes": {
            "local:default_ollama": {
                "max_concurrent": 1,
                "current_load": 1,
                "active": {"proj-alive": "catalogue"},
                "queued": [],
            }
        },
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }

    mock_build_orch = MagicMock()
    mock_build_orch.is_any_active.return_value = True  # threads alive

    mock_event_bus = MagicMock()

    from prep.services.pipeline.ghost_guard import purge_ghost_locks

    count = purge_ghost_locks(
        scheduler=mock_scheduler,
        build_orchestrator=mock_build_orch,
        event_bus=mock_event_bus,
    )

    assert count == 0
    mock_scheduler.clean_locks.assert_not_called()
    mock_event_bus.emit.assert_not_called()


def test_purge_ghost_locks_multiple_nodes():
    """Purges across multiple compute nodes in one pass."""
    mock_scheduler = MagicMock()
    mock_scheduler.status.return_value = {
        "nodes": {
            "local:ollama1": {
                "max_concurrent": 1,
                "current_load": 1,
                "active": {"proj-a": "catalogue"},
                "queued": [],
            },
            "cloud:openai": {
                "max_concurrent": 3,
                "current_load": 1,
                "active": {"proj-b": "epistemic"},
                "queued": [],
            },
        },
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }

    mock_build_orch = MagicMock()
    # proj-a is alive, proj-b is dead
    mock_build_orch.is_any_active.side_effect = lambda pid: pid == "proj-a"

    mock_event_bus = MagicMock()

    from prep.services.pipeline.ghost_guard import purge_ghost_locks

    count = purge_ghost_locks(
        scheduler=mock_scheduler,
        build_orchestrator=mock_build_orch,
        event_bus=mock_event_bus,
    )

    assert count == 1
    mock_scheduler.clean_locks.assert_called_once_with("proj-b")


def test_purge_ghost_locks_empty_scheduler():
    """No active slots means nothing to purge."""
    mock_scheduler = MagicMock()
    mock_scheduler.status.return_value = {
        "nodes": {},
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }

    mock_build_orch = MagicMock()
    mock_event_bus = MagicMock()

    from prep.services.pipeline.ghost_guard import purge_ghost_locks

    count = purge_ghost_locks(
        scheduler=mock_scheduler,
        build_orchestrator=mock_build_orch,
        event_bus=mock_event_bus,
    )

    assert count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ghost_guard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prep.services.pipeline.ghost_guard'`

- [ ] **Step 3: Write the implementation**

```python
# src/prep/services/pipeline/ghost_guard.py
"""
Ghost Guard — Phase 75
======================

Active cross-check that validates scheduler lock integrity against
build orchestrator thread liveness. Purges phantom scheduler locks
left behind by crashed worker threads.

Called on every queue read and on build transition failures to
guarantee the queue never deadlocks from ghost locks.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def purge_ghost_locks(
    scheduler=None,
    build_orchestrator=None,
    event_bus=None,
) -> int:
    """Cross-check scheduler locks against build orchestrator threads.

    For each project holding a scheduler slot, verify at least one
    build thread is alive via ``BuildOrchestrator.is_any_active()``.
    If the scheduler claims a lock but no threads exist, the lock
    is a ghost — purge it.

    Args:
        scheduler: PipelineScheduler instance. Defaults to module singleton.
        build_orchestrator: BuildOrchestrator instance. Defaults to module singleton.
        event_bus: EventBus instance. Defaults to module singleton.

    Returns:
        Number of ghost locks purged.
    """
    if scheduler is None:
        from prep.services.pipeline.scheduler import pipeline_scheduler
        scheduler = pipeline_scheduler
    if build_orchestrator is None:
        from prep.services.build_orchestrator import build_orchestrator as _bo
        build_orchestrator = _bo
    if event_bus is None:
        from prep.core.events import get_event_bus
        event_bus = get_event_bus()

    status = scheduler.status()
    nodes = status.get("nodes", {})

    # Collect all unique project_ids that hold active slots
    locked_projects: set[str] = set()
    for node_info in nodes.values():
        active = node_info.get("active", {})
        locked_projects.update(active.keys())

    if not locked_projects:
        return 0

    purged = 0
    for project_id in locked_projects:
        if not build_orchestrator.is_any_active(project_id):
            logger.warning(
                "Ghost Guard: project %s holds scheduler lock but has no "
                "active build threads — purging ghost lock",
                project_id,
            )
            scheduler.clean_locks(project_id)
            purged += 1

    if purged > 0:
        event_bus.emit("queue_changed", {
            "reason": "ghost_purged",
            "purged_count": purged,
        })
        logger.info("Ghost Guard: purged %d ghost lock(s)", purged)

    return purged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_ghost_guard.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/prep/services/pipeline/ghost_guard.py tests/test_ghost_guard.py
git commit -m "feat(queue): add ghost guard module for scheduler lock cross-check"
```

---

### Task 2: Queue API Router

**Files:**
- Create: `src/prep/api/routers/queue.py`
- Modify: `src/prep/server.py:569-592` (add router import + registration)
- Test: `tests/test_queue_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_queue_router.py
"""Tests for the global pipeline queue API router."""
import pytest
from unittest.mock import MagicMock, patch


def _make_state_machine(group, state_value, current_stage_value, started_at):
    """Create a mock PipelineGroupStateMachine."""
    sm = MagicMock()
    sm.group = group
    sm.state = MagicMock()
    sm.state.value = state_value
    sm.current_stage = current_stage_value
    sm.started_at = started_at
    sm.stage_snapshots = {}
    return sm


@patch("prep.api.routers.queue.purge_ghost_locks", return_value=0)
@patch("prep.api.routers.queue.pipeline_orchestrator")
@patch("prep.api.routers.queue.pipeline_scheduler")
@patch("prep.api.routers.queue._resolve_project_name", return_value="TestProject")
def test_get_pipeline_queue_running(mock_name, mock_sched, mock_orch, mock_purge):
    """GET /system/pipeline-queue returns running pipelines."""
    mock_sched.status.return_value = {
        "nodes": {
            "local:ollama": {
                "max_concurrent": 1,
                "current_load": 1,
                "active": {"proj-1": "catalogue"},
                "queued": [],
            }
        },
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }
    mock_sched.get_priority.return_value = "none"
    mock_sched.concurrent_workers_for_project.return_value = (1, "local:ollama")

    sm = _make_state_machine("fast_sync", "running", "catalogue", 1712431440.0)
    mock_orch._runs = {("proj-1", "fast_sync"): sm}

    from prep.api.routers.queue import get_pipeline_queue

    result = get_pipeline_queue()
    data = result["data"]
    queue = data["queue"]

    assert len(queue) == 1
    item = queue[0]
    assert item["project_id"] == "proj-1"
    assert item["project_name"] == "TestProject"
    assert item["group"] == "fast_sync"
    assert item["phase"] == "running"
    assert item["current_stage"] == "catalogue"
    assert item["started_at"] == 1712431440.0
    assert data["ghost_locks_purged"] == 0


@patch("prep.api.routers.queue.purge_ghost_locks", return_value=0)
@patch("prep.api.routers.queue.pipeline_orchestrator")
@patch("prep.api.routers.queue.pipeline_scheduler")
@patch("prep.api.routers.queue._resolve_project_name", return_value="TestProject")
def test_get_pipeline_queue_includes_queued(mock_name, mock_sched, mock_orch, mock_purge):
    """GET /system/pipeline-queue includes queued entries from scheduler."""
    mock_sched.status.return_value = {
        "nodes": {
            "local:ollama": {
                "max_concurrent": 1,
                "current_load": 1,
                "active": {"proj-1": "catalogue"},
                "queued": [
                    {"project_id": "proj-2", "stage": "catalogue", "waiting_seconds": 45.2},
                ],
            }
        },
        "priority": {"project_id": None, "level": "none", "projects": {"proj-1": "boost"}},
    }
    mock_sched.get_priority.side_effect = lambda pid: "boost" if pid == "proj-1" else "none"
    mock_sched.concurrent_workers_for_project.return_value = (1, "local:ollama")

    sm = _make_state_machine("fast_sync", "running", "catalogue", 1712431440.0)
    mock_orch._runs = {("proj-1", "fast_sync"): sm}

    from prep.api.routers.queue import get_pipeline_queue

    result = get_pipeline_queue()
    queue = result["data"]["queue"]

    assert len(queue) == 2
    # Running item first
    assert queue[0]["phase"] == "running"
    assert queue[0]["priority"] == "boost"
    # Queued item second
    assert queue[1]["phase"] == "queued"
    assert queue[1]["wait_seconds"] == 45.2


@patch("prep.api.routers.queue.purge_ghost_locks", return_value=0)
@patch("prep.api.routers.queue.pipeline_orchestrator")
@patch("prep.api.routers.queue.pipeline_scheduler")
def test_get_pipeline_queue_empty(mock_sched, mock_orch, mock_purge):
    """GET /system/pipeline-queue returns empty when nothing is running."""
    mock_sched.status.return_value = {
        "nodes": {},
        "priority": {"project_id": None, "level": "none", "projects": {}},
    }
    mock_orch._runs = {}

    from prep.api.routers.queue import get_pipeline_queue

    result = get_pipeline_queue()
    assert result["data"]["queue"] == []


def test_set_priority_delegates_to_scheduler():
    """POST /system/pipeline-queue/priority delegates to scheduler."""
    with patch("prep.api.routers.queue.pipeline_scheduler") as mock_sched, \
         patch("prep.api.routers.queue._persist_priority") as mock_persist:
        mock_sched.get_priority.return_value = "boost"

        from prep.api.routers.queue import set_queue_priority, PriorityRequest

        req = PriorityRequest(project_id="proj-1", level="boost")
        result = set_queue_priority(req)

        mock_sched.set_priority.assert_called_once_with("proj-1", "boost")
        assert result["data"]["project_id"] == "proj-1"
        assert result["data"]["level"] == "boost"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_queue_router.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/prep/api/routers/queue.py
"""
Prep Global Pipeline Queue Router — Phase 75
================================================

System-level endpoints for cross-project pipeline queue visibility,
priority management, and ghost lock remediation.

Endpoints:
  - GET  /system/pipeline-queue          — aggregated queue state
  - POST /system/pipeline-queue/priority — set project priority
  - POST /system/pipeline-queue/purge-ghosts — manual ghost lock purge
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from prep.api.envelope import ok
from prep.services.pipeline.ghost_guard import purge_ghost_locks
from prep.services.pipeline.scheduler import pipeline_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["queue"])


# ── Request/Response models ──────────────────────────────────────

class PriorityRequest(BaseModel):
    project_id: str
    level: Literal["none", "boost", "exclusive"]


class QueueItem(BaseModel):
    project_id: str
    project_name: str
    group: str
    phase: str  # running, queued, paused, failed
    current_stage: Optional[str] = None
    started_at: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    wait_seconds: Optional[float] = None
    priority: str = "none"
    compute_node: Optional[str] = None
    concurrent_workers: int = 0


# ── Helpers ──────────────────────────────────────────────────────

def _resolve_project_name(project_id: str) -> str:
    """Look up project display name from registry."""
    try:
        from prep.core.project_registry import ProjectRegistry
        registry = ProjectRegistry()
        project = registry.get_project(project_id)
        if project:
            return project.name
    except Exception:
        pass
    return project_id[:8]


def _persist_priority(project_id: str, level: str) -> None:
    """Persist priority level to project config for restore on restart."""
    try:
        from prep.core.project_registry import ProjectRegistry
        registry = ProjectRegistry()
        project = registry.get_project(project_id)
        if project:
            config = project.config if isinstance(project.config, dict) else {}
            config["priority_level"] = level
            config["is_starred"] = level != "none"
            registry.update_project(project_id, config=config)
    except Exception:
        logger.debug("Failed to persist priority for %s", project_id, exc_info=True)


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/pipeline-queue")
def get_pipeline_queue() -> Dict[str, Any]:
    """Aggregated cross-project pipeline queue state.

    Merges scheduler slot/queue state with orchestrator run metadata.
    Calls ghost guard on every read to auto-purge stale locks.
    """
    # Auto-heal ghost locks
    ghosts_purged = purge_ghost_locks()

    # Get scheduler state
    sched_status = pipeline_scheduler.status()
    nodes = sched_status.get("nodes", {})

    # Get orchestrator runs
    try:
        from prep.services.pipeline.orchestrator import pipeline_orchestrator
        runs = dict(pipeline_orchestrator._runs)
    except Exception:
        runs = {}

    now = time.time()
    queue_items: List[Dict[str, Any]] = []
    seen_projects: set[str] = set()

    # 1. Active runs from orchestrator (authoritative for running/paused state)
    for (project_id, group), sm in runs.items():
        state_val = sm.state.value if hasattr(sm.state, "value") else str(sm.state)
        phase = state_val.lower()

        # Map state machine states to simplified queue phases
        if phase in ("running", "acquiring"):
            phase = "running"
        elif phase in ("paused", "pausing"):
            phase = "paused"
        elif phase in ("queued",):
            phase = "queued"
        elif phase in ("completed", "idle"):
            continue  # Don't show completed runs in queue
        else:
            phase = phase  # failed, etc.

        started_at = getattr(sm, "started_at", None)
        elapsed = (now - started_at) if started_at else None
        current_stage = getattr(sm, "current_stage", None)

        workers, node = pipeline_scheduler.concurrent_workers_for_project(project_id)
        priority = pipeline_scheduler.get_priority(project_id)

        queue_items.append({
            "project_id": project_id,
            "project_name": _resolve_project_name(project_id),
            "group": group,
            "phase": phase,
            "current_stage": current_stage,
            "started_at": started_at,
            "elapsed_seconds": round(elapsed, 1) if elapsed else None,
            "wait_seconds": None,
            "priority": priority,
            "compute_node": node,
            "concurrent_workers": workers,
        })
        seen_projects.add(project_id)

    # 2. Queued entries from scheduler (not yet in orchestrator runs)
    for node_id, node_info in nodes.items():
        for queued in node_info.get("queued", []):
            pid = queued["project_id"]
            if pid in seen_projects:
                continue  # Already captured from orchestrator
            queue_items.append({
                "project_id": pid,
                "project_name": _resolve_project_name(pid),
                "group": queued.get("stage", "unknown"),
                "phase": "queued",
                "current_stage": None,
                "started_at": None,
                "elapsed_seconds": None,
                "wait_seconds": queued.get("waiting_seconds", 0),
                "priority": pipeline_scheduler.get_priority(pid),
                "compute_node": None,
                "concurrent_workers": 0,
            })
            seen_projects.add(pid)

    # Sort: running first, then paused, then queued, then failed
    phase_order = {"running": 0, "paused": 1, "queued": 2, "failed": 3}
    queue_items.sort(key=lambda x: (
        phase_order.get(x["phase"], 9),
        -(x.get("started_at") or 0),
    ))

    # Build compact node summary
    node_summary = {}
    for node_id, node_info in nodes.items():
        node_summary[node_id] = {
            "max_concurrent": node_info.get("max_concurrent", 1),
            "current_load": node_info.get("current_load", 0),
        }

    return ok({
        "queue": queue_items,
        "nodes": node_summary,
        "ghost_locks_purged": ghosts_purged,
    })


@router.post("/pipeline-queue/priority")
def set_queue_priority(req: PriorityRequest) -> Dict[str, Any]:
    """Set priority level for a project in the pipeline queue."""
    pipeline_scheduler.set_priority(req.project_id, req.level)
    _persist_priority(req.project_id, req.level)

    # Emit SSE event
    try:
        from prep.core.events import get_event_bus
        get_event_bus().emit("queue_changed", {
            "reason": "priority_changed",
            "project_id": req.project_id,
            "level": req.level,
        })
    except Exception:
        pass

    return ok({
        "project_id": req.project_id,
        "level": pipeline_scheduler.get_priority(req.project_id),
    })


@router.post("/pipeline-queue/purge-ghosts")
def manual_purge_ghosts() -> Dict[str, Any]:
    """Manually trigger ghost lock purge."""
    count = purge_ghost_locks()
    return ok({"purged": count})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_queue_router.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Register the router in server.py**

In `src/prep/server.py`, add after line 570 (the collaboration import):

```python
from prep.api.routers.queue import router as queue_router
```

And add after line 592 (the collaboration include):

```python
app.include_router(queue_router)
```

- [ ] **Step 6: Commit**

```bash
git add src/prep/api/routers/queue.py tests/test_queue_router.py src/prep/server.py
git commit -m "feat(queue): add global pipeline queue API router with ghost guard integration"
```

---

### Task 3: SSE Event Emission from Orchestrator

**Files:**
- Modify: `src/prep/services/pipeline/orchestrator.py:1555-1670`

- [ ] **Step 1: Add queue_changed emission after stage completion (line ~1632)**

After line 1632 (`self._resume_queued_pipeline(...)`) in the COMPLETED branch, add:

```python
            # Phase 75: notify queue UI of state change
            try:
                from prep.core.events import get_event_bus
                get_event_bus().emit("queue_changed", {
                    "reason": "pipeline_stage_completed",
                    "project_id": project_id,
                })
            except Exception:
                pass
```

Insert this block right after the `if _deferred_resume:` block ends (after line 1632), before the `elif new_phase == BuildPhase.FAILED:` on line 1634.

- [ ] **Step 2: Add queue_changed emission + ghost guard in the FAILED branch (line ~1670)**

After line 1670 (`self._resume_queued_pipeline(...)`) in the FAILED branch, add:

```python
            # Phase 75: ghost guard + queue notification on failure
            try:
                from prep.services.pipeline.ghost_guard import purge_ghost_locks
                purge_ghost_locks()
            except Exception:
                logger.debug("Ghost guard failed during FAILED transition", exc_info=True)
            try:
                from prep.core.events import get_event_bus
                get_event_bus().emit("queue_changed", {
                    "reason": "pipeline_stage_failed",
                    "project_id": project_id,
                })
            except Exception:
                pass
```

Insert after line 1670 and before line 1672 (`pfl = self._get_file_logger(...)`).

- [ ] **Step 3: Verify existing tests still pass**

Run: `.venv/bin/pytest tests/ -k "pipeline" --timeout=30 -x -q`
Expected: All existing pipeline tests pass (no regressions)

- [ ] **Step 4: Commit**

```bash
git add src/prep/services/pipeline/orchestrator.py
git commit -m "feat(queue): emit queue_changed SSE events on pipeline transitions"
```

---

### Task 4: Frontend — SidebarPipelineQueue Component

**Files:**
- Create: `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx`
- Modify: `packages/ui/src/components/navigation/index.ts`

- [ ] **Step 1: Create the SidebarPipelineQueue component**

```tsx
// packages/ui/src/components/navigation/SidebarPipelineQueue.tsx
import { useState, useEffect, useCallback, useRef } from 'react';
import { cn } from '../../lib/utils';
import {
  ChevronDown,
  ChevronRight,
  Pause,
  Play,
  X,
  Star,
  Loader2,
} from 'lucide-react';
import { Button } from '../primitives/Button';
import { StatusBadge } from '../status/StatusBadge';
import type { StatusState } from '../../types';

// ── Types ─────────────────────────────────────────────────────────

export interface QueueItem {
  project_id: string;
  project_name: string;
  group: string;
  phase: string;
  current_stage: string | null;
  started_at: number | null;
  elapsed_seconds: number | null;
  wait_seconds: number | null;
  priority: string;
  compute_node: string | null;
  concurrent_workers: number;
}

interface QueueResponse {
  queue: QueueItem[];
  nodes: Record<string, { max_concurrent: number; current_load: number }>;
  ghost_locks_purged: number;
}

export interface SidebarPipelineQueueProps {
  /** Base URL for API calls (e.g. "http://localhost:8400") */
  baseUrl: string;
  /** SSE event source URL for queue_changed events */
  eventsUrl?: string;
  /** Callback when user pauses a pipeline */
  onPause?: (projectId: string, group: string) => void;
  /** Callback when user resumes a pipeline */
  onResume?: (projectId: string, group: string) => void;
  /** Callback when user cancels a pipeline */
  onCancel?: (projectId: string, group: string) => void;
  /** Callback when user changes priority */
  onPriorityChange?: (projectId: string, level: string) => void;
  className?: string;
}

// ── Helpers ───────────────────────────────────────────────────────

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return '0s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) return `${mins}m ${secs}s`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

function phaseToStatus(phase: string): StatusState {
  switch (phase) {
    case 'running': return 'building';
    case 'queued': return 'pending';
    case 'paused': return 'stale';
    case 'failed': return 'error';
    default: return 'pending';
  }
}

function groupLabel(group: string): string {
  switch (group) {
    case 'fast_sync': return 'Fast Sync';
    case 'deep_enrichment': return 'Deep Enrich';
    default: return group;
  }
}

function phaseLabel(phase: string): string {
  return phase.charAt(0).toUpperCase() + phase.slice(1);
}

// ── Component ─────────────────────────────────────────────────────

export function SidebarPipelineQueue({
  baseUrl,
  eventsUrl,
  onPause,
  onResume,
  onCancel,
  onPriorityChange,
  className,
}: SidebarPipelineQueueProps) {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [collapsed, setCollapsed] = useState(() => {
    const saved = typeof window !== 'undefined'
      ? localStorage.getItem('prep_queue_collapsed')
      : null;
    return saved === 'true';
  });
  const [loading, setLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval>>();
  const mountedRef = useRef(true);

  // Fetch queue data
  const fetchQueue = useCallback(async () => {
    try {
      const res = await fetch(`${baseUrl}/system/pipeline-queue`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) return;
      const json = await res.json();
      if (mountedRef.current) {
        const data: QueueResponse = json.data ?? json;
        setQueue(data.queue ?? []);
      }
    } catch {
      // Silently fail — daemon may be down
    }
  }, [baseUrl]);

  // Poll every 5s
  useEffect(() => {
    mountedRef.current = true;
    fetchQueue();
    pollRef.current = setInterval(fetchQueue, 5000);
    return () => {
      mountedRef.current = false;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchQueue]);

  // SSE listener for immediate refresh
  useEffect(() => {
    if (!eventsUrl) return;

    const source = new EventSource(eventsUrl);
    const handler = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'queue_changed') {
          fetchQueue();
        }
      } catch {
        // ignore parse errors
      }
    };
    source.addEventListener('message', handler);
    return () => {
      source.removeEventListener('message', handler);
      source.close();
    };
  }, [eventsUrl, fetchQueue]);

  // Persist collapsed state
  const toggleCollapsed = useCallback(() => {
    setCollapsed(prev => {
      const next = !prev;
      localStorage.setItem('prep_queue_collapsed', String(next));
      return next;
    });
  }, []);

  // Action handlers
  const handlePause = useCallback(async (item: QueueItem) => {
    if (onPause) {
      onPause(item.project_id, item.group);
    } else {
      await fetch(`${baseUrl}/projects/${item.project_id}/pipeline/pause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group: item.group }),
      });
      fetchQueue();
    }
  }, [baseUrl, onPause, fetchQueue]);

  const handleResume = useCallback(async (item: QueueItem) => {
    if (onResume) {
      onResume(item.project_id, item.group);
    } else {
      await fetch(`${baseUrl}/projects/${item.project_id}/pipeline/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group: item.group }),
      });
      fetchQueue();
    }
  }, [baseUrl, onResume, fetchQueue]);

  const handleCancel = useCallback(async (item: QueueItem) => {
    if (onCancel) {
      onCancel(item.project_id, item.group);
    } else {
      await fetch(`${baseUrl}/projects/${item.project_id}/pipeline/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group: item.group }),
      });
      fetchQueue();
    }
  }, [baseUrl, onCancel, fetchQueue]);

  const handlePriority = useCallback(async (item: QueueItem) => {
    const nextLevel = item.priority === 'none' ? 'boost'
      : item.priority === 'boost' ? 'exclusive'
      : 'none';
    if (onPriorityChange) {
      onPriorityChange(item.project_id, nextLevel);
    } else {
      await fetch(`${baseUrl}/system/pipeline-queue/priority`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: item.project_id, level: nextLevel }),
      });
      fetchQueue();
    }
  }, [baseUrl, onPriorityChange, fetchQueue]);

  // Don't render at all if empty and collapsed
  if (queue.length === 0 && collapsed) return null;

  return (
    <div className={cn('px-2 py-2', className)}>
      {/* Header */}
      <button
        onClick={toggleCollapsed}
        className="flex items-center justify-between w-full px-2 py-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted hover:text-text transition-colors"
      >
        <span className="flex items-center gap-1.5">
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          Pipeline Queue
        </span>
        {queue.length > 0 && (
          <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold rounded-full bg-primary/15 text-primary">
            {queue.length}
          </span>
        )}
      </button>

      {/* Queue items */}
      {!collapsed && (
        <div className="mt-1 space-y-1">
          {queue.length === 0 ? (
            <p className="px-2 py-2 text-xs text-text-muted italic">
              No active pipelines
            </p>
          ) : (
            queue.map((item) => (
              <div
                key={`${item.project_id}-${item.group}`}
                className="px-2 py-1.5 rounded-md bg-surface-raised/50 border border-border/50"
              >
                {/* Row 1: Project name + priority */}
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-text truncate max-w-[140px]" title={item.project_name}>
                    {item.priority !== 'none' && (
                      <Star
                        className={cn(
                          'inline w-3 h-3 mr-1 -mt-0.5',
                          item.priority === 'exclusive' ? 'text-red-500 fill-red-500' : 'text-amber-500 fill-amber-500',
                        )}
                      />
                    )}
                    {item.project_name}
                  </span>
                  <StatusBadge status={phaseToStatus(item.phase)} label={phaseLabel(item.phase)} />
                </div>

                {/* Row 2: Group + stage + timing */}
                <div className="flex items-center justify-between mt-0.5">
                  <span className="text-[10px] text-text-muted">
                    {groupLabel(item.group)}
                    {item.current_stage && ` · ${item.current_stage}`}
                  </span>
                  <span className="text-[10px] text-text-muted tabular-nums">
                    {item.phase === 'running' && item.elapsed_seconds != null
                      ? formatDuration(item.elapsed_seconds)
                      : item.phase === 'queued' && item.wait_seconds != null
                        ? `waiting ${formatDuration(item.wait_seconds)}`
                        : ''}
                  </span>
                </div>

                {/* Row 3: Controls */}
                <div className="flex items-center gap-0.5 mt-1">
                  {/* Pause/Resume */}
                  {item.phase === 'running' && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => handlePause(item)}
                      className="h-5 w-5 text-text-muted hover:text-text"
                      title="Pause"
                    >
                      <Pause className="w-3 h-3" />
                    </Button>
                  )}
                  {item.phase === 'paused' && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => handleResume(item)}
                      className="h-5 w-5 text-text-muted hover:text-green-500"
                      title="Resume"
                    >
                      <Play className="w-3 h-3" />
                    </Button>
                  )}

                  {/* Priority star */}
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handlePriority(item)}
                    className={cn(
                      'h-5 w-5',
                      item.priority !== 'none' ? 'text-amber-500' : 'text-text-muted hover:text-amber-500',
                    )}
                    title={`Priority: ${item.priority} (click to cycle)`}
                  >
                    <Star className={cn('w-3 h-3', item.priority !== 'none' && 'fill-current')} />
                  </Button>

                  {/* Cancel */}
                  {item.phase !== 'failed' && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => handleCancel(item)}
                      className="h-5 w-5 text-text-muted hover:text-red-500 ml-auto"
                      title="Cancel"
                    >
                      <X className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Export from navigation index**

Add to `packages/ui/src/components/navigation/index.ts`:

```typescript
export { SidebarPipelineQueue, type SidebarPipelineQueueProps, type QueueItem } from './SidebarPipelineQueue';
```

- [ ] **Step 3: Export from main package index**

In `packages/ui/src/index.ts`, find line 92:

```typescript
export { Sidebar, ProjectList, ProjectTabs, AppShell, SidebarAIGateway } from './components/navigation';
```

Replace with:

```typescript
export { Sidebar, ProjectList, ProjectTabs, AppShell, SidebarAIGateway, SidebarPipelineQueue } from './components/navigation';
```

And find line 93:

```typescript
export type { SidebarProps, ProjectListProps, ProjectTabsProps, ProjectTab, AppShellProps, SidebarAIGatewayProps } from './components/navigation';
```

Replace with:

```typescript
export type { SidebarProps, ProjectListProps, ProjectTabsProps, ProjectTab, AppShellProps, SidebarAIGatewayProps, SidebarPipelineQueueProps, QueueItem } from './components/navigation';
```

- [ ] **Step 4: Verify build**

Run: `cd packages/ui && npm run typecheck`
Expected: No type errors

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/components/navigation/SidebarPipelineQueue.tsx packages/ui/src/components/navigation/index.ts packages/ui/src/index.ts
git commit -m "feat(queue): add SidebarPipelineQueue component"
```

---

### Task 5: Wire Queue Widget into Dashboard

**Files:**
- Modify: `src/prep/dashboard/src/App.tsx:893-939`

- [ ] **Step 1: Add import**

At the top of `src/prep/dashboard/src/App.tsx`, in the import block from `@prep/ui` (line 4), add `SidebarPipelineQueue` to the navigation imports:

Find:
```typescript
  // Navigation
  AppShell,
  Sidebar,
  ProjectList,
  SidebarAIGateway,
  TeamSyncIndicator,
```

Replace with:
```typescript
  // Navigation
  AppShell,
  Sidebar,
  ProjectList,
  SidebarAIGateway,
  SidebarPipelineQueue,
  TeamSyncIndicator,
```

- [ ] **Step 2: Add the queue widget into the Sidebar**

Find the `<Sidebar>` JSX block starting at line ~893. Currently it renders `<ProjectList>` as children. Add the `SidebarPipelineQueue` between `ProjectList` and the closing `</Sidebar>`:

Find:
```tsx
              />
            )}
          </Sidebar>
```

(This is lines 937-939 — the end of `ProjectList` closing tag, the `!sidebarCollapsed` conditional closing, and `</Sidebar>`)

Replace with:
```tsx
              />
            )}
            {!sidebarCollapsed && (
              <SidebarPipelineQueue
                baseUrl={import.meta.env.DEV ? `http://${window.location.hostname}:8400` : api.baseUrl}
                eventsUrl={eventsUrl}
              />
            )}
          </Sidebar>
```

- [ ] **Step 3: Verify build**

Run: `cd src/prep/dashboard && npm run typecheck`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add src/prep/dashboard/src/App.tsx
git commit -m "feat(queue): wire SidebarPipelineQueue into dashboard sidebar"
```

---

### Task 6: SSE Event Handling in useEventStream

**Files:**
- Modify: `packages/ui/src/hooks/useEventStream.ts:63-74`
- Modify: `packages/ui/src/hooks/useEventStream.ts:4-13` (return type)

- [ ] **Step 1: Add queue_changed state and handler**

In `packages/ui/src/hooks/useEventStream.ts`, add `queueChanged` counter to the return interface. Find:

```typescript
export interface UseEventStreamResult {
  logs: LogEntry[];
  tasks: Record<string, TaskProgress>;
  connected: boolean;
  clearLogs: () => void;
  /** Pipeline status updates keyed by project_id (Phase 24 SM-6) */
  pipelineEvents: Record<string, PipelineStatus & { project_id: string }>;
  /** Scope status updates keyed by project_id (Phase 24 SM-8) */
  scopeEvents: Record<string, ScopeStatus>;
}
```

Replace with:

```typescript
export interface UseEventStreamResult {
  logs: LogEntry[];
  tasks: Record<string, TaskProgress>;
  connected: boolean;
  clearLogs: () => void;
  /** Pipeline status updates keyed by project_id (Phase 24 SM-6) */
  pipelineEvents: Record<string, PipelineStatus & { project_id: string }>;
  /** Scope status updates keyed by project_id (Phase 24 SM-8) */
  scopeEvents: Record<string, ScopeStatus>;
  /** Monotonic counter that increments on every queue_changed SSE event (Phase 75) */
  queueVersion: number;
}
```

- [ ] **Step 2: Add state and handler inside the hook**

After the `scopeEvents` state declaration (line ~19), add:

```typescript
const [queueVersion, setQueueVersion] = useState(0);
```

In the `handleEvent` callback, after the `scope_status` handler block (after line ~73), add:

```typescript
      } else if (type === 'queue_changed') {
        setQueueVersion(v => v + 1);
      }
```

- [ ] **Step 3: Add to return value**

Find the return statement of `useEventStream` and add `queueVersion` to the returned object.

- [ ] **Step 4: Verify build**

Run: `cd packages/ui && npm run typecheck`
Expected: No type errors

- [ ] **Step 5: Commit**

```bash
git add packages/ui/src/hooks/useEventStream.ts
git commit -m "feat(queue): handle queue_changed SSE events in useEventStream"
```

---

### Task 7: Integration Verification

**Files:**
- No new files — end-to-end verification

- [ ] **Step 1: Run all Python tests**

Run: `.venv/bin/pytest tests/test_ghost_guard.py tests/test_queue_router.py -v`
Expected: All tests pass

- [ ] **Step 2: Run TypeScript typecheck**

Run: `cd packages/ui && npm run typecheck && cd ../../src/prep/dashboard && npm run typecheck`
Expected: No type errors in either package

- [ ] **Step 3: Run Python linter**

Run: `.venv/bin/ruff check src/prep/services/pipeline/ghost_guard.py src/prep/api/routers/queue.py`
Expected: No lint errors

- [ ] **Step 4: Verify server starts with new router**

Run: `.venv/bin/python -c "from prep.api.routers.queue import router; print('Router loaded:', len(router.routes), 'routes')"`
Expected: `Router loaded: 3 routes`

- [ ] **Step 5: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix(queue): integration fixups from verification"
```
