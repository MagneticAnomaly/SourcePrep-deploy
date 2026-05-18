# Batch — Inferred edges

**File:** `src/prep/core/batch_prompts.py:181-216`
**Symbols:** `BATCHED_INFERRED_EDGES_SYSTEM`, `build_batched_inferred_edges_prompt`
**Invoked by:** Augmenter worker — fills in graph edges that the structural parser missed
**Pipeline stage:** fast (catalogue augmentation) / enrichment
**Output schema:** structured JSON list of inferred edges (source, target, edge type, confidence)
**Status:** baseline

## Purpose
Detects cross-file dependencies that the AST parser couldn't statically resolve (dynamic imports, plugin registries, runtime config wiring). Adds these as inferred edges in the trace graph.

## Grounding (inputs)
- Batch of files with their content
- Structural edges already known (so we don't re-emit them)
- Symbol catalog snippet

## Output schema
JSON list. Each: `{source, target, edge_type, confidence, evidence_quote}`. Schema at `batch_prompts.py:365-546`.

## Known issues / hypotheses
- **False positives are expensive**: inferred edges feed `prep_impact`, so a wrong edge means a wrong blast-radius answer. Hypothesis: confidence threshold for accepting an inferred edge may be too permissive. Inspect baseline for low-confidence edges that look invented.
- **Evidence quote drift**: the prompt asks for an `evidence_quote` — verify that real outputs include quotes that *actually exist* in the input. Hallucinated quotes are a known LLM failure mode.
- **Plugin patterns**: dynamic import idioms are language-specific (Python `importlib`, JS `require()` with variable args). Hypothesis: the prompt's coverage is uneven across languages.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/batch-edges/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-edges/powermate-reborn.jsonl) — 36 inferred edges

## Iterations

_(none yet)_

## Open questions
- Should we require `evidence_quote` to be substring-matched against input before accepting the edge?
- What's the false-positive rate when run against repos with no dynamic imports (should be near zero)?

## Cross-references
- Sibling: [batch-symbol](./batch-symbol.md), [batch-file](./batch-file.md)
- Phase 136 Part 2 — prep_impact bimodal node (related impact-graph concerns)
