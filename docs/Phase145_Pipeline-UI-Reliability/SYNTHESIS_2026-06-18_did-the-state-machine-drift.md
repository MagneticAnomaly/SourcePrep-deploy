# Phase 145 Synthesis — Has the pipeline state machine drifted from its original role as canonical source of truth?

**Status:** Hypothesis + investigation plan. **Not a fix proposal** — no code or test changes proposed here. Subject to scrutiny like any other corpus doc.
**Authored:** 2026-06-18.
**Why this exists:** every open finding in Phase 145 — §2a, §2b, §2f, §2j, §2k, §2l, §2m, §2n, §2o, §2p, §2q, §2r — shares the same structural shape: *two or more representations of pipeline state disagree, the UI surfaces one of them, the user sees something different from what's actually true.* That's not a series of independent bugs. That's a single architectural question: **is the Phase 25B state machine still the canonical signal, or has it been progressively eclipsed by parallel state stores?**

---

## 1. The hypothesis (one paragraph)

The `PipelineGroupStateMachine` was introduced in Phase 25B to replace the "ad-hoc `PipelineRunPhase` enum + magic error strings" (its own module docstring) with one canonical source of truth for pipeline state. ~120 phases later, the codebase has at least **nine** parallel state representations that read, write, or derive pipeline state independently: the state machine itself, the build-orchestrator slot phase, the per-run metadata JSON, the per-stage manifest JSON, the derived `provenance.state` (model-comparison only), several disk-flag files (`.reset_barrier`, `.guard_rejections.json`, `.pipeline_last_success`, `.checkpoints/`, soft-holds), the scheduler's per-node load, the UI's `compute*State` derivations, and the watcher's debounce/auto state. Every open §2 finding traces back to two or more of these disagreeing. **The hypothesis is that the state machine is no longer the canonical signal — it is one signal among nine — and the symptoms we keep catching are the predictable surface of that drift.** If true, then no individual finding fix removes the class of bug; only a re-centering on the state machine (writer side and reader side) does.

---

## 2. What the state machine was originally for (Phase 25B intent)

From `src/prep/services/pipeline/state_machine.py:1-29` (verbatim docstring):

> Formalizes the lifecycle of a pipeline group run with explicit states, guarded transitions, and crash recovery. **Replaces the ad-hoc `PipelineRunPhase` enum + magic error strings.**
>
> States: IDLE, QUEUED, RUNNING, PAUSING, PAUSED, CANCELLING, CANCELLED, COMPLETED, FAILED, RECOVERING.

Key design intent (paraphrased from the docstring + the `_TRANSITIONS` table at line 130):

1. **One state per pipeline group at any moment.** A run is in exactly one of the ten states.
2. **Transitions are guarded.** You move between states only via explicit `Event` invocations (START, STAGE_COMPLETED, ALL_STAGES_DONE, STAGE_FAILED, PAUSE, RESUME, CANCEL, CRASH_DETECTED, RECOVERY_SUCCEEDED, RESET, etc.). Anything else raises.
3. **Terminal states are real terminals.** COMPLETED / FAILED / CANCELLED can only leave via RESET (back to IDLE). No silent flip-flopping.
4. **Recovery is a first-class state.** RECOVERING is not "RUNNING but pretending" — it's a separately-tracked phase.
5. **The state machine OWNS `stage_results`** — the dict that records, per stage, whether it `completed` / `failed` / `skipped` / `user_stopped`. That ownership is the contract.

If we were following Phase 25B's intent today, the UI's per-stage row state would derive from `stage_results[stage]` (the state machine's own dict) and the row's `running` flag would be `state == RUNNING && current_stage == X`. Single source of truth, one signal per question.

---

## 3. The state-tracking system inventory (what we actually have)

Numbered for cross-reference from §4 and §5 below. Each entry: name, location, who writes it, who reads it.

| # | System | Where | Writers | Readers |
|---|---|---|---|---|
| **S1** | `PipelineGroupStateMachine` (in-memory, per group) | `src/prep/services/pipeline/state_machine.py` | `orchestrator.py` via `Event.*` transitions | `_advance_pipeline`, `_on_build_transition`, status endpoint via `to_dict()` |
| **S2** | `BuildOrchestrator` slot phase (in-memory, per build_type) | `src/prep/services/build_orchestrator.py` (`BuildPhase`) | `BuildOrchestrator.start/cancel/_check_zombie` | `pipeline_orchestrator._on_build_transition`, status endpoint |
| **S3** | `pipeline_run_metadata.json` (per-run, on-disk) | `.sourceprep/pipeline_run_metadata.json` | `_finalize_run_metadata` (success only!), `_write_stage_manifest_and_update_run` | resume detector, UI's "Last updated" stamp |
| **S4** | `<stage>_manifest.json` (per-stage, on-disk) | `.sourceprep/<stage>_manifest.json` | each stage's worker via `ManifestStore.write_provenance` | resume detector, freshness checks, `provenance.state` deriver |
| **S5** | `provenance.state` (derived) | `pipeline_provenance.py:160-205` | computed live from S4 + current config | `/projects/{id}/pipeline/status`, dashboard `ProvenanceChip` |
| **S6** | Disk flags (`.reset_barrier`, `.guard_rejections.json`, `.pipeline_last_success`, `.checkpoints/`, soft-holds) | `.sourceprep/` | `recovery.py`, `holds.py`, `pipeline_integrity.py` | selfheal, resume detector, dispatch gates |
| **S7** | Scheduler per-node load (in-memory) | `src/prep/services/pipeline/scheduler.py` | `scheduler.acquire/release/_weighted_share` | `/system/pipeline-queue`, sidebar queue widget |
| **S8** | UI per-stage row state (in-React-state) | `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx` (`compute*State` family) | SSE handler + polling reducer | dashboard panels |
| **S9** | `AutoRebuildWatcher` debounce / auto state (in-memory) | `src/prep/core/watcher.py` | `_on_debounce_fire`, `_on_coverage_check`, `_check_incomplete_deep_enrichment` | watcher-managed; surfaced via `/projects/{id}/watch/status` |

Nine independent state representations. Phase 25B asked for **one** (S1, with S6 reserved for recovery). The drift is real and measurable.

---

## 4. How current §2 findings map to state divergence

For each open finding, the pair (or trio) of systems that disagree. Limited to findings where the divergence is visible:

| Finding | Disagreement | Diagnosis shorthand |
|---|---|---|
| **§2a** (skipped → "Running" forever) | S1 stage_results says `skipped`, S3 stage_metadata stays `pending`, S8 reads from S3 | Writer-side fix landed (P2 added `mark_stage_skipped`); UI-side fix never made S8 prefer S1 |
| **§2b** (Deep Reasoning stuck) | S5 says `match`, S1 says no active run, S8 reads from yet a third signal | Three-way disagreement — S8 doesn't trust S1 or S5 |
| **§2f** (sidebar queue stale) | S7 returns empty, but `/projects/{id}/pipeline/status` says `phase=queued, active=True` | S2 vs S7 — different in-memory stores |
| **§2j** (progress regresses) | Worker writes `progress_current` directly to S8's payload; S1 doesn't know | S1 doesn't own progress data |
| **§2k** (concurrency undershoot + work loss) | S7's `capacity_changed` fires; some subscriber cancels instead of resizing; S1 sees a `STAGE_FAILED` event with no surface | S7 and S1 talk past each other |
| **§2l** (PIPELINE_UP_TO_DATE) | S5 says match (model-only check); S4 manifest exists but `trace_epistemic.jsonl` is empty; S1 was never asked | Resume detector reads S4 not S1 |
| **§2m** (daemon stall) | (out of scope here, but the recovery path used S6 + watcher restart, not S1) | S1 wasn't involved in recovery |
| **§2n** (Stage 15 never complete) | S8 derives `complete` from a count gate (data file derivative), not from S1's `stage_results[antibodies]` | S8 ignores S1 |
| **§2o** (>50% remaining after interrupted rebuild) | S4 manifest written with `success_rate=1.0` for 20/2072 items; S1 transitioned to COMPLETED on that lie | S4 writer disagrees with input reality; S1 trusts S4 blindly |
| **§2p** (second-project hangs on Update) | S7 says nothing queued; S1 for the second project may or may not have transitioned to QUEUED; S8 surfaces neither | Three-system silence |
| **§2q** (auto-incremental never fired) | S9 (watcher) is its own subsystem; S1 wouldn't know whether the watcher even tried | S9 ↔ S1 invisible to each other |
| **§2r** (multiple rows running) | S8 derives `running` from cross-stage SSE hints that flip downstream rows before S1's `current_stage` advances | S8 races S1 |

**Pattern:** In every case, S1 (the state machine) is either ignored, eclipsed, or trusts a lie from another system. The class of bug is structural, not per-finding.

---

## 5. What likely happened (drift narrative — to be validated by §6)

This is a *hypothesis sequence*, not a proved history. The investigation plan in §6 is what would validate or refute it.

1. **Phase 25B (state machine introduced).** S1 is the canonical signal. UI reads from it via `to_dict()`. S3 (run metadata JSON) is added for durability across daemon restarts, intended as a mirror of S1.
2. **Phases ~40–80 (manifests added).** S4 (per-stage manifests) added for freshness/provenance. Resume detector starts reading S4 directly because it's on-disk and survives restarts. S1 is now a duplicate of part of S4.
3. **Phases 89–117 (scheduler hardening).** S7 (scheduler load), S6 (reset barriers, guard rejections, soft-holds) accrete to cover edge cases. Each one is its own boolean gate. Some of them write back into S1 via `Event.*`, some don't.
4. **Phases 70–120 (UI growth).** S8 (`compute*State` family) accumulates one helper per stage type. Each helper reads from a mix of S2/S4/S5 plus SSE flags from S7 — but rarely from S1 directly, because S1's `to_dict()` doesn't have the per-stage detail the UI needs.
5. **Phase 118 U2 (`STAGE_FAILED` rewrite).** Documented in `orchestrator.py:2713-2740`: "Phase 118 U2: a worker failure should mark the pipeline FAILED, not PAUSED. The original Phase 55 'auto-pause for recovery' pattern conflated three things — transient errors, real errors, and user-initiated cancels — and produced the user-visible symptom of 'single project flips to paused while running with nothing else queued.'" This is direct evidence that S1's reliability was being re-asserted as recently as Phase 118, against accumulated drift from Phase 55 onward. Suggests prior fixes have been recurring.
6. **Phases 125–145 (current).** New disk artifacts (`docs_grounding.json`, `concept_generate_manifest.json`, `audit/`, etc.) keep being added per stage, mostly outside S1's awareness. The watcher (S9) was rewritten as its own subsystem with its own gating logic, never integrated with S1. The dashboard's `compute*State` family has accumulated half a dozen helper functions, each making local decisions about state without consulting S1.

If this narrative is roughly right, the drift was incremental and well-intentioned — every individual addition solved a real problem. The aggregate effect is that S1 is no longer load-bearing.

---

## 6. Investigation plan — questions to answer before any re-centering proposal

These are research questions, not tasks. The output is a writeup, not a code change.

### IQ1 — What does S1 actually own today vs what Phase 25B intended?

Read the full state machine module + every callsite of `run.transition(...)` and `run.state`. Build a table: for each state and each transition, which other systems (S2–S9) are kept in sync? Which ones aren't? Which ones do we *want* in sync?

### IQ2 — For each finding §2a–§2r, what would the symptom have looked like if S1 had been the sole authority?

A hypothetical exercise. For each disagreement in §4 above, write out "the symptom we observed" vs "the symptom we would have observed if S8 (or S5, or S7) had read from S1." If most of them collapse into "no symptom — the UI would have shown the correct state," that confirms the hypothesis.

### IQ3 — What signals does the UI legitimately need that S1 can't provide today?

Some UI signals — per-file progress within a stage, swarm budget consumed, AIMD throttle status — are genuinely outside S1's design scope. Itemize them. The re-centering proposal needs to either: (a) extend S1 to own them, or (b) carve out an explicit "non-state-machine" surface that the UI can read without confusion. Anything in this list is a legitimate exception to the "S1 is canonical" rule.

### IQ4 — What's the smallest change that would make S1 canonical for one symptom?

Pick the simplest finding — probably §2r (multiple rows running) — and answer: if `compute*State` consulted `run.stage_results[stage]` directly, would §2r disappear? What about §2a? The answer informs whether re-centering is one targeted change or a whole-rollup refactor.

### IQ5 — What other parallel state stores exist that we haven't listed?

The S1–S9 inventory is what I noticed across the findings. The investigation should grep for `class.*State`, `enum`, `*_manifest`, `pipeline_*.json`, `.sourceprep/.*` flag files, etc. and confirm we haven't missed any. Memory-side stores (SQLite tables in the daemon store) may surface a tenth.

### IQ6 — How would Fable orchestrate the rewrite without breaking things?

Independent of the rewrite design — what's the *test harness* that ensures we don't regress one of the 130+ tests already in `tests/test_*pipeline*`, `tests/test_*scheduler*`, `tests/test_*state*`? Document the matrix Fable needs to be able to run after each step.

### IQ7 — Where does Playwright fit in eventually?

For the user-observable behaviors only. Once the source-of-truth invariants are stated (S1 owns this, S5 owns that, S8 derives the rest), Playwright is the contract verifier: render the dashboard, drive a known sequence of state transitions, assert the UI matches. The §4a row-state table in the Phase 145 README is the Playwright assertion plan, more or less. Fable can drive these in batch once the underlying invariants are stable.

---

## 7. What the corpus needs (the "canonical pipeline behavior reference")

Independent of whether the state machine gets re-centered, Fable will need a single document that says: **"for any sequence of user actions and system events, here is the state every layer should be in."** That document doesn't exist yet. The closest thing today is the Phase 145 README §4 + Phase 91 §1–§Capacity Change Broadcast, but they don't span the full lifecycle (start → pause → resume → fail → recover → reset → restart).

A future `REFERENCE_canonical-pipeline-behavior.md` would have:

1. **The state lattice.** S1's ten states + S2's BuildPhase + the cross-layer joins.
2. **Every user action.** Click Run, click Pause, click Cancel, click Force Reset, click Update, click Star, click Unstar, toggle Manual ↔ Auto.
3. **Every system event.** File change → debounce, run completes → next group, stage fails → recovery, daemon restarts → resume.
4. **For each (action × current state) cell:** which transitions fire, which manifests are written, what the UI should render.

This reference is the input to the eventual Playwright suite *and* the standard the re-centering proposal would be checked against.

**Suggested ownership:** a future `SYNTHESIS_canonical-pipeline-behavior.md` written *after* IQ1–IQ5 have produced evidence (i.e., after we know which systems own what). Don't author the reference doc before the investigation — we'd just be writing wishful thinking.

---

## 8. What we are NOT yet claiming

For the record, so the scrutiny pass can verify:

- **Not claiming the state machine is broken.** It's a working module; transitions are tested; the docstring matches the implementation. The claim is about its *role* in the larger system, not its internal correctness.
- **Not claiming the parallel state stores are wrong.** S4 (per-stage manifests) and S6 (recovery flags) exist for good reasons (durability, crash recovery). The question is whether their growth has displaced S1 from canonical, not whether they're individually justified.
- **Not claiming a rewrite is the answer.** The investigation should validate (a) the drift hypothesis and (b) the smallest-intervention principle (IQ4). Maybe the answer is "make S8 consult S1" and nothing else needs to move.
- **Not claiming Fable should lead.** Fable orchestrating *the test pass after the re-centering lands* makes sense. Fable orchestrating *the re-centering itself* needs a human's design review first — this kind of refactor has to align with intent that isn't fully in the codebase.

---

## 9. Suggested next moves (in corpus, not code)

When bandwidth allows — none of these touch code:

1. **Author IQ1's writeup** as `EVIDENCE_s1-vs-everyone-sync-table.md`. Pure investigation, no fix.
2. **Author IQ2's writeup** as `EVIDENCE_findings-replayed-against-pure-s1.md`. Hypothetical exercise per finding.
3. **Decide IQ3** as a scrutiny question on this synthesis doc.
4. **Once IQ1 + IQ2 land, author** `REFERENCE_canonical-pipeline-behavior.md` per §7.
5. **Only after the reference exists**, write a `PROPOSAL_state-machine-re-centering-v1.md` with the smallest-intervention plan IQ4 surfaced.

Each step is a doc, not a deploy. Each one is scrutinizable before the next.

---

## 10. Cross-references

- State machine module: `src/prep/services/pipeline/state_machine.py` (Phase 25B docstring at top, `_TRANSITIONS` table line 130, `is_active`/`is_terminal` properties line 298+).
- BuildOrchestrator: `src/prep/services/build_orchestrator.py` (`BuildPhase` enum line 80).
- Phase 118 U2 rewrite (evidence of recurring re-assertion): `src/prep/services/pipeline/orchestrator.py:2713-2740`.
- All open findings: README §2a–§2r.
- Existing UI invariants table: README §4a, §4c.
- Existing Phase 91 contract: `docs/Phase91_QueueRefinement/01_Resource_Allocation_Design.md`.
- The proposals that *would benefit* from a re-centered S1: `PROPOSAL_threads-B-and-C-v2-…md` (Thread C's resume detector currently reads S4 directly), `PROPOSAL_thread-A-v1-…md` (capacity broadcast / S7 already disconnected from S1).
