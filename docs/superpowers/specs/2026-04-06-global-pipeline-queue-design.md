# Global Pipeline Queue — Design Spec

**Date:** 2026-04-06
**Phase:** 75
**Status:** Approved

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
| `src/codrag/services/pipeline/orchestrator.py` | Emit `queue_changed` event in `_on_build_transition` (line ~1555 COMPLETED branch, ~1634 FAILED branch). Also call `purge_ghost_locks()` in the FAILED branch. Total: ~5 lines added. |
| `src/codrag/server.py` | Register new queue router |
| `packages/ui/src/components/navigation/Sidebar.tsx` | Accept new `queueWidget` prop slot |
| `src/codrag/dashboard/src/App.tsx` | Wire queue widget into sidebar |

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

### queue.py Router

**`GET /system/pipeline-queue`**

Merges three data sources into a unified queue response:

1. **Scheduler state** (`pipeline_scheduler.status()`): slots, queues, priorities
2. **Orchestrator runs** (`pipeline_orchestrator._runs`): state machines with group/stage/timing
3. **Project registry**: project names for display

Response schema:
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
  "nodes": {
    "local:default_ollama": {
      "max_concurrent": 1,
      "current_load": 1
    }
  },
  "ghost_locks_purged": 0
}
```

Items are ordered: RUNNING first (sorted by started_at), then PAUSED, then QUEUED (by wait time), then FAILED.

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

**Location in sidebar:** Between the ProjectList (main children) and the AI Gateway footer. Uses a new `queueWidget` prop on `Sidebar` to insert in the correct position.

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

**Component behavior:**
- Polls `GET /system/pipeline-queue` every 5s as baseline
- Listens to SSE `queue_changed` events for immediate refresh
- Collapsible header (persisted to localStorage)
- Empty state hidden or shows minimal "No active pipelines" text
- Status badges reuse existing `StatusBadge` component with color mapping:
  - Running → blue
  - Queued → amber
  - Paused → gray
  - Failed → red

**Controls mapped to existing endpoints:**
- Pause → `POST /projects/{id}/pipeline/pause` with `{ group }`
- Resume → `POST /projects/{id}/pipeline/resume` with `{ group }`
- Cancel → `POST /projects/{id}/pipeline/cancel` with `{ group }`
- Star toggle → `POST /system/pipeline-queue/priority` with `{ project_id, level }`

### Sidebar.tsx Changes

Add an optional `queueWidget` prop:
```tsx
export interface SidebarProps {
  // ... existing props
  queueWidget?: ReactNode;
}
```

Rendered between `children` and `footer`:
```tsx
<div className="flex-1 overflow-y-auto py-2">
  {children}
</div>
{queueWidget && (
  <div className="flex-shrink-0 border-t border-border">
    {queueWidget}
  </div>
)}
{footer && (
  <div className="flex-shrink-0 border-t border-border">
    {footer}
  </div>
)}
```

### App.tsx Wiring

The dashboard app creates a `<SidebarPipelineQueue />` instance and passes it as the `queueWidget` prop to `<Sidebar>`. The component manages its own data fetching internally (no prop drilling of queue state).

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
- On every `GET /system/pipeline-queue` (dashboard polls every 5s when open)
- On every `_on_build_transition` FAILED event
- On `run_fast_sync` / `run_deep_enrichment` invocation (before slot acquisition)
- Manual via `POST /system/pipeline-queue/purge-ghosts`

This guarantees ghost locks are detected within seconds of occurring, not minutes or hours.

---

## Testing Strategy

- **ghost_guard.py:** Unit test with mocked scheduler/build_orchestrator. Verify purge fires when lock exists but no threads alive. Verify no-op when threads are alive.
- **queue.py router:** Integration test hitting the endpoint with a running pipeline. Verify response schema. Verify ghost purge is called.
- **SidebarPipelineQueue.tsx:** Component test with mocked API responses for each state (running, queued, paused, empty).

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
