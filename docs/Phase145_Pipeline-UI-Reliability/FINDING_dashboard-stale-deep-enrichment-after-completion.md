# FINDING — Dashboard renders Deep Enrichment as stale-running after API says `phase=completed`

**Captured:** 2026-06-23 (screenshot ~00:22 PT, live API snapshot ~18:38 PT same day)
**Project:** SourcePrep self-index (`f1636374-abc6-410d-99ee-822120379e79`)
**Status:** new finding; bundle 4 distinct bug classes visible in the same render.

> This finding is the recurrence evidence the PR-A I3 fix was supposed to close, plus three sibling bugs surfaced in the same screenshot. The screenshot was caught manually mid-dogfooding; nothing in the existing playwright_smoke harness fired during the session. That mis-detection is itself a Phase 145 invariant-coverage gap and is called out in §6.

## 1. Evidence

Screenshot reference (Eric's local `Desktop/SCREENSHOTS/Screenshot 2026-06-23 at 12.22.20 AM.png`, not committed to repo) shows the Graph Enrichment panel with:

| Group | Stage | UI render | What the data says |
|---|---|---|---|
| FAST SYNC | Fast Catalogue | "5501% coverage · 98% conf" | `total_nodes=142, augmented_nodes=7812` → 7812/142 × 100 = **5501.4%** |
| DEEP ENRICHMENT | Deep Reasoning | spinner + blue icon + "100%" + full green bar + "2,102 / 2,102 files" | data complete, but state visual still "running" |
| DEEP ENRICHMENT | Group Reasoning | empty circle, no green chip | "156 groups analyzed" — has data |
| DEEP ENRICHMENT | Module Synthesis | empty circle, no green chip | "918 modules · 918 files" — has data |
| DEEP ENRICHMENT | Continuous Deepening | empty circle, no green chip | "100% settled · avg 87%" — has data |
| DEEP ENRICHMENT | Deep Knowledge Embedding | empty circle | "Not run" |
| FINALIZE | (all 5 stages) | green checkmarks | completed |

Live API snapshot taken from the same daemon ~18 hours later confirms the deep-enrichment group **had completed at the moment the screenshot was taken** (the daemon's later state shows `deep_enrichment.finished_at = 1782189479` which is 2026-06-23 04:17:59 UTC = ~21:17 PT 2026-06-22, ~3h before the screenshot):

```json
"deep_enrichment": {
  "phase": "completed",
  "current_stage": null,
  "current_stage_index": 5,
  "total_stages": 5,
  "stage_results": {
    "enrichment": "completed",
    "group_reasoning": "completed",
    "clustering": "completed",
    "deepening": "completed",
    "deep_knowledge": "completed"
  },
  "is_active": false,
  "is_paused": false
}
```

So the API authoritatively says **every deep_enrichment stage completed**, yet the UI rendered all 5 as either spinning or "not done" (no green chip).

## 2. Bug classes

### 2a — `Deep Reasoning 100% but still spinning + blue icon`

**Pattern:** stage row shows complete data + 100% progress + full green bar, but the icon container is the running-blue and a spinner is overlaid.

**Maps to:** §2r (intra-group inconsistency) — same class the PR-A I3 fix targeted. Either a regression introduced by PR-A/PR-B or a code path that `i3SafeStageState` does not cover.

**Hypothesis:** `i3SafeStageState` reads its own group's `current_stage` to decide whether to mask a per-row stale "running" state. With `deep_enrichment.current_stage = null` and `phase = completed`, the anchor is gone — but `i3SafeStageState` was designed to mask when current_stage is present, not when phase has moved to `completed`. So the helper sees "no anchor → return row state unchanged", which preserves the pre-completion stale "running" snapshot. Needs verification by reading `packages/ui/src/components/trace/freezeGreen.ts` `shouldApplyFreezeGreen`.

### 2b — `Group Reasoning / Module Synthesis / Continuous Deepening: have data but rendered "not done"`

**Pattern:** 3 stage rows show real analyzed counts (156 groups, 918 modules, 100% settled) but render as empty circle with no green chip.

**Maps to:** §9.1 cross-group stale-leak — already documented as §9.3 #18 still-open. PR-A I3 fix only knows about the row's own group's `current_stage`. With the group `completed`, the per-row "this-run vs prior-run" provenance attribute called out in §9.1 is what's missing.

**Hypothesis:** same code path as 2a. When `current_stage = null` and `phase = completed`, the green-chip logic should EITHER consume the stage_results map (every key with value "completed" gets the green chip) OR consume the per-stage `slot_phase` (each stage carries its own `slot_phase: "idle"` per the live API). Today the chip logic appears to rely on neither.

### 2c — `Deep Knowledge Embedding: "Not run"` despite API saying completed

**Pattern:** stage 10 explicitly renders the text "Not run" with empty circle.

**API truth:** `stage_results.deep_knowledge = "completed"`.

**Hypothesis:** the "Not run" text comes from a fallback when the stage has no `last_run_at` timestamp visible, or when the per-stage `slot_phase` is `idle` AND the renderer doesn't consult the group's `stage_results` map. This is the most user-facing of the four bugs — the literal text "Not run" against a stage that DID run is the most actively-misleading render in the panel.

### 2d — `Fast Catalogue: 5501% coverage` — NEW bug, not previously in Phase 145

**Pattern:** the coverage chip displays `5501%` for a stage that should be in [0, 100].

**API math:**
```
total_nodes = 142
augmented_nodes = 7812
displayed_coverage = augmented_nodes / total_nodes × 100 = 5501.4%
```

The numerator/denominator are inverted (or `total_nodes` is wrongly scoped to a filtered subset while `augmented_nodes` is the cumulative count across all prior runs). The correct coverage should likely be `augmented_nodes / nodes_in_scope` where `nodes_in_scope` is `~7950` (close to `augmented_nodes`).

**Surface area:** the catalogue stage's coverage chip formatter — likely in `packages/ui/src/components/trace/` or the catalogue card component.

This is independent of 2a/2b/2c and is a pure display bug.

## 3. Why the smoke harness did not catch this

The user was running the SourcePrep dogfood pipeline when the screenshot was taken. The playwright_smoke harness was NOT driving the dashboard at that moment. Even if it had been:

- **2a (intra-group stale spinner)** would fire I3 today — but I3 was claimed closed in PR-A's SCORECARD. Either the I3 fix has a coverage hole for the `phase=completed + current_stage=null` shape, OR the I13 invariant should have fired and didn't. Worth a unit test against an API snapshot synthesized from the live capture above.
- **2b (cross-group stale-leak)** is §9.3 #18 — explicitly documented as out-of-coverage. The harness needs a per-row provenance check (this-run vs prior-run), which doesn't exist yet.
- **2c ("Not run" text)** — there is no current invariant that asserts text content against API's stage_results map. Add I14: "if `stage_results[X] == 'completed'`, the row for X must not render the literal text 'Not run'."
- **2d (`5501% coverage`)** — there is no current invariant that asserts coverage chips are within `[0%, 100%]`. Add I15: "any percentage chip in the pipeline panel must be ≤ 100%."

I14 and I15 are cheap to add and would have caught 2c+2d immediately.

## 4. Recommended next steps

1. **Reproduce 2a + 2b deterministically.** Run an Op-1 smoke against SourcePrep when finalize is idle; capture the exact `pipeline/status` JSON and DOM snapshot at the moment deep_enrichment transitions to `completed`. The combination of `phase=completed` + `current_stage=null` is what the harness needs to assert against.

2. **Add I14 + I15 to `tools/phase145_uat/invariants.py`.** Both are stateless predicates over (status, dom) — cheap.

3. **Triage 2a against `i3SafeStageState`.** Likely a one-line fix in `packages/ui/src/components/trace/freezeGreen.ts` to also clear `state == "running"` rows when the group's API phase is in `TERMINAL_STATES` and the row's own `slot_phase` is `idle`.

4. **Triage 2c separately.** "Not run" text suggests a chip-fallback path that should consult `stage_results[stage_id]` before printing the fallback. Likely in the Deep Knowledge Embedding card.

5. **Triage 2d as its own one-PR fix.** Catalogue coverage chip math.

6. **Defer T5 cadence wiring until 2a-2d are either fixed or have firing invariants.** Cadence with current detector blindness will produce false-clean SCORECARDs that mask these bugs.

## 5. Filed in PROPOSAL §9.3

This finding bundles into the §9.3 follow-up index as:

- **§9.3 #28** — bug 2a (Deep Reasoning 100%-but-spinning; possible I3 regression OR coverage hole)
- **§9.3 #29** — bug 2b (cross-group stale-leak; same as §9.3 #18 but with fresh evidence)
- **§9.3 #30** — bug 2c (literal "Not run" text against completed stage; needs new I14)
- **§9.3 #31** — bug 2d (Fast Catalogue coverage chip >100%; needs new I15)

## 6. Open question for next session

The screenshot proves the smoke harness has detector blindness for bugs that are visually obvious to a human reviewer in <2 seconds. Should the next harness work be:

(a) **Add I14+I15** to close the cheapest detector gaps, OR
(b) **Wire up Playwright MCP** so the agent can drive the UI interactively + detect novel bug classes the scripted harness was never going to find, OR
(c) **Both, in parallel** — they're independent.

Recommendation: (c). I14+I15 are 2-hour work in `invariants.py`; Playwright MCP is one-time config + a new skill writeup.
