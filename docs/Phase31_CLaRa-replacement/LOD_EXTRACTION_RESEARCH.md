# Phase 31D: LOD Code Extraction — Research & Implementation Roadmap

> **Date**: 2026-02-20  
> **Status**: ✅ IMPLEMENTED — see [`LOD_EXTRACTOR_IMPLEMENTATION.md`](./LOD_EXTRACTOR_IMPLEMENTATION.md)  
> **Purpose**: Define the code compression strategy for the dual-compressor architecture. This doc covers the research; the implementation record is in the linked doc above.

---

## 1. The Problem

CoDRAG's code chunks are currently delivered to AI tools at full fidelity — every line of every function body. For large projects this means:
- Top-K results may only cover 3–5 files out of hundreds
- Function bodies are often 80%+ of token budget but only 20% of the signal
- AI tools waste tokens reading implementation details when they need structural understanding

**Goal**: Compress code context by extracting at variable detail levels — full body for highly relevant functions, signatures only for medium relevance, just names for low relevance. This is the **code channel** of the dual-compressor (LLMLingua-2 handles the language channel).

---

## 2. Key Papers & Prior Art

### 2.1 Stingy Context / TREEFRAG (arXiv 2601.19929, Jan 2025)

**The most directly relevant paper.** Introduces hierarchical code compression achieving **18:1 reduction** on real codebases (239K → 11K tokens) while preserving task fidelity.

**Core concept — 7 Levels of Detail (LOD)**:

| LOD | What's Kept | Compression | Use Case |
|-----|------------|-------------|----------|
| 0 | Full source | 1:1 | Top search result |
| 1 | Remove comments | ~1.2:1 | High relevance |
| 2 | Remove function bodies (keep signatures + docstrings) | ~3:1 | Medium relevance |
| 3 | Remove method bodies (keep class structure) | ~5:1 | Lower relevance |
| 4 | Keep only imports + class/function signatures | ~8:1 | Structural context |
| 5 | Keep only file names + top-level exports | ~15:1 | Orientation |
| 6 | Keep only directory tree | ~18:1 | High-level map |

**TREEFRAG algorithm**: Decomposes the codebase into a tree of files/modules. Each node is assigned an LOD level based on relevance to the current task. The tree is then serialized with each file at its assigned LOD.

**Key results**: 94–97% success on 40 real-world issues across 12 frontier LLMs. Outperforms flat methods (chunking, RAG) and mitigates lost-in-the-middle effects.

**Conveyance formats**: The paper explores different serialization formats:
- Markdown (most readable, moderate compression)
- JSON tree (structured, good for programmatic consumption)
- Indented text (compact, good for smaller contexts)

**No public implementation** as of Feb 2025. Paper only.

### 2.2 cAST: Code Retrieval-Augmented Generation with Structural Awareness (CMU, 2025)

Uses tree-sitter ASTs to create **structurally-aware code chunks** that respect syntax boundaries. Key insight: AST-based chunking preserves complete functions/classes instead of splitting mid-statement.

**Relevant to CoDRAG**: We already use tree-sitter via `codrag-parser`. The cAST approach validates that AST-boundary-respecting chunks significantly outperform naive line-based chunking.

### 2.3 LongCodeZip (ASE 2025)

Two-stage code compression:
1. **Coarse-grained**: Function-level ranking by conditional perplexity
2. **Fine-grained**: Entropy-based token pruning within selected functions

Requires a 7B code LLM (too heavy for CoDRAG), but the **function-level ranking concept** is directly applicable using CoDRAG's search scores instead of perplexity.

### 2.4 Repomix (2024–2025)

Popular CLI tool that uses tree-sitter to extract function/class signatures. The `--compress` flag achieves ~70% token reduction. Validates that signature extraction is a practical and proven approach.

### 2.5 Aider's Repo-Map

Creates a "map" of the codebase showing definitions and signatures without implementation bodies. Used in production by thousands of developers. Validates the LOD 4–5 approach at scale.

---

## 3. CoDRAG's Existing Infrastructure

**We already have most of the building blocks.** Here's what exists:

### 3.1 Tree-Sitter Parsing (`engine/crates/codrag-parser/`)

The Rust-based parser already:
- Parses Python, TypeScript, JavaScript, Rust, Go, Ruby, Java, Swift, CSS, HTML
- Extracts **symbol-level nodes**: functions, classes, methods, constants
- Provides **span data**: `start_line`, `end_line` for every symbol
- Identifies **containment edges**: file → class → method hierarchy
- Extracts **import edges**: cross-file dependencies

### 3.2 Trace Graph (`trace_nodes.jsonl` + `trace_edges.jsonl`)

The trace graph already provides:
- Every file as a node with `file_path`, `language`, `line_count`
- Every symbol as a node with `name`, `symbol_type` (function/class/method), `span`
- `contains` edges: file → symbol, class → method
- `imports` edges: file → file, symbol → symbol
- `calls` edges: function → function (where detectable)

### 3.3 Augmentation Data (`trace_augmented.jsonl`)

For every traced file:
- `summary`: 1-sentence description of what the file does
- `role`: classification (core, api, test, handler, utility, etc.)
- `confidence`: how sure the LLM was about the classification
- `related_files`: hypothesized relationships

### 3.4 Search Scores (`CodeIndex.search()`)

Every query produces ranked results with cosine similarity scores. These scores naturally map to LOD levels:
- Score > 0.5 → LOD 0–1 (full source, highly relevant)
- Score 0.3–0.5 → LOD 2 (signatures + docstrings)
- Score 0.15–0.3 → LOD 4 (names + types only)
- Trace neighbors → LOD 4–5 (structural context)

---

## 4. Proposed Implementation: `LODExtractor`

### 4.1 Architecture

```python
class LODExtractor:
    """Extract code at variable Levels of Detail using trace graph data."""

    def extract(
        self,
        file_path: str,
        lod: int,               # 0-6
        trace_data: TraceIndex,  # For symbol spans and hierarchy
        repo_root: Path,
    ) -> str:
        """Extract file content at the specified LOD level."""
```

### 4.2 LOD Levels for CoDRAG

| LOD | Extraction Strategy | What's Produced |
|-----|-------------------|-----------------|
| **0** | Read full file | Complete source (current behavior) |
| **1** | Strip comments (regex or tree-sitter) | Source minus comments |
| **2** | For each function/method: keep signature + docstring, replace body with `...` | Signatures with documentation |
| **3** | For each class: keep class def + method signatures, remove all bodies | Class skeletons |
| **4** | Keep only: imports, class names, function names with type hints | Structural outline |
| **5** | Keep only: file path + list of exported names | File manifest |
| **6** | N/A (handled by atlas) | Directory tree |

### 4.3 Implementation Path

**Step 1: Python prototype using trace graph data** (1 day)
- Read file from disk
- Look up symbol spans from `trace_nodes.jsonl`
- For each symbol, extract at the requested LOD by reading only the relevant line ranges
- Stitch together: imports (always kept) + symbols at LOD level

```python
def extract_lod2(self, file_path: str, trace_data: TraceIndex) -> str:
    """LOD 2: Signatures + docstrings, bodies replaced with ..."""
    source_lines = Path(file_path).read_text().splitlines()

    # Get all symbols in this file from trace graph
    file_node = trace_data.get_file_node(file_path)
    symbols = trace_data.get_contained_symbols(file_node.id)

    # Extract imports (lines before first symbol)
    first_symbol_line = min(s.span.start_line for s in symbols) if symbols else len(source_lines)
    imports = "\n".join(source_lines[:first_symbol_line])

    # For each symbol: keep signature line(s) + docstring, replace body
    parts = [imports]
    for sym in sorted(symbols, key=lambda s: s.span.start_line):
        sig_lines = extract_signature(source_lines, sym)  # def/class line(s)
        docstring = extract_docstring(source_lines, sym)   # triple-quoted string
        parts.append(f"{sig_lines}\n{docstring}\n    ...")

    return "\n\n".join(parts)
```

**Step 2: Score-based LOD assignment** (0.5 day)
- Map search result scores to LOD levels
- Top results (score > 0.5): LOD 0 (full body)
- Mid results (0.3–0.5): LOD 2 (signatures)
- Low results (0.15–0.3): LOD 4 (names only)
- Trace-expanded neighbors: LOD 4–5

**Step 3: Integration with context assembly** (1 day)
- Modify `get_context_structured()` to use LODExtractor for code chunks
- Each code chunk gets its LOD based on search score
- Assemble: LOD 0 chunks first (full detail), then LOD 2 (signatures), then LOD 4 (names)

**Step 4: Rust acceleration** (future, optional)
- Move LOD extraction into `codrag-parser` Rust crate
- Tree-sitter already parses the file; extract at LOD in one pass
- Would reduce latency from ~50ms (Python file reads) to ~5ms (Rust)

### 4.4 Expected Compression

Based on Stingy Context paper results and typical CoDRAG projects:

| LOD | Typical file | Tokens (before) | Tokens (after) | Ratio |
|-----|-------------|-----------------|----------------|-------|
| 0 | Full 200-line Python file | ~600 | ~600 | 1:1 |
| 2 | Same file, signatures only | ~600 | ~150 | 4:1 |
| 4 | Same file, names only | ~600 | ~30 | 20:1 |

For a typical CoDRAG context response (5 chunks):
- Current: 5 × LOD 0 = ~3000 tokens
- With LOD: 2 × LOD 0 + 2 × LOD 2 + 1 × LOD 4 = ~600 + 300 + 30 = ~930 tokens (3.2× compression)
- Freed budget → more files covered

### 4.5 Key Design Decisions

1. **LOD assignment is score-based, not LLM-based**: Unlike LongCodeZip (which uses a 7B model for perplexity ranking), we use CoDRAG's existing search scores. This is free — no extra model needed.

2. **Trace graph provides symbol boundaries**: Unlike Repomix/Aider (which re-parse every time), CoDRAG's trace graph already has all symbol spans pre-computed. Extraction is a file read + line slicing.

3. **LOD 6 is already implemented**: The atlas provides directory-level orientation. LOD extraction handles LOD 0–5.

4. **Augmentation summaries complement LOD 4–5**: When showing only function names (LOD 4), we can append the augmentation summary to explain what the function does. This provides context without source code.

---

## 5. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Symbol spans are stale (file modified since trace) | Garbled extraction | Check file hash against trace manifest; fall back to LOD 0 |
| Languages without good tree-sitter support | No symbol data | Fall back to LOD 0 (full source) — same as current behavior |
| Docstring extraction is language-dependent | Missing docstrings at LOD 2 | Implement per-language docstring extractors (Python, JS/TS, Rust) |
| LOD 2 may break code that's copy-pasted into editor | User confusion | Document that LOD >0 is for AI context, not for humans |

---

## 6. Testing Plan

Reuse the same evaluation framework as the LLMLingua-2 tests:
1. Take CoDRAG's existing code test data (Phase 31A)
2. Extract at each LOD level
3. Measure: function name retention, file path retention, structural accuracy
4. Compare token count vs CLaRa and vs no compression

**Pass criteria**:
- LOD 2: ≥95% function signature retention
- LOD 4: ≥99% function name retention
- LOD 2: ≥3× compression ratio
- Extraction latency: <100ms per file

---

## 7. Relationship to Dual-Compressor Architecture

```
Query arrives
  ├── Code chunks (role=code, tests)
  │     ├── Top results → LOD 0 (full source)     ← LODExtractor
  │     ├── Mid results → LOD 2 (signatures)       ← LODExtractor
  │     └── Trace neighbors → LOD 4 (names)        ← LODExtractor
  │
  └── Language content (role=docs, other, knowledge, atlas)
        └── LLMLingua-2 (light, rate=0.6)          ← LinguaCompressor ✅ DONE
```

LODExtractor is the **code counterpart** to LinguaCompressor. Together they form the dual-compressor that handles all CoDRAG content types.

---

## 8. Implementation Timeline

| Step | Effort | Dependencies |
|------|--------|-------------|
| Python `LODExtractor` prototype | 1 day | TraceIndex API |
| Per-language docstring extractors | 0.5 day | Tree-sitter grammars |
| Score-based LOD assignment | 0.5 day | Search scores |
| Integration with `get_context_structured()` | 1 day | LODExtractor + LinguaCompressor |
| Tests | 0.5 day | Test data from Phase 31A |
| **Total** | **~3.5 days** | |

---

## 9. References

1. **Stingy Context**: Ostby, D.L. "Stingy Context: 18:1 Hierarchical Code Compression for LLM Auto-Coding." arXiv:2601.19929, Jan 2025.
2. **cAST**: Wang et al. "cAST: Enhancing Code Retrieval-Augmented Generation with Structural Awareness." CMU, 2025. arXiv:2506.15655.
3. **LongCodeZip**: Shi et al. "LongCodeZip: Compress Long Context for Code Language Models." ASE 2025. arXiv:2510.00446.
4. **Repomix**: yamadashy. "Repomix: Pack your codebase into AI-friendly formats." github.com/yamadashy/repomix, 2024–2025.
5. **Aider Repo-Map**: gauthier. "Aider: AI pair programming in your terminal." github.com/paul-gauthier/aider, 2024.

---

*Research compiled: 2026-02-20. Ready for Phase 31D implementation pickup.*
