# Phase 24: State Machine Implementation Plan

> **Status:** ROUND 2 — Consolidated from user answers + code audit.
> **Source of truth:** The actual UI in `GraphEnrichmentPipeline.tsx` (not V2, not V3).
> **Instructions:** Review the "My Understanding" sections and the new follow-up questions.

---

## My Understanding (Consolidated)

### The Two Pillars

CoDRAG has **two separate indexing pipelines** that combine in the RAG:

**Pillar 1: Trace Graph Pipeline** (8 stages)
- Processes **ALL** files in the codebase automatically.
- Produces a structural graph, enriched metadata, and knowledge embeddings.
- Two groups of 4 — a "fast pass" then a "deep pass" with bigger models and reasoning.

**Pillar 2: Knowledge Scope (File Tree)**
- Users **select individual files** in the FolderTree panel.
- Selected files are chunked and embedded as **verbose full-code** in the CodeIndex.
- Serves as direct source-code context for RAG (literal code, not summaries).
- Completely separate pipeline from the Trace Graph.

**Both feed the RAG.** The Trace Graph gives condensed, enriched understanding. The Knowledge Scope gives full verbatim code for selected files. They live separately but combine at query time.

### The 8-Stage Trace Graph Pipeline (from UI source of truth)

**Group A — "Fast Sync" (Stages 1–4):**

| # | Stage ID | Label | Engine | What It Does |
|---|---|---|---|---|
| 1 | `structural` | Structural Graph | Rust | Parse AST → nodes + edges |
| 2 | `catalogue` | Fast Catalogue | 3b LLM | Quick summaries, domain tags |
| 3 | `validation` | Relationship Validation | Rust | Validate/infer edge relationships |
| 4 | `knowledge` | Knowledge Embedding | Embedding | Embed the fast-pass metadata |

**Group B — "Deep Enrichment" (Stages 5–8):**

| # | Stage ID | Label | Engine | What It Does |
|---|---|---|---|---|
| 5 | `enrichment` | Epistemic Enrichment | 14b LLM | Deep reasoning + confidence scoring |
| 6 | `clustering` | Cluster Synthesis | 14b LLM | Module-level concept synthesis |
| 7 | `deepening` | Continuous Deepening | Loop | Re-enrich stale nodes iteratively |
| 8 | `deep_knowledge` | Deep Knowledge Embedding | Embedding | Re-embed with deep metadata |

**The pattern mirrors:** Group A does a quick enrichment pass (Rust → 3b → Rust → embed). Group B does the same thing again deeper (14b → 14b → loop → re-embed). Group B uses its own enriched data as RAG knowledge.

### Group-Level Controls (NOT per-stage)

From the UI (`EnrichmentAutoConfig`):
- **Fast Sync:** `boolean` (on/off). Default: ON for Pro, forced OFF for Free.
- **Deep Enrichment:** `'manual' | 'auto' | 'scheduled'`. Default: manual.

**Trigger rules:**
- You can only start at Stage 1 or Stage 5. Always runs all 4 in the group.
- "Run" button for each group (visible when that group is manual).
- Free users: both groups manual. Pro users: configurable.
- If Fast Sync is auto + file changes → stages 1-4 run automatically.
- If Deep Enrichment is auto → stages 5-8 chain after 1-4 without stopping.

### Tier Model

- **FREE** = manual everything, 1 project, watcher can report staleness but won't auto-rebuild.
- **STARTER** = functionally identical to PRO but expires after 3 months.
- **PRO** = full automation, unlimited projects, all features.
- **TEAM / ENTERPRISE** = same as PRO + org features (shared config, SSO, audit). Pipeline behavior unchanged.

### Knowledge Scope (File Tree) Pipeline

Separate from the Trace Graph. The flow:
```
User selects/deselects files in FolderTree panel
         ↓
Debounce window (2-5s) to catch rapid changes
         ↓
Pro: CodeIndex incrementally rebuilds (background, invisible)
Free: "Index is stale" UI indicator, user clicks Rebuild
         ↓
Atomic swap — search works throughout, no downtime
         ↓
RAG is seamlessly updated with new/removed file embeddings
```

**File change overlap:** When a file that's in the Knowledge Scope also changes on disk:
- Knowledge Scope re-embeds the full file (CodeIndex)
- Trace Graph pipeline also updates the trace for that file (separate pipeline)
- Both run independently, potentially in parallel.

### Settings

- Local only, per Tauri instance. No sync.
- Current system (`config_manager.py` → `ui_config.json`) is a mess — needs rebuild.
- Goal: save on the fly, like any desktop app. Every toggle/setting persists immediately.

---

## Code Audit: Backend ↔ UI Gaps

I found several places where the **backend doesn't match** the current UI:

### Gap 1: Backend engine status returns 7 stages, UI shows 8

`@/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/api/routers/knowledge.py:80-161` returns:
```
stages: { trace, vector, catalogue, validation, epistemic, clustering, knowledge }
+ deepening (cross-cutting)
```

But the UI (`GraphEnrichmentPipeline.tsx`) expects 8 stages in two groups:
```
Fast:  structural, catalogue, validation, knowledge
Deep:  enrichment, clustering, deepening, deep_knowledge
```

**Differences:**
- Backend has `vector` (Source Embedding) as a separate stage — UI dropped this.
- Backend has ONE `knowledge` stage — UI has TWO (`knowledge` fast + `deep_knowledge` deep).
- Backend treats deepening as "cross-cutting" — UI puts it as Stage 7 in the deep group.

### Gap 2: Single `/knowledge/build` endpoint serves both Stage 4 and Stage 8

`KnowledgeIndex.build()` reads `trace_epistemic.jsonl` + `trace_modules.jsonl`. It always embeds whatever enrichment data currently exists. There's no distinction between a "fast knowledge build" (Stage 4) and a "deep knowledge build" (Stage 8).

The UI shows both stages 4 and 8 sharing the same `knowledge` prop (`KnowledgeEmbeddingStatus`).

### Gap 3: `GraphEnginePanel.tsx` (old 7-stage panel) still exists

V3 says to remove `trace-coverage` and `graph-engine` panels. The old `GraphEnginePanel.tsx` with 7 stages + per-stage toggles still exists in the codebase. These removal TODOs from V3 Phase 1 are unchecked.

### Gap 4: `deep_analysis` schedule in config but no pipeline config

`config_manager.py` has `deep_analysis` schedule config (mode, frequency, day_of_week, hour, budget). But there's no `pipeline_config` block for the group-level auto toggles or the two-group model.

---

## Follow-Up Questions (Round 2)

These are more targeted than Round 1 — focused on implementation specifics.

❓ **Q-A: Stage 4 vs Stage 8 Knowledge Embedding**
The backend currently has ONE knowledge build endpoint that embeds whatever epistemic/module data exists. Both UI stages (4 and 8) share the same status object. Is this correct behavior?

My interpretation: Stage 4 runs `KnowledgeIndex.build()` after fast catalogue — embeds the shallow 3b summaries. Stage 8 runs the SAME `KnowledgeIndex.build()` after deep enrichment — now it embeds the richer 14b data, effectively overwriting/upgrading Stage 4's output.

If so, do we need two separate indices (fast_knowledge + deep_knowledge), or is "one index that gets rebuilt at two points" the right model?

📝 USER:
I don't fully understand this but the whole point is the second pass builds upon the first pass. We do not need two in the database, we just use the better more robust second pass when it is complete. As far as I understand each entry is simply updated.

✅ **RESOLVED:** One KnowledgeIndex, rebuilt at two points. Stage 4 embeds fast-pass data, Stage 8 overwrites with deep data.

---

❓ **Q-B: The `vector` stage (Source Embedding)**
The old backend engine status includes a `vector` stage (CodeIndex source embedding). The new UI dropped this. But the CodeIndex is still built — it's part of the Knowledge Scope file tree pipeline, right?

My interpretation: The `vector` stage was the old "embed source code" step. This is now handled by the Knowledge Scope (file tree) pipeline separately. The Trace Graph pipeline no longer includes source embedding as one of its 8 stages. Correct?

📝 USER:
I don't know what you're talking about -- I didn't change anything about the file tree workflow. The trace graph is for the whole code and the file tree is for specific selected files in knowledge scope. They BOTH do embeddings. One creates embeddings for summaries of files in the trace graph format and the other ingests raw files and embeds them.

✅ **RESOLVED:** Two separate embedding pipelines. Trace Graph = summary embeddings. File Tree = raw file embeddings. Both feed the RAG.

---

❓ **Q-C: Deepening Loop trigger**
You said the deepening loop "simply works at file changes." But it's Stage 7 in the Deep Enrichment group. If deep enrichment is set to **manual**, does the deepening loop still react to file changes? Or is it only triggered as part of the group B (5→6→7→8) sequence?

My guess: The deepening loop only runs as part of group B. It's not a standalone watcher. When deep enrichment is auto, file changes trigger 1-4 then 5-8 (including deepening). When manual, user clicks "Run Deep" → 5-6-7-8 runs.

📝 USER:
I think the deepening loop has its own watcher -- HOWEVER I want you to review this and tell me what is best. We def need some method of preventing files from going stale. Maybe changed files should go back to the beginning of the pipeline and trigger a full build? I don't know. This is getting beyond what I can comprehend. I need guidance -- do you have enough clarity and context to provide a best path forward?

✅ **RESOLVED — My recommendation (implemented):**
The deepening loop runs ONLY as part of Group B (stages 5-8). It does NOT have its own watcher. When a file changes:
1. Fast Sync (1-4) re-runs automatically (if auto) or manually
2. Fast Sync marks affected trace nodes as "stale" in epistemic data
3. Next Group B run picks up stale nodes via the deepening loop (stage 7)
4. If deep enrichment is auto → chains after fast sync automatically
5. If manual → user sees stale indicator and clicks Run when ready

This keeps the two-group model clean and avoids a third watcher.

---

❓ **Q-D: Backend engine status endpoint — rewrite?**
Given Gap 1 above, the `/projects/{id}/engine/status` endpoint needs to be rewritten from 7-stage to 8-stage model with the two-group structure. Should this be done as part of the state machine work, or is it a separate cleanup task?

📝 USER:
Maybe one cleanup pass just before we do state machine work.

✅ **RESOLVED:** New `/projects/{id}/pipeline/status` endpoint created with 8-stage two-group model. Old `/engine/status` kept for backward compat.

---

❓ **Q-E: Old panels cleanup**
V3 Phase 1 TODOs (remove `trace-coverage` + `graph-engine` panels from registry/App.tsx) are unchecked. The `GraphEnginePanel.tsx` component still exists. Should we clean this up as part of Phase 24, or leave it for V3's own TODO list?

📝 USER:
I only know the panel names in the front end -- don't remove but put a flag on the frontend saying "legacy preparing for removal."

✅ **RESOLVED:** `@deprecated` JSDoc + file-level comment added to `GraphEnginePanel.tsx`. Already removed from `panelRegistry.ts`.

---

❓ **Q-F: Settings rebuild approach**
Current state: `config_manager.py` does `json.dumps()` to `ui_config.json`. It works but is brittle (no schema validation, no change events, monolithic writes).

Options for "save on the fly":
1. **Keep JSON + add debounced auto-save** — simplest, add a `save_debounced()` that writes 500ms after last change. Risk: concurrent writes.
2. **SQLite key-value store** — fast, atomic, supports concurrent reads. Python `sqlite3` + Rust `rusqlite` for Tauri. Well-suited for settings.
3. **Tauri Store plugin** (`tauri-plugin-store`) — built-in key-value store for Tauri apps. Automatic persistence. But only accessible from the Tauri frontend, not the Python daemon.

My recommendation: **Option 2 (SQLite)** — works for both the Python daemon and future Tauri app, atomic writes, no data loss on crash, fast. We can use the same DB for all settings (global + per-project).

📝 USER:
Yes option 2 -- if we think option 3 is a good option we can consider it for production but we need a dev workflow for now and the future.

✅ **RESOLVED:** SQLite key-value store. Pending implementation.

---

## Implementation Plan — Progress

> Updated with actual implementation status.

### Phase 1: Backend Alignment (SM-4 + SM-6 Foundation) ✅ DONE

**SM-4: Build Orchestrator** ✅
- [x] `src/codrag/services/build_orchestrator.py` — BuildSlot state machine
- [x] `BuildPhase` enum: `IDLE → QUEUED → RUNNING → COMPLETED → FAILED`
- [x] `BuildSlot` per project per build-type (8 build types)
- [x] Thread monitoring: detect dead threads, transition to `FAILED`
- [x] Listener system for phase transition notifications
- [ ] Refactor existing build endpoints to use orchestrator (incremental)

**SM-6: Pipeline Orchestrator (8-Stage, Two-Group)** ✅
- [x] `src/codrag/services/pipeline_orchestrator.py`
- [x] Two groups: `FastSync` (stages 1-4) and `DeepEnrichment` (stages 5-8)
- [x] Group-level controls: `run_fast_sync()`, `run_deep_enrichment()`, `run_all()`
- [x] Dependency: deep group chains after fast sync via listener
- [x] `WorkerFactory` creates stage workers from core classes directly
- [x] `PipelineRun` tracks per-group progress and per-stage results

**Pipeline API Router** ✅
- [x] `src/codrag/api/routers/pipeline.py` — registered in `server.py`
- [x] `POST /projects/{id}/pipeline/fast` — run stages 1-4
- [x] `POST /projects/{id}/pipeline/deep` — run stages 5-8
- [x] `POST /projects/{id}/pipeline/all` — run all, chaining deep after fast
- [x] `GET /projects/{id}/pipeline/status` — 8-stage two-group status
- [x] `POST /projects/{id}/pipeline/cancel` — cancel a running group

**Frontend Wiring** ✅
- [x] `PipelineStatus` + `PipelineGroupRun` types in `types.ts`
- [x] 5 pipeline methods on `CodragApiClient` in `client.ts`
- [x] `useTraceSystem.ts`: `handleRunFastSync` → `api.runPipelineFast()`
- [x] `useTraceSystem.ts`: `handleRunDeepEnrichment` → `api.runPipelineDeep()`
- [x] `useTraceSystem.ts`: `handleRunAutoPilot` → `api.runPipelineAll()`
- [x] `GraphEnginePanel.tsx` flagged as `@deprecated` (legacy preparing for removal)

**Tests** ✅
- [x] `tests/test_build_orchestrator.py` — 18 tests (lifecycle, progress, cancel, zombie, multi-project, listeners)
- [x] `tests/test_pipeline_orchestrator.py` — 17 tests (sequencing, chaining, failure, cancellation, status)

**Integration Layer** ✅
- [x] `server.py`: Added missing backward-compat wrappers (`_project_augment_status`, `_get_llm_client_for_slot`, `_get_project_*`, `_is_project_*`)
- [x] `pipeline_orchestrator.py`: SSE event bridge emits `task` + `pipeline_status` events on stage transitions
- [x] `config_manager.py`: Added `pipeline_config` block (fast_sync.auto, deep_enrichment.mode/schedule, budgets)
- [x] `feature_gate.py`: STARTER=PRO, added `auto_fast_sync`, `auto_deep_enrichment`, `auto_scope_rebuild` gates
- [x] `useEventStream.ts`: Added `pipeline_status` SSE event handler → `pipelineEvents` state
- [x] `App.tsx`: Destructures `pipelineEvents` from event stream (available for reactive UI updates)

### Phase 2: Knowledge Scope Pipeline (SM-8: File Tree Orchestrator) ✅ DONE

- [x] `src/codrag/services/scope_orchestrator.py` — ScopeOrchestrator singleton
- [x] Track `pending_adds`, `pending_removes`, `pending_changes` from FolderTree changes
- [x] Debounce window (configurable, default 3s, min 500ms)
- [x] Background build in daemon thread with atomic state transitions
- [x] Pro: auto on scope change. Free: marks `STALE`, manual `trigger_rebuild()` button.
- [x] File change detection: `on_files_changed()` queues re-embed for scoped files
- [x] SSE `scope_status` events emitted on state transitions
- [x] `tests/test_scope_orchestrator.py` — 18 tests (lifecycle, debounce, stale, manual trigger, multi-project)

### Phase 3: Settings Persistence ✅ DONE

- [x] `src/codrag/services/settings_store.py` — SQLite key-value store (`codrag_settings.db`)
- [x] Namespaced keys: `global/<key>`, `project/<id>/<key>`
- [x] Auto-migrate from `ui_config.json` on first init (in `server.py configure()`)
- [x] `config_manager.py` bridged: `load_ui_config` reads SQLite first (JSON fallback), `save_ui_config` does dual-write
- [x] `src/codrag/api/routers/settings.py` — Settings REST API:
  - GET/PUT/DELETE `/settings/{key}` (global)
  - GET/PUT/DELETE `/projects/{id}/settings/{key}` (per-project)
  - POST `/settings/pipeline-config` (convenience merge endpoint)
- [x] Listener system for change notifications
- [x] `tests/test_settings_store.py` — 27 tests (CRUD, project, bulk, migration, listeners, concurrency)
- [x] Frontend: `CodragApiClient` + `ApiClient` interface updated with 7 settings methods
- [x] `useTraceSystem.ts`: enrichment auto-config loads from backend on init, saves via `updatePipelineConfig()`, keeps localStorage as fallback

### Phase 4: Tier Gating Integration ✅ DONE

- [x] Simplify `feature_gate.py`: STARTER functions as PRO (unlimited projects, all features)
- [x] Added pipeline-specific gates: `auto_fast_sync`, `auto_deep_enrichment`, `auto_scope_rebuild`
- [x] Watcher `trigger_build` in `projects.py` now checks `auto_fast_sync` gate → uses `pipeline_orchestrator.run_fast_sync()` (Pro) or legacy trace build (Free)

### Phase 5: Frontend Integration ✅ DONE

- [x] SSE `pipeline_status` + `scope_status` events handled in `useEventStream.ts`
- [x] `App.tsx`: destructures `pipelineEvents` + `scopeEvents` from event stream
- [x] `useTraceSystem.ts`: reactive pipeline SSE updates replace polling — running flags, auto-refresh on group completion/failure
- [x] `useTraceSystem.ts`: pipeline status initial hydration on project selection (`getPipelineStatus()`)
- [x] Auto-config persistence wired to backend settings API (replaces localStorage as primary)
- [x] `PipelineStatus` type aligned: flat shape (`fast_sync`/`deep_enrichment` top-level) matches both REST and SSE
- [x] `ScopeStatus` type added to `types.ts`
- [x] Settings API methods (7) + Scope API methods (4) added to `ApiClient` interface + `CodragApiClient` class
- [x] `handleToggleInclude` in `App.tsx` now calls `api.addScopeFiles()` / `api.removeScopeFiles()` → scope orchestrator notified
- [x] `src/codrag/api/routers/scope.py` — Scope REST API: status, add, remove, rebuild. Registered in `server.py`.
- [x] FolderTree stale indicator UI component: added to `FolderTreePanel` and `FileExplorerDetail` (Building/Stale/Pending badges)

### Phase 6: SM-1 Frontend Reducers (Dashboard Refactoring) — In Progress

**Phase A: Decompose useTraceSystem** ✅
- [x] `useEnrichment.ts` (306 lines) — extracted enrichment stages with `enrichmentReducer.ts`
- [x] Self-hydrate: `useTraceSystem` now owns trace status + coverage hydration on project change (was in App.tsx)
- [x] Removed `setTraceStatus` / `setTraceCoverage` from hook return — hook owns its lifecycle, no external setters

**Phase B: Extract Search + Context** ✅ (already done)
- [x] `useSearchContext.ts` (141 lines) — extracted from App.tsx

**Phase C: Extract Project + File System** ✅
- [x] `useProjectManager.ts` (293 lines) — owns projects, selectedProjectId, projectStatuses, buildingProjects, transientCompleteProjects, projectConfig, configDirty, and all CRUD/build/config actions
- [x] Self-hydrates on project change (status + config fetch)
- [x] Auto-selects first project
- [x] `useFileSystem.ts` (373 lines) — already extracted

**Phase D: Simplify useDashboardPanels** — Pending
- [ ] Replace 120+ individual props with domain hook return objects

**Results:**
- `App.tsx`: 771 → 531 lines (−31%)
- `useTraceSystem.ts`: 800 → 552 lines (−31%)
- New `useProjectManager.ts`: 293 lines
- Zero TypeScript errors
