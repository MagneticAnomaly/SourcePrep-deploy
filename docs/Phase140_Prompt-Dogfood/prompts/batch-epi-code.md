# Batch — Epistemic code

**File:** `src/prep/core/batch_prompts.py:221-259`
**Symbols:** `BATCHED_EPISTEMIC_CODE_SYSTEM`, `build_batched_epistemic_code_prompt`
**Invoked by:** Epistemic enrichment worker (deep pass)
**Pipeline stage:** deep (epistemic enrichment)
**Output schema:** structured JSON — deep code analysis (architecture layer, subsystem, design patterns, cross-refs, tech debt, staleness, confidence)
**Status:** baseline

## Purpose
Batched version of the single-file epistemic code prompt. Used when throughput matters more than per-file context depth — typically the bulk pass over many files.

## Grounding (inputs)
- Batch of code files with full content (or large slice)
- Their position in the trace graph (in/out degree)

## Output schema
JSON list, fields including: `extended_summary`, `domain_tags`, `architecture_layer`, `subsystem`, `design_patterns`, `cross_refs`, `tech_debt`, `staleness_risk`, `confidence`.

## Known issues / hypotheses
- **Overlap with single-file epistemic-code prompt** (`epistemic_enrichment.py:53-87`). Both produce the same fields — when do we use which? If batched is "fast path" and single-file is "deep path," the prompts should diverge in instruction tightness; verify they do.
- **Layer taxonomy**: architecture_layer values (presentation / domain / infra / etc.) are not standardized in any documented vocabulary I've seen. Hypothesis: outputs drift across batches because the model invents categories.
- **Confidence calibration** (memory: `project_llm_confidence_calibration.md`). If the prompt asks for a 0-1 float, expect clumping around 0.7-0.85. Switch to named tiers.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured: TBD

## Iterations

_(none yet)_

## Open questions
- Should we publish a fixed taxonomy of layer/subsystem values?
- When is batched-epi-code better than single-file epistemic-code? Should one supersede the other?

## Cross-references
- Sibling: [batch-epi-doc](./batch-epi-doc.md), [epistemic-code](./epistemic-code.md)
- Memory: `project_llm_confidence_calibration.md`
- Phase 22 — Epistemic enrichment (parent architecture)
