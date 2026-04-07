# Phase 81 — Implementation Plan

**Date:** 2026-04-07
**Branch:** `phase81/ui-bugfixes`
**Base:** main @ `0dccbca0`
**Status:** Plan finalized, ready for stage-by-stage execution

---

## Completed

### Stage 0: Audit + P0 Fixes (DONE)
- Committed to main: `a86331b0`
- 4 P0 pause bugs fixed
- 3 docs created (audit, inventory, fix notes)

---

## Stages

### Stage 1: Pause P1 Fixes

**Goal:** Complete the pause system so all triggers produce consistent behavior.

**Research findings (2026-04-07 research pass):**

- `build_orchestrator.py:374-377` STILL emits `phase: FAILED, error: "Paused by user"` — this is the low-level build slot, not the pipeline state machine
- The SSE bridge (`orchestrator.py:2906`) fires `pipeline_status` on build_orchestrator slot transitions, calling `pipeline.status()` which reads the state machine
- **But** `_pause_group()` does NOT emit SSE after its `PAUSING→PAUSED` transition (line 1883). The final `PAUSED` state is only discoverable via API polling.
- So the SSE sequence on pause is: build slot `FAILED` → SSE fires → `pipeline.status()` shows `phase: "pausing"` → silence until next poll
- The legacy `"Paused by user"` detection catches the build_orchestrator's FAILED event, which may be the ONLY event in some timing windows
- `handleTogglePause` is passed through to `GraphEnrichmentPipeline` as `onTogglePause` prop (line 832 of useDashboardPanels) but the component declares it in its interface (line 63) without actually using it in the render body — it's dead code in the component

**Changes (revised after research):**

1. **Backend: Emit SSE after pause completes** (`orchestrator.py:1883`)
   - After `run.transition(Event.STAGE_FLUSHED)`, emit `pipeline_status` SSE event
   - This ensures the frontend sees `phase: "paused"` via SSE, not just polling
   - Uses the same `bus.emit("pipeline_status", ...)` pattern as the SSE bridge

2. **Frontend: Add `'pausing'` to pause detection** (`useEnrichment.ts:319, 370`)
   - Add `phase === 'pausing'` as a pause trigger (in addition to `paused` and legacy `failed`)
   - This catches the intermediate state from the SSE bridge
   - **Keep** the legacy `failed + "Paused by user"` detection for now — it's still the most reliable signal from the build_orchestrator layer. Remove it only after the backend SSE fix is confirmed working.

3. **Auto->Manual pauses running pipeline** (`useTraceSystem.ts:376-431`)
   - In `handleEnrichmentAutoConfigChange`, when `fastSync` goes `true->false` and pipeline is running, call pause
   - Same for `deepEnrichment` going from `auto`->`manual`
   - Requires passing `handlePausePipeline` into useTraceSystem deps (currently only in useEnrichment)

4. **Clean up handleTogglePause** (`useTraceSystem.ts:303-310`)
   - `onTogglePause` is declared in GraphEnrichmentPipeline's props but never referenced in the component body — dead prop
   - Remove the prop from the component interface, the handler from useTraceSystem, and the wiring in useDashboardPanels/App.tsx
   - Also remove `paused={p.projectConfig.trace.paused}` (line 831) and the legacy `isPaused` prop

**Estimated scope:** ~60 lines across 5 files (1 backend + 4 frontend).

---

### Stage 2: Hydration Gaps (P1)

**Goal:** Ensure all hooks properly reset and abort on project switch.

**Hooks to retrofit (ordered by risk):**

1. **useConceptSystem** — Highest priority. Currently takes bare `hydratedProjectId` (App.tsx:305) but doesn't use signal or isHydrating. Add `signal` and `isHydrating` params, abort in-flight requests on switch, reset state on project change.

2. **Atlas/Activity/Provenance** — Move from bare `useState` in App.tsx to a `useAtlasSystem` hook (or add to useEnrichment). Add project-switch reset, add to hydration fetch chain, add loading state.

3. **useSearchContext** — Add project-switch reset. When `selectedProjectId` changes, clear results and context. Already resets via `resetSearch` on destroy but NOT on switch.

4. **useDeepAnalysis** — Add signal support. Currently fetches on mount but has no abort mechanism.

**Pattern to follow:** Look at `useAuditSystem` or `useGoalpostsSystem` as exemplars — they properly accept `{ signal, isHydrating }` and use them.

**CoDRAG research needed:** `codrag_impact` on each hook before modifying. `codrag_search` for "useConceptSystem" call sites.

**Estimated scope:** ~100 lines across 4-5 files.

---

### Stage 3: Loading States (P2)

**Goal:** Every panel shows a clear loading indicator during hydration instead of stale/empty data.

**Changes:**

1. Create `<PanelLoading />` primitive component (small spinner + "Loading..." text)
2. Replace null-state fallback patterns in useDashboardPanels for: goalposts, advisor, roadmap
3. Add `loading` prop to AtlasStatusCard, ActivityHeatmap
4. Wire `projectLoading` through to panels that currently show stale data during switch

**Estimated scope:** ~80 lines, 1 new component + 5-6 panel tweaks.

---

### Stage 4: Error Visibility (P2-P3)

**Goal:** Replace silent error swallowing with visible feedback.

**Changes:**

1. Add `error` state to hooks that currently swallow (`useTraceSystem` coverage fetch, `useEnrichment` status fetches)
2. Show inline error messages in panels instead of empty/stale data
3. Add React error boundaries around each panel in ModularDashboard

**Estimated scope:** ~120 lines across many files. Lower priority, can defer.

---

## Execution Notes

- Execute stages sequentially (each depends on the previous being stable)
- Use `codrag_impact` before each file modification
- TypeScript check after each stage: `npx tsc --noEmit -p src/codrag/dashboard/tsconfig.json`
- Commit after each stage with clear message
- Each stage should be independently shippable (no half-done state)

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Fix pause before hydration | Pause is the most visible user-facing bug; hydration gaps are subtle |
| Don't introduce zustand/jotai | Current hook architecture is fine; the problem is missing discipline, not missing tools |
| Move atlas to a hook | Bare useState in App.tsx is the anti-pattern; a hook provides lifecycle management |
| Keep polling as-is | SSE + polling works; the issue is reconciliation, not the mechanism itself |
| Stage-by-stage commits | Each stage is independently valuable; no big-bang rewrite |
