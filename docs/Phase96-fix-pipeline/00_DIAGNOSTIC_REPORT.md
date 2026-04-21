# Phase 96: Pipeline Diagnostic Report

**Date:** 2026-04-10
**Scope:** Pipeline stages 1-10 (Sync + Enrich), Scheduler, Queue, MCP, Daemon
**Test baseline:** 164 passing, 23 failing across pipeline test suite

---

## Executive Summary

The pipeline is in a degraded state following Phase 89 (state machine fixes) and Phase 91 (scheduler/swarm redesign). The core symptom: **the pipeline cannot reliably run all stages sequentially to completion.** Stages get skipped, run simultaneously, or stall in `queued` state. Concurrency within stages has regressed from 10+ parallel workers to 1-2. Progress reporting is unreliable because it reflects impossible states from the sequencing bugs. Server logs die off mid-pipeline. MCP server disconnects during operation.

This document catalogs every issue discovered during diagnostic investigation.

---

## 0. Live Reproduction (2026-04-10)

We reproduced the pipeline stall live by restarting the daemon and observing behavior. Key findings:

### 0.1 Freshness-Skip Slot Leak (ROOT CAUSE OF STALL)

**Reproduced on:** SMOKE: rust_repo (project `0c50e42e`)

Sequence of events captured from daemon log:
1. Daemon auto-recovered deep enrichment, resumed at stage 3/6 (atlas)
2. Scheduler acquired slot: `acquired slot on cloud:default_ollama for atlas (1/1 dynamic cap)`
3. Freshness check fired: `Stage atlas skipped for 0c50e42e: all outputs are newer than inputs — already current`
4. Next stage deepening tried to acquire: `queued on cloud:default_ollama for deepening (position 1)`
5. Prep project completed structural, tried inferred_edges: `queued on cloud:default_ollama for inferred_edges (position 2)`
6. **Both pipelines stuck forever** — nothing will release the held atlas slot

**API confirmation** (`GET /system/pipeline-queue`):
```json
{
  "cloud:default_ollama": {
    "max_concurrent": 10,
    "current_load": 1,
    "active": { "0c50e42e-...": "atlas" },  // STILL HELD — atlas was SKIPPED!
    "queued": [
      { "stage": "deepening", "waiting_seconds": 265 },
      { "stage": "inferred_edges", "waiting_seconds": 252 }
    ]
  }
}
```

**Root cause in code** (`orchestrator.py`):
- Line ~1570: `pipeline_scheduler.acquire()` — slot acquired
- Line 1589: `run._current_node_id = node_id` — node stashed
- Line 1661: `_should_skip_stage_freshness()` returns True
- Line 2542: Stage result set to "skipped"
- Line 2546: `run.current_stage_index += 1`
- Line 2547: `self._advance_pipeline(run)` — recursive call
- **MISSING: `pipeline_scheduler.release()` is never called for the skipped stage**

The slot acquired for the skipped stage remains held forever. No worker was launched, so no `_on_build_transition()` will fire, so no release will happen.

### 0.2 Dynamic Capacity Capped at 1

Despite `max_concurrent: 10` configured for the cloud:default_ollama node, the scheduler log showed `1/1 dynamic cap` when acquiring. The AIMD `current_limit` has not ramped up from its default, confirming the jumpstart regression (issue 2.1).

### 0.3 Dashboard Screenshot

Playwright screenshot captured showing:
- Pipeline Queue: SMOKE: rust_repo (Pending, Deep Enrich → deepening), Prep (Pending, Fast Sync → inferred_edges)
- Scheduler panel: shows "deepening loop on SMOKE: rust_repo" and "Inferred Edge Discovery on Prep" as active, but both are actually queued
- All downstream stages show "Waiting for..." status
- Screenshot saved: `/tmp/prep_dashboard.png`

### 0.4 Daemon Silent Death

The daemon exited cleanly (exit code 0) after ~10 minutes with no error or traceback. Last log lines were normal health check responses. No crash, no exception — it just stopped. This is the "server logs die off" symptom reported by the user. Possible causes:
- External signal (SIGTERM) from another process
- Sandbox timeout killing the background process
- Uvicorn worker timeout or lifecycle management

### 0.5 Additional Error Captured

During dashboard load:
```
ERROR:prep.api.routers.settings:Security health check failed: 'SettingsStore' object has no attribute 'get_global'
```
This indicates a missing method on SettingsStore — likely added to the API router but not implemented in the store.

### 0.6 MCP Server Disconnected

During the diagnostic session, the Prep MCP server disconnected from Claude Code (all 6 `mcp__prep__*` tools became unavailable). This correlates with daemon instability — the MCP server proxies through the daemon, so daemon death kills MCP.

---

## 1. Pipeline Stage Sequencing Failures

### 1.1 Stages Stuck in `queued` (CRITICAL)

**Test:** `test_fast_sync_sequences_all_5_stages`
**Result:** `assert 'queued' == 'completed'` — pipeline never completes

**Root cause:** Race condition in `_advance_pipeline()` re-entrance. The method is called outside the orchestrator lock (line ~1972 in `orchestrator.py`), so concurrent invocations can interleave. When a stage completes nearly instantly (Rust stages, freshness skips), the completion callback `_on_build_transition()` fires before the first `_advance_pipeline()` call returns. The new call tries to acquire a scheduler slot while the old call hasn't finished its bookkeeping, leading to the pipeline getting stuck in `queued`.

**Code path:**
```
_advance_pipeline(stage N) → starts worker
    ↓ (worker completes instantly)
_on_build_transition() fires → calls _advance_pipeline(stage N+1)
    ↓ (tries to acquire scheduler slot)
scheduler.acquire() fails → pipeline transitions to QUEUED
    ↓ (but the release from stage N hasn't happened yet)
Pipeline stuck — no release will trigger dequeue
```

**Files involved:**
- `src/prep/services/pipeline/orchestrator.py` — `_advance_pipeline()` (~line 1380), `_on_build_transition()` (~line 1706)
- `src/prep/services/build_orchestrator.py` — `_notify()` fires listeners outside lock (~line 366)

### 1.2 Stage Skipping (Double Index Increment)

**Symptom:** Pipeline jumps from stage N to stage N+2, skipping N+1.

**Root cause:** Two independent paths both increment `current_stage_index`:

1. **State machine transition** (`state_machine.py:355`): `STAGE_COMPLETED` event handler increments `current_stage_index += 1`
2. **Freshness skip** (`orchestrator.py:2546`): Manual `run.current_stage_index += 1` before recursive `_advance_pipeline()` call

When a freshness skip happens and is immediately followed by a `STAGE_COMPLETED` transition, the index gets incremented twice, causing the next stage to be skipped entirely.

**Files involved:**
- `src/prep/services/pipeline/state_machine.py:355` — `STAGE_COMPLETED` handler
- `src/prep/services/pipeline/orchestrator.py:2546` — freshness skip manual increment

### 1.3 Two Stages Running Simultaneously

**Symptom:** Sequential stages execute in parallel (visible in UI as overlapping progress bars).

**Root cause:** `_advance_pipeline()` has no re-entrance guard. The recursive call pattern:

```
_advance_pipeline() → freshness skip → recursive _advance_pipeline()
                                         ↓
                                     starts stage N+1 worker (daemon thread)
    ↓ (meanwhile)
Original _advance_pipeline() returns
    ↓ (stage N+1 worker completes fast)
_on_build_transition() → _advance_pipeline() → starts stage N+2
    ↓
Stages N+1 and N+2 can overlap if N+1 hasn't finished its bookkeeping
```

**Files involved:**
- `src/prep/services/pipeline/orchestrator.py` — recursive `_advance_pipeline()` calls at lines ~2547, ~2558

### 1.4 Wrong Terminal States

**Tests:**
- `test_pipeline_fails_when_stage_fails` — expects `failed`, gets `paused`
- `test_cancel_fast_sync` — expects `failed`, gets `cancelled`

These suggest the state machine transition table was modified in Phase 89/91 and the terminal state routing changed. The tests may need updating, or the state machine may be routing `STAGE_FAILED` through incorrect transitions.

### 1.5 Deep Enrichment Stage Count Mismatch

**Test:** `test_deep_enrichment_sequences_all_5_stages` — `assert 6 == 5`

**Root cause:** Test expects 5 stages but `DEEP_ENRICHMENT_STAGES` still has 6 (includes ATLAS). This will resolve when Atlas is moved to the Finalize group, but indicates the test was written against the planned 5-stage layout before the actual code change was made.

---

## 2. Scheduler Concurrency Regression

### 2.1 AIMD Jumpstart Dead for Ollama Providers (CRITICAL)

**19 test failures** related to `available_batch_workers` returning dramatically lower values than configured.

**Root cause:** The AIMD (Additive Increase, Multiplicative Decrease) congestion control logic was nested inside an `if rate_limit_remaining is not None` guard. Ollama never sends rate-limit headers, so `rate_limit_remaining` is always `None`. This means:

- **Jumpstart doubling never runs** — `current_limit` stays at its default (5)
- **Congestion detection never runs** — no adaptive scaling at all
- **`dynamic_capacity = min(current_limit, max_concurrent) = min(5, 12) = 5`**

Combined with `_weighted_share()` reserving N-1 headroom and splitting across projects:
- Single project: `full_budget = max(1, 5 - 1) = 4` → **4 workers instead of 12**
- Two projects: `4 / 2 = 2` → **2 workers each**
- Three projects: `4 / 3 = 1` → **1 worker each**

This explains why the user sees "only 2-3 resources" utilized despite configuring 12 concurrent calls.

**Commit `b17c7a65`** ("fix(scheduler): AIMD jumpstart was dead code for Ollama providers") partially addresses this by restructuring the AIMD logic so congestion detection and jumpstart work for all providers. However, this fix may not be fully integrated or may have introduced other regressions.

**Specific test failures:**

| Test | Expected | Got | Cause |
|------|----------|-----|-------|
| `test_cloud_concurrent_ten` | 10 slots acquirable | 5th fails | dynamic_capacity capped at 5 |
| `test_single_project_gets_full_budget` | 3 | 2 | headroom reservation |
| `test_single_project_ten_slots` | 10 | 4 | dynamic_capacity = 5, budget = 4 |
| `test_exclusive_gets_full_budget` | 10 | 4 | same cap applies to exclusive |
| `test_no_priority_equal_split` | 5 | 2 | budget split from capped pool |
| `test_ten_concurrency_two_boost_two_normal` | 4 (boost) | 2 | same |

### 2.2 Embedding Slot Acquisition Failure

**Test:** `test_embedding_concurrency_two` — second project can't acquire embedding slot.

The embedding concurrency pool may have similar capping issues or a separate bug in the embedding-specific slot path.

### 2.3 Swarm Detection Broken for Cloud Models

**Tests:** 4 `TestIsSwarmActiveForStage` failures — `kimi-k2.5:cloud` on Ollama and `claude-sonnet-4.6` on Anthropic both return `False` for swarm capability.

**Root cause:** The swarm registry (`swarm_registry.py` / `swarm_models.json`) may not include these model identifiers, or the model name matching logic doesn't handle the `:cloud` suffix or the `claude-sonnet-4.6` identifier (may be mapped as `claude-3-5-sonnet` or similar).

### 2.4 Fair-Share Weighting Errors

Multiple `TestWeightedFairShare` failures where boost and normal priorities don't distribute correctly. All related to the `dynamic_capacity` cap from the AIMD issue — the math is correct but operates on an artificially low base.

---

## 3. Daemon & Server Issues

### 3.1 Server Logs Die Off

**Symptom:** Server log output stops mid-pipeline. The user reports logs dying off during pipeline execution.

**Possible causes:**
- Logger buffer not flushing under high throughput
- Uncaught exception in a daemon thread killing the logging context
- SQLite WAL locking (Phase 92 partially addressed this) causing logger writes to block
- Worker threads crashing silently without logging the exception

**Investigation needed:** Run daemon with `--log-level debug` and watch for the exact point where logging stops. Check if it correlates with a specific stage transition or scheduler event.

### 3.2 Daemon Startup Log Shows Multiple Issues

From the daemon startup capture (2026-04-10):

```
WARNING: Stage enrichment has manifest but output trace_epistemic.jsonl is missing/empty — treating as incomplete
WARNING: Atlas manifest exists but atlas_segments_manifest.json is missing/empty — treating as incomplete
```

These warnings indicate **manifest/output file inconsistency** — manifests claim stages completed but the actual output files are missing. This could cause:
- Incorrect freshness detection (stage thinks it's complete but isn't)
- Resume from wrong point after crash/restart
- The freshness skip bug (1.2) to interact badly with missing outputs

### 3.3 Ghost Pipeline Hydration on Startup

The daemon startup shows multiple projects being hydrated with PAUSED state:
```
Hydrated PAUSED state for b1fd79e7.../deep_enrichment at stage 3/6 (atlas) — user can Resume to continue
Hydrated PAUSED state for 33308e87.../deep_enrichment at stage 3/6 (atlas) — user can Resume to continue
Hydrated PAUSED state for 0c50e42e.../deep_enrichment at stage 3/6 (atlas)
Hydrated PAUSED state for 968c889b.../deep_enrichment at stage 1/6 (group_reasoning)
```

Multiple projects stuck at Atlas (stage 3/6 in deep enrichment) or Group Reasoning. This is consistent with the sequencing bugs — stages stall and never advance, leaving ghost PAUSED states that accumulate across daemon restarts.

### 3.4 Scheduler Slot Contention on Startup

The startup log shows the scheduler immediately acquiring a slot and queuing others:
```
Scheduler: 1d6f0b35... acquired slot on cloud:default_ollama for enrichment (1/1 dynamic cap)
Scheduler: 0c50e42e... queued on cloud:default_ollama for atlas (position 2)
```

Note: **`1/1 dynamic cap`** — the scheduler is operating with a dynamic capacity of 1 despite being configured for higher concurrency. This is the AIMD regression in action (issue 2.1).

### 3.5 Exclusive Priority Starvation

```
Scheduler: priority 7230f731... → exclusive (new)
```

One project has exclusive priority, which blocks all other projects from acquiring slots. If this project is inactive or stuck, it starves the entire pipeline system. The priority was restored from saved state on startup — there may need to be a TTL or auto-expiry for exclusive priorities.

---

## 4. MCP Server Status

### 4.1 Import Structure Changed

The MCP server no longer exports `app` from `prep.mcp.server`:
```python
ImportError: cannot import name 'app' from 'prep.mcp.server'
```

The module exports `MCPServer` class instead. This may affect:
- The MCP wrapper script (`prep-mcp-wrapper.sh`)
- Any IDE configurations that import/launch the MCP server
- Direct mode MCP (`prep.mcp_direct`)

### 4.2 MCP Functionality Untested

The MCP server's 6 tools (`prep`, `prep_search`, `prep_impact`, `prep_audit`, `prep_observe`, `prep_concepts`) proxy through the daemon at :8400. Since the daemon has pipeline scheduling issues, the MCP tools that query pipeline state (`prep` ambient context) may return stale or incorrect data.

**Testing needed:**
- Can the MCP server start and complete the handshake?
- Do tool calls return valid responses?
- Does `prep` (no-arg ambient context) return correct structural data?
- Does `prep_search` return results?

### 4.3 Direct Mode Drift

Per CLAUDE.md: "Direct mode (`src/prep/mcp_direct.py`) has drifted behind server mode. The `prep` no-arg ambient context call is broken in direct mode." This is a known issue but compounds the testing challenge — if server mode is broken too, there's no working MCP path.

---

## 5. Queue System Issues

### 5.1 Queue Status Endpoint Reliability

The queue API endpoint (`GET /system/pipeline-queue`) merges data from the orchestrator and scheduler. With the sequencing bugs causing ghost states and stale locks, the queue status likely shows:
- Projects listed as "running" that are actually stuck
- Incorrect stage assignments
- Ghost locks that survive purge attempts

### 5.2 Ghost Lock Accumulation

The queue endpoint runs `clean_locks()` on every read to purge ghost locks. However, with the scheduler slot contention issue (3.4), legitimate locks may be incorrectly purged during the stage transition window — or ghost locks may persist because the cleanup heuristic doesn't catch all cases.

### 5.3 Queue/Pipeline Interface Coupling

The queue system was designed to be pipeline-agnostic (the pipeline just needs to `acquire()`/`release()` slots), but Phase 91 introduced swarm-specific logic into the scheduler:
- `open_swarm_window()` / `close_swarm_window()` — swarm-aware blocking
- `is_swarm_active_for_stage()` — model-aware swarm detection
- `_is_blocked_by_swarm()` — checked in every `acquire()` call

This coupling means queue bugs can cause pipeline bugs and vice versa.

---

## 6. Test Suite Baseline

**Run date:** 2026-04-10
**Command:** `pytest tests/test_pipeline_state_machine.py tests/test_pipeline_orchestrator.py tests/test_pipeline_orchestrator_transitions.py tests/test_pipeline_scheduler.py -v`

### Results: 164 passed, 23 failed

### Failures by Category:

#### Orchestrator Sequencing (4 failures)
| Test | Expected | Got |
|------|----------|-----|
| `TestFastSync::test_fast_sync_sequences_all_5_stages` | completed | queued |
| `TestDeepEnrichment::test_deep_enrichment_sequences_all_5_stages` | 5 stages | 6 stages |
| `TestFailureHandling::test_pipeline_fails_when_stage_fails` | failed | paused |
| `TestCancellation::test_cancel_fast_sync` | failed | cancelled |

#### Scheduler Concurrency (14 failures)
| Test | Expected | Got |
|------|----------|-----|
| `test_cloud_concurrent_ten` | acquire succeeds | acquire fails |
| `test_single_project_gets_full_budget` | 3 workers | 2 workers |
| `test_single_project_ten_slots` | 10 workers | 4 workers |
| `test_ten_concurrency_two_boost_two_normal` | 4 workers | 2 workers |
| `test_no_priority_equal_split` | 5 workers | 2 workers |
| `test_exclusive_gets_full_budget` | 10 workers | 4 workers |
| `test_one_boost_three_normal` | 2 workers | 1 worker |
| `test_cloud_provider_finds_cloud_node` | 3 workers | 2 workers |
| `test_inactive_node_returns_full_capacity` | 5 workers | 4 workers |
| `test_embedding_concurrency_two` | acquire succeeds | acquire fails |
| `test_single_project_gets_full_budget` (swarm) | 10 workers | 4 workers |
| `test_two_projects_still_gets_full_budget` | 10 workers | 4 workers |
| `test_three_projects_with_boost_still_gets_full` | 10 workers | 4 workers |
| `test_prefix_fallback_when_no_project_id` | 8 workers | 4 workers |
| `test_local_ollama_finds_local_node` | 4 workers | 3 workers |

#### Swarm Detection (5 failures)
| Test | Expected | Got |
|------|----------|-----|
| `test_kimi_on_ollama_group_reasoning` | True | False |
| `test_kimi_on_ollama_clustering` | True | False |
| `test_kimi_on_ollama_atlas` | True | False |
| `test_claude_sonnet_on_anthropic` (group_reasoning) | True | False |

---

## 7. Proposed Fix Strategy

### Phase 96A: Pipeline Stage Sequencing (Priority 1)
**Goal:** All 10 stages (5 sync + 5 enrich) run sequentially to completion.

1. Add re-entrance guard to `_advance_pipeline()` — prevent concurrent calls
2. Consolidate stage index increments — only the state machine should increment, remove manual increments from freshness skip
3. Convert recursive `_advance_pipeline()` to iterative loop
4. Fix terminal state routing for failure/cancellation
5. Update deep enrichment test for 5-stage layout (after Atlas removal)

**Validation:** All 4 orchestrator tests pass. Run full cycle on `SMOKE: rust_repo`.

### Phase 96B: Scheduler Concurrency (Priority 2)
**Goal:** `available_batch_workers` returns correct values matching configured concurrency.

1. Fix AIMD jumpstart to work for all providers (not just those with rate-limit headers)
2. Review `_weighted_share()` headroom reservation — may be too aggressive
3. Fix swarm model detection for kimi and claude-sonnet identifiers
4. Fix embedding slot acquisition path

**Validation:** All 19 scheduler tests pass.

### Phase 96C: Live Validation (Priority 3)
**Goal:** Full pipeline cycle completes on real project with observable progress.

1. Start daemon, trigger pipeline on `SMOKE: rust_repo`
2. Monitor all 10 stages complete sequentially
3. Verify progress bars update correctly
4. Verify server logs don't die off
5. Verify queue status endpoint returns accurate data

### Phase 96D: MCP Validation (Priority 4)
**Goal:** MCP tools work end-to-end.

1. Verify MCP server starts and completes handshake
2. Test all 6 tools return valid responses
3. Verify `prep` ambient context reflects pipeline state correctly

---

## 8. Key Files Reference

| File | Lines | Role |
|------|-------|------|
| `src/prep/services/pipeline/orchestrator.py` | ~2000+ | Pipeline sequencing, stage advancement |
| `src/prep/services/pipeline/scheduler.py` | ~1100+ | Concurrency/slot management, AIMD, swarm |
| `src/prep/services/pipeline/state_machine.py` | ~500 | State machine transitions |
| `src/prep/services/pipeline/stages.py` | ~212 | Stage definitions, group constants, mappings |
| `src/prep/services/pipeline/workers.py` | ~900+ | Worker factory, stage-specific workers |
| `src/prep/services/build_orchestrator.py` | ~300 | BuildSlot lifecycle, worker threads |
| `src/prep/services/pipeline/recovery.py` | ~??? | Crash recovery, PAUSED hydration |
| `src/prep/services/pipeline/resume.py` | ~??? | Resume point detection |
| `src/prep/api/routers/queue.py` | ~235 | Queue status HTTP endpoint |
| `src/prep/api/routers/pipeline.py` | ~600+ | Pipeline control HTTP endpoints |
| `src/prep/mcp/server.py` | ~??? | MCP server (proxies to daemon) |
| `tests/test_pipeline_orchestrator.py` | ~397 | Orchestrator integration tests |
| `tests/test_pipeline_scheduler.py` | ~1200+ | Scheduler unit tests |
| `tests/test_pipeline_state_machine.py` | ~659 | State machine unit tests |

---

## 9. Related Phase History

| Phase | What Changed | Impact on Current State |
|-------|-------------|----------------------|
| Phase 72B | Priority system (exclusive/boost) | Works but can cause starvation (see 3.5) |
| Phase 82 | AIMD congestion control | Broken for Ollama (see 2.1) |
| Phase 89 | Atomic stage handoff, release-after-advance | Fixed some races, introduced others (see 1.1) |
| Phase 91 | Swarm window, 4-tier scheduling, capacity event bus | Swarm detection broken (see 2.3), added coupling (see 5.3) |
| Phase 92 | SQLite WAL checkpoint on startup/shutdown | Partially mitigates log die-off (see 3.1) |
| Phase 93 | Semantic chunking (in progress) | No pipeline impact |
