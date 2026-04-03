# Pipeline Architecture Audit: Initial Build vs Incremental/Stale Pipeline

**Date:** 2026-04-02  
**Scope:** Full trace graph pipeline — initial build, incremental updates, triggers, UI integration  
**Reference:** `docs/Phase61_SelfHeal/pipeline_diagnostic_postmortem.md`

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [Audit A: Initial Build Pipeline](#2-audit-a-initial-build-pipeline)
3. [Audit B: Incremental/Stale Pipeline](#3-audit-b-incrementalstale-pipeline)
4. [Critical Blockers](#4-critical-blockers)
5. [Architectural Issues](#5-architectural-issues)
6. [UI Integration Issues](#6-ui-integration-issues)
7. [Recommended Fixes (Priority Order)](#7-recommended-fixes-priority-order)
8. [Test Plan](#8-test-plan)

---

## 1. Pipeline Overview

### 11-Stage Model

**Fast Sync (Stages 1-5):**
| # | Stage | Worker | Queue | Incremental? |
|---|-------|--------|-------|-------------|
| 1 | STRUCTURAL | TraceBuilder (Rust) | CPU | NO — always full rebuild |
| 2 | INFERRED_EDGES | InferredEdgesAnalyzer | LLM | YES — content hash skip |
| 3 | CATALOGUE | TraceAugmenter | LLM | YES — content hash skip |
| 4 | VALIDATION | Validator | LLM | YES |
| 5 | KNOWLEDGE | KnowledgeIndex | Embedding | Partial |

**Deep Enrichment (Stages 6-11):**
| # | Stage | Worker | Queue | Incremental? |
|---|-------|--------|-------|-------------|
| 6 | ENRICHMENT | EpistemicEnricher | LLM | YES — content hash skip |
| 7 | GROUP_REASONING | GroupReasoningAnalyzer | LLM | YES |
| 8 | CLUSTERING | ModuleSynthesizer | LLM | YES |
| 9 | ATLAS | CodebaseAtlas | LLM | Partial |
| 10 | DEEPENING | ContinuousDeepening | LLM | YES |
| 11 | DEEP_KNOWLEDGE | KnowledgeIndex | Embedding | Partial |

### Key Files

| Component | File | Lines |
|-----------|------|-------|
| Orchestrator | `src/codrag/services/pipeline/orchestrator.py` | ~3000 |
| Stages & Types | `src/codrag/services/pipeline/stages.py` | ~150 |
| Workers | `src/codrag/services/pipeline/workers.py` | ~500 |
| State Machine | `src/codrag/services/pipeline/state_machine.py` | ~200 |
| Scheduler | `src/codrag/services/pipeline/scheduler.py` | ~150 |
| Build Orchestrator | `src/codrag/services/build_orchestrator.py` | ~411 |
| Build Manager | `src/codrag/services/build_manager.py` | ~600 |
| Watcher | `src/codrag/core/watcher.py` | ~593 |
| Coverage | `src/codrag/core/trace/coverage.py` | ~349 |
| Checkpoint | `src/codrag/services/pipeline_checkpoint.py` | ~270 |
| Journal | `src/codrag/services/pipeline_journal.py` | ~509 |
| API Routes | `src/codrag/api/routers/pipeline.py` | ~545 |
| Watch Routes | `src/codrag/api/routers/projects/watch.py` | ~215 |
| Frontend Hook | `src/codrag/dashboard/src/hooks/useEnrichment.ts` | ~499 |
| Frontend Hook | `src/codrag/dashboard/src/hooks/useTraceSystem.ts` | ~706 |
| SSE Hook | `packages/ui/src/hooks/useEventStream.ts` | ~122 |
| Pipeline UI | `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` | ~500 |

---

## 2. Audit A: Initial Build Pipeline

### Trigger Chain

```
User clicks "Run Fast Sync" (or "Auto-Pilot")
    ↓
useTraceSystem.handleRunFastSync() → api.runPipelineFast(projectId)
    ↓
POST /projects/{id}/pipeline/fast
    ↓
pipeline_orchestrator.run_fast_sync(project_id)
    ↓
_detect_resume_point() → returns 0 (no manifests on disk)
    ↓
_start_group(project_id, "fast_sync", FAST_SYNC_STAGES, resume_from=0)
    ↓
PipelineGroupStateMachine(IDLE → START → RUNNING)
    ↓
journal.start_run() → SQLite persistence
    ↓
_advance_pipeline(sm) → starts Stage 1
    ↓
WorkerFactory.create_worker() → _trace_worker()
    ↓
BuildOrchestrator.start() → spawns daemon thread
    ↓
TraceBuilder.build() (Rust engine)
    ↓
_on_build_transition(COMPLETED) → _advance_pipeline() → Stage 2...
    ↓
[Repeat for stages 2-5]
    ↓
ALL_STAGES_DONE → chain deep enrichment (if auto) → stages 6-11
```

### What Works Well

1. **State machine is sound** — PipelineGroupStateMachine with formal transitions prevents invalid states
2. **Journal persistence** — Run intent is persisted to SQLite before work starts (crash recovery)
3. **Checkpoint system** — Critical data files backed up before destructive stages
4. **Heartbeat monitoring** — 10s heartbeat thread + 60s crash detection window
5. **0-node sanity check** — Catches Rust engine failures after Stage 1
6. **Budget throttle** — Prevents runaway auto-chaining on token budget exhaustion
7. **Telemetry scrubbing** — Fixed the 2MB/s DOS attack (postmortem fix)
8. **Auto-pause on failure** — Phase 55: LLM errors pause pipeline instead of terminal FAILED

### Issues (Minor — Pipeline Works)

| Issue | Severity | Location | Description |
|-------|----------|----------|-------------|
| No structural incrementality | Low | `builder.py` | Always re-parses ALL files even if only 1 changed. Rust is fast so this is acceptable but wasteful for large repos. |
| `_chain_deep` lazy-init | Medium | `orchestrator.py:411` | `getattr(self, "_chain_deep", {})` creates a new dict each time if attribute doesn't exist. Should be in `__init__`. |
| Force-reset race | Low | `orchestrator.py:1298-1310` | If a stage slot is "stuck", does `cancel() + sleep(0.1) + start()`. The 100ms sleep is fragile. |

---

## 3. Audit B: Incremental/Stale Pipeline

### Trigger Chain

```
[After initial build is complete, all 11 manifests exist on disk]

Trigger A: File watcher detects changes
    watchdog → _queue_path() → debounce(5s) → _on_debounce_fire()
    → trigger_build(paths) → pipeline_orchestrator.run_fast_sync()

Trigger B: Periodic coverage check (every 5 min)
    _on_coverage_check() → compute_trace_coverage()
    → stale/untraced detected → _on_trigger_build(["__coverage_gap__"])

Trigger C: Post-completion retrigger (15s delay)
    _maybe_retrigger_for_coverage() → background thread
    → check_coverage_gap() → run_fast_sync()

Trigger D: User clicks "Retrace Stale" in UI
    handleRetraceStale() → api.runPipelineFast(projectId)
    → pipeline_orchestrator.run_fast_sync()
```

### Incremental Flow

```
run_fast_sync(project_id)
    ↓
_detect_resume_point() → returns len(stages) (ALL complete)
    ↓
check_coverage_gap() → {needs_rebuild: True, stale: 5, untraced: 3}
    ↓
incremental = True, resume = 0
    ↓
self._incremental_runs.add(project_id)  ← IN-MEMORY ONLY
    ↓
_start_group("fast_sync", stages, resume_from=0)
    ↓
Stage 1 (STRUCTURAL): Full rebuild — Rust re-parses ALL files
    → trace_nodes.jsonl updated with new file set
    → trace_manifest.json["file_hashes"] updated
    ↓
Stage 2 (INFERRED_EDGES): Reads manifest hashes → skips unchanged files
    → ONLY processes files with different content hash
    → Appends new edges to trace_inferred_edges.jsonl  ← BUG: never cleans old edges
    ↓
Stage 3 (CATALOGUE): Reads trace_augmented.jsonl + file hashes
    → _needs_augmentation(node, existing, file_hashes)
    → Skips nodes where file_hash matches existing augmentation
    → Processes only new/changed nodes
    ↓
Stage 4 (VALIDATION): Similar incremental logic
    ↓
Stage 5 (KNOWLEDGE): Re-embeds (partial incrementality)
    ↓
fast_sync complete → chain deep_enrichment
    ↓
run_deep_enrichment()
    ↓
is_incremental = project_id in self._incremental_runs  ← reads in-memory flag
    self._incremental_runs.discard(project_id)  ← clears flag
    ↓
_detect_resume_point(skip_mtime_cascade=is_incremental)
    → With skip_mtime_cascade=True: doesn't invalidate based on mtime
    → All deep manifests exist → resume >= len(stages) → BUT is_incremental=True
    → resume = 0 → run all stages in incremental mode
    ↓
Deep workers process only new/changed data
```

### Worker Incrementality Details

**How workers detect "already processed":**

All incremental workers share this pattern:
1. Read `trace_manifest.json["file_hashes"]` — per-file content hashes from Stage 1
2. Read their own output file (e.g., `trace_augmented.jsonl`)
3. For each node: check if `file_hash` in output matches current hash
4. Skip if match, process if different or missing

```python
# Pattern used by Catalogue (augmenter.py:451-468) and Epistemic (epistemic_enrichment.py:421-446)
def _needs_augmentation(self, node, existing, file_hashes) -> bool:
    node_id = node["id"]
    if node_id not in existing:
        return True  # New node
    entry = existing[node_id]
    file_path = node.get("file_path", "")
    if file_path and entry.file_hash:
        current_hash = file_hashes.get(file_path)
        if current_hash and current_hash != entry.file_hash:
            return True  # File changed
    return False  # Skip — already processed with same content
```

**Progress reporting with baseline offset:**
```python
# Workers report: "Processing 56/100 (56 already done)"
progress_callback(msg, current + skip_offset, total_nodes, skip_offset)
```

---

## 4. Critical Blockers

### BLOCKER 1: `_incremental_runs` Flag Is In-Memory Only

**File:** `orchestrator.py:78`  
**Impact:** HIGH — If daemon restarts between fast_sync completing and deep_enrichment starting, the incremental flag is lost. Deep enrichment then cascade-invalidates all manifests via mtime comparison, causing a FULL deep rebuild instead of incremental.

**Evidence:**
```python
# Line 78 — not persisted anywhere
self._incremental_runs: set[str] = set()

# Line 201 — set during fast_sync
self._incremental_runs.add(project_id)

# Line 225-226 — read during deep_enrichment
is_incremental = project_id in self._incremental_runs
self._incremental_runs.discard(project_id)
```

**Fix:** Persist to journal or a lightweight file in `<index_dir>/pipeline_state.json`.

---

### BLOCKER 2: No Cleanup of Stale Derivative Files

**File:** `builder.py` (structural stage), `workers.py:252-304`  
**Impact:** HIGH — When files are deleted/excluded, their edges remain in `trace_inferred_edges.jsonl` forever. The inferred edges stage only appends, never truncates or removes edges for deleted source nodes.

**Confirmed:** `grep` for any `unlink`, `delete`, `cleanup`, `wipe` of `trace_inferred_edges` returns zero results. The postmortem recommended this fix but it was never implemented.

**Evidence from postmortem:**
> "fast_sync (which generates the initial tree) should aggressively wipe stale derivative JSONL traces (like inferred_edges.jsonl or old trace_epistemic.jsonl) so old artifacts don't masquerade as current pipeline state if downstream tasks decide to skip."

**Fix:** After Stage 1 (STRUCTURAL) completes, validate all derivative output files against the current node set and remove entries referencing deleted nodes. OR truncate derivative files when running in non-incremental mode.

---

### BLOCKER 3: Coverage Gap Exception Silently Suppresses Rebuild

**File:** `orchestrator.py:174, 618-626`  
**Impact:** MEDIUM-HIGH — If `compute_trace_coverage()` throws (disk error, corrupt manifest, missing file), the catch returns `needs_rebuild: False`. The calling code at line 174 also catches and returns `False`. This means any exception in coverage detection silently prevents incremental updates.

**Evidence:**
```python
# Line 174 — bare except returns False
except Exception:
    logger.info("All fast_sync stages already complete on disk for %s — skipping", project_id)
    return False  # ← silently skips rebuild!

# Line 618-626 — coverage gap returns safe default
except Exception:
    return {
        "total": 0, "traced": 0, "untraced": 0, "stale": 0,
        "needs_rebuild": False,  # ← silently suppresses!
        "coverage_pct": 0.0,
    }
```

**Fix:** Log the exception at WARNING level. Consider returning `needs_rebuild: True` as the safe default (better to rebuild unnecessarily than to silently miss files).

---

### BLOCKER 4: Coverage Retrigger Lost on Daemon Restart

**File:** `orchestrator.py:628-710`  
**Impact:** MEDIUM — The 15-second delayed retrigger runs in a daemon thread. If the daemon restarts during those 15 seconds, the retrigger is lost. There's no persistence of retrigger intent.

**Evidence:**
```python
# Line 642 — runs in daemon thread, sleeps 15s
def _check_and_retrigger():
    time.sleep(self._COVERAGE_RETRIGGER_DELAY)  # 15 seconds
    # ... then checks and triggers

# Line 709 — daemon thread = dies with process
t = threading.Thread(target=_check_and_retrigger, daemon=True)
```

**Fix:** Persist retrigger intent in journal. On startup recovery, check for pending retriggers.

---

## 5. Architectural Issues

### ARCH 1: `_chain_deep` Dict Is Lazy-Initialized and In-Memory

**File:** `orchestrator.py:411`  
**Impact:** MEDIUM — `run_all()` sets `_chain_deep[project_id] = True`, but uses `getattr(self, "_chain_deep", {})` which creates a NEW dict if the attribute was never set. This means:
- First call to `run_all()` creates the dict and sets the flag
- But `_on_build_transition` at line 1135 does `getattr(self, "_chain_deep", {})` — if the orchestrator was somehow re-created, it gets an empty dict

Also: the chain flag is in-memory only. Daemon restart = orphaned deep enrichment.

---

### ARCH 2: Structural Stage Always Full Rebuild

**File:** `builder.py`  
**Impact:** LOW (Rust is fast) — Even in incremental mode, Stage 1 re-parses ALL files. For a 5000-file repo, this takes 5-30 seconds. A delta approach using `trace_manifest.json["file_hashes"]` to skip unchanged files would reduce this to <1 second for small changes.

---

### ARCH 3: 30-Minute Coverage Cooldown

**File:** `watcher.py:31`  
**Impact:** MEDIUM — `_COVERAGE_COOLDOWN_SECONDS = 1800` prevents coverage checks from re-triggering within 30 minutes. If the first retrigger fails (e.g., LLM down), the user waits 30 minutes for the next automatic attempt.

---

### ARCH 4: InferredEdges Appends Without Pruning

**File:** `inferred_edges.py`  
**Impact:** HIGH — The inferred edges worker loads existing edges and checks for duplicates, but it never REMOVES edges whose source or target nodes no longer exist in the trace graph. Over time, `trace_inferred_edges.jsonl` grows unboundedly with edges to deleted files.

---

### ARCH 5: Multiple Coverage Check Paths

**Impact:** LOW-MEDIUM — Coverage is checked in 3 places with different thresholds:
1. `run_fast_sync()` at line 128: `needs_rebuild = (untraced + stale) > 0` — any gap triggers
2. Watcher `_on_coverage_check()`: uses "close enough" thresholds (95% + ≤20 files + stale=0)
3. `_maybe_retrigger_for_coverage()`: same as #1

This means the watcher may decide NOT to trigger (close enough), but if run_fast_sync() is called directly, it WILL trigger. Inconsistent behavior.

---

## 6. UI Integration Issues

### UI 1: SSE-Driven State vs API-Polled Counters

**Files:** `useEnrichment.ts`, `useEventStream.ts`, `GraphEnrichmentPipeline.tsx`

The frontend uses a dual-source model:
- **SSE events** drive running/completed flags (1-2s latency)
- **API polling** (3s interval) drives progress counters

This works well for initial builds, but for incremental builds:
- The **baseline offset** in progress counters (e.g., "56/100 (56 already done)") depends on workers reporting it correctly
- If SSE reports "running" but the API hasn't polled yet, the progress bar shows 0/0 briefly

### UI 2: Stage State Computation Assumes Sequential

**File:** `GraphEnrichmentPipeline.tsx:268-285`

The key design principle:
> "The pipeline is SEQUENTIAL. If a later stage's SSE running flag is true, the earlier stage has definitely finished."

This is correct for both initial and incremental builds. However:
- Incremental builds may skip stages very quickly (0 items to process)
- The UI may not render intermediate "complete" states for fast-skipping stages
- Result: stages appear to "jump" from idle to complete without visual feedback

### UI 3: Paused State Hydration Is Fragile

**File:** `useEnrichment.ts:327-434`

Paused state is detected by checking if `pipeline_status.error` contains "Paused by user". This string-matching approach is fragile — any change to the error message format breaks pause detection.

### UI 4: Cross-Project State Reset Timing

**File:** `useEnrichment.ts:248-320`

When switching projects:
1. State resets immediately
2. Parallel fetches fire for all status endpoints
3. Sequential pipeline status fetch overrides running flags

Race condition: if the user switches projects rapidly, stale fetch responses from the previous project could arrive after the reset, contaminating the new project's state.

---

## 7. Recommended Fixes (Priority Order)

### P0 — Must Fix for Incremental Pipeline

| # | Fix | Files | Effort |
|---|-----|-------|--------|
| 1 | **Persist incremental flag** — Write `_incremental_runs` to `<index_dir>/pipeline_state.json` so it survives daemon restart | `orchestrator.py` | Small |
| 2 | **Prune stale inferred edges** — After Stage 1 completes, remove edges from `trace_inferred_edges.jsonl` whose source/target nodes are not in the current `trace_nodes.jsonl` | `orchestrator.py` or `workers.py` (post-structural hook) | Medium |
| 3 | **Fix silent exception in coverage gap** — Change line 174 to log at WARNING and return True (safe default = rebuild) | `orchestrator.py:174` | Tiny |
| 4 | **Initialize `_chain_deep` in `__init__`** — Move from lazy `getattr` to proper initialization | `orchestrator.py:62-78` | Tiny |

### P1 — Stability Improvements

| # | Fix | Files | Effort |
|---|-----|-------|--------|
| 5 | **Persist retrigger intent** — Write pending retrigger to journal so it survives restart | `orchestrator.py`, `pipeline_journal.py` | Medium |
| 6 | **Reduce coverage cooldown** — Change from 1800s (30min) to 300s (5min) with exponential backoff on repeated failures | `watcher.py:31` | Small |
| 7 | **Unify coverage thresholds** — Use the same "close enough" logic in all 3 coverage check paths | `orchestrator.py`, `watcher.py` | Small |

### P2 — Polish

| # | Fix | Files | Effort |
|---|-----|-------|--------|
| 8 | **Structural delta mode** — Use file hashes from manifest to skip unchanged files in Rust engine | `builder.py`, Rust engine | Large |
| 9 | **UI: cancel stale fetches on project switch** — Use AbortController to cancel in-flight requests | `useEnrichment.ts` | Small |
| 10 | **UI: show "skipped" state for fast-completing incremental stages** — Brief "complete (0 new)" indicator | `GraphEnrichmentPipeline.tsx` | Small |

---

## 8. Test Plan

### Segment 1: Incremental Flag Persistence (P0-1)

```
1. Run initial full pipeline → all 11 stages complete
2. Add 2 new files to the project
3. Trigger run_fast_sync() → should enter incremental mode
4. KILL the daemon process before deep_enrichment starts
5. Restart daemon
6. Verify: deep_enrichment starts in incremental mode (not full rebuild)
7. Check: deep stage manifests are NOT cascade-invalidated
```

### Segment 2: Stale Derivative Cleanup (P0-2)

```
1. Run full pipeline → all manifests exist
2. Delete a file from the project
3. Trigger incremental pipeline
4. After Stage 1 completes: verify trace_nodes.jsonl does NOT contain deleted file
5. After Stage 2 completes: verify trace_inferred_edges.jsonl does NOT contain edges to deleted file
6. Verify: no "ghost" edges in the trace graph
```

### Segment 3: Coverage Gap Recovery (P0-3)

```
1. Corrupt trace_manifest.json (make it invalid JSON)
2. Trigger run_fast_sync() when all manifests exist
3. Verify: coverage gap check logs WARNING (not silent INFO)
4. Verify: pipeline triggers rebuild instead of silently skipping
```

### Segment 4: End-to-End Incremental (Integration)

```
1. Run full pipeline from scratch → all 11 stages complete
2. Modify 3 files in the project
3. Add 2 new files
4. Delete 1 file
5. Trigger incremental pipeline (via watcher or manual)
6. Verify:
   - Stage 1: Full rebuild but fast (Rust)
   - Stage 2: Only processes 5 changed files (skip 95%)
   - Stage 3: Only augments 5 changed files
   - Stages 4-5: Similar incremental behavior
   - Stage 6-11: Only enriches 5 changed files
   - UI: Shows baseline offset progress (e.g., "95/100 (95 skipped)")
   - No stale edges for the deleted file
   - Total time: << initial full build
```

### Segment 5: UI Stability

```
1. Start incremental pipeline
2. Switch projects in the dashboard mid-pipeline
3. Switch back immediately
4. Verify: correct pipeline status displayed (not stale data from other project)
5. Verify: progress bars show correct baseline offsets
```
