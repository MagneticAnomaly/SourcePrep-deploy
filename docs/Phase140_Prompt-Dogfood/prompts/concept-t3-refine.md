# Concept — T3 Refine

**File:** `src/prep/core/concept_t3_refine.py:119-260`
**Symbols:** `T3_SYSTEM_PROMPT`, `_FEW_SHOT_EXAMPLES`, `make_t3_system_prompt`, `make_t3_user_prompt`
**Invoked by:** Phase 125 T3 refine stage — per-cluster batched call
**Pipeline stage:** synth (T3 refine pass)
**Output schema:** JSON per concept with tier (T1/T2/T3), critique-first ordering (counter-evidence → coincidence → falsification → verdict)
**Status:** baseline

## Purpose
Re-evaluates concepts against the strict T1/T2/T3 tier rubric, applying adversarial critique-first ordering. The pass that pushes weak T2s down to T3 or filters them out entirely.

## Grounding (inputs)
- A cluster of related candidate concepts (anchor-overlap grouped)
- Their anchor files' content
- Three few-shot examples (lines 184-248): graded T1, T2-boundary, T3 with explicit counter-evidence, coincidence, falsification fields

## Output schema
Per-concept JSON. Required fields: `counter_evidence`, `coincidence_check`, `falsification_attempt`, `verdict`, `tier`. Order matters — critique BEFORE verdict.

## Known issues / hypotheses
- **Few-shot quality is load-bearing**. The three examples define the rubric in practice; their failure modes will be copied. Worth auditing each example for clarity and whether they cover the actual edge cases the model sees in practice.
- **Confidence calibration** (memory: `project_llm_confidence_calibration.md`). T3 Refine has the rationale-before-score discipline. Hypothesis: T3 outputs should show tighter tier distribution than Validate outputs. Verify with snapshot comparison.
- **Promotion strategy** (memory: `project_concept_promotion_strategy.md`). T3 Refine is the de facto filter — if it under-rejects, the manual-review queue explodes. Inspect snapshot for `verdict: T3` vs `verdict: reject` distribution.

## Snapshot 2026-05-17 → updated 2026-05-18 with fresh concept-pipeline run
- Prompt source SHA: `45f6da3f0f1a`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): all 66 concept records (tier distribution visible in `status` field): [`../snapshots/2026-05-17_baseline/outputs/concept-t3-refine/powermate-reborn-concepts.json`](../snapshots/2026-05-17_baseline/outputs/concept-t3-refine/powermate-reborn-concepts.json)
  - **T3 refine artifacts not separately captured** — refine results are folded into the final `status` field on each concept. Pipeline metadata shows `gate_activated: 0, gate_triaged: 0, gate_archived: 0` for the gate stage (was T3-refine in earlier phases? worth verifying which stage this maps to in current Phase 125c).

## Iterations

### 2026-05-19: B1 — t3-refine prompt audit + wiring check

**Type:** analysis-only (no prompt edit)

**Read materials:**
- `T3_SYSTEM_PROMPT` (`concept_t3_refine.py:119-182`) — tier definitions as passing tests, adversarial-critique-first instruction.
- `_FEW_SHOT_EXAMPLES` (`concept_t3_refine.py:184-248`) — 3 graded examples T1 → T2-boundary → T3, with full counter-evidence / coincidence / falsification fields.
- `make_t3_system_prompt` + `make_t3_user_prompt` (`concept_t3_refine.py:251-260+`) — assembly.
- Wiring check: `grep -rn 'concept_t3_refine\|make_t3_' src/prep/ --include='*.py'` returns ZERO external callers (only intra-file references inside `concept_t3_refine.py` itself).
- Tests exist: `tests/test_concept_t3_refine.py`.

**Strong points of the current prompt** (no iteration needed):
- **Three few-shot examples T1 → T2-boundary → T3** with verbatim JSON outputs including counter-evidence, coincidence, falsification, tier_pairwise BEFORE tier — exactly the calibration shape recommended by grounding §7.
- **Tier definitions as passing tests** ("a developer who violated this pattern would either (a) get a test failure, OR (b) be flagged by a linter, OR (c) be pointed at a written decision document") — operationalizes the tiers in a way that resists tier inflation.
- **Adversarial critique first** is enforced via field order: counter_evidence → coincidence → falsification → tier_pairwise → tier → tier_justification → consolidation_action. Tier is index-5 of 8 fields.
- **`consolidation_action` field** (keep/split/merge/drop) is a thoughtful addition — gives T3 Refine the power to consolidate the concept set, not just re-tier.
- **`tier_justification` field** asks the LLM to cite the specific passing-test that was satisfied. Forces accountability.

**Finding — the well-engineered T3 Refine prompt is NOT WIRED into the current pipeline.**

Evidence:
- `grep -rn 'concept_t3_refine\|make_t3_\|T3_SYSTEM_PROMPT' src/prep/ --include='*.py'` returns matches only inside `concept_t3_refine.py` itself.
- `grep -rn 'concept_t3_refine\|make_t3_' tests/ --include='*.py'` returns only `tests/test_concept_t3_refine.py` (tests the module in isolation, not via pipeline).
- The pipeline's concepts-stage metadata shows `gate_activated: 0, gate_triaged: 0, gate_archived: 0` for the run on PowerMate. This `gate_*` stage looks like it was intended to consume T3 Refine output but has 0 in every bucket — either nothing is producing input to it, or the gate isn't running.
- The current pipeline is **Generate (swarm) → Validate (per-candidate) → Synthesize** with no T3 Refine pass between or after.

**Two reads of why:**
- **(a) Subsumed**: Phase 125c may have moved T3 Refine's responsibilities into Validate (both use the same T1/T2/T3 rubric; Validate has a 4-field adversarial-critique-first output too). T3 Refine became redundant and was left in the tree as dead code.
- **(b) Orphaned**: T3 Refine was designed as a separate gate stage, the wiring was partially built (the `gate_*` stats exist), but the integration was never finished. The module survives because its tests pass in isolation.

I lean **(b) orphaned** because:
- The `gate_*` stats existing in pipeline metadata implies there's plumbing for it.
- T3 Refine has features Validate lacks: `consolidation_action` (keep/split/merge/drop), `coincidence` (separate from counter_evidence), `tier_justification`.
- Tests for `concept_t3_refine.py` are passing — someone is keeping it alive.

**Verdict:** `analysis (no edit)`. The prompt copy itself is high-quality. The fix is structural — either (a) deprecate and remove if Validate subsumes its role, or (b) finish the wiring to make it the `gate` stage between Validate and Synthesize. Either way, this is outside Phase 140's "prompt copy" scope.

**Recommended next action (out of Phase 140):**
1. Trace `gate_*` stats lineage in the pipeline orchestrator (`src/prep/services/pipeline/`) to determine whether T3 Refine is meant to populate them.
2. If yes — finish the wiring; T3 Refine's `consolidation_action` would also help with the Phase 125 concept-promotion deduplication problem (memory: `project_concept_promotion_strategy.md`).
3. If no — deprecate `concept_t3_refine.py` to dead-code archive; Validate already does the tier-grading work.

**Cross-references:** [`../findings/concept-t3-refine-unwired.md`](../findings/concept-t3-refine-unwired.md) (cross-cutting finding — module exists but doesn't run).

## Open questions
- Are 3 few-shot examples enough, or does the model need a 4th showing a "concept that survives all critiques and earns T1" case?
- Does the batched (per-cluster) call cause cross-contamination — i.e., does one concept's verdict bias the next?

## Cross-references
- Sibling: [concept-synthesize](./concept-synthesize.md), [concept-validate](./concept-validate.md), [concept-generate](./concept-generate.md)
- Memory: `project_llm_confidence_calibration.md`, `project_concept_promotion_strategy.md`
- Phase 125c — Quality-Checked Concept Swarm (architecture parent)
