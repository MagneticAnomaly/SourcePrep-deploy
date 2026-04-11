# Phase 93: Semantic Chunking & Contextual Retrieval — Implementation Summary

**Date:** 2026-04-10
**Status:** Implemented
**Scope:** `src/codrag/core/sg_filter.py`, `src/codrag/core/chunking.py`, `src/codrag/core/index.py`, `src/codrag/core/knowledge.py`

---

## What Was Built

Two improvements to CoDRAG's indexing and retrieval quality, inspired by analysis of [garrytan/gbrain](https://github.com/garrytan/gbrain)'s chunking architecture.

### P1: Semantic Boundary Detection for Markdown

**Problem:** When a markdown section exceeded `max_chars` (1800), `_split_long_text()` split at paragraph boundaries. If a single paragraph was too large, it fell through to character-level slicing — breaking mid-sentence and mid-thought.

**Solution:** Savitzky-Golay signal processing on sentence embedding similarities to find natural topic boundaries.

**Algorithm:**
1. Split oversized section into sentences
2. Embed each sentence (batch call to existing embedder)
3. Compute cosine similarity between adjacent sentence embeddings
4. Apply SG filter (window=5, poly=3, deriv=1) to get the 1st derivative
5. Find zero-crossings (negative-to-non-negative = local similarity minima = topic shifts)
6. Filter: only keep boundaries where raw similarity is below 20th percentile
7. Group sentences at boundaries, merge small groups, post-process oversized groups

**Fallback chain:** 4 graceful fallbacks to `_split_long_text()`:
- Fewer than 5 sentences (not enough signal)
- `embed_batch()` raises an exception
- SG filter finds no boundaries
- Empty result after grouping

### P2: Contextual Retrieval

**Problem:** Chunks were embedded without awareness of their role in the broader file. A chunk from the middle of `index.py:build()` didn't carry "this is part of the build pipeline" in its embedding vector.

**Solution:** Two-tier context enrichment, both using data already available — zero additional LLM calls.

**Tier 1 (fast sync, no LLM):** For multi-chunk files, the file's META_SYNOPSIS (already computed) is prepended to each chunk's embedding text via a `File context:` line in `_format_chunk_for_embedding()`. META_SYNOPSIS chunks themselves are excluded to avoid circular self-reference.

**Tier 2 (deep enrichment, uses existing epistemic data):** In `KnowledgeIndex.build()`, a `Context:` prefix is synthesized from existing epistemic metadata — `architecture_layer`, `subsystem`, `design_patterns` — and prepended to the epistemic document before embedding. Only non-empty fields are included. No new LLM calls; the data was already produced by the enrichment pipeline's Stage 6 (ENRICHMENT).

---

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `src/codrag/core/sg_filter.py` | +119 | **NEW** — Savitzky-Golay filter via Vandermonde matrices + least-squares, boundary detection via zero-crossings with percentile filtering, min-distance enforcement |
| `src/codrag/core/chunking.py` | +111/-1 | Added `_split_sentences()`, `_semantic_split()`, optional `embedder` param on `chunk_markdown()` |
| `src/codrag/core/index.py` | +14/-8 | Pass `embedder=self.embedder` to `chunk_markdown()`, thread `file_synopsis` through build loop to `_format_chunk_for_embedding()` |
| `src/codrag/core/knowledge.py` | +19/-5 | Synthesize context prefix from epistemic metadata in document assembly |
| `tests/test_sg_filter.py` | +81 | **NEW** — 9 tests: derivative computation (constant, linear, shape, short-raises) + boundary detection (clear dips, flat, min-distance, short fallback, empty) |
| `tests/test_semantic_chunking.py` | +74 | **NEW** — 6 tests: backward compat (no embedder, small section) + semantic split (oversized, fallback, metadata, post-processing) |
| `tests/test_contextual_retrieval.py` | +136 | **NEW** — 5 tests: Tier 1 (synopsis present, no synopsis, META_SYNOPSIS excluded) + Tier 2 (epistemic context, missing fields) |

**Total: 546 lines added, 14 removed across 7 files.**

---

## Commits

```
7ec6a2c5 fix: add embed_batch fallback and oversized-group test from code review
3237e85a feat(P2): add Tier 2 contextual retrieval — epistemic context prefix
7bc4bc67 feat(P2): add Tier 1 contextual retrieval — synopsis prefix in embeddings
96958308 feat(P1): wire semantic chunking into CodeIndex.build()
58b8950e feat(P1): add semantic boundary detection for oversized markdown sections
68e5acc5 feat(P1): add Savitzky-Golay filter for semantic boundary detection
```

---

## Test Results

- **20/20 Phase 93 tests pass** (sg_filter: 9, semantic_chunking: 6, contextual_retrieval: 5)
- **102/102 regression tests pass** (incremental_rebuild, manifest_ids, adaptive_k, mmr_diversity, knowledge_surrogate, intent_detection, score_calibration, min_score_threshold, path_weights, primer)
- **Zero failures, zero regressions**

---

## Deviations from Spec

| Spec | Actual | Reason |
|------|--------|--------|
| `np.convolve(signal, kernel[::-1], mode="same")` | Reflected padding + trim: `np.pad(signal, half, mode="reflect")` then `convolved[half:-half]` | Standard SG best practice — `mode="same"` causes boundary artifacts that produced incorrect derivatives at signal edges |
| `domain_tags` in `Context:` prefix (P2 Tier 2) | Omitted from `Context:` prefix | Already present in the `Domain:` line below — including it in both places would be redundant |
| Local variable `parts` in semantic split | Renamed to `split_parts` | Avoided shadowing the outer `parts: List[Chunk]` accumulator in `chunk_markdown()` |

All deviations are improvements. No spec requirements were dropped.

---

## Backward Compatibility

Both features are fully backward-compatible and opt-in:

- `chunk_markdown()` without `embedder` param behaves identically to before (default `None` skips semantic splitting)
- `_format_chunk_for_embedding()` without `file_synopsis` param behaves identically to before (default `""` adds nothing)
- `KnowledgeIndex.build()` with epistemic entries missing `subsystem`/`design_patterns` fields produces the same output as before (context prefix is only added when fields are present)
- The Rust chunker (`engine/crates/codrag-chunking/`) is unchanged and operates independently

**Re-indexing is required** to benefit from the changes — same as any embedding-affecting modification.

---

## Known Limitations

1. **Sentence splitting on abbreviations:** The regex `(?<=[.!?])\s+` splits after any period followed by whitespace, including abbreviations like "Dr. Smith" or "e.g. this". Mitigated by the SG filter requiring 5+ sentences for semantic analysis and the percentile-based boundary filtering, but can produce noisy sentence signals in abbreviation-dense text.

2. **FakeEmbedder produces random boundaries:** In tests, `FakeEmbedder` generates deterministic pseudo-random embeddings from text hashes. The "semantic" boundaries it finds are not truly semantic — they're hash-based. Tests verify the mechanical pipeline works (chunks produced, metadata preserved, fallbacks trigger) but cannot verify real semantic quality. Real quality evaluation requires the NativeEmbedder or OllamaEmbedder with actual text.

3. **Pre-existing `domain_tags=None` crash:** In `knowledge.py` line 346, `', '.join(entry.get('domain_tags', []))` will crash if `domain_tags` is explicitly `None` in the JSONL (vs. missing). This is a pre-existing bug not introduced by Phase 93.

---

## What Comes Next (from Research Doc)

The [01_Chunking_Research.md](01_Chunking_Research.md) identified additional opportunities beyond P1/P2:

| Priority | Opportunity | Status |
|----------|-------------|--------|
| **P1** | Semantic boundary detection for markdown | Implemented (this phase) |
| **P2** | Contextual Retrieval | Implemented (this phase) |
| **P3** | Multi-query expansion (LLM rephrasing for broader recall) | Not started |
| **P3** | Cross-file text-similarity dedup | Not started |
| **P4** | Contract-first operations pattern (reduce MCP/CLI/API drift) | Not started |
| **P4** | Late chunking (Jina-style, requires model change) | Not started |

---

## Catalyst: What We Learned from gbrain

This phase was catalyzed by researching [garrytan/gbrain](https://github.com/garrytan/gbrain). Key findings:

- **gbrain's semantic and LLM chunkers are dead code** — only the basic recursive chunker is wired into its import pipeline. The sophisticated techniques exist but are never called in production.
- **Savitzky-Golay semantic boundary detection** works well as a signal processing approach to text segmentation. The from-scratch implementation (Vandermonde + least-squares) is ~60 lines and needs only numpy.
- **Reciprocal Rank Fusion (K=60)** is the gold standard for hybrid search merging. CoDRAG already uses RRF in its FTS5 boost layer.
- **Contextual Retrieval doesn't require per-chunk LLM calls** if you already have rich metadata from an enrichment pipeline. CoDRAG's epistemic data provides equivalent context for free.
- **CoDRAG's existing advantages** (AST-aware chunking, local-first embeddings, 7-layer boosting, intent detection, MMR diversity, trace expansion) remain stronger than gbrain's retrieval stack for code intelligence.
