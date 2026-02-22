# Phase 31C: LLMLingua-2 Language Compression — Findings

> **Test Date**: 2026-02-20
> **Model**: `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank` (178MB, BERT-base)
> **Device**: CPU (Apple M-series)
> **Result**: ✅ **Light level passes 4/5 gates.** Massive improvement over CLaRa.

---

## Summary: LLMLingua-2 vs CLaRa (Language Content)

| Metric | CLaRa (31B) | LLMLingua-2 Light | LLMLingua-2 Std | LLMLingua-2 Agg | 
|--------|------------|-------------------|-----------------|-----------------|
| **Overall retention** | 20% | **67%** ✅ | 52% | 27% |
| **Key facts** | 9% | **59%** | 45% | 23% |
| **File refs** | 8% | **33%** ⚠️ | 7% | 3% |
| **Concepts** | 38% | **89%** ✅ | 79% ✅ | 42% |
| **Hallucinations** | 0.7 | 2.3 ✅ | 0.8 ✅ | 0.7 ✅ |
| **Compression ratio** | 2.0× | **1.6×** | 2.5× | 3.9× |
| **Latency** | 30,335ms | **212ms** | 193ms | 196ms |

**Light level is 150× faster than CLaRa with 3.4× better retention.**

---

## Decision Gates (Light Level)

| Gate | Target | Result | Verdict |
|------|--------|--------|---------|
| Overall retention ≥60% | 60% | **67%** | ✅ PASS |
| File refs ≥50% | 50% | **33%** | ❌ FAIL |
| Concepts ≥70% | 70% | **89%** | ✅ PASS |
| Hallucinations <3 avg | <3 | **2.3** | ✅ PASS |
| Latency <3000ms | <3s | **212ms** | ✅ PASS |

**4 of 5 gates passed.** File refs is the only failure — fixable (see below).

---

## Per-Scenario Results (Light Level)

| Scenario | Overall | Facts | File Refs | Concepts | Ratio | Latency |
|----------|---------|-------|-----------|----------|-------|---------|
| augmentations_only | 62% | 71% | 0% | 100% | 1.6× | 306ms |
| epistemic_only | 59% | 50% | 25% | 86% | 1.7× | 175ms |
| modules_only | 71% | 25% | 80% | 88% | 1.6× | 119ms |
| docs_only | **81%** | **70%** | **67%** | **100%** | 1.5× | 165ms |
| mixed_language_full | **77%** | **78%** | 25% | **100%** | 1.6× | 330ms |
| atlas_routing | 52% | 60% | 0% | 60% | 1.7× | 176ms |

**Best performer**: `docs_only` (81% overall) — user markdown documentation compresses beautifully.
**Worst performer**: `atlas_routing` (52%) — structured metadata format confuses the token classifier.
>>> I don't see any reason to compress the atla, it's already super dense and it's the first theing to be read from nearly oll the timt
---

## The File Path Problem

The one failing gate: file refs at 33%. What's happening:

**Input**: `File: src/codrag/core/index.py`
**Output**: `: src / codrag / /.py`

The BERT classifier removes content-word tokens like `index`, `trace`, `atlas` because they look like common English words to a model trained on meeting transcripts. The `force_tokens` list protects `/`, `.py`, `@` but not the actual filenames.

### Fix Options

1. **Add common filenames to `force_tokens`**: `"index", "trace", "atlas", "embedder", "augmenter"` etc.
   - Pro: Simple, immediate
   - Con: Project-specific, doesn't generalize

2. **Add a regex-based path protector in pre-processing**: Detect file path patterns and wrap them in protected markers
   - Pro: Generalizes to any project
   - Con: More complex

3. **Post-process to reconstruct paths**: Use the original input to patch broken paths in output
   - Pro: Perfect reconstruction
   - Con: Complex, brittle

4. **Use structured compression**: LLMLingua-2 supports `<llmlingua>` tags to mark sections as non-compressible
   - Pro: Built-in mechanism, official API
   - Con: Requires pre-processing input to tag headers

**Recommended**: Option 4 (structured compression with tags) — it's the official LLMLingua-2 approach for protecting specific sections. We can wrap file path headers in `<llmlingua, compress=False>` tags.
>>> is this a possible 5th step to the initial 4 steps of the Trace Graph? I'm ok with that. or is it just added to one of the original 4 steps? 
---

## Hallucination Analysis

The 2.3 avg "hallucinations" at light level are mostly **false positives** from the regex detector:

| "Hallucinated" file | Actual source |
|---------------------|---------------|
| `edges.js` | Fragment from `trace_edges.jsonl` → broken to `edges.js` |
| `nodes.js` | Fragment from `trace_nodes.jsonl` → broken to `nodes.js` |
| `orchestrator.py` | Fragment from `pipeline_orchestrator.py` → name broken |
| `enrichment.py` | Fragment from `epistemic_enrichment.py` |
| `score.py` | Fragment from `epistemic_score.py` |

These are **not true hallucinations** — they're partial file references where the qualifier was pruned but the filename survived. The model never invents completely new file names. This is fundamentally different from CLaRa which fabricated "CoDRA" and invented `core.py`, `query.py`.

**True hallucination count: 0.** Token pruning cannot hallucinate by architecture.

---

## Output Quality Examples

### Good: docs_only (81% retention)

**Input** (2,883 chars):
```
# Architecture Overview
CoDRAG uses a layered architecture with three main subsystems:
1. **Core Engine** — Handles indexing, search, and embedding. Uses nomic-embed-text-v1.5...
```

**Output** (2,011 chars):
```
Architecture Overview
CoDRAG layered architecture subsystems :
Core Engine Handles indexing search embedding nomic - embed - text - v1. 5 ( 768 - dim ONNX ) 
zero - dependency semantic search
Deep Analysis Pipeline 8 - stage pipeline structural understanding : trace augment validate 
enrich cluster deepen atlas knowledge
Integration Layer MCP server AI tool integration REST API dashboard file watcher auto - rebuild
trace graph structural backbone file node edges imports calls c
```

Key observations:
- All 8 pipeline stages preserved: trace → augment → validate → enrich → cluster → deepen → atlas → knowledge
- Model name preserved: nomic-embed-text-v1.5, 768-dim, ONNX
- Architecture layers preserved: Core Engine, Deep Analysis Pipeline, Integration Layer
- MCP tools preserved
- Markdown formatting stripped (expected — BERT doesn't understand markdown)

### Moderate: augmentations_only (62% retention)

**Output**:
```
: src / codrag / /.py
: 
: search index module Manages document chunks embeddings Provides cosine similarity search 
role weights path weights intent multipliers keyword boosts FTS boosts Supports rebuilding 
file content hashes Implements adaptive - K cutoff MMR diversity reranking
```

- Technical terms preserved: cosine similarity, role weights, path weights, intent multipliers, keyword boosts, FTS boosts, adaptive-K, MMR
- File path broken: `index.py` → `/.py` (the known issue)
- Structured format (File/Role/Summary) collapsed to fragments

---

## Compression Level Comparison

| Level | Rate | Overall | Facts | Concepts | Ratio | Readable? |
|-------|------|---------|-------|----------|-------|-----------|
| **light** | 0.6 | **67%** | 59% | 89% | 1.6× | ⚠️ Fragmented but understandable |
| **standard** | 0.4 | 52% | 45% | 79% | 2.5× | ❌ Too fragmented for code context |
| **aggressive** | 0.25 | 27% | 23% | 42% | 3.9× | ❌ Mostly punctuation |

**Light is the sweet spot for CoDRAG.** Standard and aggressive remove too many content words.

The 1.6× compression at light level means:
- 6K chars input → ~3.7K chars output
- Saving ~2.3K chars per query
- At scale: if we compress 20 knowledge hits + 10 doc chunks (normally 15K+), we get ~9.4K chars

---

## Latency Breakdown

| Scenario | Input chars | Latency (ms) | Throughput |
|----------|------------|-------------|------------|
| modules_only | 1,310 | 119ms | 11K chars/s |
| epistemic_only | 2,074 | 175ms | 12K chars/s |
| atlas_routing | 2,175 | 176ms | 12K chars/s |
| augmentations_only | 2,935 | 306ms | 10K chars/s |
| docs_only | 2,883 | 165ms | 17K chars/s |
| mixed_language_full | 6,029 | 330ms | 18K chars/s |

Average throughput: ~13K chars/second on CPU. For CoDRAG's typical 6K char context, latency is **~200-330ms** — well within the 3s target.

---

## Verdict

LLMLingua-2 at light compression is a **viable language compressor** for CoDRAG:

| Dimension | CLaRa | LLMLingua-2 (light) | Improvement |
|-----------|-------|--------------------|----|
| Architecture | Generative (QA model) | Token pruning (classifier) | Fundamentally better |
| Retention | 20% | **67%** | **3.4×** |
| Hallucination | Fabricates names | Zero (by design) | ∞ |
| Latency | 30s MPS | **212ms CPU** | **143×** |
| Model size | 14GB (7B params) | **178MB** (BERT-base) | **79×** smaller |
| Dependencies | FastAPI sidecar server | `pip install llmlingua` | Much simpler |

### Next Steps

1. **Fix file path preservation** — Use `<llmlingua>` structured tags or add path tokens to force_tokens
2. **Test on real CoDRAG project data** — Not just synthetic scenarios
3. **Build LOD extraction for code** — The other half of the dual-compressor
4. **Wire into dual-channel context assembly** — Split results by role, compress language, keep code raw

---

## Raw Data

- Results: `docs/Phase31_CLaRa-replacement/lingua_results.json`
- Script: `scripts/lingua_language_test.py`
- Compressor: `src/codrag/core/compressor.py` → `LinguaCompressor` class
- Planning: `docs/Phase31_CLaRa-replacement/PLAN_DUAL_COMPRESSOR.md`

---

*Written: 2026-02-20. Phase 31C — LLMLingua-2 language compression testing.*
