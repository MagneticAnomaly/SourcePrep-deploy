# Phase 31: CLaRa Compression Testing — Findings

> **Test Date**: 2026-02-20
> **CLaRa Server**: apple/CLaRa-7B-Instruct, compression-16, PyTorch MPS backend
> **Hardware**: Mac Studio, Apple Silicon, 16GB+ unified memory
> **Model Load Time**: 14.7s cold start

---

## Executive Summary

**CLaRa compression is NOT suitable for CoDRAG's code context use case in its current form.**

The model was designed for QA over natural language documents (Wikipedia passages), not for preserving code structure. When given source code, it:

1. **Generates natural language descriptions** instead of preserving code
2. **Drops file paths entirely** (0% retention across all tests)
3. **Hallucinate project names and acronyms** ("CoDRAG" expanded to fabricated names)
4. **Runs too slowly on MPS** (20–65 seconds per request vs <3s target)

The good news: CoDRAG's current defaults (K=5, max_chars=6000, no compression) are already in the research-validated sweet spot. CLaRa compression is a future optimization that requires either (a) a code-specific compression model, or (b) a fundamentally different integration approach.

---

## Test Results

### Phase A: Smoke Test ✓

CLaRa server responded correctly. Three max_new_tokens values tested:

| max_new_tokens | Output Chars | Latency (MPS) |
|----------------|-------------|---------------|
| 128 | 641 | 20.8s |
| 256 | 1,124 | 25.1s |
| 512 | 2,187 | 42.2s |

**Finding**: Output scales roughly linearly with max_new_tokens. The model generates complete sentences, not code.

**Critical finding**: CLaRa fabricated what "CoDRAG" means in every response:
- "Command-line Differential Anomaly and Graph"
- "Codex"
- "Contextual Deep Learning for Anomalous Relations and Graphs"

None of these appear in the input. This is pure hallucination from the base Mistral-7B model.

---

### Phase B: Code Retention Tests ❌

Three code test cases with known expected elements. max_new_tokens=512.

#### Overall Results

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| **Function name retention** | ≥80% | **70%** (avg of 50%, 60%, 100%) | ❌ FAIL |
| **Class name retention** | ≥80% | **44%** (avg of 75%, 33%, 25%) | ❌ FAIL |
| **File path retention** | ≥80% | **0%** (0/6 paths survived) | ❌ FAIL |
| **Key fact retention** | ≥60% | **19%** (avg of 12%, 33%, 12%) | ❌ FAIL |
| **Overall retention** | ≥80% | **29%** | ❌ FAIL |
| **Hallucination count** | <5 avg | **4.0** avg | ✅ PASS (barely) |

#### Per-Test Breakdown

**Test 1: Search Pipeline** (search + embedder code)
- Input: 2,955 chars → Output: 1,739 chars (1.7× compression)
- Functions: 2/4 retained (search, embed — missed _resolve_path_weight, _ensure_model_ready)
- Classes: 3/4 retained (CodeIndex, OllamaEmbedder, Embedder — missed NativeEmbedder)
- Paths: 0/2 retained
- Facts: 1/8 retained (cosine similarity — missed role_weights, path_weights, min_score, top-K, nomic-embed-text, Matryoshka, 768)
- Hallucinations: 9 (including "OllaOEmbedder", "OllaOllamaEmbedder" — garbled class names)
- Latency: 33.8s

**Test 2: Trace System** (trace builder + epistemic scoring)
- Input: 1,674 chars → Output: 941 chars (1.8× compression)
- Functions: 3/5 retained (build, search, neighbors — missed _build_rust, node_degree)
- Classes: 1/3 retained (TraceIndex — missed TraceBuilder, EpistemicScore)
- Paths: 0/2 retained
- Facts: 3/9 retained (Rust engine, graph, structural — missed callers, callees, imports, epistemic, composite, 6 components)
- Hallucinations: 3
- Latency: 18.8s

**Test 3: Compression Pipeline** (compressor + API integration)
- Input: 1,807 chars → Output: 263 chars (6.9× compression)
- Functions: 1/1 retained (compress)
- Classes: 1/4 retained (ClaraCompressor — missed NoopCompressor, ContextCompressor, CompressResult)
- Paths: 0/2 retained
- Facts: 1/8 retained (clara_compression — missed localhost:8765, memories, query, budget_chars, compression_ratio, require_feature, Pro tier)
- Hallucinations: 0
- Latency: 5.9s

#### Key Observations

1. **File paths are completely lost.** CLaRa never outputs `src/codrag/core/index.py` or any file path. It generates prose descriptions instead. This is a fundamental mismatch — CoDRAG's context format relies on file path headers for attribution.

2. **Private methods are lost.** Internal methods like `_resolve_path_weight` and `_build_rust` are consistently dropped. CLaRa prioritizes high-level concepts over implementation details.

3. **Numerical facts are lost.** Specific values like "768", "0.15" (min_score), "16" (compression rate) are dropped. CLaRa generalizes to concepts rather than preserving specific values.

4. **Garbled names.** The most concerning hallucination was "OllaOEmbedder" and "OllaOllamaEmbedder" — partial corruptions of "OllamaEmbedder". This suggests the token-level compression sometimes corrupts proper nouns.

5. **Actual compression ratio is only 1.7–6.9×**, not the advertised 16×. The "16×" figure refers to internal token-level compression, not text output reduction. The `max_new_tokens` parameter controls output length, not a true compression ratio.

---

### Phase C: Latency Profile ❌

Tested on MPS (Apple Silicon) with warm model.

| Volume | Chunks | Input Chars | Output Chars | Latency |
|--------|--------|-------------|-------------|---------|
| 1K (tiny) | 1 | 1,887 | 624 | **11.3s** |
| 6K (default) | 7 | 13,430 | 980 | **25.3s** |
| 20K (large) | 25 | 48,048 | 1,128 | **65.3s** |

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Cold start | <30s | 14.7s | ✅ PASS |
| Per-request (1 chunk) | <2s | 11.3s | ❌ FAIL (5.6× over) |
| Per-request (7 chunks) | <3s | 25.3s | ❌ FAIL (8.4× over) |
| Per-request (25 chunks) | <3s | 65.3s | ❌ FAIL (21.8× over) |

**Latency scales roughly linearly with input volume.** Each additional chunk adds ~2.2 seconds.

At K=30 (the proposed CLaRa-mode default), estimated latency would be ~**70 seconds** — completely impractical for interactive use.

---

### Phase D: End-to-End Benchmark (Quick)

Baseline (K=5, no compression) vs CLaRa (K=30, compression) on real CoDRAG project.

| Config | Avg Output Chars | Avg Tokens | Avg Latency | Compression |
|--------|-----------------|------------|-------------|-------------|
| **baseline_k5** | 6,031 | ~1,507 | **1.2s** | none |
| **clara_k30** | 618 | ~154 | **26.2s** | 16× (40K→618) |

**The baseline delivers 10× more useful content at 21× lower latency.**

CLaRa compressed 40,000 chars of real CoDRAG code down to ~618 chars of natural language prose. The output is too short (max_new_tokens=128 in the API default) and contains no file paths, no function signatures — just a narrative summary.

Even if max_new_tokens were increased, the fundamental problem remains: CLaRa generates QA-style prose, not preserved code context.

---

## Decision Gate Results

| Gate | Criteria | Result | Verdict |
|------|----------|--------|---------|
| **G1: Code Accuracy** | Function/class names ≥80% | 29% overall | ❌ **FAIL** |
| **G2: No Hallucination** | <5 fabricated names avg | 4.0 avg | ✅ PASS (barely) |
| **G3: Latency Budget** | <3s total on MPS | 25s avg | ❌ **FAIL** |
| **G4: Quality Win** | CLaRa ≥ baseline on 60% | Baseline 10× more content, 21× faster | ❌ **FAIL** |

**3 of 4 gates failed. CLaRa compression is not ready for CoDRAG's code context use case.**

---

## Root Cause Analysis

### Why CLaRa Fails on Code

CLaRa was trained on **Wikipedia QA tasks** (Natural Questions, HotpotQA, MuSiQue, 2WikiMultiHopQA). Its training data is natural language documents, and its objective is answering factual questions.

When given source code, CLaRa treats it as natural language and:
1. **Paraphrases** rather than preserves (it was trained to generate answers, not compress text)
2. **Generalizes** specific values to concepts (because QA doesn't need exact numbers)
3. **Ignores structural metadata** like file paths (because Wikipedia doesn't have file paths)
4. **Hallucinates domain knowledge** from Mistral-7B's training data (because it has priors about what code libraries do)

### The Fundamental Mismatch

CoDRAG needs: **"Here is the code, with file paths and exact function signatures preserved"**
CLaRa provides: **"Here is what I think the code does, explained in prose"**

These are different tasks. CLaRa is a QA model, not a code compression model.

---

## Recommendations

### Short-Term (Keep Current Approach)

1. **Keep CLaRa disabled by default.** The current NoopCompressor + K=5 + max_chars=6000 is the right approach.
2. **Do not ship CLaRa as a Pro feature** until a code-suitable compression model exists.
3. **Keep the ClaraCompressor/NoopCompressor abstraction.** The interface is correct — only the model behind it is wrong.

### Medium-Term (Alternative Approaches to Investigate)

| Approach | Description | Effort | Promise |
|----------|-------------|--------|---------|
| **LLM-based summarization** | Use a code-aware LLM (e.g. CodeLlama, DeepSeek-Coder) to summarize code chunks while preserving signatures | Medium | High |
| **LLMLingua-2 for code** | Token-pruning approach preserves original text — no hallucination risk | Low | Medium |
| **Extractive compression** | AST-based: keep function signatures + docstrings, drop implementation bodies | Low | Medium-High |
| **Hybrid** | Extractive first (keep signatures), then LLM summarization of bodies | Medium | High |
| **Wait for code-trained CLaRa** | Apple may release code-domain CLaRa variants | Zero | Unknown |

### Long-Term Vision

The ideal CoDRAG compression pipeline would be:

```
Raw code chunks (40K chars)
    ↓
[1] Extractive pass: Keep function signatures, class names, imports, file paths
    (~15K chars — guaranteed no hallucination)
    ↓
[2] Summarization pass: Code-aware LLM summarizes implementation bodies
    (~6K chars — controlled generation)
    ↓
[3] Format: Structured output with file path headers preserved
    ↓
Output: ~6K chars with 100% path accuracy, high function accuracy
```

This is fundamentally different from CLaRa's approach. CLaRa does step 2 (summarization) but skips step 1 (extractive) and step 3 (structured output).

---

## What CoDRAG Gets Right (Validation)

The testing process validated CoDRAG's current architecture:

1. **K=5 / max_chars=6000 is the right default.** Research says 1.5K–4K tokens is the sweet spot for injected RAG context. CoDRAG delivers exactly this.

2. **The 8-layer filtering pipeline works.** CoDRAG's value is in *selecting* the right 5 chunks, not in compressing 50 chunks into 5.

3. **Trace expansion adds value without compression.** Following graph edges to find structurally related code is orthogonal to compression — it improves *what* is selected, not *how much* is sent.

4. **The compression abstraction is correct.** `ContextCompressor` → `ClaraCompressor` / `NoopCompressor` is clean. When a suitable model arrives, it drops in.

---

## Raw Data

- Quality test results: `docs/Phase31_CLaRa-tests/quality_512tokens.json`
- Latency profile: `docs/Phase31_CLaRa-tests/latency_quick.json`
- Scripts: `scripts/clara_benchmark.py`, `scripts/clara_quality_eval.py`, `scripts/clara_latency_profile.py`

---

*Findings written: 2026-02-20. Based on CLaRa-7B-Instruct, compression-16, MPS backend.*
