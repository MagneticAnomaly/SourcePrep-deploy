# Phase 31C: Dual-Compressor Architecture — Implementation Plan

> **Date**: 2026-02-20
> **Status**: Planning → Implementation
> **Prerequisite**: Phase 31A (CLaRa code tests, FAILED) + Phase 31B (CLaRa language tests, FAILED) + Compression Model Research (10 candidates evaluated)

---

## 1. Problem Statement

CoDRAG's context output to AI tools (via MCP `codrag_context`) is currently uncompressed. Users with large codebases generate context that:
- Exceeds LLM context windows (especially for smaller models)
- Burns tokens proportionally to context size (API cost)
- Contains redundant information (verbose docs, overlapping chunks)

CLaRa-7B-Instruct was tested and **failed catastrophically** on both code (29% retention) and language (20% retention). The root cause: CLaRa is a QA generation model, not a compression model. It generates new text rather than faithfully preserving the input.

## 2. Solution: Dual-Compressor Architecture

We adopt a **two-channel** approach because code and natural language have fundamentally different compression requirements:

| Content Type | Compression Strategy | Tool | Why |
|-------------|---------------------|------|-----|
| **Code chunks** (role=code, tests) | **LOD Extraction** — hierarchical detail levels based on relevance score | In-house (tree-sitter + trace data) | Code needs exact preservation of identifiers, structure, and syntax |
| **Language content** (role=docs, other + knowledge + atlas) | **Token Pruning** — remove low-importance tokens while preserving original text | LLMLingua-2 (Microsoft, MIT) | Language tolerates token removal but not hallucination |

### Why Two Models Instead of One

1. **LLMLingua-2 on code** works but isn't optimal — it treats all tokens equally, doesn't understand that a function name is more important than whitespace or a print statement. At aggressive compression (>5×), it breaks syntax.

2. **LOD extraction on language** doesn't work — natural language doesn't have an AST or "signature vs body" distinction.

3. **Both approaches have zero hallucination** — token pruning removes but never invents, LOD extraction is purely extractive.

## 3. Phase 31C Scope: LLMLingua-2 for Language (This Sprint)

Phase 31C implements and tests the **language channel only**. The code LOD channel is Phase 31D (separate sprint).

### 3.1 What We're Building

A `LinguaCompressor` class that:
1. Extends `ContextCompressor` (existing ABC in `compressor.py`)
2. Wraps `llmlingua.PromptCompressor` with the LLMLingua-2 model
3. Uses `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank` (178MB, BERT-base) for speed
4. Configures `force_tokens` to protect CoDRAG's formatting tokens (`\n`, `@`, `/`, `.py`, `.ts`, `.rs`, etc.)
5. Maps `level` parameter to compression rates:
   - `light` → rate=0.6 (keep 60% of tokens)
   - `standard` → rate=0.4 (keep 40%)
   - `aggressive` → rate=0.25 (keep 25%)
6. Lazy-loads the model on first `compress()` call (don't block startup)
7. Falls back to `NoopCompressor` behavior on any error

### 3.2 How It Integrates

The existing integration points are already wired:

```
# In projects.py:
def _get_compressor(compression: str) -> ContextCompressor:
    if compression == "clara":
        return ClaraCompressor(...)
    # NEW:
    if compression == "lingua":
        return LinguaCompressor(...)
    return NoopCompressor()
```

The `ContextRequest` model already accepts `compression: str` and `compression_level: str`. We just add `"lingua"` as a valid value alongside `"clara"` and `"none"`.

### 3.3 Model Selection Rationale

Two LLMLingua-2 models are available:

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank` | 178MB | Fast (~50ms) | Good |
| `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` | 560MB | Moderate (~150ms) | Better |

We start with **BERT-base** (178MB) because:
- 3× faster inference
- 3× smaller download
- Sufficient quality for our needs (we're compressing natural language, not translating)
- Can upgrade to XLM-RoBERTa-Large later if quality is insufficient

### 3.4 force_tokens Configuration

LLMLingua-2's `force_tokens` parameter specifies tokens that must NEVER be removed during compression. For CoDRAG:

```python
FORCE_TOKENS = [
    # Structural formatting
    '\n', '---', '|',
    # File path components
    '@', '/', '.py', '.ts', '.tsx', '.js', '.rs', '.go', '.md',
    '.jsx', '.rb', '.java', '.swift', '.css', '.html', '.json',
    '.toml', '.yaml', '.yml',
    # CoDRAG context markers
    '[', ']', 'score=',
    # Common code identifiers that appear in language descriptions
    '(', ')', ':', '::', '->', '=>',
    # Punctuation that changes meaning
    '?', '!',
]
```

This ensures that even under aggressive compression:
- File paths like `@src/codrag/core/index.py` survive intact
- Section headers and separators survive
- Score annotations survive

### 3.5 Test Plan

We reuse the existing `clara_language_test.py` test data (6 scenarios, realistic CoDRAG pipeline output) but call LLMLingua-2 locally instead of the CLaRa HTTP server.

**Pass criteria** (same gates as CLaRa tests, for fair comparison):

| Gate | Target | CLaRa Result |
|------|--------|-------------|
| Overall retention ≥60% | 60% | 20% ❌ |
| File refs ≥50% | 50% | 8% ❌ |
| Concepts ≥70% | 70% | 38% ❌ |
| Hallucinations <3 avg | <3 | 0.7 ✅ |
| Latency <3s on CPU/MPS | <3s | 30s ❌ |

**Additional metrics** we'll measure:
- Compression ratio at each level (light/standard/aggressive)
- Token count before/after (for LLM cost estimation)
- Whether `force_tokens` actually preserved file paths
- Readability of compressed output (manual inspection)

### 3.6 Files Changed

| File | Change |
|------|--------|
| `src/codrag/core/compressor.py` | Add `LinguaCompressor` class |
| `src/codrag/core/__init__.py` | Export `LinguaCompressor` |
| `src/codrag/api/routers/projects.py` | Add `"lingua"` to `_get_compressor()` |
| `scripts/lingua_language_test.py` | NEW — test script against CoDRAG language data |

## 4. Phase 31D Scope: LOD Extraction for Code (Future Sprint)

Separate research document: `docs/Phase31_CLaRa-replacement/LOD_EXTRACTION_RESEARCH.md`

This is a larger effort (2–3 days) that requires:
- Extending the codrag-parser Rust crate to extract at different LOD levels
- Building a Python `LODExtractor` that uses trace graph data to select LOD per file
- Testing on real code output from CoDRAG

## 5. Phase 31E Scope: Dual-Channel Context Assembly (Future Sprint)

Once both compressors are proven:
1. Modify `get_context_structured()` to split results by role
2. Route code chunks → LODExtractor
3. Route language chunks → LinguaCompressor
4. Also search KnowledgeIndex for augmentation/epistemic summaries → LinguaCompressor
5. Load relevant atlas segment descriptions → LinguaCompressor
6. Merge compressed language summary + LOD code chunks into final output
7. Dashboard: compression toggle (none / language-only / dual / aggressive)

## 6. Dependency & Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLMLingua-2 fails quality gates | High | Fall back to NoopCompressor; consider XLM-RoBERTa-Large model |
| Model download too slow for first use | Medium | Show progress in dashboard; model is only 178MB |
| torch dependency conflicts | Medium | llmlingua uses torch; CoDRAG already has optional torch for ONNX |
| MPS acceleration not supported | Low | BERT-base is fast enough on CPU (~50ms) |
| force_tokens not granular enough | Low | Can extend with custom post-processing to protect specific patterns |

## 7. Success Criteria

Phase 31C is successful if:
1. ✅ `LinguaCompressor` passes all 4 quality gates on language content
2. ✅ Latency <3s on CPU for typical CoDRAG context (6K chars)
3. ✅ Zero hallucinations (guaranteed by token pruning architecture)
4. ✅ `force_tokens` preserves file paths and CoDRAG formatting
5. ✅ Compression ratio ≥2× at `standard` level
6. ✅ Drops into existing `_get_compressor()` / `_apply_compression()` pipeline

---

*Plan written: 2026-02-20. Author: Phase 31C implementation planning.*
