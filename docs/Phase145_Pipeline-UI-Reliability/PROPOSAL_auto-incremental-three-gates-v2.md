# Phase 145 Proposal — Fix the gates that silently block auto-incremental fast_sync (v2, implemented)

**Status:** Implemented. Supersedes `PROPOSAL_auto-incremental-three-gates-v1.md`,
which was revised after code-and-evidence scrutiny found its RC#3 mechanism
was contradicted by live data (see §1.5 below).

**Scope (as shipped):**
- `src/prep/api/routers/projects/watch.py` — A1 (return actual `started`), plus
  `is_building` now covers the `finalize` group and stale `queued` runs.
- `src/prep/core/watcher.py` — A2 (loop-guard replaces the "close enough" gate),
  A4 (exponential backoff on refused triggers), coverage cooldown only consumed
  on successful trigger, coverage-check self-heals stale `any_running` state.
- `src/prep/services/pipeline/orchestrator.py` — A3 (stale blocking-run
  force-reset + stub-extrapolation-risk refinement of the downstream-partial
  guard).
- `src/prep/services/pipeline/stages.py` — hoisted `SHARED_OUTPUT_STAGES`.
- `src/prep/services/pipeline/recovery.py` — both local `_SHARED_OUTPUT_STAGES`
  copies now use the hoisted constant.
- `tests/test_phase145_auto_incremental_gates.py` — 21 tests.

---

## 1. What changed between v1 and v2 (the scrutiny outcome)

### 1.1 RC#1 (close-enough gate) — confirmed as written

`watcher.py` suppressed the coverage-check backstop whenever
`stale == 0 and coverage_pct >= 95.0 and untraced <= 20`. Verified. **But the
gate's stated premise is false:** `compute_trace_coverage` only reports
*eligible* files as untraced (include/exclude globs and `max_file_bytes` are
applied upstream), so "untraced files are likely binary/generated/excluded"
cannot be true. The gate's only real value is loop-prevention against
eligible-but-*untraceable* files (the parser/worker drops them every run, so
the untraced set never shrinks). v1's option (a) — a hardcoded source-extension
list — collapsed under this analysis: matching untraced paths against the
project's include globs is a tautology, since untraced files already passed
exactly that filter.

**v2 design:** the gate is removed. In its place is a **loop guard**: if the
untraced path set is *identical* to the set at the last coverage-triggered
rebuild, the rebuild demonstrably did not resolve those files → suppress with
an escalating backoff (cooldown × 2^N, capped at 6h). Stale files
(`stale > 0`) always re-trigger. This preserves the loop protection without
ever suppressing a first rebuild attempt for legitimate source.

### 1.2 RC#2 (trigger_build always returns True) — confirmed as written

`watch.py` captured `started = run_fast_sync(...)` and returned `True`
unconditionally; the watcher's `if not started: re-queue` branch never ran.
Fixed exactly as v1 proposed. Additionally, scrutiny found the coverage-check
path **consumed the 30-minute cooldown before the trigger and ignored its
return value** — a refused trigger burned the cooldown and could not retry for
30 minutes. v2 sets `_last_coverage_trigger_at` only on a truthy return.

### 1.3 RC#3 — v1's mechanism was WRONG; the real blocker is stale in-memory runs

v1 §1.5 asserted: §2n (Immune System UI shows "Not run") →
`antibodies_manifest.json` missing → `finalize_resume = 4` →
`downstream_partial = True` → permanent block.

Scrutiny disproved every link:

1. **The §2n finding itself says the manifest IS written.** The antibodies
   worker's manifest writer runs unconditionally after the worker returns
   (orchestrator `_write_stage_manifest_and_update_run`); §2n is a UI
   count-gate bug (`count > 0` required to render complete), not a
   missing-manifest bug.
2. **Live disk state on the SourcePrep dogfood project:** all 15 stage
   manifests present and non-stub, including `antibodies_manifest.json`;
   `pipeline_run_metadata.json` shows the antibodies stage `completed` with
   `derived: 5, saved: 5`.
3. **The project's own decision telemetry records the actual skip:**
   ```json
   {"ts": "2026-06-29T15:08:57", "choice": "skip_queue_pipeline_incomplete",
    "reason": "finalize is queued",
    "deep_resume": 5, "finalize_resume": 5,
    "deep_partial": false, "finalize_partial": false,
    "blocking_run": ["finalize", "queued"]}
   ```
   Both resume points were 5/5. The block came from the **`blocking_run`
   branch** (`orchestrator.py`): a finalize run stuck in `QUEUED` state in
   `self._runs` (a queued run whose capacity notification never fired, or a
   remnant that survived a daemon restart) blocked every incremental fast_sync.
   `is_active` includes `QUEUED`, and nothing ever settled the run.

**Compounding factor found during scrutiny:** the watcher's coverage check
early-returns on `po_status.any_running` — which counts the stale queued run —
*before* reaching the heartbeat watchdog that calls `force_reset_stale_runs`.
The stale run suppressed the very mechanism that would have healed it.
Likewise, `watch.py`'s `is_building` stale-guard only covered
`("fast_sync", "deep_enrichment")` and only `phase == "running"` — a stale
**queued finalize** run was invisible to every recovery path.

**v2 A3 design (two parts):**

- **(a) Blocking-run liveness.** When `run_fast_sync` finds a blocking
  downstream run that is not user-paused, it calls the existing
  `force_reset_stale_runs(project_id)` — which only resets active runs whose
  current stage's build slot is idle and whose age exceeds the staleness
  window (600s) — and treats a reset group as non-blocking. A genuinely
  running or legitimately-queued (slot busy) run still blocks; a user-paused
  run is never reset (deliberate state). The coverage check's `any_running`
  guard got the same self-heal so the backstop path recovers without waiting
  for a filesystem event.
- **(b) Stub-extrapolation refinement of `downstream_partial`.** The guard's
  stated concern is selfheal manufacturing stub manifests from partial
  on-disk data. v1 proposed checking `STAGE_DATA_FILES`, which scrutiny showed
  is wrong in both directions: it has no entries for `rules`/`concepts`/
  `audit`/`antibodies` (zero detection), and it lists *shared* files for
  `deepening` (`trace_epistemic.jsonl` is enrichment's output), so it would
  false-positive on the normal "enrichment done, deepening never ran"
  steady-state. v2 instead mirrors selfheal's actual orphan-stub rule
  (`recovery.py`): a stage past the resume point is blocking iff
  `STAGE_OUTPUT_FILE[stage]` is non-None, the stage is not in
  `SHARED_OUTPUT_STAGES`, the file exists with size > 1 KiB, and no provenance
  manifest exists. This is exactly the condition under which selfheal would
  manufacture a stub. `SHARED_OUTPUT_STAGES` was hoisted to `stages.py` and
  is now shared by `recovery.py` (both sites) and the orchestrator.

### 1.4 A4 (logging + backoff) — confirmed necessary, strengthened

Scrutiny verified the `min_rebuild_gap_ms` throttle does **not** limit the
refused-trigger retry loop: `_last_trigger_at_epoch` is only set on successful
triggers, so a permanently-refusing `run_fast_sync` re-debounced every
`debounce_ms` (5s) forever. v2 adds exponential backoff
(`debounce × 2^(N-1)`, capped at 5 min) with a WARNING log per retry that
points at the orchestrator log for the refusing gate's reason. The counter
resets on a successful trigger, `start()`, or `clear_pending_state()`.

## 2. What was deliberately NOT changed

- **§2n itself** (Immune System UI count-gate). Still a real UI bug; owned by
  the state-machine re-centering proposal (T1). Note the dependency direction
  flipped from v1: this fix never depended on §2n's disk state at all.
- **The `downstream_partial` guard's paused-run semantics.** Hydrated or
  user-paused runs still block incremental fast_sync. The G3/always-paused-on-
  restart contract is deliberate; changing it is out of scope.
- **The `on_coverage_gap` callback contract.** Still unwired in production;
  the fallback path is now correct, so wiring it is unnecessary.
- **`_COVERAGE_CHECK_INTERVAL` (5 min) and `_COVERAGE_COOLDOWN_SECONDS`
  (30 min).** Reasonable defaults, unchanged. The cooldown is now only
  consumed by successful triggers.

## 3. Risk notes

- **Loop-guard false positive:** a file re-edited after every rebuild keeps
  the same path, but `stale > 0` bypasses the guard entirely, and the event
  path (debounce) handles active editing independently. The guard only
  engages on `stale == 0` + identical untraced set.
- **Cost of removing the gate:** an untraced-only trigger runs structural
  (`resume = 0`, full Rust rescan). Rate-limited by the 30-min cooldown on
  success and the escalating backoff on no-progress. Bounded and visible.
- **`force_reset_stale_runs` safety:** it refuses to reset when the stage's
  build slot is RUNNING or QUEUED, so a legitimately queued downstream run
  survives. Only abandoned runs (slot idle, age > 600s) are reset.
- **Conservative fallback:** `_has_stub_extrapolation_risk` returns True on
  any internal error, keeping the guard engaged when unsure.

## 4. Tests

`tests/test_phase145_auto_incremental_gates.py` (21 tests):

- **A1:** trigger_build returns False on refusal / True on start / True on
  exception-fallback (legacy build path).
- **A4:** refusal re-queues pending paths, doubles the delay per consecutive
  failure, caps at 5 min; success resets the counter.
- **A2:** §2q scenario (9 untraced source files, 99.1% coverage) triggers;
  unchanged untraced set after a trigger backs off; changed set re-triggers;
  stale files always trigger; refused trigger doesn't consume the cooldown;
  stale `any_running` run is force-reset and the check proceeds.
- **A3:** antibodies-incomplete-without-outputs doesn't block; shared-output
  stages (deepening/deep_knowledge) never block on the earlier stage's file;
  genuine orphan output (>1 KiB, no manifest) blocks; sub-1 KiB doesn't;
  errors are conservative. Stale queued finalize run is force-reset and
  fast_sync proceeds; genuinely active runs still block; user-paused runs
  block without a reset attempt.

## 5. Verification

- 21/21 new tests pass.
- Watcher suites (`test_watcher_staleness`, `test_watcher_relevance`,
  `test_immune_watcher`): 33/33 pass.
- Pipeline suites (orchestrator, transitions, state machine, recovery, resume,
  backups, barriers, checkpoints, health): pass; two failures
  (`test_recovery_manager.py::TestCleanShutdownMarker::test_check_marker_read_only`
  and `test_index_recovery.py::TestRecoveryBehaviors::test_rebuild_clears_stale_temp_dirs`)
  reproduce identically with all changes stashed — pre-existing, unrelated
  (they track the in-flight `paths.py`/`data_dir_migration.py` working-tree
  changes).
- `ruff check` on all touched files: no new errors vs HEAD baseline.

## 6. Live-validation checklist (next daemon session)

1. Restart the daemon with these changes; put a project on Auto with a known
   untraced source file. Expect a fast_sync within one 5-min coverage cycle.
2. `grep 'stale_blocking_run_reset\|force-reset' <idx_dir>/logs/pipeline_*.log`
   — any stale queued/paused-adjacent runs get cleaned on first contact.
3. `grep 'trigger refused' daemon log` — WARNING per refusal with retry count;
   absence means the gates are passing.
4. Simulate untraceable files (e.g. an eligible file the parser rejects):
   expect one trigger, then `untraceable, backing off` INFO lines with
   escalating intervals.

## 7. Cross-references

- v1 proposal (superseded): `PROPOSAL_auto-incremental-three-gates-v1.md`
- §2q: `FINDING_auto-incremental-never-fired-despite-stale-files.md`
- §2s: `FINDING_edge-discovery-stuck-pending-auto-incremental-refuses.md`
- §2n: `FINDING_stage15-antibodies-never-complete.md` — UI count-gate; NOT a
  missing-manifest bug (this proposal's v1 misread it; see §1.3)
- `PROPOSAL_state-machine-re-centering-v1.md` — UI-rendering half of §2s (T1)
- `PROPOSAL_rebuild-pre-registration-hang-and-barrier-safety-v1.md` —
  orthogonal manual-rebuild path
