# Batch — Epistemic doc

**File:** `src/prep/core/batch_prompts.py:264-308`
**Symbols:** `BATCHED_EPISTEMIC_DOC_SYSTEM`, `build_batched_epistemic_doc_prompt`
**Invoked by:** Epistemic enrichment worker (deep pass, docs)
**Pipeline stage:** deep (epistemic enrichment)
**Output schema:** structured JSON — deep doc analysis (extended summary, domain tags, doc_type, doc_status, decision_chains, staleness, confidence)
**Status:** baseline

## Purpose
Batched epistemic enrichment for docs. Same shape as batch-epi-code but with doc-specific fields like `doc_type`, `doc_status`, and `decision_chains` (linkage from a doc to other docs/files it depends on or supersedes).

## Grounding (inputs)
- Batch of docs with full content
- Trace-graph position
- Optional: prior epistemic enrichment on related docs

## Output schema
JSON list including doc-only fields (`doc_type`, `doc_status`, `decision_chains`) alongside the shared epistemic fields.

## Known issues / hypotheses
- **Doc-status overlap with batch-doc**: batch-doc also produces `doc_status`. Two prompts emitting the same field → drift risk. Hypothesis: pick one as source of truth; have the other read it via grounding.
- **Decision chain fabrication**: `decision_chains` ask the LLM to identify which docs supersede / depend on this one. Hallucination risk is high — verify chains point to real files.
- **Search docs bias** (memory: `project_search_docs_bias.md`). Deep doc enrichment makes docs more findable; magnifies bias if not balanced.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured: TBD

## Iterations

_(none yet)_

## Open questions
- Should `decision_chains` be constrained to docs the model can see in grounding (vs free-form invention)?
- Is batched epistemic-doc better than batch-doc + batch-narrative combined? Or do they each add unique value?

## Cross-references
- Sibling: [batch-doc](./batch-doc.md), [batch-narrative](./batch-narrative.md), [batch-epi-code](./batch-epi-code.md), [epistemic-doc](./epistemic-doc.md)
- Memory: `project_search_docs_bias.md`
- Phase 22 — Epistemic enrichment (parent architecture)
