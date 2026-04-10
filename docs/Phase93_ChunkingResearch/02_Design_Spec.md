# Phase 93: Semantic Chunking & Contextual Retrieval — Design Spec

**Date:** 2026-04-10
**Status:** Approved
**Catalyst:** [01_Chunking_Research.md](01_Chunking_Research.md) — analysis of garrytan/gbrain's chunking techniques

---

## Scope

Two improvements to CoDRAG's indexing and retrieval quality:

- **P1: Semantic Boundary Detection** — replace dumb `_split_long_text()` with Savitzky-Golay signal processing for oversized markdown sections
- **P2: Contextual Retrieval** — prepend file-level context to chunks before embedding so embeddings carry awareness of where a chunk fits in the broader file

Both are backward-compatible. P1 is purely algorithmic (no LLM). P2 synthesizes context from existing pipeline data (no new LLM calls).

---

## P1: Semantic Boundary Detection for Markdown

### Problem

When a markdown section exceeds `max_chars` (1800), `_split_long_text()` in `src/codrag/core/chunking.py` splits at paragraph boundaries (`\n\n`). If a single paragraph exceeds `max_chars`, it falls through to character-level slicing — breaking mid-sentence and mid-thought.

This produces chunks with poor semantic coherence and degrades embedding quality.

### Solution

Replace `_split_long_text()` with a semantic boundary detector that:
1. Embeds each sentence in the oversized section
2. Finds natural topic boundaries using signal processing on the similarity curve
3. Groups sentences at boundaries into semantically coherent chunks

### Algorithm: Savitzky-Golay Semantic Boundary Detection

```
Input: text (oversized markdown section), max_chars, embedder
Output: list of semantically coherent text chunks

1. SPLIT text into sentences
   - Regex: split on sentence-ending punctuation followed by whitespace
   - Also split on double newlines (paragraph boundaries)
   - Preserve original text for reassembly

2. GUARD: if len(sentences) < 5:
   - Fall back to _split_long_text() (not enough signal for SG filter)

3. EMBED each sentence using the provided embedder (batch call)
   - Returns array of embedding vectors, shape (n_sentences, dim)

4. COMPUTE pairwise cosine similarity between adjacent sentence embeddings
   - similarities[i] = cosine(embed[i], embed[i+1])
   - Result: array of length n_sentences - 1

5. GUARD: if len(similarities) < 5:
   - Fall back to percentile-based splitting (see step 5b)

6. APPLY Savitzky-Golay filter (window=5, polynomial_order=3, derivative_order=1)
   - Smooth the similarity signal and compute its 1st derivative
   - Implementation in src/codrag/core/sg_filter.py

7. FIND zero-crossings (topic boundaries)
   - Where derivative transitions from negative to non-negative
   - = local minima in the similarity curve = topic shifts

8. FILTER boundaries
   - Only keep where raw similarity is below 20th percentile
     (genuine low-similarity boundaries, not just local dips)
   - Enforce minimum distance of 2 between boundaries

9. GROUP sentences at boundaries into chunks

10. POST-PROCESS
    - If any group exceeds max_chars * 1.5: recursively split with _split_long_text()
    - If any group is below min_chars and can merge with neighbor: merge

Step 5b (fallback when < 5 similarities):
   - Mark positions where similarity < 20th percentile as boundaries
   - Group at boundaries, same post-processing as step 10
```

### Integration Point

**File:** `src/codrag/core/chunking.py`

**Change:** `chunk_markdown()` gains an optional `embedder: Optional[Embedder] = None` parameter.

```python
# Current (line 193):
for part in _split_long_text(section_text, max_chars):
    emit(part, section_meta, idx)
    idx += 1

# New:
if embedder is not None:
    parts = _semantic_split(section_text, max_chars, embedder)
else:
    parts = _split_long_text(section_text, max_chars)
for part in parts:
    emit(part, section_meta, idx)
    idx += 1
```

**Callers:** `CodeIndex.build()` in `index.py` line 561 passes the embedder when calling `chunk_markdown()`. No other caller needs to change — Rust chunker and other Python callers continue to work without an embedder.

### New File: `src/codrag/core/sg_filter.py`

Standalone Savitzky-Golay filter implementation. Pure numpy, no external dependencies.

```python
"""
Savitzky-Golay filter for semantic boundary detection.

Implements the SG filter from scratch using Vandermonde matrices.
Used to smooth similarity signals and compute derivatives for
finding topic boundaries in text.
"""

def savitzky_golay_derivative(
    signal: np.ndarray,
    window: int = 5,
    poly_order: int = 3,
    deriv_order: int = 1,
) -> np.ndarray:
    """Apply SG filter and return the nth derivative of the signal."""
    ...

def find_boundaries(
    similarities: np.ndarray,
    percentile_threshold: float = 20.0,
    min_distance: int = 2,
) -> List[int]:
    """Find topic boundaries in a similarity signal using SG filtering."""
    ...
```

~50-60 lines of implementation. The SG filter builds a Vandermonde matrix for the window indices, computes the pseudoinverse via `numpy.linalg.lstsq`, and convolves with the signal. Standard numerical method.

### New Function: `_semantic_split()` in `chunking.py`

```python
def _semantic_split(
    text: str,
    max_chars: int,
    embedder: Embedder,
    min_chars: int = 350,
) -> List[str]:
    """Split oversized text at semantic boundaries using embedding similarity."""
    ...
```

~60-80 lines. Orchestrates the algorithm above: sentence splitting, embedding, SG boundary detection, grouping, post-processing.

### Scope Boundary

- **In scope:** Markdown sections that exceed `max_chars` after heading-based splitting
- **Out of scope:** Code chunking (tree-sitter / AST-aware splitting is better for code)
- **Out of scope:** Rust chunker changes (bottleneck is embedding latency, not split logic)

---

## P2: Contextual Retrieval

### Problem

Chunks are embedded without awareness of their role in the broader file. A chunk from the middle of `index.py:build()` carries path metadata but the embedding itself doesn't encode "this is part of the build pipeline." Queries about "how does the build pipeline work" may not rank it well.

### Solution: Two-Tier Context Enrichment

#### Tier 1: Fast Sync (No LLM)

**File:** `src/codrag/core/index.py`, method `_format_chunk_for_embedding()` (line 1840)

**Current behavior:** Prepends `Path:`, `Section:`, `Hash:` metadata lines to chunk content before embedding.

**Enhancement:** For multi-chunk files, also prepend the file's META_SYNOPSIS (already computed at line 566-586). This gives the embedding awareness of the file's overall purpose and structure.

```python
def _format_chunk_for_embedding(self, chunk: Chunk, file_hash: str,
                                 file_synopsis: str = "") -> str:
    meta = chunk.metadata
    bits: List[str] = []
    if meta.get("name"):
        bits.append(f"Name: {meta['name']}")
    bits.append(f"Path: {meta.get('source_path', '')}")
    if meta.get("section"):
        bits.append(f"Section: {meta['section']}")
    # NEW: file-level context from synopsis
    if file_synopsis and meta.get("section") != "META_SYNOPSIS":
        bits.append(f"File context: {file_synopsis}")
    bits.append(f"Hash: {file_hash}")
    bits.append("")
    bits.append(chunk.content)
    return "\n".join(bits)
```

**Trade-off:** Adds ~200-500 chars of context prefix to each chunk's embedding input. Well within the 8192-token limit of nomic-embed-text-v1.5. Slightly increases embedding computation but the model capacity is not the bottleneck.

**Caller change:** `CodeIndex.build()` passes `file_synopsis` to `_format_chunk_for_embedding()` when available. The synopsis is already computed for META_SYNOPSIS chunks (line 567) — just needs to be threaded through.

#### Tier 2: Deep Enrichment (Uses Existing Epistemic Data)

**File:** `src/codrag/core/knowledge.py`, in `KnowledgeIndex.build()` document assembly

**Current behavior:** Assembles document content from epistemic entries with `File:`, `Domain:`, `Layer:`, `Summary:` fields.

**Enhancement:** Synthesize a richer contextual prefix from the epistemic metadata that's already available:

```python
context_parts = []
if entry.get("architecture_layer"):
    context_parts.append(f"Architecture: {entry['architecture_layer']} layer")
if entry.get("subsystem"):
    context_parts.append(f"Subsystem: {entry['subsystem']}")
if entry.get("design_patterns"):
    context_parts.append(f"Patterns: {', '.join(entry['design_patterns'])}")
if entry.get("domain_tags"):
    context_parts.append(f"Domains: {', '.join(entry['domain_tags'])}")

context_line = ". ".join(context_parts)
text_parts = [
    f"Context: {context_line}",  # NEW
    f"File: {node_id}",
    f"Summary: {extended_summary}",
]
```

**Key insight:** No new LLM calls. The epistemic data is already computed by Stage 6 (ENRICHMENT). We're just formatting it as a context prefix for the embedding. Zero additional cost.

### Scope Boundary

- **In scope:** Embedding-time context enrichment using existing data
- **Out of scope:** LLM-generated per-chunk context (gbrain/Anthropic style) — the epistemic metadata already provides equivalent information
- **Out of scope:** Query-time context injection (search already has 7-layer boosting)

---

## Files Changed

| File | Change | P1/P2 |
|------|--------|-------|
| `src/codrag/core/sg_filter.py` | **NEW** — Savitzky-Golay filter implementation | P1 |
| `src/codrag/core/chunking.py` | Add `_semantic_split()`, optional `embedder` param to `chunk_markdown()` | P1 |
| `src/codrag/core/index.py` | Pass embedder to `chunk_markdown()`, pass synopsis to `_format_chunk_for_embedding()` | P1+P2 |
| `src/codrag/core/knowledge.py` | Synthesize context prefix from epistemic metadata | P2 |
| `tests/test_sg_filter.py` | **NEW** — SG filter unit tests | P1 |
| `tests/test_semantic_chunking.py` | **NEW** — Semantic split integration tests | P1 |
| `tests/test_contextual_retrieval.py` | **NEW** — Context prefix tests for both tiers | P2 |

### Files NOT Changed

- `engine/crates/codrag-chunking/src/lib.rs` — Rust chunker stays as-is
- `src/codrag/services/pipeline/` — No pipeline stage changes
- `src/codrag/core/embedder.py` — Embedder interface unchanged
- `src/codrag/core/epistemic_enrichment.py` — Enricher unchanged

---

## Testing Strategy

### P1 Unit Tests (`tests/test_sg_filter.py`)

1. **Known signal → expected derivative:** Hand-crafted similarity array, verify SG filter output matches expected derivative values
2. **Known boundaries → detected:** Similarity array with clear dips at positions 5 and 12, verify `find_boundaries()` returns `[5, 12]`
3. **No boundaries → empty:** Flat similarity array, verify no boundaries detected
4. **Short signal fallback:** Array with < 5 values, verify fallback to percentile method
5. **Edge cases:** All-zero signal, all-identical signal, single-element signal

### P1 Integration Tests (`tests/test_semantic_chunking.py`)

1. **Backward compatibility:** `chunk_markdown()` without embedder produces identical output to current behavior
2. **Semantic split quality:** Real markdown text (~3000 chars, multiple topics), verify chunks don't split mid-sentence
3. **Fallback on few sentences:** Text with 3 sentences, verify falls back to `_split_long_text()`
4. **Oversized group handling:** Verify post-processing splits groups that exceed `max_chars * 1.5`

### P2 Unit Tests (`tests/test_contextual_retrieval.py`)

1. **Tier 1 — synopsis prefix:** `_format_chunk_for_embedding()` with `file_synopsis` → prefix present in output
2. **Tier 1 — no synopsis:** `_format_chunk_for_embedding()` without synopsis → identical to current behavior
3. **Tier 1 — META_SYNOPSIS excluded:** Synopsis not prepended to META_SYNOPSIS chunks (avoid circular self-reference)
4. **Tier 2 — epistemic context:** KnowledgeIndex document assembly with epistemic data → context prefix in document content
5. **Tier 2 — missing fields graceful:** Epistemic entry with missing `subsystem`/`design_patterns` → context still generated from available fields

### Manual Evaluation

Before/after comparison on representative queries:
- "how does the build pipeline work"
- "what handles embedding generation"
- "where is trace expansion configured"
- "how does the scheduler decide what to run"
- ~6 more domain-specific queries

Compare top-5 results with and without contextual retrieval. Not automated scoring — manual spot-check for ranking improvement.

---

## Dependencies

- **numpy** — already a dependency, used for SG filter math
- **Embedder interface** — already exists, no changes needed
- No new external dependencies

---

## Rollout

Both features are backward-compatible and opt-in:

1. **P1** activates when `embedder` is passed to `chunk_markdown()`. Current callers that don't pass it get identical behavior.
2. **P2 Tier 1** activates when `file_synopsis` is available. Files with single chunks (no synopsis) are unaffected.
3. **P2 Tier 2** activates when epistemic data includes the relevant fields. Missing fields are gracefully skipped.

No feature flags needed. No migration needed. Re-indexing is required to benefit from the changes (same as any embedding-affecting change).
