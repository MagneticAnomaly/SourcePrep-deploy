# Phase 96D: Dashboard UI State Sync — Diagnostic

**Date:** 2026-04-11
**Scope:** Dashboard display of pipeline state, project activity, and queue contents
**Status:** Backend (96A + 96B) validated working. UI shows stale/misleading state that masks the backend fix.

---

## Context

After Phase 96A + 96B landed (commit `997c579d`), the backend pipeline is provably working:
- 192/192 pipeline tests pass
- Live rebuild on SMOKE: rust_repo completed all 6 deep enrichment stages in 781s with no stalls
- Live run on Prep ran structural + inferred_edges + catalogue cleanly (1609 nodes augmented in 13 minutes) before user cancelled mid-way

But the dashboard gives the user the impression that nothing is fixed. This document catalogs the specific UI bugs that make a working pipeline look broken.

---

## Symptoms Reported by User

1. "Only one active project, then I refreshed and suddenly had 2"
2. "Toggled off Prep and it's still running in the logs"
3. "Queue shows nothing at all"
4. "The pipeline itself is just off"
5. "Active state doesn't save"

---

## Root-Cause Investigation

### Symptom 1 & 5 — "Active state doesn't save / ghost activates on refresh"

**Backend says:** Toggle persistence works. Verified via API:
```
GET /projects → 10 projects
  SMOKE: rust_repo   activity=active    active_cfg=True
  Prep             activity=inactive  active_cfg=False  ← persisted correctly
  (8 others)         activity=inactive  active_cfg=False
```

**What the user saw:** After toggling off Prep, refresh showed Prep as active again.

**Root cause hypothesis:** The dashboard computes "active" from TWO sources:
- `config.active` flag (persisted)
- Inferred from "has a running pipeline"

When the user toggles off Prep mid-pipeline:
1. Backend persists `active=False` to project config
2. Backend sends cancel signal to the running pipeline
3. Cancel processes through the state machine — takes up to several seconds for stage teardown
4. During that window, the pipeline's state is `cancelling` or still `running`
5. UI refresh fetches project list AND pipeline status
6. UI display logic: `shown_as_active = config.active || pipeline_is_running`
7. Result: project appears "active" until the cancel fully propagates

**Where the bug lives:** Frontend display logic conflates configured-active with has-pipeline. Should display only from `config.active` (persisted intent), not from transient pipeline state.

**Likely files to fix:**
- `packages/ui/src/components/navigation/ProjectList.tsx` — project active indicator
- `src/prep/dashboard/src/hooks/useProjectManager.ts` — project active state hook

---

### Symptom 3 — "Queue shows nothing at all"

**Backend says:** Queue API returns `Prep — fast_sync/knowledge [cancelled]`.

**What the user saw:** Queue panel appeared empty.

**Screenshot analysis:** Actually the queue panel shows `Prep — Pending — Fast Sync → knowledge` — labeled "Pending" not "Cancelled". So the API is returning the item and the UI IS rendering it, but:
- **Wrong label:** `cancelled` is mapped to "Pending" visually (label bug)
- **No terminal filter:** Cancelled entries should be ephemeral — either shown as completed for ~10s then removed, or filtered entirely

**Root cause:** The frontend queue panel:
1. Doesn't have a mapping for phase=`cancelled` (falls through to default "Pending"?)
2. Doesn't filter terminal states (cancelled, failed, completed) from the active queue
3. Backend queue endpoint returns cancelled entries because they match the `_PHASE_ORDER` filter set in `queue.py:32`

**Where the bug lives:**
- Backend: `src/prep/api/routers/queue.py:44` — `_EXCLUDED_STATES = {"completed", "idle"}` should include `cancelled` and `failed`
- Frontend: queue panel component needs phase→label mapping for all states

---

### Symptom 2 — "Toggled off Prep and it's still running in the logs"

**Backend says:** Prep was cancelled at stage 4/knowledge, error="Cancelled by user". Last log write was at 11:41 AM, current time 8:00 AM (19 minutes idle).

**What the user saw:** Logs appearing to show Prep activity.

**Root cause:** The dashboard's "activity indicator" or "ongoing operations" panel doesn't tell the difference between:
1. Real-time log events streaming via SSE (live activity)
2. Last-known pipeline state displayed statically (historical)

Both render with similar UI (pipeline panel, progress bars). The user can't tell them apart.

**Where the bug lives:** Frontend pipeline status panel should show a "last updated" timestamp relative to now, with strong visual distinction between "running" and "last known state". Currently the UI shows the same display for both.

---

### Symptom 4 — "The pipeline itself is just off"

**What the user saw:** The Graph Enrichment panel showing chi-go's state with "Ready to catalogue" / "Waiting for catalogue" — looking like a stalled pipeline.

**Screenshot analysis:** This is chi-go's LAST known pipeline state. chi-go is inactive. The pipeline panel has no awareness that it's showing a frozen historical view.

**Root cause:** The Graph Enrichment pipeline panel is **decoupled from the selected project's activity state**:
- Sidebar selection → determines which project's data to show
- Selected project may be inactive → its data is stale
- Panel renders stale data without indicator

**Where the bug lives:**
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` — should show "snapshot" badge when displaying inactive project data
- A top-level indicator should clarify: "Viewing chi-go (inactive) — not currently running"

---

## Additional Issues Observed

### I1 — Connection storm from Vite dev proxy

When the dashboard is open in a browser tab, the Vite dev proxy opens 50+ concurrent TCP connections to the daemon within seconds. FastAPI's default 40-thread anyio pool saturates, and endpoints touching the scheduler lock start hanging for 3+ seconds. `/health` (which doesn't touch scheduler) remains responsive.

**Impact:** `/system/pipeline-queue`, `/compute/scheduler`, `/projects/{id}/pipeline/status` all timeout under dashboard load, even though the backend pipeline is running fine.

**Fix options:**
1. Reduce dashboard poll intervals (currently sub-second per endpoint)
2. Consolidate polling into the existing `/events` SSE stream
3. Raise anyio thread pool cap from 40 to 200 in `server.py` lifespan
4. Investigate why Vite proxy doesn't reuse connections (proxy config or keep-alive issue)

### I2 — `SettingsStore.get_global` missing attribute

Recurring log error:
```
ERROR:prep.api.routers.settings:Security health check failed:
  'SettingsStore' object has no attribute 'get_global'
```

A router was added calling a method that doesn't exist. Non-fatal but noisy. Tracked as separate bug.

### I3 — Queue endpoint label inconsistency

Backend queue API sorts by `_PHASE_ORDER` with `cancelled` at priority 3. The frontend can't distinguish `cancelled` from `queued` based on the label it renders ("Pending"). Label table needs expansion.

---

## Proposed Fix Strategy

This is **Phase 96D** — UI state synchronization. It's distinct from 96A/B/C (backend) but blocks user validation of those fixes.

### 96D.1 — Queue endpoint terminal-state filtering (backend, 1 line)

```python
# src/prep/api/routers/queue.py:44
_EXCLUDED_STATES = {"completed", "idle", "cancelled", "failed"}
```

This removes ghost entries from the queue API immediately. The frontend can still be wrong about labels, but at least the list is accurate.

### 96D.2 — Connection storm mitigation (backend, ~10 lines)

Raise anyio thread pool in `server.py` lifespan:
```python
from anyio import to_thread
limiter = to_thread.current_default_thread_limiter()
limiter.total_tokens = 200
```

Stopgap only — real fix is reducing UI polling.

### 96D.3 — Dashboard active-state logic (frontend)

Display project "active" indicator purely from `config.active`, never from "has pipeline running". Running pipelines on inactive projects are a real state (finish-the-current-stage-then-stop pattern) but should be shown as "stopping" or "draining", not "active".

### 96D.4 — Pipeline panel stale-state indicator (frontend)

When the viewed project has no currently-running pipeline, show a "last updated X ago" badge. When it has an active pipeline, show progress + timestamp. Visual distinction must be strong enough that the user knows instantly whether they're looking at live or historical data.

### 96D.5 — Live UI watching with Playwright (tooling)

To validate 96D fixes and any future UI work, we need a driver that can:
1. Open the dashboard in a headless browser
2. Click actions (select project, trigger rebuild, toggle active)
3. Wait for backend state transitions
4. Query DOM for current display state
5. Screenshot at key moments
6. Compare UI state to API state to catch desyncs

Phase 96D will include a Python script (`tools/playwright_smoke.py` or similar) that exercises the dashboard against `SMOKE: rust_repo` and reports any UI↔backend desyncs.

---

## Verification Plan for 96D

1. **Fix 96D.1** (1-line backend queue filter) — verify ghost entries disappear
2. **Write Playwright smoke driver** — navigate, click, screenshot, diff against API
3. **Run driver against rust_repo rebuild cycle** — capture the UI at each stage transition
4. **Report discrepancies** — anywhere the UI shows different state than the API
5. **Fix frontend bugs** (96D.3, 96D.4) targeted by driver findings
6. **Rerun driver** — verify parity

---

## Files Most Likely to Change

| File | Change type | 96D phase |
|---|---|---|
| `src/prep/api/routers/queue.py` | 1-line add to exclude set | 96D.1 |
| `src/prep/server.py` | anyio thread pool bump | 96D.2 |
| `packages/ui/src/components/navigation/ProjectList.tsx` | active indicator logic | 96D.3 |
| `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` | stale-state badge | 96D.4 |
| `src/prep/dashboard/src/hooks/useProjectManager.ts` | active state source | 96D.3 |
| `tools/playwright_smoke.py` (new) | UI driver for smoke tests | 96D.5 |

---

## Out of Scope

- Backend pipeline behavior (already fixed in 96A/B)
- Test failures in `test_pipeline_budget.py` / `test_pipeline_journal.py` (pre-existing, separate)
- MCP server stability (separate workstream)
- Dashboard splash screen / startup detection UX (separate)
