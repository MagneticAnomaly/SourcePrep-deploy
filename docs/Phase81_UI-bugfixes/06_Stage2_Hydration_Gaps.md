# Phase 81 Stage 2 — Hydration Gaps

**Date:** 2026-04-07
**Commit:** `9303c08b` on `phase81/ui-bugfixes`
**Status:** Complete

---

## Problem

9 of 18 dashboard hooks lacked hydration controller support. On rapid project switching, these hooks could:
- Fire API requests for the wrong (stale) project
- Show data from the previous project until the new fetch completed
- Fail to abort in-flight requests, wasting daemon thread pool capacity

## Changes

### 1. useConceptSystem — AbortSignal support

**File:** `src/codrag/dashboard/src/hooks/useConceptSystem.ts`

- Added `opts: { signal?: AbortSignal }` parameter
- Pass `signal` to all `fetch()` calls (concepts, stats, questions)
- Ignore `AbortError` in catch block (project switch, not a real error)
- Updated dependency array to include `opts.signal`
- Wired in `App.tsx`: `useConceptSystem(hydration.hydratedProjectId, { signal: hydration.signal })`

**Before:** Fetch fires, user switches project, stale response updates wrong project's state.
**After:** Fetch aborts on switch, no stale data contamination.

### 2. Atlas / Activity / Provenance — immediate reset

**File:** `src/codrag/dashboard/src/App.tsx` (hydration effect at line ~642)

Added three `null` resets at the top of the project-switch effect:

```typescript
setAtlasStatus(null)
setActivityData(null)
setPipelineProvenance(null)
```

**Before:** Atlas panel showed previous project's data (segments, hub files) until deep enrichment completed for the new project.
**After:** Panel shows empty/loading immediately on switch, then populates when fetch completes.

These are still bare `useState` in App.tsx (not a dedicated hook). Moving to a `useAtlasSystem` hook is a future improvement but the immediate cross-project contamination is fixed.

### 3. useSearchContext — reset on project switch

**File:** `src/codrag/dashboard/src/hooks/useSearchContext.ts`

Added `useEffect` watching `selectedProjectId`:

```typescript
useEffect(() => {
  setSearchResults([])
  setSelectedChunk(null)
  setContext('')
  setContextMeta(null)
}, [selectedProjectId])
```

**Before:** Search results from Project A remained visible after switching to Project B. User could accidentally use wrong project's context.
**After:** Results clear immediately on project switch. Query text is preserved (user may want to re-search).

### 4. useDeepAnalysis — reset per-project state

**File:** `src/codrag/dashboard/src/hooks/useDeepAnalysis.ts`

Added `useEffect` watching `selectedProjectId`:

```typescript
useEffect(() => {
  setDeepAnalysisStatus({})
  setDeepAnalysisRunning(false)
  setBudgetUsage(null)
  setTokenUsageData(null)
}, [selectedProjectId])
```

**Before:** Budget usage and token data from Project A persisted after switching to Project B.
**After:** Resets to defaults on switch, re-populated by `fetchDeepAnalysisStatus()` in the hydration chain.

---

## Hydration Coverage After This Stage

| Hook | Before | After |
|------|--------|-------|
| useConceptSystem | No signal, no abort | Signal + abort |
| useSearchContext | No reset on switch | Reset results + context |
| useDeepAnalysis | No reset on switch | Reset status + budget + tokens |
| Atlas/Activity/Provenance (App.tsx) | No reset | Null on switch |
| useLLMConfig | No hydration | Unchanged (global, not per-project) |
| useWatchSystem | No hydration | Unchanged (re-fetched in hydration chain) |

---

## Verification

- TypeScript: clean (only pre-existing errors)
