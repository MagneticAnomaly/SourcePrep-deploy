# Phase 81 — Dashboard Panel Inventory & State Audit

**Date:** 2026-04-07
**Status:** Inventory complete, per-panel deep-dives pending

---

## Dashboard Architecture Overview

### State Flow

```
                     ┌──────────────────────────────┐
                     │           App.tsx             │
                     │  (composes ~18 hooks, passes  │
                     │   state to useDashboardPanels) │
                     └──────────┬───────────────────┘
                                │
              ┌─────────────────┼─────────────────────┐
              │                 │                      │
     useHydrationController  useEventStream    useProjectManager
     (debounce + abort)      (SSE → logs,      (projects, config,
                              tasks, pipeline   status, selection)
                              events, scope)
              │                 │                      │
              ▼                 ▼                      ▼
   ┌────────────────────────────────────────────────────────┐
   │              Domain Hooks (per-feature)                 │
   │  useTraceSystem    useEnrichment    useLLMConfig       │
   │  useSearchContext   useFileSystem    useWatchSystem     │
   │  useDeepAnalysis    useAuditSystem   useSpaghettiSystem│
   │  useGoalpostsSystem useRoadmapSystem useOpportunities  │
   │  useArchitectureSystem  useConceptSystem  useAgentOps  │
   └────────────────────┬───────────────────────────────────┘
                        │
                        ▼
              useDashboardPanels.tsx
              (maps hook state → panel components)
                        │
                        ▼
              ModularDashboard (react-grid-layout)
              (renders panels in configurable grid)
```

### The Three State Sources

Every panel potentially receives state from three overlapping sources:

| Source | Update Pattern | Latency | Reliability |
|--------|---------------|---------|-------------|
| **SSE (useEventStream)** | Push, real-time | ~100ms | Drops on reconnect |
| **API Polling** | Pull, 3s intervals | 3-6s | Stale during load |
| **Optimistic Updates** | Immediate on user action | 0ms | Can conflict with SSE |

**The fundamental problem:** There is no reconciliation layer. Each hook independently decides how to merge these three sources. Some hooks use SSE as the authoritative source and only poll for detail data. Others ignore SSE entirely and poll on intervals. Some use optimistic updates that get clobbered by the next SSE event.

### Hydration Controller (Phase 70)

`useHydrationController` provides a 250ms debounce on project switches plus an `AbortSignal`. This is the closest thing to a coordinated state reset — but only 9 of 18 hooks use it:

| Hook | Uses hydration signal? | Uses isHydrating? |
|------|----------------------|-------------------|
| useTraceSystem | Yes | Yes |
| useEnrichment | Yes | Yes |
| useAuditSystem | Yes | Yes |
| useGoalpostsSystem | Yes | Yes |
| useRoadmapSystem | Yes | Yes |
| useOpportunitiesSystem | Yes | Yes |
| useArchitectureSystem | Yes | No |
| useSpaghettiSystem | Yes | No |
| useConceptSystem | **No** | **No** |
| useSearchContext | **No** | **No** |
| useFileSystem | Yes (signal only) | **No** |
| useDeepAnalysis | **No** | **No** |
| useLLMConfig | **No** | **No** |
| useWatchSystem | **No** | **No** |
| useLicenseSystem | N/A (global) | N/A |
| useProjectManager | Via ref (delayed) | Via ref (delayed) |

Hooks without hydration support may fire API calls for a stale project during the 250ms debounce window, or may not abort in-flight requests when the user rapidly switches projects.

---

## Panel Inventory

### Panel: trace-pipeline (Pipeline / Graph Enrichment)

| Aspect | Detail |
|--------|--------|
| **Component** | `GraphEnrichmentPipeline` (`packages/ui/src/components/trace/`) |
| **Hook(s)** | `useTraceSystem` + `useEnrichment` |
| **State source** | SSE (primary for running/paused), API polling (3s for progress), optimistic (pause/resume) |
| **Hydration** | Yes — both hooks reset on project switch, abort in-flight |
| **Loading state** | `projectLoading` shows spinner during hydration |
| **Error handling** | Toast on action failure, silent on poll failure |
| **Known issues** | See 01_Pipeline_Pause_and_UI_State_Audit.md (10 bugs documented) |
| **Scoped doc** | `01_Pipeline_Pause_and_UI_State_Audit.md` |

### Panel: graph-structure (Coverage / Files)

| Aspect | Detail |
|--------|--------|
| **Component** | `GraphStructurePanel` (`packages/ui/src/components/trace/`) |
| **Hook(s)** | `useTraceSystem` (coverage), `useFileSystem` (tree) |
| **State source** | API polling (3s during build), SSE (build completion triggers refresh) |
| **Hydration** | Partial — useTraceSystem has it, useFileSystem uses signal but not isHydrating |
| **Loading state** | `traceCoverage.loading` flag; but file tree has no loading state |
| **Error handling** | Silent — all catch blocks swallow errors |
| **Known issues** | File tree can show stale project's files during rapid project switch. Coverage summary fetched separately from full coverage (race). |
| **Priority** | P2 — works but has edge cases on project switch |

### Panel: index-health (Index Health)

| Aspect | Detail |
|--------|--------|
| **Component** | `IndexHealthPanel` (`packages/ui/src/components/`) |
| **Hook(s)** | Reads from `useTraceSystem` + `useEnrichment` (no dedicated hook) |
| **State source** | Derived — assembles status from multiple hooks in useDashboardPanels |
| **Hydration** | Inherits from parent hooks |
| **Loading state** | Shows `null` data when `projectStatus` is null (handled in component) |
| **Error handling** | None — relies on upstream hooks |
| **Known issues** | Complex data assembly in useDashboardPanels (lines 878-908) with lots of fallback chains (`??`). If one upstream value is stale, the derived view is inconsistent. |
| **Priority** | P3 — cosmetic inconsistency |

### Panel: atlas (Atlas Status)

| Aspect | Detail |
|--------|--------|
| **Component** | `AtlasStatusCard` (`packages/ui/src/components/trace/`) |
| **Hook(s)** | None — `atlasStatus` is a bare `useState` in App.tsx:352 |
| **State source** | Manual fetch (`fetchAtlas`) triggered on deep completion |
| **Hydration** | **No** — atlas is fetched ad-hoc, not on project switch |
| **Loading state** | **None** — shows nothing until atlas is fetched |
| **Error handling** | Silent catch: `catch { /* Atlas not available yet */ }` |
| **Known issues** | Atlas panel shows stale data from previous project until deep enrichment completes for current project. No loading indicator. No automatic refresh on project switch. |
| **Priority** | P1 — panel can show wrong project's atlas |

### Panel: deep-analysis-settings (Deep Analysis Settings)

| Aspect | Detail |
|--------|--------|
| **Component** | `DeepAnalysisSettings` |
| **Hook(s)** | `useDeepAnalysis` |
| **State source** | API (initial fetch), local state (schedule changes) |
| **Hydration** | **No** — does not use hydration controller |
| **Loading state** | **None** |
| **Error handling** | Toast on error |
| **Known issues** | Schedule config may not refresh on project switch if useDeepAnalysis doesn't reset. |
| **Priority** | P2 |

### Panel: activity-heatmap (Activity Heatmap)

| Aspect | Detail |
|--------|--------|
| **Component** | `ActivityHeatmap` (`packages/ui/src/components/`) |
| **Hook(s)** | None — `activityData` is a bare `useState` in App.tsx:353 |
| **State source** | Manual fetch, triggered alongside atlas |
| **Hydration** | **No** |
| **Loading state** | Shows "No activity data available yet" when null |
| **Error handling** | None |
| **Known issues** | Same as atlas — stale data, no project-switch refresh |
| **Priority** | P2 |

### Panel: audit (Audit)

| Aspect | Detail |
|--------|--------|
| **Component** | `AuditPanel` (`packages/ui/src/components/audit/`) |
| **Hook(s)** | `useAuditSystem` |
| **State source** | API (initial fetch + on-demand) |
| **Hydration** | Yes — uses hydrated project ID + signal + isHydrating |
| **Loading state** | Likely — needs component-level check |
| **Error handling** | Unknown — needs audit |
| **Known issues** | None apparent from App-level wiring |
| **Priority** | P3 — probably fine |

### Panel: health_scanner (Health Scanner)

| Aspect | Detail |
|--------|--------|
| **Component** | `HealthScannerPanel` |
| **Hook(s)** | `useAuditSystem` + `useSpaghettiSystem` |
| **State source** | API |
| **Hydration** | `useAuditSystem` yes; `useSpaghettiSystem` uses signal but not isHydrating |
| **Loading state** | `spaghettiLoading` flag passed |
| **Known issues** | Spaghetti system may fire requests during hydration debounce |
| **Priority** | P3 |

### Panel: spaghetti (Spaghetti Finder)

| Aspect | Detail |
|--------|--------|
| **Component** | `SpaghettiFinderPanel` |
| **Hook(s)** | `useSpaghettiSystem` |
| **State source** | API |
| **Hydration** | Signal only (no isHydrating check) |
| **Loading state** | Yes (`loading` flag) |
| **Known issues** | Minor — may make a request during debounce window |
| **Priority** | P3 |

### Panel: goalposts (Goalposts)

| Aspect | Detail |
|--------|--------|
| **Component** | `GoalpostsPanel` |
| **Hook(s)** | `useGoalpostsSystem` |
| **State source** | API |
| **Hydration** | Yes (full) |
| **Loading state** | Renders with empty props + `missing: ['Loading...']` when state is null |
| **Error handling** | Error passed as prop |
| **Known issues** | The null-state fallback renders a full GoalpostsPanel with no-op handlers and `missing: ['Loading...']` — this is a static "empty" state, not a loading indicator. User sees "Loading..." text but no spinner. |
| **Priority** | P2 — misleading loading state |

### Panel: advisor (Advisor)

| Aspect | Detail |
|--------|--------|
| **Component** | `AdvisorPanel` |
| **Hook(s)** | `useGoalpostsSystem` (shared with goalposts) |
| **State source** | API |
| **Hydration** | Yes (via goalposts hook) |
| **Loading state** | Same pattern as goalposts — null fallback with no-op handlers |
| **Known issues** | Same as goalposts |
| **Priority** | P2 |

### Panel: roadmap (Roadmap)

| Aspect | Detail |
|--------|--------|
| **Component** | `RoadmapPanel` |
| **Hook(s)** | `useRoadmapSystem` |
| **State source** | API + SSE (scans) |
| **Hydration** | Yes (full) |
| **Loading state** | Null-state fallback like goalposts, but with `ready: false` |
| **Error handling** | Error prop |
| **Known issues** | Similar null-state fallback pattern. Also, roadmap has many async handlers (GitHub sync, mine, sprint suggest) with no loading feedback. |
| **Priority** | P2 |

### Panel: token-budget (Token Budget)

| Aspect | Detail |
|--------|--------|
| **Component** | `TokenBudgetPanel` |
| **Hook(s)** | `useDeepAnalysis` (budgetUsage) |
| **State source** | API |
| **Hydration** | **No** (useDeepAnalysis doesn't use hydration controller) |
| **Loading state** | Shows `null` data when budget not enabled |
| **Known issues** | Budget data may be stale or from wrong project during rapid switch |
| **Priority** | P3 |

### Panel: opportunities (Opportunities)

| Aspect | Detail |
|--------|--------|
| **Component** | `OpportunitiesPanel` |
| **Hook(s)** | `useOpportunitiesSystem` |
| **State source** | API + SSE agent status |
| **Hydration** | Yes (full) |
| **Loading state** | Yes (`loading`, `refreshing` flags) |
| **Error handling** | Error prop |
| **Known issues** | None apparent |
| **Priority** | P3 — looks well-wired |

### Panel: architecture (Architecture Diagram)

| Aspect | Detail |
|--------|--------|
| **Component** | `ArchitectureDiagramPanel` |
| **Hook(s)** | `useArchitectureSystem` |
| **State source** | API |
| **Hydration** | Signal only (no isHydrating) |
| **Loading state** | Yes (`loading` flag) |
| **Error handling** | Error prop |
| **Known issues** | Minor — may fetch during debounce |
| **Priority** | P3 |

### Panel: concepts (Concepts)

| Aspect | Detail |
|--------|--------|
| **Component** | `ConceptsPanel` |
| **Hook(s)** | `useConceptSystem` |
| **State source** | API |
| **Hydration** | **No** — doesn't use hydration controller at all |
| **Loading state** | Yes (`loading`, `initializing` flags) |
| **Error handling** | Error prop |
| **Known issues** | No abort on project switch — may show stale concepts from previous project. No debounce protection. |
| **Priority** | P1 — no hydration = cross-project contamination risk |

### Panel: search (Context + Search)

| Aspect | Detail |
|--------|--------|
| **Component** | Search input + `ContextOutput` |
| **Hook(s)** | `useSearchContext` |
| **State source** | API (on-demand) |
| **Hydration** | **No** |
| **Loading state** | `searchLoading` flag |
| **Error handling** | Toast |
| **Known issues** | Search results persist across project switches. `resetSearch` is called from useTraceSystem's destroy handler but NOT on project switch. |
| **Priority** | P2 — stale search results from wrong project |

### Sidebar: llm-status (AI Gateway)

| Aspect | Detail |
|--------|--------|
| **Component** | `SidebarAIGateway` |
| **Hook(s)** | `useLLMConfig` |
| **State source** | API (endpoint fetch + model list) |
| **Hydration** | **No** — LLM config is global, not per-project |
| **Loading state** | `loadingModels`, `testingSlot` |
| **Known issues** | None — global config is correct to not hydrate per-project |
| **Priority** | P3 — fine |

---

## Common Anti-Patterns

### 1. Silent Error Swallowing

Almost every hook has `catch { /* silent */ }` or `catch(() => {})`. While this prevents ugly error UIs, it also means:
- Users get no feedback when panels fail to load
- Debugging requires checking browser network tab
- Panels silently show stale/empty data instead of an error state

### 2. Null-State Fallback Components

Goalposts, Advisor, and Roadmap all render the full panel component with empty/no-op props when the hook state is null. This means the component must internally handle the "not loaded yet" case, but the signal it receives (`missing: ['Loading...']`, `ready: false`) is inconsistent across panels.

### 3. Bare useState in App.tsx

Atlas status (`atlasStatus`), activity data (`activityData`), and pipeline provenance (`pipelineProvenance`) are managed as bare `useState` in App.tsx rather than in hooks. This means:
- No hydration controller integration
- No abort on project switch
- No loading states
- Manual fetch functions that may not be called at the right time

### 4. Inconsistent Hydration Adoption

9 of 18 hooks are hydration-aware. The other 9 may fire requests for stale projects during the 250ms debounce window. The hydration controller was added in Phase 70, but not all existing hooks were retrofitted.

### 5. Derived State Assembly in useDashboardPanels

The `useDashboardPanels` hook (lines 878-908 for index-health alone) assembles complex derived state from multiple upstream hooks with many `??` fallback chains. This creates a fragile intermediate layer where any upstream timing issue produces an inconsistent derived view.

---

## Recommended Fix Strategy

### Phase 81a: Pause Fix (DONE)
P0 bugs from doc 01 — applied.

### Phase 81b: Hydration Gaps (P1)
Retrofit hydration controller support into:
1. `useConceptSystem` — highest risk (no abort, no debounce)
2. Atlas/Activity/Provenance — move from bare useState to a proper hook
3. `useSearchContext` — add project-switch reset
4. `useDeepAnalysis` — add signal support

### Phase 81c: Loading States (P2)
Add consistent loading indicators:
1. Define a standard `<PanelLoading />` component
2. Use it in all panels' null-state fallback instead of ad-hoc empty props
3. Add loading flag to atlas, activity, search panels

### Phase 81d: Error Boundaries (P3)
1. Replace `catch { /* silent */ }` with `catch { setError(...) }` in hooks
2. Add `<PanelError />` component for panel-level error display
3. Wrap each panel in a React error boundary

### Phase 81e: State Architecture Review (Future)
Evaluate whether to:
- Extract a `useProjectState()` composite hook that holds all per-project state with coordinated hydration
- Introduce a lightweight state store (zustand) for cross-panel shared state
- Formalize the SSE → state reconciliation pattern

This is a larger effort that should be informed by the fixes in 81b-81d.
