# Finding — concept-t3-refine is well-engineered but unwired

**Discovered:** 2026-05-19 (during B1 group audit of concept family)
**Severity:** structural; affects 1 prompt site directly + Phase 125 concept-promotion strategy indirectly
**Status:** documented, awaiting structural decision

## TL;DR

`src/prep/core/concept_t3_refine.py` defines a well-engineered LLM prompt with three graded few-shot examples (T1 → T2-boundary → T3), adversarial-critique-first ordering, a `tier_pairwise` calibration field, a `consolidation_action` (keep/split/merge/drop) field, and a `tier_justification` field requiring citation of the passing test that was satisfied. It has unit tests in `tests/test_concept_t3_refine.py`.

**Nothing in the production pipeline calls it.** `grep -rn 'concept_t3_refine\|make_t3_' src/prep/ --include='*.py'` returns matches only inside `concept_t3_refine.py` itself.

The 2026-05-18 PowerMate pipeline run shows `gate_activated: 0, gate_triaged: 0, gate_archived: 0` in concepts-stage metadata — there's plumbing for a "gate" stage but nothing producing input to it.

## Why this matters for Phase 140

- The T3 Refine prompt is the only place in the concept family that has graded few-shot examples. If we ever ship the path-A grounding fix from [`concept-pipeline-grounding-gap.md`](./concept-pipeline-grounding-gap.md), having T3 Refine wired as a final tier-gate would help distinguish marginally-stronger T2-boundary candidates from outright T3s.
- The `consolidation_action` field (keep/split/merge/drop) is directly relevant to memory `project_concept_promotion_strategy.md` ("1,590 manual review unacceptable; LLM confidence clusters 0.7-0.95 (useless filter); anchor-overlap clustering is the lever"). T3 Refine's consolidation could be a second lever.
- The module exists but does nothing — that's dead code that accumulates maintenance cost while testing for nobody.

## Two reads of why it's unwired

### (a) Subsumed by Validate

Phase 125c may have moved T3 Refine's responsibilities into Validate (both use the same T1/T2/T3 rubric; Validate has a 4-field adversarial-critique-first output: counter_evidence → falsification → rationale → verdict).

**Implication:** Deprecate `concept_t3_refine.py`. Remove the dead code. Keep the few-shot examples as documentation if there's interest.

### (b) Orphaned mid-integration

T3 Refine was designed as a separate gate stage between Validate and Synthesize. The pipeline orchestrator has `gate_*` stat fields suggesting plumbing was built, but the integration was never finished.

**Implication:** Finish the wiring. Add a "gate" stage that takes Validate's `activated` outputs and runs them through T3 Refine for final tier-grading and consolidation. The `gate_*` stats then become populated.

## Which read is correct

I lean **(b) orphaned** because:
- The `gate_*` pipeline metadata fields exist (vs simply not appearing if the stage was never planned).
- T3 Refine has fields Validate lacks: `consolidation_action`, `coincidence` (separate from counter_evidence), `tier_justification` with explicit "cite which TIER PASSING TEST is satisfied".
- Unit tests are maintained — someone is keeping the module alive.

But (a) is plausible if Phase 125c deliberately consolidated to reduce LLM round-trips. The pipeline metadata field could be a leftover from earlier planning.

**To decide:** trace the `gate_*` field origin in `src/prep/services/pipeline/` and check Phase 125 docs for whether T3 Refine was deliberately deprecated or pending integration.

## Recommendation

**Outside Phase 140 scope.** Phase 140 audits prompt copy; this is pipeline plumbing.

The right next step is a structural ticket to (a) decide subsumed-vs-orphaned, (b) either wire it in or delete the module + the `gate_*` fields together.

In the meantime, Phase 140 marks `concept-t3-refine` as `analysis-only — module unwired, no prompt-copy iteration possible until structural decision made`.

## Cross-references

- [`prompts/concept-t3-refine.md`](../prompts/concept-t3-refine.md) Iteration #1 — full audit + recommendation
- [`findings/concept-pipeline-grounding-gap.md`](./concept-pipeline-grounding-gap.md) — related (Path A grounding fix would make a wired T3 Refine more effective)
- Memory: `project_concept_promotion_strategy.md` (T3 Refine's consolidation_action is a possible lever)
- Phase 125c — Quality-Checked Concept Swarm (parent architecture; may explain the subsumption-vs-orphaning)
