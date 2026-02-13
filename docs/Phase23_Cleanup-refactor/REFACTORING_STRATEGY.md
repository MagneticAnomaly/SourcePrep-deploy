# CoDRAG Refactoring Strategy (Phase 23)

**Status:** Frontend extraction complete · Backend pending
**Target:** `src/codrag/dashboard/src/App.tsx` and related architecture.

## 1. Problem Statement
The `App.tsx` file has grown to ~2430 lines. It currently violates the Single Responsibility Principle by acting as a "God Object" that manages:
1.  **Global State:** Theme, License, Connection status.
2.  **Data Fetching:** Direct API calls for Projects, Trace, Coverage, Files, LLM status, etc.
3.  **UI Layout:** Defines the entire `SettingsDrawer`, `panelContent` mapping, and dashboard layout logic.
4.  **Business Logic:** Complex state machines for "Deep Analysis", "Trace Building", and "Watch" modes.

This makes the file:
*   Hard to read and navigate.
*   Prone to merge conflicts.
*   Difficult to test (too many dependencies).
*   Hard to optimize (re-renders unrelated parts of the tree).

## 2. Refactoring Strategy

### 2.1 Component Extraction
Move inline components and large render blocks into dedicated files.

*   **`SettingsDrawer`**:
    *   **Current:** Lines 201-539 (~340 lines).
    *   **Action:** Extract to `src/components/settings/SettingsDrawer.tsx`.
    *   **Props:** Currently takes ~35 props. This suggests the need for a Context or better state grouping (see Section 2.2).

*   **`PanelContent` & `PanelDetails`**:
    *   **Current:** Lines 1899-2269 (~370 lines).
    *   **Action:** Extract to `src/hooks/useDashboardPanels.tsx` or `src/config/dashboardPanels.tsx`.
    *   **Benefit:** Decouples the *definition* of panels from the *rendering* of the app shell.

### 2.2 Custom Hooks (Logic Extraction)
Group related `useState`, `useEffect`, and `useCallback` logic into domain-specific hooks.

*   **`useAppState` (or `useGlobalPreferences`)**:
    *   Manages: `uiMode`, `uiTheme`, `bgImage`, `isConnected`, `loading`.
*   **`useProjectData`**:
    *   Manages: `projects`, `selectedProjectId`, `projectStatus`, `buildingProjects`.
    *   Actions: `refreshProjects`, `handleAddProject`, `handleBuild`.
*   **`useLLMConfig`**:
    *   Manages: `llmConfig`, `availableModels`, `testingSlot`, `testResults`.
    *   Actions: `handleTestEndpoint`, `handleSaveConfig` (partial).
*   **`useTraceSystem`**:
    *   Manages: `traceStatus`, `traceCoverage`, `augmentationStatus`, `epistemicStatus`, `moduleStatus`, `deepeningStatus`.
    *   Actions: `handleBuildTrace`, `handleRunAugmentation`, `handleRunEpistemic`, etc.
*   **`useDeepAnalysis`**:
    *   Manages: `deepAnalysisSchedule`, `deepAnalysisStatus`, `deepAnalysisRunning`.
*   **`useLicenseSystem`**:
    *   Manages: `licenseStatus`, `licenseKeyInput`, `devTierOverride`.

### 2.3 Context Adoption
To avoid "Prop Drilling" (passing 35 props to SettingsDrawer), use React Context for global singletons.

*   **`ConfigContext`**: Holds `ProjectConfig` and `GlobalConfig`.
*   **`LicenseContext`**: Holds license state and actions.

### 2.4 API Layer Refinement
*   The `api` object is currently used directly in components.
*   Consider using a library like **TanStack Query (React Query)** to handle caching, loading states, and polling automatically, replacing hundreds of lines of `useEffect` + `setInterval` polling logic (e.g., `handleBuild`, `handleRunAugmentation` polling loops).

## 3. Proposed File Structure

```
src/codrag/dashboard/src/
├── App.tsx                  # <--- Reduced to < 200 lines (Providers + Shell)
├── context/
│   ├── ConfigContext.tsx
│   └── LicenseContext.tsx
├── hooks/
│   ├── useProjectData.ts
│   ├── useTraceSystem.ts
│   ├── useLLMConfig.ts
│   └── useDeepAnalysis.ts
└── components/
    ├── settings/
    │   └── SettingsDrawer.tsx
    └── dashboard/
        └── DashboardPanels.tsx
```

## 4. Execution Plan (Incremental)

1.  **Phase A (Low Risk):** Extract `SettingsDrawer` to a separate file. ✅
2.  **Phase B (Logic Grouping):** Create `useLLMConfig` and `useLicenseSystem` hooks. ✅
3.  **Phase C (Panel Decoupling):** Extract `panelContent` logic. ✅
4.  **Phase D (Complex Logic):** Extract `useTraceSystem` (the largest chunk of logic). ✅
5.  **Phase E (State Management):** Introduce Contexts or React Query — deferred to Phase 24.

### 4.1 Frontend Extraction Results

| Sprint | Extraction | File | Lines |
|--------|-----------|------|-------|
| S1 | SettingsDrawer component | `components/settings/SettingsDrawer.tsx` | ~450 |
| S2 | useLicenseSystem hook | `hooks/useLicenseSystem.ts` | ~75 |
| S3 | useLLMConfig hook | `hooks/useLLMConfig.ts` | ~220 |
| S4 | useDeepAnalysis hook | `hooks/useDeepAnalysis.ts` | ~105 |
| S5 | useWatchSystem hook | `hooks/useWatchSystem.ts` | ~70 |
| S6 | useTraceSystem hook | `hooks/useTraceSystem.ts` | ~485 |
| S7 | useDashboardPanels hook | `hooks/useDashboardPanels.tsx` | ~530 |
| S8 | Final cleanup + JSDoc | — | — |

**App.tsx:** 2,461 → 946 lines (−62%)

## 5. Backend Refactoring Strategy
**Target:** `src/codrag/server.py` (4,351 lines).

### 5.1 Problem Statement
`server.py` has become a monolith containing:
*   **FastAPI App Definition:** Middleware, exception handlers.
*   **Endpoint Definitions:** All routes are defined in one file.
*   **Service Logic:** Thread management for 3 different types of builds (Index, Trace, Knowledge).
*   **Global State:** `_project_indexes`, `_build_locks`, `_watchers`.
*   **Utility Logic:** `_ui_config_path`, event generators.

### 5.2 Proposed Split (Router Pattern)
Use `APIRouter` to split endpoints into modules under `src/codrag/api/routers/`.

*   `routers/projects.py`: CRUD, status, config.
*   `routers/trace.py`: All `/projects/{id}/trace/*` endpoints.
*   `routers/knowledge.py`: Knowledge index endpoints.
*   `routers/llm.py`: Proxy endpoints, model status.
*   `routers/system.py`: Health, events, license, global config.

### 5.3 Service Layer Extraction
Move the heavy thread management and locking logic out of the HTTP layer.

*   `src/codrag/services/build_manager.py`:
    *   Manage `_build_thread`, `_project_build_threads`.
    *   Handle locking and progress reporting.
*   `src/codrag/services/project_manager.py`:
    *   Manage `ProjectRegistry` interaction and cache invalidation.

### 5.4 Execution Plan
1.  Create `src/codrag/api/routers/__init__.py`.
2.  Move Trace endpoints (lines ~2000-2800) to `routers/trace.py`.
3.  Move Knowledge endpoints to `routers/knowledge.py`.
4.  Extract `BuildManager` class to encapsulate the 10+ global variables managing threads.

## 6. Secondary Targets & Observations

### 6.1 Frontend
*   `packages/ui/src/components/marketing/MarketingHero.tsx` (722 lines): Contains 10+ hero variants in one file.
    *   **Strategy:** Split into `heroes/HeroVariantA.tsx`, `heroes/HeroVariantB.tsx`, etc.
*   `packages/ui/src/components/project/FolderTree.tsx` (685 lines): Complex tree logic.
    *   **Strategy:** Extract specific tree manipulation logic (e.g. `useTreeTraversal`, `useDragAndDrop`) into hooks.

### 6.2 Backend (Core)
*   `src/codrag/core/trace.py` (1,324 lines):
    *   Contains `TraceBuilder`, `TraceIndex`, `PythonAnalyzer` (AST logic), and graph data structures.
    *   **Strategy:** Move `PythonAnalyzer` and language-specific logic to `codrag/core/analyzers/`. Move `TraceIndex` graph operations to `codrag/core/graph/`.
*   `src/codrag/core/index.py` (1,273 lines):
    *   Manages vector search, embedding, persistence.
    *   **Strategy:** Good candidate for splitting into `IndexBuilder` vs `IndexSearcher`.
