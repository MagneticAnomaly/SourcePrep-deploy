# Phase 24 — Dashboard State Machine

## Problem Statement

`App.tsx` is a 1,846-line monolith containing **54 `useState` calls**, **53 `useCallback` handlers**, and **12 `useEffect` watchers** — all independent, manually synchronized. This causes:

1. **Stale-state bugs** — e.g. trace build completes via SSE but `exists` never flips because the watcher only resets `building`.
2. **Impossible states** — nothing prevents `building: true` + `exists: false` from persisting forever.
3. **Scattered side-effects** — a single user action (e.g. "Build Trace Graph") must update 3–5 separate `useState` variables in the right order across multiple callbacks.
4. **Prop-drilling hell** — dozens of handlers and state slices are threaded through the panel memoization block.

## Goal

Replace the ad-hoc `useState` soup with **domain-scoped state machines** using `useReducer` (zero new dependencies). Each reducer owns a coherent slice of state, defines explicit actions/transitions, and co-locates side-effect triggers.

This is **not** a rewrite — it's an incremental extraction. App.tsx stays as the orchestrator; reducers are pulled into separate files and composed via hooks.

---

## Current State Inventory

### 54 `useState` calls, grouped by domain

| Domain | Count | Variables |
|--------|-------|-----------|
| **Connection** | 2 | `isConnected`, `isDaemonUnhealthy` |
| **Global/Error** | 2 | `loading`, `_error` |
| **Projects** | 4 | `projects`, `selectedProjectId`, `projectStatuses`, `buildingProjects` |
| **UI Chrome** | 6 | `addModalOpen`, `sidebarCollapsed`, `uiMode`, `uiTheme`, `settingsOpen`, `bgImage`, `dashboardLayout` |
| **Search** | 6 | `query`, `searchK`, `minScore`, `searchLoading`, `searchResults`, `selectedChunk` |
| **Context** | 5 | `contextK`, `contextMaxChars`, `contextIncludeSources`, `contextIncludeScores`, `contextStructured`, `context`, `contextMeta` |
| **File Tree / Paths** | 5 | `fileTree`, `pathWeights`, `includedPaths`, `pinnedPaths`, `pinnedFiles` |
| **Watch** | 2 | `watchStatus`, `watchLoading` |
| **Project Config** | 3 | `projectConfig`, `configDirty`, `deepAnalysisSchedule` |
| **Trace Pipeline** | 4 | `traceStatus`, `traceCoverage`, `indexAutoRebuild`, `enrichmentAutoConfig` |
| **Enrichment Stages** | 12 | `augmentationStatus`, `augmenting`, `deepAnalysisStatus`, `deepAnalysisRunning`, `epistemicStatus`, `epistemicRunning`, `moduleStatus`, `clusterRunning`, `deepeningStatus`, `deepeningRunning`, `knowledgeStatus`, `knowledgeBuilding` |

### Key pain points by domain

- **Trace Pipeline + Enrichment Stages** (16 vars) — the most tightly coupled and the source of nearly every recent bug. A single build action touches `traceStatus.building`, `traceCoverage.building`, and multiple enrichment stage booleans.
- **Search + Context** (11 vars) — independent from trace but still have their own loading/result lifecycle.
- **UI Chrome** (6 vars) — pure local preferences, lowest priority to refactor.

---

## Architecture

### Approach: `useReducer` per domain

```
src/codrag/dashboard/src/
├── state/
│   ├── tracePipelineReducer.ts    ← Phase 1 (highest value)
│   ├── enrichmentReducer.ts       ← Phase 2
│   ├── searchReducer.ts           ← Phase 3
│   ├── projectReducer.ts          ← Phase 4
│   └── index.ts                   ← barrel
├── hooks/
│   ├── useTracePipeline.ts        ← reducer + side-effect callbacks
│   ├── useEnrichment.ts
│   ├── useSearchContext.ts
│   └── useProjectManager.ts
└── App.tsx                         ← composes hooks, passes to panels
```

Each `useXxx` hook:
1. Calls `useReducer(xxxReducer, initialState)`
2. Wraps `dispatch` calls in named callbacks (e.g. `startBuild`, `buildCompleted`)
3. Handles API calls and dispatches on success/failure
4. Returns `{ state, actions }` to App.tsx

### State machine pattern (per reducer)

```typescript
// Example: tracePipelineReducer.ts

type TracePhase = 'idle' | 'building' | 'ready' | 'error';

interface TracePipelineState {
  phase: TracePhase;
  enabled: boolean;
  exists: boolean;
  counts: { nodes: number; edges: number };
  engine?: string;
  coverage: {
    summary: TraceCoverageSummary | null;
    untraced: TraceCoverageFile[];
    stale: TraceCoverageFile[];
    excluded: TraceCoverageFile[];
    loading: boolean;
  };
  autoConfig: EnrichmentAutoConfig;
  indexAutoRebuild: boolean;
  error?: string;
}

type TracePipelineAction =
  | { type: 'BUILD_STARTED' }
  | { type: 'BUILD_COMPLETED'; payload: TraceStatusResponse }
  | { type: 'BUILD_FAILED'; error: string }
  | { type: 'STATUS_LOADED'; payload: TraceStatusResponse }
  | { type: 'COVERAGE_LOADING' }
  | { type: 'COVERAGE_LOADED'; payload: TraceCoverageResponse }
  | { type: 'COVERAGE_FAILED' }
  | { type: 'DESTROYED' }
  | { type: 'SET_AUTO_CONFIG'; payload: EnrichmentAutoConfig }
  | { type: 'SET_INDEX_AUTO_REBUILD'; payload: boolean };
```

**Key invariants enforced by the reducer:**
- `phase === 'building'` → `exists` can be true or false (rebuild vs first build)
- `BUILD_COMPLETED` always sets `exists: true`, `phase: 'ready'`
- `DESTROYED` resets to initial state
- `BUILD_STARTED` is a no-op if already `phase === 'building'`

---

## Implementation Plan

### Phase 1 — Trace Pipeline Reducer (highest value, fixes active bugs)

**Files created:**
- `src/codrag/dashboard/src/state/tracePipelineReducer.ts`
- `src/codrag/dashboard/src/hooks/useTracePipeline.ts`

**Replaces these `useState` calls in App.tsx:**
- `traceStatus` (enabled, exists, building, counts, engine)
- `traceCoverage` (summary, untraced, stale, excluded, building, loading)
- `indexAutoRebuild`
- `enrichmentAutoConfig`

**Replaces these `useCallback` handlers:**
- `handleRunFastSync`
- `handleBuildTrace`
- `handleTraceAll`
- `handleRetraceStale`
- `handleEnableTrace`
- `handleTogglePause`
- `fetchTraceCoverage`
- `handleAddExcludePattern`
- `handleRemoveExcludePattern`
- `handleDestroyGraph`

**Replaces this `useEffect`:**
- SSE trace-build completion watcher (lines 1067–1094)

**Migration steps:**
1. Create `tracePipelineReducer.ts` with state type, action type, and reducer function
2. Create `useTracePipeline.ts` hook that:
   - Calls `useReducer`
   - Accepts `api`, `selectedProjectId`, `findActiveTask`, `isPro`
   - Exposes `state` and named action functions
   - Contains the SSE watcher as an internal `useEffect`
3. In App.tsx: replace the 4 `useState` + ~10 `useCallback` + 1 `useEffect` with a single `const { trace, traceActions } = useTracePipeline(...)`
4. Update panel props to read from `trace.*` instead of individual variables
5. Run TypeScript check + manual verify

**Estimated LOC removed from App.tsx:** ~200 lines
**Risk:** Low — pure refactor, no behavior change

---

### Phase 2 — Enrichment Stages Reducer

**Files created:**
- `src/codrag/dashboard/src/state/enrichmentReducer.ts`
- `src/codrag/dashboard/src/hooks/useEnrichment.ts`

**Replaces these `useState` calls (12 variables):**
- `augmentationStatus`, `augmenting`
- `deepAnalysisStatus`, `deepAnalysisRunning`
- `epistemicStatus`, `epistemicRunning`
- `moduleStatus`, `clusterRunning`
- `deepeningStatus`, `deepeningRunning`
- `knowledgeStatus`, `knowledgeBuilding`

**State machine for each stage:**
```
idle → running → completed
              ↘ failed
```

**Replaces these `useCallback` handlers:**
- `handleRunAugmentation`
- `handleRunDeepAnalysis`, `handleCancelDeepAnalysis`
- `handleRunEpistemic`
- `handleRunModuleSynthesis`
- `handleRunDeepening`
- `handleRunKnowledgeBuild`
- `handleRunDeepEnrichment`

**Estimated LOC removed from App.tsx:** ~250 lines

---

### Phase 3 — Search + Context Reducer

**Files created:**
- `src/codrag/dashboard/src/state/searchReducer.ts`
- `src/codrag/dashboard/src/hooks/useSearchContext.ts`

**Replaces:** 11 `useState` calls, ~5 callbacks

**Lower priority** — these states are already fairly isolated and don't cause cross-domain bugs.

**Estimated LOC removed from App.tsx:** ~100 lines

---

### Phase 4 — Project Manager Reducer

**Files created:**
- `src/codrag/dashboard/src/state/projectReducer.ts`
- `src/codrag/dashboard/src/hooks/useProjectManager.ts`

**Replaces:** `projects`, `selectedProjectId`, `projectStatuses`, `buildingProjects`, `projectConfig`, `configDirty`

**Estimated LOC removed from App.tsx:** ~150 lines

---

## What stays in App.tsx

After all 4 phases, App.tsx becomes a ~500-line orchestrator:

```typescript
function App() {
  const api = useApiClient()
  const { connected, unhealthy } = useConnection(api)
  const { projects, selected, actions: projectActions } = useProjectManager(api)
  const { trace, actions: traceActions } = useTracePipeline(api, selected.id, ...)
  const { enrichment, actions: enrichActions } = useEnrichment(api, selected.id, ...)
  const { search, actions: searchActions } = useSearchContext(api, selected.id)
  const license = useLicenseSystem()
  const llm = useLLMConfig(...)

  // UI chrome (stays as useState — too simple to extract)
  const [uiMode, setUiMode] = useState(...)
  const [settingsOpen, setSettingsOpen] = useState(false)
  // ...

  // Panel content map (memoized)
  const panelContent = useMemo(() => ({ ... }), [...])

  return <Dashboard ... />
}
```

---

## Sequencing & Dependencies

```
Phase 1 (Trace Pipeline)  ──→  Phase 2 (Enrichment)
         ↓                              ↓
   Phase 3 (Search)            Phase 4 (Projects)
```

Phase 1 and Phase 2 are tightly related (enrichment depends on trace existence). Do them back-to-back. Phases 3 and 4 are independent and can be done in any order.

## Testing Strategy

Each phase:
1. TypeScript compilation check (`npx tsc --noEmit`)
2. Manual smoke test: open dashboard, select project, trigger build, verify all panels update
3. Regression check: destroy graph, verify reset; toggle free/pro; verify disabled states

## Decision Log

| Decision | Rationale |
|----------|-----------|
| `useReducer` over Zustand/XState | Zero new deps, familiar pattern, sufficient for this scale |
| Domain-scoped hooks over single global store | Each hook is independently testable, no cross-domain coupling |
| Incremental migration over big-bang rewrite | Each phase is independently shippable and verifiable |
| Keep UI chrome as `useState` | Too simple and isolated to warrant a reducer |
