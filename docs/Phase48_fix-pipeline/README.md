# Phase 48: Fix Pipeline — Comprehensive Audit & Fix Plan

## Overview

The CoDRAG enrichment pipeline has several interrelated bugs causing:
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

---

## How Pipeline SHOULD Work

### Manual Mode
1. User clicks "Run" on Fast Sync → runs stages 1-5 sequentially
2. User clicks "Run" on Deep Enrichment → runs stages 6-11 sequentially
3. Each stage's worker checks existing data and skips already-processed items (incremental)
4. Progress bars show blue for in-progress, green+orange for reruns with stale data
5. All stages show green checkmarks when complete

### Auto Mode (Fast Sync = Auto, Deep Enrichment = Auto)
1. **On startup**: Pipeline checks for stale/incomplete projects and runs automatically
2. **On file change**: Watcher detects change → triggers full pipeline (fast sync → auto-chain deep)
3. **After deep enrichment**: If settled_ratio is below target, re-trigger deepening with backoff
4. **Continuous**: As long as there are code changes or unsettled nodes, the LLMs keep working
5. **Budget throttle**: Prevents runaway costs by capping tokens per time window

### Scheduled Mode (Deep Enrichment = Scheduled)
1. ScheduleEvaluator checks every 60s
2. If interval elapsed OR stale threshold exceeded → triggers deep enrichment
3. Time-based: "run every N minutes"
4. Threshold-based: "run when X% of nodes are stale"

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

### Sprint 4: Robustness & Verification

| ID | Description | Files | Status |
|----|-------------|-------|--------|
| P48-F11 | Add pipeline integration test | `tests/test_pipeline_integration.py` | ⬜ Future |
| P48-F12 | Add auto-mode integration test | `tests/test_pipeline_auto.py` | ⬜ Future |
| P48-F13 | Verify incremental behavior of each worker | Individual worker tests | ⬜ Future |

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
