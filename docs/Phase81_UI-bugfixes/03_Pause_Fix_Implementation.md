# Phase 81 — Pause Button P0 Fixes (Implemented)

**Date:** 2026-04-07
**Status:** Committed to main @ `a86331b0`

---

## Changes Made

### Fix 1: FAST_COMPLETED/FAST_FAILED now clears fastPaused

**File:** `src/codrag/dashboard/src/state/enrichmentReducer.ts:190`

**Problem:** When fast sync completes or fails, `fastPausedStage` was cleared but `fastPaused` was not. This meant the UI could show stale "Paused" state after a successful pipeline completion. `DEEP_COMPLETED` already cleared `deepPaused` — this was an inconsistency.

**Fix:** Added `fastPaused: false` to the `FAST_COMPLETED`/`FAST_FAILED` reducer case.

### Fix 2: Resume button visible regardless of Auto/Manual mode

**File:** `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1153`

**Problem:** The deep enrichment Resume button was gated on `deepMode === 'manual'`. If a user paused deep enrichment while in Auto mode (via the stage-row hover button), or if the pipeline was paused and they then switched to Auto mode, the Resume button disappeared with no way to recover.

**Fix:** Removed the `deepMode === 'manual'` guard. Resume now shows whenever `deepPaused && !deepRunning`, matching the fast sync Resume button pattern (line 1089).

### Fix 3: Deep stage onPause guard matches fast stage pattern

**File:** `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1211`

**Problem:** Deep enrichment stages always received `onPause` (if the handler existed), regardless of whether the stage was running. Fast stages correctly gated this on `stage.state === 'running' || stage.state === 'rerunning'`. While StageRow has an internal guard (`isRunning && hovered`), passing `onPause` unconditionally is inconsistent and could cause issues with future StageRow changes.

**Fix:** Applied the same guard pattern as fast stages: `stage.state === 'running' || stage.state === 'rerunning' ? onPausePipeline : undefined`.

### Fix 4: Removed hardcoded rerun values from footer progress bar

**File:** `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:1241`

**Problem:** The overall health progress bar at the bottom of the pipeline panel always passed `rerun={{ donePercent: 50, stalePercent: 20 }}` — hardcoded values that don't reflect actual pipeline state. This rendered a visual overlay on the progress bar that was always wrong.

**Fix:** Removed the `rerun` prop entirely. The progress bar now shows only the calculated `roundedProgress` value.

---

## P1 Pause Issues (completed in Stage 1 @ `acfb33b9`)

| Bug | Status | Description |
|-----|--------|-------------|
| Auto→Manual doesn't pause | **Fixed** | Toggle now calls `pausePipeline()` when switching to Manual |
| Legacy paused detection | **Mitigated** | Added `pausing` phase detection; kept legacy for compat |
| Optimistic pause flicker | **Fixed** | Backend now emits SSE after PAUSED transition |
| handleTogglePause dead code | **Removed** | Removed from useTraceSystem, App.tsx, useDashboardPanels, component |

---

## Verification

TypeScript compilation: all errors are pre-existing (AnimatedCLI/IDE unused vars, OpportunitiesSummary type mismatch). No new errors introduced by these fixes.
