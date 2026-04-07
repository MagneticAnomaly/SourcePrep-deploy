# Phase 81 — Pipeline Pause & Dashboard UI State Audit

**Date:** 2026-04-07
**Status:** Analysis complete, fixes pending
**Scope:** Pipeline pause/resume, Auto/Manual toggle, general dashboard state consistency

---

## Executive Summary

The pipeline pause function is not a single button — it's a **multi-trigger system** that should pause the pipeline when:

1. The Pause button is clicked on a running stage (hover-to-reveal)
2. The Auto/Manual toggle switches to Manual (if running in Auto mode)
3. A project is toggled inactive
4. The Auto toggle defaults to a paused/idle state on first load

Currently these triggers work through different code paths with inconsistent behavior. The broader issue is that many UI elements are loosely coupled to backend state — they work "well enough" individually but create unpredictable combined behavior. None of this is a regression; it's the first systematic audit.

---

## Architecture Overview

### State Layers

```
Backend State Machine (authoritative)
  src/codrag/services/pipeline/state_machine.py
  States: IDLE → QUEUED → RUNNING → PAUSING → PAUSED → (RESUME) → RUNNING
                                   → COMPLETED / FAILED / CANCELLED

SSE Events (real-time bridge)
  Pushes { phase: "running"|"paused"|"pausing"|..., current_stage: "catalogue"|... }

Frontend Reducer (UI state)
  src/codrag/dashboard/src/state/enrichmentReducer.ts
  Mirrors backend via SYNC_RUNNING + SYNC_PAUSED actions

Frontend Compute Functions (derived visual state)
  packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:278-501
  Each stage independently computes: disabled|waiting|running|complete|...
```

### Key Files

| Layer | File | Lines |
|-------|------|-------|
| State machine | `src/codrag/services/pipeline/state_machine.py` | 94-184 |
| Orchestrator pause | `src/codrag/services/pipeline/orchestrator.py` | 861-901, 1831-1899 |
| API endpoints | `src/codrag/api/routers/pipeline.py` | 518-571 |
| Frontend reducer | `src/codrag/dashboard/src/state/enrichmentReducer.ts` | 1-212 |
| useEnrichment hook | `src/codrag/dashboard/src/hooks/useEnrichment.ts` | 190-224 |
| useTraceSystem hook | `src/codrag/dashboard/src/hooks/useTraceSystem.ts` | 303-310, 376-431 |
| Pipeline UI | `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` | 552-684, 1074-1254 |
| SlidingSwitch | `packages/ui/src/components/primitives/SlidingSwitch.tsx` | 1-108 |
| API client | `packages/ui/src/api/client.ts` | 145-174 |

---

## Bug 1: Pause Button — Multiple Inconsistent Triggers

### What Should Happen

Pause should be a single unified concept: "stop the pipeline gracefully, save progress, show amber state." These triggers should all produce the same result:

1. **Hover-pause button** on a running stage row
2. **Group-level pause** (not currently exposed as a separate button)
3. **Auto→Manual toggle switch** (should pause if running)
4. **Project deactivation** (should pause all running pipelines)

### What Actually Happens

#### Trigger 1: StageRow hover-pause button (lines 621-628)
- Calls `onPausePipeline(group)` → `handlePausePipeline` in useEnrichment.ts:190
- Sends `POST /pipeline/pause` to backend
- Dispatches optimistic `SYNC_PAUSED` to reducer
- **Works correctly** for the happy path, but:
  - Only visible on hover (discoverability issue)
  - `onPause` is only passed when `stage.state === 'running'` (line 1138) — but during `PAUSING` phase the SSE may report the stage as still running, creating a race where pressing pause again does nothing or errors

#### Trigger 2: Auto→Manual toggle
- `handleEnrichmentAutoConfigChange` in useTraceSystem.ts:376-431
- **Does NOT pause the pipeline.** When switching from Auto to Manual, it just updates the config. If the pipeline was already running in Auto mode, it continues running.
- **BUG:** Switching to Manual should pause any active pipeline run, or at minimum stop auto-triggers. Currently the pipeline keeps running after toggling to Manual.

#### Trigger 3: Project deactivation
- The `inactive` prop disables buttons (line 1102) but does **not** pause a running pipeline
- **BUG:** Deactivating a project should cancel/pause all running pipelines for that project

#### Trigger 4: Default Auto config state
- Default is `{ fastSync: true, deepEnrichment: 'manual' }` (line 505, useTraceSystem.ts:110)
- On first load, Fast Sync defaults to Auto=true, Deep defaults to Manual
- **Issue:** If Auto=true but no pipeline is running, the initial state is ambiguous. The "Watching" badge appears (line 1081) but nothing is actually running. This creates confusion about whether the system is active.

### Recommended Fix

Create a unified `pausePipeline(group, reason)` function that:
1. Calls the backend pause endpoint
2. Updates the reducer
3. Is called from ALL triggers (button, toggle, deactivation)

For Auto→Manual: call `pausePipeline` if the group is currently running.
For deactivation: call `pausePipeline` for all active groups.

---

## Bug 2: FAST_COMPLETED Does Not Clear fastPaused

### What Happens

In `enrichmentReducer.ts:188-195`:
```typescript
case 'FAST_COMPLETED':
case 'FAST_FAILED':
  return {
    ...state,
    inferredEdgesRunning: false, augmenting: false, validating: false,
    fastKnowledgeBuilding: false, fastPausedStage: undefined,
    // NOTE: fastPaused is NOT cleared here
  }
```

`FAST_COMPLETED` clears `fastPausedStage` but does NOT clear `fastPaused`. Meanwhile `DEEP_COMPLETED` DOES clear `deepPaused` (line 201).

### Impact

If fast sync is paused, then resumed, then completes — `fastPaused` stays `true` in the reducer. The next SSE event will overwrite it via `SYNC_PAUSED`, but there's a window where the UI could show a stale "Paused" state after completion.

### Recommended Fix

Add `fastPaused: false` to the `FAST_COMPLETED`/`FAST_FAILED` case (matching `DEEP_COMPLETED`).

---

## Bug 3: Paused State Detection Has Legacy Fallback Logic

### What Happens

In useEnrichment.ts:319-325 and 369-376, paused state is detected via:
```typescript
fastPaused: ps.fast_sync?.phase === 'paused' ||
  (ps.fast_sync?.phase === 'failed' && (ps.fast_sync?.error || '').includes('Paused by user'))
```

This dual check exists because the backend originally used `phase: "failed"` with `error: "Paused by user"` before the proper `PAUSED` state was added to the state machine.

### Impact

- If the backend ever emits a `failed` phase with an error message containing "Paused by user" for a non-pause reason, the UI will incorrectly show paused state
- The legacy path complicates the code and creates confusion about what "paused" actually means
- During the `PAUSING` intermediate state, the frontend doesn't show any pausing indicator — it looks like it's still running until `PAUSED` arrives

### Recommended Fix

1. Remove the legacy `failed + 'Paused by user'` detection if the backend no longer produces it
2. Add `'pausing'` to the ACTIVE_PHASES set for display purposes (show a "Pausing..." indicator)

---

## Bug 4: Resume Button Only Shows in Manual Mode (Deep Enrichment)

### What Happens

In GraphEnrichmentPipeline.tsx:1153:
```typescript
{deepMode === 'manual' && deepPaused && onResumePipeline && !deepRunning && (
  <button onClick={() => onResumePipeline('deep_enrichment')}>Resume</button>
)}
```

If deep enrichment is paused while in Auto mode, the Resume button is hidden because `deepMode !== 'manual'`.

### Impact

If a user pauses deep enrichment, then switches to Auto mode, or if the pipeline was paused while in Auto mode (e.g., via the stage-row pause button), there's no way to resume it from the UI.

### Recommended Fix

Show the Resume button whenever `deepPaused` is true, regardless of mode. Or: auto-resume on switching to Auto mode if paused.

---

## Bug 5: Per-Stage Paused Highlight Heuristic Can Be Wrong

### What Happens

In GraphEnrichmentPipeline.tsx:1129-1132:
```typescript
const isStagePaused = fastPausedStage
  ? !!(fastPaused && !fastRunning && stage.id === fastPausedStage)
  : !!(fastPaused && !fastRunning && stage.state !== 'complete' && stage.state !== 'disabled' &&
    fastStages.slice(0, idx).every(s => s.state === 'complete' || s.state === 'disabled'));
```

The heuristic fallback (when `fastPausedStage` is not set) marks the first non-complete, non-disabled stage as paused. This works if compute functions return correct states, but:

- During the optimistic update in `handlePausePipeline` (line 200-202), `fastPausedStage` is explicitly set to `undefined` because the client doesn't know which stage the backend will land on
- The compute functions may return `running` for the paused stage (because SYNC_RUNNING hasn't been cleared yet), which means `stage.state !== 'complete'` is true but the stage still appears to be running, not paused

### Impact

There's a brief flicker where the stage shows as "running" immediately after clicking pause, before the SSE confirms the paused state with the correct stage.

### Recommended Fix

On optimistic pause, immediately clear the running flag for all stages in the group and set the stage states to reflect the paused state. Alternatively, add a `PAUSING` intermediate state to the frontend that shows "Pausing..." with an amber spinner.

---

## Bug 6: handleTogglePause Is a Dead Code Path

### What Happens

In useTraceSystem.ts:303-310:
```typescript
const handleTogglePause = useCallback(() => {
  if (!selectedProjectId) return
  const newPaused = !deps.projectConfig.trace.paused
  const newConfig = { ...deps.projectConfig, trace: { ...deps.projectConfig.trace, paused: newPaused } }
  deps.setProjectConfig(newConfig)
  deps.setConfigDirty(true)
  api.updateProject(selectedProjectId, { config: newConfig }).catch(() => { })
}, [api, selectedProjectId, deps.projectConfig, deps.setProjectConfig, deps.setConfigDirty])
```

This toggles `projectConfig.trace.paused` — a project-level config flag. This is **completely separate** from the pipeline state machine's PAUSED state. It writes to the project config DB but does NOT interact with the pipeline orchestrator.

### Impact

- `handleTogglePause` is exported and available as a prop (`onTogglePause`) but does nothing to actually pause the pipeline
- There are now TWO different "pause" concepts: project-config-pause and pipeline-state-machine-pause
- The `trace.paused` config field may be checked by the file watcher but is ignored by the pipeline orchestrator

### Recommended Fix

Either:
1. Remove `handleTogglePause` if it's unused, OR
2. Make it call the pipeline pause endpoint instead of toggling a config flag, OR
3. Rename it to clarify it's a "pause watching" toggle, not a "pause pipeline" toggle

---

## Bug 7: Auto Toggle Defaults and Initial State Confusion

### What Happens

1. Default config: `fastSync: true` (Auto), `deepEnrichment: 'manual'`
2. On startup, the config is loaded from backend settings, falling back to localStorage, falling back to defaults
3. If Fast Sync is Auto=true, the "Watching" badge appears immediately (line 1081-1086)
4. A watcher-start is attempted after a 2-second delay (useTraceSystem.ts:695-716)
5. But no pipeline run is triggered unless `!traceStatus.building` (line 404)

### Impact

- New projects show "Watching" badge but nothing happens until files change
- The gap between "Watching" displayed and watcher actually starting (2s delay) can cause confusion
- If the backend settings endpoint fails, the fallback chain (backend → localStorage → defaults) can produce different configs on different page loads

### Recommended Fix

1. Don't show "Watching" badge until watcher is confirmed running (check watcher status)
2. Consider defaulting to `fastSync: false` for new projects — require explicit opt-in
3. Consolidate the config loading to a single source of truth (backend settings only, with explicit migration)

---

## Bug 8: Compute Functions Don't Account for Paused State

### What Happens

The `compute*State` functions (lines 278-501) return states like `running`, `complete`, `disabled`, `not_built` — but none return `paused`. The paused state is handled separately via the `isStagePaused` heuristic at render time (lines 1129-1132).

### Impact

- Stage state (`stage.state`) and paused state (`isPaused`) are independent, which means a stage can be `state: 'running'` AND `isPaused: true` simultaneously
- The StageRow component handles this (lines 586-633) but the precedence rules are implicit in the rendering order, not explicit in the state model
- Any new consumer of stage state would need to independently handle the paused overlay

### Recommended Fix

Either:
1. Add `'paused'` to the `StageState` type and return it from compute functions when the group is paused, OR
2. Document the contract: "isPaused is an overlay on top of stage state and takes visual precedence"

Option 1 is cleaner but requires changes to all compute functions. Option 2 maintains the current architecture but needs a clear comment.

---

## Bug 9: Deep Enrichment StageRow Always Gets onPause

### What Happens

In GraphEnrichmentPipeline.tsx:1211:
```typescript
onPause={onPausePipeline ? () => onPausePipeline('deep_enrichment') : undefined}
```

For deep stages, `onPause` is always passed (if `onPausePipeline` exists), regardless of whether the stage is running. Compare with fast stages (line 1138):
```typescript
onPause={stage.state === 'running' || stage.state === 'rerunning' ? onPausePipeline : undefined}
```

### Impact

For deep stages, the StageRow component receives `onPause` even when the stage isn't running. The StageRow guards this at render time (`isRunning && hovered && onPause`), so it doesn't visually break — but the inconsistency suggests the guard was meant to be at the parent level.

### Recommended Fix

Apply the same pattern as fast stages:
```typescript
onPause={stage.state === 'running' || stage.state === 'rerunning' ? onPausePipeline : undefined}
```

---

## Bug 10: Overall Progress Bar Has Hardcoded Rerun Values

### What Happens

In GraphEnrichmentPipeline.tsx:1241-1242:
```typescript
<StageProgressBar
  progress={roundedProgress}
  rerun={{ donePercent: 50, stalePercent: 20 }}
/>
```

The footer progress bar always shows `donePercent: 50, stalePercent: 20` hardcoded, regardless of actual pipeline state.

### Recommended Fix

Either compute actual values from stage states or remove the `rerun` prop from the footer bar.

---

## Broader UI Consistency Issues

### Issue A: Multiple State Sources, No Single Source of Truth

The dashboard has three overlapping state sources:
1. **SSE events** (real-time, authoritative for running/paused phase)
2. **API polling** (3-second intervals for progress data)
3. **Optimistic UI updates** (immediate on user action)

These can conflict. Example flow:
1. User clicks Pause → optimistic `SYNC_PAUSED(fastPaused: true)`
2. SSE fires with `phase: "pausing"` → `SYNC_PAUSED(fastPaused: false)` (because `pausing !== paused`)
3. SSE fires with `phase: "paused"` → `SYNC_PAUSED(fastPaused: true)` (correct again)

The step 2 blip causes a momentary un-pause in the UI.

### Issue B: No Loading/Transition States

The UI jumps directly between states without intermediate loading indicators:
- No "Pausing..." state between clicking pause and backend confirming
- No "Starting..." state between clicking Run and first SSE event
- No "Resuming..." state between clicking resume and pipeline restarting

### Issue C: Disabled vs Not Built vs Waiting Are Visually Ambiguous

All three show similar grey/muted states. A user can't tell whether a stage is:
- Disabled because prerequisites aren't met
- Not yet built (ready to run)
- Waiting for a previous stage to finish

---

## Recommended Fix Priority

| Priority | Bug | Effort | Impact |
|----------|-----|--------|--------|
| P0 | Bug 2: FAST_COMPLETED doesn't clear fastPaused | 1 line | Stale pause state |
| P0 | Bug 4: Resume hidden in Auto mode | 2 lines | Can't resume pipeline |
| P0 | Bug 9: Deep stage onPause inconsistency | 1 line | Prevents unexpected behavior |
| P0 | Bug 10: Hardcoded progress bar rerun values | 3 lines | Visual lie |
| P1 | Bug 1: Auto→Manual doesn't pause | ~20 lines | Confusing mode switch |
| P1 | Bug 3: Legacy paused detection | ~10 lines | Simplification + correctness |
| P1 | Bug 5: Optimistic pause flicker | ~15 lines | Polish |
| P1 | Bug 6: handleTogglePause dead code | ~10 lines | Code hygiene |
| P2 | Bug 7: Auto default + Watching badge | ~20 lines | First-run confusion |
| P2 | Bug 8: Paused not in StageState | Architecture | Cleaner model |
| P2 | Issue A: SSE/optimistic conflict | ~30 lines | Race condition fix |
| P2 | Issue B: No transition states | ~40 lines | UX polish |
| P3 | Issue C: Visual ambiguity | Design | Needs design review |

---

## Next Steps

1. Fix P0 bugs (mechanical, low-risk)
2. Implement unified pause trigger for P1 Bug 1
3. Clean up legacy code (P1 Bug 3, Bug 6)
4. Design review for P2/P3 issues
