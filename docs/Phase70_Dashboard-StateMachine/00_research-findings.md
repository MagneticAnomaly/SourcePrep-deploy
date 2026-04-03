# Phase 70: Dashboard Project-Switch Performance — Research Findings

## Problem Statement

When switching between projects in the CoDRAG dashboard, the UI first lags (no content updates), then completely freezes. The daemon becomes unresponsive under the load of simultaneous requests.

## Root Cause Analysis

### The Hydration Cascade

When `selectedProjectId` changes, **12+ hooks** each independently fire `useEffect` calls that trigger API requests. The total is ~20-25 simultaneous HTTP requests hitting the daemon:

| Hook | API Calls on Project Switch | Polling? |
|------|----------------------------|----------|
| useProjectManager | `getProjectStatus`, `getProject` (config) | 2s while building |
| useFileSystem | `getProjectFiles`, `getPathWeights`, `getIncludedPaths` | No |
| useTraceSystem | `getTraceStatus`, `getTraceCoverage`, `getPipelineStatus` | 3s while building |
| useEnrichment | 6x status fetches (augment, epistemic, module, deepening, knowledge, pipeline) | 3s while running |
| useAuditSystem | `getAuditStatus`, then `getAuditFindings` + `getAuditReports` | 1.5s while running |
| useSpaghettiSystem | `getSpaghettiScores` | No |
| useGoalpostsSystem | `getGoalposts` | 2s while generating |
| useRoadmapSystem | `getRoadmap`, `getVelocity` | 2s while generating |
| useOpportunitiesSystem | `getOpportunities`, `getOpportunitiesSummary` | 30s for agent status |
| useAgentOps | `getAgentsStatus`, `getHRRoster`, `getHRReadiness`, `getResearchHistory` | No |
| useDeepAnalysis | (on-demand only) | 2s while running |
| App.tsx directly | `refreshWatchStatus`, `fetchDeepAnalysisStatus`, `fetchAtlas`, `fetchProvenance`, `getProjectActivity` | 10s while pipeline runs |

### Why It Freezes

1. **Daemon overload:** 20-25 concurrent requests overwhelm the single-threaded Python backend
2. **Render cascade:** Each API response triggers `setState` -> re-render -> which may trigger more effects
3. **No cancellation:** Hooks don't cancel in-flight requests on project switch; stale responses arrive and set state for the wrong project
4. **Poll overlap:** Polling intervals from the old project can overlap with the new project's hydration
5. **Unbatched state updates:** `setState` calls inside async callbacks are not auto-batched by React 18

### Existing Mitigations (Partial)

- Most hooks clear state immediately on project switch (prevents stale data display)
- `useEnrichment` has a `cancelled` flag in its hydration effect
- `useGoalpostsSystem` and `useRoadmapSystem` clean up polling intervals on project change
- Health polling skips checks while the tab is hidden

### What's Missing

- No `AbortController` to cancel in-flight HTTP requests
- No debouncing of project selection
- No coordination between hooks (each acts independently)
- No concurrency control on outgoing requests
- No suppression of polls during hydration phase
