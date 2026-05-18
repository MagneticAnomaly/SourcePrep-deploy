# Concept — Validate

**File:** `src/prep/core/concept_validate_prompt.py:49-227`
**Symbols:** `VALIDATE_SYSTEM_PROMPT`, `build_validate_user_prompt`
**Invoked by:** Validate swarm worker — once per candidate concept
**Pipeline stage:** synth (Validate pass)
**Output schema:** strict JSON `{verdict, tier, rationale, counter_evidence, falsification}`
**Status:** baseline

## Purpose
Hostile-reviewer critique of one candidate concept. The prompt asks the LLM to play adversarial reviewer — quote evidence, search for counter-evidence, attempt falsification, then issue a verdict.

## Grounding (inputs)
- One candidate concept (title + draft rationale + anchors)
- The anchor files' content
- Audit context if relevant

## Output schema
Strict JSON. Schema is defined inline in the prompt (lines ~190-220). Verdict ∈ {accept, reject, partial}. Tier follows the T1/T2/T3 rubric.

## Known issues / hypotheses
- **Confidence calibration** (memory: `project_llm_confidence_calibration.md`). Prompt should produce rationale BEFORE tier — verify this ordering is present in VALIDATE_SYSTEM_PROMPT. If the model is asked for tier first, social-register clumping kicks in and tiers cluster around the middle.
- **Adversarial framing fatigue**: hostile-reviewer prompts can produce performatively negative critiques regardless of input quality. Worth comparing a "fair-witness" framing variant on the same candidates.
- **Few-shot omission**: T3 Refine has few-shot examples; Validate does not. Hypothesis: adding 2-3 worked examples (accept / reject / partial) would tighten the tier distribution.

## Snapshot 2026-05-17 → updated 2026-05-18 with fresh concept-pipeline run
- Prompt source SHA: `f257c13839aa`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): all 66 concept records (status reflects validate verdicts): [`../snapshots/2026-05-17_baseline/outputs/concept-validate/powermate-reborn-concepts.json`](../snapshots/2026-05-17_baseline/outputs/concept-validate/powermate-reborn-concepts.json)
  - **Validate-stage breakdown** (from pipeline metadata): of 19 synth concepts seen, validate **activated 6, triaged 3, archived 10**. 0 parse failures. Reject-rate ≈ 53% — within the 5-40% sanity band from grounding §9, slightly hot. Possible iteration target.

## Iterations

_(none yet)_

## Open questions
- Is the falsification step too aggressive for T1 concepts that genuinely have no counter-evidence? Causes false `partial` verdicts?
- Does per-concept critique scale — or should we batch candidates and let the LLM compare them?

## Cross-references
- Sibling: [concept-synthesize](./concept-synthesize.md), [concept-t3-refine](./concept-t3-refine.md), [concept-generate](./concept-generate.md)
- Memory: `project_llm_confidence_calibration.md`, `project_concept_promotion_strategy.md`
- Phase 125c — Quality-Checked Concept Swarm (architecture parent)
