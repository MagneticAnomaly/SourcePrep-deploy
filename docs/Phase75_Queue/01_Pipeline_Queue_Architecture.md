# Phase 75: Global Pipeline Queue & Ghost Lock Remediation

## 1. Executive Summary

CoDRAG's multi-project pipeline scheduling already has robust slot-based scheduling, FIFO queues, priority (boost/exclusive), zombie thread detection, and heartbeat staleness checks. What's missing is a **unified cross-project view** of this state and an **active ghost lock purge** that validates scheduler locks against actual thread liveness.

Phase 75 introduces the **Global Pipeline Queue**: a system-level API endpoint and sidebar UI widget that aggregates scheduler, orchestrator, and build thread state into a single "Air Traffic Control" view. Coupled with this is the **Ghost Guard** — an active cross-check that purges phantom scheduler locks on every queue read, guaranteeing the queue never deadlocks from crashed worker processes.

## 2. What Already Exists (Leveraged, Not Rebuilt)

| Capability | Location | Status |
|---|---|---|
| Slot-based scheduling with FIFO queues | `PipelineScheduler` in `services/pipeline/scheduler.py` | Done |
| Priority system (none/boost/exclusive) | `scheduler.set_priority()`, weighted fair-share | Done |
| Ghost lock cleanup primitive | `scheduler.clean_locks()` | Done |
| Zombie thread detection | `BuildOrchestrator._check_zombie()` | Done (passive) |
| Heartbeat + staleness detection | `pipeline_metadata.py` (5min stale, 1hr zombie) | Done |
| Pause/Resume/Cancel per project | `api/routers/pipeline.py` endpoints | Done |
| Scheduler status snapshot | `pipeline_scheduler.status()` → nodes/queues/priority | Done |
| Auto-resume on slot free | `orchestrator._resume_queued_pipeline()` | Done |
| SSE event bus | `core/events.get_event_bus()` + `/events` endpoint | Done |

## 3. New Work

### 3.1 Ghost Guard (`services/pipeline/ghost_guard.py`)

Active cross-check that validates scheduler lock integrity:

```
FOR each (project_id, stage) in scheduler.active_stages across ALL nodes:
    IF NOT build_orchestrator.is_any_active(project_id):
        scheduler.clean_locks(project_id)  # ghost lock detected
        emit queue_changed event
```

This is mathematically sound: if the scheduler claims a project holds a compute slot, but the build orchestrator confirms zero living threads for that project, the lock cannot be legitimate.

**Trigger points:**
- Every `GET /system/pipeline-queue` call (cheap, idempotent)
- `_on_build_transition` FAILED events in orchestrator
- `run_fast_sync` / `run_deep_enrichment` invocation
- Manual via `POST /system/pipeline-queue/purge-ghosts`

### 3.2 Queue API (`api/routers/queue.py`)

**`GET /system/pipeline-queue`** — Aggregated queue state:

```json
{
  "queue": [
    {
      "project_id": "uuid-1234",
      "project_name": "DebateHaus",
      "group": "fast_sync",
      "phase": "RUNNING",
      "current_stage": "catalogue",
      "started_at": 1712431440,
      "elapsed_seconds": 142.5,
      "priority": "boost",
      "compute_node": "local:default_ollama",
      "concurrent_workers": 3
    },
    {
      "project_id": "uuid-5678",
      "project_name": "Antigravity",
      "group": "deep_enrichment",
      "phase": "QUEUED",
      "current_stage": null,
      "started_at": null,
      "wait_seconds": 45.2,
      "priority": "none",
      "compute_node": null,
      "concurrent_workers": 0
    }
  ],
  "nodes": { ... },
  "ghost_locks_purged": 0
}
```

**`POST /system/pipeline-queue/priority`** — Set project priority (wraps `scheduler.set_priority()`).

**`POST /system/pipeline-queue/purge-ghosts`** — Manual ghost lock purge.

### 3.3 SSE Event: `queue_changed`

Emitted on the existing event bus when pipelines start/stop/fail/pause or ghost locks are purged. The UI subscribes to trigger immediate re-fetches instead of waiting for the next poll cycle.

### 3.4 Sidebar Queue Widget (`SidebarPipelineQueue.tsx`)

Compact widget mounted between ProjectList and AI Gateway in the sidebar:

```
┌─────────────────────────┐
│ Pipeline Queue      (2) │  header + count badge
├─────────────────────────┤
│ ⭐ DebateHaus           │  priority star
│ Fast Sync · Running     │  group + status badge
│ catalogue · 2m 22s      │  stage + elapsed
│ [⏸] [✕]                │  pause, cancel
├─────────────────────────┤
│ Antigravity             │
│ Deep Enrich · Queued    │
│ waiting · 45s           │
│ [⭐] [✕]               │  boost, cancel
└─────────────────────────┘
```

Controls map directly to existing pipeline endpoints (pause/resume/cancel) and the new priority endpoint. Polls every 5s with SSE-triggered immediate refresh.

## 4. Files Changed

| File | Change |
|------|--------|
| `services/pipeline/ghost_guard.py` | **NEW** — Ghost lock cross-check module |
| `api/routers/queue.py` | **NEW** — System-level queue API router |
| `packages/ui/.../SidebarPipelineQueue.tsx` | **NEW** — Sidebar queue widget |
| `services/pipeline/orchestrator.py` | Emit `queue_changed` event + call `purge_ghost_locks()` on FAILED (~5 lines) |
| `server.py` | Register queue router |
| `packages/ui/.../Sidebar.tsx` | Add `queueWidget` prop slot |
| `dashboard/src/App.tsx` | Wire queue widget into sidebar |

## 5. Design Spec

Full design spec: `docs/superpowers/specs/2026-04-06-global-pipeline-queue-design.md`
