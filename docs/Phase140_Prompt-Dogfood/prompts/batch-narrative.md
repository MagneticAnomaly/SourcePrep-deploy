# Batch — Doc narrative

**File:** `src/prep/core/batch_prompts.py:141-176`
**Symbols:** `BATCHED_NARRATIVE_SYSTEM`, `build_batched_narrative_prompt`
**Invoked by:** Augmenter worker (`src/prep/core/augmenter.py`)
**Pipeline stage:** fast (catalogue augmentation)
**Output schema:** structured JSON — short narrative summary (less structured than batch-doc)
**Status:** baseline

## Purpose
Simpler doc summarization for unstructured prose (long-form blog drafts, narrative READMEs). Where batch-doc tries to classify type+status, batch-narrative just summarizes.

## Grounding (inputs)
- Batch of docs with: path, leading content slice

## Output schema
JSON list. Each: `{path, summary}`. Lighter schema than batch-doc.

## Known issues / hypotheses
- **Overlap with batch-doc**: when do we call narrative vs doc? If both run on the same files, we have duplicated tokens. Verify the dispatch logic and whether one supersedes the other.
- **Summary length drift**: "summary" with no length cap drifts long. Hypothesis: adding "max 2 sentences" to the prompt tightens outputs without losing content.
- **Search docs bias** (memory: `project_search_docs_bias.md`). Narrative summaries become search-indexable; doc-heavy bias amplified if these summaries get prominent ranking.

## Snapshot 2026-05-17
- Prompt source SHA: `3ec1255d5b0f`
- Outputs captured:
  - Slot A: TBD
  - Slot B (PowerMateReborn): [`../snapshots/2026-05-17_baseline/outputs/batch-narrative/powermate-reborn.jsonl`](../snapshots/2026-05-17_baseline/outputs/batch-narrative/powermate-reborn.jsonl) — **mixed jsonl**: filter records with narrative-only summaries (no `doc_type`/`doc_status` structure)

## Iterations

_(none yet)_

## Open questions
- Is the narrative-vs-doc dispatch deterministic, or do some files get both?
- Should narrative summaries cite section anchors (h2 headers) for deep-linking?

## Cross-references
- Sibling: [batch-doc](./batch-doc.md), [batch-epi-doc](./batch-epi-doc.md)
- Memory: `project_search_docs_bias.md`
