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

### 2026-05-19: A4 — doc_status 100% "active" clumping; cannot distinguish from batch-narrative output

**Type:** analysis-only (no edit shipped — sample size too small + snapshot conflated with batch-narrative)

**Read materials:**
- `BATCHED_DOC_SYSTEM` + `build_batched_doc_prompt` (`batch_prompts.py:102-136`).
- PowerMate output: filtered from shared `outputs/batch-doc/powermate-reborn.jsonl` — 6 records with `doc_type` AND `doc_status` set.

**Snapshot methodology note:** Same as `batch-file` Iteration #1 — all 4 batch-* snapshot files are byte-identical. The shared jsonl contains 6 records with doc_type/doc_status fields; cannot distinguish whether each came from `batch-doc` (structured) or `batch-narrative` (simpler) just from output shape. The `doc_type` values emitted (`overview` ×4, `readme` ×1, `plan` ×1) all appear in BOTH prompts' allowed taxonomies. Need a per-prompt capture (or a routing-signal added to output) to separately audit.

**Finding #1 — `doc_status` is 100% "active" across all 6 records.** Files classified:

| File | doc_type | doc_status |
|---|---|---|
| README.md | readme | active |
| docs/README.md | overview | active |
| docs/research/RESEARCH_AUDIO.md | overview | active |
| docs/research/RESEARCH_BRIGHTNESS.md | overview | active |
| scripts/CODE_SIGNING.md | plan | active |
| scripts/SPARKLE_SETUP.md | overview | active |

100% "active" with 0 variation. Three reads:
- **(a) Genuinely all active.** Plausible for a small project — none of these docs are explicitly deprecated. The model is right.
- **(b) Model bias toward "active".** "Active" is the safe default; without explicit deprecation signals, it's the model's natural pick. The taxonomy includes `completed`, `shelved`, `superseded`, `draft`, `stale` — none used. PowerMate's docs.research/ files are clearly *research* documents — could they be classified `completed` (the research is done) rather than `active`?
- **(c) Insufficient grounding for `stale` calls.** Prompt feeds content slice but not file mtime relative to repo HEAD. "Stale" can't be classified without temporal grounding. Page hypothesis #2 ("Status drift: 'archived' docs that don't have an `Archive:` header may get misclassified") anticipates this.

I lean (b)+(c): the model defaults safely to "active" because (i) it doesn't have temporal signal, (ii) the taxonomy doesn't give clear discriminators between active/completed/draft when no explicit header is present.

**Recommendation if iterating:**
- Add temporal grounding: file mtime (relative to repo HEAD), commit-history hints (last-touched age). This is grounding-layer work (out of Phase 140 scope).
- OR loosen the prompt: "When status signal is absent, default to `active`. If the doc reads as a finished research write-up (no TODOs, no 'next steps', no open questions), prefer `completed`. If the doc is explicitly marked draft/WIP/TBD, use `draft`."

**Finding #2 — `doc_type` taxonomy under-utilized.** Prompt allows 11 values: `research, design_spec, plan, guide, reference, changelog, readme, todo, status, analysis, overview`. PowerMate's 6 docs use only 3 values (overview, readme, plan).

`docs/research/RESEARCH_AUDIO.md` and `docs/research/RESEARCH_BRIGHTNESS.md` are classified `overview` despite their filename literally containing "RESEARCH" — and the `research` taxonomy value exists! The model isn't using the most specific taxonomy term.

Worth a one-line nudge: "Use the most specific `doc_type` that fits. If the filename contains 'RESEARCH', 'DESIGN', 'PLAN', etc., prefer the matching specific type over `overview`."

**Finding #3 — `confidence: 1.0` on all 6 records** — same float-clumping as batch-file. Same recommendation: port named-tier rubric.

**Verdict:** **analysis (no edit shipped).** Three deferred actions:

1. **Capture batch-doc and batch-narrative separately** before iterating — sample size of 6 isn't enough for confident calls.
2. **Filename-aware doc_type nudge** — high-value, low-risk edit.
3. **Status grounding via mtime** — out of Phase 140 scope.

**Grounding citations:**
- Memory: `project_search_docs_bias.md` — directly affects this prompt's downstream impact on search.
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §7 (confidence clumping).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §1 (taxonomy use — explicit examples improve specificity).

**Cross-references:** [`batch-narrative.md`](./batch-narrative.md) (cannot separately audit — same data), [`batch-epi-doc.md`](./batch-epi-doc.md) (deep Pass-2 of doc enrichment), [`batch-file.md`](./batch-file.md) (sibling — same shared-jsonl issue).

## Open questions
- Is the doc-type vocabulary covering what search actually needs (it should align with the classifier in Phase 136 Part 4)?
- Should the doc-status decision get an LLM confidence field?

## Cross-references
- Sibling: [batch-narrative](./batch-narrative.md), [batch-epi-doc](./batch-epi-doc.md), [batch-file](./batch-file.md)
- Memory: `project_search_docs_bias.md`
- Phase 136 Part 4 — Search intent classifier
