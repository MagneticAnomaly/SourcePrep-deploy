# PROPOSAL v1 — Re-center the pipeline on the Phase 25B state machine

> **STATUS: DRAFT v1 — awaiting scrutiny — 2026-06-18.** Do not execute as-is. This proposal addresses the architectural drift documented in [`SYNTHESIS_2026-06-18_did-the-state-machine-drift.md`](SYNTHESIS_2026-06-18_did-the-state-machine-drift.md), grounded in the evidence in [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md) + [`EVIDENCE_findings-replayed-against-pure-s1.md`](EVIDENCE_findings-replayed-against-pure-s1.md), and targets the contract in [`REFERENCE_canonical-pipeline-behavior.md`](REFERENCE_canonical-pipeline-behavior.md). It is structured for **deliberate second-guessing before execution**. Every sub-thread has an explicit "what to verify before approving" section and a risk register. Some sub-threads depend on open questions (OQ1–OQ8 in the REFERENCE doc) that must be answered first.

**Goal:** When this proposal is executed (in tiered phases, not all at once), the result is: (i) the UI's `compute*State` family consults S1 as the canonical source of pipeline state — closing 6 of 18 open findings with one localized intervention; (ii) the four "Persists" findings (§2b, §2k, §2l Thread B, §2q) each get their own targeted upstream repair; (iii) a Playwright invariant suite asserts §4 of REFERENCE_canonical-pipeline-behavior.md so future drift is caught before it reaches the user; (iv) the architectural contract is documented in code (not just in markdown) so the next reviewer doesn't have to derive it from scratch.

**Architecture:** Three tiers — T1 (UI re-centering, smallest + highest-leverage), T2 (subsystem repairs, four independent sub-threads), T3 (long-term invariant enforcement). Each sub-thread can ship independently. Tier ordering is by risk-adjusted yield, not by code dependency. **Recommended execution order: T1 → T2 in any order → T3 → re-evaluate Threads A and B-and-C-v2 against the new contract.**

**Independence:** Each sub-thread is independent of every other (they touch different files, different subsystems, different language stacks). T1 ships from one PR; each T2 sub-thread from its own; T3 from a few.

**Out of scope (still):** Redesigning Phase 25B itself (we're restoring its contract, not changing it). Performance work (§2c). API config redesign (§2h). Native runtime hangs (§2m).

---

## 0. Pre-flight: what must be true before executing

This proposal depends on OQ1–OQ8 in REFERENCE_canonical-pipeline-behavior.md §9. **Do not execute T1 without first answering OQ1** (does S1 grow a `"skipped"` value?) and **OQ5** (does the status endpoint label field sources?). Other OQs gate other tiers — noted per sub-thread.

T1 also needs the existing UI tests to be wired up — `packages/ui` has no test runner today per `PROPOSAL_threads-B-and-C-v2-…md` Thread D. Either piggyback on Thread D's vitest install OR include the install as part of T1.

---

## 1. Tier T1 — UI re-centers `compute*State` on S1  *[evidence: solid; closes 6 findings]*

### T1 — Premise

Per EVIDENCE_s1-vs-everyone-sync-table.md §5 and EVIDENCE_findings-replayed-against-pure-s1.md §2: every `compute*State` function in `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:505+` reads from S4 manifest fields, never from S1's `stage_results`. The status endpoint already serves S1's `stage_results` in the response payload — it's available, the UI just ignores it.

The intervention is: **make every `compute*State` function consult `stage_results[stage_id]` first; fall through to the existing cold-state logic only when S1 has no opinion on the stage (`<absent>` in `stage_results`).**

### T1 — Scope and shape

Five `compute*State` functions plus the finalize `finStageState` helper. Each gets the same prepended check.

Helper to add at the top of the file:

```typescript
/**
 * Phase 145 T1: trust S1's stage_results as the canonical state signal.
 *
 * S1 (PipelineGroupStateMachine) owns stage_results per its Phase 25B
 * docstring. When stage_results[stage_id] has a value, it overrides
 * cold-state derivation. Cold-state checks remain as fallback for
 * stages S1 has no opinion on yet.
 */
function stateFromS1(
  stageId: string,
  groupState: { state?: string; current_stage?: string; current_stage_index?: number; stage_results?: Record<string, string> },
  stageIndex: number,
): StageState | null {
  // S1's stage_results vocabulary (per state_machine.py:268, post-OQ1 resolution)
  const result = groupState?.stage_results?.[stageId];
  if (result === 'completed') return 'complete';
  if (result === 'failed') return 'failed';
  if (result === 'skipped') return 'skipped';  // OQ1 Option A only
  if (result === 'user_stopped') return 'paused';
  if (result === 'restored_from_backup') return 'recovering';

  // No opinion in stage_results. Check whether this stage is the active one.
  if (groupState?.state === 'running' && groupState?.current_stage === stageId) return 'running';
  if (groupState?.state === 'queued') return 'queued';
  if (groupState?.state === 'paused') return 'paused';
  if (groupState?.state === 'recovering') return 'recovering';

  // Stage is downstream of current — implicitly not yet reached
  if (groupState?.state === 'running' && stageIndex > (groupState?.current_stage_index ?? -1)) {
    return 'not_yet_reached';
  }

  // S1 has no opinion and the group is idle. Caller falls back to cold-state.
  return null;
}
```

Each `compute*State` function gets one new line at the top of its body:

```typescript
function computeEpistemicState(
  trace: TraceStageInfo,
  aug?: AugmentationStatus,
  ep?: EpistemicStatus,
  running?: boolean,
  // ... existing args ...
  // NEW: S1 group state passed through from status payload
  groupState?: PipelineGroupState,
  stageIndex?: number,
): StageState {
  // T1: trust S1 first
  const s1 = groupState && stageIndex !== undefined
    ? stateFromS1('enrichment', groupState, stageIndex)
    : null;
  if (s1 !== null) return s1;

  // ... existing logic unchanged as fallback ...
}
```

### T1 — TDD step list (after OQ1+OQ5 resolved + vitest wired)

- **T1.1** — In `GraphEnrichmentPipeline.tsx`: export `computeEpistemicState`, `computeModuleState`, `computeAtlasState`, `computeDeepeningState`, `computeFastKnowledgeState`, `computeDeepKnowledgeState`. (Same export change as PROPOSAL_threads-B-and-C-v2 Thread C C1.1 — if that lands first, T1 reuses it.)
- **T1.2** — Write `packages/ui/src/components/trace/__tests__/computeStateFromS1.test.ts`. Per-function cases:
  - "Returns `complete` when `stage_results[id] == 'completed'`"
  - "Returns `failed` when `stage_results[id] == 'failed'`"
  - "Returns `skipped` when `stage_results[id] == 'skipped'`" (Option A only)
  - "Returns `running` when group is RUNNING and current_stage matches"
  - "Returns `not_yet_reached` when stage index > current_stage_index"
  - "Falls through to existing cold-state logic when `stage_results` has no entry AND group is IDLE"
  - **Control case:** "Does NOT change behavior when groupState is undefined (backward-compat)" — same fixtures as today's test suite (if any).
- **T1.3** — Run tests; expect new tests to FAIL (helper doesn't exist yet).
- **T1.4** — Add `stateFromS1` helper + wire it as the first check in each `compute*State`.
- **T1.5** — Run tests; expect PASS.
- **T1.6** — Run existing vitest suite (`pipelineRollup.test.ts` etc.); expect PASS (backward-compat preserved).
- **T1.7** — `npm run typecheck` in `packages/ui`.
- **T1.8** — Build the dashboard, hard-refresh against Applifier (still in the §2l Thread A drifted state). Verify: deep-enrichment rows that the backend reports as `provenance.state == "match"` AND `stage_results == "completed"` now render `complete` instead of "Not run." Overall Health rises.
- **T1.9** — Commit.

### T1 — What this closes

Per EVIDENCE_findings-replayed-against-pure-s1.md §3:

- §2a (UI side of skipped→running) — IF Option A for OQ1
- §2f (queue widget reads S7; needs separate change to read `/projects/<id>/pipeline/status.<group>.phase` from S1)
- §2l Thread A (the row-vs-toast contradiction)
- §2n (Stage 15 count-gate replaced by `stage_results["antibodies"]`)
- §2p (UI side — queue badge appears for queued projects)
- §2r (sequential running invariant — only `current_stage` renders `running`)

### T1 — What this does NOT close

- §2k (scheduler subsystem; T2.b)
- §2l Thread B (reset barrier; PROPOSAL_threads-B-and-C-v2 Thread B)
- §2q (watcher visibility; T2.d)
- §2b (S5 derivation; T2.a)
- §2j, §2o (manifest writer / progress reporting; needs backend fix not addressed here)

### T1 — Risk register

| # | Risk | Mitigation |
|---|---|---|
| RT1.1 | The fallback logic still runs for stages S1 has no opinion on (mostly: never-run projects). If a stage's cold-state check is wrong, T1 doesn't fix it. | Acceptable — T1 is additive, not replacement. The wrong cold-state checks become visible via I10 + dashboard smoke. |
| RT1.2 | `stage_results` may contain stale entries from prior runs that don't get cleared on `RESET`. UI would render stale "completed" for a freshly-reset project. | Verify in T1.8 against a Force-Reset project — does `RESET` event clear `stage_results`? Per state_machine.py reset path (line 187), yes — but confirm. |
| RT1.3 | The `stage_results = "user_stopped"` value (orchestrator.py:2735) is written without firing an Event. Status payload may serialize it; UI maps to `paused`. If the project is actually IDLE/QUEUED elsewhere this could mislead. | Test case for the "user_stopped" path. If it's a problem, the orchestrator should fire `Event.CANCEL` instead of dual-write. |
| RT1.4 | Option B for OQ1 (S1 doesn't grow `"skipped"`) means the UI must consult S3 for skip reason. T1's helper would map `"completed"` → `complete` and lose the skip distinction. | If Option B is chosen, the helper's `completed` branch must additionally consult `status.stages[id].skipped_reason` (from S3) and return `'skipped'` when present. Adds a second source — partially defeats the re-centering goal. |
| RT1.5 | The `groupState` parameter is now optional (default `undefined`). Tests must explicitly pass it; production code paths must wire it from the status payload. If a caller forgets, behavior silently reverts to today. | Track callers in the typecheck step (T1.7). Make groupState required after the migration window. |
| RT1.6 | The helper assumes one stage per group, but Stage 15 (`antibodies`) might be tested across multiple groups depending on how the finalize wave dispatch works (per Phase 96 reorganization concept). | Confirm via grep that each stage_id appears in exactly one group's `stages` list. If multiple, the helper needs a (group_id, stage_id) key. |

### T1 — What to verify before approving (the scrutiny prompts)

1. **OQ1 is resolved.** The choice between Options A and B materially changes T1's helper.
2. **OQ5 is resolved.** If the status endpoint will add per-field source labels, T1's helper can use them.
3. **vitest is installed in packages/ui.** Either piggyback on PROPOSAL_threads-B-and-C-v2 Thread D OR include the install in T1.
4. **RT1.2 cleared.** Verify `RESET` event clears `stage_results` on the actual state machine.
5. **RT1.6 cleared.** Confirm no stage_id appears in multiple groups.
6. **Backward-compat tests in T1.2** — these must be specific. If today's `pipelineRollup.test.ts` passes a fixture without `groupState`, that fixture is the control case.

---

## 2. Tier T2 — Subsystem repairs (four independent sub-threads, no order)

Each closes one of the "Persists" findings. None depends on another. None depends on T1 (T1 is UI; T2 is backend or wiring).

### T2.a — S5 (`provenance.state`) vocabulary fix  *[evidence: partial; closes §2b]*

**Premise:** `pipeline_provenance.py:160–205` derives `provenance.state` purely from model comparison. `"match"` means "model matches current config," not "stage produced output." UI consumes `"match"` and treats it as a completion signal (per §2b symptom). **Either** rename the state values for clarity (`"model_match"` / `"model_drift"` instead of `"match"` / `"drift"`), **or** add a separate `output_present` field S5 also computes from S4's output_files map.

**Decision deferred to scrutiny.** Both options work. Renaming is breaking; adding is non-breaking.

**Test surface:** existing `tests/test_*provenance*` (`grep -l provenance tests/`) — modify whichever pin the current vocabulary.

**Closes:** §2b.

### T2.b — Scheduler (S7) ↔ S1 synchronization  *[evidence: hypothesis only, gated on PROPOSAL_thread-A diagnostic DG-A]*

**Premise:** Per [`FINDING_concurrency-undershoot-and-cross-project-work-loss.md`](FINDING_concurrency-undershoot-and-cross-project-work-loss.md) and [`PROPOSAL_thread-A-v1-…md`](PROPOSAL_thread-A-v1-concurrency-undershoot-and-work-loss.md), the scheduler's capacity broadcasts don't sync into S1, and work loss happens when a `capacity_changed` event triggers cancellation rather than resize.

**This sub-thread is already PROPOSAL_thread-A-v1** in flight. T2.b is just a marker that Thread A's work also serves the re-centering hypothesis. **Read PROPOSAL_thread-A-v1 directly; don't author a competing T2.b plan.**

**Closes:** §2k.

### T2.c — Reset barrier (S6) lifecycle fix  *[evidence: solid, already specified]*

**Premise:** Per [`FINDING_reset-barrier-stuck-on-failed-finalize.md`](FINDING_reset-barrier-stuck-on-failed-finalize.md) and [`PROPOSAL_threads-B-and-C-v2-…md`](PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md) Thread B, `maybe_clear_scoped_barrier` runs only on success paths. Failure paths leak the barrier.

**This sub-thread is already PROPOSAL_threads-B-and-C-v2 Thread B.** T2.c is a marker; don't compete.

**Closes:** §2l Thread B.

### T2.d — Watcher (S9) visibility  *[evidence: solid via FINDING §2q; closes §2q]*

**Premise:** Per [`FINDING_auto-incremental-never-fired-despite-stale-files.md`](FINDING_auto-incremental-never-fired-despite-stale-files.md), the watcher's debounce decisions are invisible — user can't tell whether it fired-and-failed or never fired. Per REFERENCE_canonical-pipeline-behavior.md §6.5: every watcher decision should be queryable.

**Scope:**

- Modify: `src/prep/core/watcher.py` (add `_decision_history: deque[WatcherDecision]` with max 10)
- Modify: `src/prep/api/routers/projects/watch.py` (add `decisions` field to `/projects/<id>/watch/status` response)
- Modify: dashboard (add a "watcher idle since…" / "last skip: <reason>" line to the Graph Scope card or a separate panel)

**TDD step list (sketched):**

- T2.d.1 — Author `tests/test_phase145_watcher_decision_history.py` with cases: watcher fires → decision recorded with `action: "fired"`; watcher skips due to barrier → `action: "skip_barrier_active"`; watcher skips due to budget exhaustion → `action: "skip_budget_exhausted"`; debounce coalesces → not recorded as separate decision.
- T2.d.2 — Implement the history + API surface.
- T2.d.3 — Dashboard fetches `/projects/<id>/watch/status` and renders the last decision under Graph Scope.
- T2.d.4 — Smoke: touch a file in a project with Auto enabled; confirm the dashboard shows `last_decision: "fired" at <timestamp>` within debounce + 1s.

**Closes:** §2q (with Option A for OQ3).

### T2 — Summary table

| Sub-thread | Closes | Status | Where the work lives |
|---|---|---|---|
| T2.a | §2b | Open, specify per OQ resolution | This proposal |
| T2.b | §2k | **Already in flight** as PROPOSAL_thread-A-v1 | Cross-reference there |
| T2.c | §2l Thread B | **Already in flight** as PROPOSAL_threads-B-and-C-v2 Thread B | Cross-reference there |
| T2.d | §2q | Open, specified above | This proposal |

So T2's *original* new work is T2.a + T2.d only. T2.b and T2.c are pre-existing.

---

## 3. Tier T3 — Long-term invariant enforcement

### T3.a — Status endpoint per-field provenance labels

**Premise:** OQ5 resolution. Add a `_provenance` sub-object to the `/projects/<id>/pipeline/status` response listing source per field. Lets the UI pick deliberately and lets debugging tools show the source store.

**Files:** `src/prep/api/routers/pipeline.py` (add the labeling).
**Test:** `tests/test_phase145_status_endpoint_provenance.py` (assert each field has a source label).
**Risk:** payload size grows ~30%. Acceptable for a debugging-grade signal.

### T3.b — Playwright invariant suite

**Premise:** REFERENCE_canonical-pipeline-behavior.md §8 defines 12 UI invariants. Author a Playwright suite that asserts each.

**Files:** `tools/playwright/pipeline-uat/invariants.spec.ts` (new). Use the existing playwright_smoke.py harness if it's still alive, or build fresh per Phase 145 README §6.1.

**Triage per OQ8:** Some invariants are CI-grade (I1, I2, I3, I10 — pure rules); others are timing-sensitive (I9 — watcher fire). The scrutiny pass triages.

**Closes:** prevents future drift of the §2a/§2l/§2n/§2r class.

### T3.c — Code-side documentation of the contract

**Premise:** REFERENCE_canonical-pipeline-behavior.md §4 ownership rule is currently only in markdown. Add a docstring or a typed contract to `src/prep/services/pipeline/state_machine.py` that names S1 as canonical for `stage_results` AND references the REFERENCE doc.

**Files:** `src/prep/services/pipeline/state_machine.py` (extend the module docstring with a "Sole canonicity" section).
**Risk:** Documentation rot if not maintained. Mitigation: add to OQ7 — the doc reference goes in CLAUDE.md as a must-update file.

### T3.d — `prep_concept` to encode the rule

Save a concept via the prep MCP that captures "S1 is canonical for `stage_results`" with the assertion: `grep -n "stage_results" packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx — must return ≥1 match in stateFromS1()`. This makes the rule auditable by the immune system.

### T3 — Summary

| Sub-thread | What | Risk |
|---|---|---|
| T3.a | Status endpoint adds `_provenance` labels | Low |
| T3.b | Playwright invariant suite for 12 UI invariants | Low per invariant |
| T3.c | Encode the canonicity rule in state_machine.py docstring + CLAUDE.md | Low |
| T3.d | `prep_concept` with grep assertion | Low |

T3 is mostly low-risk paperwork that pays compounding dividends. Recommended to ship alongside T1.

---

## 4. Cross-cutting risk register (the second-guess prompts)

This is the explicit "scrutinize this proposal" section. Each risk gets a question the scrutiny pass must answer.

| # | Risk | Question for scrutiny |
|---|---|---|
| R1 | T1's helper makes `groupState` optional. If a future caller forgets to pass it, behavior reverts to today's bugs silently. | Should `groupState` be required immediately (breaking callers) or after a migration window? |
| R2 | T1 depends on OQ1 (skipped vocabulary). If OQ1 chooses Option B, T1's helper grows a second-source consultation for S3 — partially defeats the purpose. | Has OQ1 been answered? If Option B, is the partial defeat acceptable? |
| R3 | RT1.6 — same stage_id in multiple groups would break the helper's lookup. | Did anyone verify this? |
| R4 | The 4 "Persists" findings (T2) are independent of T1. If only T1 ships, the user sees clear progress on 6 findings but the 4 backend ones remain — risk of "looks fixed, isn't fixed" perception. | What's the communication plan? Should the dashboard surface "4 known persistent issues" until T2 ships? |
| R5 | T2.a (S5 vocabulary fix) is itself a state-store change. If we rename `"match"` → `"model_match"`, every grep / test / doc / dashboard that hardcoded `"match"` must be updated. | Is there a deprecation path (return both old and new values during a window)? |
| R6 | T3.b (Playwright suite) requires the dashboard to be in a known-state. Today the dashboard state depends on which projects are registered + which manifests are on disk. Tests need fixtures. | What's the fixture strategy — fresh tmp projects per test, or shared seeded state? |
| R7 | T3.c puts the canonicity rule in two places (REFERENCE doc + state_machine.py docstring). If they drift, which wins? | Convention: docstring wins for code-level claims; REFERENCE wins for behavioral claims. Make explicit. |
| R8 | The proposal assumes Fable orchestrates the eventual execution. Fable may decide to re-shape it. The proposal's value is in the analysis, not the prescriptive task list. | Is the analysis robust enough that Fable could ignore the task list and re-derive the same conclusions from EVIDENCE + REFERENCE? |
| R9 | This proposal's diff is large in scope but each sub-thread is small. Reviewing it as one giant PR would hide subtleties. | Mandate one PR per sub-thread (T1 alone, T2.a alone, etc.). Don't bundle. |
| R10 | RT1.4 — Option B for OQ1 keeps a dual source (S1 "completed" + S3 "skipped reason"). This perpetuates the drift the proposal aims to eliminate. | If chosen, log Option B as a known compromise + schedule a follow-up to revisit. |

---

## 5. Decision dependency graph

```
OQ1 (skipped vocabulary)──────────────┐
                                       ├──► T1 (UI re-centering)
OQ5 (status endpoint labels)──────────┤
                                       │
T1 (close 6 findings)──────────────────┴──► T3.b (Playwright invariants)
                                            │
T2.a (S5 vocab)──► closes §2b               │
T2.b = PROPOSAL_thread-A-v1 ──► closes §2k  │
T2.c = PROPOSAL_threads-BC-v2 Thread B      │
                ──► closes §2l Thread B     │
T2.d (watcher visibility)──► closes §2q ────┘

T3.a (status labels) ─► independent
T3.c (code-side contract) ─► after T1 lands
T3.d (prep_concept) ─► after T1 lands
```

T1 + T2.a + T2.d can be authored in parallel once OQ1/OQ5 resolve. T3 follows after T1.

---

## 6. What ratification looks like (the scrutiny output format)

When this proposal is scrutinized, the output is a `SCRUTINY_v1_state-machine-re-centering.md` doc with:

1. A decision per OQ1–OQ8.
2. An answer per R1–R10.
3. A revised execution order (or an endorsement of the recommended order).
4. A "ready to execute" or "blocked, needs v2" verdict per sub-thread.
5. Any new defects discovered → recorded as D1, D2, … and either fixed in v2 or accepted with rationale.

Don't author the scrutiny inline if it's substantial — separate doc.

---

## 7. What this proposal explicitly does NOT propose

So the scrutiny pass can verify these are correct omissions:

- **No redesign of Phase 25B.** The state machine vocabulary + transitions stay. We're restoring its canonical role, not changing it (except possibly OQ1's `"skipped"` addition).
- **No removal of S2–S9.** Every parallel store exists for a reason. We're recentering the *reader-side* trust hierarchy, not deleting durability/recovery state.
- **No new state machine layer.** No "MetaStateMachine" wrapping all nine stores. That direction was rejected in synthesis §8.
- **No UI rewrite.** T1 is one helper + one line change per `compute*State` function. ~50 lines total of net code change.
- **No watcher rewrite (S9).** T2.d adds visibility, not behavior change.
- **No scheduler rewrite (S7).** T2.b defers entirely to PROPOSAL_thread-A-v1.

---

## 8. What we are explicitly NOT yet claiming (so scrutiny can verify)

- Not claiming T1 alone fixes the dashboard. T1 closes 6 findings; the other 12 are out of T1's scope. The user-perceived improvement is significant but partial.
- Not claiming Fable will execute this verbatim. The proposal is a *scrutiny-ready candidate*, not a directive.
- Not claiming the smallest-intervention principle (per synthesis IQ4) is exhausted. There may be even smaller interventions for individual findings — but T1 is the smallest single intervention that closes multiple findings at once.
- Not claiming the REFERENCE doc is complete. OQ1–OQ8 + the (action × state) matrix in §5 of REFERENCE may have gaps. Scrutiny is supposed to find them.
- Not claiming this proposal supersedes Threads A or B-and-C-v2. Both ship independently; this proposal addresses the meta-layer, they address specific symptoms.

---

## 9. How Fable should approach this corpus (operational note)

Recommended reading order when Fable opens Phase 145 cold:

1. `README.md` §1 + §2 (symptom catalog).
2. The 8 `FINDING_*` files (one per open §2 entry that has its own file).
3. `SYNTHESIS_2026-06-18_did-the-state-machine-drift.md` (the hypothesis).
4. `EVIDENCE_s1-vs-everyone-sync-table.md` (what is).
5. `EVIDENCE_findings-replayed-against-pure-s1.md` (what would change).
6. `REFERENCE_canonical-pipeline-behavior.md` (the target contract).
7. This proposal.
8. The two prior proposals (`PROPOSAL_thread-A-v1`, `PROPOSAL_threads-B-and-C-v2`) and their relationship to T2.b/T2.c above.

Then before executing anything:

1. Answer OQ1–OQ8 (decisions belong to Fable + a human).
2. Run a scrutiny pass on this proposal, producing the `SCRUTINY_*.md`.
3. Revise per scrutiny → v2 if needed.
4. Execute T1 first (highest leverage, lowest risk).
5. Re-evaluate Threads A and B-and-C-v2 against the new (post-T1) baseline before executing them — some of their tasks may overlap or be obviated.

---

## 10. Cross-references

- Hypothesis: [`SYNTHESIS_2026-06-18_did-the-state-machine-drift.md`](SYNTHESIS_2026-06-18_did-the-state-machine-drift.md).
- Evidence: [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md), [`EVIDENCE_findings-replayed-against-pure-s1.md`](EVIDENCE_findings-replayed-against-pure-s1.md).
- Target contract: [`REFERENCE_canonical-pipeline-behavior.md`](REFERENCE_canonical-pipeline-behavior.md).
- Cross-thread proposals: [`PROPOSAL_thread-A-v1-…md`](PROPOSAL_thread-A-v1-concurrency-undershoot-and-work-loss.md), [`PROPOSAL_threads-B-and-C-v2-…md`](PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md).
- Prior re-centering precedent (encoded as prep concept): "Canonical registry extracted to break triple-source duplication after audit finding" (`packages/ui/src/config/mcpSetup.ts`).
- Other prior precedent (~600-line cleanup): "Changeset-driven pipeline eliminates per-stage staleness derivation" (Phase 134).
- Code: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:505+` (compute*State family — T1 target); `src/prep/services/pipeline/state_machine.py` (S1, T3.c target); `src/prep/services/pipeline_provenance.py:160–205` (S5, T2.a target); `src/prep/core/watcher.py` (S9, T2.d target); `src/prep/api/routers/pipeline.py:432–960` (status endpoint, T3.a target); `src/prep/api/routers/projects/watch.py` (T2.d target).
