# Phase 145 Scrutiny — Pass v1 on `PROPOSAL_state-machine-re-centering-v1.md`

**Status:** First scrutiny pass — 2026-06-18. Self-scrutiny by the same author who wrote the proposal. **A fresh-eyes pass by an independent agent is still recommended** before v2 is authored (see §6 below).
**Author:** Same assistant that drafted the proposal — bias risk noted.
**Method:** Re-read [`PROPOSAL_state-machine-re-centering-v1.md`](PROPOSAL_state-machine-re-centering-v1.md), [`EVIDENCE_findings-replayed-against-pure-s1.md`](EVIDENCE_findings-replayed-against-pure-s1.md), [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md), and [`REFERENCE_canonical-pipeline-behavior.md`](REFERENCE_canonical-pipeline-behavior.md) end-to-end. Spot-verified the most consequential code claims directly. Then deliberately tried to break each verdict, each task, each risk-register entry.

**Headline:** **11 defects found.** Three are critical (would mis-execute T1 in production). Four are documentation issues. Four are scope/framing issues. **The drift hypothesis still holds**, but the proposal's claim "T1 closes 6 findings cleanly" is overstated — under closer inspection it's "**4 clean wins, 2 partial wins that need T2.a bundled, 2 verdicts that were wrong in IQ2**." Don't execute T1 as written; revise per D1+D3 first.

---

## 0. Defect catalog (severity-ordered)

| # | Severity | What | Where | Fix in v2? |
|---|---|---|---|---|
| **D1** | Critical | §2l-A and §2n verdicts in IQ2 oversimplified — T1 alone would render `'complete'` for stages that produced 0 output, **actively masking the bug**. T1 must bundle T2.a (output-presence signal) to be net-positive for these two findings. | EVIDENCE_findings-replayed §2l-A, §2n; PROPOSAL T1 scope | YES |
| **D2** | Critical | §2j and §2o verdicts in IQ2 wrong — recorded as "Different bug" assuming T1 *replaces* progress display. T1 actually *adds a check before* existing logic; progress display path is unchanged. Both should be **Persists**. | EVIDENCE_findings-replayed §2j, §2o + the tally | YES |
| **D3** | Critical | T1 helper's exact-string match `if (result === 'failed')` will **never match real failures**. `orchestrator.py:2742` overwrites with `f"failed: {slot.error}"` (e.g., `"failed: Dispatch paused on soft-hold..."`). Confirmed by direct read of orchestrator.py:2742. | PROPOSAL T1 helper code | YES |
| **D4** | Important | `"user_stopped"` written without firing `Event.STAGE_FAILED` (orchestrator.py:2735) creates SM state inconsistency: state could be RUNNING while `stage_results[X] == "user_stopped"`. Helper returns `'paused'` despite group being RUNNING. | PROPOSAL T1 helper logic | Probably YES |
| **D5** | Important | T1 depends on OQ1+OQ5 per the proposal's "what must be true before executing" — but actually T1 can ship with Option B fallback for OQ1 (just don't include the `"skipped"` branch). OQ5 also not strictly required if helper takes the existing payload shape. Dependencies overstated. | PROPOSAL §0 + T1 scrutiny prompts | Note in v2 |
| **D6** | Important | Revised tally after D1+D2 changes the proposal's headline economics. New count: 4 cleanly Fixed, 2 partially fixed (need T2.a bundled), 6 Persists (not 4), 7 N/A. Proposal headline "closes 6 findings" → "closes 4 cleanly, 2 with T2.a bundled." | PROPOSAL §1, §2 summary | YES |
| **D7** | Documentation | REFERENCE §5.1 "Click Run on COMPLETED group" cell is ambiguous about RESET-then-START vs PIPELINE_UP_TO_DATE 409. Today's behavior depends on `force_from_start` flag; reference should be explicit. | REFERENCE §5.1 row | Edit inline |
| **D8** | Documentation | REFERENCE §6.4 "capacity_changed resizes; never cancels" is the *target*, not current behavior (current cancels — that's §2k). Needs a current-vs-target label so a reader doesn't take it as a description of what's deployed. | REFERENCE §6.4 | Edit inline |
| **D9** | Documentation | PROPOSAL §9 "How Fable should approach this corpus" reading order omits `PROPOSAL_thread-A-v1` and `PROPOSAL_threads-B-and-C-v2`. Inconsistent with the T2.b / T2.c sub-threads that explicitly defer to them. | PROPOSAL §9 | Edit inline |
| **D10** | Documentation | OQ7 in REFERENCE ("who updates this doc?") raises the question but doesn't propose an owner. Suggest amending REFERENCE §9 OQ7 with a recommended mechanism (CLAUDE.md "must-update" reference). | REFERENCE §9 OQ7 | Edit inline |
| **D11** | Scope/framing | The `mcpSetup.ts triple-source` precedent the proposal cites is structurally weaker than implied — that was static config extraction; this is runtime state. Citing as "exact precedent" overstates the analogy. Should be "similar pattern." | PROPOSAL §10, EVIDENCE §10 cross-refs | Edit inline |

---

## 1. The critical defects, with evidence

### D1 — T1 alone makes §2l-A and §2n worse, not better

**IQ2's verdict:** §2l-A (Applifier "Not run" vs `match`) → **Fixed.** §2n (Antibodies never complete) → **Fixed (mostly).**

**Reality:** Both findings have the same root shape: **a stage ran to completion per the orchestrator but produced 0 useful output.** On Applifier, the prior deep_enrichment run fired `Event.STAGE_COMPLETED` after producing 0 enriched nodes (trace_epistemic.jsonl is 0 bytes per earlier evidence capture). So `stage_results["enrichment"] == "completed"`.

If T1 ships alone:

- Today: UI renders `'not_built'` (S4 `enabled: false` because `enriched_count == 0`). The user sees "Not run" — which is *honest about the failure to produce*. The user has reason to click Force Reset.
- Under T1: UI renders `'complete'` because `stage_results["enrichment"] == "completed"`. The user sees a green check — but the stage produced nothing useful. The user has **no reason to suspect anything is wrong**.

This is worse than current behavior in a meaningful way: T1 hides the existing-but-honest signal of "stage didn't produce output" behind a green check derived from `stage_results`. The current UI is wrong in the direction of "looks incomplete when complete-per-orchestrator." T1's UI would be wrong in the direction of "looks complete when zero-output."

**For §2n** the same logic applies: `stage_results["antibodies"] == "completed"` after the worker runs to completion even if it derived zero antibodies. T1 renders green check; user has no signal that the stage is silently producing nothing.

**Fix in v2:** T1 must be **bundled with T2.a (output-presence signal)** before either §2l-A or §2n is honestly closed. The combined render rule:

```
if S1.stage_results[X] == "completed" AND S4.output_present(X):
    return 'complete'
elif S1.stage_results[X] == "completed" AND NOT S4.output_present(X):
    return 'complete_empty'   # new state — "ran but produced 0"
elif ...
```

This requires T2.a to land *first* or *concurrently*. Reorder the proposal accordingly. Alternatively, T1 ships with an explicit "warns when stage_results says complete but cold-state count is 0" Thread D-style chip (per [`PROPOSAL_threads-B-and-C-v2`](PROPOSAL_threads-B-and-C-v2-barrier-and-resume-detector.md) Thread D) — same effective result.

### D2 — §2j and §2o verdicts misread T1's mechanics

**IQ2's verdicts:** §2j (progress regresses) → **Different bug.** §2o (>50% remaining) → **Different bug.**

**IQ2's reasoning (verbatim from EVIDENCE_findings-replayed §2j):** "If UI consulted ONLY stage_results[stage], it would render 'completed' or 'failed' — no progress bar at all."

**Why this is wrong:** T1 does NOT consult ONLY stage_results. The helper falls through to existing logic when stage_results has no entry for that stage. During a run, the active stage has no entry in stage_results until STAGE_COMPLETED fires. So during the live run when §2j and §2o symptoms occur, the helper returns `null` for that stage, fall-through happens, existing progress-rendering path runs unchanged, progress bar appears with the same data source as today. The regression / 43% confusion is unchanged.

**Correct verdict for both:** **Persists.** T1 doesn't touch the progress signal path.

**Fix in v2:** Update EVIDENCE_findings-replayed-against-pure-s1 §2j and §2o entries. Update the tally. Update PROPOSAL §1 headline economics.

### D3 — T1 helper's exact-string match never catches real failures

**The helper as written:**

```typescript
if (result === 'failed') return 'failed';
```

**Direct read of orchestrator.py:2742 (verified):**

```python
matching_run.stage_results[stage.value] = f"failed: {slot.error}"
```

So after a real worker failure, `stage_results[X]` is e.g. `"failed: Dispatch paused on soft-hold (project='...', endpoint='cloud:default_ollama')"`. The literal `"failed"` is written transiently by `state_machine.py:407` during the `STAGE_FAILED` transition but **immediately overwritten** by the orchestrator with the detail string.

The helper's exact match would not match. The helper would fall through, see group state == FAILED (or RUNNING during transitions), and render whatever the fall-through logic produces. **Real failures would still show inconsistent state.**

**Fix in v2:** Use a prefix match — `if (result === 'failed' || result.startsWith('failed:')) return 'failed'`. Apply the same logic to any value the orchestrator might prefix-extend (`"restored_from_backup:..."` is possible per future changes).

Also worth: add a unit test specifically for the prefix-failure case using the actual error string from `FINDING_reset-barrier-stuck-on-failed-finalize.md` ("Dispatch paused on soft-hold"). That regression-pins the lesson.

### D4 — `"user_stopped"` divergence creates inconsistent helper output

Per EVIDENCE_s1-vs-everyone-sync-table §2: `orchestrator.py:2735` writes `stage_results[stage.value] = "user_stopped"` **without firing `Event.STAGE_FAILED`**.

So the SM state at that moment is still whatever it was — possibly RUNNING if the user click was the only sign of intent. T1's helper checks `stage_results` first, finds `"user_stopped"`, returns `'paused'` for that row. But the group state machine might still be in RUNNING with another stage being current. The other stages would render whatever they should — but this one stage renders `'paused'` mid-run, which is incoherent.

**Fix in v2:** Either (a) bring orchestrator.py:2735 into line — fire `Event.CANCEL` properly instead of dual-writing stage_results, OR (b) the helper treats `"user_stopped"` as "ignore, fall through" since it's an inconsistent signal. (b) is the smaller change; (a) is the canonicality fix. Recommend (a) as part of this proposal's broader "S1 actually owns what its docstring claims" cleanup.

---

## 2. The important defects

### D5 — OQ1/OQ5 dependency overstated

The proposal §0 says T1 cannot execute until OQ1 and OQ5 are answered. Neither is strictly true:

- **OQ1 (skipped vocabulary):** the helper can simply omit the `"skipped"` branch if Option B is chosen. T1 ships, the cosmetic skip-reason is lost (acceptable trade-off; documented in EVIDENCE §2a verdict). Decision can defer until a later vocabulary-tightening pass.
- **OQ5 (per-field source labels):** the helper reads `groupState.stage_results[X]` — the existing payload field. No need for source labels to ship T1. OQ5 is an improvement, not a prerequisite.

**Fix in v2:** Reword §0 — OQ1+OQ5 are *helpful decisions to make before authoring T1's tests*, not *blockers*. Soften "must answer first" to "should ratify but T1 ships with Option B fallback if not."

### D6 — Revised tally changes proposal headline

After D1 + D2:

| Verdict (revised) | Count | Findings |
|---|---:|---|
| **Cleanly Fixed by T1 alone** | 4 | §2a, §2f (UI), §2p (UI), §2r |
| **Partially Fixed; needs T2.a bundled** | 2 | §2l Thread A, §2n |
| **Persists** | 6 | §2b, §2j, §2k, §2l Thread B, §2o, §2q |
| **N/A** | 7 | §2c, §2d, §2e, §2g, §2h, §2i, §2m |
| **Total** | 19 | |

So T1 alone is a clean win on 4 findings, a partial-but-not-bundled-yet win on 2 more, and silent on the rest. The proposal's §1 "T1 closes 6 findings with one localized intervention" is *technically* correct but misleading without the T2.a caveat.

**Fix in v2:** Update headline to "T1 cleanly closes 4 of 18 findings + partially helps 2 more if bundled with T2.a." Rewrite §1 architecture paragraph to reflect this — T1 + T2.a should be treated as a single bundle for the §2l-A and §2n closure.

### D7, D8 — REFERENCE doc framing issues

Both are small edits.

- **D7:** §5.1 "Click Run on COMPLETED group" cell currently reads "decision: `RESET` then `START` OR PIPELINE_UP_TO_DATE 409." Today's actual code path: the dashboard's Run button sends `force_from_start=true` (per the §2l finding's footnote), which causes RESET-then-START. PIPELINE_UP_TO_DATE 409 only fires from automated callers (auto-chain). Update REFERENCE §5.1 to reflect this distinction.

- **D8:** §6.4 reads "RUNNING — Subscribers (worker semaphores) resize. NEVER cancel work in flight." This is the *target*, since today's behavior on §2k is exactly the cancellation that the target forbids. Add a "(target)" or "(post-fix)" label to make this explicit.

### D9 — PROPOSAL §9 reading order incomplete

`PROPOSAL_state-machine-re-centering-v1.md` §9 lists 7 docs but omits `PROPOSAL_thread-A-v1` and `PROPOSAL_threads-B-and-C-v2`. T2.b and T2.c both defer to those proposals, so a reader following §9 verbatim would miss them.

**Fix:** Add steps 7'+ for the two cross-thread proposals and their relationship to T2.b/T2.c.

### D10 — OQ7 needs an owner mechanism

REFERENCE §9 OQ7 asks "When this reference doc is wrong, who updates it?" but doesn't answer. Suggest amending OQ7's recommendation: **`CLAUDE.md` lists this reference doc as a must-update-when-changing-pipeline file, same convention Phase 130's docs-binding pattern uses (prep concept "Docs site uses code sources of truth, not marketing copy, for accuracy").**

### D11 — `mcpSetup.ts` precedent comparison is structurally weaker than implied

The proposal cites the prep concept "Canonical registry extracted to break triple-source duplication after audit finding" as a precedent. Re-reading the concept: it was about *static configuration data* (MCP tool list) appearing in three places. The state machine case is about *runtime state* synchronized across nine subsystems via events + manifests + disk flags. Different lifecycle, different consistency requirements, different fix shapes.

The pattern of "team has done canonical-source extraction before" is correct. The specific applicability of the prior fix's shape is overstated.

**Fix:** Replace "exact precedent" framing with "similar pattern, different scope." The Phase 134 ~600-line per-stage-staleness deletion is actually a closer precedent — runtime, same module surface.

---

## 3. Things the proposal got RIGHT (worth keeping)

- **Three-tier architecture (T1/T2/T3).** Clean separation by risk + scope.
- **Each sub-thread independently shippable.** Verified: T2.a, T2.d, T3.a, T3.b, T3.c, T3.d all touch disjoint files.
- **T2.b / T2.c as cross-references to existing proposals.** Avoids the proposal becoming a "redo Thread A" trap.
- **Risk register R1–R10.** Comprehensive even though scrutiny found D1–D11 not in R1–R10 (see §4 below).
- **OQ1–OQ8 as explicit decision gates.** Even if D5 says they're overstated, having them as gates is the right shape.
- **"What we are explicitly NOT claiming" sections.** Helps the scrutiny pass and any future reader bound the proposal's scope.
- **Decision dependency graph §5.** Single-glance summary of what waits for what.
- **Recommended execution order T1 → T2 → T3.** Correct prioritization by risk-adjusted yield.

These are the parts a v2 should preserve.

---

## 4. Risks the proposal's R1–R10 missed (worth adding)

Scrutiny found these were not in the original risk register:

- **R11 (new):** T1's helper assumes a sequential per-group state machine. If Phase 96's "wave-based Finalize dispatch" (per prep concept "Pipeline reorganized into 15 stages across three groups with wave-based Finalize dispatch") allows parallel sub-stages within finalize, the `current_stage_index` model breaks. **Mitigation:** verify wave-based dispatch still serializes within `current_stage_index`; if not, the helper needs a per-wave dimension.
- **R12 (new):** D3 (string-overwrite). The helper relied on a contract S1's docstring claimed (`stage_results[X] ∈ {"completed", "failed", ...}`) but orchestrator.py:2742 violates that contract. Pin the contract in v2 — either fix orchestrator (recommended) or update the helper.
- **R13 (new):** D1's bundling requirement (T1 + T2.a). The proposal's "each sub-thread independently shippable" claim breaks for the §2l-A and §2n closure — they require both. **Mitigation:** mark T1 + T2.a as a "co-deploy" bundle in §5 decision graph.
- **R14 (new):** Self-scrutiny by the author has bias. This pass found 11 defects but more may exist that I'm blind to (especially around UI rendering, where I have less direct evidence). **Mitigation:** dispatch a fresh-eyes scrutiny agent before v2 ships.

---

## 5. Recommendations for v2

If v2 is authored, these are the concrete changes to make:

### 5.1 In `EVIDENCE_findings-replayed-against-pure-s1.md`

- Update §2j: verdict **Persists** with corrected reasoning (T1 falls through to existing progress path, regression unchanged).
- Update §2o: verdict **Persists** with same correction.
- Update §2l Thread A: verdict **Partially fixed** with explicit "needs T2.a (output-presence signal) for honest closure."
- Update §2n: verdict **Partially fixed** with same caveat.
- Update §3 tally + §0 headline to reflect the revised counts.
- Add a new §4.x subsection: "Why the partial-fix findings need T2.a bundled."

### 5.2 In `PROPOSAL_state-machine-re-centering-v1.md` → v2

- Fix D3: helper uses prefix match for `"failed:"` and similar prefixable values. Add a test case using the exact error string from `FINDING_reset-barrier-stuck-on-failed-finalize.md`.
- Fix D4: helper handles `"user_stopped"` either by falling through OR proposal includes fixing orchestrator.py:2735 to fire `Event.CANCEL` properly.
- Update §0: soften OQ1/OQ5 dependencies per D5.
- Update §1: headline reflects revised tally per D6.
- Mark T1+T2.a as a "co-deploy bundle" in §5 decision graph per R13.
- Add R11–R14 to the risk register.
- Update §9 reading order per D9.
- Update §10 cross-references per D11 (replace `mcpSetup.ts` "exact precedent" framing with Phase 134 staleness-cleanup precedent).

### 5.3 In `REFERENCE_canonical-pipeline-behavior.md`

- D7: Edit §5.1 "Click Run on COMPLETED" row to distinguish manual (force_from_start=true) vs automated callers.
- D8: Add `(target)` labels to §6.4 + any other current-vs-target ambiguities.
- D10: Amend OQ7 with `CLAUDE.md` must-update mechanism recommendation.

### 5.4 No changes needed in

- `SYNTHESIS_2026-06-18_did-the-state-machine-drift.md` — the hypothesis still holds under scrutiny.
- `EVIDENCE_s1-vs-everyone-sync-table.md` — the IQ1 evidence stands; scrutiny found one factual claim worth re-verifying (RT1.2 — confirmed by direct read of state_machine.py:429, `Event.RESET` clears stage_results).

---

## 6. Recommended next step — fresh-eyes scrutiny

This pass was author-by-author. The risk (R14) of self-scrutiny bias is real. Before v2 is finalized:

- Dispatch a fresh `Explore` agent with the full corpus and the prompt "find as many defects in `PROPOSAL_state-machine-re-centering-v1.md` as possible, prioritizing things that would fail in production." Aim for at least one round of independent scrutiny per critical defect (D1, D2, D3, R11).
- Compare the fresh agent's findings to D1–D11 here. Overlap validates; divergence is signal.

If the fresh-eyes pass finds < 3 additional defects with severity ≥ Important, treat this self-scrutiny + the fresh pass together as the "scrutinized" mark for v2 authoring. If it finds ≥ 5 additional defects, v2 needs its own scrutiny pass before execution.

---

## 7. Verdict on the synthesis hypothesis itself

The synthesis was: *"S1 has been progressively eclipsed by parallel state stores; re-centering on it would close a meaningful fraction of UI symptoms."*

**Scrutiny verdict:** the hypothesis holds. After the corrections in D1+D2:

- 4 findings clearly fixed by UI re-centering alone — direct evidence of S1 having the right answer when S8 reads the wrong source.
- 2 findings need T1 + T2.a bundled — also evidence of the eclipse pattern, just with an additional upstream signal needed for honest closure.
- 6 Persists findings live in subsystems S5/S6/S7/S9 that S1 doesn't claim to own. These don't disconfirm the hypothesis — they confirm S1's scope is narrower than "all pipeline questions" (per REFERENCE §4 ownership rule).

The hypothesis was directionally correct. The proposal's *headline numbers* were overstated. The *direction of intervention* is right.

---

## 8. Cross-references

- Target of scrutiny: [`PROPOSAL_state-machine-re-centering-v1.md`](PROPOSAL_state-machine-re-centering-v1.md).
- Inputs scrutinized: [`EVIDENCE_findings-replayed-against-pure-s1.md`](EVIDENCE_findings-replayed-against-pure-s1.md), [`EVIDENCE_s1-vs-everyone-sync-table.md`](EVIDENCE_s1-vs-everyone-sync-table.md), [`REFERENCE_canonical-pipeline-behavior.md`](REFERENCE_canonical-pipeline-behavior.md), [`SYNTHESIS_2026-06-18_did-the-state-machine-drift.md`](SYNTHESIS_2026-06-18_did-the-state-machine-drift.md).
- Verified code citations: `src/prep/services/pipeline/orchestrator.py:2735, 2737, 2742` (`stage_results` writers), `src/prep/services/pipeline/state_machine.py:386–430` (Event handlers including `STAGE_FAILED`, `RESET`).
