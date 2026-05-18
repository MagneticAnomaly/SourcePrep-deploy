# Batch — File roles

**File:** `src/prep/core/batch_prompts.py:59-97`
**Symbols:** `BATCHED_FILE_SYSTEM`, `build_batched_file_prompt`
**Invoked by:** Augmenter worker (`src/prep/core/augmenter.py`)
**Pipeline stage:** fast (catalogue augmentation)
**Output schema:** structured JSON — file role classification (hub / entry / leaf / config / test / etc.) plus summary
**Status:** baseline

## Purpose
Classifies each code file by role and produces a brief summary. Role labels feed the atlas's WORKSPACE MAP and the dashboard's file inventory; summaries feed `prep_search`.

## Grounding (inputs)
- Batch of files with: path, language, leading byte slice (truncated)
- Import / export hints from the structural graph

## Output schema
JSON list. Each: `{path, role, summary, primary_responsibility}`. Schema at `batch_prompts.py:365-546`.

## Known issues / hypotheses
- **Phase 136 Part 1 (File role split for search)**: revealed file-role classification was conflating multiple dimensions. Verify the prompt's role label vocabulary post-fix matches what the search layer expects.
- **Truncation artifacts**: leading byte slice may cut off mid-function. Hypothesis: roles get miscalled when truncation happens to land on imports vs body. Worth inspecting outputs for files known to be truncated.
- **Off-by-language miscalls**: TS files with `.tsx` extension sometimes get classified as React component when they're really utility — possibly because the prompt over-weights extension.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/batch-file/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-file/powermate-reborn.jsonl) — **mixed jsonl**: filter records by `node_id` starting `file:` with `role` set

## Iterations

_(none yet)_

## Open questions
- Is the role taxonomy stable, or does it drift as the codebase grows?
- For files <100 bytes, should we skip the LLM call entirely?

## Cross-references
- Sibling: [batch-symbol](./batch-symbol.md), [batch-doc](./batch-doc.md), [batch-narrative](./batch-narrative.md)
- Phase 136 Part 1 — File role split for search
