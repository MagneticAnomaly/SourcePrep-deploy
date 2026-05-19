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

### 2026-05-19: B3 — same guidance-gap pattern as batch-epi-code; decision_chains fabrication risk

**Type:** analysis-only (no prompt edit, no separately-captured batched output)

**Read materials:**
- `BATCHED_EPISTEMIC_DOC_SYSTEM` + `build_batched_epistemic_doc_prompt` (`batch_prompts.py:264-308`).
- Sibling single-file `EPISTEMIC_DOC_PROMPT` (`epistemic_enrichment.py:89-126`).
- Doc-side evidence in `outputs/epistemic-code/powermate-reborn.jsonl` (mixed-extension file): the README.md record shows the **single-file path's** decision_chains output shape — structured `{decision, rationale, tradeoffs}` objects, not the schema's flat-string list.

**Finding #1 — same field-level guidance gap as batch-epi-code.** See [`batch-epi-code.md`](./batch-epi-code.md) Iteration #1 for the full side-by-side. Doc-specific additions:

| Field | Single-file (`EPISTEMIC_DOC_PROMPT`) | Batched (`build_batched_epistemic_doc_prompt`) |
|---|---|---|
| `doc_type` | full taxonomy listed, "research\|design_spec\|plan\|guide\|reference\|changelog\|readme\|todo\|status\|analysis\|overview" | same taxonomy in pipe-syntax |
| `doc_status` | "active\|completed\|shelved\|superseded\|draft\|stale" | same |
| `decision_chains` | "key decisions or conclusions documented here" (list of strings) | `"decision_chains": []` — placeholder, no description |
| `tech_debt` | "list ONLY explicit issues found in the text. Do not hallucinate or guess." | `"tech_debt": []` — no anti-hallucination clause |
| `cross_references` | (implicit — no per-field description, inherits "files this doc references") | `"cross_references": []` — no description |

**Finding #2 — `decision_chains` is the highest hallucination-risk field in this prompt.** Per page hypothesis ("Decision chain fabrication risk is high"), the field asks the model to identify supersession/dependency chains across docs. With only the doc's content + neighbor context as grounding, the model has weak signal for "X supersedes Y" relationships — it's most of the way to inventing them.

Evidence from the single-file path's README.md output:
- `decision_chains`: 5 items, each `{decision, rationale, tradeoffs}` — content is anchored in README claims, not fabricated cross-doc supersession.
- The structured form *helps* — it forces the model to pair each decision with a rationale, which acts as a self-check (can I justify this decision from the doc?). Bare-string `"decision_chains": ["Decision A"]` would be much easier to hallucinate.

Implication for the batched prompt: it inherits the bare-string schema with NO description, NO "anchored in this doc" instruction, AND no structured-pair self-check. Triple risk.

**Finding #3 — `doc_status` overlap with batch-doc.** The page's existing hypothesis ("Doc-status overlap with batch-doc: two prompts emitting the same field → drift risk") is real. Both `batch-doc` (Pass 1) and `batch-epi-doc` (Pass 2) emit `doc_status`. The Pass 2 input includes `pass1_doc_status: "{...}"` — so the Pass 2 model has access to Pass 1's verdict. But the schema asks Pass 2 to emit its own `doc_status` independently, with no instruction like "preserve `pass1_doc_status` unless you have specific evidence it changed." Without that instruction, two paths:
- Pass 2 echoes Pass 1's doc_status → field is redundant.
- Pass 2 contradicts Pass 1's doc_status → drift, downstream confusion about source of truth.

A small clarifying clause would resolve: "Preserve `pass1_doc_status` unless the content excerpt contradicts it. If you change it, explain the change in `extended_summary`."

**Finding #4 — `cross_references` field misuse pattern is likely worse for docs.** In `epistemic-code` snapshot, README.md emitted structured cross-references with `relationship: "documented_by" | "configured_by" | "built_by"` — a useful enrichment. But the schema spec for docs (`epistemic_enrichment.py:117`) is `"cross_references": ["src/path/to/code.py"]` — flat list of strings. The structured form is again the model recovering quality from a too-thin schema.

For batched docs, the same drift will happen, but without the inline description the single-file has. May see entirely free-form cross_references (mixed strings + objects depending on the model's mood).

**Verdict:** `analysis (no edit shipped this iteration).` Same cross-cutting issue as batch-epi-code — defer to a single batched-vs-single-guidance-gap finding.

**Recommended next iteration:**

1. **Capture batched-epi-doc output** in a deliberate side-by-side rerun.
2. **Port single-file `EPISTEMIC_DOC_PROMPT` field guidance into `build_batched_epistemic_doc_prompt`** — specifically the `tech_debt` anti-hallucination clause and a new `decision_chains` description anchored to the doc body.
3. **Add a Pass-1/Pass-2 reconciliation clause** for `doc_status` — preserve pass1 verdict unless content contradicts.
4. **Match `decision_chains` schema to the emergent structured shape** observed in the single-file output (`{decision, rationale, tradeoffs}`), in both prompts.

**Grounding citations:**
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §5 (schema overhead — schema too thin forces the model to extend it, but inconsistently across calls).
- [`../03_PromptEngineeringGrounding.md`](../03_PromptEngineeringGrounding.md) §9 (Caulfield over-abduction — `decision_chains` is the canonical over-abduction setup: ask for chains, get invented chains).
- Memory: `project_search_docs_bias.md` — deeper doc enrichment amplifies the search bias unless the new structured fields are balanced against `audit-architecture` and other doc-aware enrichments.

**Cross-references:** [`batch-epi-code.md`](./batch-epi-code.md) (sibling, same guidance gap from the code side), [`epistemic-doc.md`](./epistemic-doc.md) (single-file doc variant — the prompt this batched version was supposed to mirror), [`batch-doc.md`](./batch-doc.md) (Pass-1 doc role classifier — source of `doc_status` overlap).

### 2026-05-19: B3-followup — shipped guidance port + structured schema + doc_status reconciliation

**Type:** prompt edit + schema edit (single iteration; ships the recommendations from Iteration #1 + cross-cutting finding)

**Commit:** `3c22cb09 fix(prompts): Phase 140 B-side iterations — batched prompts (edges + epistemic)`

**Edits:**
- `BATCHED_EPISTEMIC_DOC_SYSTEM`: restored the "grounded in the actual document content" anchoring clause.
- `build_batched_epistemic_doc_prompt`: ported field-level guidance + structured shapes for decision_chains / cross_references / tech_debt. Added FIELD DISCIPLINE block with doc_status reconciliation rule and decision_chains anti-hallucination guidance.
- `epistemic_doc` JSON schema: cross_references / tech_debt / decision_chains all arrays of structured objects — enforced at structured-output decode time.

**Confidence in shipping without rerun:** 90% same as batch-epi-code sibling. The decision_chains-as-`{decision, rationale, tradeoffs}` shape is validated by README.md sequential-path output (Iteration #1 quoted evidence). doc_status reconciliation is a 3-line clarification with clear improvement.

**Verdict:** **partial** — shipped to `main`; awaiting PowerMate BYOK-profile rerun. Will re-verdict as `kept` if rerun shows:
- BYOK doc output matches local-sequential output shape (per [`epistemic-doc.md`](./epistemic-doc.md) Iteration #2)
- doc_status field changes between Pass 1 and Pass 2 are accompanied by extended_summary justification
- decision_chains entries are structured objects, not bare strings

**Follow-ups:**
1. Same as `batch-epi-code` Iteration #2: trigger BYOK PowerMate rerun, capture batched-doc output, diff vs sequential baseline.
2. Cross-check doc_status reconciliation: filter records to `architecture_layer: "documentation"` in `outputs/epistemic-code/powermate-reborn.jsonl`, compare doc_status to `outputs/batch-doc/powermate-reborn.json` (Pass 1) to measure reconciliation compliance.

## Open questions
- Should `decision_chains` be constrained to docs the model can see in grounding (vs free-form invention)?
- Is batched epistemic-doc better than batch-doc + batch-narrative combined? Or do they each add unique value?

## Cross-references
- Sibling: [batch-doc](./batch-doc.md), [batch-narrative](./batch-narrative.md), [batch-epi-code](./batch-epi-code.md), [epistemic-doc](./epistemic-doc.md)
- Memory: `project_search_docs_bias.md`
- Phase 22 — Epistemic enrichment (parent architecture)
