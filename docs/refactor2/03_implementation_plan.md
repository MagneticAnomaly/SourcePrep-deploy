# Refactor 2: Implementation Plan

Based on the large files and architectural optimization audits, here is the step-by-step implementation plan for the second major refactoring phase (Refactor 2).

This refactoring focuses on structural improvements without changing the core business logic. All tests must pass after each phase.

## Phase 1: Core Subsystem Decoupling (Backend)
**Target:** `src/prep/core/`

### 1.1 The Trace Subsystem
Extract components from `trace.py` (2,460 lines) into a `prep/core/trace/` subpackage.
- **Goal:** Create `models.py`, `builder.py`, `index.py`, and `analyzers/` directory.
- **Steps:**
  1. Create the `src/prep/core/trace/` directory and an empty `__init__.py`.
  2. Move data structures (`TraceNode`, `TraceEdge`, `TraceBuildResult`, `FileError`) to `models.py`.
  3. Move language parsers (`PythonAnalyzer`, `SwiftAnalyzer`, `GenericRegexAnalyzer`, `JSAnalyzer`, etc.) to `analyzers.py` (or individual files in `analyzers/`).
  4. Move `TraceBuilder` to `builder.py`.
  5. Move `TraceIndex` and graph query logic to `index.py`.
  6. Update imports across the codebase (`from prep.core.trace import TraceIndex` should still work via `__init__.py` barrel exports).

### 1.2 The Atlas Subsystem
Extract components from `atlas.py` (2,315 lines) into a `prep/core/atlas/` subpackage.
- **Goal:** Separate models, prompts, generation, and routing.
- **Steps:**
  1. Create the `src/prep/core/atlas/` directory.
  2. Move `AtlasDocument`, `Segment`, `SegmentDescriptor`, `SegmentDocument` to `models.py`.
  3. Move hardcoded prompts (`_ROOT_ATLAS_SYSTEM_PROMPT`, etc.) to `prompts.py`.
  4. Move the `CodebaseAtlas` generation and parallel execution logic to `generator.py`.
  5. Move embedding/routing logic (`generate_routing`, `embed_segments`) to `router.py`.
  6. Update `__init__.py` to export `CodebaseAtlas` to preserve external APIs.

## Phase 2: API Layer Refinement (Backend)
**Target:** `src/prep/api/routers/`

### 2.1 The Projects Router
Split `projects.py` (2,228 lines) into smaller, domain-focused routers.
- **Goal:** Create `src/prep/api/routers/projects/` subpackage.
- **Steps:**
  1. Create the `projects/` directory.
  2. Create `crud.py` for project lifecycle (`POST /projects`, `GET /projects`, `DELETE /projects/{id}`).
  3. Create `search.py` for retrieval endpoints (`GET /projects/{id}/search`, `GET /projects/{id}/context`).
  4. Create `watch.py` for watcher control (`POST /projects/{id}/watch/start`, etc.).
  5. Create `files.py` for file tree and content (`GET /projects/{id}/files`, `GET /projects/{id}/file`).
  6. In `src/prep/api/routers/projects/__init__.py`, assemble a main `router` that includes all these sub-routers so `server.py` doesn't need to change its mounting logic.

### 2.2 The Trace Router
Split `trace.py` (1,600 lines) into smaller endpoints.
- **Goal:** Create `src/prep/api/routers/trace_routes/` (name to avoid conflict with core/trace).
- **Steps:**
  1. Move standard graph queries (neighbors, path, search) to `query.py`.
  2. Move build endpoints (build, LSP edges) to `build.py`.
  3. Move enrichment pipeline endpoints (epistemic, modules, deepen) to `enrichment.py`.
  4. Assemble via `__init__.py`.

## Phase 3: Types and UI Components (Frontend)
**Target:** `packages/ui/`

### 3.1 Domain-Driven Types
Split `packages/ui/src/types.ts` (997 lines).
- **Goal:** Move types to `packages/ui/src/types/` directory.
- **Steps:**
  1. Extract `LLMConfig`, `ModelSlot`, `ClaraConfig` to `models.ts`.
  2. Extract `Project`, `ProjectConfig`, `ActivityStatus` to `project.ts`.
  3. Extract `TraceNode`, `TraceEdge`, `TraceCoverage` to `trace.ts`.
  4. Extract `PipelineRun`, `StageState` to `pipeline.ts`.
  5. Re-export everything from `packages/ui/src/types.ts` (or `index.ts`) so consumer imports don't break.

### 3.2 Splitting Marketing Heroes
Refactor `packages/ui/src/components/marketing/MarketingHero.tsx` (825 lines).
- **Goal:** Modularize the 10 hero variants.
- **Steps:**
  1. Create `components/marketing/heroes/` directory.
  2. Extract `CenteredHero.tsx`, `NeoHero.tsx`, `SwissHero.tsx`, etc.
  3. Keep `MarketingHero.tsx` as a simple factory/switch component that imports and renders the correct variant based on the `variant` prop.

### 3.3 FolderTree Logic Extraction
Refactor `packages/ui/src/components/project/FolderTree.tsx` (719 lines).
- **Goal:** Separate UI from complex tree state logic.
- **Steps:**
  1. Extract the recursive node rendering into a `FolderTreeNode.tsx` component.
  2. Extract the ancestral explosion and inclusion toggle logic into a `useFolderSelection.ts` hook.

## Phase 4: Structural Verification
- **Goal:** Ensure no logic is lost during the move.
- **Methodology:** 
  1. Map all functions/classes in the original file.
  2. Verify they exist in the new files.
  3. Run Python unit tests (`pytest`).
  4. Run TypeScript checks (`tsc --noEmit`).
  5. Run Vite and Storybook builds.

## Rules of Engagement for Refactoring
1. **No Logic Changes:** Do not change how a function works, only where it lives.
2. **Backward Compatibility:** Use `__init__.py` (Python) and barrel exports `index.ts` (TypeScript) to ensure that external modules importing these components do not break.
3. **Incremental Commits:** Verify tests pass after each sub-phase (e.g., after splitting `trace.py`, run tests before moving to `atlas.py`).
