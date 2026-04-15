# Phase 107 -- Pipeline & State Machine Stability

> **Scope:** Resolve all remaining pipeline liveness, state coherence, and orchestrator reliability issues.
> **Prior art:** Phases 75, 76, 81, 89, 91, 92, 96, 105
> **Status:** Research & TODO (**reality-checked 2026-04-15** — see §1.5)
> **Date:** 2026-04-15

> **⚠️ Reality-check delta (2026-04-15):** The first draft of this plan was written against pre-105b summaries. §4.1 (Phase 105a Completion, 13 items) is **100% SHIPPED** in commits `a4e25579`, `48069466`, `67863620`, `d9722433`, `3e9f3b44`, `9ca1ab2e`, `bae833c0`, `a76690c3`. F-66 is **FIXED** (`85bf33b7`). Lock contention O(N_stages) pattern is **FIXED via F-41** (`f449ef00`, snapshot-based status reads). F-68 and F-15 are **PARTIAL**. Atomic Stage Handoff (§4.2) is still-open. See §1.5 for full verdict, §4.x for per-TODO tags.

---

## 1. Problem Statement

The pipeline orchestrator has been the single most-worked subsystem across Phases 74-105. Phase 96 alone fixed **63 out of 69 findings** -- but the fixes were predominantly tactical (one-off patches to each symptom). The root cause analysis in Phase 89 identified that **three independent lock domains** (StateMachine, Scheduler, BuildOrchestrator) update sequentially during stage transitions, creating windows where they disagree. This architectural tension has not been resolved -- only bandaged.

**Remaining open findings from Phase 96:**
- F-15: Pre-existing test rot (resume_strategy, mcp_server, queue_router, trace_builder_globs, team_sync_integration)
- F-66: Two-tone progress bar baseline lost on page refresh
- F-68: No "interrupted incremental" concept in recovery -- should show "Resume" not "Run"

**Systemic issues not yet addressed:**
- The stage handoff race window (Phase 89 T0-T10 timeline) still exists
- `_advance_pipeline` does ~200 lines of bookkeeping outside any lock (manifest writing, journal, integrity checks) -- any exception is swallowed
- No formal "stage handoff" transaction that atomically updates all three systems
- Finalize stages bypass the orchestrator entirely when triggered from UI buttons (Phase 105 root cause)
- Swarm window coordination adds a 4th lock domain (Phase 91)

## 1.5 Reality Check Against Current Code (2026-04-15)

Claim-by-claim verification of §1 against the working tree + git log.

| Claim (from §) | Verdict | Evidence |
|---|---|---|
| §1 F-66 "two-tone progress bar baseline lost on refresh" | **FIXED** | `85bf33b7` — baseline persisted to `stage_manifest.py`; survives page refresh + daemon restart |
| §1 F-68 "no 'interrupted incremental' concept; should show Resume not Run" | **PARTIAL** | JSON flag mechanism exists at `orchestrator.py:717`; daemon-restart detection works; **UI does not expose Resume/Discard buttons** |
| §1 F-15 "pre-existing test rot" | **PARTIAL** | `cc417e20` skips settings_store WAL tests; **resume_strategy, mcp_server, queue_router, trace_builder_globs, team_sync_integration tests still unaddressed** |
| §1 "stage handoff race window (T0-T10) still exists" | **STILL-OPEN** | `_advance_pipeline` still does bookkeeping outside locks; no StageHandoff class exists |
| §1 "~200 lines of bookkeeping outside any lock" | **STILL-OPEN** | Confirmed in `_advance_pipeline` |
| §1 "no formal 'stage handoff' transaction" | **STILL-OPEN** | No StageHandoff class in tree |
| §1 "Finalize stages bypass the orchestrator" | **FIXED** | `67863620` — Atlas, Concepts, Audit all route through `run_single_stage` → orchestrator; direct-call endpoints deleted (`d9722433` for Atlas; comments in `concepts.py:206-213`, `audit.py:37-42` for the other two) |
| §2.1 three independent lock domains | **CONFIRMED** | `orchestrator.py:80`, `state_machine.py:273`, `build_orchestrator._lock` |
| §2.2 "incremental flag via JSON file" (crash-vulnerable) | **CONFIRMED** | `orchestrator.py:166-205` — still JSON-file based |
| §2.3 "O(N_stages) lock acquisition in status()" | **FIXED (F-41)** | `f449ef00` — `orchestrator.py:1101-1154` now uses `snapshot()` (lock-free). The O(N) pattern is gone. |
| §2.4 "Finalize bypass (Phase 105 root cause)" | **FIXED** | See §1.5 row 7 above. `run_single_stage` at `orchestrator.py:818-884`; endpoint `POST /projects/{id}/pipeline/stages/{stage_id}/run` live (`48069466`). |

**Bottom line for §1 framing:** The Problem Statement still reads as if the finalize bypass, F-66, and O(N) lock contention are open. **They are not.** The genuinely remaining systemic issues are: (a) stage handoff race (§4.2, unshipped), (b) JSON-file incremental flag (§4.6, unshipped), (c) F-68 UI wiring (§4.3, partial), (d) F-15 test rot triage on five remaining test files (§4.3, partial), (e) WAL audit (§4.5, unshipped).

## 2. Root Cause Analysis (from source inspection)

### 2.1 Three Sources of Truth

From `orchestrator.py` and Phase 89 doc:

| System | Lock | What it tracks |
|---|---|---|
| `PipelineGroupStateMachine` | `state_machine._lock` | Run state (RUNNING/QUEUED/COMPLETED), `current_stage_index` |
| `PipelineScheduler` | `scheduler._lock` | Which project holds a compute slot on which node |
| `BuildOrchestrator` | `build_orchestrator._lock` | Whether a worker thread is alive |

The critical moment is **T4** in a stage handoff: `scheduler.release()` frees the slot, but the state machine still says RUNNING, and ~200 lines of bookkeeping follow before the next stage is dispatched. If any bookkeeping step throws, the pipeline silently stalls.

### 2.2 Incremental Mode Fragility

`orchestrator.py:166-205` shows `_persist_incremental_flag` / `_read_and_clear_incremental_flag` using a JSON file on disk. This is a crash-vulnerable pattern: if the daemon dies between writing the flag and clearing it, the pipeline will behave unexpectedly on restart. Phase 89 identified this as "No progress_baseline for Rebuild" gap.

### 2.3 Lock Contention Under Load

F-41 (Phase 96) documented that `/system/pipeline-queue` and `/pipeline/status` block for 15x sequential lock acquisitions in `PipelineOrchestrator.status()`, contending with worker thread state transitions. The fix was to reduce polling, but the underlying O(N_stages) lock acquisition pattern remains.

### 2.4 Finalize Bypass Bug

Phase 105 identified that pressing "Regenerate" in the Atlas panel calls `atlas.generate_segmented()` directly -- bypassing the orchestrator entirely. No queue entry, no journal entry, no stage state transition. This affects Atlas, Concepts, and Audit (all three have UI trigger buttons that bypass the orchestrator). Phase 105a spec exists but has 33 pending implementation tasks.

## 3. Proposed Solutions

### Solution A: Atomic Stage Handoff Transaction

Replace the sequential lock-acquire pattern with a single `StageHandoff` operation that atomically updates all three systems under a coordinating lock:

```python
class StageHandoff:
    """Atomic transition between pipeline stages."""
    def execute(self, project_id, completed_stage, next_stage):
        with self._coordinator_lock:
            # 1. Release scheduler slot
            deferred = scheduler.release(project_id, completed_stage, node)
            # 2. Advance state machine
            sm.transition(Event.STAGE_COMPLETED)
            # 3. Write manifest + journal (inside the lock -- fast ops only)
            self._write_checkpoint(project_id, completed_stage)
            # 4. Dispatch next stage or complete
            if next_stage:
                scheduler.acquire(project_id, next_stage, node)
            else:
                sm.transition(Event.ALL_STAGES_DONE)
```

**Risk:** Holding a lock across all three systems increases lock contention. Mitigation: keep only fast I/O (manifest JSON writes) inside the lock; defer slow operations (integrity checks, atlas generation) to a post-handoff queue.

### Solution B: Event-Sourced Pipeline Journal

Instead of three independent state stores, make the `pipeline_journal` the single source of truth. Each state change is an append-only event. The state machine, scheduler, and build orchestrator derive their state from the journal on read. On crash recovery, replay the journal to reconstruct state.

**Advantage:** Eliminates disagreement by design. Single writer, multiple readers.
**Risk:** Higher complexity. Needs careful benchmarking to ensure journal reads don't add latency to status endpoints.

### Solution C: Phase 105a (Minimal -- Finalize Rewire)

Complete the Phase 105a spec as-is: add `run_single_stage(project_id, stage_id)` to the orchestrator, expose as `POST /projects/{id}/pipeline/stages/{stage_id}/run`, delete direct-call endpoints. This doesn't fix the handoff race but eliminates the most visible symptom (finalize bypass).

### Recommended Approach: C then A

Ship 105a first (it's spec'd and scoped). Then implement Solution A for the handoff race. Solution B is a future architectural evolution.

## 4. TODO

### 4.1 Phase 105a Completion (Finalize Rewire) — **SHIPPED, all 13 items**

Entire section was completed in the Phase 105a/105b commit series. Preserved here for audit traceability; **do not re-work**.

- [x] Implement `run_single_stage(project_id, stage_id)` in `PipelineOrchestrator` — **[FIXED: a4e25579]** (`orchestrator.py:818-884`)
- [x] Add validation: stage must be in `FINALIZE_STAGES` — **[FIXED: 48069466]** (`orchestrator.py:846-850`)
- [x] Expose as `POST /projects/{id}/pipeline/stages/{stage_id}/run` in FastAPI router — **[FIXED: 48069466]**
- [x] Rewire `useAtlasLens.regenerate()` to call new endpoint — **[FIXED: 3e9f3b44]** (renamed `runAtlasStage`)
- [x] Rewire Concepts "Initialize" button — **[FIXED: 67863620]** (`concepts.py:206-213` records migration)
- [x] Rewire Audit "Run Audit" button — **[FIXED: 67863620]** (`audit.py:37-42` records migration)
- [x] Delete old direct-call `POST /projects/{id}/atlas/regenerate` — **[FIXED: d9722433]**
- [x] Delete old direct-call `POST /projects/{id}/concepts/initialize` — **[FIXED: 67863620]** (handler removed; route descriptor comment-only artifact)
- [x] Verify queue entry appears in sidebar within ~200ms — **[FIXED: bae833c0]** (covered by 105a test fixture `31d015b9`)
- [x] Verify pipeline journal records group="atlas"/etc with timestamps — **[FIXED: 9ca1ab2e]** (solo runs registered under stage value as group key)
- [x] Verify stage state transitions in pipeline panel — **[FIXED: d6b65330]** (`orchestrator.py:1091-1099` exposes solo runs through finalize slot)
- [x] Verify cancel + pause work for single-stage runs — **[FIXED: 9ca1ab2e]** (`orchestrator.py:862-868`)
- [x] Write tests for `run_single_stage` (unit + integration) — **[FIXED: a76690c3]** (`tests/test_orchestrator_single_stage.py`, 7.2K)

### 4.2 Atomic Stage Handoff — **STILL-OPEN, all 8 items**

The recommended approach was "C then A" — ship §4.1 (C) first, then Solution A. §4.1 is shipped; A is untouched. F-41 snapshot-based reads (`f449ef00`) reduced lock contention pressure enough that A is no longer blocking MVP, but the handoff race window still exists and should be closed for confidence-in-production.

- [ ] Design `StageHandoff` class with coordinating lock — **[STILL-OPEN]**
- [ ] Identify safe-in-lock vs deferred bookkeeping ops — **[STILL-OPEN]**
- [ ] Refactor `_on_build_transition` to delegate to `StageHandoff.execute()` — **[STILL-OPEN]** (still calls `_advance_pipeline` directly)
- [ ] Move slow operations to post-handoff deferred queue — **[STILL-OPEN]**
- [ ] Add watchdog timer (30s stall detection) — **[STILL-OPEN]**
- [ ] Add structured logging for every handoff — **[STILL-OPEN]** (basic logging exists, not handoff-focused)
- [ ] Stress test: 3 projects, 15 stages, random pauses/cancels/resumes — **[STILL-OPEN]**
- [ ] Verify zero stalls across 100 consecutive runs — **[STILL-OPEN]**

### 4.3 Open Bug Fixes (from Phase 96)
- [x] F-66: Persist two-tone progress bar baseline — **[FIXED: 85bf33b7]** (manifest persistence; survives refresh + daemon restart)
- [ ] F-68: Add "Resume" button state when `incremental_pending=true` — **[PARTIAL]** JSON flag + daemon-restart detection work (`orchestrator.py:717`); UI wiring missing — no Resume/Discard buttons in dashboard. **Scoped follow-up.**
- [ ] F-15: Triage pre-existing test rot — **[PARTIAL]** Settings-store WAL tests skipped (`cc417e20`); remaining files untouched: `test_resume_strategy.py`, `test_mcp_server.py`, `test_queue_router.py`, `test_trace_builder_globs.py`, `test_team_sync_integration.py`.

### 4.4 Lock Contention Reduction
- [x] Profile `status()` lock acquisitions — **[FIXED: f449ef00]** (F-41 diagnosed & deployed)
- [x] Implement snapshot-based status — **[FIXED: f449ef00]** (`orchestrator.py:1119` calls `snapshot()`, no per-stage lock)
- [ ] Reduce `/system/pipeline-queue` to O(1) via cached queue snapshot — **[STILL-OPEN]** (cache not implemented; deferred)

### 4.5 SQLite WAL Recovery (from Phase 92)
- [ ] Audit all SQLite stores for WAL vs DELETE mode consistency — **[NEEDS-VERIFICATION]** (partial visibility from F-15 commit; no audit doc)
- [ ] Verify dedicated DB files (concept_store, antibody_store, pipeline_journal) from F-36/F-37 — **[NEEDS-VERIFICATION]**
- [ ] Add startup health check for stale WAL files — **[STILL-OPEN]** (no such check found)
- [ ] Add `codrag_settings.db` busy_timeout configuration — **[STILL-OPEN]** (still hardcoded)

> *Reminder from user memory:* WAL mode is unreliable on the 4TB-BAD USB drive (`codrag_data/`); DELETE mode works. Auto-detection still needed.

### 4.6 Incremental Pipeline Recovery
- [ ] Replace JSON-file incremental flag with journal event (crash-safe) — **[STILL-OPEN]** (JSON mechanism still at `orchestrator.py:166-205`)
- [ ] On daemon restart, detect "interrupted incremental" and offer Resume — **[PARTIAL]** Detection works; UI wiring missing (same underlying gap as F-68)
- [x] Show progress baseline from last successful stage in UI — **[FIXED: 85bf33b7]** (baseline persisted to manifest via F-66 fix)
- [ ] Test: kill daemon mid-stage, restart, verify resume — **[STILL-OPEN]** (no such test)

### 4.7 Recovery UI Wiring (NEW — extracted from F-68 + §4.6 PARTIALs)

Both F-68 and §4.6 resume flow have working infrastructure but no UI surface. Small, scoped, high-value follow-up.

- [ ] Add `incremental_pending` field to `/pipeline/status` response (if not already)
- [ ] In `useStageRegenerate` / equivalent dashboard hook, expose Resume vs Discard state when flag is true
- [ ] Show "Resume" button (not "Run") in affected panels
- [ ] Wire Resume to call pipeline start with correct offset; Discard to clear flag
- [ ] E2E test: kill daemon mid-stage, restart, verify Resume button appears and works

## 5. Links to Prior Work

| Phase | What it built | Status | Gap this phase addresses |
|---|---|---|---|
| 75 | Global Pipeline Queue + Ghost Guard | Design complete | Queue ghost entries (F-10 fixed, but UI deferred) |
| 76 | Zero-Downtime Rebuild | Design complete | Not started -- blocked on stable handoff |
| 81 | UI Bugfixes + Dashboard State Audit | Stages 0-3 done, Stage 4 deferred | Hydration gaps persist in some hooks |
| 89 | State Machine Root Cause Analysis | RCA complete, 27 tasks pending | The handoff race this phase fixes |
| 91 | Queue Refinement | 20/20 tasks done | Swarm UI visuals deferred |
| 92 | SQLite WAL Recovery | Design complete, 0 tasks done | Section 4.5 |
| 96 | Fix Pipeline (masterwork) | 63/69 fixed; **F-66 now fixed; F-41 now deployed** | F-68 partial, F-15 partial |
| 105 | Independent Finalize | **Spec SHIPPED** (105a + 105b) | §4.1 complete; §4.7 (Recovery UI wiring) is the new scoped follow-up |

## 6. Success Criteria

1. Zero pipeline stalls in 100 consecutive full-pipeline runs on test repo
2. All finalize stages routed through orchestrator (no direct-call endpoints)
3. Status endpoint responds in <50ms regardless of pipeline activity
4. Daemon restart mid-pipeline correctly offers "Resume" in UI
5. All pre-existing test failures in pipeline tests resolved or categorized
