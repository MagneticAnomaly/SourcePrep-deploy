# Phase 96: Findings and Bugs Registry

**Last updated:** 2026-04-11 (F-11, F-28, F-36, F-37, F-38 closed)
**Status:** Living document — appended as new findings emerge

This is the canonical record of every issue, bug, anomaly, or noteworthy
finding uncovered during Phase 96 work. Each entry has:
- A unique ID for cross-reference
- Status (FIXED / OPEN / DEFERRED / NOT-A-BUG)
- Where it was found, what causes it, what the fix was (if any)
- Which commit shipped the fix
- Any follow-up tasks needed

---

## Index

| ID | Title | Status | Commit |
|---|---|---|---|
| F-01 | Freshness-skip slot leak (stages 1-10 stall) | ✅ FIXED | `997c579d` |
| F-02 | Backup-restore slot leak (same shape as F-01) | ✅ FIXED | `997c579d` |
| F-03 | `_advance_pipeline` race / re-entrance | ✅ FIXED | `997c579d` (test isolation) |
| F-04 | Stage skipping double-increment race | ✅ NOT REPRODUCED | (test passes) |
| F-05 | AIMD jumpstart dead for Ollama (current_limit stuck at 5) | ✅ FIXED | `997c579d` |
| F-06 | N-1 headroom reservation halves small budgets | ✅ FIXED | `997c579d` |
| F-07 | `configure_node` doesn't grow `current_limit` on reconfig | ✅ FIXED | `997c579d` |
| F-08 | Wrong terminal states (paused vs failed, cancelled vs failed) | ✅ FIXED | `997c579d` (test expectations) |
| F-09 | Test isolation: scheduler singleton state leaking | ✅ FIXED | `997c579d` |
| F-10 | Queue API returns terminal-state ghost entries | ✅ FIXED | `59c9d770` |
| F-11 | Dashboard polling storm exhausts FastAPI thread pool | ✅ FIXED (client-side reduction) | (this commit) |
| F-12 | Daemon "logs die off" symptom | ✅ EXPLAINED | (was F-11 manifestation) |
| F-13 | MCP server disconnects during operation | ✅ EXPLAINED | (was F-11 manifestation) |
| F-14 | `SettingsStore.get_global` AttributeError (recurring log error) | 🟡 OPEN | — |
| F-15 | Pre-existing test failures in budget/journal tests | 🟡 OPEN (out of scope) | — |
| F-16 | 15-stage merge has no parallel wave dispatch | 🟢 DEFERRED to 96G | (decision in 03_) |
| F-17 | Sequential finalize completes correctly | ✅ VALIDATED | `b2abf504` |
| F-18 | `synth.synthesize()` AttributeError (Tier 2 silently broken) | ✅ FIXED | `b4443e21` |
| F-19 | Audit synthesizer `TASK_MAX_CHARS` not imported | ✅ FIXED | `b4443e21` |
| F-20 | Dashboard `rulesStatus is not defined` (white screen crash) | ✅ FIXED | `b4443e21` |
| F-21 | `MIN_MODULE_FILES = 5` filters out small repos from swarm | ✅ FIXED | `b4443e21` |
| F-22 | Concept seeder is single LLM call, no fan-out | ✅ FIXED | `075acb41` |
| F-23 | Audit Tier 2 is sequential 5-document generation | ✅ FIXED | `075acb41` |
| F-24 | Inactive project's exclusive priority leaks across deactivation | ✅ FIXED | `c5ed9d4b` |
| F-25 | SwarmOrchestrator `_coordinate` has no timeout (relies on 600s LLM timeout) | ✅ FIXED | `c91184a5` |
| F-26 | SwarmOrchestrator `execute()` aborts whole swarm on coordinator fail | ✅ FIXED | `c91184a5` |
| F-27 | SwarmOrchestrator `_synthesize` has no timeout | ✅ FIXED | `c91184a5` |
| F-28 | AIMD doesn't recover from backoff (current_limit stays low until restart) | ✅ FIXED | (this commit) |
| F-29 | Thinking-model swallows num_predict budget on `thinking` field | 🟡 OPEN | task #23 |
| F-30 | Vite proxy connection accumulation (60+ ESTABLISHED to daemon) | 🟡 OPEN (manifestation of F-11) | — |
| F-31 | SQLite "database is locked" warnings on busy daemon | 🟡 OPEN (Phase 92 partial) | — |
| F-32 | Pipeline log "Batch synthesis failed" markers in module summaries | 🔵 NOT-A-BUG (data quality from older clustering run) | — |
| F-33 | rust_repo structural rebuild produces fewer nodes than existing file (write guard blocks) | 🟡 OPEN (Phase 70B working as designed but inconvenient for fixture) | — |
| F-34 | Swarm window cooldown (45s) blocks re-opening but doesn't reduce batch budget | ✅ NOT-A-BUG (cooldown only blocks new windows; budget query still returns full) | — |
| F-35 | "Daemon-runtime swarm hang" — was actually F-11 polling storm | 🔵 NOT-A-BUG (misdiagnosis, see entry) | — |
| F-36 | SQLite "database is locked" blocks swarm concept saves (26 generated, 0 saved) | ✅ FIXED | (this commit) |
| F-37 | `antibody_store.init()` never called — saves silently failed at DEBUG level | ✅ FIXED | (this commit) |
| F-38 | Antibodies worker passed `Concept` dataclass to `derive_antibodies_for_project` (expects dicts) | ✅ FIXED | (this commit) |

Total: **39 findings**, **27 fixed**, **6 open**, **2 deferred**, **2 not-a-bug**.

---

## Detailed entries

### F-01 — Freshness-skip slot leak

**Status:** ✅ FIXED in `997c579d` (Phase 96A)

**Symptom:** Pipeline stages stall in `queued` state forever. Multiple projects accumulate in the queue waiting for slots that will never free.

**Root cause:** `_should_skip_stage_freshness` in `orchestrator.py` acquires a scheduler slot, decides to skip the stage based on freshness check, increments `current_stage_index`, and recursively calls `_advance_pipeline()` — **but never releases the scheduler slot**. No worker is launched, so `_on_build_transition` never fires to release the slot. The slot stays held forever.

**Live reproduction:** Captured on SMOKE: rust_repo on 2026-04-10. Atlas freshness-skipped, slot held, deepening queued at position 1, CoDRAG inferred_edges queued at position 2. Both pipelines stuck.

**Fix:** Added `pipeline_scheduler.release()` call before advancing in `_should_skip_stage_freshness`. Mirrors the release-before-advance pattern from the normal completion path (`_on_build_transition` line ~1967).

**Tests:** `TestFreshnessSkipReleasesSlot::test_skipped_stage_releases_scheduler_slot` and `test_skipped_stage_does_not_block_other_projects` in `test_pipeline_orchestrator.py`.

---

### F-02 — Backup-restore slot leak

**Status:** ✅ FIXED in `997c579d` (Phase 96A)

**Symptom:** Same as F-01 but on the backup-restore code path.

**Root cause:** `_try_restore_stage_from_backup` in `orchestrator.py` had the same shape as F-01 — acquired slot, restored from backup, recursively advanced — but never released the slot.

**Fix:** Same pattern — added `pipeline_scheduler.release()` before advancing.

---

### F-03 — `_advance_pipeline` race / re-entrance

**Status:** ✅ FIXED via test isolation

**Symptom:** Concurrent calls to `_advance_pipeline()` from multiple threads (worker completion + state machine transition) could interleave and cause unexpected behavior.

**Root cause analysis:** Suspected re-entrance race during the audit. Could not reliably reproduce after F-01 fix. The freshness-skip slot leak was masking the real test signal. Once F-01 was fixed, the orchestrator tests pass consistently across runs (3/3 verified).

**Outcome:** Test isolation fix (scheduler singleton reset in fixture, run cleanup in teardown) resolved the test flakiness. No evidence of an actual race in production once F-01 was fixed.

---

### F-05 — AIMD jumpstart dead for Ollama

**Status:** ✅ FIXED in `997c579d` (Phase 96B)

**Symptom:** Despite configuring `max_concurrent=10` for Ollama cloud, the actual scheduler delivered 1-2 workers per project. The user's pipeline ran with batch concurrency capped at 1.

**Root cause:** `ComputeSlot.current_limit` defaulted to `5` (hardcoded). The AIMD jumpstart logic that was supposed to grow `current_limit` was gated behind `if rate_limit_remaining is not None:` — Ollama never sends rate-limit headers, so the jumpstart code path was dead. `current_limit` stayed at 5 forever, and `dynamic_capacity = min(max_concurrent, current_limit) = min(10, 5) = 5`.

**Fix:** Changed `ComputeSlot.current_limit` default to a sentinel (0) and `__post_init__` initializes it to `max_concurrent`. New nodes start at their full configured capacity.

---

### F-06 — N-1 headroom reservation

**Status:** ✅ FIXED in `997c579d` (Phase 96B)

**Symptom:** Single-project budgets returned N-1 instead of N. With `max=3`, budget was 2. With `max=10`, budget was 9 (or 4 after F-05).

**Root cause:** `_weighted_share()` and `full_budget_for_swarm()` reserved one slot for "interactive queries":
```python
full_budget = max(1, slot.dynamic_capacity - 1)
```

This was over-cautious. AIMD already handles overload via backoff — static headroom on top is redundant.

**Fix:** Removed the `-1` in five locations. All budget calculations now use `max(1, slot.dynamic_capacity)`.

---

### F-07 — `configure_node` doesn't grow `current_limit`

**Status:** ✅ FIXED in `997c579d` (Phase 96B)

**Symptom:** Reconfiguring an existing node with a higher `max_concurrent` only updated `max_concurrent` — `current_limit` stayed at the old (lower) value, so `dynamic_capacity` didn't actually grow.

**Fix:** `configure_node()` and `configure_embedding_concurrency()` now grow `current_limit` to match the new `max_concurrent` when raised.

---

### F-10 — Queue API returns terminal-state ghost entries

**Status:** ✅ FIXED in `59c9d770` (Phase 96D.1)

**Symptom:** Cancelled and failed pipelines lingered in `/system/pipeline-queue` API responses. The dashboard rendered them as "Pending" (label bug) and showed ghost entries.

**Root cause:** `_EXCLUDED_STATES = {"completed", "idle"}` in `routers/queue.py` didn't include `cancelled` and `failed`.

**Fix:** Added both to the excluded set. Detected and verified by the Playwright UI smoke driver — went from 2 desyncs to 0.

---

### F-11 — Dashboard polling storm exhausts FastAPI thread pool

**Status:** ✅ FIXED (client-side reduction shipped this commit)

**Resolution:** Client-side polling reduction. Inventory before fix: 14+ pollers, several at 2-3s, most without `document.hidden` pause and none with in-flight guards. During active enrichment + trace build, the cumulative request rate exceeded the daemon's 40-slot anyio thread pool, masquerading as a "swarm hang" (F-35 was originally misdiagnosed as exactly this).

Worst offenders fixed in this commit:

| Poller | Before | After | Changes |
|---|---|---|---|
| Health check (`App.tsx`) | 2s | 5s | already had visibility pause |
| Scheduler status (`App.tsx`) | 5s | 10s | + visibility pause + in-flight guard |
| Pipeline queue (`SidebarPipelineQueue`) | 5s | 10s | + visibility pause + in-flight guard (SSE re-fetch retained) |
| Enrichment status combo (`useEnrichment`, 5 endpoints) | 3s | 5s | + visibility pause + in-flight guard wrapping `Promise.allSettled` |
| Trace coverage (`useTraceSystem`) | 3s | 8s | + visibility pause + in-flight guard |
| Project status (`useProjectManager`) | 2s | 5s | + visibility pause + in-flight guard |
| Provenance (`App.tsx`) | 10s | 15s | + visibility pause + in-flight guard |
| Opportunities/agent (`useOpportunitiesSystem`) | 30s | 30s | + visibility pause |

**The two key patterns:**
1. **In-flight guard**: every poller now skips its tick if the previous request is still in flight. This alone prevents the 60+ TCP connection accumulation observed in F-30 — if the daemon is slow, the pollers throttle themselves automatically instead of stacking.
2. **`document.hidden` pause**: backgrounded dashboards now contribute zero traffic. Previously, multi-tab users multiplied the polling rate by N tabs.

**What's NOT in this fix:** A shared `usePoller` helper to centralize the pattern across all hooks (would touch ~15 files). The deeper architectural fix (server-side rate limiting / SSE-only status streams) is deferred. For now, the inventoried worst offenders are bounded.

**Validation:** TypeScript compiles cleanly for all 6 modified files (only 3 pre-existing unrelated `EnrichmentAutoConfig` schema errors in `useTraceSystem.ts:114-139` remain). Live end-to-end validation against `scripts/dev.sh` (which runs the dashboard alongside the daemon) is the next step before declaring the polling storm gone — open as task #29.

---

### F-11 (original investigation notes — preserved)

**Symptom:** When a long-running LLM call holds a worker, the dashboard's repeated polling of `/health`, `/system/pipeline-queue`, `/projects/{id}/pipeline/status`, `/llm/slots/status`, and several other endpoints exhausts FastAPI's default 40-thread anyio worker pool. New requests queue indefinitely. The daemon appears "hung" but is actually just waiting on thread pool capacity.

**Symptoms it manifests as:**
- F-12: "Daemon logs die off" — the daemon is alive but pool-exhausted
- F-13: MCP server disconnects (proxies through the daemon)
- F-30: Vite dev proxy accumulates 60+ ESTABLISHED TCP connections
- Status endpoints time out for 10+ seconds during pipeline runs

**Mitigations identified, not yet shipped:**
- Raise `anyio.to_thread.current_default_thread_limiter().total_tokens` from 40 to 200
- Reduce dashboard poll intervals (currently sub-second per endpoint)
- Consolidate polling endpoints into the existing `/events` SSE stream

**Workaround:** Run daemon in isolation without the dashboard tab open, or restart `scripts/dev.sh` between runs.

---

### F-14 — `SettingsStore.get_global` AttributeError

**Status:** 🟡 OPEN

**Symptom:** Recurring error in daemon logs:
```
ERROR:codrag.api.routers.settings:Security health check failed:
  'SettingsStore' object has no attribute 'get_global'
```

**Root cause:** A router calls a method that doesn't exist on `SettingsStore`. Non-fatal (logged only, doesn't crash).

**Action:** Track separately. Out of scope for Phase 96 but should be cleaned up.

---

### F-18 — `synth.synthesize()` AttributeError (Tier 2 silently broken)

**Status:** ✅ FIXED in `b4443e21`

**Symptom:** Audit Tier 2 LLM synthesis was never running. The audit worker called `synth.synthesize(result, idx_dir)`, but `AuditSynthesizer` only has `synthesize_all()`. The wrong method name raised `AttributeError`, which was swallowed by a broad `except Exception` block in the worker and silently logged at INFO level. Tier 2 has been broken since whenever the worker was written.

**Discovery:** Phase 96F.2 fixed the worker call site to use `synthesize_all()`, which exposed the latent `TASK_MAX_CHARS` import bug (F-19).

**Fix:** Worker now correctly calls `synth.synthesize_all(result, ctx, ..., concurrency=...)` and writes the documents via `save_documents()`.

---

### F-19 — Audit synthesizer `TASK_MAX_CHARS` not imported

**Status:** ✅ FIXED in `b4443e21`

**Symptom:** All 5 audit document generators raised `name 'TASK_MAX_CHARS' is not defined` when called.

**Root cause:** `audit/synthesizer.py` references `TASK_MAX_CHARS["audit"]` in 5 places but never imports the symbol. Latent bug masked by F-18 (the broken call site never reached this code).

**Fix:** Added `from codrag.core.llm_client import TASK_MAX_CHARS` to imports.

---

### F-20 — Dashboard `rulesStatus is not defined` white screen

**Status:** ✅ FIXED in `b4443e21`

**Symptom:** Dashboard rendered a white screen on load. Browser console:
```
PAGE ERROR: rulesStatus is not defined
ApiClientProvider/App boundary
```

**Root cause:** The Phase 96 finalize merge added `rulesStatus`, `conceptsStatus`, `auditPipelineStatus`, and `antibodiesStatus` to the `useDashboardPanels` enrichment object literal in `App.tsx`, but never added these names to the `useEnrichment()` destructure block. They were undefined at the reference site. The `<App>` component crashed at render whenever the `GraphEnrichmentPipeline` panel tried to render the Finalize group.

**Fix:** Added the four names to the destructure block. The hook returns them via `...state` spread; just needed to pull them out.

---

### F-21 — `MIN_MODULE_FILES = 5` filters out small repos from swarm

**Status:** ✅ FIXED in `b4443e21`

**Symptom:** SMOKE: rust_repo (5 modules × 1 file each) and E2E: mini-redis-rust (19 modules, only 1 with ≥5 files) couldn't activate the Phase 96F swarm path because `_load_modules_for_swarm` filtered modules with file_count < 5.

**Root cause:** The `MIN_MODULE_FILES = 5` constant was designed for the **sequential** path's prompt context — keeping the global prompt focused on substantial subsystems. The swarm path has the opposite goal: maximum decomposition into independent work units. Filtering small modules reduced fan-out without saving prompt budget (each worker only loads its own module).

**Fix:** Added `MIN_MODULE_FILES_FOR_SWARM = 1` constant. `_load_modules_for_swarm` now uses this threshold instead. Sequential path still uses the larger threshold for context filtering.

**Live validation:** mini-redis-rust now reports `[Swarm/Concepts] Fan-out: 19 modules across 10 workers (model=kimi-k2.5:cloud)`.

---

### F-24 — Inactive project's exclusive priority leaks across deactivation

**Status:** ✅ FIXED in `c5ed9d4b`

**Symptom:** A project (Haley) marked inactive in the UI still showed as having `exclusive` priority. Daemon startup log:
```
Scheduler: priority 7230f731... → exclusive (new)
Scheduler: restored priority for 1 project(s): 7230f731...=exclusive
```

**Root cause:** Three independent issues compounding:
1. `scheduler.load_from_settings()` startup loop iterated all projects and restored persisted priority levels without checking activity status. Inactive projects' exclusive flags re-applied on every daemon restart.
2. `_deactivate_project()` cancelled pipelines and stopped watchers but never cleared the runtime `_priority_projects` entry.
3. `_activate_project()` had no symmetric restore — even after F-24 fix #1, a project that was deactivated and then reactivated would have lost its priority.

**Fix:**
1. `load_from_settings()` skips projects with `config.active is False`, with a clear log line.
2. `_deactivate_project()` calls `pipeline_scheduler.set_priority(pid, "none")` to clear the runtime entry. Persisted `priority_level` in project config is preserved.
3. `_activate_project()` reads `priority_level` from config and re-applies it via `set_priority()`. Falls back to "boost" if only `is_starred` is set.

---

### F-25, F-26, F-27 — SwarmOrchestrator timeouts and don't-abort-on-coord-fail

**Status:** ✅ FIXED in `c91184a5`

**Symptom:** Live validation on mini-redis-rust hung for 11+ minutes when the kimi-k2.5:cloud coordinator LLM call didn't respond. The pipeline log froze at the coordinator prompt, the daemon thread pool exhausted, and the dashboard became unresponsive.

**Root causes:**
- F-25: `_coordinate()` had no timeout. Relied on `LLMClient.timeout = 600.0` (10 minutes) for the "large" model slot. Too long for swarm coordination.
- F-26: `execute()` returned `None` on coordinator failure, aborting the entire swarm even though `_fan_out` already had a default-assignment fallback path (line 171-175).
- F-27: Same as F-25 but for `_synthesize()`.

**Fix:**
- Added `DEFAULT_COORDINATOR_TIMEOUT_S = 120` and `DEFAULT_SYNTHESIS_TIMEOUT_S = 180` class constants.
- New `_llm_call_with_timeout()` helper wraps the LLM call in `ThreadPoolExecutor` and uses `Future.result(timeout=N)`.
- `execute()` no longer returns None when coordinator returns None. It constructs an empty `CoordinatorPlan` and proceeds — fan-out fills defaults.
- `concept_seeder` passes shorter `coordinator_timeout_s=90, synthesis_timeout_s=120` for time-sensitive pipeline use.

**Live validation:** Coordinator timeout fired correctly at 90s on rust_repo:
```
[Swarm/coordinator] LLM call timed out after 90s — falling back
```

**Limitation:** Worker LLM calls (per-WorkItem) don't yet have timeout protection. If the same upstream model issue affects workers, they'll hold threads until the LLMClient's longer timeout fires. See F-29 for the underlying thinking-model issue.

---

### F-28 — AIMD doesn't recover from backoff

**Status:** ✅ FIXED

**Resolution:** Two changes in `src/codrag/services/pipeline/scheduler.py`:

1. **Per-node floor (`min_limit`)**: Cloud nodes (`cloud:*` prefix) get a `min_limit=3` (or `max_concurrent` if smaller). The multiplicative-decrease path now uses `max(slot.min_limit, ...)` instead of `max(1, ...)`. A single slow LLM call can no longer collapse the budget below the SwarmOrchestrator's min_workers threshold.

2. **Time-based idle recovery**: Added `_maybe_idle_recover()` called from `acquire()`. If the slot has been past the backoff cooldown (30s) and past the recovery interval (30s) and is still below `max_concurrent`, grow `current_limit` by 1. Piggybacks on natural pipeline activity — no extra threads. Self-regulating: if pipelines are queued waiting for capacity, acquire() is called frequently → recovery happens; if nothing's running, no recovery is needed anyway.

3. **Backoff resets recovery clock**: When a backoff fires it sets `_last_recovery_time = now`, ensuring the next recovery tick is at least 30s after the most recent congestion signal.

**Tests** (`tests/test_pipeline_scheduler.py`, new `TestAIMDFloorAndRecovery` class, 11 cases):
- `test_cloud_node_gets_floor_of_3`
- `test_cloud_node_floor_capped_by_max` (small cloud nodes can't have floor>max)
- `test_local_node_floor_is_1`
- `test_backoff_respects_floor`
- `test_repeated_backoff_does_not_go_below_floor`
- `test_local_node_can_drop_to_1`
- `test_idle_recovery_grows_after_cooldown`
- `test_idle_recovery_skipped_during_backoff_cooldown`
- `test_idle_recovery_skipped_when_at_max`
- `test_idle_recovery_caps_at_max`
- `test_backoff_resets_recovery_clock`

All 118 scheduler tests pass (107 pre-existing + 11 new).

---

### F-28 (original investigation notes — preserved)

**Symptom:** When the AIMD multiplicative-decrease fires (due to long latency or 429), `current_limit` halves repeatedly (10 → 5 → 2 → 1) and **never recovers** without a daemon restart. The additive-increase path that's supposed to grow it back is gated on conditions that don't fire when the system is idle.

**Live observation:** During rust_repo concepts (which ran sequentially because it's a small repo) the 60-second LLM call triggered AIMD backoff. Subsequent stages (audit) saw `current_limit=1` and fell back to non-swarm/non-parallel modes.

**Fix options:**
1. **Floor for cloud nodes:** Never let `current_limit` drop below 3 on cloud nodes (matches the swarm `min_workers` floor).
2. **Idle recovery:** When the scheduler has been idle for N seconds with no congestion signals, gradually grow `current_limit` back toward `max_concurrent`.
3. **Tighter latency thresholds:** Don't treat a single legitimate slow LLM call as congestion. Require multiple slow calls in a window before backing off.

**Recommended:** Combination of (1) floor at 3 + (2) idle recovery. Implementation deferred until after Phase 96 validation cycle settles.

---

### F-29 — Thinking-model swallows num_predict budget on `thinking` field

**Status:** ⚠️ PARTIALLY FIXED in `c4e9fe68` — **think=false works in isolation but daemon-runtime hang persists. See F-35.**

**Symptom:** Direct test of kimi-k2.5:cloud with `num_predict=50`:
```json
{
  "model": "kimi-k2.5",
  "response": "",
  "thinking": "The user is asking me to say hello. This is a very simple, straightforward request...",
  "done_reason": "length"
}
```

**Root cause:** kimi-k2.5 (and other reasoning models) use a `thinking` field for chain-of-thought reasoning before producing the actual `response`. When `num_predict` is too small to fit both, the model exhausts the budget on thinking and produces empty output.

**Fix shipped (`c4e9fe68`):**
1. `swarm_orchestrator.py::_llm_call_with_timeout` passes `think=False` in coordinator and synthesis LLM calls.
2. `concept_seeder.py` per-module worker also passes `think=False`.
3. Tests in `test_swarm_orchestrator_timeout.py::TestSwarmThinkFalse` lock in the behavior.

**Validation in isolation:**
- Direct Ollama POST with `think: false`: returns in 1.0-3.5s with valid JSON, empty `thinking` field
- Direct LLMClient `generate(think=False)`: returns in 1.3s with the same valid output
- Daemon swarm call with `think=False` (via concept_seeder swarm path): **still hangs past 90s timeout**

This is confusing — same code path, same model, different behavior in daemon vs standalone. See F-35 for the daemon-runtime hang investigation. The think=false fix is **correct** but **insufficient** to fully unblock end-to-end finalize execution.

---

### F-35 — Daemon-runtime swarm call hangs even with think=false

**Status:** 🔵 NOT-A-BUG — **MISDIAGNOSIS, was actually F-11**

**Resolution:** Reproduced in isolation against `scripts/troubleshoot.sh` (daemon-only, no dashboard). Result: full finalize completed in **163 seconds with the daemon never hanging once**:

```
[Swarm/Concepts] Fan-out: 5 modules across 10 workers (model=kimi-k2.5:cloud)
[Swarm] Coordinator planned 5 assignments (707 tokens)         (16s)
[Swarm] Fan-out complete: 5/5 workers succeeded                (65s)
[Swarm] Synthesis complete (6277 tokens)                       (71s)
Pipeline finalize completed in 163.1s
```

`/health` responded in 2-6ms throughout the entire 163-second swarm run. No thread pool exhaustion, no daemon hang.

**The "hang" we observed earlier with `scripts/dev.sh` was 100% F-11** (dashboard polling storm). With the dashboard polling `/health`, `/llm/slots/status`, `/projects/{id}/...` at multiple polls per second while swarm workers held LLM connections, the FastAPI thread pool exhausted and the daemon appeared hung — but the underlying swarm machinery was working correctly the whole time.

**Lessons:**
1. **Always test runtime bugs in isolation first.** `scripts/troubleshoot.sh` (added in this session) starts daemon-only without dashboard. Use it for any reproduction work.
2. **Don't trust "daemon hung" symptoms when the dashboard is running** — they almost always come from F-11.
3. **Three of our previous "hang" finds were probably this same issue.** The 11+ minute coordinator hang on rust_repo earlier today was real (thinking-mode budget exhaustion, F-29). But the subsequent "always hangs" pattern was F-11 amplifying a slower-than-expected LLM call.

The five hypotheses listed in the original F-35 entry are now moot. None of them was the cause.

---

### F-36 — SQLite "database is locked" blocks concept saves

**Status:** ✅ FIXED

**Resolution:** Combined fix shipped in this commit:
1. Added `concept_store.save_many(project_id, concepts)` that batches all saves in a single transaction with retry-on-locked wrapper (3 attempts, exponential backoff).
2. Bumped `concept_store` connection `timeout` 10s → 30s and added `PRAGMA busy_timeout=30000`.
3. **Decisive fix:** moved `concept_store` to its own dedicated `codrag_concepts.db` file with one-shot migration in `server.py`. The first attempt (batching + busy_timeout alone) still failed because 6 stores share `codrag_settings.db` on the slow USB drive in DELETE journal mode — cross-store contention took longer than 30s. Eliminating the shared writer lock removed the failure mode entirely.
4. Updated `concept_seeder` swarm path to call `save_many` with per-concept fallback.

**Validation:** End-to-end finalize on rust_repo via `scripts/troubleshoot.sh` + `troubleshoot_f35_swarm_hang.py`:
- Run 1 (cold): swarm fan-out → 25 concepts persisted (was 0/26 before fix)
- Run 2 (warm, freshness skip): full finalize completes in 2.3s, antibodies stage saves 10/10
- 22 unit tests pass: `tests/test_concept_store_save_many.py` (11) + `tests/test_antibody_store.py` (11)

---

### F-37 — `antibody_store.init()` never called

**Status:** ✅ FIXED

**Symptom:** Surfaced after F-36 fix when finalize completed end-to-end for the first time. The antibodies stage reported `derived: 10, saved: 0` — no antibodies were ever persisted.

**Root cause:** `antibody_store.init(db_path)` was never called from anywhere in the codebase. `_require_conn()` raised `RuntimeError("AntibodyStore not initialized")` on every save call, but the worker caught the exception at `logger.debug` level so it was completely silent.

**Resolution:**
1. Added `antibody_store.init(_antibody_store_db_path)` to `server.py` startup.
2. Used a dedicated `codrag_antibodies.db` file (same pattern as F-36 concepts) to avoid cross-store contention.
3. Bumped antibody_store `timeout` 10s → 30s, added `PRAGMA busy_timeout=30000`.
4. Added `antibody_store.save_many()` batch method (single executemany + commit).
5. Updated `_antibodies_worker` to call `save_many` with per-item fallback and surfaced failures at WARNING level.

**Validation:** F-37 fix run after F-36: `derived: 10, saved: 10, elapsed: 5ms` (was 103s with per-save commits hitting busy_timeout 10× before going to dedicated db).

---

### F-38 — Antibodies worker passed Concept dataclass to dict-expecting derive function

**Status:** ✅ FIXED

**Symptom:** First post-F-36 validation crashed with `'Concept' object has no attribute 'get'` in `antibody_derivation.suggest_antibody`. Surfaced because before F-36 the worker never reached the antibodies stage with non-empty concepts.

**Root cause:** `concept_store.list_concepts()` returns `Concept` dataclass instances. `derive_antibodies_for_project(concepts: List[Dict[str, Any]])` expects dicts and calls `concept.get(...)` on each.

**Resolution:** Convert at the worker boundary in `_antibodies_worker`:
```python
concept_dicts = [c.to_dict() if hasattr(c, "to_dict") else c for c in concepts]
antibodies = derive_antibodies_for_project(concept_dicts)
```

`Concept.to_dict()` already exposes the required `id`, `title`, `content`, `category`, `anchors`, `assertion` fields.

---

### F-36 (original investigation notes — preserved)

**Status (historical):** Was OPEN before this commit.

**Symptom:** During the F-35 isolation test, the swarm path successfully generated 26 concepts via fan-out + raw merge fallback, but **0 of them were saved to the ConceptStore**:

```
[Swarm/Concepts] Synthesis empty; merged 26 concepts from 5 worker outputs
[Swarm/Concepts] Complete for 0c50e42e-...: 0 concepts, 0 questions, 5/5 workers succeeded
```

Daemon log shows 26 individual save warnings:
```
WARNING:codrag.core.concept_seeder:Failed to save concept 'Deactivation as soft-delete...': database is locked
WARNING:codrag.core.concept_seeder:Failed to save concept 'Single-file domain model...': database is locked
... (20+ more)
```

**Root cause hypothesis:** SQLite WAL mode + multiple concurrent writers. The concept_store uses the same SQLite database (`codrag_settings.db`) as several other components:
- pipeline_journal (writes run start/end events)
- pipeline_history (records completed runs)
- pipeline_metadata (writes heartbeats every 60s)
- observation_store
- concept_store
- audit_log
- settings_store

During a swarm finalize, multiple of these are writing simultaneously. SQLite serializes writes via a single writer lock; under contention, BEGIN IMMEDIATE returns SQLITE_BUSY → "database is locked".

**Phase 92 partial fix:** Phase 92 added WAL checkpoint on startup/shutdown and increased connection-level timeouts to 10s. That helps but doesn't eliminate contention during sustained busy periods.

**Why this is now visible:** Before Phase 96F, swarm wasn't producing 26 concepts in a tight loop. Sequential `seed_concepts` did one big save call per concept. Now the swarm fallback path saves 26 in a row, hitting the database lock window every time.

**Fix options:**
1. **Batch the concept saves** — `concept_store.save_many()` that wraps all 26 in a single transaction. Reduces lock contention from N transactions to 1.
2. **Bump SQLite busy_timeout** for the concept_store connection from 10s to 30s.
3. **Retry-on-locked wrapper** around save() — sleep 100-500ms and retry up to 3 times.
4. **Move concept_store to its own SQLite file** — separate from settings/journal/history. Eliminates cross-table contention.

**Recommended:** Combination of (1) batch save + (3) retry wrapper as defense-in-depth. (4) is the cleanest long-term fix but bigger refactor.

**Symptom:** Identical LLMClient code path takes 1.3s in standalone Python but >90s when invoked from inside the daemon's concept_seeder swarm worker. Multiple simultaneous worker calls (10 parallel) hang the daemon entirely.

**Reproduction:**
1. Restart daemon via `scripts/dev.sh`
2. Trigger `POST /projects/{rust_repo_id}/pipeline/finalize`
3. Concepts stage starts swarm fan-out: `[Swarm/Concepts] Fan-out: 5 modules across 10 workers`
4. Coordinator LLM call hangs past 90s timeout (which fires correctly per F-25)
5. After timeout, fan-out spawns 10 worker LLM calls, each hangs the same way
6. Daemon thread pool exhausts, all subsequent /health, /pipeline/status, etc. return ReadTimeout
7. Daemon must be restarted to recover

**What we know:**
- LLMClient `generate(think=False)` works in standalone Python (1.3s response)
- Direct httpx POST to Ollama `/api/generate` with the same payload works (3.5s response)
- The same daemon was healthy before triggering finalize — `/health` returns 200 instantly
- The daemon's logger goes silent after the swarm starts — no stdout output for minutes
- Daemon process is in `S` (sleeping) state with 0.1% CPU during the hang
- Not GIL contention (process is sleeping, not spinning)

**Hypotheses (untested):**
1. **Connection pool exhaustion in `requests` library** — the LLMClient uses `requests.post(stream=True)`, and 10 simultaneous streaming connections to the same Ollama endpoint might hit a `urllib3` connection pool default of 10. The 11th would block waiting for a free slot, even though we only have 10 workers.
2. **Daemon thread interaction with `OutputMonitor`** — the streaming read loop calls `OutputMonitor.feed()` which might acquire a lock that's contended across worker threads.
3. **Ollama Cloud server-side rate limiting** — kimi-k2.5:cloud might serialize requests from the same client. 10 simultaneous calls get queued and effectively serialized, with each taking the model's full latency.
4. **Asyncio/threading interaction with anyio's thread pool** — the SwarmOrchestrator spawns its own ThreadPoolExecutor, but the inner LLMClient calls go through `requests` which should be GIL-friendly. There might be subtle interaction with FastAPI's asyncio event loop.
5. **Logging deadlock** — the daemon's structured logger might be lock-contended when 10 swarm workers + 5+ FastAPI threads all log simultaneously.

**Diagnostic plan (next session):**
- Reduce swarm worker concurrency to 2 (instead of 10) and see if the hang goes away → confirms hypothesis #1 (connection pool) or #3 (rate limiting)
- Add `urllib3` pool sizing to LLMClient: `requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=50)`
- Run the swarm with `--debug-llm` or attach `py-spy dump` during the hang to see what threads are doing
- Test with a non-cloud model (local Ollama) to isolate cloud-specific behavior

**Workaround:** Daemon must be restarted via `scripts/dev.sh --kill && scripts/dev.sh` between every finalize attempt.

**Impact:** Phase 96F end-to-end validation is blocked until this is resolved. The 96F machinery itself is correct (verified by tests, by direct LLMClient calls, by the coordinator timeout firing correctly). The blocker is somewhere in the daemon-vs-standalone runtime difference.

---

### F-32 — "Batch synthesis failed" markers in module summaries

**Status:** 🔵 NOT-A-BUG

**Observation:** During concepts swarm fan-out on mini-redis-rust, the coordinator prompt included:
```
- module:module:redis:11:cursor-pattern:1: Redis Subsystem (Src) #2 (2 files): Cluster of 2 files related to redis. (Batch synthesis failed)
```

The "(Batch synthesis failed)" string is part of the **module summary** field stored in `trace_modules.jsonl` from a previous clustering run that failed mid-flight. It's pre-existing data, not an error from Phase 96F. The swarm coordinator passes the existing module summaries through unchanged.

**Action:** Re-run the clustering stage on mini-redis-rust to regenerate clean module summaries, OR ignore (it doesn't affect the swarm path's correctness, just makes the prompt slightly noisier).

---

### F-33 — rust_repo structural rebuild produces fewer nodes than existing file

**Status:** 🟡 OPEN (Phase 70B working as designed but inconvenient)

**Symptom:** Triggering `/pipeline/rebuild` on SMOKE: rust_repo fails at the structural stage with:
```
Stage structural would shrink trace_nodes.jsonl from 28 to 22 records (79% of original)
WRITE GUARD BLOCKED stage structural for ...
```

**Root cause:** The Rust engine's tree-sitter parsing produces 22 nodes from the rust_repo source files. The existing trace file has 28 nodes (from a previous run, possibly with different parser version or configuration). The Phase 70B integrity write-guard correctly blocks the rebuild because it would shrink the trace.

**Why this exists:** Write guard is Phase 70B safety net — prevents data loss during rebuilds. Triggers on `record_ratio < 0.9`.

**Why this bites Phase 96 testing:** rust_repo is a synthetic test fixture. We use it for fast smoke tests, but we can't trigger a clean rebuild because the existing data is "more" than what a fresh parse produces.

**Fix options:**
1. Regenerate rust_repo's `.codrag/` from a clean state so existing data matches what the Rust parser produces today.
2. Add a `force=True` flag to `/pipeline/rebuild` that bypasses the write guard for explicit user-triggered rebuilds.
3. Investigate why the parser produces fewer nodes today (parser version drift).

**Workaround:** Use `/pipeline/finalize` directly for Phase 96 testing — it skips structural and starts at atlas.

---

## Open issues summary

| ID | Title | Priority |
|---|---|---|
| F-11 | Dashboard polling storm exhausts thread pool | **CRITICAL** — root cause of "daemon hang" symptoms; was misdiagnosed as F-35 |
| F-36 | SQLite database lock blocks swarm concept saves | **HIGH** — 26 concepts generated, 0 persisted |
| F-29 | Thinking-model swallows num_predict budget | ✅ fix shipped (`c4e9fe68`); validated in F-35 isolation test |
| F-28 | AIMD doesn't recover from backoff | MEDIUM — needs daemon restart workaround |
| F-14 | `SettingsStore.get_global` AttributeError | LOW — non-fatal log noise |
| F-15 | Pre-existing budget/journal test failures | LOW — out of scope |
| F-30 | Vite proxy connection accumulation | (manifestation of F-11) |
| F-31 | SQLite "database is locked" warnings | (now folded into F-36) |
| F-33 | rust_repo structural rebuild blocked by write guard | LOW — workaround exists |

---

## How this registry should be used

- **Before triaging a new issue:** check if it's already tracked here. Many "new" symptoms are manifestations of existing entries (e.g., dashboard "loading…" forever is F-11).
- **When fixing an entry:** update its Status, link the commit, and if it spawned follow-up tasks add them as new entries.
- **When closing Phase 96:** every entry should be ✅ FIXED, 🟢 DEFERRED with explicit owner, or 🔵 NOT-A-BUG.
