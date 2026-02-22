# Research Clarity: Embedding vs Compression vs Context Architecture

> **Purpose**: This document untangles three separate concerns that got conflated during Phase 33/34 research. Each operates at a different stage of the CoDRAG pipeline and should be evaluated independently.

---

## The Three Concerns

### 1. Embedding Model Selection (Phase 33)

**Question**: Which Nomic model produces the best vectors for retrieval across ALL content types?

**Pipeline stage**: BUILD TIME — every file (code + docs) is chunked and embedded into vectors.

**Key constraint**: CoDRAG indexes EVERYTHING together. In production, there's one `CodeIndex` per project containing chunks from `.py`, `.tsx`, `.md`, `.toml`, etc. The embedding model must handle all of these well because they're all in the same vector space and all compete during cosine similarity search.

**The right test**: Full-index builds on real repos, then measure retrieval quality with realistic queries. This is the `--full` mode (default) in `eval_real_repos.py`.

**Current candidates**:
| Model | Runtime | Status |
|:------|:--------|:-------|
| `nomic-embed-text-v1.5` | ONNX (CPU, built-in) | Default today |
| `nomic-embed-text-v2-moe` | Ollama (GPU) | Alternative, requires Ollama |

### 2. Compression Strategy (Future phase)

**Question**: How do we serve MORE context in fewer tokens at query time?

**Pipeline stage**: SERVING TIME — after search finds the best chunks, compression reduces their size before sending to the AI model.

**Two compression targets**:
- **Code files** → LOD extractor (already built). Replaces function bodies with signatures, names, or summaries. Works on trace graph data.
- **Language files** → LLMLingua2 (not yet integrated). Compresses natural language by removing redundant tokens.

**Key insight**: Compression is ORTHOGONAL to embedding. The embedding model creates vectors at build time. Compression happens at serving time. You could use v1.5 for embedding and LOD for compression — they don't interact.

**The one interaction**: If we compress content BEFORE embedding (e.g., embed LOD-compressed code instead of raw code), that changes what gets embedded and could affect retrieval quality. But today CoDRAG embeds raw content and compresses only at serving time. Testing pre-embedding compression is a separate experiment.

### 3. Context Architecture (Phase 34)

**Question**: How do we leverage CoDRAG's structural signals (trace graph, file selections, atlas) to provide better context?

**Pipeline stage**: QUERY TIME — how search results are selected, expanded, and assembled.

**Key signals**: included_paths scope boost, trace expansion (imports/calls), atlas routing, knowledge routing, ambient context mode.

**Key insight**: This is about the SEARCH PIPELINE, not the embedding model. Whether you use v1.5 or v2-moe, the context architecture improvements (trace-always-on, scope boost, LOD-stratified assembly) apply equally.

---

## What Got Conflated

### The confusion

During Phase 33 planning, the framing was:
> "CoDRAG has two compression targets: language compression (Nomic embeddings) and code compression (LOD + trace graph)"

This is wrong. **Embedding is not compression.** Embedding creates vectors for retrieval. LOD is compression. They're different pipeline stages:

```
BUILD TIME:     raw file → chunk → EMBED → vector (for retrieval)
                                     ↑ THIS is the Phase 33 question

SERVING TIME:   search results → LOD COMPRESS → assembled context (for AI model)
                                      ↑ THIS is the compression question
```

### The tangential tests

The `--docs-only`, `--strip-code`, and `--trace-only` eval modes tested **index composition** — "what if we only indexed certain content types?" These are interesting but tangential:

| Mode | What it tested | Why it's tangential |
|:-----|:---------------|:--------------------|
| docs-only | "How well do models retrieve docs when only docs are indexed?" | Production indexes everything together. We don't have a docs-only index. |
| strip-code | "Does removing code blocks from docs help/hurt retrieval?" | We don't strip code blocks in production. |
| trace-only | "Can structural metadata alone support retrieval?" | Trace-only is a degenerate case, not the production index. |

These modes gave us useful **insight** (e.g., "v2-moe is better at matching natural language to structural metadata") but they don't directly inform the embedding model decision. The decision must be based on **full-index performance** because that's how production works.

### The dual-model idea

The Phase 33 TODO had: "Should CoDRAG use separate models for code vs language?" This is premature. Before exploring dual-model complexity, we need to:
1. Fully evaluate the single-model options on full indexes
2. Understand whether the full pipeline (with trace expansion, atlas routing, etc.) already mitigates the weaknesses of either model
3. Only pursue dual-model if a single model clearly can't handle the unified index

---

## What's Actually Valid From Our Research

### Phase 33 — Valid results

1. **Full-index v1.5 vs v2-moe** (the core comparison):
   - v1.5 wins on structured single-language repos (test-nextjs: 71% vs 57%)
   - v2-moe wins on diverse multi-language repos (test3-jezebel: 62% vs 56%)
   - v2-moe has a catastrophic failure mode on test2-halley (0% R@1 vs 43%)

2. **v2-moe context fix** — real production bug fix, needed regardless of model choice

3. **Eval framework** — `eval_real_repos.py` with 10 repos and ground-truth queries is reusable

4. **v2-moe score calibration** — raw scores are much lower (avg 0.690 vs 0.962), which may affect score thresholds

### Phase 33 — Tangential but informative

5. **Docs-only outperforms full for doc queries** → This validates that code chunks dilute doc retrieval. But the fix isn't "index less" — it's "rank better" (intent classification, role weights, atlas routing already address this).

6. **v2-moe excels on trace-only** → v2-moe is better at matching NL queries to structural metadata. This matters because the knowledge index contains LLM-generated summaries (pure language) — v2-moe may perform much better there.

### Phase 34 — Valid but separate

7. **Context-first architecture** — scope boost, trace-always-on, ambient context. These are query-time pipeline improvements, not embedding concerns. Proceed independently.

---

## Clean Research Plan

### Step 1: Finish the embedding model decision (Phase 33)

**Goal**: Choose v1.5 or v2-moe (or both with auto-selection) as the production embedding model.

**Remaining tests**:
- [ ] Run full-index eval on ALL 10 repos (we only have full-index v2-moe for 3 TEST repos)
- [ ] Investigate v2-moe's 0% R@1 on test2-halley — is this a calibration issue or a real retrieval failure?
- [ ] Test with the FULL CoDRAG pipeline (atlas routing + knowledge routing + intent classification + all boosts) — our current eval only tests `CodeIndex.search()` in isolation
- [ ] Test score threshold sensitivity — does v2-moe's lower score range cause issues with `min_score=0.15` and adaptive-K?

**Decision criteria**:
- R@1/MRR on full-index across all repos
- Robustness (no catastrophic failures like test2-halley)
- Score calibration compatibility with existing thresholds
- Practical: ONNX (no deps) vs Ollama (GPU, external service)

### Step 2: Compression testing (separate phase)

**Goal**: Measure how LOD compression and potentially LLMLingua2 affect serving quality.

**Depends on**: Step 1 (need a chosen embedding model to test compression against)

**Key questions**:
- Does LOD-compressed context give better AI model responses than raw context?
- Should we embed LOD-compressed content (pre-embedding compression) or raw content?
- Is LLMLingua2 worth integrating for doc content?

### Step 3: Context architecture (Phase 34, already in progress)

**Goal**: Leverage structural signals at query time.

**Independent of** Steps 1 and 2. Can proceed in parallel.
