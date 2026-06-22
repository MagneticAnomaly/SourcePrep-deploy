# Phase 145 Evidence — Replaying every open finding against a pure-S1 UI

**Status:** Static evidence capture — 2026-06-18. Hypothetical exercise, not a real fix.
**Source:** Direct code reading by a research agent of every Phase 145 `FINDING_*.md` plus the README §2 entries that don't have their own file, cross-referenced against the UI's `compute*State` family and what S1 would have said at the moment each symptom was observed.
**Companion:** Answers IQ2 of [`SYNTHESIS_2026-06-18_did-the-state-machine-drift.md`](SYNTHESIS_2026-06-18_did-the-state-machine-drift.md). Pairs with [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md).

---

## 0. Headline tally (read this first)

For each of the 18 open Phase 145 findings (§2a–§2r), three possible verdicts under the hypothetical "UI consults S1's `stage_results` instead of its current signal":

| Verdict | Count | Findings |
|---|---:|---|
| **Fixed** by reading S1 | 6 | §2a, §2f (UI side), §2l Thread A, §2n, §2p (UI side), §2r |
| **Persists** — root cause is upstream of S1 | 4 | §2b, §2k, §2l Thread B, §2q |
| **Different bug** — trade-off (would hide useful info) | 2 | §2j, §2o |
| **N/A** — not state-related | 6 | §2c, §2d, §2e, §2g, §2h, §2i, §2m *(§2m is N/A; that's 7 — listed below)* |

(Correction on the row above: §2c, §2d, §2e, §2g, §2h, §2i, §2m = 7 N/A. Total = 6 + 4 + 2 + 7 = 19, accounting for §2l's two threads being counted separately.)

**Verdict on the drift hypothesis:** Validated *for UI rendering*. Re-centering `compute*State` on S1 closes a clear majority of UI-visible symptoms with one localized change. **NOT validated as a complete cure** — four findings are upstream of S1 and require separate work on S5/S6/S7/S9.

---

## 1. Method

For each finding:

1. **Identify the signal the UI actually reads** — cite the code path (most are `compute*State` family in `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:505+`).
2. **State what S1 says** at the moment the symptom occurs — concrete: what would `run.state` and `run.stage_results[<stage>]` actually contain?
3. **Verdict** — Fixed / Persists / Different bug / N/A.

The exercise is hypothetical: no code change. The point is to learn what fraction of the open findings live in the UI's signal selection vs. live in upstream state-store disagreements that no UI change can repair.

---

## 2. Per-finding analysis

### §2a — "Incomplete" / "0% Running" when stage finished (skipped, not-run displays)

- **Current UI signal:** `pipeline_run_metadata.json` stage metadata `status` field (S3). The P2 fix added `mark_stage_skipped()` to write `"skipped"` into S3.
- **What S1 says:** When freshness check skips a stage, the orchestrator fires `Event.STAGE_COMPLETED`. Per `state_machine.py:392–396`, that writes `stage_results[stage] = "completed"`. **S1 has no separate "skipped" value** — it categorically conflates skip-because-fresh with finish-because-ran.
- **Hypothetical:** UI checks `stage_results[stage] == "completed"` → renders green check. The "Running 0%" forever bug disappears, but the skip reason ("skipped: freshness detected") would not surface.
- **Verdict:** **Fixed** (the bug goes away) — but with a UX regression (skip reason lost). The state machine's vocabulary doesn't carry "skipped" as distinct from "completed."

### §2b — Deep Reasoning stuck across all projects (UI vs `provenance.state` drift)

- **Current UI signal:** `computeEpistemicState()` (line 505). Reads `ep?.running` first; falls through to forward-progression SSE hints (line 525); cold-state checks last.
- **What S1 says:** `run.state == RUNNING && current_stage == "enrichment"` → enrichment is the active stage. If state is COMPLETED → all done. If IDLE → nothing happening.
- **Hypothetical:** Even reading S1 directly, the symptom is that **the upstream signal (provenance.state == "match", which is the S5 derivation) is contradicting itself**. S1 owns broad state (RUNNING vs COMPLETED) but not the fine-grained "this stage produced 0 output" signal. Reading S1 doesn't help when S5 is producing a confusing "match" verdict that the UI is forwarding.
- **Verdict:** **Persists.** Root cause is S5 ↔ S8 misalignment, not S1 ↔ anything.

### §2c — Dashboard sluggish / unresponsive

- **Current issue:** SSE event volume + React re-render storms.
- **S1 involvement:** None. Render-layer performance issue.
- **Verdict:** **N/A.** Not state-related.

### §2d — Cross-project surprise triggers (fan-out on settings toggle)

- **Current issue:** Already fixed by P1 (`11033fc2`).
- **S1 involvement:** S1 correctly tracked per-project run state; the bug was in the API caller loop iterating across projects.
- **Verdict:** **N/A.** Already fixed; not a state machine issue.

### §2e — Process Logs panel hides actual error

- **Current issue:** Traceback lines not visually prioritized.
- **S1 involvement:** None. Log-rendering UX.
- **Verdict:** **N/A.**

### §2f — Sidebar queue shows stale state (`/system/pipeline-queue` says empty, `/projects/{id}/pipeline/status` says queued)

- **Current UI signal:** Sidebar widget polls `/system/pipeline-queue` which reads from S7 (scheduler).
- **What S1 says:** `run.is_queued` (per `state_machine.py:311–312`) = True for projects waiting on capacity. If the widget polled `/projects/{id}/pipeline/status` instead, it would see `fast_sync.phase == "queued"` (from S1's `to_dict()`).
- **Hypothetical:** Widget reads S1's phase → shows project as queued. The UI symptom disappears.
- **Verdict:** **Fixed (UI side).** The underlying S1↔S7 sync problem persists — the scheduler still doesn't know the project is queued, so it won't allocate correctly when capacity frees — but the user-visible "queue shows empty" symptom is fixed.

### §2g — ImportError 500s on endpoints

- **Current issue:** Already fixed (`883158db`).
- **S1 involvement:** None. Import bug.
- **Verdict:** **N/A.**

### §2h — Multiple "config" endpoints with no single contract

- **Current issue:** API architecture — six config endpoints with overlapping purpose.
- **S1 involvement:** None. Configuration ownership, not run state.
- **Verdict:** **N/A.**

### §2i — Changeset never reports edits

- **Current issue:** `ManifestStore.write_provenance` dropped `hash_algo` + `built_at` keys (FIXED 2026-06-15).
- **S1 involvement:** S1 doesn't own manifest fields. S4 writer-side bug.
- **Verdict:** **N/A.**

### §2j — Stage progress regresses at sub-stage boundaries

- **Current UI signal:** `epistemic?.progress_current` / `progress_total` from the worker callback (lines 1395–1398). Worker writes directly into the stage snapshot.
- **What S1 says:** S1 knows terminal state (`completed`/`failed`) but not progress numbers. `StageSnapshot` has progress fields (line 69–71) but worker fills them, S1 doesn't validate monotonicity.
- **Hypothetical:** If UI consulted ONLY `stage_results[stage]`, it would render "completed" or "failed" — no progress bar at all. The regression would be invisible (no bar to shrink), but the user loses progress visibility entirely.
- **Verdict:** **Different bug.** Reading from S1 hides the symptom by losing the feature. Real fix is backend-side (make worker progress emission monotonic).

### §2k — Concurrency undershoot + cross-project work loss

- **Current issue:** Scheduler (S7) allocates 2–4 instead of 10; second project's work shut off mid-stage.
- **What S1 says:** Both projects in RUNNING. Doesn't own the `capacity_changed` broadcast (S7) or the worker semaphore sizing.
- **Hypothetical:** UI reads S1 → shows both as running. Doesn't explain or fix the 2–4 vs 10 undershoot — that's S7's domain. Doesn't surface the work-loss failure either.
- **Verdict:** **Persists.** Scheduler bug. S1 not involved.

### §2l Thread A — UI drift on Applifier: rows show "Not run" while backend says `match`

- **Current UI signal:** `GraphEnrichmentPipeline.tsx` reads the `enabled` flag from the stage status blob, which the API derives as `enriched_count > 0` (`pipeline.py:623`). Empty trace_epistemic.jsonl → `enabled: false` → row renders "Not run."
- **What S1 says:** `stage_results["enrichment"] == "completed"` from the prior run (which ran and finished — see EVIDENCE_s1-vs-everyone-sync-table.md §1.1 line 2607).
- **Hypothetical:** UI checks `stage_results["enrichment"]` first → renders complete. The toast "PIPELINE_UP_TO_DATE" and the row state agree.
- **Verdict:** **Fixed.** UI re-centering on S1 closes Thread A cleanly. (Thread B is separate — see below.)

### §2l Thread B — Reset barrier stuck on failed finalize

- **Current issue:** `maybe_clear_scoped_barrier` only called on success path.
- **S1 involvement:** S1 doesn't own the reset barrier (S6).
- **Verdict:** **Persists.** S6 lifecycle bug. Separate orchestrator fix (see [`PROPOSAL_threads-B-and-C-v2`](PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md) Thread B).

### §2m — Daemon stall + frontend lockup

- **Current issue:** Native CoreML hang or lock contention.
- **S1 involvement:** None. Resource/threading issue.
- **Verdict:** **N/A.**

### §2n — Stage 15 (Antibodies) never appears complete

- **Current UI signal:** `finStageState('antibodies', !!(effectiveAntibodiesStatus?.count))` at line 1550–1557. Stage complete iff `count > 0`.
- **What S1 says:** `stage_results["antibodies"] == "completed"` if the worker ran to completion (Event.STAGE_COMPLETED fires regardless of whether the worker produced any rows).
- **Hypothetical:** UI checks `stage_results["antibodies"] == "completed"` instead of count. Across the six scenarios in the finding:
  - (a) Never dispatched → no entry → renders `not_built` ✓
  - (b) Worker raised before manifest write → `failed` ✓
  - (c) Skipped (no concepts) → `completed` ✓ (correct; skip reason hidden)
  - (d) Found concepts but derivation filter rejected all → `completed` ✓
  - (e) `save_many` failed → may or may not have written; ambiguous (worker may have set `failed`)
  - (f) `data_dir` divergence → `completed` (but DB has no rows — *now wrong in a different way*)
- **Verdict:** **Fixed (mostly).** Scenarios (a)(b)(c)(d) render correctly. Scenarios (e)(f) introduce a different false-positive class. The finding's recommended fix (gate on manifest existence + a `ran` boolean) is strictly better than either S1-only or count-only, but S1-only is already an improvement on count-only.

### §2o — Incremental shows >50% remaining after interrupted rebuild

- **Current UI signal:** `epistemic?.progress_current / progress_total` rendering "896 / 2,073 files · 43%".
- **What S1 says:** `stage_results["enrichment"] == "completed"` (the orchestrator wrote success_rate=1.0 even after processing only 20 of 2072). S1 doesn't know the item counts.
- **Hypothetical:** UI shows "Deep Reasoning: complete" with no progress bar. The 43% confusion is gone, but the user can't see that recovery work is happening.
- **Verdict:** **Different bug.** Same shape as §2j — removing the symptom by removing the feature. The real fix is the upstream manifest-writer not lying about success_rate.

### §2p — Two-project incremental blocked during swarm (queue invisibility)

- **Current UI signal:** Sidebar widget polls `/system/pipeline-queue` (S7).
- **What S1 says:** Applifier's deep_enrichment SM in QUEUED state, per `is_queued` property.
- **Hypothetical:** If widget polled `/projects/{id}/pipeline/status` and showed projects with `deep_enrichment.phase == "queued"`, Applifier would render "Queued behind DebateHaus."
- **Verdict:** **Fixed (UI side).** Same shape as §2f. Backend S1↔S7 sync issue persists — scheduler still doesn't know — but the UI symptom disappears.

### §2q — Auto-incremental never fired despite stale files

- **Current issue:** Watcher (S9) dormant; no UI signal whether it fired-and-failed or never fired.
- **What S1 says:** Whether a run is RUNNING. Doesn't own the watcher's debounce decision logic.
- **Hypothetical:** UI shows S1 = IDLE for hours. User can *infer* the watcher should have fired — but still doesn't know *why* it didn't. S9's opacity is independent of S1's visibility.
- **Verdict:** **Persists.** S1 and S9 are orthogonal subsystems.

### §2r — Multiple stages render `running` simultaneously

- **Current UI signal:** `computeEpistemicState()` and siblings (line 505+). Line 525 forward-progression SSE hints: `if (clusterRunning || atlasRunning || deepeningRunning || deepKnowledgeBuilding) return 'complete'`. Downstream-running flags can flip an upstream row before the API's per-stage `running` flag clears.
- **What S1 says:** `run.current_stage_index == X && run.state in ACTIVE_STATES`. **Exactly one stage is active at a time per group state machine.**
- **Hypothetical:** UI computes `running` as `run.current_stage_index == this.index && run.state in ACTIVE_STATES`. Only the stage at `current_stage_index` ever renders `running`. SSE hints ignored.
- **Verdict:** **Fixed.** The multi-spinner symptom disappears entirely. This is the cleanest single win on the table.

---

## 3. Numerical tally (corrected)

| Verdict | Count | Findings |
|---|---:|---|
| **Fixed** | 6 | §2a, §2f (UI), §2l Thread A, §2n, §2p (UI), §2r |
| **Persists** | 4 | §2b, §2k, §2l Thread B, §2q |
| **Different bug** | 2 | §2j, §2o |
| **N/A** | 7 | §2c, §2d, §2e, §2g, §2h, §2i, §2m |
| **Total** | 19 | (§2l is split into Thread A + Thread B) |

---

## 4. What the tally tells us

**The 6 "Fixed" findings are exclusively UI-rendering symptoms.** Every one stems from `compute*State` reading a parallel signal (S3 metadata, S4 manifest fields, S7 scheduler view, S8 SSE forward-hints) when S1's `stage_results[stage]` would have given the right answer with no extra logic. A targeted, low-risk UI change — *make `compute*State` consult `stage_results[stage]` first, fall back to existing logic only when S1 has no opinion* — would close all 6 with one PR-shaped change.

**The 4 "Persists" findings live upstream of S1.** None of them are S1 bugs. They're:

- §2b — S5 (`provenance.state` derivation) is confusing because it only compares model names, not output presence
- §2k — S7 (scheduler) doesn't sync capacity-change cancellations into S1
- §2l Thread B — S6 (reset barrier) has its own lifecycle independent of S1 transitions
- §2q — S9 (watcher) doesn't surface its state through any UI channel

Each needs its own targeted work in its own subsystem. Re-centering the UI on S1 alone does not reach them — but it doesn't *cause* them either.

**The 2 "Different bug" findings are progress-related** (§2j, §2o). Reading S1 alone removes the bug by removing the progress bar — losing the feature. The cleanest fix here is backend-side: workers should emit monotonic, truthful progress numbers, and manifest writers should not lie about `success_rate`. S1 doesn't need to grow a progress field.

**The 7 "N/A" findings are not state-machine questions.** Performance (§2c), API caller bugs (§2d, §2g), log readability (§2e), API architecture (§2h), already-fixed writer bugs (§2i), native runtime hangs (§2m). These are unrelated to the drift hypothesis.

---

## 5. Strategic implication for the proposal

Three tiers, each independently shippable:

| Tier | Closes | Scope | Risk |
|---|---|---|---|
| **T1 — UI re-centering** | 6 findings | One file edit to `GraphEnrichmentPipeline.tsx`'s `compute*State` family | Low — fallback logic preserved when S1 has no opinion |
| **T2 — Upstream subsystem repairs** | 4 findings | Independent per-subsystem: S5 (provenance vocabulary), S6 (barrier lifecycle), S7 (scheduler↔S1 sync), S9 (watcher visibility) | Medium-High per subsystem; each is its own thread |
| **T3 — Long-term reference enforcement** | Prevents future drift | Author `REFERENCE_canonical-pipeline-behavior.md` + Playwright invariant suite that asserts compute*State outputs match S1 + status endpoint labels each field's source store | Low risk per change, but multi-phase scope |

The proposal that follows ([`PROPOSAL_state-machine-re-centering-v1.md`](PROPOSAL_state-machine-re-centering-v1.md)) breaks T1/T2/T3 into discrete sub-threads with their own scrutiny questions.

---

## 6. Cross-references

- The hypothesis: [`SYNTHESIS_2026-06-18_did-the-state-machine-drift.md`](SYNTHESIS_2026-06-18_did-the-state-machine-drift.md).
- IQ1's companion: [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md).
- Each finding cited above has its own `FINDING_*.md` in this directory or its own §2x entry in `README.md`.
- The compute*State family: `packages/ui/src/components/trace/GraphEnrichmentPipeline.tsx:505–680`.
- The state machine: `src/prep/services/pipeline/state_machine.py` (Phase 25B canonical, `stage_results` at line 268, transitions at lines 130–191).
