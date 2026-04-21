# Phase 96: Resolution Report

**Date:** 2026-04-11
**Scope:** Phases 96A (stage sequencing) and 96B (scheduler concurrency)
**Status:** Both phases complete, live-validated on SMOKE: rust_repo

---

## Test Results

| Metric | Baseline | After 96A | After 96B |
|--------|----------|-----------|-----------|
| Orchestrator tests failing | 4 | **0** | 0 |
| Scheduler tests failing | 19 | 15 | **0** |
| State machine tests failing | 0 | 0 | 0 |
| Transition tests failing | 0 | 0 | 0 |
| **Total failing** | **23** | **15** | **0** |
| **Total passing** | **164** | **176** | **189** |

---

## Phase 96A — Pipeline Stage Sequencing

### The Bug

When a stage was skipped by the freshness check (`_should_skip_stage_freshness`) or restored from backup (`_try_restore_stage_from_backup`), the orchestrator:

1. Acquired a scheduler slot for the stage
2. Checked freshness, decided to skip
3. Manually incremented `current_stage_index`
4. Called `_advance_pipeline()` recursively
5. **Never released the scheduler slot**

The slot was held forever because no worker was launched, so `_on_build_transition()` never fired to trigger the release. The next stage queued waiting for a slot that would never free. Entire pipeline stalled.

### The Fix

Added scheduler slot release before advancing when a stage is skipped. Both paths now mirror the release-before-advance pattern from the normal completion path:

**`src/codrag/services/pipeline/orchestrator.py`** — `_should_skip_stage_freshness()`:
```python
if should_skip:
    run.stage_results[stage.value] = "skipped"

    # Phase 96: Release the scheduler slot acquired for this stage
    # BEFORE advancing.  Without this release, the slot is held
    # forever (no worker was launched, so _on_build_transition will
    # never fire to release it).
    _release_node = getattr(run, '_current_node_id', None)
    if pipeline_scheduler.is_held_by(run.project_id):
        _deferred = pipeline_scheduler.release(
            run.project_id, stage, _release_node,
        )
        if _deferred:
            self._resume_queued_pipeline(
                _deferred.project_id, _deferred.stage,
            )

    run.current_stage_index += 1
    self._advance_pipeline(run)
```

Same fix applied to `_try_restore_stage_from_backup()`.

### Regression Tests

Added `TestFreshnessSkipReleasesSlot` in `tests/test_pipeline_orchestrator.py`:

1. **`test_skipped_stage_releases_scheduler_slot`** — single project, stage 2 skipped, verifies pipeline completes (doesn't stall in `queued`)
2. **`test_skipped_stage_does_not_block_other_projects`** — proj-1 skips all stages, proj-2 runs all stages, both must complete

Also fixed test isolation: the `pipeline` fixture now resets `pipeline_scheduler` singleton state between tests (was leaking slots/queues/priorities/listeners between tests).

---

## Phase 96B — Scheduler Concurrency

### The Bug

Two independent issues compounded to cap Ollama concurrency at 1-2 workers instead of the configured 10:

**1. `ComputeSlot.current_limit = 5` hardcoded default**

The AIMD congestion control used `current_limit` as a dynamic cap:
```python
dynamic_capacity = min(max_concurrent, current_limit)
```

With `current_limit=5`, a node configured for `max_concurrent=10` only delivered 5 slots. The AIMD jumpstart logic was supposed to grow `current_limit` on successful batches, but it was gated behind `if rate_limit_remaining is not None:` — Ollama never sends rate-limit headers, so the jumpstart never ran. `current_limit` stayed at 5 forever.

**2. N-1 headroom reservation in fair-share**

`_weighted_share()` reserved one slot for "interactive queries":
```python
full_budget = max(1, slot.dynamic_capacity - 1)
```

Combined with the capped `dynamic_capacity=5`, this meant single-project budgets were 4 (not 10). With multiple projects, each got `4 / N` → 1-2 workers per project.

Same pattern repeated in `full_budget_for_swarm()` and `available_batch_workers_for_provider()`.

**3. `configure_node` didn't grow existing `current_limit`**

When reconfiguring a node (e.g., `configure_embedding_concurrency(2)` after initial `max=1`), the new `max_concurrent` was set but `current_limit` stayed stuck at the old value.

### The Fix

**`src/codrag/services/pipeline/scheduler.py`:**

1. `ComputeSlot.__post_init__()` now initializes `current_limit` to `max_concurrent`:
```python
def __post_init__(self):
    if self.current_limit <= 0 or self.current_limit > self.max_concurrent:
        self.current_limit = max(1, self.max_concurrent)
```

2. Removed `-1` headroom reservation in 4 locations:
   - `_weighted_share()`
   - `full_budget_for_swarm()` (fast path)
   - `full_budget_for_swarm()` (prefix fallback)
   - `available_batch_workers_for_provider()` (exclusive path)
   - `available_batch_workers_for_provider()` (fallback path)

   All now use `max(1, slot.dynamic_capacity)` instead of `max(1, slot.dynamic_capacity - 1)`.

3. `configure_node()` and `configure_embedding_concurrency()` now grow `current_limit` when the max is raised:
```python
if slot.current_limit < new_max:
    slot.current_limit = new_max
```

4. Updated 3 stale test expectations that encoded the old buggy behavior:
   - `test_status_includes_aimd_fields` — expected `current_limit=5`, now expects `10` (matches configured max)
   - `test_get_max_dynamic_capacity` — expected `min(10, 5) = 5`, now expects `10`
   - `test_full_budget_for_swarm_returns_none_below_min_workers` — expected `max=3 → None`, now expects `max=2 → None` (N=2 is still below min_workers=3)

### Why the N-1 Headroom Was Removed (Not Just Reduced)

The "reserve 1 slot for interactive queries" heuristic predated Phase 82's AIMD. With AIMD in place, overload is already handled by backoff — the scheduler reduces `current_limit` when queue times spike or 429s come back. Static headroom on top of AIMD is redundant and halves small-capacity budgets.

---

## Live Validation — SMOKE: rust_repo

Triggered via `POST /projects/0c50e42e.../pipeline/rebuild` with the fresh daemon running our fixes.

### fast_sync (5 stages, 7.9 seconds total)

```
stage 1/5: structural     → ran → completed (28 nodes)
stage 2/5: inferred_edges → ran → completed
stage 3/5: catalogue      → ran → completed (28/28 augmented)
                             ↑ Batch concurrency: 10 workers ← 96B
stage 4/5: validation     → skipped (freshness) → slot released ← 96A
stage 5/5: knowledge      → ran → completed
                          → slot released
→ all_stages_done → completed in 7.9s
→ Auto-chained deep_enrichment
```

### deep_enrichment (6 stages, continuing)

```
stage 1/6: enrichment      → skipped (5 files already enriched) → slot released ← 96A
stage 2/6: group_reasoning → ran → completed (1 reused, 0 analyzed)
                           → slot released
stage 3/6: clustering      → running (waiting on kimi-k2.5:cloud LLM call for synthesis)
```

### Key validations

| Behavior | Expected | Observed |
|---|---|---|
| Sequential stage execution | ✅ | ✅ Every stage acquired → ran → released → next |
| Freshness-skipped stages release slots | ✅ | ✅ validation, enrichment both released correctly |
| `current_load` returns to 0 between stages | ✅ | ✅ `0/1 dynamic cap` after every release |
| Max concurrency matches config | 10 | **10** ✅ (`cloud:default_ollama: 0/10`) |
| Batch workers within stage | 10 | **10** ✅ (`Batch concurrency: 10 workers, provider=ollama, model=kimi-k2.5:cloud`) |
| No stages skipped unexpectedly | ✅ | ✅ (all expected stages ran in order) |
| No simultaneous stages | ✅ | ✅ (one at a time, sequential) |
| Auto-chain fast→deep | ✅ | ✅ (explicit_run_all reason) |

---

## Known Remaining Issues (NOT blocking Phase 96)

### 1. Dashboard Connection Storm

The Vite dev proxy + Chrome tab open ~60 TCP connections to the daemon within seconds, exhausting FastAPI's 40-thread anyio worker pool. Endpoints that touch the scheduler (`/system/pipeline-queue`, `/compute/scheduler`, `/projects/{id}/pipeline/status`) start timing out under this load. Endpoints that don't touch shared state (`/health`, async `/events`) remain responsive.

**Workaround:** Run daemon in isolation without the dashboard attached. Phase 96 live tests worked fine in this mode.

**Fix:** Out of scope for 96. Should be tracked as "96D — UI polling reduction" with:
- Reduce dashboard poll intervals from sub-second to 2-5s
- Consolidate multiple polling endpoints into a single SSE stream
- Raise anyio thread pool cap from default 40 to 200
- Investigate why Vite proxy isn't reusing connections

### 2. `SettingsStore.get_global` Missing Attribute

`ERROR:codrag.api.routers.settings:Security health check failed: 'SettingsStore' object has no attribute 'get_global'`

A router was added that calls a method which doesn't exist on the SettingsStore. Non-fatal (logged only, doesn't crash). Out of scope for 96.

### 3. Pre-existing Test Failures

6 tests in `tests/test_pipeline_budget.py` and `tests/test_pipeline_journal.py` were already failing at baseline (verified by stashing our changes and re-running). Not caused by Phase 96 work. Should be tracked separately.

---

## Remaining Phase 96 Work

### 96C — Live cycle validation on fresh state

Still to verify:
- **Initial build** (empty `.prep/` directory, every stage runs from scratch)
- **Incremental** (modified file → only affected stages re-run)
- **Rebuild** ✅ validated above

### Files Modified

| File | Change |
|---|---|
| `src/codrag/services/pipeline/orchestrator.py` | Release scheduler slot in freshness-skip and backup-restore paths (96A) |
| `src/codrag/services/pipeline/scheduler.py` | ComputeSlot current_limit default, remove N-1 headroom, configure_node growth (96B) |
| `tests/test_pipeline_orchestrator.py` | Added TestFreshnessSkipReleasesSlot, fixed test isolation, updated stale expectations |
| `tests/test_pipeline_scheduler.py` | Updated 3 test expectations to match new behavior |
| `docs/Phase96-fix-pipeline/00_DIAGNOSTIC_REPORT.md` | Initial investigation writeup |
| `docs/Phase96-fix-pipeline/01_RESOLUTION_REPORT.md` | This document |
