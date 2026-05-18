# Batch — Doc type/status

**File:** `src/prep/core/batch_prompts.py:102-136`
**Symbols:** `BATCHED_DOC_SYSTEM`, `build_batched_doc_prompt`
**Invoked by:** Augmenter worker (`src/prep/core/augmenter.py`)
**Pipeline stage:** fast (catalogue augmentation)
**Output schema:** structured JSON — doc type (spec / plan / status / readme / architecture / etc.) + status (active / archived / stale / superseded)
**Status:** baseline

## Purpose
Classifies markdown/documentation files by *type* and *status*. Type drives the search layer's doc filters; status powers the staleness UI in the dashboard.

## Grounding (inputs)
- Batch of docs with: path, leading content slice
- File modification time may inform staleness

## Output schema
JSON list. Each: `{path, doc_type, doc_status, summary}`. Schema at `batch_prompts.py:365-546`.

## Known issues / hypotheses
- **Search docs bias** (memory: `project_search_docs_bias.md`). Corpus is 46% MD; `prep_search` keys on roadmap/planning docs over UI code; no doc-vs-code prior in `index.py` ranking. This prompt is responsible for the `doc_type` classification that *should* let ranking down-weight planning docs — verify the type taxonomy distinguishes "planning artifact" from "user-facing doc" clearly.
- **Status drift**: "archived" docs that don't have an `Archive:` header may get misclassified. Hypothesis: prompt is over-reliant on explicit status hints; could benefit from staleness heuristics in grounding (mtime relative to repo HEAD).
- **Stub README problem**: many subdir READMEs are 1-2 lines — `doc_type` and `summary` for them is mostly noise. Worth filtering upstream.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/batch-doc/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-doc/powermate-reborn.jsonl) — **mixed jsonl**: filter records where `doc_type` and `doc_status` are present

## Iterations

_(none yet)_

## Open questions
- Is the doc-type vocabulary covering what search actually needs (it should align with the classifier in Phase 136 Part 4)?
- Should the doc-status decision get an LLM confidence field?

## Cross-references
- Sibling: [batch-narrative](./batch-narrative.md), [batch-epi-doc](./batch-epi-doc.md), [batch-file](./batch-file.md)
- Memory: `project_search_docs_bias.md`
- Phase 136 Part 4 — Search intent classifier
