# Global Pipeline Queue — Design Spec

**Date:** 2026-04-06
**Phase:** 75
**Status:** Implemented

## Problem

CoDRAG users managing multiple projects have no cross-project visibility into pipeline scheduling. Ghost locks from crashed workers silently block the queue with no way to detect or clear them. The scheduler, orchestrator, and build orchestrator each hold partial state, but nothing aggregates it into a unified view. Users experience stalled pipelines with no feedback about what's running, what's waiting, or why.

## Solution

A **Global Pipeline Queue** that:
1. Aggregates scheduler slots, orchestrator run state, and build thread health into a single cross-project view
2. Exposes this via a new `GET /system/pipeline-queue` API endpoint
3. Renders in the dashboard sidebar as a compact queue widget between ProjectList and AI Gateway
4. Automatically purges ghost locks on every queue read via a cross-check between scheduler lock state and build orchestrator thread liveness
5. Emits SSE events (`queue_changed`) so the UI can refresh reactively instead of blind-polling

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `src/codrag/services/pipeline/ghost_guard.py` | Ghost lock cross-check: validates scheduler locks against build orchestrator threads |
| `src/codrag/api/routers/queue.py` | System-level queue API router (`/system/pipeline-queue`) |
| `packages/ui/src/components/navigation/SidebarPipelineQueue.tsx` | Sidebar queue widget UI component |

### Modified Files

| File | Change |
|------|--------|
| `src/codrag/services/pipeline/orchestrator.py` | Emit `queue_changed` event in `_on_build_transition` COMPLETED and FAILED branches. Call `purge_ghost_locks()` in FAILED branch. ~25 lines added. |
| `src/codrag/server.py` | Register new queue router (+2 lines) |
| `src/codrag/dashboard/src/App.tsx` | Import `SidebarPipelineQueue`, render inside Sidebar, pass `queueVersion` from `useEventStream` |
| `packages/ui/src/hooks/useEventStream.ts` | Handle `queue_changed` SSE event, expose `queueVersion` counter |
| `packages/ui/src/components/navigation/index.ts` | Export `SidebarPipelineQueue` |
| `packages/ui/src/index.ts` | Export `SidebarPipelineQueue` from package |

### Unchanged Files

| File | Why |
|------|-----|
| `src/codrag/services/pipeline/scheduler.py` | `status()`, `clean_locks()`, `set_priority()` already sufficient |
| `src/codrag/services/build_orchestrator.py` | `is_any_active()`, `_check_zombie()` already sufficient |
| `src/codrag/api/routers/pipeline.py` | Existing pause/resume/cancel endpoints reused directly |

---

## Backend Design

### ghost_guard.py

```python
"""
Ghost Guard — Phase 75
Validates scheduler lock integrity against build orchestrator thread liveness.
"""

def purge_ghost_locks() -> int:
    """Cross-check scheduler locks against build orchestrator threads.
    
    For each project holding a scheduler slot, verify at least one
    build thread is alive via BuildOrchestrator.is_any_active().
    If the scheduler claims a lock but no threads exist, the lock
    is a ghost — purge it and emit a queue_changed event.
    
    Returns the number of ghost locks purged.
    """
```

Logic:
1. Read `pipeline_scheduler.status()` to get all nodes and their `active` dict (project_id -> stage)
2. For each active project_id across all nodes, call `build_orchestrator.is_any_active(project_id)`
3. If scheduler says locked but build orchestrator says no threads alive:
   - Call `pipeline_scheduler.clean_locks(project_id)`
   - Log warning with project_id and node
4. If any locks were purged, emit `queue_changed` on the event bus
5. Return purge count

Trigger points:
- Every `GET /system/pipeline-queue` call (cheap, idempotent, O(n) where n = active projects)
- Called from orchestrator's `_on_build_transition` on FAILED transitions (catch crashes immediately)
- Manual via `POST /system/pipeline-queue/purge-ghosts`

### queue.py Router

**`GET /system/pipeline-queue`**

Merges three data sources into a unified queue response:

1. **Scheduler state** (`pipeline_scheduler.status()`): slots, queues, priorities
2. **Orchestrator runs** (`pipeline_orchestrator._runs`): state machines with group/stage/timing
3. **Project registry**: project names for display

Response schema (phases are lowercase, matching state machine `.value`):
```json
{
  "queue": [
    {
      "project_id": "uuid-1234",
      "project_name": "DebateHaus",
      "group": "fast_sync",
      "phase": "running",
      "current_stage": "catalogue",
      "started_at": 1712431440,
      "elapsed_seconds": 142.5,
      "wait_seconds": null,
      "priority": "boost",
      "compute_node": "local:default_ollama",
      "concurrent_workers": 3
    },
    {
      "project_id": "uuid-5678",
      "project_name": "Antigravity",
      "group": "deep_enrichment",
      "phase": "queued",
      "current_stage": null,
      "started_at": null,
      "elapsed_seconds": null,
      "wait_seconds": 45.2,
      "priority": "none",
      "compute_node": null,
      "concurrent_workers": 0
    }
  ],
  "nodes": {
    "local:default_ollama": {
      "max_concurrent": 1,
      "current_load": 1
    }
  },
  "ghost_locks_purged": 0
}
```

Items are ordered: running first, then paused, then queued, then failed. Completed/idle runs are excluded.

**`POST /system/pipeline-queue/priority`**

Set priority for a project in the queue.

Request:
```json
{
  "project_id": "uuid-1234",
  "level": "boost"  // "none" | "boost" | "exclusive"
}
```

Delegates to `pipeline_scheduler.set_priority()` and persists to project config.

**`POST /system/pipeline-queue/purge-ghosts`**

Manual ghost lock purge. Returns `{ "purged": N }`.

### SSE Event: `queue_changed`

Emitted on the existing event bus (`codrag.core.events.get_event_bus()`) when:
- A pipeline starts, completes, fails, pauses, or resumes (from `_on_build_transition` in orchestrator)
- Ghost locks are purged (from ghost_guard)
- Priority changes (from queue router)

Payload:
```json
{
  "type": "queue_changed",
  "data": {
    "reason": "pipeline_started",  // or "ghost_purged", "priority_changed", "pipeline_completed", etc.
    "project_id": "uuid-1234"
  }
}
```

The UI uses this to trigger an immediate re-fetch of `/system/pipeline-queue` rather than waiting for the next poll cycle.

---

## Frontend Design

### SidebarPipelineQueue.tsx

**Location in sidebar:** Rendered as a direct child inside the `<Sidebar>` in `App.tsx`, below the `<ProjectList>` and gated on `!sidebarCollapsed`.

**Visual layout:**

```
┌─────────────────────────┐
│ Pipeline Queue      (2) │  ← header with count badge, collapsible
├─────────────────────────┤
│ ⭐ DebateHaus           │  ← priority star
│ Fast Sync · Running     │  ← group tag + status badge
│ catalogue · 2m 22s      │  ← current stage + elapsed
│ [⏸] [✕]                │  ← pause, cancel controls
├─────────────────────────┤
│ Antigravity             │
│ Deep Enrich · Queued    │
│ waiting · 45s           │
│ [⭐] [✕]               │  ← star (boost), cancel
├─────────────────────────┤
│ (empty: "No pipelines") │  ← when queue is empty
└─────────────────────────┘
```

**Component props:**
- `baseUrl` — API base URL for fetch calls
- `queueVersion` — Monotonic counter from `useEventStream`'s `queueVersion`; triggers immediate re-fetch on SSE `queue_changed` events without creating a duplicate `EventSource`

**Component behavior:**
- Polls `GET /system/pipeline-queue` every 5s as baseline
- Re-fetches immediately when `queueVersion` prop changes (driven by the shared `useEventStream` SSE connection)
- Collapsible header (persisted to localStorage)
- When empty and collapsed, renders nothing; when empty and expanded, shows "No active pipelines"
- Status badges reuse existing `StatusBadge` component (maps phase → StatusState: running→building, queued→pending, paused→stale, failed→error)

**Controls mapped to existing endpoints:**
- Pause → `POST /projects/{id}/pipeline/pause` with `{ group }`
- Resume → `POST /projects/{id}/pipeline/resume` with `{ group }`
- Cancel → `POST /projects/{id}/pipeline/cancel` with `{ group }`
- Star toggle → `POST /system/pipeline-queue/priority` with `{ project_id, level }` (cycles none→boost→exclusive→none)

### Sidebar.tsx — Unchanged

No modifications to `Sidebar.tsx` were needed. The queue widget is rendered as a direct child inside the Sidebar JSX in `App.tsx`, not via a prop.

### App.tsx Wiring

The dashboard app renders `<SidebarPipelineQueue>` inside `<Sidebar>` after `<ProjectList>`, gated on `!sidebarCollapsed`. It passes `baseUrl` and `queueVersion` (from the shared `useEventStream` hook). The component manages its own data fetching internally.

### useEventStream.ts

Added `queue_changed` event handling: when the SSE stream receives a `queue_changed` event, a `queueVersion` counter increments. This is exposed in the hook's return value and consumed by `SidebarPipelineQueue` via prop.

---

## Ghost Lock Remediation

The ghost guard solves the root cause described in Phase 75:

**Current bug:** If a worker thread crashes fatally, `_check_zombie()` in BuildOrchestrator transitions the slot to FAILED, but only when someone calls `status()` or `is_active()` — it's passive. If no one checks, the scheduler lock remains held indefinitely.

**Fix:** `purge_ghost_locks()` actively cross-checks on every queue read and every build transition. The check is:

```
IF scheduler.slot.active_stages[project_id] exists
AND NOT build_orchestrator.is_any_active(project_id)
THEN scheduler.clean_locks(project_id)  # ghost lock
```

This is mathematically sound: if the scheduler claims a project holds a compute slot, but the build orchestrator confirms zero living threads for that project, the lock cannot be legitimate.

**Trigger frequency:**
- On every `GET /system/pipeline-queue` call (dashboard polls every 5s when open)
- On every `_on_build_transition` FAILED event in the orchestrator
- Manual via `POST /system/pipeline-queue/purge-ghosts`

This guarantees ghost locks are detected within seconds of occurring, not minutes or hours.

---

## Testing (Implemented)

- **`tests/test_ghost_guard.py`** (4 tests): Orphaned lock cleanup, no-op when threads alive, multi-node purge, empty scheduler.
- **`tests/test_queue_router.py`** (6 tests): Running pipeline items, queued entries from scheduler, empty state, priority delegation, sort ordering, completed/idle exclusion.
- **SidebarPipelineQueue.tsx:** No component tests yet (v1 — visual testing via dashboard).

---

## Scope Boundaries (v1)

**In scope:**
- Queue visibility (what's running, queued, paused)
- Ghost lock auto-purge
- Priority control from queue UI
- Pause/resume/cancel from queue UI

**Out of scope (future):**
- Drag-to-reorder queue position
- Queue history / completed runs log
- Estimated time remaining per stage
- Queue notifications / toasts
