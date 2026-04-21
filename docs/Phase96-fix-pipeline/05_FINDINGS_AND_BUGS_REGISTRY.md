# Phase 96: Findings and Bugs Registry

**Last updated:** 2026-04-11 (F-11, F-14, F-28, F-29, F-30, F-31, F-36, F-37, F-38, F-39 closed; only F-15 and F-33 remain open, both deferred)
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
| F-14 | `SettingsStore.get_global` AttributeError (recurring log error) | ✅ FIXED | (this commit) |
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
| F-29 | Thinking-model swallows num_predict budget on `thinking` field | ✅ FIXED | `c4e9fe68` (think=false) — daemon hang caveat resolved by F-11 |
| F-30 | Vite proxy connection accumulation (60+ ESTABLISHED to daemon) | ✅ FIXED via F-11 | (in-flight guards eliminate stacking) |
| F-31 | SQLite "database is locked" warnings on busy daemon | ✅ FIXED via F-36/F-37 | (concept_store + antibody_store moved to dedicated DB files) |
| F-32 | Pipeline log "Batch synthesis failed" markers in module summaries | 🔵 NOT-A-BUG (data quality from older clustering run) | — |
| F-33 | rust_repo structural rebuild produces fewer nodes than existing file (write guard blocks) | ✅ FIXED via F-51 + F-52 | (Danger Zone Rebuild now bypasses write guard) |
| F-34 | Swarm window cooldown (45s) blocks re-opening but doesn't reduce batch budget | ✅ NOT-A-BUG (cooldown only blocks new windows; budget query still returns full) | — |
| F-35 | "Daemon-runtime swarm hang" — was actually F-11 polling storm | 🔵 NOT-A-BUG (misdiagnosis, see entry) | — |
| F-36 | SQLite "database is locked" blocks swarm concept saves (26 generated, 0 saved) | ✅ FIXED | (this commit) |
| F-37 | `antibody_store.init()` never called — saves silently failed at DEBUG level | ✅ FIXED | (this commit) |
| F-38 | Antibodies worker passed `Concept` dataclass to `derive_antibodies_for_project` (expects dicts) | ✅ FIXED | (this commit) |
| F-39 | `project_trace_status` short-circuits to empty stub when `config.trace.enabled=False`, ignoring on-disk graph | ✅ FIXED | (this commit) |
| F-40 | `AutoRebuildWatcher._is_relevant` used `Path.match()` which doesn't honor `**` — directory excludes silently broken | ✅ FIXED | (this commit) |
| F-41 | `/system/pipeline-queue` and `/pipeline/status` block under long-running stage — 15× sequential lock acquisitions in `PipelineOrchestrator.status()` contend with worker thread state transitions | ✅ FIXED | (this commit) |
| F-42 | `GraphEnrichmentPipeline` panel: every stage gated on `trace.enabled` (auto-build flag) instead of `trace.exists` — completed stages rendered as "Disabled" / "Waiting for X" | ✅ FIXED | (this commit) |
| F-43 | Index build progress callback fires at file START, leaving bar "stuck" at previous % during slow file (e.g. 7s+ on a big markdown file) — UX shows no progression | 🟡 OPEN | — |
| F-44 | 2-tone incremental progress bar wiring (initial audit was wrong) | ✅ FIXED + audit corrected | knowledge stage `73c33828`; live validation showed catalogue/inferred_edges already wired |
| F-45 | `_start_project_knowledge_build` import fails — name doesn't exist in `codrag.server`, every `/knowledge/build` request returned 500 | ✅ FIXED | (this commit) |
| F-46 | Structural worker tries to mutate frozen `Project` dataclass — `FrozenInstanceError`, blocks all `/pipeline/fast` runs | ✅ FIXED | (this commit) |
| F-47 | `/pipeline/fast` gate doesn't recognize `phase=cancelled` — cancelled deep_enrichment runs block all subsequent fast_sync attempts until daemon restart | 🟡 OPEN | — |
| F-48 | `/pipeline/rebuild` timed out >5s on rust_repo — endpoint may be doing synchronous work that should be backgrounded | ✅ FIXED via F-46/F-51/F-52 | — |
| F-49 | 5 trace READ endpoints (`/trace/coverage`, `/trace/search` × 2, `/trace/node`, `/trace/neighbors`) raise `TRACE_DISABLED` when `config.trace.enabled=False`, ignoring on-disk graph — disconnects Graph Scope panel | ✅ FIXED | (this commit) |
| F-50 | `/projects/{id}/search` `trace_expand` skipped when `trace.enabled=false`, even with built graph on disk — same root-cause class | ✅ FIXED | (this commit) |
| F-51 | Write guard blocks Danger Zone Rebuild — `force_from_start=True` not honored, shrinkage check fires anyway | ✅ FIXED | (this commit) |
| F-52 | `force_from_start=True` silently undone by backup-restore-then-redetect path — Danger Zone Rebuild completed in 0.0s without doing any work | ✅ FIXED | (this commit) |
| F-53 | Graph Scope Queue tab renders empty when no untraced/stale files — daemon returns `traced` array but dashboard never displays it; coverage fetch also gated on `trace.enabled` | ✅ FIXED | (this commit) |
| F-54 | `/pipeline/finalize` hangs 30s on `journal.start_run()` — pipeline_journal still shared `codrag_settings.db` (same pattern F-36 fixed for concept_store and F-37 for antibody_store) | ✅ FIXED | (this commit) |
| F-55 | Three more stores still shared `codrag_settings.db` (`pipeline_history`, `token_telemetry`, `observation_store`) → "database is locked" warning + intermittent settings save failures | ✅ FIXED | (this commit) |
| F-56 | Manual/Auto/Schedule mode global instead of per-project — switching projects carried over the previous project's mode and triggered cross-project Phase 81 auto-pauses | ✅ FIXED | (this commit) |
| F-47 | `/pipeline/fast` gate doesn't recognize `phase=cancelled` — cancelled deep_enrichment runs block all subsequent fast_sync attempts until daemon restart | ✅ FIXED | (this commit) |
| F-43 | Index build progress callback fired with `(i+1)/total` at file START — bar appeared "stuck" at the previous % during slow files | ✅ FIXED | (this commit) |
| F-59 | Swarm hang — 4-layer onion: coordinator zombie thread, urllib3 pool exhaustion, shared Session blocking, iter_lines() hang on cloud models | ✅ FIXED | `0ee05575` (5 commits) |
| F-60 | Finalize stage statuses not hydrated on project switch — concepts/rules/audit/antibodies show "Not seeded" even when complete | ✅ FIXED | `2c523e2a` |
| F-61 | Finalize running state not detected during hydration — switching to project mid-finalize shows static "Not seeded" instead of spinner | ✅ FIXED | `2c523e2a` |
| F-62 | `/system/pipeline-queue` endpoint hangs indefinitely during swarm execution — lock contention between swarm worker threads and sync queue builder | ✅ FIXED | `2c523e2a` |

| F-63 | PUT /projects drops `ignore_patterns` and `auto_config` — Exclude Tree selections vanish on every config save | ✅ FIXED | `f9c3f6d6` |
| F-64 | PAUSED pipeline groups allow concurrent group starts — Knowledge Embedding + Deep Reasoning run simultaneously | ✅ FIXED | `b04314c1` |
| F-65 | Manual/Auto toggles revert to global on project switch — `useProjectManager` dropped `auto_config` during hydration + backend auto-run read global not per-project | ✅ FIXED | `2e93ad88`, `47e989da` |
| F-66 | Two-tone progress bar baseline lost on page refresh | 🟡 OPEN | — |
| F-67 | Daemon restart loses incremental progress — old manifests falsely claim completion + mtime sync defeats rebuild | ✅ FIXED | `1bc783ed`, `9dc9091f` |
| F-68 | No "interrupted incremental" concept in recovery — should show "Resume" not "Run" | 🟡 OPEN | — |
| F-69 | Inactive projects bypass all pipeline guards — recovery hydration + auto-run + watcher all ignore active status | ✅ FIXED | `784d6831`, `467d7b5e`, `0980b492` |

Total: **69 findings**, **63 fixed**, **3 open** (F-15 test rot, F-66 two-tone persistence, F-68 resume UX), **2 deferred**, **2 not-a-bug**. The 2 settings_store WAL tests now correctly skip on the production DELETE-mode codebase. The remaining F-15 failures (resume_strategy, mcp_server, queue_router, trace_builder_globs, team_sync_integration, etc.) are pre-existing test rot from earlier phases and are out of Phase 96 scope.

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

**Validation:** TypeScript compiles cleanly for all 6 modified files (only 3 pre-existing unrelated `EnrichmentAutoConfig` schema errors in `useTraceSystem.ts:114-139` remain).

**Live validation (added later via Playwright):** Drove the dashboard with headless Chromium against the running `scripts/dev.sh` stack while sampling `lsof -nP -iTCP:8400 -sTCP:ESTABLISHED` once per second for 60s, including a click-into the CoDRAG project to start per-project polling. Results:

```
samples:           57
duration_s:        60
min_connections:    4
max_connections:   20
p50_connections:    6
p95_connections:   18
mean_connections:  7.8
samples_above_20:   0  (was the threshold)
samples_above_40:   0  (was the historical broken baseline midpoint)
```

The historical broken baseline observed during the F-35 misdiagnosis was 60+ ESTABLISHED connections that never drained. After the fix the steady-state max never exceeded 20, the median sat at 6, and zero samples exceeded the threshold. **F-11 fully validated end-to-end.**

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

**Status:** ✅ FIXED

**Symptom:** Recurring error in daemon logs:
```
ERROR:codrag.api.routers.settings:Security health check failed:
  'SettingsStore' object has no attribute 'get_global'
```

**Root cause:** Two non-existent methods were being called on the `SettingsStore` singleton in 9 places across `src/codrag/api/routers/settings.py` and `src/codrag/core/llm_client.py`:
- `store.get_global("active_project")` — should be `store.get("active_project")`. The store has a `.get()` method for global settings; there is no `.get_global()`.
- `store.get_project(active_id, "root_path")` — should be `store.project_get(active_id, "root_path")`. The store uses `project_get`/`project_set`/`project_delete` for the per-project namespace; there is no `.get_project()` (that name belongs to `ProjectRegistry`, a different class).

Every call site was wrapped in `try/except Exception: logger.warning(...)`, so the bug failed silently as recurring log noise instead of breaking functionality. The actual functionality (loading admin policy, redact patterns, etc.) was never working — it was always falling through to the default permissive policy.

**Fix:** Renamed all 9 call sites to the correct method names. Both modules import cleanly and the routers no longer raise `AttributeError`.

**Validation:** Smoke imports of both modules succeed. 37 settings_store tests pass; the 2 WAL-mode failures (`test_close_checkpoints_wal`, `test_wal_checkpoint_on_init_recovers_stale_wal`) reproduce on origin/main without these changes — pre-existing F-15 territory, related to the SettingsStore using `journal_mode=DELETE` to dodge USB-drive WAL corruption.

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

**Status:** ✅ FIXED in `c4e9fe68` (think=false). The "daemon-runtime hang" caveat noted below was a misdiagnosis (F-35 → F-11) and has been resolved by the F-11 dashboard polling reduction. The think=false fix was always correct and sufficient.

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

### F-43 — Index build progress bar appears stuck on slow files

**Status:** 🟡 OPEN

**Symptom:** When the user clicks **Rebuild** on a project, the bar in `IndexStatusCard` (top of card) appears stuck at one percentage (e.g. `20%` for `AGENTS.md`) for many seconds, then suddenly sweeps through the remaining files in well under a second. Eric: "the UI is updating faster and not hanging, but also it never really loads the current state and looks to be in a broken state."

**Verified via SSE listener** (`/tmp/sse_listener.py`) — force rebuild on rust_repo, listening on `/events`:
```
[ 1.62s]  20% Indexing AGENTS.md          ← file 1 starts
[10.16s]  40% Indexing README.md          ← AGENTS.md took 8.5s, file 2 starts
[10.36s]  60% Indexing src/main.rs        ← +0.2s
[10.56s]  80% Indexing src/models.rs      ← +0.2s
[10.96s] 100% Indexing src/service.rs     ← +0.4s
```

So the daemon IS sending one event per file with correct percentages. But the callback fires at the *start* of each file's processing (`src/codrag/core/index.py:463`):
```python
for i, file_path in enumerate(filtered_files):
    rel_path = ...
    if progress_callback:
        progress_callback(rel_path, i + 1, total_files)
    # ... reading + chunking + embedding happens AFTER
```

This means a slow file leaves the bar at the *previous* percentage for the entire duration. For `AGENTS.md`, the bar reads `20% (1/5)` for 8.5 seconds — looks frozen even though the daemon is correctly working through file 1.

**Fix options (none shipped yet):**
1. **Move callback to end of loop** — bar shows "completed N files" instead of "starting file N+1". Still has the slow-file freeze, but at least the bar updates after long work.
2. **Sub-file progress** — emit progress per *chunk*, not per file. A 50-chunk file fires 50 events instead of 1.
3. **Heartbeat events** — emit a "still working on N" event every 2-3 seconds during a slow file so the bar doesn't appear frozen.

(2) is the most user-visible but most invasive. (3) is the smallest fix.

---

### F-44 — 2-tone incremental progress bar wiring (initially mis-audited)

**Status:** ✅ FIXED + initial audit was wrong

**Original symptom:** Eric: "test the incremental and you should see 2-toned progress bars". On an incremental build, `StageProgressBar` should render a green section (already-done) plus an orange section (currently being re-processed). I claimed in the initial audit that this was dead code in 14/15 stages because only `epistemic_enrichment.py:781` passed `baseline > 0` to `progress_cb`.

**That audit was wrong.** Multiple workers ALREADY pass baseline correctly via different patterns:

| Stage | File | Pattern |
|---|---|---|
| `inferred_edges` | `core/inferred_edges.py:392, 422, 483` | Passes `already_done` as baseline directly |
| `catalogue` (augment) | `core/augmenter.py:1607-1612` | Wraps `progress_callback` with a closure that injects `_skip_offset` as baseline |
| `enrichment` (epistemic) | `core/epistemic_enrichment.py:781, 1004` | Passes `existing_count` as baseline |
| `knowledge` | `core/knowledge.py:507-538` | F-44 fix: passes `docs_reused` as baseline |

The audit error was looking only for literal `progress_baseline=` assignments and missing the augmenter's callback-wrapping pattern. The `_logged_progress` wrapper at `pipeline/workers.py:254` already accepted 4 args and forwarded `baseline` correctly — so any worker that passed it through would activate the 2-tone bar.

**Live validation (this run):** Triggered an incremental fast_sync on rust_repo after adding `src/f44_demo.rs`. `/pipeline/status` reported during the catalogue stage:

```
inferred_edges: cur=1 tot=1 BASE=3 phase=completed     [2-TONE]
catalogue:     cur=22 tot=24 BASE=21 phase=running     [2-TONE]
```

`progress_baseline > 0` flowing live through `BuildSlot → /pipeline/status → StageProgressBar.computeStageRerun()`. The pipeline log confirmed the build completed in 65.6s, with `knowledge_documents.json: 35 → 37 records (+2)` matching the new file's chunks exactly.

**What this commit shipped (still useful):**
- `core/knowledge.py` — wired `docs_reused` as baseline through the embedding loop. Knowledge stage now activates 2-tone alongside the others.
- `services/headless_runner.py::_make_progress_cb` — accepts and ignores the 4th `baseline` arg so the harness logger doesn't `TypeError` on the new wider signature.
- `services/build_manager.py::_project_knowledge_build_worker` — same 4-arg widening for the standalone `/knowledge/build` SSE path (the SSE event stream still doesn't carry baseline; that's a separate enhancement).

**Stages still missing baseline wiring** (would benefit but not blocking):
- Structural Graph (Rust trace builder — could surface "files reused from AST cache")
- Module Synthesis (could surface cached module summaries)
- Concepts (could surface already-seeded modules)
- Audit (could surface cached findings)

These are nice-to-haves; the core 2-tone bar is now demonstrably working for inferred_edges, catalogue, knowledge, and enrichment.

---

### F-42 — `GraphEnrichmentPipeline` panel ignores `trace.exists`, gates everything on `trace.enabled`

**Status:** ✅ FIXED

**Symptom:** Eric: "the pipeline shows a bunch of tasks that look to be incomplete before other complete stages. that's impossible, I believe these states are actually complete." For the CoDRAG project (21,531 trace nodes, 65,124 edges, 602 modules, atlas built, all on-disk artifacts present), the dashboard's Graph Enrichment panel rendered:

- Structural Graph: **Disabled**
- Edge Discovery: **Waiting for graph**
- Fast Catalogue: **Waiting for graph**
- Relationship Validation: **Waiting for catalogue**
- Knowledge Embedding: **Waiting for catalogue**
- Deep Reasoning: **Waiting for catalogue**

…even though every one of those stages had complete data on disk.

**Root cause:** Same family as F-39, but on the dashboard side. Every `compute*State` function in `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` started with:
```typescript
if (!trace.enabled) return 'disabled';
```

`trace.enabled` is the **auto-build preference flag**, not "data exists". When a project has `config.trace.enabled=False` (the CoDRAG default — its config is just `{"active": true}`), every downstream stage short-circuited to `disabled` regardless of actual on-disk state. F-39 fixed the daemon side so `trace.exists=true` is reported correctly, but the dashboard was still gating on the wrong field.

**Fix:** Replace `if (!trace.enabled) return 'disabled'` with `if (!trace.exists && !trace.enabled) return 'disabled'` in 4 functions, and simplify the two functions that already had `!trace.enabled || !trace.exists` to just `!trace.exists`. Six call sites total in `compute{Trace,InferredEdges,Augment,Validation,Epistemic,FastKnowledge}State`.

**Validation (live, via Playwright):** Re-captured the dashboard for CoDRAG after rebuilding the dashboard. Every stage in Graph Enrichment now renders as ✓ complete:
- Structural Graph ✓
- Edge Discovery ✓
- Fast Catalogue ✓
- Relationship Validation ✓
- Knowledge Embedding ✓
- Deep Reasoning ✓
- Group Reasoning ✓ (Analyzed)
- Module Synthesis ✓ (602 modules)
- Continuous Deepening ✓
- Deep Knowledge Embedding ✓

This was the surface expression of "the dashboard looks broken / never loads the current state" — the data was there, the dashboard just refused to admit it.

**Family note:** F-39 (daemon-side trace status) + F-42 (dashboard-side trace stage rendering) together close the entire "fully-built project shows as needing initialization" failure mode. Both bugs were the same conceptual error (treating an auto-build preference flag as a data-presence flag), at different layers of the stack.

---

### F-40 — `AutoRebuildWatcher._is_relevant` glob matching silently broken for directories

**Status:** ✅ FIXED

**Symptom:** During the CoDRAG self-swarm validation (task #17), the pipeline log filled up with:
```
[codrag.services.build_manager] Indexing .claude/worktrees/busy-swirles/AGENTS.md
[codrag.services.build_manager] Indexing .claude/worktrees/busy-swirles/CLAUDE.md
[codrag.services.build_manager] Indexing .claude/worktrees/busy-swirles/backend_config.py
...
```

`.claude/worktrees/` is where Claude Code stages parallel-task git worktrees. Each worktree is a near-complete copy of the repo. The CoDRAG project's policy correctly listed `**/.claude/**` in `exclude_globs`, and `.claude` is also in `DEFAULT_EXCLUDE_DIR_NAMES` — but the watcher was reporting these files as "relevant" anyway and triggering delta builds that walked the duplicated repo.

**Root cause:** `AutoRebuildWatcher._is_relevant` (in `src/codrag/core/watcher.py`) used `pathlib.Path.match()` to check exclude patterns. **`Path.match()` does NOT support the recursive `**` wildcard the way fnmatch / gitignore-style globs do** — every directory-level exclude pattern silently failed to match.

Verified empirically:
```python
>>> Path(".claude/worktrees/busy-swirles/backend_config.py").match("**/.claude/**")
False
>>> Path(".claude/worktrees/busy-swirles/backend_config.py").match(".claude/**")
False
>>> import pathspec
>>> pathspec.PathSpec.from_lines("gitignore", ["**/.claude/**"]).match_file(...)
True   # ✓
```

This silently broke `.claude/`, `.git/`, `.prep/`, `.venv/`, `node_modules/`, and **every other directory exclude in every project's policy**. Files inside those dirs were being reported as relevant, triggering repeat builds. The build_manager DID filter correctly when called directly (CodeIndex.build uses pathspec internally), but the watcher's pre-filter let bad paths through, and the delta-build path took those paths as `roots` and re-indexed them.

**Fix:** Replace `Path.match()` with `pathspec.PathSpec.from_lines("gitignore", ...)`. The rest of the codebase already uses pathspec for exactly this — the watcher was an outlier. Switched from the deprecated `gitwildmatch` dialect to `gitignore` to silence the deprecation warning.

```python
# BEFORE
for pat in exclude_globs:
    if Path(rel_posix).match(pat):  # silently fails on **/...
        return False

# AFTER
import pathspec
if exclude_globs:
    if pathspec.PathSpec.from_lines("gitignore", exclude_globs).match_file(rel_posix):
        return False
```

**Tests:** New `tests/test_watcher_relevance.py` with 19 cases covering:
- 4 `.claude/worktrees/...` paths (the original bug)
- 7 other default-exclude directories (`.git`, `.codrag`, `.venv`, `node_modules`, including a nested `src/foo/node_modules/...`)
- 5 normal include paths (`.py`, `.md`, `.ts`, `.tsx`, plus a `.sh` that's excluded by include_globs)
- Lock files, empty include_globs, empty both lists

All 19 pass. Full watcher test suite (31 tests across `test_watcher_relevance`, `test_watcher_staleness`, `test_immune_watcher`) is green.

**Existing projects** still have polluted indexes from the broken watcher. Workaround: rebuild from scratch (`Knowledge Base Status → Rebuild`) to drop the worktree-derived chunks. The watcher will no longer re-add them.

**Related:** This fix structurally subsumes the memory note about AGENTS.md being noise in the trace graph — every dotfile dir-exclude now actually works.

---

### F-41 — `/pipeline/status` and `/system/pipeline-queue` block during long-running stage

**Status:** 🟡 OPEN — root cause identified, fix sketched

**Symptom:** During any sufficiently long pipeline run (concept seeding fan-out, knowledge embedding on a USB drive, multi-stage incremental fast_sync), `/health` continues responding in 1-7ms, but `/pipeline/status` and `/system/pipeline-queue` start timing out at 30s+. Eventually `/health` itself wedges and the daemon needs a manual restart.

**Mechanism (identified during F-44 live validation):**

`PipelineOrchestrator.status()` at `services/pipeline/orchestrator.py:932` does this:

```python
def status(self, project_id: str) -> Dict[str, Any]:
    with self._lock:                          # 1. PipelineOrchestrator lock
        fast_run = self._runs.get(...)
        deep_run = self._runs.get(...)
        fin_run  = self._runs.get(...)

    stage_statuses = {}
    for stage_id in list(StageId):              # 15 iterations
        bt = STAGE_BUILD_TYPE[stage_id]
        slot = self._orchestrator.status(...)   # 2. BuildOrchestrator lock per call
        stage_statuses[stage_id.value] = slot.to_dict()
```

The loop acquires `BuildOrchestrator._lock` 15 separate times. While most of those acquisitions are individually fast, ANY one of them can block if the pipeline is mid-stage and another caller is holding the same lock for any reason (state transition, slot creation, zombie check). With 15 sequential lock acquisitions per status call AND the dashboard polling status every few seconds AND multiple groups (fast/deep/finalize) running, contention is essentially guaranteed.

The pipeline-status FastAPI handler runs in its own ThreadPoolExecutor (max 4 workers), so this isn't FastAPI thread pool exhaustion (F-11 territory). It's contention on the actual orchestrator locks. When all 4 status executor threads are blocked, subsequent status requests pile up, and eventually the daemon's main FastAPI thread pool fills with awaiting status calls.

**Why this is distinct from F-11:** F-11 was about request *stacking* exhausting the FastAPI thread pool. F-41 is about a single request blocking on a contended internal lock — different mechanism, similar surface symptom.

**Fix sketch (not yet implemented — risks deadlock if rushed):**

Option A — single-call snapshot read:
```python
def status_snapshot(self, project_id: str) -> Dict[str, Any]:
    """Lock-free read from cached stage_snapshots already maintained by workers."""
    # PipelineGroupStateMachine already maintains _stage_snapshots that are
    # updated by progress_cb. Read those instead of walking BuildOrchestrator slots.
    ...
```

Option B — bounded lock acquisition with stale fallback:
```python
acquired = self._orchestrator._lock.acquire(timeout=2.0)
if not acquired:
    return self._last_known_slot_state[stage_id]  # cached
try:
    ...
finally:
    self._orchestrator._lock.release()
```

Option C — split BuildOrchestrator lock into read/write:
- `_state_lock`: held briefly during transitions
- Snapshot data lives outside the lock and is updated atomically

Option A is least invasive. Option C is the cleanest long-term fix.

**Workaround:** Restart the daemon. Confirmed to clear the wedge every time.

**Live observations:**
- During F-44 validation (incremental fast_sync, 65.6s), `/pipeline/status` started timing out around the 25-second mark mid-catalogue. By 60s the daemon needed a restart.
- During the original F-35 misdiagnosis era (rust_repo finalize swarm), the same pattern hit — was originally attributed to FastAPI thread pool (F-11) but the underlying lock contention is separate.

---

### F-39 — `project_trace_status` short-circuits to empty stub when config flag is False

**Status:** ✅ FIXED

**Symptom:** Eric reported "I see issues with the codrag data after I ran scripts/dev.sh — it says initialize but I know it's been built in .codrag". The dashboard was showing CoDRAG with the "Initialize Trace Graph" panel and Knowledge Base Status reading 0 Code / 0 Docs / 0 Graph / 0 Total / "No project loaded", even though `.prep/trace_nodes.jsonl` (8.6 MB, 21,531 lines) and `trace_edges.jsonl` (31,459 lines) had been written that morning.

**Root cause:** `services/project_helpers.py::project_trace_status()` checked `project.config.trace.enabled` and short-circuited to an empty stub if the flag was False — without ever consulting `TraceIndex.status()` or the on-disk files. The CoDRAG project's config is `{"active": true}` with no `trace` key, so `enabled` came out False, and the daemon advertised the project as having no graph.

```python
# BEFORE
enabled = bool((trace_cfg or {}).get("enabled", False))
if not enabled:
    return {"enabled": False, "exists": False, "counts": {"nodes": 0, "edges": 0}, ...}
trace_idx = bm.get_project_trace_index(project)
status = trace_idx.status()
```

This short-circuit also masked the same condition for any project where the user (or a pipeline run) built the graph but never flipped the config flag to True. `TraceIndex.status()` itself correctly probes the disk and reports counts; the daemon just never called it.

**Resolution:** Always probe the on-disk index via `trace_idx.status()` and merge the config flag in as the `enabled` field separately. The flag now means "auto-build preference" — existing data is reported regardless.

```python
# AFTER
enabled = bool((trace_cfg or {}).get("enabled", False))
try:
    trace_idx = bm.get_project_trace_index(project)
    status = trace_idx.status()
except Exception as e:
    return {"enabled": enabled, "exists": False, ..., "last_error": str(e)}
status["enabled"] = enabled
status["building"] = bm.is_project_trace_building(project.id)
return status
```

**Validation (live, via Playwright + curl):**

Before:
```json
"trace": {"enabled": false, "exists": false, "counts": {"nodes": 0, "edges": 0}}
```
Dashboard: "Initialize Trace Graph", 0 / 0 / 0 / 0, "No project loaded".

After (same project, post-restart):
```json
"trace": {
  "enabled": false, "exists": true, "building": false,
  "counts": {"nodes": 21531, "edges": 32562},
  "engine": "python", "degraded": false, ...
}
```
Dashboard: 68 Code, 593 Docs, 21.5k Graph, 661 Total. The Graph Enrichment panel shows the full enrichment pipeline with stage names, and Module Synthesis even reports "602 modules · 602 files".

**Knowledge Sources panel:** Initially appeared empty in the first post-fix capture, but a longer Playwright wait (~8s) showed it populating correctly with `codrag_data`, `docs`, `engine`, `logs`, `overnight_results`, `packages`, etc. The empty render was just the pre-fetch state — the panel reads from `useFileSystem.fetchFileTree`, which fires asynchronously after `selectedProjectId` changes. Not a separate bug.

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
1. Regenerate rust_repo's `.prep/` from a clean state so existing data matches what the Rust parser produces today.
2. Add a `force=True` flag to `/pipeline/rebuild` that bypasses the write guard for explicit user-triggered rebuilds.
3. Investigate why the parser produces fewer nodes today (parser version drift).

**Workaround:** Use `/pipeline/finalize` directly for Phase 96 testing — it skips structural and starts at atlas.

---

## `config.trace.enabled` audit (post F-39 / F-42 / F-49 / F-50)

Eric asked us to make sure `config.trace.enabled` is still functioning as designed after the F-39 / F-42 / F-49 / F-50 round of fixes. **The flag's design intent is "auto-build preference" — it controls whether the watcher and auto-trigger paths kick off builds, NOT whether on-disk data is served to readers.** Every use of the flag in the codebase now falls into one of two correct categories:

### KEEP — Auto-build / write-side gates (correctly respect the flag)

| File | Line | Purpose |
|---|---|---|
| `services/pipeline/workers.py` | 303-314 | Post-build update_project: if a manual structural build succeeded, flip enabled=true so the watcher will pick up future changes. F-46 area. |
| `api/routers/projects/watch.py` | 111 | Watcher trigger gate — only auto-fast-sync when enabled=true. **Without this, every project would auto-build on file changes regardless of preference.** |
| `api/routers/projects/crud.py` | 383 | `_activate_project`: only start the watcher / auto-sync setup for trace-enabled projects. |
| `api/routers/settings.py` | 308 | "Auto-mode activated" trigger: only run fast_sync for trace-enabled projects when global auto-mode is flipped on. |
| `api/routers/settings.py` | 332 | Same, for deep enrichment auto-mode. |
| `api/routers/trace_routes/query.py` | 55 | `/trace/build` POST gate — refuses to build trace when explicitly disabled. The only TRACE_DISABLED gate that survived F-49. |
| `server.py` | 846 | Startup auto-run: only auto-build trace-enabled projects on daemon start. |
| `dashboard/src/hooks/useTraceSystem.ts` | 328 | `handleRunFastSync`: when the user clicks "Run Fast Sync", auto-flip trace.enabled=true so the watcher takes over going forward. |

### KEEP — Status display fields (expose the flag value, don't gate on it)

| File | Line | Purpose |
|---|---|---|
| `api/routers/pipeline.py` | 253 | Returns `{"enabled": ..., "exists": ..., "stats": ...}` so clients can show both the preference and the data state. |
| `api/routers/knowledge.py` | 120 | Same shape, /engine/status endpoint. |
| `mcp/tool_hi.py` | 82 | MCP `codrag` tool extracts the flag for the orientation summary. |
| `cli.py` | 497 | CLI `status` command displays "Enabled but Not Built" / "Disabled" / "Ready" tri-state correctly using both `exists` and `enabled`. |
| `core/team_config.py` | 74, 133 | `trace_enabled_default` — team-config feature flag for new projects. |

### FIXED — read-side false negatives that conflated preference with data presence

| ID | File | Fix |
|---|---|---|
| F-39 | `services/project_helpers.py::project_trace_status` | Always probe disk via `trace_idx.status()`, expose `enabled` as a separate field. |
| F-42 | `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (6 sites) | Every `compute*State()` function now gates on `!trace.exists && !trace.enabled` instead of `!trace.enabled` alone. |
| F-49 | `api/routers/trace_routes/query.py` (5 sites) | Removed `TRACE_DISABLED` gate from /trace/coverage, /trace/search × 2, /trace/node, /trace/neighbors. The TRACE_NOT_BUILT check below already covers "no data on disk". |
| F-50 | `api/routers/projects/search.py:806` | `trace_expand` no longer gated on `enabled` — checks `ti.exists()` directly. |

### Borderline (not fixed, intentional design semantics preserved)

| File | Line | Why we left it alone |
|---|---|---|
| `services/project_helpers.py::check_index_staleness` | 455 | Picks `built_at` reference: trace_manifest if enabled=true, else legacy index stats. Changing this would alter staleness semantics in subtle ways (e.g., projects with both trace data AND legacy index could flip to a different staleness reading). The current behavior is "the staleness check uses the build artifact you've opted into". If a future fix is wanted, change to `prefer trace_manifest if it exists, else fall back to legacy`. |

### Net result

The flag's contract is now consistent: **`enabled` means "auto-rebuild on", `exists` means "data on disk is queryable"**. Read endpoints serve disk; write/auto-build endpoints respect the preference. The Graph Scope panel reconnects, the dashboard pipeline panel renders complete stages green, and `trace_expand` search works on built graphs even with the auto-build flag off.

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
