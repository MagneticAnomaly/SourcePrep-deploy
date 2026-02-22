# Phase 31: CLaRa Compression Testing Strategy

> **Goal**: Validate that CLaRa compression lets CoDRAG deliver 5–10× more raw context while keeping the final token footprint at ~1,500 tokens — the proven sweet spot for downstream LLM accuracy.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Research Synthesis](#research-synthesis)
3. [CoDRAG + CLaRa Strategy](#codrag--clara-strategy)
4. [Testing Plan](#testing-plan)
5. [Benchmark Matrix](#benchmark-matrix)
6. [Success Criteria](#success-criteria)
7. [Scripts & Artifacts](#scripts--artifacts)
8. [Open Questions](#open-questions)

---

## 1. Executive Summary

### The Opportunity

CoDRAG's default context output is **~1,500 tokens** (6,000 chars, K=5). With trace expansion it's ~2,000 tokens. This is deliberately conservative — research shows this is the sweet spot where downstream LLM accuracy is highest.

But **what if the question needs more context?** Architecture queries, large refactors, and multi-hop reasoning benefit from seeing more of the codebase. The problem: pushing past ~15K tokens causes measurable accuracy degradation (Chen 2025, Chroma 2025).

**CLaRa solves this.** Apple's 7B compression model achieves **16× semantic compression** while preserving QA accuracy — in some benchmarks *exceeding* uncompressed baselines. If we feed CLaRa 10× more raw context (60,000 chars / ~15,000 tokens) and compress it back to ~1,500 output tokens, we get:

- **10× more codebase coverage** per query
- **Same token footprint** as today's default
- **Better signal density** — CLaRa is query-aware, so it prioritizes relevant details

### The Question This Phase Answers

> "When CLaRa is enabled, can we raise `max_chars` from 6,000 to 60,000 and `K` from 5 to 30–50, compress the result back to ~6,000 chars, and achieve **equal or better** downstream answer quality?"

---

## 2. Research Synthesis

### 2.1 CLaRa: What We Know

**Source**: Apple ML Research, arXiv 2511.18659 (Nov 2025)

| Fact | Value |
|------|-------|
| **Model** | CLaRa-7B-Instruct (Mistral-7B-Instruct-v0.2 base) |
| **Size** | 7B parameters, ~14GB fp16 |
| **Compression modes** | `compression-16` (16×), `compression-128` (128×) |
| **Mechanism** | Learned memory tokens per document → latent space compression |
| **Training** | 3-stage: SCP pretraining (2M Wikipedia passages) → instruction tuning → end-to-end with differentiable top-k |
| **Hardware** | CUDA 14GB+ VRAM, MPS 16GB+ unified, CPU 28GB+ (slow) |

**Benchmark results (CLaRa-Mistral-7B, Normal setting, 5 retrieved docs):**

| Dataset | Compression | F1 | vs LLMLingua-2 | vs PISCO | vs Full-Text |
|---------|-------------|-----|-----------------|----------|--------------|
| NQ | 4× | 50.89 | +5.37 | +1.13 | +2.36 |
| HotpotQA | 4× | varies | +5.37 avg | +1.13 avg | competitive |
| MuSiQue | 16× | competitive | better | better | comparable to DRO |
| 2WikiMultiHop | 16× | 47.18 | better | better | +3.53 vs DRO |

**Key findings from the paper:**
- At 16× compression, CLaRa **matches or exceeds** full-text RAG baselines
- At 128× compression, quality drops but remains usable (EM 69.96 on NQ Oracle, only −6.54 from 4×)
- "Weak document relevance bottlenecks the system before compression quality does" — retrieval quality matters more than compression ratio
- Retrieval performance is excellent: 96.21% Recall@5 at 4× on HotpotQA (vs BGE-Reranker 85.93%)

### 2.2 Comparison: CLaRa vs LLMLingua vs PISCO

| Method | Type | Compression | Accuracy Preservation | Speed | Hardware |
|--------|------|-------------|----------------------|-------|----------|
| **CLaRa** | Soft (latent space) | 16–128× | Best (exceeds full-text) | ~300ms/request (GPU) | 14GB VRAM |
| **LLMLingua** | Hard (token pruning) | Up to 20× | Good (−1.5% at 20×) | Fast (small LM perplexity) | 2–4GB |
| **LLMLingua-2** | Hard (trained classifier) | Up to 20× | Better than v1 | Fast | 2–4GB |
| **PISCO** | Soft (embedding) | 16× | Good (competitive) | Similar to CLaRa | Similar |

**CLaRa's advantage for CoDRAG:**
- **Query-aware compression** — CLaRa takes both memories AND query, focusing compression on query-relevant details
- **Generative output** — produces readable text (not truncated tokens), which the downstream LLM can directly reason over
- **Already integrated** — `ClaraCompressor` and `clara-server` are in our codebase

### 2.3 The "Sweet Spot" Research

From our existing CONTEXT_VOLUME_RESEARCH.md and additional sources:

| Finding | Source | Implication for CLaRa Strategy |
|---------|--------|-------------------------------|
| RAG performance saturates at 4K–16K tokens | Databricks 2024 | Feed CLaRa 15K tokens pre-compression, output ~1.5K |
| Even perfect retrieval degrades at 30K+ tokens | Chen 2025 (EMNLP) | CLaRa's compressed output MUST stay under 4K tokens for the downstream LLM |
| Semantic distractors are worst | Chroma 2025 | CLaRa's query-aware compression naturally filters semantic noise |
| "Lost in the Middle" U-shaped attention | Liu 2023 | CLaRa collapses all memories into a single answer — no "middle" to lose |
| 719% latency at 15K words | Bintner-adjacent 2025 | CLaRa eliminates the latency hit by compressing before delivery |

### 2.4 Critical Insight: CLaRa Isn't Just Smaller — It's Different

Traditional RAG: Send 5 best chunks → LLM reasons over raw text
CLaRa RAG: Send 50 chunks to CLaRa → CLaRa generates a **query-focused synthesis** → LLM reasons over the synthesis

This means:
- **The downstream LLM never sees 50 chunks** — it sees a dense, pre-reasoned summary
- **The "lost in the middle" problem doesn't apply** — CLaRa has already reasoned over all 50 chunks
- **The token budget is spent on signal, not raw code** — every token in the compressed output was selected for query relevance

---

## 3. CoDRAG + CLaRa Strategy

### 3.1 Two Operating Modes

| Mode | When CLaRa is OFF (default) | When CLaRa is ON (Pro tier) |
|------|---------------------------|----------------------------|
| **K** | 5 | 20–50 |
| **max_chars** | 6,000 | 30,000–60,000 |
| **trace_expand** | optional | always on |
| **trace_max_chars** | 2,000 | 10,000–20,000 |
| **Output to LLM** | ~1,500 tokens (raw chunks) | ~1,500 tokens (compressed synthesis) |
| **Codebase coverage** | 5 files max | 20–50 files |
| **Structural depth** | 1-hop neighbors | 3-hop neighbors |

### 3.2 The Pipeline When CLaRa is Enabled

```
User Query
    ↓
[1] Embed query
    ↓
[2] Search with K=30, max_chars=40000  ← WIDER NET
    ↓
[3] Score × role_weights × intent × path_weights
    ↓
[4] Top-30 chunks assembled (~40,000 chars / ~10,000 tokens)
    ↓
[5] Trace expansion with trace_max_chars=15000  ← DEEPER GRAPH WALK
    ↓
[6] Total raw context: ~55,000 chars (~14,000 tokens)
    ↓
[7] Split into memories (one per chunk/file), send to CLaRa with query
    ↓
[8] CLaRa compresses + synthesizes → ~4,000–6,000 chars (~1,000–1,500 tokens)
    ↓
OUTPUT → sent to LLM via MCP (same token budget as default mode)
```

### 3.3 Compression Target Calculation

| Scenario | Raw Input | CLaRa 16× | Effective Output | Status |
|----------|-----------|-----------|------------------|--------|
| Conservative (K=15) | 20,000 chars / 5K tokens | 1,250 chars / 312 tokens | 1,250 chars | ⚠️ Too aggressive |
| Balanced (K=30) | 40,000 chars / 10K tokens | 2,500 chars / 625 tokens | 2,500 chars | ✅ Sweet spot |
| Aggressive (K=50) | 60,000 chars / 15K tokens | 3,750 chars / 937 tokens | 3,750 chars | ✅ Good |
| Maximum (K=80) | 100,000 chars / 25K tokens | 6,250 chars / 1,562 tokens | 6,250 chars | ⚠️ Approaching limit |

**Recommended default when CLaRa enabled: K=30, max_chars=40000, compression_target_chars=6000**

This gives CLaRa ~10K tokens of raw material and produces ~1,500 tokens of compressed output — the same budget as today's default.

### 3.4 What "Compression" Really Means Here

**Important**: CLaRa's `compression-16` doesn't mean "16× fewer characters." It means **16 input tokens → 1 memory token in latent space**. The *output* is natural language generated from the compressed representation. The actual character reduction depends on:

1. How much redundancy exists across the input memories
2. How focused the query is (specific queries → shorter answers)
3. The `max_new_tokens` parameter (default 128, can be set higher)

We need to test empirically what `max_new_tokens` value produces the right output length for code context. The paper used 64–128 for QA tasks. For code synthesis, we likely need **256–512**.

---

## 4. Testing Plan

### 4.1 Test Dimensions

| Dimension | Values to Test | Why |
|-----------|---------------|-----|
| **Input volume** | 6K, 15K, 30K, 60K, 100K chars | Find the practical ceiling |
| **K value** | 5, 10, 20, 30, 50 | How many chunks to retrieve |
| **max_new_tokens** | 128, 256, 512, 1024 | Output length for code context |
| **Compression subfolder** | compression-16, compression-128 | Quality vs compression tradeoff |
| **Query type** | Factual, architectural, multi-hop, debugging | Different query patterns |
| **Chunk format** | Raw code, with headers, with file paths, mixed code+docs | What CLaRa preserves best |

### 4.2 Test Phases

#### Phase A: CLaRa Server Smoke Test
- Verify clara-server runs and responds
- Measure cold start time and per-request latency
- Test with trivial input (3 sentences) and verify response shape

#### Phase B: Code-Specific Compression Quality
- Feed real CoDRAG source files as "memories"
- Test if CLaRa preserves: function signatures, import paths, class hierarchies, variable names, error handling patterns
- Compare compressed output to original: what's kept, what's lost?

#### Phase C: Volume Scaling
- Systematically increase input volume from 6K to 100K chars
- Measure: compression ratio, output quality, latency, memory usage
- Find the practical ceiling where quality plateaus or degrades

#### Phase D: End-to-End Quality (The Real Test)
- Use CoDRAG's actual search pipeline with real queries
- Compare answer quality: default (K=5, no compression) vs CLaRa (K=30, compressed)
- Judge by: relevance of output, completeness of answer, accuracy of code references

#### Phase E: Latency Budget
- Measure total round-trip: CoDRAG search + CLaRa compression
- Target: <3 seconds total (search + compression)
- Test on: MPS (Mac), CUDA (GPU server), CPU (worst case)

### 4.3 Test Queries (Code-Specific)

These are designed to test different information needs:

| ID | Query | Type | Expected Coverage |
|----|-------|------|-------------------|
| Q1 | "How does the trace builder work?" | Architectural | trace.py + dependencies |
| Q2 | "What happens when a file changes and the watcher triggers?" | Multi-hop | watcher → build_manager → index |
| Q3 | "Show me how CLaRa compression is integrated" | Factual | compressor.py + projects.py |
| Q4 | "How do path weights affect search results?" | Detailed | index.py search() + repo_policy.py |
| Q5 | "What's the full pipeline from project creation to first search?" | Breadth | 10+ files |
| Q6 | "Debug: why might search return 0 results for a valid query?" | Debugging | embedder + index + min_score logic |
| Q7 | "How does the MCP server route tool calls to projects?" | Integration | mcp_server.py + mcp_tools.py |
| Q8 | "What are all the Pydantic models used in the API?" | Enumeration | all routers |
| Q9 | "Explain the epistemic scoring system" | Domain-specific | epistemic_score.py + epistemic_enrichment.py |
| Q10 | "How does the atlas routing work?" | Complex | atlas.py + index.py + projects.py |

---

## 5. Benchmark Matrix

### 5.1 Compression Quality Metrics

| Metric | How to Measure | Target |
|--------|---------------|--------|
| **Information Retention** | % of key facts from original preserved in compressed output | ≥80% |
| **Code Accuracy** | Function names, parameters, return types correct | ≥95% |
| **Path Accuracy** | File paths mentioned in compressed output are real | 100% |
| **Hallucination Rate** | Facts in compressed output not in original input | <5% |
| **Compression Ratio** | input_chars / output_chars | 4–16× |
| **Semantic Similarity** | Cosine sim of embeddings: original vs compressed | ≥0.75 |

### 5.2 End-to-End Quality Metrics

| Metric | How to Measure | Target |
|--------|---------------|--------|
| **Answer Relevance** | Human judge: does the compressed context answer the query? (1–5) | ≥4.0 |
| **Coverage** | How many relevant files are represented in compressed output? | ≥2× vs default |
| **Completeness** | Does the answer cover all aspects of the query? (1–5) | ≥3.5 |
| **vs Default Baseline** | Side-by-side: CLaRa mode vs default mode, which answer is better? | CLaRa ≥60% wins |

### 5.3 Performance Metrics

| Metric | Target (MPS) | Target (CUDA) | Target (CPU) |
|--------|-------------|---------------|-------------|
| **Cold start** | <30s | <15s | <120s |
| **Per-request latency** | <2s | <500ms | <10s |
| **Memory (model loaded)** | <16GB unified | <14GB VRAM | <28GB RAM |
| **Total pipeline** | <3s | <1.5s | Not recommended |

---

## 6. Success Criteria

### Must-Have (P0)
- [ ] CLaRa produces readable, accurate compressed code context
- [ ] Function names, file paths, and import chains survive compression
- [ ] K=30 + CLaRa produces better answers than K=5 without CLaRa on ≥60% of queries
- [ ] Total latency (search + compression) <3s on MPS

### Should-Have (P1)
- [ ] Compression ratio of 5–10× on typical code context
- [ ] Hallucination rate <5% (no invented function names, no wrong file paths)
- [ ] Output length controllable via max_new_tokens to hit ~6000 char target
- [ ] Graceful degradation: if CLaRa fails, fall back to uncompressed (already implemented)

### Nice-to-Have (P2)
- [ ] compression-128 mode usable for quick queries (extreme compression)
- [ ] Latency <1s on CUDA
- [ ] Works with CPU-only (for users without GPU) at acceptable latency
- [ ] Identify optimal K and max_chars defaults for CLaRa mode

---

## 7. Scripts & Artifacts

### 7.1 Directory Structure

```
scripts/
  clara_benchmark.py        # Main benchmark harness
  clara_quality_eval.py     # Quality evaluation (information retention)
  clara_latency_profile.py  # Latency profiling across backends

docs/Phase31_CLaRa-tests/
  README.md                 # This document
  RESULTS.md                # Benchmark results (generated)
  FINDINGS.md               # Analysis and recommendations (after testing)
```

### 7.2 Script Descriptions

- **`clara_benchmark.py`**: End-to-end benchmark. Connects to a running CoDRAG daemon + CLaRa server. Runs all 10 test queries at different K/max_chars/max_new_tokens configurations. Saves raw results as JSON.

- **`clara_quality_eval.py`**: Offline quality analysis. Takes benchmark results JSON. Measures information retention, code accuracy, hallucination rate, semantic similarity. Produces a summary table.

- **`clara_latency_profile.py`**: Latency-focused profiling. Sends increasing volumes of context to CLaRa. Measures cold start, warm latency, memory usage. Outputs a latency-vs-volume curve.

---

## 8. Open Questions

| ID | Question | Impact | Resolution Path |
|----|----------|--------|-----------------|
| OQ-1 | What `max_new_tokens` produces good code synthesis? Paper used 64–128 for QA. | High — controls output length | Test 128/256/512/1024 in Phase B |
| OQ-2 | Should we chunk per-file or per-function before sending to CLaRa? | Medium — affects compression quality | Test both in Phase B |
| OQ-3 | Does CLaRa hallucinate function names or file paths on code? | High — a dealbreaker if yes | Explicit test in Phase B |
| OQ-4 | What's the latency on Apple Silicon MPS with 50 memories? | High — UX impact | Phase E profiling |
| OQ-5 | Should CLaRa output be structured (JSON) or natural language? | Medium — affects downstream tool parsing | Test both formats |
| OQ-6 | Can we use compression-128 for "quick check" queries? | Low — nice optimization | Test in Phase C |
| OQ-7 | How does CLaRa handle mixed code + documentation chunks? | Medium — CoDRAG sends both | Test in Phase B |

---

## References

1. **CLaRa** — He et al., "CLaRa: Bridging Retrieval and Generation with Continuous Latent Reasoning." arXiv:2511.18659, Nov 2025.
2. **PISCO** — "Pretty Simple Compression for Retrieval-Augmented Generation." ACL Findings 2025.
3. **LLMLingua** — Jiang et al., "LLMLingua: Compressing Prompts for Accelerated Inference." arXiv:2310.05736, 2023.
4. **Context Volume Research** — CoDRAG internal, `docs/Phase28_ContextWindowResearch/CONTEXT_VOLUME_RESEARCH.md`.
5. **CLaRa-Remembers-It-All** — CoDRAG vendor, `vendor/clara-server/`.
6. **Chen et al. (2025)** — "Context Length Alone Hurts LLM Performance." EMNLP 2025.
7. **Chroma (2025)** — "Context Rot: How Increasing Input Tokens Impacts LLM Performance."

---

*Created: 2026-02-20. Phase 31 — CLaRa Compression Testing.*
