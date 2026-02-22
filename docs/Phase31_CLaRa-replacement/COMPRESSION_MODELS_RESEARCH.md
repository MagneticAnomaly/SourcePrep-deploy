# CLaRa Replacement Research — Compression Model Candidates

> **Date**: 2026-02-20
> **Context**: CLaRa-7B-Instruct failed both code (29% retention) and language (20% retention) tests. We need a replacement that actually preserves content rather than generating QA answers.
> **Strategy**: Possibly use two models — one for code, one for language/docs — since these are fundamentally different compression tasks.

---

## CoDRAG Requirements

| Requirement | Target | Why |
|-------------|--------|-----|
| **Code retention** | ≥80% of function names, file paths, imports | AI tools need exact references |
| **Language retention** | ≥60% of key facts, domain concepts | Docs summaries must preserve specifics |
| **Zero hallucination** | No fabricated names/paths | Invented code references are worse than no compression |
| **Latency** | <3s on MPS, <1s on CUDA | Interactive MCP tool response time |
| **Model size** | <2GB (ideally <500MB) | Ships with CoDRAG or auto-downloads |
| **No GPU required** | Must work on CPU/MPS | Most CoDRAG users are on Mac laptops |
| **Python API** | pip-installable, no sidecar server | Simpler than CLaRa's FastAPI sidecar |
| **Preserves structure** | File path headers, code blocks intact | CoDRAG's context format relies on `[@path]` headers |

---

## Model Categories

### Category A: Token Pruning (Hard Prompt)
**How it works**: A classifier scores each token's importance, then removes low-scoring tokens. Original text is preserved — only tokens are deleted.

**Key property**: **Zero hallucination** — can only remove, never invent.

### Category B: Soft Prompt Compression
**How it works**: Encodes text into special compressed tokens (embeddings). The LLM reads these tokens instead of the original text.

**Key property**: Extreme compression ratios (up to 500×), but requires specific LLM architecture.

### Category C: Generative Summarization
**How it works**: An LLM reads the text and generates a shorter version.

**Key property**: Can restructure and paraphrase, but risks hallucination. (CLaRa is in this category — we know it fails.)

### Category D: Structural/AST-Based
**How it works**: Parses code into an AST, extracts signatures/structure, discards implementation bodies.

**Key property**: Perfect for code, but doesn't apply to natural language.

---

## Candidate Evaluations

### 1. LLMLingua-2 (Microsoft) ⭐⭐⭐⭐⭐

| Attribute | Details |
|-----------|---------|
| **Category** | A — Token Pruning |
| **Paper** | ACL 2024 Findings |
| **Model** | `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` (XLM-RoBERTa-Large, ~560M params) |
| **Small variant** | `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank` (~178M params) |
| **Install** | `pip install llmlingua` |
| **Deps** | transformers, torch (already in CoDRAG's dep tree) |
| **Compression** | 2×–20× configurable via `rate` parameter |
| **Latency** | ~50–200ms on CPU for typical prompts (3–6× faster than LLMLingua-1) |
| **Hallucination** | **Zero** — only removes tokens, never generates |
| **Content type** | Task-agnostic — works on code AND language |
| **License** | MIT |

**How it works**: Trained via data distillation from GPT-4. A BERT/XLM-RoBERTa encoder classifies each token as "keep" or "drop". Tokens marked "drop" are removed. The remaining text is the compressed output — original words in original order.

**API**:
```python
from llmlingua import PromptCompressor

llm_lingua = PromptCompressor(
    model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
    use_llmlingua2=True,
)

result = llm_lingua.compress_prompt(
    prompt,
    rate=0.33,  # Keep 33% of tokens
    force_tokens=['\n', '?', ':', '@', '/', '.py', '.ts', '.md'],  # Never remove these
)
compressed = result['compressed_prompt']
```

**CoDRAG fit**:
- ✅ `force_tokens` can preserve file path components (`@`, `/`, `.py`, `.ts`)
- ✅ Works on both code and language (task-agnostic)
- ✅ Zero hallucination by design
- ✅ MIT license, pip install, no sidecar
- ✅ Configurable compression ratio
- ⚠️ At high compression (>5×), may remove semantically important tokens from code
- ⚠️ Doesn't understand code structure (treats all tokens equally)

**Verdict**: **Top candidate for language compression.** Likely good for code at moderate ratios (2–3×). The `force_tokens` feature is key — we can protect file paths and syntax.

---

### 2. LongLLMLingua (Microsoft) ⭐⭐⭐⭐

| Attribute | Details |
|-----------|---------|
| **Category** | A — Token Pruning (RAG-optimized) |
| **Paper** | ACL 2024 / ICLR ME-FoMo 2024 |
| **Model** | Uses any causal LM (default: GPT-2, or LLaMA-7B for better quality) |
| **Install** | Same `pip install llmlingua` package |
| **Compression** | Up to 4× with 21.4% RAG performance improvement |
| **Latency** | Slower than LLMLingua-2 (uses causal LM inference) |
| **Hallucination** | **Zero** — token removal only |
| **Special feature** | **Context reordering** — puts most relevant info at start/end to avoid lost-in-the-middle |

**How it works**: Specifically designed for RAG scenarios. Uses question-aware perplexity to rank document relevance, then prunes tokens. Also reorders context to mitigate the "lost in the middle" problem.

**CoDRAG fit**:
- ✅ Designed exactly for RAG (CoDRAG IS a RAG system)
- ✅ Question-aware: compression adapts to the query
- ✅ Context reordering could improve AI tool responses
- ⚠️ Requires a causal LM (GPT-2 ~500MB, or LLaMA-7B ~14GB)
- ⚠️ Slower than LLMLingua-2 (causal LM inference per document)
- ❌ GPT-2 quality may be poor on code tokens

**Verdict**: **Interesting for the RAG reordering feature**, but LLMLingua-2 is faster and doesn't need a causal LM. Could be a future enhancement.

---

### 3. LongCodeZip (ASE 2025) ⭐⭐⭐⭐

| Attribute | Details |
|-----------|---------|
| **Category** | A+D — Hybrid (function-level ranking + token pruning) |
| **Paper** | ASE 2025 |
| **Model** | Requires a code LLM (default: Qwen2.5-Coder-7B-Instruct) |
| **Install** | `pip install git+https://github.com/YerbaPage/LongCodeZip.git` |
| **Compression** | Configurable via `rate` parameter |
| **Hallucination** | **Zero** — pruning only, no generation |
| **Content type** | **Code only** |

**How it works**: Two-stage framework:
1. **Coarse-grained**: Chunks code by function boundaries, ranks functions by conditional perplexity w.r.t. the query. Selects most relevant functions.
2. **Fine-grained**: Within selected functions, uses entropy-based block detection + 0/1 knapsack optimization to prune tokens while maximizing relevance.

**API**:
```python
from longcodezip import LongCodeZip

compressor = LongCodeZip(model_name="Qwen/Qwen2.5-Coder-7B-Instruct")
result = compressor.compress_code_file(
    code=code_string,
    query=query,
    instruction=instruction,
    rate=0.5,  # Keep 50% of tokens
)
compressed_code = result['compressed_code']
```

**CoDRAG fit**:
- ✅ Understands code structure (function-level chunking)
- ✅ Query-aware: selects functions relevant to the question
- ✅ Zero hallucination (pruning, not generation)
- ❌ **Requires 7B code LLM** — too heavy for desktop deployment
- ❌ Code-only — can't handle docs/language
- ❌ Latency: 7B model inference on MPS would be ~20s+ (same problem as CLaRa)
- ⚠️ New project (ASE 2025), limited community adoption

**Verdict**: **Right idea, wrong weight class.** The function-level + token-level approach is exactly what CoDRAG needs for code, but requiring a 7B model defeats the purpose. However, we could potentially **replace the 7B model with a smaller classifier** or use CoDRAG's existing chunking (we already chunk by function boundaries via tree-sitter!).

---

### 4. Stingy Context / TREEFRAG (2025) ⭐⭐⭐⭐

| Attribute | Details |
|-----------|---------|
| **Category** | D — Structural/AST-Based |
| **Paper** | arXiv 2601.19929 (Jan 2025) |
| **Model** | No ML model — pure algorithmic (tree-sitter + heuristics) |
| **Install** | No public implementation yet (paper only) |
| **Compression** | 18:1 on real codebases (239K → 11K tokens) |
| **Hallucination** | **Zero** — extractive only |
| **Content type** | **Code only** |

**How it works**: Defines 7 "Levels of Detail" (LOD) for code:
1. LOD 0: Full source
2. LOD 1: Remove comments
3. LOD 2: Remove function bodies (keep signatures)
4. LOD 3: Remove method bodies (keep class structure)
5. LOD 4: Keep only imports + class/function signatures
6. LOD 5: Keep only file names + top-level exports
7. LOD 6: Keep only directory tree

Uses tree-sitter to parse code and extract at the desired LOD level. The TREEFRAG algorithm selects which files get which LOD based on relevance.

**Results**: 94–97% success on 40 real-world issues across 12 frontier models.

**CoDRAG fit**:
- ✅ **Perfect conceptual match** — hierarchical LOD is exactly what CoDRAG's trace graph provides
- ✅ No ML model needed — pure algorithmic, instant, zero latency
- ✅ Zero hallucination (extractive)
- ✅ Uses tree-sitter (CoDRAG already has tree-sitter via codrag-parser)
- ❌ **No public implementation** — paper only as of Feb 2025
- ❌ Code-only — no language/docs compression
- ⚠️ Requires reimplementation based on paper

**Verdict**: **The approach we should build ourselves.** CoDRAG already has tree-sitter parsing and trace graph data. We can implement LOD-style extraction using our existing infrastructure. This is the strongest code compression strategy — and we have all the building blocks.

---

### 5. Repomix (yamadashy) ⭐⭐⭐

| Attribute | Details |
|-----------|---------|
| **Category** | D — Structural/Tree-sitter |
| **Tool type** | CLI tool (Node.js) |
| **Install** | `npx repomix` or `npm install -g repomix` |
| **Compression** | ~70% token reduction with `--compress` flag |
| **Hallucination** | **Zero** — extractive only |
| **Content type** | **Code + some docs** |

**How it works**: Packs entire repos into a single AI-friendly file. With `--compress`, uses tree-sitter to extract function/class signatures while stripping implementation bodies. Also has an MCP server.

**CoDRAG fit**:
- ✅ Proven tool with community adoption (JSNation 2025 nomination)
- ✅ Uses tree-sitter (same parser CoDRAG uses)
- ❌ **Node.js tool, not Python** — can't integrate as a library
- ❌ Whole-repo packing, not query-aware compression
- ❌ Not designed for per-query context assembly
- ⚠️ Different use case: repo-to-file packing, not RAG context compression

**Verdict**: **Wrong tool for our use case.** Repomix packs whole repos, CoDRAG needs per-query context compression. But the tree-sitter signature extraction approach is exactly what Stingy Context does — and we can implement that ourselves.

---

### 6. 500xCompressor (ACL 2025) ⭐⭐

| Attribute | Details |
|-----------|---------|
| **Category** | B — Soft Prompt Compression |
| **Paper** | ACL 2025 Main |
| **Model** | Custom extension on LLaMA-based models |
| **Compression** | 6× to 480× |
| **Hallucination** | Medium — regenerated text has small differences |
| **Content type** | Natural language only |

**How it works**: Compresses N natural language tokens into 1 special "soft" token (embedding). The LLM reads these compressed tokens to answer questions or regenerate the original text. Requires a specific LLM architecture with the 500xCompressor weights.

**CoDRAG fit**:
- ✅ Extreme compression ratios
- ❌ **Requires specific LLM architecture** — compressed tokens only work with the trained model
- ❌ CoDRAG outputs text for ANY LLM (Cursor, Windsurf, Claude, ChatGPT) — soft tokens are incompatible
- ❌ Models not yet publicly available (datasets uploaded, not open)
- ❌ Natural language only
- ❌ Regenerated text has small errors (62–73% capability retention)

**Verdict**: **Incompatible with CoDRAG's architecture.** CoDRAG produces text context consumed by arbitrary LLMs. Soft prompt compression requires the downstream LLM to understand the compressed tokens. This is fundamentally incompatible.

---

### 7. CPC — Context-aware Prompt Compression (AAAI 2025) ⭐⭐⭐

| Attribute | Details |
|-----------|---------|
| **Category** | A — Sentence-Level Pruning |
| **Paper** | AAAI 2025 |
| **Model** | Custom context-aware encoder (small) |
| **Compression** | Competitive with LLMLingua-2 |
| **Hallucination** | **Zero** — sentence removal only |
| **Content type** | Natural language |

**How it works**: Instead of token-level pruning (LLMLingua-2), operates at the **sentence level**. A context-aware encoder scores each sentence's relevance to the question, then removes low-scoring sentences. Faster than token-level methods because fewer decisions.

**CoDRAG fit**:
- ✅ Fast (fewer scoring decisions than token-level)
- ✅ Zero hallucination
- ✅ Question-aware
- ⚠️ Sentence-level granularity may be too coarse for code (code "sentences" = lines)
- ⚠️ No public implementation found
- ❌ Natural language only

**Verdict**: **Interesting for language, but LLMLingua-2 is more proven.** Sentence-level is coarser than token-level, which could be an advantage (less risk of breaking syntax) or disadvantage (less compression). No public implementation is a blocker.

---

### 8. Nano-Capsulator (NAACL 2024) ⭐⭐

| Attribute | Details |
|-----------|---------|
| **Category** | C — Generative Summarization |
| **Paper** | NAACL 2024 |
| **Compression** | 81.4% length reduction, 4.5× latency improvement |
| **Hallucination** | Medium — generates new text |

**How it works**: Instead of deleting tokens, generates a concise "capsule" summary. Uses reward-based training with semantic preservation + utility preservation objectives.

**CoDRAG fit**:
- ❌ **Same category as CLaRa** — generative summarization
- ❌ We already proved generative approaches fail on our content (CLaRa: 20–29%)
- ❌ Risk of hallucination

**Verdict**: **Skip.** Same fundamental approach as CLaRa. We've already proven generative compression doesn't work for CoDRAG.

---

### 9. Selective Context ⭐⭐

| Attribute | Details |
|-----------|---------|
| **Category** | A — Token Pruning (entropy-based) |
| **Paper** | Earlier work (2023) |
| **Model** | Any causal LM (GPT-2) |
| **Install** | `pip install selective-context` |

**How it works**: Uses self-information (entropy) from a base language model to identify redundant tokens. Higher-entropy tokens are more informative and kept; lower-entropy tokens are removed.

**CoDRAG fit**:
- ✅ Simple, proven approach
- ⚠️ Superseded by LLMLingua-2 in all benchmarks
- ⚠️ Requires causal LM inference (slower)
- ❌ Not as good as LLMLingua-2 on any metric

**Verdict**: **Superseded.** LLMLingua-2 is strictly better on accuracy, speed, and ease of use.

---

### 10. MInference (Microsoft, 2024) ⭐⭐

Not a compressor — a sparse attention mechanism for processing long prompts faster. Doesn't reduce token count, just speeds up LLM inference on long inputs. Not relevant for CoDRAG (we don't control the downstream LLM).

---

## Comparison Matrix

| Model | Category | Code? | Language? | Hallucination | Model Size | Latency | Python API | Public? | CoDRAG Score |
|-------|----------|-------|-----------|---------------|------------|---------|------------|---------|--------------|
| **LLMLingua-2** | Token prune | ⚠️ | ✅ | Zero | 178–560MB | ~100ms | ✅ pip | ✅ | **⭐⭐⭐⭐⭐** |
| **LongLLMLingua** | Token prune | ⚠️ | ✅ | Zero | 500MB–14GB | ~500ms | ✅ pip | ✅ | ⭐⭐⭐⭐ |
| **LongCodeZip** | Hybrid | ✅ | ❌ | Zero | ~14GB (7B) | ~20s MPS | ✅ pip | ✅ | ⭐⭐⭐⭐ |
| **Stingy Context** | AST/LOD | ✅ | ❌ | Zero | 0 (no model) | ~0ms | ❌ paper | ❌ | ⭐⭐⭐⭐ |
| **Repomix** | AST/tree-sitter | ✅ | ⚠️ | Zero | 0 (no model) | ~0ms | ❌ Node.js | ✅ | ⭐⭐⭐ |
| **CPC** | Sentence prune | ❌ | ✅ | Zero | Small | ~50ms | ❌ | ❌ | ⭐⭐⭐ |
| **500xCompressor** | Soft prompt | ❌ | ✅ | Medium | ~14GB | ~1s | ⚠️ | ⚠️ | ⭐⭐ |
| **Nano-Capsulator** | Generative | ❌ | ✅ | Medium | ~14GB | ~1s | ❌ | ❌ | ⭐⭐ |
| **Selective Context** | Token prune | ⚠️ | ✅ | Zero | 500MB | ~300ms | ✅ pip | ✅ | ⭐⭐ |
| **CLaRa (tested)** | Generative | ❌ | ❌ | Low | 14GB (7B) | 20–65s | ✅ HTTP | ✅ | ⭐ |

---

## Recommended Strategy: Dual-Compressor Architecture

Based on this research, CoDRAG should use **two complementary approaches**:

### For Code: LOD Extraction (Stingy Context approach) — Build In-House

CoDRAG already has everything needed:
- **Tree-sitter parsing** via `codrag-parser` Rust crate
- **Trace graph** with file → symbol containment edges
- **Function/class span data** in trace nodes
- **Augmentation summaries** that describe what each function does

**Implementation**: A `LODCompressor` that:
1. Takes a list of code chunks + their source files
2. For each file, extracts at the appropriate LOD level:
   - **LOD 2** (high relevance): Full function with body
   - **LOD 3** (medium relevance): Function signature + docstring only
   - **LOD 4** (low relevance): Just the function name + file path
3. LOD level selected based on search score (top results get LOD 2, tail gets LOD 4)

**Why build vs buy**: No existing tool fits. LongCodeZip needs a 7B model. Stingy Context has no implementation. Repomix is Node.js. CoDRAG already has the parser infrastructure.

**Expected compression**: 3–10× on code, with ~100% retention of function signatures and file paths.

### For Language: LLMLingua-2 — Use Off-the-Shelf

The clear winner for natural language compression:
- **pip install llmlingua** — ready to use
- **178MB model** (BERT-base) or **560MB model** (XLM-RoBERTa-Large)
- **~100ms latency** on CPU
- **Zero hallucination** — token pruning only
- **`force_tokens`** feature preserves our critical formatting tokens

**Implementation**: A `LinguaCompressor(ContextCompressor)` that:
1. Takes language content (doc chunks, augmentation summaries, epistemic entries, atlas text)
2. Runs LLMLingua-2 with `force_tokens` to protect file paths and key formatting
3. Returns compressed text with original words preserved

**Expected compression**: 2–5× on language content, with high retention of key facts.

### Combined Pipeline

```
Query arrives via MCP
  │
  ├─ CodeIndex search (K=5) → code chunks
  │     │
  │     ├─ Top-3 results (score > 0.5): LOD 2 (full body)
  │     ├─ Results 4-5 (score > 0.3): LOD 3 (signature + docstring)
  │     └─ Trace neighbors: LOD 4 (name + path only)
  │
  ├─ KnowledgeIndex search (K=20) → augmentation/epistemic summaries
  │     └─ LLMLingua-2 compress (rate=0.4) → dense summary
  │
  ├─ Doc chunks from CodeIndex (role=docs) → markdown passages
  │     └─ LLMLingua-2 compress (rate=0.5) → compressed docs
  │
  └─ Atlas segment descriptions
        └─ LLMLingua-2 compress (rate=0.6) → compressed atlas

Final output (~6–8K chars):
  [Atlas context ~500 chars]
  [Knowledge summary ~1K chars]
  [Compressed docs ~1K chars]
  [Raw code chunks ~4K chars with LOD-based detail]
```

---

## Implementation Priority

| Step | What | Effort | Dependencies |
|------|------|--------|-------------|
| **1** | `LinguaCompressor` — wrap LLMLingua-2 | 1 day | `pip install llmlingua` |
| **2** | Test LLMLingua-2 on CoDRAG language data | 1 day | Step 1 + existing test harness |
| **3** | `LODExtractor` — tree-sitter based code LOD | 2–3 days | Existing codrag-parser |
| **4** | Test LOD extraction on CoDRAG code data | 1 day | Step 3 + existing test harness |
| **5** | Dual-channel context assembly in endpoint | 1–2 days | Steps 1–4 |
| **6** | Dashboard integration (compression toggle) | 1 day | Step 5 |

**Total: ~7–9 days** to ship a dual-compressor with tested quality.

---

## Next Steps

1. **Prototype LLMLingua-2** against our existing language test data (`scripts/clara_language_test.py`)
2. **Prototype LOD extraction** using existing trace graph data
3. Measure retention + latency for both
4. If both pass quality gates → implement dual-channel context assembly

---

*Research compiled: 2026-02-20. Sources: Gemini research + arxiv papers + GitHub repos.*
