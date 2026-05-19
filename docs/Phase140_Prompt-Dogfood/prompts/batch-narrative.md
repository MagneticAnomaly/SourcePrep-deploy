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

### 2026-05-19: A4 — corrects page stub on schema; cannot separately audit without per-prompt capture

**Type:** analysis-only (no edit shipped; snapshot conflated with batch-doc)

**Read materials:**
- `BATCHED_NARRATIVE_SYSTEM` + `build_batched_narrative_prompt` (`batch_prompts.py:141-176`).
- PowerMate output: shared with batch-doc (same md5 across all 4 batch-* snapshot files).

**Correction to page stub schema (line 17) — page says `{path, summary}` is the schema. Actual schema (line 168-173 of batch_prompts.py) is `{id, file, summary, role: "documentation", confidence, doc_type, doc_status}`** — same shape as batch-doc but with shorter taxonomies:

- batch-narrative doc_type allowed: `overview|changelog|readme|plan|other`
- batch-doc doc_type allowed: `research|design_spec|plan|guide|reference|changelog|readme|todo|status|analysis|overview`

The page stub "Lighter schema than batch-doc" is misleading — narrative's schema has the same set of fields, just with smaller taxonomy options for doc_type. The page should be updated.

**Finding #1 — cannot separately audit batch-narrative output from snapshot.** All 6 doc records in the shared jsonl could be from EITHER prompt. The doc_type values used (`overview`, `readme`, `plan`) all appear in BOTH taxonomies. Without knowing which dispatcher fired for which file, we cannot attribute outputs to a specific prompt.

To separately audit, need either:
- (a) Per-prompt capture (call build_batched_narrative_prompt explicitly on a known doc, write output to a distinct snapshot file).
- (b) Add a `prompt_source: "narrative" | "structured"` field to the output so future captures discriminate.

(b) is a 3-line worker-side change; (a) is a one-time methodology fix. Either is in scope for snapshot methodology, out of scope for prompt-copy iteration.

**Finding #2 — `BATCHED_NARRATIVE_SYSTEM` is the most minimal system prompt in the audit-batched family.** Single sentence: "You are a document summarizer. You produce brief, accurate summaries of documents." Compare to `BATCHED_DOC_SYSTEM`: "You are a documentation analyst. You classify documentation files by their type, status, and relationship to the codebase." More persona-only than instructional; per grounding §6, persona alone is weak signal.

**Finding #3 — narrative content cap is 2000 chars (line 163: `head = (item.get('head', '') or '')[:2000]`).** Hard input cap. Better than `batch-doc`'s longer cap because narrative is for "unstructured prose" where reading the first 2000 chars usually conveys the document's nature. Smart design — small models won't choke on long narratives.

**Finding #4 — `summary` field has no length cap in the schema** (page hypothesis #2 anticipates this). The prompt asks for "1-2 sentence description" inline (line 170), but no programmatic enforcement. Captured summaries from the shared snapshot are reasonable (1-2 sentences) but could drift on different models.

**Verdict:** **analysis (no edit shipped).** Two deferred actions:

1. **Update page stub** to reflect actual schema (7 fields, not 2).
2. **Separately capture batch-narrative output** before further iteration (snapshot methodology fix).

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §6 (persona alone is weak — narrative-system is the most minimal in the family).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (length calibration — prompt-side "1-2 sentence" instruction is weaker than API-side `max_tokens`).

**Cross-references:** [`batch-doc.md`](./batch-doc.md) (sibling, same shared-jsonl issue), [`batch-epi-doc.md`](./batch-epi-doc.md) (deep Pass-2 of doc enrichment).

## Open questions
- Is the narrative-vs-doc dispatch deterministic, or do some files get both?
- Should narrative summaries cite section anchors (h2 headers) for deep-linking?

## Cross-references
- Sibling: [batch-doc](./batch-doc.md), [batch-epi-doc](./batch-epi-doc.md)
- Memory: `project_search_docs_bias.md`
