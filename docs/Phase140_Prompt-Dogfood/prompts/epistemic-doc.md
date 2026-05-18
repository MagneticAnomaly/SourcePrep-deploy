# Epistemic — Doc (single-file)

**File:** `src/prep/core/epistemic_enrichment.py:89-140`
**Symbols:** `EPISTEMIC_SYSTEM`, `EPISTEMIC_DOC_PROMPT`
**Invoked by:** `epistemic_enrichment.py` worker (doc nodes)
**Pipeline stage:** deep (epistemic enrichment, Phase 22 Pass 2)
**Output schema:** structured JSON — extended summary, domain tags, architecture layer, subsystem, design patterns, cross-refs, tech debt, staleness risk, confidence + doc_type, doc_status, decision_chains
**Status:** baseline

## Purpose
Deep per-doc enrichment for the trace graph. Doc analogue of `epistemic-code` with doc-only fields like `doc_type`, `doc_status`, `decision_chains`.

## Grounding (inputs)
- Full doc content
- The doc's trace-graph neighbors (linked docs, referenced files)
- Prior epistemic enrichment on neighbors

## Output schema
JSON. Shared epistemic fields plus `doc_type`, `doc_status`, `decision_chains`.

## Known issues / hypotheses
- **Three doc-status prompts overlap**: batch-doc, batch-epi-doc, and this prompt all classify `doc_status`. Likely producing inconsistent values. Hypothesis: pick one source of truth and have the others read it.
- **decision_chains hallucination risk**: same concern as batch-epi-doc — chains may invent linkages. Verify chains point to real files / docs in grounding.
- **Search docs bias** (memory: `project_search_docs_bias.md`). Deep doc enrichment makes docs even more findable; if doc-vs-code ranking prior isn't added in `index.py`, this amplifies the bias.

## Snapshot 2026-05-17
- Prompt source SHA: `7c6239a6f300`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/epistemic-doc/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/epistemic-doc/powermate-reborn.jsonl) — **mixed jsonl**: filter for `.md` / doc records

## Iterations

_(none yet)_

## Open questions
- How does this differ from `batch-epi-doc`? Is single-file mode ever invoked, or did batched supersede it?
- Should `decision_chains` accept only verified-in-grounding targets, with hallucinated ones silently dropped?

## Cross-references
- Sibling: [epistemic-code](./epistemic-code.md), [batch-epi-doc](./batch-epi-doc.md), [batch-doc](./batch-doc.md)
- Memory: `project_search_docs_bias.md`, `project_llm_confidence_calibration.md`
- Phase 22 — Epistemic enrichment (parent architecture)
