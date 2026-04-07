# Phase 81 Stage 1 — Pause System P1 Fixes

**Date:** 2026-04-07
**Commit:** `acfb33b9` on `phase81/ui-bugfixes`
**Status:** Complete

---

## Research Finding That Changed The Plan

The original plan assumed the backend's pipeline state machine (`PAUSING->PAUSED`) emitted SSE events. **It does not.** The SSE bridge only fires on build_orchestrator slot transitions, not pipeline state machine transitions.

The actual SSE sequence on pause:
1. Build orchestrator: slot goes `FAILED` with `error: "Paused by user"`
2. SSE bridge fires → calls `pipeline.status()` → returns `phase: "pausing"` (state machine mid-transition)
3. Pipeline orchestrator completes `PAUSING->PAUSED` → **silence** (no SSE emit)
4. Frontend only sees `phase: "paused"` on the next API poll (3+ seconds later)

This explains why the pause button felt unreliable — the frontend had a 3-second blind spot.

---

## Changes

### Backend: `src/codrag/services/pipeline/orchestrator.py`

**1. Added `_emit_pipeline_status()` helper** (new method on `PipelineOrchestrator`)

```python
def _emit_pipeline_status(self, project_id: str) -> None:
    """Emit a pipeline_status SSE event after state machine transitions
    that don't go through the build_orchestrator."""
    bus = get_event_bus()
    bus.emit("pipeline_status", {
        "project_id": project_id,
        **self.status(project_id),
    })
```

**2. Called after `_pause_group()` completes** (after `PAUSING->PAUSED` transition at line 1883)

This ensures the frontend receives `phase: "paused"` via SSE immediately, not just via polling.

### Frontend: `src/codrag/dashboard/src/hooks/useEnrichment.ts`

**3. Added `'pausing'` to pause detection** (both hydration and SSE handler)

Before:
```typescript
fastPaused: fast?.phase === 'paused' || (fast?.phase === 'failed' && ...)
```

After:
```typescript
const fastIsPausedSSE = fast?.phase === 'paused' || fast?.phase === 'pausing'
  || (fast?.phase === 'failed' && (fast?.error || '').includes('Paused by user'))
```

This catches the intermediate `pausing` state from the SSE bridge, so the UI shows amber immediately instead of continuing to show blue "running" during the flush.

The legacy `failed + "Paused by user"` detection was **kept** because `build_orchestrator.py:374` still emits `FAILED` with that error. Removing it requires a backend change to the build_orchestrator layer.

### Frontend: `src/codrag/dashboard/src/hooks/useTraceSystem.ts`

**4. Auto->Manual toggle now pauses running pipeline**

Added `pausePipeline` to `UseTraceSystemDeps` interface. In `handleEnrichmentAutoConfigChange`:

```typescript
// Phase 81: When switching to Manual, pause any running pipeline for that group.
if (!config.fastSync && prevFastSync && traceStatus.building) {
  pausePipelineRef.current?.('fast_sync').catch(() => {})
}
if (config.deepEnrichment === 'manual' && prevDeep !== 'manual') {
  pausePipelineRef.current?.('deep_enrichment').catch(() => {})
}
```

Wired via `App.tsx`: `pausePipeline: handlePausePipeline` in useTraceSystem deps.

### Dead Code Removal (6 files)

**5. Removed `handleTogglePause`** — toggled `projectConfig.trace.paused` (a config flag the pipeline orchestrator ignores), not the pipeline state machine.

| File | What was removed |
|------|-----------------|
| `useTraceSystem.ts` | `handleTogglePause` function + return value |
| `App.tsx` | Destructuring + props pass-through |
| `useDashboardPanels.tsx` | Interface field + `onTogglePause` / `paused` prop wiring |
| `GraphEnrichmentPipeline.tsx` | `onTogglePause` prop, `isPaused` prop, `paused` prop, legacy fallback |
| `GraphEnrichmentPipeline.stories.tsx` | `onTogglePause` + `paused` replaced with `fastPaused` |
| `enrichmentReducer.ts` | Updated comments to reflect actual detection logic |

---

## Verification

- TypeScript: clean (only pre-existing errors)
- Backend import: `from codrag.services.pipeline.orchestrator import pipeline_orchestrator` succeeds
