# Phase 96E / 96F: 15-Stage Merge Gap Plan

**Date:** 2026-04-11
**Context:** The 15-stage reorganization is ~87% merged into the codebase. This document plans what ships next, with swarm and scheduler implications considered.

---

## Where we are right now

### ✅ Merge is 87% complete

Working correctly on `main`:
- `stages.py` — 15 StageIds, all mappings, `FINALIZE_WAVES` defined (but unused)
- `workers.py` — All 4 new workers (Rules, Concepts, Audit, Antibodies) + WorkerFactory dispatch
- `pipeline.py` router — `/finalize` endpoint, 3-group status, cancel/pause/resume groups
- `GraphEnrichmentPipeline.tsx` — 15 stage IDs, `finalizeStages` array, third group UI
- `types.ts` — Four new status interfaces
- State machine — `TestFinalizeGroup` tests pass (5-stage sequential lifecycle)

### 🔴 The one critical gap

**`orchestrator.py` has no wave-based parallel dispatch.**
- `FINALIZE_WAVES` is defined in `stages.py:265` but never imported in `orchestrator.py`
- `_advance_pipeline()` walks `run.stages` sequentially using `current_stage_index`
- Result: Finalize stages run sequentially, not in waves

**But here's the key finding:** sequential finalize execution **already works**. `run_finalize()` exists, delegates through `_advance_pipeline`, and the state machine correctly drives 5 stages one after another. The gap is an *optimization* (parallelism), not a *bug* (stages don't run).

---

## Critical data the audit revealed

### Finalize stage queue type assignments

| Stage | Queue | Slot needed? | Model |
|---|---|---|---|
| atlas | LLM | ✓ yes | large (thinking) |
| rules | RUST | ✗ no | — |
| concepts | LLM | ✓ yes | large (thinking) |
| audit | LLM | ✓ yes | large (thinking) |
| antibodies | RUST | ✗ no | — |

### Wave composition

| Wave | Stages | LLM slots needed |
|---|---|---|
| 0 | atlas | 1 |
| 1 | rules, **concepts**, **audit** | **2** |
| 2 | antibodies | 0 |

**This changes everything about the wave parallelism design.** The naive mental model was "wave 1 runs 3 stages in parallel". The *actual* picture is:
- **rules** runs on CPU for free (no scheduler contention)
- **concepts** and **audit** both need the LLM slot for the same project on the same node

This is where the scheduler's data model breaks down. Today:

```python
# scheduler.py ComputeSlot
active_stages: Dict[str, str] = field(default_factory=dict)
# project_id → stage_id (ONE stage per project per node)

def acquire(self, project_id: str, stage_id: str) -> bool:
    if not self.has_capacity:
        return False
    self.active_stages[project_id] = stage_id   # ← OVERWRITES previous entry
    return True
```

If concepts acquires, then audit tries to acquire for the same project, **audit overwrites concepts** in `active_stages`. When concepts eventually finishes and calls `release(project_id, expected_stage="concepts")`, the check fails because the stored stage is now "audit". Concepts silently loses its slot tracking.

And `current_load = len(active_stages)` counts unique *project_ids*, not unique stages. Two stages for the same project count as load=1 — the capacity accounting is wrong when one project holds multiple slots.

**Wave parallelism requires a real scheduler data model change**, not a quick orchestrator tweak.

### Swarm implications

`SWARM_CAPABLE_STAGES = {group_reasoning, clustering, atlas}`

- `group_reasoning` and `clustering` are in the Enrich group (unchanged)
- `atlas` is now in the Finalize group as wave 0

When atlas runs as wave 0:
1. `_advance_pipeline` checks `SWARM_CAPABLE_STAGES` → atlas qualifies
2. `open_swarm_window(project_id, atlas, node_id)` succeeds
3. Atlas runs with exclusive access + fan-out
4. When atlas completes → `close_swarm_window()` → starts 45-second cooldown
5. Wave 1 (rules/concepts/audit) tries to start
6. **Cooldown blocks OTHER projects from opening swarm windows**, but rules/concepts/audit aren't swarm-capable. They acquire slots normally.
7. No swarm interaction issues *between waves within the same project*.

**Swarm gotcha for wave parallelism (if we implement it):** if concepts and audit run in parallel, and concepts internally uses batch concurrency (10 workers via the 96B fix), then audit's batch is competing for the same LLM pool. With `max_concurrent=10`, if concepts grabs 5 workers and audit grabs 5 workers, they share the pool correctly — but we need to make sure `concurrent_workers_for_project(project_id, stage)` splits the budget fairly when one project has two active stages. Today it returns the full node budget for a single project.

---

## Plan: Split into Phase 96E and Phase 96F

### Phase 96E — Ship the 15-stage merge (sequential finalize)

**Goal:** Prove the merge works end-to-end on a real project. Ship the working version before optimizing.

**Scope:**
1. ✅ Sequential finalize execution already works (confirmed by state machine tests)
2. Add orchestrator-level integration test for `run_finalize()` with mocked workers
3. Add `TestPipelineModes::test_finalize_sequences_all_5_stages` mirroring the existing initial/incremental/rebuild tests
4. Update `test_all_15_stages_have_build_type_mapping` to be exhaustive
5. Live validate on `SMOKE: rust_repo`: POST /pipeline/finalize, watch 5 stages complete
6. Live validate full-cycle: POST /pipeline/all, verify 15 stages total via Playwright driver
7. Minor cleanups:
   - Fix `pipeline.py:170` docstring ("Fast Sync (1-4) then Deep Enrichment (5-8)" → 3-group 15-stage)
   - Remove dead `trigger_concept_seeding` from `post_flight.py`
   - Remove dead `_regenerate_rules_with_full_atlas` delegate from `orchestrator.py`

**Risk:** Low. Sequential execution is the simplest case. The state machine handles it. No data model changes.

**Time savings vs wave parallelism:** ~0 (we're shipping what already works)

**Commit:** `feat(96E): validate and test 15-stage sequential finalize`

---

### Phase 96F — Wave-based parallelism for Finalize (design + implement)

**Goal:** Run wave 1 stages concurrently where the scheduler model permits, reducing wall-clock time for the Finalize group.

**This is a separate workstream** because it requires data model changes in the scheduler, state machine extensions, and UI work to display multiple simultaneous stages.

**Design questions to resolve before implementation:**

1. **Scheduler data model:** How to track multiple concurrent stages per project per node?
   - Option A: Change `active_stages` to `Dict[Tuple[str, str], float]` = `{(project_id, stage): acquired_at}`. Touches every read/write site (~20 locations).
   - Option B: Only allow one LLM stage per project even within a wave. Wave 1 becomes "rules (CPU) + concepts (LLM) in parallel, then audit (LLM)". Atlas + rules + concepts in parallel, then audit + antibodies.
   - Option C: Map each finalize LLM stage to a different "virtual node" in the scheduler so they don't contend at the slot level. e.g., `cloud:default_ollama:concepts` vs `cloud:default_ollama:audit`. Requires node-routing changes.

2. **State machine:** How to track multiple running stages in a group?
   - Option A: Add `wave_index` and `wave_pending: Set[str]` to `PipelineGroupStateMachine`. Transition semantics: wave advances when `wave_pending` is empty.
   - Option B: Spawn sub-state-machines for each wave stage. Too much complexity.
   - Option C: Keep `current_stage_index` but allow it to advance by more than 1 at a time. Track concurrent stages in a separate `_running_stages: Set[str]` on the run object. When all running stages finish, advance.

3. **UI:** How does `GraphEnrichmentPipeline.tsx` display 3 stages "running" at once?
   - Visual: a bracket or rail linking wave-1 stages
   - State: each stage has its own progress indicator
   - Progress aggregation: show a single "wave 1 progress" or per-stage?

4. **Error handling:** If one stage in a wave fails, what happens to the others?
   - Option A: Let running stages finish, then fail the group. Non-blocking cleanup.
   - Option B: Cancel siblings immediately. Requires cancellation plumbing for each worker.
   - Option C: Retry the failed one while siblings continue. Complex.

5. **Swarm + wave interaction:** Does atlas's swarm cooldown impact wave 1?
   - Atlas closes swarm window → 45s cooldown starts
   - Wave 1 tries to start — cooldown doesn't block non-swarm stages → OK
   - But: if concepts or audit becomes swarm-capable in the future, this needs re-evaluation

6. **Batch concurrency allocation across concurrent stages:** With 10 workers total on the LLM node and both concepts and audit running, how are workers split?
   - Current `concurrent_workers_for_project` returns the full weighted share for ONE stage of ONE project
   - With two concurrent stages in the same project, they need to split the budget
   - Simplest: each stage in a wave gets `weighted_share / wave_size` workers

**Minimum viable wave parallelism (compromise):**
Instead of changing the scheduler data model, we could exploit the queue_type routing:
- `rules` and `antibodies` already use RUST queue → no scheduler slot needed → they always run "for free" when triggered
- Dispatch wave 1 in two passes:
  - Pass 1: dispatch all non-LLM stages (rules, audit Tier 1 if we split audit)
  - Pass 2: dispatch the single LLM stage (concepts)
- This gives us parallelism between rules and concepts with zero scheduler changes
- But audit is currently marked LLM (Tier 2 is LLM), so only rules runs "for free" in wave 1

**Scope if we go minimal:**
1. Import `FINALIZE_WAVES` in orchestrator
2. Add `_advance_finalize(run)` that dispatches wave stages, skipping slot-check for RUST-queue stages
3. Track wave completion using a simple counter on the run object
4. Keep state machine largely unchanged; wave_index is orchestrator-level bookkeeping
5. UI displays stages sequentially regardless (parallelism is invisible to user — sync of stage start/end is close enough in time)

**Risk:** Medium. Touches orchestrator core and introduces a new execution mode. But no data model changes to the scheduler.

**Risk if we go full (Option A in data model):** High. Scheduler refactor touches dozens of call sites.

**Commit:** `feat(96F): wave-based parallel dispatch for Finalize group`

---

## REVISED PLAN (2026-04-11, after discussion)

**The initial plan treated wave parallelism as the primary optimization. That's backwards.**

### Core insight: swarm wins by ~9x over wave parallelism

Math on wave 1 (rules + concepts + audit) with 10-worker LLM budget:

| Approach | atlas | rules | concepts | audit | antibodies | total |
|---|---|---|---|---|---|---|
| Sequential, no swarm (today) | 60s (1w) | 1s | 60s (1w) | 60s (1w) | 1s | **182s** |
| Wave-parallel, budget split | 60s (1w swarm) | 1s | 180s (~5w) | 180s (~5w) | 1s | **~240s** (worse!) |
| Sequential, swarm per LLM stage | 6s (10w swarm) | 1s | 6s (10w swarm) | 6s (10w swarm) | 1s | **~20s** |

Wave parallelism with shared budget is *slower* than sequential because each stage runs on fewer workers. Swarm-per-stage monopolizes the full 10-worker budget for each LLM stage in turn, and fan-out gives ~10x throughput per stage.

**The real Phase 96F target is: make concepts and audit swarm-capable.** Wave parallelism is relegated to "fallback for models that don't support swarm" — and even then it's marginal.

### Current swarm state in the codebase

| Stage | Implementation | Swarm-capable? |
|---|---|---|
| atlas | `CodebaseAtlas.generate_segmented()` uses `SwarmOrchestrator` internally | ✅ yes |
| group_reasoning | Direct `SwarmOrchestrator` instantiation in `core/group_reasoning.py:458` | ✅ yes |
| clustering | Uses swarm internally | ✅ yes |
| **concepts** | `seed_concepts()` → single LLM call, no decomposition | ❌ NO |
| **audit Tier 2** | Single LLM synthesis, no decomposition | ❌ NO |
| rules | Python template (no LLM) | N/A |
| antibodies | Python derivation (no LLM) | N/A |

`SWARM_CAPABLE_STAGES = {group_reasoning, clustering, atlas}`

The work for 96F is **extending the swarm pattern to concepts and audit** — which requires decomposing their work into independent parallel units.

---

### Revised phase plan

## Phase 96E — Sequential finalize validation (unchanged, ship first)

**Goal:** validate the 15-stage merge works end-to-end without introducing any new code.

- Add `TestPipelineModes::test_finalize_sequences_all_5_stages` integration test
- Add `test_run_all_chains_all_three_groups` test
- Fix `/pipeline/all` docstring
- Remove dead `trigger_concept_seeding` and `_regenerate_rules_with_full_atlas` delegates
- Live validate on rust_repo via Playwright driver
- Commit and push

**Risk:** low. No new behavior — just coverage for existing sequential execution.
**Savings:** none. This is the safety net.

## Phase 96F — Swarm-enable concepts and audit (primary optimization)

**Goal:** make concepts and audit use the SwarmOrchestrator pattern so each stage monopolizes the 10-worker budget when running.

This is a meaningful refactor, not a config change. Concepts currently does one LLM call; decomposing it into swarm-parallelizable units is a real design question.

### 96F design questions (need answers before implementation)

**Q1 — Concept decomposition unit:** What do concept workers process independently?
- **Option A: Per-module.** Each module (from clustering output) becomes a work unit. Worker prompts the LLM with just that module's context and generates concepts for it. Synthesizer merges, dedupes, and surfaces cross-module invariants.
  - Natural fit with existing `trace_modules.jsonl` output
  - Produces module-scoped concepts with clear anchors
  - ~5-20 modules typical → good fan-out shape
- **Option B: Per-category.** Workers generate "architectural", "security", "performance", "invariant" concepts separately. Synthesizer merges.
  - Fixed N workers (small fan-out if < 5 workers)
  - Risk: categories bleed into each other, dedup is hard
- **Option C: Per-file-cluster.** Workers process file clusters (not module clusters). Same shape as clustering.
  - Duplicates clustering effort
- **Recommendation:** Option A. Best fan-out shape, leverages existing module output, produces concepts with clean anchors.

**Q2 — Audit Tier 2 decomposition unit:** What does the LLM synthesis do per-worker?
- **Option A: Per-finding-category.** Split Tier 1 findings by category (coupling, complexity, testability, etc.). Each worker synthesizes one category's findings into high-level observations. Synthesizer produces the overall audit report.
  - Natural — analyzers already emit categorized findings
  - Variable fan-out (maybe 5-10 categories)
- **Option B: Per-analyzer.** Each analyzer gets its own synthesis worker.
  - Too granular — some analyzers produce 0-1 findings
- **Option C: Per-severity.** Group by critical/warning/info.
  - Too coarse — 3 workers max
- **Recommendation:** Option A. Category-based matches the existing Tier 1 data shape.

**Q3 — Tier 1 analyzer parallelism:** Should analyzers run in parallel too?
- Analyzers are pure CPU. Running them in parallel is a `ThreadPoolExecutor`, not swarm.
- This is independent of swarm enablement — can be done in 96F or deferred.
- **Recommendation:** Defer. The win is small; most analyzers run in milliseconds.

**Q4 — Swarm model registry updates:**
- `swarm_models.json` maps models → swarm tier (COORDINATOR, BOTH, WORKER, UNSUITABLE)
- For concepts/audit to use swarm, their assigned models (currently `large` slot) need to be registered as swarm-capable.
- **Likely no change needed** — the `large` slot models used for atlas/group_reasoning/clustering are already swarm-registered. Concepts and audit use the same slot, so they inherit the same models.
- **Action:** Verify `kimi-k2.5:cloud` and other large-slot models are in the swarm registry with tier=COORDINATOR or BOTH.

**Q5 — Fallback behavior when swarm isn't available:**
- If model doesn't support swarm → current `is_swarm_active_for_stage()` returns False → falls back to non-swarm
- If budget < 3 workers → swarm skipped → falls back
- For concepts/audit: the non-swarm fallback is the **current sequential single-call behavior**. We're extending the code to do swarm when possible and keep the single-call path for the fallback.
- **No new fallback code required** — just ensure the refactored worker supports both modes.

**Q6 — Min fan-out threshold for concepts/audit:**
- Atlas uses `generate_segmented` only if ≥ 2 segments exist, falls back to single-atlas otherwise.
- Concepts should swarm only if ≥ 3 modules exist (match the budget floor).
- Audit should swarm only if ≥ 3 categories have findings.
- **Action:** Add these guards to the refactored workers.

### 96F implementation scope

1. **`core/concept_seeder.py` refactor (~200 lines changed)**
   - Extract the context assembly logic so it can produce per-module contexts
   - Add a new `seed_concepts_swarm()` entry point that:
     - Loads modules from `trace_modules.jsonl`
     - If ≥ 3 modules and model supports swarm → fan out per-module via `SwarmOrchestrator`
     - Workers generate concepts scoped to their module
     - Synthesizer merges, dedupes by title/anchor, produces final concept list
     - Writes to `ConceptStore`
   - Keep `seed_concepts()` (non-swarm) as the fallback path

2. **`core/audit/runner.py` refactor (~150 lines changed)**
   - Split Tier 2 out into `_synthesize_tier2_swarm()` and `_synthesize_tier2_sequential()`
   - Swarm path decomposes by category
   - Sequential path is the current single-call logic
   - Route based on swarm availability

3. **`scheduler.py` — add CONCEPTS and AUDIT to SWARM_CAPABLE_STAGES (2 lines)**
   ```python
   SWARM_CAPABLE_STAGES: Set[str] = {
       "group_reasoning", "clustering", "atlas", "concepts", "audit",
   }
   ```

4. **`workers.py` — wire the new swarm paths (~30 lines)**
   - `_concepts_worker` calls `seed_concepts_swarm()` if swarm eligible, else `seed_concepts()`
   - `_audit_worker` uses new Tier 2 router

5. **`orchestrator.py` — no changes needed** (existing swarm window logic already handles new SWARM_CAPABLE_STAGES entries)

6. **Tests:**
   - Unit test `seed_concepts_swarm` with mocked `SwarmOrchestrator`
   - Unit test audit Tier 2 swarm decomposition
   - Integration test: `test_concepts_uses_swarm_when_eligible`
   - Integration test: `test_concepts_falls_back_to_sequential`

7. **Live validation:**
   - Run finalize on rust_repo with swarm-enabled concepts
   - Watch log for "Swarm: fanning out to N workers for concepts"
   - Verify ~10x speedup vs current

**Risk:** medium. Refactoring is contained to 2 core files + wiring. The swarm framework itself (`SwarmOrchestrator`) is already proven. The risk is in the decomposition logic — making sure per-module concepts don't miss cross-module invariants.

**Savings:** ~100-150 seconds per finalize run (concepts: 60s → 6s, audit: 60s → 6s).

## Phase 96G — Wave parallelism fallback (deferred, probably unnecessary)

**Goal:** run wave 1 stages concurrently when swarm isn't available.

Only worth doing if we encounter a real workload where:
- Model doesn't support swarm (no COORDINATOR-tier models configured)
- Project is large enough that sequential execution matters
- Users complain about wall-clock time

In that case, we'd implement the scheduler data model changes previously described. But sequential-with-swarm is so much faster than wave-parallel-without-swarm that this is probably never worth doing.

**Status:** deferred indefinitely.

---

## Recommendation

**Ship Phase 96E now. Design Phase 96F carefully before touching code.**

Reasoning:
1. **96E has no design risk** — sequential execution already works. We're just validating and adding tests.
2. **96F has real design risk** — the scheduler's data model wasn't built for multiple concurrent stages per project per node. Getting it wrong breaks slot tracking everywhere.
3. **Wave parallelism savings are small** relative to total pipeline time. A typical finalize run:
   - Atlas: 2-5 minutes (LLM-heavy, swarm-capable)
   - Rules: ~1 second (pure CPU)
   - Concepts: 1-2 minutes (LLM)
   - Audit: 30 seconds Tier 1, 1-2 minutes Tier 2 (LLM)
   - Antibodies: ~1 second (pure CPU)
   - **Sequential total:** ~5-10 minutes
   - **Ideal wave-parallel total:** ~4-8 minutes
   - **Savings:** ~1-2 minutes per run (~20%)
4. **96E unblocks live UI testing with Playwright** on all 3 modes (initial / incremental / rebuild) against a complete 15-stage pipeline. That was the user's immediate goal.
5. **Phase 96F can ship later** when we've had time to carefully design the scheduler data model changes and have a solid spec.

---

## Phase 96E Step-by-Step

### 96E.1 — Fix pipeline/all docstring (1 line)
`src/codrag/api/routers/pipeline.py:170`:
```python
# Before:
"""Run all stages: Fast Sync (1-4) then Deep Enrichment (5-8)."""
# After:
"""Run all 15 stages: Sync (1-5), Enrich (6-10), Finalize (11-15)."""
```

### 96E.2 — Remove dead post_flight delegates (10-20 lines)
- `post_flight.py` — remove `trigger_concept_seeding` function
- `orchestrator.py` — remove `_regenerate_rules_with_full_atlas` delegate (currently unused since call site is commented out)

### 96E.3 — Add orchestrator integration test for finalize
`tests/test_pipeline_orchestrator.py`:
```python
def test_finalize_sequences_all_5_stages(self, pipeline):
    """Finalize group runs all 5 stages (sequentially) to completion."""
    executed: list[str] = []
    def worker_factory(pid, stage):
        def worker(slot, cb):
            executed.append(stage.value)
            return {"ok": True}
        return worker

    with patch(
        "codrag.services.pipeline.orchestrator.WorkerFactory.create_worker",
        side_effect=worker_factory,
    ), patch(
        "codrag.services.pipeline.orchestrator.ResumeStrategy.should_skip_stage_freshness",
        return_value=(False, ""),
    ):
        pipeline.run_finalize("proj-finalize")
        # Poll until complete or timeout
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            status = pipeline.status("proj-finalize")
            fin = status.get("finalize")
            if fin and fin["phase"] in ("completed", "failed"):
                break
            time.sleep(0.1)

        status = pipeline.status("proj-finalize")
        fin = status["finalize"]
        assert fin["phase"] == "completed", f"Finalize stuck in {fin['phase']}"
        assert len(executed) == 5
        assert executed == ["atlas", "rules", "concepts", "audit", "antibodies"]
```

Plus a companion test for `run_all` that chains all 3 groups (sync + enrich + finalize) to verify end-to-end orchestration.

### 96E.4 — Full pipeline test suite passes
Run `pytest tests/test_pipeline_*.py` and confirm all tests green. Expect 192 + ~2 new = ~194 passing.

### 96E.5 — Live validation with Playwright driver
Using `scripts/playwright_ui_smoke.py`:
```bash
.venv/bin/python scripts/playwright_ui_smoke.py \
    --trigger all \
    --timeout 1800 \
    --headed
```
Watches all 15 stages complete on rust_repo. Screenshots at each transition.

### 96E.6 — Commit and push
```
feat(96E): validate and test 15-stage sequential finalize

- Add run_finalize integration test in TestPipelineModes
- Add run_all chaining test (sync → enrich → finalize)
- Fix /pipeline/all docstring
- Remove dead trigger_concept_seeding + _regenerate_rules_with_full_atlas
- Live validated on SMOKE: rust_repo — all 15 stages complete end-to-end
```

---

## Phase 96F Step-by-Step (draft, not yet scheduled)

**Deferred until Phase 96E ships and we have a clean spec.**

Design document first: `docs/Phase96-fix-pipeline/04_WAVE_PARALLELISM_DESIGN.md`
- Resolve the 6 design questions listed above
- Decide Option A vs B vs C for scheduler data model
- Specify state machine changes
- Specify UI display changes

Then implementation, then tests.

---

## Swarm Implications Summary

| Scenario | Impact |
|---|---|
| Atlas in Finalize wave 0 | No change. Opens swarm window, runs, closes, 45s cooldown. Same as before in Deep Enrichment. |
| Cooldown during wave 1 start | Cooldown only blocks OTHER projects from opening swarm. Rules/Concepts/Audit aren't swarm-capable; not blocked. |
| Multi-project during Finalize | Project A running Finalize atlas holds swarm window. Project B blocked from opening its own swarm until A's window closes + cooldown expires. Existing drain-target logic handles this. |
| Wave parallelism + batch concurrency (96F) | If concepts+audit run concurrently in the same project, they share the LLM node's 10-worker budget. `concurrent_workers_for_project` needs to split the budget across concurrent stages in the same project. Today it returns full budget for one project. |
| Future swarm-capable audit/concepts | Out of scope for 96F. Would require treating wave 1 as "at most one swarm-capable stage at a time" with fallback logic. |

---

## Success Criteria

### For Phase 96E:
- [ ] Orchestrator test for `run_finalize()` passes
- [ ] Orchestrator test for `run_all()` chaining passes
- [ ] Live rust_repo smoke shows all 15 stages running to completion
- [ ] Playwright driver reports 0 desyncs during the run
- [ ] Committed and pushed

### For Phase 96F (future):
- [ ] Design doc drafted and approved
- [ ] Scheduler data model change (or alternative) implemented and unit-tested
- [ ] Orchestrator wave dispatch implemented
- [ ] State machine wave tracking implemented
- [ ] UI shows parallel stages clearly
- [ ] Error handling for partial wave failure
- [ ] Live rust_repo smoke shows wave-1 stages overlapping in time
- [ ] Wall-clock improvement measured vs 96E baseline
