# Batch — Symbol summaries

**File:** `src/prep/core/batch_prompts.py:22-54`
**Symbols:** `BATCHED_SYMBOL_SYSTEM`, `build_batched_symbol_prompt`
**Invoked by:** Augmenter worker (`src/prep/core/augmenter.py`)
**Pipeline stage:** fast (catalogue augmentation)
**Output schema:** structured JSON, schema at `batch_prompts.py:365-546`
**Status:** baseline

## Purpose
Generates compact per-symbol summaries (functions, classes, methods) for the trace graph. Outputs flow into the symbol overlays the catalogue serves to `prep_search` and `prep_impact`.

## Grounding (inputs)
- Batch of symbols with: name, file, signature, surrounding context
- Token budget per batch is bounded; batching is for throughput

## Output schema
JSON list, one entry per symbol. Schema enforces fields like `summary` (short), `purpose`, `key_args`. Validated server-side via JSON Schema (see `batch_prompts.py:365-546`).

## Known issues / hypotheses
- **Schema-vs-prompt drift**: schema lives at the bottom of `batch_prompts.py` and prompts up top. Easy for the prompt to ask for fields the schema rejects. Worth confirming round-trip on baseline.
- **Symbol context**: how much surrounding code is fed? Too little and summaries become vacuous; too much and tokens balloon. Hypothesis: there's a sweet spot we haven't measured.
- **Generic-function trap**: utility functions (e.g., `def get_id(self): return self.id`) produce summaries that are longer than the function. Worth seeing if the prompt could detect and produce shorter summaries.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/batch-symbol/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-symbol/powermate-reborn.jsonl) — **mixed jsonl**: filter records by `node_id` starting `symbol:`. Generated 2026-04-29 by `gemini-3-flash-preview:cloud`.

## Iterations

_(none yet)_

## Open questions
- Should symbol summaries cite their file location (redundant with grounding) or stay name-only?
- Trivial / one-liner symbols — is there value in summarizing them at all?

## Cross-references
- Sibling: [batch-file](./batch-file.md), [batch-doc](./batch-doc.md), [batch-cluster](./batch-cluster.md)
- Phase 136 Part 1 — File role split for search
