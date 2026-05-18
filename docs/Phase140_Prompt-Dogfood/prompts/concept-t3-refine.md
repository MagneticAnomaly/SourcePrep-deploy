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

_(none yet)_

## Open questions
- Are 3 few-shot examples enough, or does the model need a 4th showing a "concept that survives all critiques and earns T1" case?
- Does the batched (per-cluster) call cause cross-contamination — i.e., does one concept's verdict bias the next?

## Cross-references
- Sibling: [concept-synthesize](./concept-synthesize.md), [concept-validate](./concept-validate.md), [concept-generate](./concept-generate.md)
- Memory: `project_llm_confidence_calibration.md`, `project_concept_promotion_strategy.md`
- Phase 125c — Quality-Checked Concept Swarm (architecture parent)
