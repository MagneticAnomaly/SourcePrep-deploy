# Phase 23 — Refactoring Implementation Plan

**Created:** 2026-02-13
**Companion doc:** `REFACTORING_STRATEGY.md` (problem analysis & architecture)
**Goal:** Incrementally reduce complexity without breaking anything.

---

## Guiding Principles

1. **One refactor per commit.** Every step must leave the codebase in a working state.
2. **Safest first.** Pure file-moves and component extractions before logic changes.
3. **Backend and frontend in parallel tracks.** They share no compile step, so sprints can interleave.
4. **No new features.** Only structural changes. Behavior must be identical before and after each step.

---

## Verification Matrix

Every sprint ends with **all** of these gates passing:

| Gate | Command | What it proves |
|---|---|---|
| **Python tests** | `pytest tests/ -x -q` | Backend logic unchanged (347 tests) |
| **UI typecheck** | `cd packages/ui && npm run typecheck` | No type regressions in shared lib |
| **UI build** | `cd packages/ui && npm run build` | Shared lib compiles clean |
| **Dashboard typecheck** | `cd src/codrag/dashboard && npx tsc --noEmit` | App types clean |
| **Dashboard build** | `cd src/codrag/dashboard && npx vite build` | App bundles without error |
| **Storybook build** | `cd packages/ui && npx storybook build` | All stories render |
| **Manual smoke** | Start daemon + dashboard, verify: project list, build, search, settings drawer, trace panel | No runtime regression |

---

## Sprint 1 — Frontend: Extract `SettingsDrawer` (Safest)

**Risk:** Very Low — pure file move, zero logic changes.
**Lines removed from App.tsx:** ~340
**Estimated effort:** 30 min

### Tasks

- [ ] **S1.1** Create `src/codrag/dashboard/src/components/settings/SettingsDrawer.tsx`
  - Copy lines 143–539 from `App.tsx` (the `SettingsDrawerProps` interface, constants, and `SettingsDrawer` function).
  - Add necessary imports (`useState`, `useApiClient`, lucide icons, `@codrag/ui` primitives).
  - Export `SettingsDrawer` and `SettingsDrawerProps`.
- [ ] **S1.2** Update `App.tsx`
  - Replace the inline `SettingsDrawer` with `import { SettingsDrawer } from './components/settings/SettingsDrawer'`.
  - Remove now-unused imports (`Key`, `Shield`, `Trash2`, `ImageIcon` if only used there).
  - Remove `DEV_TIER_OPTIONS`, `MODE_OPTIONS`, `THEME_OPTIONS` if they moved.
- [ ] **S1.3** Move helper constants
  - Move `MODE_OPTIONS`, `THEME_OPTIONS`, `DEV_TIER_OPTIONS` into the new file (they are only used by `SettingsDrawer`).

### Testing Checkpoint

```
# Gate: full verification matrix
cd packages/ui && npm run typecheck && npm run build
cd src/codrag/dashboard && npx tsc --noEmit && npx vite build
# Manual: open Settings drawer → Project / Global / Developer tabs all render and function
```

---

## Sprint 2 — Frontend: Extract `useLicenseSystem` Hook

**Risk:** Low — self-contained state with no cross-dependencies.
**Lines removed from App.tsx:** ~60
**Estimated effort:** 20 min

### Tasks

- [ ] **S2.1** Create `src/codrag/dashboard/src/hooks/useLicenseSystem.ts`
  - Move state: `licenseStatus`, `licenseKeyInput`, `licenseLoading`, `licenseError`, `devTierOverride`.
  - Move callbacks: `fetchLicense`, `handleActivateLicense`, `handleDeactivateLicense`, `handleDevTierOverrideChange`.
  - Hook takes `api` (from `useApiClient()`) as implicit dependency (call `useApiClient()` inside).
  - Returns all state + actions as a flat object.
- [ ] **S2.2** Update `App.tsx` — replace the 5 `useState` + 4 `useCallback` with `const license = useLicenseSystem()`.
- [ ] **S2.3** Update `SettingsDrawer` call-site — thread `license.*` props.

### Testing Checkpoint

```
# Gate: full verification matrix
# Manual: Settings > Global > activate/deactivate license key
# Manual: Settings > Developer > tier override toggle
```

---

## Sprint 3 — Frontend: Extract `useLLMConfig` Hook

**Risk:** Low — self-contained but larger; touches config auto-save.
**Lines removed from App.tsx:** ~130
**Estimated effort:** 30 min

### Tasks

- [ ] **S3.1** Create `src/codrag/dashboard/src/hooks/useLLMConfig.ts`
  - Move state: `llmConfig`, `availableModels`, `loadingModels`, `testingSlot`, `testResults`.
  - Move callbacks: `handleLLMConfigChange`, `handleAddEndpoint`, `handleEditEndpoint`, `handleDeleteEndpoint`, `handleTestEndpoint`, `handleFetchModels`, `handleTestModel`.
  - Move the auto-save `useEffect` (lines 1728–1741, the `llmConfigSkipRef` pattern).
  - Move the auto-fetch-models `useEffect` (lines 1811–1827).
- [ ] **S3.2** Update `App.tsx` — `const llm = useLLMConfig()`.
- [ ] **S3.3** Update `panelContent` references to use `llm.*`.

### Testing Checkpoint

```
# Gate: full verification matrix
# Manual: LLM Status panel → add endpoint, test connection, change model
# Manual: Verify LLM config persists across page reload (auto-save)
```

---

## Sprint 4 — Frontend: Extract `useDeepAnalysis` Hook

**Risk:** Low — small, isolated polling loop.
**Lines removed from App.tsx:** ~80
**Estimated effort:** 20 min

### Tasks

- [ ] **S4.1** Create `src/codrag/dashboard/src/hooks/useDeepAnalysis.ts`
  - Move state: `deepAnalysisSchedule`, `deepAnalysisStatus`, `deepAnalysisRunning`.
  - Move callbacks: `fetchDeepAnalysisStatus`, `handleRunDeepAnalysis`, `handleCancelDeepAnalysis`.
  - Move the auto-save schedule `useEffect` (lines 1787–1798, the `deepAnalysisSkipRef` pattern).
  - Hook takes `selectedProjectId` as parameter.
- [ ] **S4.2** Update `App.tsx` — `const deepAnalysis = useDeepAnalysis(selectedProjectId)`.
- [ ] **S4.3** Update `SettingsDrawer` and `panelContent` references.

### Testing Checkpoint

```
# Gate: full verification matrix
# Manual: Settings > Project > Deep Analysis section renders
# Manual: Deep Analysis panel in dashboard triggers/cancels run
```

---

## Sprint 5 — Frontend: Extract `useWatchSystem` Hook

**Risk:** Low — small and isolated.
**Lines removed from App.tsx:** ~40
**Estimated effort:** 15 min

### Tasks

- [ ] **S5.1** Create `src/codrag/dashboard/src/hooks/useWatchSystem.ts`
  - Move state: `watchStatus`, `watchLoading`.
  - Move callbacks: `refreshWatchStatus`, `handleStartWatch`, `handleStopWatch`.
  - Hook takes `selectedProjectId`.
- [ ] **S5.2** Update `App.tsx` — `const watch = useWatchSystem(selectedProjectId)`.
- [ ] **S5.3** Update `panelContent['watch']` to use `watch.*`.

### Testing Checkpoint

```
# Gate: full verification matrix
# Manual: Watch panel → start/stop watch, verify status updates
```

---

## Sprint 6 — Frontend: Extract `useTraceSystem` Hook (Largest)

**Risk:** Medium — most complex piece, many interdependent states.
**Lines removed from App.tsx:** ~350
**Estimated effort:** 60 min

### Tasks

- [ ] **S6.1** Create `src/codrag/dashboard/src/hooks/useTraceSystem.ts`
  - Move state: `traceStatus`, `traceCoverage`, `augmentationStatus`, `augmenting`, `epistemicStatus`, `epistemicRunning`, `moduleStatus`, `clusterRunning`, `deepeningStatus`, `deepeningRunning`, `graphEngineStatus`, `llmSlotsStatus`.
  - Move callbacks: `handleBuildTrace`, `handleEnableTrace`, `handleTogglePause`, `fetchTraceCoverage`, `handleTraceAll`, `handleRetraceStale`, `handleAddExcludePattern`, `handleRemoveExcludePattern`, `handleSearchTrace`, `handleGetTraceNode`, `handleGetTraceNeighbors`, `fetchAugmentationStatus`, `handleRunAugmentation`, `fetchEpistemicStatus`, `handleRunEpistemic`, `fetchModuleStatus`, `handleRunModuleSynthesis`, `fetchDeepeningStatus`, `handleRunDeepening`, `fetchGraphEngineStatus`, `handleRunStage`, `handleRunAutoPilot`, `handleStopEngine`, `fetchLLMSlotsStatus`, `handleDestroyGraph`, `handleDestroyIndex`.
  - Move the SSE trace-build-completion `useEffect` (lines 1643–1659).
  - Hook takes `selectedProjectId`, `projectConfig`, `setProjectConfig`, `setConfigDirty`, `findActiveTask`.
- [ ] **S6.2** Update `App.tsx` — `const trace = useTraceSystem(...)`.
- [ ] **S6.3** Update all `panelContent` entries that reference trace state.

### Testing Checkpoint

```
# Gate: full verification matrix
# Manual: Trace Explorer panel → search, navigate nodes
# Manual: Trace Coverage panel → queue files, map all, retrace stale
# Manual: Graph Enrichment Pipeline panel → run each stage
# Manual: Settings > Project > Danger Zone → Reset Graph, Full Reset
```

---

## Sprint 7 — Frontend: Extract `useDashboardPanels` Hook

**Risk:** Low — pure render extraction, no logic changes.
**Lines removed from App.tsx:** ~370
**Estimated effort:** 30 min

### Tasks

- [ ] **S7.1** Create `src/codrag/dashboard/src/hooks/useDashboardPanels.tsx`
  - Move the `panelContent` useMemo (lines 1899–2207).
  - Move the `panelDetails` useMemo (lines 2230–2269).
  - Move the `dynamicPanelDefs` and `allPanelDefs` useMemo blocks.
  - The hook takes all the domain hooks' return values as parameters.
- [ ] **S7.2** Update `App.tsx` — call `useDashboardPanels(...)` and pass results to `<ModularDashboard>`.

### Testing Checkpoint

```
# Gate: full verification matrix
# Manual: All dashboard panels render correctly (status, search, context, file tree, trace, etc.)
# Manual: Pin/unpin files, verify pinned file panels appear/disappear
```

---

## Sprint 8 — Frontend: Final App.tsx Cleanup

**Risk:** Low — cosmetic, no logic changes.
**Estimated effort:** 15 min

### Tasks

- [ ] **S8.1** Review `App.tsx` — it should now be ~200–300 lines.
  - Top-level: hook calls, remaining `useEffect`s (init, theme, project-change refresh).
  - Render: `<StartupScreen>` | `<LoadingState>` | `<AppShell>` + `<ModularDashboard>`.
- [ ] **S8.2** Remove dead imports, unused variables.
- [ ] **S8.3** Add brief JSDoc comments to each hook file describing its responsibility.
- [ ] **S8.4** Update `REFACTORING_STRATEGY.md` — mark frontend extraction as complete.

### Testing Checkpoint

```
# Gate: full verification matrix (final pass)
# Manual: full end-to-end walkthrough of all features
```

---

## Sprint 9 — Backend: Extract `routers/system.py`

**Risk:** Low — well-understood FastAPI pattern.
**Lines removed from server.py:** ~200
**Estimated effort:** 30 min

### Tasks

- [ ] **S9.1** Create `src/codrag/api/routers/__init__.py` (empty).
- [ ] **S9.2** Create `src/codrag/api/routers/system.py`
  - Move: `GET /health`, `GET /events` (SSE), `GET /version`, `GET /mcp-config`.
  - Move: `GET /global-config`, `PUT /global-config`.
  - Import shared state (config dicts, event bus) from `server.py` — keep globals in `server.py` for now.
  - Use `APIRouter(prefix="", tags=["system"])`.
- [ ] **S9.3** Update `server.py` — `app.include_router(system_router)`.
- [ ] **S9.4** Verify all moved endpoints still respond at the same paths.

### Testing Checkpoint

```
pytest tests/ -x -q                     # All 347 tests pass
curl http://localhost:8400/health        # Returns OK
curl http://localhost:8400/events        # SSE stream opens
# Manual: dashboard connects and loads
```

---

## Sprint 10 — Backend: Extract `routers/license.py`

**Risk:** Low — small, self-contained.
**Lines removed from server.py:** ~100
**Estimated effort:** 20 min

### Tasks

- [ ] **S10.1** Create `src/codrag/api/routers/license.py`
  - Move: `GET /license`, `POST /license/activate`, `POST /license/deactivate`.
  - Use `APIRouter(prefix="/license", tags=["license"])`.
- [ ] **S10.2** Update `server.py` — include router.

### Testing Checkpoint

```
pytest tests/test_feature_gate.py -x -q  # 37 tests pass
# Manual: Settings > Global > license activate/deactivate
```

---

## Sprint 11 — Backend: Extract `routers/trace.py`

**Risk:** Medium — largest endpoint group, touches thread state.
**Lines removed from server.py:** ~600
**Estimated effort:** 45 min

### Tasks

- [ ] **S11.1** Create `src/codrag/api/routers/trace.py`
  - Move all `/projects/{id}/trace/*` endpoints:
    - `GET /status`, `POST /build`, `GET /coverage`, `POST /ignore`
    - `GET /nodes`, `GET /nodes/{id}`, `GET /nodes/{id}/neighbors`
    - `GET /search`, `DELETE /destroy`
  - Move all `/projects/{id}/epistemic/*`, `/projects/{id}/cluster/*`, `/projects/{id}/deepening/*` endpoints.
  - Move `_epistemic_state`, `_cluster_state`, `_deepening_state` dicts.
  - Move `_deep_analysis_state` and deep analysis endpoints.
  - Import shared helpers (`_require_project`, `_get_project_trace_index`, build thread functions) from `server.py`.
- [ ] **S11.2** Update `server.py` — include router.
- [ ] **S11.3** Ensure `TRACE_FILES` constant is accessible to both `server.py` (for destroy) and `routers/trace.py`.

### Testing Checkpoint

```
pytest tests/test_trace_endpoints.py -x -q  # Trace endpoint tests pass
pytest tests/ -x -q                          # Full suite passes
# Manual: Trace Explorer, Coverage, Pipeline panels all function
```

---

## Sprint 12 — Backend: Extract `routers/knowledge.py`

**Risk:** Low — small, isolated.
**Lines removed from server.py:** ~80
**Estimated effort:** 15 min

### Tasks

- [ ] **S12.1** Create `src/codrag/api/routers/knowledge.py`
  - Move: `GET /projects/{id}/knowledge/status`, `POST /projects/{id}/knowledge/build`.
  - Move: `GET /projects/{id}/engine/status` (aggregation endpoint).
- [ ] **S12.2** Update `server.py` — include router.

### Testing Checkpoint

```
pytest tests/ -x -q
# Manual: Graph Engine panel shows all 7 stages
```

---

## Sprint 13 — Backend: Extract `routers/llm.py`

**Risk:** Low — proxy endpoints with no shared state.
**Lines removed from server.py:** ~150
**Estimated effort:** 20 min

### Tasks

- [ ] **S13.1** Create `src/codrag/api/routers/llm.py`
  - Move: `POST /llm/proxy/test`, `POST /llm/proxy/models`, `POST /llm/proxy/test-model`.
  - Move: `GET /llm/slots/status`.
  - Move: `GET /embedding/status`, `POST /embedding/download`.
- [ ] **S13.2** Update `server.py` — include router.

### Testing Checkpoint

```
pytest tests/ -x -q
# Manual: LLM Status panel → test endpoints, fetch models
```

---

## Sprint 14 — Backend: Extract `BuildManager` Service

**Risk:** Medium — touches threading and global state.
**Lines removed from server.py:** ~300
**Estimated effort:** 45 min

### Tasks

- [ ] **S14.1** Create `src/codrag/services/__init__.py` (empty).
- [ ] **S14.2** Create `src/codrag/services/build_manager.py`
  - Extract class `BuildManager` encapsulating:
    - `_project_indexes`, `_project_trace_indexes`, `_project_knowledge_indexes` caches.
    - `_project_build_lock`, `_project_build_threads` and related thread management.
    - `_project_trace_build_lock`, `_project_trace_build_threads`.
    - `_project_knowledge_build_lock`, `_project_knowledge_build_threads`.
    - Worker functions: `_project_build_worker`, `_project_trace_build_worker`, `_project_knowledge_build_worker`.
    - Query methods: `is_building()`, `is_trace_building()`, `is_knowledge_building()`.
    - Start methods: `start_build()`, `start_trace_build()`, `start_knowledge_build()`.
    - Index accessors: `get_index()`, `get_trace_index()`, `get_knowledge_index()`.
  - Singleton instance created at module level.
- [ ] **S14.3** Update `server.py` and all routers to use `build_manager.get_index(project)` instead of `_get_project_index(project)`.
- [ ] **S14.4** Remove the 10+ global variables from `server.py`.

### Testing Checkpoint

```
pytest tests/ -x -q                          # CRITICAL: full suite must pass
pytest tests/test_trace_endpoints.py -x -q
pytest tests/test_atomic_build.py -x -q
# Manual: Build a project, run trace build, verify status polling works
# Manual: Concurrent operations don't deadlock
```

---

## Sprint 15 — Backend: Final `server.py` Cleanup

**Risk:** Low — cosmetic.
**Estimated effort:** 15 min

### Tasks

- [ ] **S15.1** Review `server.py` — should now be ~1500–2000 lines (project CRUD, file serving, search, context, config).
- [ ] **S15.2** Remove dead imports, unused helper functions.
- [ ] **S15.3** Add docstrings to each router file.
- [ ] **S15.4** Update `REFACTORING_STRATEGY.md` — mark backend extraction as complete.

### Testing Checkpoint

```
pytest tests/ -x -q  # Final gate
# Manual: full end-to-end walkthrough
```

---

## Future Sprints (Deferred — Higher Risk)

These are **not** part of the initial cleanup. Track for later phases.

| ID | Description | Risk | Prerequisite |
|---|---|---|---|
| F1 | Introduce `LicenseContext` to eliminate prop drilling | Medium | S2 complete |
| F2 | Introduce TanStack Query to replace manual polling | High | S1–S8 complete |
| F3 | Split `core/trace.py` into `analyzers/` + `graph/` | Medium | S14 complete |
| F4 | Split `core/index.py` into builder/searcher | Medium | S14 complete |
| F5 | Split `MarketingHero.tsx` into per-variant files | Low | Independent |
| F6 | Extract `FolderTree` hooks | Low | Independent |

---

## Sprint Dependency Graph

```
Frontend Track              Backend Track
─────────────              ─────────────
S1 (SettingsDrawer)         S9  (routers/system)
  │                           │
S2 (useLicenseSystem)       S10 (routers/license)
  │                           │
S3 (useLLMConfig)           S11 (routers/trace)     ← largest
  │                           │
S4 (useDeepAnalysis)        S12 (routers/knowledge)
  │                           │
S5 (useWatchSystem)         S13 (routers/llm)
  │                           │
S6 (useTraceSystem) ← lrg  S14 (BuildManager)      ← riskiest
  │                           │
S7 (useDashboardPanels)    S15 (server.py cleanup)
  │
S8 (App.tsx cleanup)
```

**Frontend and backend tracks are independent** — they can be interleaved or parallelized.
Within each track, sprints are strictly sequential (each builds on the previous).

---

## Success Criteria

When all 15 sprints are complete:

- **`App.tsx`**: ≤ 300 lines (down from 2,430)
- **`server.py`**: ≤ 2,000 lines (down from 4,351)
- **New files created**: ~12 (6 hooks, 1 component, 5 routers)
- **Test count**: Same or higher (347+)
- **Zero behavior changes**: Every feature works identically
