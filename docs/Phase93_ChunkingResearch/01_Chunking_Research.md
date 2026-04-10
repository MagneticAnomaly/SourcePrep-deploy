# Phase 93: Chunking & Retrieval Research

**Date:** 2026-04-10
**Status:** Research
**Catalyst:** Analysis of [garrytan/gbrain](https://github.com/garrytan/gbrain) revealed sophisticated chunking techniques worth evaluating against CoDRAG's current approach.

---

## Executive Summary

GBrain (Garry Tan's personal knowledge brain) implements a 3-tier chunking system with Savitzky-Golay semantic boundary detection, LLM-guided chunking, and RRF-based hybrid search. While GBrain targets personal knowledge (documents, meetings, notes) rather than code, several of its retrieval techniques are directly transferable to CoDRAG's code-focused indexing. This document catalogs what we can learn, what's already better in CoDRAG, and concrete opportunities for improvement.

---

## 1. GBrain's Chunking Architecture

### 1.1 Recursive Chunker (Baseline)

GBrain's fallback chunker uses a **5-level delimiter hierarchy**:

| Level | Delimiters |
|-------|-----------|
| L0 | `\n\n` (paragraphs) |
| L1 | `\n` (lines) |
| L2 | `. `, `! `, `? ` (sentences) |
| L3 | `; `, `: `, `, ` (clauses) |
| L4 | whitespace (words) |

Defaults: **300-word chunks, 50-word overlap**. Splits at the highest-level delimiter producing multiple pieces; oversized pieces recurse to the next level. Pieces are greedily merged up to `target * 1.5` words.

**CoDRAG comparison:** CoDRAG's code chunker uses a simpler sliding window (2000 chars, 200 char overlap). The markdown chunker is heading-aware (splits on H1-H6). Neither has a multi-level delimiter cascade. The gbrain approach is more suitable for prose; CoDRAG's heading-aware approach is more suitable for markdown documentation.

### 1.2 Semantic Chunker (Savitzky-Golay)

The standout technique. Algorithm:

1. Split text into sentences (regex: `(?<=[.!?])\s+`)
2. Embed each sentence independently
3. Compute pairwise cosine similarity between adjacent sentence embeddings
4. Apply **Savitzky-Golay filter** (window=5, polynomial order=3, derivative order=1) to the similarity signal
5. Find **zero-crossings** in the 1st derivative (negative-to-non-negative transitions = local similarity minima = topic boundaries)
6. Filter boundaries: only keep where raw similarity is below **20th percentile**
7. Enforce **minimum distance of 2** between boundaries
8. Oversized groups (> `chunkSize * 1.5` words) are recursively split

The SG filter implementation is from-scratch: builds a Vandermonde matrix for `[-2, -1, 0, 1, 2]`, computes `(J^T J)^{-1} J^T` via Gauss-Jordan elimination, extracts the derivative row. No external dependencies.

**Key insight:** Treats the similarity sequence as a 1D signal and uses established signal processing to find natural breakpoints, rather than relying on arbitrary thresholds or fixed token windows.

**Limitation found:** The semantic and LLM chunkers are **dead code** in gbrain's current pipeline. Only the recursive chunker is actually wired into the import flow. The sophisticated chunkers are exported but never called in production.

### 1.3 LLM-Guided Chunker

1. Pre-split into **128-word candidates** (recursive chunker, zero overlap)
2. Slide a **window of 5 candidates** across the text
3. Ask Claude Haiku: *"Where does the FIRST major topic shift occur?"* (each candidate truncated to 200 chars)
4. If split found: window advances to split point. If none: advance by 1.
5. Max **3 retries** per window on unparseable responses
6. Merge candidates between split points

**Assessment:** Interesting but expensive. Research consensus is that LLM-guided boundary detection offers marginal gains over well-tuned algorithmic approaches. The better use of LLMs in chunking is **contextual enrichment** (Anthropic's Contextual Retrieval approach) rather than boundary detection.

---

## 2. GBrain's Search Architecture

### 2.1 Reciprocal Rank Fusion (RRF)

GBrain uses RRF with **K=60** (the original paper's default, Cormack et al., SIGIR 2009):

```
rrfScore = 1 / (K + rank)    // rank is 0-based
```

Vector search (pgvector HNSW, cosine) and keyword search (PostgreSQL tsvector) results are fused by dedup key (`slug:chunk_text_prefix`). Multiple query variants (from Haiku expansion) each contribute vector results, all merged via RRF.

**CoDRAG comparison:** CoDRAG already uses RRF for its FTS5 boost layer (`rrf_k=60, rrf_weight=12.0`), but applies it as an additive boost to the cosine similarity score rather than as a standalone fusion mechanism. GBrain's approach is purer: RRF as the sole merging function between independent retrieval lists. CoDRAG's approach is more nuanced (7 independent boost sources), but also more complex and harder to tune.

### 2.2 Multi-Query Expansion

GBrain uses Claude Haiku to generate **2 alternative phrasings** for queries with 3+ words. Each variant gets its own vector search, all merged via RRF.

**CoDRAG comparison:** CoDRAG has no query expansion. It extracts structural signals (file paths, symbols, keywords) from queries but doesn't rephrase for broader recall. This is a clear gap.

### 2.3 Four-Layer Deduplication

| Layer | Strategy | Threshold |
|-------|----------|-----------|
| 1. By source | Highest-scoring chunk per page | N/A |
| 2. Text similarity | Jaccard on word sets | > 0.85 drops |
| 3. Type diversity | No page type > 60% of results | 60% cap |
| 4. Page cap | Max 2 chunks per page | 2 |

**Design issue found:** Layer 2 uses Jaccard as "proxy for cosine similarity" but 0.85 Jaccard is far stricter than 0.85 cosine — these metrics are not equivalent at the same threshold.

**CoDRAG comparison:** CoDRAG has file-level dedup (keep highest per source_path) and MMR diversity reranking (lambda=0.7). CoDRAG's MMR approach is more principled for diversity than gbrain's type-ratio cap. However, CoDRAG lacks the explicit text-similarity dedup layer — MMR handles this implicitly but less directly.

---

## 3. What CoDRAG Already Does Better

| Area | CoDRAG Advantage |
|------|-----------------|
| **Code-aware chunking** | AST-aware via tree-sitter (Rust engine). Heading-aware markdown chunking. gbrain has no structural awareness. |
| **Local-first** | ONNX native embeddings (nomic-embed-text-v1.5, 768-dim). No API keys, no cost, no latency. gbrain requires OpenAI API. |
| **Structural search signals** | 7 boost layers including trace in-degree, role weights, segment routing, structural query matching. gbrain has only vector + keyword. |
| **Intent detection** | Automatic query intent classification (debug, refactor, add_feature, understand) adjusts search parameters. gbrain has no intent awareness. |
| **MMR diversity reranking** | Principled diversity via Maximal Marginal Relevance. gbrain uses simpler type-ratio caps. |
| **Adaptive-K gap detection** | Truncates results at score gaps to avoid low-confidence noise. gbrain returns fixed top-N. |
| **Graph-augmented retrieval** | Trace expansion follows import/call edges for structural context. gbrain has no graph model. |
| **File synopsis chunks** | META_SYNOPSIS chunks anchor file identity in embedding space. gbrain has no equivalent. |

---

## 4. Concrete Opportunities from GBrain

### 4.1 Semantic Boundary Detection for Documentation Chunks (HIGH VALUE)

**Current state:** CoDRAG's markdown chunker splits on headings only. For long sections under a single heading, it falls through to the code-style sliding window (2000 chars, 200 overlap). This can split mid-paragraph or mid-thought.

**Opportunity:** Apply Savitzky-Golay semantic boundary detection as a **second pass** for oversized markdown sections. When a heading-bounded section exceeds `max_chars`, instead of a dumb sliding window, embed sentences within the section and find natural topic boundaries.

**Scope:** Markdown chunking only. Code chunks should remain AST-aware (tree-sitter is better for code than any text-based boundary detection).

**Estimated effort:** Medium. Requires per-sentence embedding within the chunking pass, SG filter implementation, and integration into the Python markdown chunker. Could reuse the existing NativeEmbedder.

### 4.2 Multi-Query Expansion (MEDIUM VALUE)

**Current state:** CoDRAG extracts structural signals from queries (paths, symbols, keywords) but doesn't generate alternative phrasings.

**Opportunity:** For semantic search queries (not structural lookups), generate 1-2 alternative phrasings using a lightweight LLM. Merge results via RRF. This could help when the user's phrasing doesn't match the indexed code's vocabulary.

**Trade-off:** Adds latency and LLM dependency to every search. Could be opt-in for broad queries only, skip for structural/locate queries.

**Scope:** `src/codrag/core/index.py` search path. Use existing LLM client infrastructure.

### 4.3 Text-Similarity Dedup Layer (LOW-MEDIUM VALUE)

**Current state:** CoDRAG deduplicates at file level (keep highest per source_path) and uses MMR for diversity. But two chunks from *different* files can be near-duplicates (e.g., copy-pasted boilerplate, similar docstrings).

**Opportunity:** Add a Jaccard (or cosine on stored embeddings) similarity check between retained results. Drop near-duplicates across files, not just within files.

**Trade-off:** MMR already handles this partially. The marginal gain may be small. Worth profiling before investing.

### 4.4 Contract-First Operations Pattern (MEDIUM VALUE, LONG-TERM)

**Current state:** CoDRAG's MCP tools are defined in `mcp_tools.py`, handlers in `mcp/server.py`, CLI in `cli.py` — three separate sources of truth that can drift.

**Opportunity:** Define operations once (schema + handler), auto-generate MCP tool definitions, CLI subcommands, and API routes. Reduces maintenance burden and prevents drift.

**Scope:** Architectural refactor. Not chunking-specific, but a good pattern observed in gbrain.

### 4.5 Contextual Retrieval (HIGH VALUE, from Anthropic research)

**Current state:** Chunks are embedded without document-level context. A chunk from the middle of a file has no awareness of where it sits in the broader file.

**Opportunity:** Anthropic's Contextual Retrieval approach: prepend a short LLM-generated context summary to each chunk before embedding. Example: *"This chunk is from the search method of CodeIndex, which handles hybrid semantic+keyword retrieval."* Reported 49% reduction in retrieval failures (67% combined with BM25).

**Trade-off:** Requires LLM call during indexing for every chunk. Expensive at build time, but amortized over many searches. Could be an optional enrichment pass.

**Scope:** Build pipeline (`src/codrag/core/index.py` build path). The META_SYNOPSIS chunk is already a step in this direction.

### 4.6 Jina-Style Late Chunking (EXPLORATORY)

**Current state:** CoDRAG embeds each chunk independently after splitting.

**Opportunity:** Embed the full document through a long-context model first, then segment the token-level embeddings into chunks. Preserves cross-chunk context in embeddings. Requires a long-context embedding model (Jina embeddings-v3 supports 8192 tokens).

**Trade-off:** Requires model change. nomic-embed-text-v1.5 already supports 8192 tokens but the chunking pipeline would need restructuring. More research needed on whether this works well for code.

---

## 5. Recommended Priority

| # | Opportunity | Value | Effort | Priority |
|---|-----------|-------|--------|----------|
| 1 | Semantic boundary detection for markdown | High | Medium | **P1** |
| 2 | Contextual Retrieval (LLM context prepend) | High | Medium | **P1** |
| 3 | Multi-query expansion | Medium | Low-Med | **P2** |
| 4 | Cross-file text-similarity dedup | Low-Med | Low | **P3** |
| 5 | Contract-first operations | Medium | High | **P3** |
| 6 | Late chunking | Exploratory | High | **P4** |

Items 1 and 2 address real retrieval quality gaps. Item 3 is a quick win. Items 4-6 are longer-term improvements.

---

## 6. Academic References

| Topic | Source |
|-------|--------|
| Savitzky-Golay filter | Savitzky & Golay, "Smoothing and Differentiation of Data" (Analytical Chemistry, 1964) |
| Semantic chunking in RAG | Greg Kamradt, semantic chunking implementations (2023); LangChain SemanticChunker |
| Reciprocal Rank Fusion | Cormack, Clarke, Buettcher, "RRF outperforms Condorcet and individual Rank Learning Methods" (SIGIR 2009). K=60 is the paper's default. |
| Contextual Retrieval | Anthropic, "Introducing Contextual Retrieval" (September 2024). 49% fewer retrieval failures. |
| Late Chunking | Jina AI, "Late Chunking" (October 2024). Preserves cross-chunk context in embeddings. |
| RAGAS evaluation | Shahul Es et al., "RAGAS: Automated Evaluation of RAG" (2023). Context precision/recall metrics. |
| AST-aware code chunking | Sourcegraph Cody, Continue.dev, CoDRAG (tree-sitter). Industry standard for code. |
| GraphRAG | Microsoft, "From Local to Global: A GraphRAG Approach" (2024). Knowledge graphs over chunks. |
| ColBERT late interaction | Khattab & Zaharia, "ColBERT: Efficient and Effective Passage Search" (SIGIR 2020). Token-level matching. |
| Repo Map technique | Paul Gauthier / Aider, tree-sitter signature extraction for high-signal context (2023-2024) |

---

## 7. GBrain Notable Design Decisions

For reference, aspects of gbrain's architecture that are interesting but not directly transferable:

- **"Compiled truth + timeline" model:** Each knowledge page has curated content above a separator, append-only evidence below. Good epistemological design for AI-maintained knowledge bases. CoDRAG's observation/concept system serves a similar purpose differently.
- **Skills as fat markdown:** Operational workflows shipped as markdown files that work across CLI and plugin contexts. Interesting distribution model.
- **Single Bun binary:** The entire TypeScript app compiles to one binary via `bun build --compile`. CoDRAG's multi-process architecture (Python + Rust + Node) makes this impractical.
- **PostgreSQL + pgvector:** Cloud-native storage. CoDRAG deliberately chose local-first (SQLite + numpy). Different design philosophies, both valid.
