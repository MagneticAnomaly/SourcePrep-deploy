# Finding — concept pipeline grounding gap

**Discovered:** 2026-05-18 (during Sprint 2 baseline read of PowerMate concept records)
**Severity:** structural; not a prompt-copy bug but affects two prompt sites
**Status:** documented, awaiting decision

## TL;DR

The concept-pipeline's `Validate` stage cannot confirm implementation-specific concepts (claims about `dlopen`, signal handlers, byte ordering, timer queue affinity, etc.) because the **upstream grounding it receives is rationale-shaped, not source-shaped**. Validate sees per-file *summaries* but not the actual file content. As a result:

- Implementation-detail concepts get systematically REJECTED regardless of correctness.
- Architectural / positioning concepts get accepted (because file rationales can speak to those).
- The visible symptom is Validate's reject rate (~53% on PowerMate, slightly hot per grounding §9) — but the cause is upstream.

## Evidence

PowerMate Slot B baseline ([`snapshots/2026-05-17_baseline/outputs/concept-validate/powermate-reborn-concepts.json`](../snapshots/2026-05-17_baseline/outputs/concept-validate/powermate-reborn-concepts.json), captured 2026-05-18 from `prep_concepts.db`):

| Status | Count | Pattern |
|---|---|---|
| `active` (T2-T3) | 6 | Predominantly architectural / positioning claims |
| `triage_pending` | 3 | Implementation-specific, marginal grounding |
| `archived` (REJECT) | 10 | Most have `assertion` field explicitly noting grounding gap |
| `seed` | 47 | Pre-validate (didn't make it through dedup or weren't scored) |

Quoted assertions from archived candidates (from the LLM's own falsification attempt):
- "Without grounding, neither test can be performed."
- "Since grounding is empty, no falsification query can be executed against actual source."
- "the falsification requires inspecting a file that is not in the grounding."
- "Sources/PowerMateBLETransport.swift is not in grounding, so this falsification is unexecutable."

These are not Validate hallucinating — Validate is correctly following its rubric ("If you cannot quote a verbatim grounding span supporting the claim, verdict=REJECT"). The problem is what's IN the grounding.

## Root cause (hypothesis, not yet verified in code)

`build_validate_user_prompt` (`src/prep/core/concept_validate_prompt.py:136-208`) accepts:
- `related_rationale` — module rationale summaries
- `related_doc_excerpts` — planning docs
- `related_audit_findings` — audit results

It does NOT accept a `related_file_content` parameter. The T3b runner that filters these by anchor overlap (referenced in the docstring on line 145-147) doesn't include actual source code — only the upstream rationale and docs.

For a concept like "dlopen/dlsym of private DisplayServices prevents launch failure on systems lacking the framework" with anchors `["Sources/BrightnessController.swift"]`, Validate sees:
- Whatever the per-file rationale summary says about `BrightnessController.swift` (probably "manages display brightness through multiple fallback strategies" or similar — 1-2 sentences)
- Maybe `docs/SPARKLE_SETUP.md` if it's in the doc excerpts

It does NOT see the actual `BrightnessController.swift` source with the `dlopen` calls. So even though the claim is verifiable in <5 min via grep, Validate can't quote a grounding span for it.

## Two paths forward

### Path A — fix the upstream grounding (preferred)

Modify the T3b runner that builds `related_*` parameters to *also* attach a small source slice from each anchor file. Heuristic: if the candidate's content mentions specific symbols/APIs (regex: `\b[a-z_]+\(|`...), pull a ±20-line window around the first match in each anchor file. Pass this as a new `related_file_excerpts` parameter and update `build_validate_user_prompt` to render it.

- **Pro:** Fixes the bug at the source. Validate prompt stays strict. Concept quality goes up across the board.
- **Con:** Outside Phase 140's "prompt copy" scope — this is pipeline plumbing work. Needs a separate phase ticket or sub-phase.
- **Risk:** File slices increase token cost per Validate call. Need to measure.

### Path B — soften Validate's REJECT rule (stopgap)

Add to the REJECT criteria in `VALIDATE_SYSTEM_PROMPT`:

> EXCEPTION: If the concept's claim is implementation-specific (mentions a specific API, symbol, byte order, signal name, framework, etc.) and the grounding doesn't include source for the anchor file, downgrade to **T1** with rationale "grounding insufficient for full falsification but claim is plausible." Do NOT REJECT in this case.

- **Pro:** In scope for Phase 140. Single prompt edit. Recovers the false-negative concepts as T1 (low confidence but not lost).
- **Con:** Band-aid. T1 concepts accumulate without ever being properly tier-graded. Reject rate falls but accept rate balloons with low-confidence noise.

## Recommendation

**Defer Path A to a separate ticket.** Phase 140 is about prompt copy; the T3b runner is pipeline plumbing.

**Don't ship Path B yet.** It will create noise (lots of T1 concepts) that masks the real fix.

**Instead:** open a structural ticket for Path A. Phase 140 captures this finding so the work is named when someone picks it up. In the meantime, the 53% reject rate is *informative* (it shows the gap exists), not actionable.

## What changes downstream when Path A ships

After Path A: re-run PowerMate concept pipeline, re-capture, expect:
- Reject rate drops into the 5-40% band per grounding §9
- Many of the 10 currently-archived concepts move to T1/T2/T3
- Some legitimately stay REJECTed (e.g., the "Documentation as hardware-owner recruitment" one is closer to a product-strategy editorial than a code claim)

That re-capture becomes the new baseline for `concept-validate` and `concept-generate`.

## Cross-references

- [`prompts/concept-validate.md`](../prompts/concept-validate.md) Iteration #1 (full analysis)
- [`prompts/concept-generate.md`](../prompts/concept-generate.md) Iteration (observation)
- Memory: `project_concept_promotion_strategy.md`, `project_llm_confidence_calibration.md`
- Grounding doc: [`03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §7 (calibration), §9 (adversarial)
