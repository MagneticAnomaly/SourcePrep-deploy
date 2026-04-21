# Phase 48: Fix Pipeline — Comprehensive Audit & Fix Plan

## Overview

The Prep enrichment pipeline has several interrelated bugs causing:
1. **Atlas Building & Continuous Deepening stuck orange** even after multiple runs
2. **Fast Sync reruns from scratch** instead of incrementally processing stale data
3. **Progress bar colors wrong** — green instead of blue/orange during rerun
4. **Deep Enrichment restarts from scratch** instead of processing only new/stale nodes
5. **Auto mode only triggers on startup/project-enable** — not continuously when files change
6. **Deepening never truly "completes"** — settled_ratio thresholds cause perpetual orange

---

## Architecture Summary

### Pipeline Structure (11 stages, 2 groups)

**Fast Sync (stages 1–5):**
| # | Stage ID | Label | Worker | Queue |
|---|----------|-------|--------|-------|
| 1 | `structural` | Structural Graph | TraceBuilder (Rust) | RUST |
| 2 | `inferred_edges` | Edge Discovery | InferredEdgesAnalyzer (LLM) | LLM |
| 3 | `catalogue` | Fast Catalogue | TraceAugmenter (LLM) | LLM |
| 4 | `validation` | Relationship Validation | pass-through (Rust) | RUST |
| 5 | `knowledge` | Knowledge Embedding | KnowledgeIndex.build() | EMBEDDING |

**Deep Enrichment (stages 6–11):**
| # | Stage ID | Label | Worker | Queue |
|---|----------|-------|--------|-------|
| 6 | `enrichment` | Deep Reasoning | EpistemicEnricher (LLM) | LLM |
| 7 | `group_reasoning` | Group Reasoning | GroupReasoningEngine (LLM) | LLM |
| 8 | `clustering` | Module Synthesis | ClusterSynthesizer (LLM) | LLM |
| 9 | `atlas` | Atlas Building | CodebaseAtlas (LLM) | LLM |
| 10 | `deepening` | Continuous Deepening | DeepeningLoop (LLM) | LLM |
| 11 | `deep_knowledge` | Deep Knowledge Embedding | KnowledgeIndex.build() | EMBEDDING |

### Key Files

| File | Role |
|------|------|
| `services/pipeline/orchestrator.py` | Main orchestrator — starts groups, advances stages, chains groups, auto-mode |
| `services/pipeline/stages.py` | Stage definitions, group membership, task/queue mappings |
| `services/pipeline/state_machine.py` | Formal state machine (IDLE→RUNNING→COMPLETED etc.) |
| `services/pipeline/workers.py` | Worker factory — creates callables for each stage |
| `services/pipeline_budget.py` | BudgetThrottle + ScheduleEvaluator for auto/scheduled modes |
| `services/scope_orchestrator.py` | Knowledge Scope rebuild orchestrator (file tree changes) |
| `services/build_orchestrator.py` | Low-level BuildSlot execution (threads, listeners) |
| `api/routers/pipeline.py` | HTTP endpoints + pipeline status assembly |
| `api/routers/projects/watch.py` | Watcher setup — `trigger_build` → `pipeline_orchestrator.run_fast_sync()` |
| `server.py` (configure) | Startup auto-run, schedule evaluator init |
| `core/watcher.py` | AutoRebuildWatcher — debounced file change detection |
| `packages/ui/.../GraphEnrichmentPipeline.tsx` | Frontend pipeline visualization |
| `packages/ui/.../StageProgressBar.tsx` | Progress bar component (normal + rerun modes) |

### How the Pipeline Flows

1. **Manual trigger**: User clicks Run → `POST /pipeline/fast` → `orchestrator.run_fast_sync(pid)`
2. **`_start_group()`**: Creates `PipelineGroupStateMachine`, transitions IDLE→RUNNING, calls `_advance_pipeline()`
3. **`_advance_pipeline()`**: Picks `stages[current_stage_index]`, creates worker via `WorkerFactory`, submits to `BuildOrchestrator.start()`
4. **`_on_build_transition()`**: BuildOrchestrator callback fires when stage COMPLETED/FAILED. Calls `sm.transition(STAGE_COMPLETED)` which increments `current_stage_index`, then calls `_advance_pipeline()` again
5. **Group completion**: When `current_stage_index >= len(stages)`, transitions to COMPLETED
6. **Auto-chain**: If fast_sync completes and auto mode is on, calls `run_deep_enrichment()`
7. **Watcher trigger**: File change → debounce → `trigger_build()` → `pipeline_orchestrator.run_fast_sync()`

---

## Bugs Found

### BUG-1: Atlas stuck orange — `atlas.is_stale()` returns true after pipeline completes

**Symptom**: Atlas Building stage shows orange (stale) clock icon even after successful pipeline run.

**Root cause**: `computeAtlasState()` in the frontend checks `atlas.stale` from the API. The `CodebaseAtlas.is_stale()` method compares the atlas generation timestamp against the trace manifest modification time. After the pipeline runs stages 1–5 (Fast Sync), the trace manifest is updated. When Deep Enrichment then runs stages 6–10, the atlas is generated at stage 9. But stage 10 (deepening) and stage 11 (deep_knowledge) run AFTER atlas — they modify trace files, making the atlas appear stale again relative to those files.

**Location**: 
- `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:247` — `if (atlas.stale) return 'stale'`
- `core/atlas.py` — `is_stale()` method
- `api/routers/pipeline.py:218` — `"stale": atlas.is_stale()`

**Fix**: Atlas should NOT be considered stale if it was generated during the current pipeline run. Either:
- (a) After deepening/deep_knowledge complete, touch the atlas timestamp, OR
- (b) `is_stale()` should compare against trace_nodes.jsonl mtime (not trace_manifest.json which changes on structural rebuild), OR
- (c) Frontend should treat atlas as complete if deepening stage has run (later stages prove atlas ran)

### BUG-2: Continuous Deepening stuck orange — settled_ratio threshold too aggressive

**Symptom**: Deepening shows orange/stale even after running. Screenshot shows "73% settled · avg 56%".

**Root cause**: `computeDeepeningState()` returns `'stale'` when `settled_ratio >= 0.5` but `< 0.90`. A 73% settled ratio is treated as stale. This is by design but misleading — 73% is actually a good result for a first deepening pass. The 90% "complete" threshold is nearly impossible to reach in a single pass (the DeepeningLoop only does `max_iterations=10` with `batch_size=20`).

**Location**: 
- `GraphEnrichmentPipeline.tsx:265-267`:
  ```
  if (deep.settled_ratio >= 0.90) return 'complete';
  if (deep.settled_ratio >= 0.5) return 'stale';
  return 'warning';
  ```

**Fix**: Lower the "complete" threshold to 0.70 (or even 0.50) since:
- The DeepeningLoop processes only 20 nodes per iteration × 10 iterations = 200 nodes max
- With 661 enriched nodes, convergence to 90% in a single pass is impossible
- OR: Show "complete" if the deepening stage ran successfully (regardless of ratio) and treat ratio as informational only

### BUG-3: Watcher triggers only `run_fast_sync()` — never triggers deep enrichment continuously

**Symptom**: Auto mode only runs pipeline on startup/project-enable. File changes trigger Fast Sync but NOT Deep Enrichment continuously.

**Root cause**: The watcher's `trigger_build()` callback in `watch.py:117` calls `pipeline_orchestrator.run_fast_sync(proj.id)` — it does NOT call `run_all()`. So file changes only trigger Fast Sync. Deep Enrichment auto-chaining relies on `_is_deep_enrichment_auto()` being true AND the fast_sync completing, which does chain correctly. BUT there's a critical issue: **after the initial run completes, the watcher doesn't re-trigger the pipeline for subsequent file changes that make the graph stale**.

The watcher calls `run_fast_sync()` which rebuilds the structural graph. After fast sync completes, `_advance_pipeline` checks `_is_deep_enrichment_auto()` and chains deep enrichment. This SHOULD work for continuous mode. The real problem is likely that the pipeline status remains `"completed"` from the previous run, and `_start_group()` creates a NEW state machine each time (line 240), so stale state from previous runs shouldn't block it.

**ACTUAL ROOT CAUSE**: The watcher's `trigger_build()` at `watch.py:106` triggers BOTH a legacy `_start_project_build()` AND `pipeline_orchestrator.run_fast_sync()`. The legacy build competes with the pipeline's structural stage. If the legacy build is already running when the pipeline tries to start its structural stage via BuildOrchestrator, the stage fails or gets stuck.

**Location**: `api/routers/projects/watch.py:82-124`

**Fix**: The watcher should ONLY trigger the pipeline orchestrator when trace is enabled, NOT also trigger the legacy `_start_project_build()`. The pipeline's structural stage handles the trace build internally, and the knowledge stage handles embedding.

### BUG-4: Fast Sync reruns from scratch instead of incrementally

**Symptom**: When manually re-running Fast Sync, stage 2 (Edge Discovery / catalogue) appears to redo everything from scratch instead of skipping already-processed nodes.

**Root cause**: The `TraceAugmenter.run()` and `InferredEdgesAnalyzer.run()` workers DO support incremental processing (they check existing augmented/inferred data and skip). But the `TraceBuilder.build()` in stage 1 does a FULL rebuild every time — it doesn't do incremental trace builds. This means every trace node gets new timestamps, which makes downstream stages think everything is "new".

Additionally, the progress reporting may be confusing: even in incremental mode, the augmenter iterates ALL nodes (to check which need work), so the progress bar shows total nodes, not just stale ones. This makes it LOOK like it's redoing everything even when it's mostly skipping.

**Location**: `workers.py:223-258` (trace worker always does full rebuild)

**Fix**: 
- (a) TraceBuilder already supports incremental via hash comparison in `trace_manifest.json`. Verify it's actually being used.
- (b) The progress callback should report "N new + M stale / T total" so the UI can show accurate rerun progress.

### BUG-5: Progress bar shows green instead of blue/orange during rerun

**Symptom**: During a rerun, the progress bar shows green (success color) instead of the expected blue (in-progress) + orange (stale).

**Root cause**: The rerun bi-color bar logic in `GraphEnrichmentPipeline.tsx:741-744` correctly computes `staleRerun` from `staleCounts`, BUT the `staleCounts` prop may not be populated. Looking at how this prop is wired:

The `staleCounts` prop needs to come from the pipeline status API. The `StageProgressBar` uses `bg-success` (green) for the "done" portion and `bg-orange-500` for the stale portion. But if `staleCounts` is undefined/null, the `isTraceRerun` flag is false, and the normal (non-rerun) progress bar is shown, which uses `color="bg-blue-500"`.

The real issue: when a stage IS running and shows a progress bar, the code at line 430-435 renders `StageProgressBar` with `color="bg-blue-500"` and `rerun={hasRerun ? stage.rerun : undefined}`. The rerun data flows from `staleRerun` → only applied to stages with `state === 'running'` in the `finalFastStages` map (line 743). This means the rerun coloring ONLY works when `staleCounts` is properly provided AND the stage is running.

**The bug**: The `staleCounts` prop is likely not being provided by the parent component (`App.tsx` / `useDashboardPanels`). Need to verify how it's wired.

**Location**: 
- `GraphEnrichmentPipeline.tsx:523-528` — staleRerun computation
- `GraphEnrichmentPipeline.tsx:741-744` — finalFastStages rerun application
- Need to check `useDashboardPanels.tsx` and `App.tsx` for `staleCounts` wiring

### BUG-6: Auto mode has no continuous re-trigger mechanism

**Symptom**: Auto mode triggers once on startup and once when watcher fires, but doesn't continuously re-run when there's stale data.

**Root cause**: The architecture has three auto-trigger points:
1. **Startup** (`server.py:596-699`): Checks `fast_auto` + `deep_mode` and runs pipeline once
2. **Watcher** (`watch.py:114-117`): File changes → `run_fast_sync()` → auto-chains deep if configured
3. **Schedule evaluator** (`pipeline_budget.py:195-264`): Only triggers for `scheduled` mode, NOT `auto` mode

For **continuous auto mode**, the intended flow is:
- Watcher detects file change → triggers `run_fast_sync()`
- Fast sync completes → auto-chains `run_deep_enrichment()` 
- Deep enrichment completes → ??? (nothing re-triggers deepening for remaining unsettled nodes)

**Missing piece**: After deep enrichment completes and there are still unsettled nodes (settled_ratio < target), there is NO mechanism to re-trigger another deepening pass. The `DeepeningLoop` does `max_iterations=10` internally, but once the pipeline group completes, it's done. There's no "keep going until converged" loop at the orchestrator level.

Similarly, after the pipeline fully completes, if more files change, the watcher correctly fires again. But if NO files change and the graph just needs more deepening passes, nothing triggers a re-run.

**Fix**: Add a post-completion hook in the orchestrator that checks if:
- Deep enrichment just completed AND auto mode is on
- Deepening settled_ratio is below target (e.g., 0.70)
- Re-trigger `run_deep_enrichment()` with a backoff delay

### BUG-7: `deep_knowledge` stage shares the same `KnowledgeEmbeddingStatus` as `knowledge` stage

**Symptom**: Deep Knowledge Embedding (stage 11) shows the same chunk count as Knowledge Embedding (stage 5). The green checkmark on stage 5 may appear because of stage 11's data.

**Root cause**: In `pipeline.py:268`:
```python
"deep_knowledge": knowledge_status,  # Same index, re-built with richer data
```
Both stages share the exact same `knowledge_status` object. The frontend's `computeDeepKnowledgeState()` at line 300 tries to distinguish via `know?.deep_chunks_embedded`, but `deep_chunks_embedded` may not exist on the status object.

**Location**: `api/routers/pipeline.py:268`

**Fix**: Either:
- (a) Add a `deep_chunks_embedded` field to the knowledge index status, OR
- (b) Track stage 5 vs stage 11 completion separately in the pipeline state

### BUG-8: Duplicate log messages — every log line appears twice

**Symptom**: Every augmentation progress line appears twice in the Process Logs panel:
```
INFO [prep.core.augmenter] Augmentation progress: 2325/13153 (18%) — avg 28.2s/item
INFO [prep.core.augmenter] Augmentation progress: 2325/13153 (18%) — avg 28.2s/item
INFO [prep.services.pipeline.workers] [Haley/Fast Catalogue] augment_symbols (2325/13153 — 18%)
INFO [prep.services.pipeline.workers] [Haley/Fast Catalogue] augment_symbols (2325/13153 — 18%)
```

**Root cause**: Two independent logging chains fire for the same event:
1. The augmenter itself logs at `augmenter.py:1265-1268` inside its progress loop (`logger.info("Augmentation progress: ...")`)
2. The `_logged_progress` wrapper at `workers.py:234-240` wraps the progress callback and ALSO emits `logger.info("[Haley/Fast Catalogue] ...")` for every progress tick

This produces 2 log lines per tick. But the user is seeing **4 lines** (each pair duplicated), which means there may also be a double-handler on the Python logger (e.g., root logger + module logger both attached, or uvicorn's log config duplicating handlers).

**Location**:
- `core/augmenter.py:1265-1268` — augmenter's own `logger.info()` in the progress loop
- `services/pipeline/workers.py:234-240` — `_logged_progress` wrapper also calls `logger.info()`
- Possibly `server.py` or uvicorn config — duplicate log handler attachment

**Fix**: 
- (a) Remove the `logger.info()` calls from inside the augmenter's progress loop — let `_logged_progress` be the single source of progress logging
- (b) Audit Python logging config for duplicate handlers (root logger + named logger both writing to same output)

### BUG-9: Augmenter processes 13153 items when only 3739 files exist

**Symptom**: The Graph Scope panel shows 3739 files, but the augmenter reports `0/13153 nodes enriched` and processes 13153 items. This makes the pipeline appear to be doing 3.5x more work than expected.

**Root cause**: The augmenter processes **all trace nodes** — both `kind=file` nodes (3739) AND `kind=symbol` nodes (~9414). The `total_work` at `augmenter.py:1187` is computed as:
```python
total_work = len(to_augment_symbols) + len(to_augment_files)
```
This is architecturally correct — symbols need augmentation too (each function/class/method gets a summary). But the UI is misleading because:
1. Graph Scope shows "0/3739 files traced" — counting only files
2. The pipeline status API reports `0/13153 nodes enriched` — counting symbols + files
3. The user sees a 3.5x discrepancy with no explanation

**Location**:
- `core/augmenter.py:1180-1187` — symbol + file node counting
- `api/routers/pipeline.py` — status endpoint reports total_nodes (symbols + files)
- Graph Scope panel — shows file count only

**Fix**:
- (a) Pipeline status should report `files_to_process` AND `symbols_to_process` separately so the UI can show "3739 files + 9414 symbols = 13153 items"
- (b) The progress message should say "augment_symbols (2325/9414)" during Pass 1 and "augment_files (150/3739)" during Pass 2, not a combined counter
- (c) Graph Scope should show a breakdown: "3739 files · 9414 symbols" instead of just "13153 nodes"

### BUG-10: Queue (3739 items) doesn't clear when pipeline starts processing

**Symptom**: The "Queue 3739" badge in Graph Scope remains at 3739 even while the pipeline is actively processing. Previously, items cleared from the queue as they were processed.

**Root cause**: The "Queue" tab in Graph Scope shows **untraced files** from the trace coverage API (`GET /projects/{id}/trace/coverage`). This is NOT the pipeline's work queue — it's a separate concept. The trace coverage shows files that haven't been indexed into the trace graph yet. Once the Structural Graph stage (stage 1) completes, these files ARE traced. But the coverage API may not refresh during the pipeline run, or the frontend polls it too infrequently.

Additionally, during stage 3 (Fast Catalogue / augmentation), the trace graph already exists — the queue should have already cleared after stage 1 completed. If it hasn't, either:
1. The trace coverage endpoint isn't being re-fetched between stages
2. The structural stage didn't actually trace all 3739 files (some may have been excluded)

**Location**:
- Graph Scope panel — polls `GET /projects/{id}/trace/coverage`
- `core/trace.py` — `compute_trace_coverage()` computes traced vs untraced

**Fix**:
- (a) After Structural Graph stage completes, emit an SSE event that tells the frontend to refresh trace coverage
- (b) Verify that the trace builder actually processes all 3739 files (check exclude globs)
- (c) Consider merging the "Queue" concept with pipeline progress so the user sees one unified view

### BUG-11: Structural Graph stuck on "Completing..." while later stages are running

**Symptom**: After Edge Discovery and Fast Catalogue are actively running, the Structural Graph stage still shows "Completing..." instead of showing its actual node/edge counts.

**Root cause**: `computeTraceState()` at `GraphEnrichmentPipeline.tsx:127` correctly returns `'complete'` when later stages are running. But `structuralStats` at line 565 shows "Completing..." when:
```typescript
if (trace.counts.nodes === 0 && (inferredEdgesRunning || augmenting || ...))
  return 'Completing...';
```
This means `trace.counts.nodes === 0` — the frontend hasn't received the updated trace counts yet. The trace status API returns 0 nodes because:
1. The trace index was rebuilt by stage 1 but the in-memory cache wasn't refreshed
2. The `/trace/status` endpoint reads from a stale `TraceIndex` instance
3. The build_manager's `project_trace_indexes[project_id]` was updated by the worker, but the status endpoint may be reading from a different TraceIndex instance

**Location**:
- `GraphEnrichmentPipeline.tsx:565` — "Completing..." condition
- `services/pipeline/workers.py:272-274` — worker updates `build_manager.project_trace_indexes`
- The trace status API endpoint that returns `counts.nodes`

**Fix**:
- (a) After the structural worker stores the new TraceIndex in build_manager, emit an SSE event with the actual node/edge counts so the frontend updates immediately
- (b) The trace status endpoint should always read from `build_manager.project_trace_indexes` (the fresh instance) rather than creating a new TraceIndex from disk
- (c) Remove the "Completing..." fallback — if the state is `complete`, show "Loading counts..." or just the green checkmark without stats until counts arrive

### BUG-12: "No model configured for inferred_edges" warning then stage runs anyway

**Symptom**: On pipeline startup, the orchestrator emits:
```
WARNING ModelAwareness: no model configured for task inferred_edges (stage inferred_edges) — falling back to legacy VRAM lifecycle
```
Then the stage proceeds to run with the correct model.

**Root cause**: The `ModelAwareness` VRAM lifecycle system (separate from the `WorkerFactory`) tries to pre-load the model for the upcoming stage. It resolves the task→model mapping via `_get_model_identity_for_task("inferred_edges")`. If the mapping fails (e.g., no model explicitly assigned to the `inferred_edges` task in mapped mode, or the `code_model` slot isn't configured in structured mode), it logs a warning and falls back to "legacy VRAM lifecycle" (no pre-loading). The stage's **worker** then independently resolves the model via `_get_llm_client_for_task("inferred_edges")` which has different fallback logic (code→small→fail) and succeeds.

**Location**:
- `services/pipeline/orchestrator.py` — `ModelAwareness` pre-load logic
- `services/pipeline/workers.py:310` — `_get_llm_client_for_task("inferred_edges")`
- `server.py` — `_get_model_identity_for_task()` vs `_get_llm_client_for_task()`

**Fix**: 
- (a) `_get_model_identity_for_task()` should use the same fallback chain as `_get_llm_client_for_task()` (code→small)
- (b) Or demote the warning to DEBUG level since the worker handles the fallback correctly

### BUG-13: Pause/Resume completely broken — all stages turn orange, resume doesn't actually resume

**Symptom**: Three interrelated problems:
1. **All stages turn orange on pause**: Pressing pause turns ALL stage rows orange with "Paused" text, not just the running stage. Completed stages (Structural Graph, Edge Discovery) that already have green checkmarks should keep their green state.
2. **Resume doesn't resume**: Pressing Resume marks the previously-running stage as broken (orange) and weirdly shows the NEXT stage as complete. The pipeline does NOT actually continue running — it shows the "Run" button instead.
3. **After resume, pipeline state is inconsistent**: The state machine was replaced with a brand new one, losing all stage_results history.

**Root causes (3 separate bugs):**

**(a) Frontend: `isPaused` applied to ALL stage rows (not just the paused one)**

In `GraphEnrichmentPipeline.tsx:871-877`, Fast Sync stages pass `isPaused={fastPaused}` to **every** `StageRow`. When `fastPaused=true`, all 5 stages render as paused (orange). The Deep Enrichment group already had the correct per-stage logic (lines 937-946) — Fast Sync was missing it.

**(b) Backend: `resume_paused()` creates a brand new state machine instead of resuming the existing one**

`resume_paused()` called `_start_group()` which creates a **new** `PipelineGroupStateMachine` (line 324). The old PAUSED SM was discarded. The new SM:
- Starts from IDLE→RUNNING (not PAUSED→RUNNING)
- Loses `stage_results` (which stages were already completed)
- Loses progress tracking from the old run
- Creates a new journal entry instead of continuing the old one

The check at `_start_group:311` — `if existing and existing.is_active: return False` — doesn't block this because PAUSED is NOT in `ACTIVE_STATES`.

**(c) Backend: `_on_build_transition` race condition with pause**

`_pause_group()` signals the worker to stop (line 779) then **immediately** transitions to PAUSED (line 784) without waiting. When the worker eventually raises `PipelinePausedError`, the FAILED callback fires but:
1. The matching loop at line 594 only finds `is_active` runs — PAUSED runs were invisible
2. The intercept at line 667 only checked `state == PAUSING` — missed the PAUSED case

**Location**:
- `GraphEnrichmentPipeline.tsx:871-877` — `isPaused={fastPaused}` on all fast stages
- `orchestrator.py:194-225` — `resume_paused()` implementation
- `orchestrator.py:589-598` — `_on_build_transition` matching loop
- `orchestrator.py:663-669` — PAUSING intercept for FAILED callbacks

**Fix (all three applied)**:
- (a) Frontend: Compute `isStagePaused` per-stage for Fast Sync (matches existing Deep pattern)
- (b) Backend: `resume_paused()` now uses `Event.RESUME` on the existing SM instead of creating a new one
- (c) Backend: `_on_build_transition` matching loop now includes PAUSED runs; FAILED intercept checks both PAUSING and PAUSED states

### BUG-15: `force_reset_stale_runs` skips stages 3-5 while augmenter is actively running

**Symptom**: After Edge Discovery completes and Fast Catalogue starts, the pipeline rapidly "completes" stages 3, 4, and 5 without actually running them. Logs show:
```
Force-resetting stale pipeline .../fast_sync (stuck at stage catalogue for 1760s)
Pipeline .../fast_sync: running → running (event=stage_completed, stage_idx=3)
Force-resetting stale pipeline .../fast_sync (stuck at stage validation for 1760s)
Pipeline .../fast_sync: running → running (event=stage_completed, stage_idx=4)
Force-resetting stale pipeline .../fast_sync (stuck at stage knowledge for 1763s)
Pipeline .../fast_sync: running → running (event=stage_completed, stage_idx=5)
```
The augmenter IS actively running in its worker thread (processing items at 33s/item) but the state machine has already been force-advanced past it.

**Root cause**: `force_reset_stale_runs()` checks `run.started_at` (when the **group** started, not when the current stage started) against a 600-second timeout. For a large repo where stages 1-2 take 30+ minutes, by the time stage 3 starts, `elapsed = now - started_at` is already 1760s — far exceeding the 600s limit. The function then fires `STAGE_COMPLETED` repeatedly, force-advancing through all remaining stages.

Critically, it **never checks whether the build slot is actually idle/stuck**. The augmenter worker IS actively running in its build slot, but `force_reset_stale_runs` doesn't look at the slot — it only checks the SM's `started_at`.

**Location**:
- `orchestrator.py:256-307` — `force_reset_stale_runs()` uses group `started_at` not stage timing
- `watch.py:152-161` — watcher calls `force_reset_stale_runs()` when `started_at > 600s`

**Fix (applied)**: `force_reset_stale_runs()` now checks the **actual build slot status** for the current stage. If `slot.phase == RUNNING` or `QUEUED`, the pipeline is NOT stuck — the worker is just slow (normal for large repos). Only resets if the build slot is IDLE/COMPLETED/FAILED but the SM still thinks the pipeline is running (meaning the completion callback was lost). Also changed from force-completing stages to `STAGE_FAILED` transition for proper error state.

### BUG-14: Pipeline always restarts from stage 1 — loses checkpoint progress, re-runs completed stages

**Symptom**: After pausing at 18% of stage 3 (Fast Catalogue), refreshing the page or restarting the app, then clicking "Run":
1. The UI shows stages 1-2 as complete (green checkmarks) with correct stats
2. Clicking Run restarts from stage 1 (Structural Graph) instead of stage 3
3. Stage 2 (Edge Discovery) which was fully complete gets re-run from scratch
4. The 18% augmentation checkpoint (~2,400 items) is lost because stage 1's full rebuild changes file hashes

**Root causes (2 separate issues):**

**(a) Pipeline state is entirely in-memory — lost on restart**

The orchestrator's `_runs` dict (mapping `(project_id, group)` → `PipelineGroupStateMachine`) is a plain Python dict. When the server restarts, ALL pipeline state is lost — which stages completed, which is paused, progress counters, etc. The UI has nothing to hydrate from.

**(b) `run_fast_sync()` always starts from stage 0 — never checks disk**

When `run_fast_sync()` is called (from the Run button or server startup), it calls `_start_group()` which creates a brand new SM starting from `current_stage_index=0`. It never checks whether stages 1-2 already have completed output on disk. This means every Run starts from scratch even if previous stages completed successfully.

**(c) Stage 1 (TraceBuilder) full rebuild invalidates downstream checkpoints**

Even though the augmenter uses file hash comparison (not timestamps) for staleness detection, a full trace rebuild can change node IDs. If a node's ID changes, the augmenter treats it as a "new" node even though the file content is identical. This effectively invalidates the checkpoint data.

**Location**:
- `orchestrator.py:93-95` — `run_fast_sync()` always starts from stage 0
- `orchestrator.py:368-410` — `_start_group()` creates new SM with `resume_from=0`
- `orchestrator.py:64` — `_runs` dict is in-memory only

**Fix (applied)**:
- (a) Added `_detect_resume_point(project_id, stages)` — checks manifest files on disk to determine which stages already completed. Uses manifest mtime vs structural trace mtime for staleness (if trace was rebuilt after a downstream stage completed, that stage re-runs).
- (b) `run_fast_sync()` and `run_deep_enrichment()` now call `_detect_resume_point()` to auto-skip completed stages. Added `force_from_start=True` parameter for when files actually changed (watcher triggers).
- (c) Watcher's `trigger_build()` passes `force_from_start=True` (files changed → rebuild everything). Manual Run button uses auto-detect (skip completed stages).

**How it works for the user's specific case**:
- `.runprep/trace_manifest.json` exists → stage 1 (structural) completed
- `.runprep/trace_inferred_manifest.json` exists AND newer than trace_manifest → stage 2 (edges) completed  
- `.runprep/trace_augment_manifest.json` exists BUT older than trace_manifest → stage 3 (catalogue) needs to re-run
- Clicking Run starts from stage 3, augmenter loads existing `trace_augmented.jsonl` (18% checkpoint), skips already-done nodes

---

## How Pipeline SHOULD Work — Detailed Specification

This section describes the **intended behavior** of every pipeline stage, including what data flows between stages, how the UI should update at each transition, what SSE events fire, and what the user should see at every step.

### Overall Flow Principles

1. **Sequential within groups**: Stages within a group (Fast Sync or Deep Enrichment) run strictly one at a time, in order. Stage N+1 cannot start until Stage N completes.
2. **Incremental by default**: Every LLM-based stage checks for existing data and skips already-processed items. Only new or stale items are processed.
3. **Atomic writes**: Each stage writes its output atomically (write to temp, rename). Crashes during a stage don't corrupt previous data.
4. **Checkpoint saves**: Long-running stages (augmentation, epistemic) save checkpoints every N items so crash recovery doesn't lose progress.
5. **Single log line per event**: Each progress tick should produce exactly ONE log line, not duplicates.

### Trigger Points

| Trigger | What Runs | Condition |
|---------|-----------|-----------|
| User clicks "Run" on Fast Sync | Stages 1-5 | Always |
| User clicks "Run" on Deep Enrichment | Stages 6-11 | Fast Sync must have completed at least once |
| Watcher detects file change | Fast Sync (1-5), then optionally Deep (6-11) | `fast_auto=true`; deep chains if `deep_mode="auto"` |
| Server startup | Fast Sync + Deep | `fast_auto=true` AND project has stale/incomplete data |
| Schedule evaluator tick | Deep Enrichment (6-11) | `deep_mode="scheduled"` AND interval elapsed or threshold exceeded |
| Deepening re-trigger | Deep Enrichment (6-11) | `deep_mode="auto"` AND settled_ratio < 0.70 after previous deep run |

### Stage-by-Stage Specification

#### Stage 1: Structural Graph (Rust)

**Purpose**: Parse all included source files using tree-sitter, extract symbols (functions, classes, methods, types), and build the trace graph (nodes + edges representing imports, calls, contains relationships).

**Input**: 
- Project path + include/exclude globs from project config
- `max_file_bytes`, `hard_limit_bytes`, `max_files`, `max_nodes`, `max_edges` from UI config

**Worker**: `WorkerFactory._trace_worker()` → `TraceBuilder.build()`

**Output files written** (to project index dir):
- `trace_nodes.jsonl` — one JSON object per node (file nodes + symbol nodes)
- `trace_edges.jsonl` — one JSON object per edge (imports, calls, contains)
- `trace_manifest.json` — metadata: file hashes, timestamp, node/edge counts

**What happens**:
1. Worker reads include/exclude globs from project config and UI config
2. `TraceBuilder` walks the project directory, filtering by globs
3. For each included file, tree-sitter parses it and extracts symbols
4. Nodes and edges are written to JSONL files
5. Worker stores the new `TraceIndex` in `build_manager.project_trace_indexes[project_id]`
6. Worker returns `{stage: "structural", nodes: N}`

**UI update on completion**:
- SSE event: `pipeline_stage_complete` with `{stage: "structural", nodes: N, edges: M}`
- Frontend: `computeTraceState()` returns `'complete'`
- Structural Graph row: green checkmark icon, stats show "N nodes - M edges"
- Graph Scope panel: "Queue" should drop to 0 (all files are now traced), "traced & embedded" counter updates
- Next stage (Edge Discovery) row: transitions from "Waiting for graph" to running state

**What can go wrong**:
- If globs are wrong, too many or too few files get traced (BUG-9 related)
- If TraceIndex isn't stored in build_manager, status endpoint returns stale 0 counts (BUG-11)

#### Stage 2: Edge Discovery (LLM — Code slot)

**Purpose**: Use an LLM to discover cross-file relationships that tree-sitter can't detect (dynamic dispatch, config-driven wiring, framework magic).

**Input**:
- `trace_nodes.jsonl` + `trace_edges.jsonl` from Stage 1
- LLM client resolved via `_get_llm_client_for_task("inferred_edges")` — prefers code_model, falls back to small_model

**Worker**: `WorkerFactory._inferred_edges_worker()` → `InferredEdgesAnalyzer.run()`

**Output files written**:
- `trace_inferred_edges.jsonl` — discovered edges with `origin: "inferred"` field

**What happens**:
1. Worker resolves LLM client (code → small fallback)
2. If no model available, stage is SKIPPED (returns `{skipped: true, reason: "no_llm"}`)
3. `InferredEdgesAnalyzer` loads existing inferred edges and file list
4. For each file not yet analyzed, sends file content + symbol info to LLM
5. LLM returns discovered edges (e.g., "function A calls function B via dynamic dispatch")
6. Edges above confidence threshold are written to JSONL
7. Progress callback fires per file: `("discover_edges", current, total)`

**UI update on completion**:
- SSE event: `pipeline_stage_complete` with `{stage: "inferred_edges", edges_written: N}`
- Edge Discovery row: green checkmark, stats show "N edges discovered"
- If skipped: grey dash icon, stats show "Skipped (no LLM)"
- Next stage (Fast Catalogue) transitions to running state

**What can go wrong**:
- ModelAwareness warning fires even when worker resolves correctly (BUG-12)
- If the code_model slot isn't configured, stage skips — this is fine but the warning is confusing

#### Stage 3: Fast Catalogue (LLM — Fast slot)

**Purpose**: Generate a summary, role classification, and confidence score for every trace node (symbols AND files). This is the primary "understanding" pass.

**Input**:
- `trace_nodes.jsonl` + `trace_edges.jsonl` from Stage 1
- `trace_inferred_edges.jsonl` from Stage 2 (merged into edge set)
- `trace_augmentations.jsonl` — existing augmentation data (for incremental skipping)
- `trace_manifest.json` — file hashes (for staleness detection)
- LLM client via `_get_llm_client_for_task("catalogue")`

**Worker**: `WorkerFactory._augment_worker()` → `TraceAugmenter.run()`

**Output files written**:
- `trace_augmentations.jsonl` — one `AugmentationEntry` per node (summary, role, confidence, etc.)
- `trace_augment_manifest.json` — metadata: counts, duration, model info

**What happens**:
1. Loads all trace nodes and separates into symbol nodes + file nodes
2. Loads existing augmentations and file hashes
3. Filters to nodes needing augmentation: `_needs_augmentation()` checks if node is new (not in existing) or stale (file hash changed since last augment)
4. `total_work = len(to_augment_symbols) + len(to_augment_files)` — this is symbols + files, NOT just files
5. Pre-flight LLM test: sends a tiny prompt to verify model is responding
6. **Pass 1 — Symbol augmentation**: Iterates all symbols needing augmentation. For each: sends symbol name, file context, imports to LLM. Gets back summary, role, confidence. Progress: `("augment_symbols", done, total_work)`
7. **Pass 2 — File augmentation**: Iterates all files needing augmentation. For cloud models with batching enabled, sends multiple files per API call. Progress: `("augment_files", done, total_work)`
8. Writes augmentations atomically
9. Checkpoints every N items to prevent data loss on crash

**UI update during processing**:
- Fast Catalogue row: spinning icon, blue progress bar, percentage shown
- Stats: "N% · augment_symbols" or "N% · augment_files"
- Progress callback fires every item — frontend receives via SSE `pipeline_progress` event

**UI update on completion**:
- SSE event: `pipeline_stage_complete` with `{stage: "catalogue", augmented: N, total_nodes: T}`
- Fast Catalogue row: green checkmark, stats show "N nodes catalogued"
- Graph Scope: "N/T nodes enriched" counter updates, enrichment progress bar fills

**What can go wrong**:
- total_work includes symbols+files but UI only shows file count (BUG-9)
- Progress logs appear twice due to augmenter + _logged_progress both logging (BUG-8)
- Queue doesn't clear because Graph Scope polls trace coverage, not augmentation status (BUG-10)
- Takes extremely long on large repos (13K+ items at 28s/item = 100+ hours)

#### Stage 4: Relationship Validation (Rust)

**Purpose**: Re-validate the trace graph after augmentation. Ensures edge integrity, removes dangling references, updates edge weights based on augmentation confidence scores.

**Input**: All trace files + augmentations from stages 1-3

**Worker**: `WorkerFactory._validation_worker()` — pass-through or lightweight Rust validation

**Output**: Updated edge data if needed; mostly a consistency check

**UI update on completion**:
- Relationship Validation row: green checkmark
- Stats: brief summary or "Validated"

#### Stage 5: Knowledge Embedding (EMBEDDING queue)

**Purpose**: Build the searchable vector index from augmented trace data. This creates `documents.json` + `embeddings.npy` that the `/context` search endpoint requires.

**Input**: `trace_nodes.jsonl` + `trace_augmentations.jsonl` + file contents

**Worker**: `WorkerFactory._knowledge_worker()` → `build_manager.start_project_build()`

**Output files written**:
- `documents.json` — chunk metadata (file path, content, augmentation summary)
- `embeddings.npy` — dense vectors from the embedding model
- `knowledge_documents.json` + `knowledge_embeddings.npy` — knowledge index variant

**UI update on completion**:
- Knowledge Embedding row: green checkmark
- Fast Sync group: "Running..." badge changes to nothing (all 5 stages complete)
- Index Health panel: updates with chunk count, file count, health score
- The project is now searchable via `/context` endpoint and MCP tools
- If auto-chain is enabled: Deep Enrichment automatically starts (see below)

**Auto-chain handoff**:
After all 5 Fast Sync stages complete, the orchestrator checks:
1. Is `_chain_deep[project_id]` set? (explicit request to chain) → `run_deep_enrichment()`
2. Is `_is_deep_enrichment_auto()` true? (auto mode) → `run_deep_enrichment()`
3. Neither → pipeline group transitions to COMPLETED, done.

#### Stages 6-11: Deep Enrichment

These stages follow the same pattern: sequential execution, incremental processing, SSE updates.

| Stage | Purpose | Key Detail |
|-------|---------|------------|
| 6: Deep Reasoning | Multi-hop reasoning about each node using graph context | Reads neighbors from trace graph, reasons about role in larger architecture |
| 7: Group Reasoning | Reasons about groups of related nodes together | Uses connected components from trace graph |
| 8: Module Synthesis | Groups enriched nodes into semantic modules | Uses domain tags + connected components clustering |
| 9: Atlas Building | Generates architectural overview of the codebase | Uses module info to build segment descriptors + routing index |
| 10: Continuous Deepening | Re-processes nodes that changed or have low confidence | Iterates max 10x with batch of 20, computes settled_ratio |
| 11: Deep Knowledge Embedding | Rebuilds knowledge index with enriched data | Same as Stage 5 but with richer augmentation data |

### UI State Machine for Each Stage Row

Each stage row in the Graph Enrichment panel can be in one of these visual states:

| State | Icon | Progress Bar | Stats Text | Trigger |
|-------|------|-------------|------------|---------|
| `disabled` | grey circle | none | "Waiting for [dependency]" | Previous stage hasn't completed |
| `not_built` | grey circle | none | "Ready to [action]" | Previous stage complete, this stage never ran |
| `running` | spinning circle | blue bar + percentage | "N/M items - message" | Stage is actively processing |
| `complete` | green checkmark | none | "N items - summary" | Stage finished successfully |
| `stale` | orange clock | none | "N items - needs update" | Stage completed previously but data is stale |
| `warning` | yellow triangle | none | "N items - quality issue" | Stage completed but quality metrics are low |
| `error` | red X | none | "Failed: reason" | Stage threw an exception |

**Transition rules**:
- `disabled` → `running`: When the orchestrator starts this stage (previous stage just completed)
- `running` → `complete`: When `_on_build_transition(COMPLETED)` fires for this stage
- `running` → `error`: When `_on_build_transition(FAILED)` fires
- `complete` → `stale`: When underlying data changes (e.g., files modified after augmentation)
- Any → `running`: When pipeline re-runs this stage

### SSE Events

The pipeline communicates state changes to the frontend via Server-Sent Events:

| Event Type | Payload | When |
|------------|---------|------|
| `pipeline_started` | `{project_id, group, stages}` | Group starts (fast_sync or deep_enrichment) |
| `pipeline_progress` | `{project_id, stage, current, total, message}` | Worker progress callback fires |
| `pipeline_stage_complete` | `{project_id, stage, result}` | Stage worker returns successfully |
| `pipeline_stage_failed` | `{project_id, stage, error}` | Stage worker throws exception |
| `pipeline_complete` | `{project_id, group}` | All stages in group finished |
| `pipeline_paused` | `{project_id, group}` | User paused the pipeline |

**Frontend SSE handling**:
- `useEnrichment.ts` / `enrichmentReducer.ts` processes these events
- Each event updates the corresponding stage's state in the React state tree
- The `GraphEnrichmentPipeline` component re-renders with new state

### What "Completing..." Should Mean vs What It Means Now

**Should mean**: Stage is in its final write phase (writing output files, flushing checkpoint). Brief, <5 second state.

**Currently means**: Stage is marked complete by the orchestrator BUT the frontend hasn't received updated counts yet. `trace.counts.nodes === 0` because the trace status API returns stale data. This is BUG-11 — the "Completing..." text is a workaround for stale API data, not a real stage state.

### Expected Timing (Apple Silicon, Local LLM)

For a ~3700 file codebase with qwen3:8b on local Ollama:

| Stage | Expected Duration | Items | Per-Item |
|-------|-------------------|-------|----------|
| 1: Structural Graph | 5-30 seconds | 3739 files | <10ms/file (Rust) |
| 2: Edge Discovery | 30-120 minutes | 3739 files | 2-5s/file (LLM) |
| 3: Fast Catalogue | 4-8 hours | ~13000 nodes | 1-2s/node (LLM) |
| 4: Validation | <5 seconds | — | — |
| 5: Knowledge Embedding | 30-120 seconds | — | — |
| 6-11: Deep Enrichment | 2-6 hours | varies | varies |

If Stage 3 is taking 28s/item (as reported), that's ~10x slower than expected. Possible causes:
- Model is too large for the hardware (swapping)  (not possible on Apple hardware)
- Exclude globs aren't applied → processing node_modules / generated files
- Batch profile is OFF when it should be Compact+ (cloud model not getting batched)

### Process Logs Panel — Expected Log Format

Each stage should produce **exactly one log line per progress tick**, formatted as:
```
INFO [prep.services.pipeline.workers] [ProjectName/StageName] message (current/total — N%)
```

NOT:
```
INFO [prep.core.augmenter] Augmentation progress: 2325/13153 (18%) — avg 28.2s/item
INFO [prep.core.augmenter] Augmentation progress: 2325/13153 (18%) — avg 28.2s/item  ← DUPLICATE
INFO [prep.services.pipeline.workers] [Haley/Fast Catalogue] augment_symbols (2325/13153 — 18%)
INFO [prep.services.pipeline.workers] [Haley/Fast Catalogue] augment_symbols (2325/13153 — 18%)  ← DUPLICATE
```

Health polling should produce one line per poll interval (2-5 seconds), not duplicate pairs:
```
INFO [uvicorn.access] 127.0.0.1:53670 - "GET /health HTTP/1.1" 200
```
NOT two identical lines.

---

## Fix Plan & Implementation Status

### Sprint 1: Critical Fixes (Make pipeline complete correctly) — ✅ DONE

| ID | Bug | Fix | Files | Status |
|----|-----|-----|-------|--------|
| P48-F1 | BUG-2: Deepening "complete" threshold too high | Lowered from 0.90→0.70 for 'complete', 0.50→0.40 for 'stale' | `GraphEnrichmentPipeline.tsx:265-266` | ✅ |
| P48-F2 | BUG-1: Atlas always stale after pipeline | If deepening has run (total_scored > 0), treat atlas as complete regardless of fingerprint | `GraphEnrichmentPipeline.tsx:232-255` | ✅ |
| P48-F3 | BUG-3: Watcher triggers both legacy build AND pipeline | When trace enabled + pipeline available, skip legacy build entirely. Pipeline's own stages handle trace + embedding. | `watch.py:82-142` | ✅ |
| P48-F4 | BUG-7: deep_knowledge shares status with knowledge | Created separate `deep_knowledge_status` dict with `deep_chunks_embedded` field | `pipeline.py:182-195,283` | ✅ |

### Sprint 2: Auto Mode Fixes (Make auto actually continuous) — ✅ DONE

| ID | Bug | Fix | Files | Status |
|----|-----|-----|-------|--------|
| P48-F5 | BUG-6: No re-trigger for deepening | Added `_maybe_retrigger_deepening()` — after deep enrichment completes, if settled_ratio < 0.70 and auto mode on, schedules another pass in 30s | `orchestrator.py:770-843` | ✅ |
| P48-F6 | BUG-6: ScheduleEvaluator only handles 'scheduled' | Added auto-mode handling — checks every 2min if unconverged deepening work exists | `pipeline_budget.py:204-225` | ✅ |
| P48-F7 | Watcher should call `run_all()` when both auto | When deep_mode=="auto", watcher calls `run_all()` instead of `run_fast_sync()` | `watch.py:106-120` | ✅ |

### Sprint 3: UI/UX Fixes (Progress bars, colors, status display)

| ID | Bug | Fix | Files | Status |
|----|-----|-----|-------|--------|
| P48-F8 | BUG-5: staleCounts not wired to frontend | Already wired via `traceCoverage.summary` — staleCounts=0 when "0 stale" in Graph Scope (correct behavior) | `useDashboardPanels.tsx:748-751` | ✅ Already correct |
| P48-F9 | BUG-4: Progress doesn't distinguish new vs stale | Workers iterate all nodes, skip already-done; bi-color bar only activates with stale trace files | N/A | ⬜ Deferred (cosmetic) |
| P48-F10 | Running stage shows wrong color | In-progress bar uses `bg-blue-500` (correct); green+orange only shows during rerun with stale data | `StageProgressBar.tsx` | ✅ Already correct |

### Sprint 4: Live Run Bugs (Discovered during Haley 3739-file run)

| ID | Bug | Fix | Files | Status |
|----|-----|-----|-------|--------|
| P48-F11 | BUG-8: Duplicate log lines (4x) | Remove augmenter's own progress `logger.info()`; audit Python log handler config for double-attach | `augmenter.py:1265-1268`, `workers.py:234`, logging config | ⬜ |
| P48-F12 | BUG-9: 13153 items vs 3739 files | Show symbols+files breakdown in UI; split progress into Pass 1 (symbols) / Pass 2 (files) | `augmenter.py:1187`, `pipeline.py`, `GraphEnrichmentPipeline.tsx` | ⬜ |
| P48-F13 | BUG-10: Queue 3739 doesn't clear | Emit SSE after structural stage; verify trace coverage refreshes between stages | `workers.py`, SSE events, Graph Scope panel | ⬜ |
| P48-F14 | BUG-11: Structural "Completing..." stale | Trace status endpoint should read from build_manager cache; emit node/edge counts via SSE | `workers.py:272`, trace status endpoint, `GraphEnrichmentPipeline.tsx:565` | ⬜ |
| P48-F15 | BUG-12: ModelAwareness warning for inferred_edges | Align `_get_model_identity_for_task()` fallback chain with `_get_llm_client_for_task()` | `orchestrator.py`, `server.py` | ⬜ |
| P48-F16 | BUG-8b: Duplicate health endpoint polling | Audit frontend health polling — may be two useEffect intervals or SSE reconnect loop | `App.tsx`, `useTraceSystem.ts` | ⬜ |
| P48-F17 | BUG-13a: All stages turn orange on pause | Compute `isStagePaused` per-stage for Fast Sync (matching Deep Enrichment pattern) | `GraphEnrichmentPipeline.tsx:871-884` | ✅ |
| P48-F18 | BUG-13b: Resume creates new SM instead of resuming | `resume_paused()` now uses `Event.RESUME` on existing SM, calls `_advance_pipeline()` | `orchestrator.py:194-225` | ✅ |
| P48-F19 | BUG-13c: Race condition — PAUSED runs invisible to callbacks | Matching loop includes PAUSED runs; FAILED intercept checks both PAUSING and PAUSED | `orchestrator.py:589-598,663-669` | ✅ |
| P48-F20 | BUG-14a: Pipeline always restarts from stage 1 | Added `_detect_resume_point()` — checks manifest files on disk to skip completed stages | `orchestrator.py:307-377` | ✅ |
| P48-F21 | BUG-14b: run_fast_sync never checks disk state | `run_fast_sync/run_deep_enrichment` now call `_detect_resume_point()` with staleness check | `orchestrator.py:93-128` | ✅ |
| P48-F22 | BUG-14c: Watcher should force stage 1 rebuild | Watcher passes `force_from_start=True`; manual Run uses auto-detect | `watch.py:113-118`, `orchestrator.py:170` | ✅ |
| P48-F23 | BUG-15: force_reset_stale_runs skips stages | Now checks build slot phase — only resets if slot is IDLE (worker crashed), not if RUNNING (worker just slow) | `orchestrator.py:256-307` | ✅ |
| P48-F24 | BUG-16: Pause makes next stage turn green | `computeValidationState()` now checks `aug.augmented_nodes < total * 0.5` → returns 'disabled' for partial data | `GraphEnrichmentPipeline.tsx:189-192` | ✅ |
| P48-F25 | BUG-17: Model swap (swap_model) fails with STAGE_FAILED | QUEUED state added to FAILED intercept — swap_model's pause→resume→enqueue race no longer errors | `orchestrator.py:784-801` | ✅ |
| P48-F26 | AI Gateway model changes should require Save button | Removed auto-save, added explicit `saveLLMConfig()`. Save button activates when config is dirty. Swap only triggers on Save. | `useLLMConfig.ts`, `App.tsx`, `useDashboardPanels.tsx`, `AIModelsSettings.tsx` | ✅ |
| P48-F27 | BUG-18: Crash/restart loses pipeline state, UI stuck on "Running" | `_hydrate_paused_runs_from_disk()` scans disk manifests on startup, creates PAUSED SMs for incomplete work. Fixed import: `get_registry` from `project_helpers`. | `orchestrator.py:1302-1363` | ✅ |

### Sprint 5: Hot Scope Reload (Scope changes take effect during running pipeline)

**Problem:** When the user adds a folder to Exclude Tree while Stage 3 (Fast Catalogue) is running, the augmenter continues processing the old file list because it loaded `trace_nodes.jsonl` once at the start of `run()`. The exclude change only takes effect on the next Stage 1 rebuild — which means the entire multi-hour augmentation pass processes files the user explicitly told it to skip.

**Why this happens (architecture):**
1. Stage 1 (TraceBuilder) reads include/exclude globs at build time → writes `trace_nodes.jsonl`
2. Stage 3 (Augmenter) reads `trace_nodes.jsonl` once at `run()` start → builds `to_augment_symbols` + `to_augment_files` lists → iterates them sequentially
3. The augmenter has **zero knowledge** of exclude patterns — it just processes whatever nodes exist in the JSONL
4. There is no mechanism to signal a running stage that the scope changed

**Design: Pause-Rebuild-Resume approach**

The cleanest approach is: when scope patterns change, **pause the running stage, rebuild the trace graph with new patterns, then resume the stage**. The augmenter's incremental logic will skip already-processed items, and the new trace_nodes.jsonl will exclude the newly-excluded files.

```
User changes Exclude Tree
        │
        ▼
  Debounce (2s) — accumulate multiple changes
        │
        ▼
  Is pipeline running?
    ├─ NO → Save patterns to config. Done.
    │       (Next Run will use new patterns via Stage 1)
    │
    └─ YES → "Hot scope reload" sequence:
              1. Pause the running stage (fast flush, checkpoint)
              2. Re-run Stage 1 (TraceBuilder) with new globs
                 — This rebuilds trace_nodes.jsonl with fewer files
                 — Fast: Rust parser, takes 5-30s even for large repos
              3. Resume the paused stage
                 — Augmenter re-reads trace_nodes.jsonl (new, smaller list)
                 — Incremental logic skips already-augmented items
                 — Newly-excluded files are simply absent from the list
              4. Total interruption: ~30-60 seconds for a large repo
```

**Implementation plan:**

| ID | Task | Files | Status |
|----|------|-------|--------|
| P48-F33 | `hot_scope_reload()` orchestrator method — pause → rebuild Stage 1 → resume | `orchestrator.py:170-245` | ✅ |
| P48-F34 | Wire `POST /trace/ignore` and `PUT /included_paths` to trigger hot_scope_reload when pipeline running | `trace_routes/query.py:215-233`, `projects/crud.py:381-386` | ✅ |
| P48-F35 | Add debounce (2s) on pattern changes to batch multiple edits | Frontend | ⬜ Future |
| P48-F36 | Augmenter re-reads trace_nodes.jsonl on resume | Automatic — `resume_paused()` creates new worker via `_advance_pipeline()` | ✅ |
| P48-F37 | Stage 1 "scope-only rebuild" — fast mode that only re-walks the file tree without re-parsing symbols | `trace/builder.py` | ⬜ Future |

**Alternative: Per-item glob check (simpler, less correct)**

Instead of pause-rebuild-resume, the augmenter could check each node's `file_path` against the current exclude globs before processing it:

```python
# In augmenter's inner loop (line 1233):
for node in to_augment_symbols:
    # Check if file is still in scope
    fp = node.get("file_path", "")
    if self._is_excluded(fp):
        done += 1
        result.skipped += 1
        continue
    # ... normal augmentation
```

**Pros:** No pause needed. Immediate effect. Simple implementation.
**Cons:** The trace_nodes.jsonl still contains the old files (inconsistent state). Progress counter is misleading (skipped items still count toward total). Doesn't affect stages 1-2 which already ran.

**Recommendation:** Start with the per-item glob check (quick win, reduces wasted LLM calls immediately) and add the full pause-rebuild-resume as a follow-up.

### Sprint 6: Cloud Batching & Thinking Models (see CLOUD_BATCHING_RESEARCH.md)

**Research doc:** `docs/Phase48_fix-pipeline/CLOUD_BATCHING_RESEARCH.md`

| ID | Task | Files | Status |
|----|------|-------|--------|
| P48-F40 | Thinking model output stripping (backward brace-matching in `_parse_json_response`) | `llm_client.py:255-338` | ✅ |
| P48-F41 | Cloud model detection for Ollama (`is_cloud_model_via_ollama()` + `detect_profile_from_context` update) | `batch_profiles.py:197-283` | ✅ |
| P48-F41b | Remove duplicate augmenter progress logging (4 instances of "Augmentation progress" removed) | `augmenter.py` | ✅ |
| P48-F42 | Symbol batching (Pass 1) -- `_augment_symbols_batched()` with ID-based reordering | `augmenter.py:890-1062` | ✅ |
| P48-F42b | Fix pre-existing `_synthetic_entry` wrong-args bug in file batching (would crash on partial batch results) | `augmenter.py` (2 call sites) | ✅ |
| P48-F42c | Add thinking-model awareness to `BatchedResponseParser` (Strategy 1b: `_parse_json_response` for kimi-style preambles) | `batch_strategy.py:71-81` | ✅ |
| P48-F43 | Empirical validation benchmark (batch sizes 1/10/25/50 across 4+ models) | `scripts/benchmark_batching.py` | ⬜ |
| P48-F44 | Adaptive batch sizing based on model type + context window | `batch_profiles.py` | ⬜ |

### Sprint 7: Robustness & Verification

| ID | Description | Files | Status |
|----|-------------|-------|--------|
| P48-F30 | Add pipeline integration test | `tests/test_pipeline_integration.py` | ⬜ Future |
| P48-F31 | Add auto-mode integration test | `tests/test_pipeline_auto.py` | ⬜ Future |
| P48-F32 | Verify incremental behavior of each worker | Individual worker tests | ⬜ Future |

---

## Detailed State Flow Diagram

```
Startup
  │
  ├─ fast_auto=true? ──yes──→ run_all() or run_fast_sync()
  │                              │
  │                              ▼
  │                    _start_group("fast_sync")
  │                              │
  │                    SM: IDLE → RUNNING
  │                              │
  │                    _advance_pipeline()
  │                              │
  │                    stage[0] → BuildOrchestrator.start()
  │                              │
  │                    _on_build_transition(COMPLETED)
  │                              │
  │                    SM: STAGE_COMPLETED (index++)
  │                              │
  │                    _advance_pipeline() → stage[1]...
  │                              │
  │                    ... repeat for all 5 stages ...
  │                              │
  │                    SM: ALL_STAGES_DONE → COMPLETED
  │                              │
  │                    _trigger_code_index_build()
  │                              │
  │                    Auto-chain check:
  │                    ├─ _chain_deep[pid]? → run_deep_enrichment()
  │                    ├─ _is_deep_enrichment_auto()? → run_deep_enrichment()
  │                    └─ neither → done
  │
  ├─ Watcher file change ──→ trigger_build()
  │                              │
  │                    ├─ _start_project_build() ← BUG: shouldn't do this
  │                    └─ pipeline_orchestrator.run_fast_sync()
  │                              │
  │                    (same flow as above)
  │
  └─ Schedule evaluator ──→ run_deep_enrichment() (scheduled mode only)
```

---

## Current Settings Check

The pipeline config is stored in `settings_store` under key `pipeline_config`:
```json
{
  "fast_sync": { "auto": true/false },
  "deep_enrichment": { 
    "mode": "manual" | "auto" | "scheduled",
    "schedule": { "interval_minutes": 60, "threshold_percent": 20 },
    "budget": { "max_tokens_per_run": 0, "max_minutes_per_run": 5 }
  }
}
```

The frontend's `autoConfig` maps to:
- `fastSync: boolean` → `pipeline_config.fast_sync.auto`
- `deepEnrichment: DeepEnrichmentMode` → `pipeline_config.deep_enrichment.mode`
