# Phase 93: Semantic Chunking & Contextual Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve CoDRAG's chunking quality for oversized markdown sections (P1) and add file-level context to chunk embeddings (P2) so search retrieval is more semantically accurate.

**Architecture:** P1 adds a Savitzky-Golay signal processing layer to `_split_long_text()` that detects natural topic boundaries via embedding similarity. P2 threads file synopsis context into `_format_chunk_for_embedding()` (Tier 1, fast sync) and synthesizes epistemic context prefixes in `KnowledgeIndex.build()` (Tier 2, deep enrichment). Both features are backward-compatible and opt-in.

**Tech Stack:** Python, numpy (SG filter math), existing `Embedder` ABC (for sentence-level embedding in P1), existing `KnowledgeIndex` (for P2 Tier 2).

**Spec:** `docs/Phase93_ChunkingResearch/02_Design_Spec.md`

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `src/codrag/core/sg_filter.py` | Savitzky-Golay filter + boundary detection (pure numpy) | **Create** |
| `src/codrag/core/chunking.py` | Add `_semantic_split()`, optional embedder param to `chunk_markdown()` | **Modify** |
| `src/codrag/core/index.py` | Pass embedder to `chunk_markdown()`, pass synopsis to `_format_chunk_for_embedding()` | **Modify** |
| `src/codrag/core/knowledge.py` | Synthesize context prefix from epistemic metadata | **Modify** |
| `tests/test_sg_filter.py` | SG filter unit tests | **Create** |
| `tests/test_semantic_chunking.py` | Semantic split + `chunk_markdown` integration tests | **Create** |
| `tests/test_contextual_retrieval.py` | Context prefix tests for both P2 tiers | **Create** |

---

## Task 1: Savitzky-Golay Filter (P1 foundation)

**Files:**
- Create: `src/codrag/core/sg_filter.py`
- Create: `tests/test_sg_filter.py`

- [ ] **Step 1: Write the failing tests for the SG filter**

Create `tests/test_sg_filter.py`:

```python
"""Tests for Savitzky-Golay filter and boundary detection."""

from __future__ import annotations

import numpy as np
import pytest

from codrag.core.sg_filter import savitzky_golay_derivative, find_boundaries


class TestSavitzkyGolayDerivative:
    """Tests for the SG filter derivative computation."""

    def test_constant_signal_zero_derivative(self):
        """A flat signal should have zero derivative everywhere."""
        signal = np.array([0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8], dtype=np.float64)
        deriv = savitzky_golay_derivative(signal, window=5, poly_order=3, deriv_order=1)
        assert deriv.shape == signal.shape
        np.testing.assert_allclose(deriv, 0.0, atol=1e-10)

    def test_linear_signal_constant_derivative(self):
        """A linear signal should have constant first derivative."""
        signal = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], dtype=np.float64)
        deriv = savitzky_golay_derivative(signal, window=5, poly_order=3, deriv_order=1)
        # Interior points should have derivative ~1.0
        np.testing.assert_allclose(deriv[2:-2], 1.0, atol=1e-10)

    def test_output_shape_matches_input(self):
        """Output array should have the same shape as input."""
        signal = np.random.rand(20)
        deriv = savitzky_golay_derivative(signal, window=5, poly_order=3, deriv_order=1)
        assert deriv.shape == signal.shape

    def test_short_signal_raises(self):
        """Signal shorter than window should raise ValueError."""
        signal = np.array([0.5, 0.6, 0.7])
        with pytest.raises(ValueError, match="Signal length"):
            savitzky_golay_derivative(signal, window=5, poly_order=3, deriv_order=1)


class TestFindBoundaries:
    """Tests for topic boundary detection."""

    def test_clear_dips_detected(self):
        """Obvious similarity dips should be detected as boundaries."""
        # High similarity with clear drops at positions 4 and 9
        similarities = np.array([
            0.9, 0.85, 0.88, 0.87,  # coherent block 1
            0.3,                      # dip = boundary
            0.9, 0.88, 0.86, 0.89,  # coherent block 2
            0.25,                     # dip = boundary
            0.91, 0.87, 0.90,       # coherent block 3
        ], dtype=np.float64)
        bounds = find_boundaries(similarities, percentile_threshold=20.0, min_distance=2)
        # Should detect boundaries near positions 4 and 9
        assert len(bounds) >= 2
        assert any(3 <= b <= 5 for b in bounds), f"Expected boundary near 4, got {bounds}"
        assert any(8 <= b <= 10 for b in bounds), f"Expected boundary near 9, got {bounds}"

    def test_flat_signal_no_boundaries(self):
        """A flat similarity signal should produce no boundaries."""
        similarities = np.array([0.85, 0.86, 0.84, 0.85, 0.86, 0.85, 0.84], dtype=np.float64)
        bounds = find_boundaries(similarities, percentile_threshold=20.0, min_distance=2)
        assert len(bounds) == 0

    def test_min_distance_enforced(self):
        """Boundaries closer than min_distance should be filtered."""
        # Two dips right next to each other
        similarities = np.array([
            0.9, 0.9, 0.2, 0.2, 0.9, 0.9, 0.9, 0.9,
        ], dtype=np.float64)
        bounds = find_boundaries(similarities, percentile_threshold=30.0, min_distance=2)
        # Should only keep one of the two adjacent dips
        assert len(bounds) <= 1

    def test_short_signal_uses_percentile_fallback(self):
        """Signals with < 5 values should use percentile-only method."""
        similarities = np.array([0.9, 0.3, 0.9], dtype=np.float64)
        bounds = find_boundaries(similarities, percentile_threshold=30.0, min_distance=1)
        # Should find the dip at position 1
        assert 1 in bounds

    def test_empty_signal_returns_empty(self):
        """Empty similarity array should return no boundaries."""
        bounds = find_boundaries(np.array([], dtype=np.float64))
        assert bounds == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sg_filter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'codrag.core.sg_filter'`

- [ ] **Step 3: Implement the SG filter**

Create `src/codrag/core/sg_filter.py`:

```python
"""
Savitzky-Golay filter for semantic boundary detection.

Implements the SG filter using Vandermonde matrices and least-squares.
Used to smooth similarity signals and compute derivatives for
finding topic boundaries in text.
"""

from __future__ import annotations

from typing import List

import numpy as np


def savitzky_golay_derivative(
    signal: np.ndarray,
    window: int = 5,
    poly_order: int = 3,
    deriv_order: int = 1,
) -> np.ndarray:
    """Apply Savitzky-Golay filter and return the nth derivative of the signal.

    Args:
        signal: 1D input signal array.
        window: Filter window size (must be odd, >= poly_order + 1).
        poly_order: Polynomial order for local fitting.
        deriv_order: Derivative order (0 = smoothing, 1 = first derivative).

    Returns:
        Filtered/differentiated signal of same shape as input.

    Raises:
        ValueError: If signal is shorter than window or parameters are invalid.
    """
    if len(signal) < window:
        raise ValueError(
            f"Signal length ({len(signal)}) must be >= window ({window})"
        )
    if window % 2 == 0:
        raise ValueError("Window must be odd")
    if poly_order >= window:
        raise ValueError("poly_order must be < window")

    half = window // 2
    # Build Vandermonde matrix for indices [-half, ..., 0, ..., half]
    indices = np.arange(-half, half + 1, dtype=np.float64)
    # Each row is [1, i, i^2, ..., i^poly_order]
    vander = np.vander(indices, N=poly_order + 1, increasing=True)

    # Least-squares solution: coeffs = (V^T V)^{-1} V^T
    # The deriv_order'th row of this matrix gives the convolution kernel
    coeffs = np.linalg.lstsq(vander, np.eye(window), rcond=None)[0]
    # The derivative filter is the deriv_order'th row, scaled by deriv_order!
    import math
    kernel = coeffs[deriv_order] * math.factorial(deriv_order)

    # Convolve with the signal (mode='same' preserves length)
    result = np.convolve(signal, kernel[::-1], mode="same")
    return result


def find_boundaries(
    similarities: np.ndarray,
    percentile_threshold: float = 20.0,
    min_distance: int = 2,
) -> List[int]:
    """Find topic boundaries in a similarity signal.

    Uses Savitzky-Golay filtering to find zero-crossings of the first
    derivative (local minima in similarity = topic shifts), filtered by
    a percentile threshold on raw similarity values.

    For short signals (< 5 values), falls back to simple percentile-based
    boundary detection.

    Args:
        similarities: Array of pairwise cosine similarities between adjacent items.
        percentile_threshold: Only keep boundaries where raw similarity
            is below this percentile (default 20th = genuinely low).
        min_distance: Minimum gap between boundaries.

    Returns:
        Sorted list of boundary indices.
    """
    if len(similarities) == 0:
        return []

    threshold = float(np.percentile(similarities, percentile_threshold))

    # Short signal: simple percentile fallback (not enough data for SG filter)
    if len(similarities) < 5:
        bounds = [i for i in range(len(similarities)) if similarities[i] <= threshold]
        return _enforce_min_distance(bounds, min_distance)

    # Apply SG filter to get 1st derivative
    try:
        derivative = savitzky_golay_derivative(
            similarities, window=5, poly_order=3, deriv_order=1
        )
    except (ValueError, np.linalg.LinAlgError):
        # Fallback if SG filter fails
        bounds = [i for i in range(len(similarities)) if similarities[i] <= threshold]
        return _enforce_min_distance(bounds, min_distance)

    # Find zero-crossings: negative -> non-negative = local minima
    minima = []
    for i in range(1, len(derivative)):
        if derivative[i - 1] < 0 and derivative[i] >= 0:
            minima.append(i)

    # Filter: only keep where raw similarity is below percentile threshold
    bounds = [m for m in minima if m < len(similarities) and similarities[m] <= threshold]
    return _enforce_min_distance(bounds, min_distance)


def _enforce_min_distance(bounds: List[int], min_distance: int) -> List[int]:
    """Filter boundaries to enforce minimum distance between them."""
    if not bounds or min_distance <= 0:
        return bounds
    filtered = [bounds[0]]
    for b in bounds[1:]:
        if b - filtered[-1] >= min_distance:
            filtered.append(b)
    return filtered
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_sg_filter.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/sg_filter.py tests/test_sg_filter.py
git commit -m "feat(P1): add Savitzky-Golay filter for semantic boundary detection

Phase 93 P1 foundation. Pure numpy implementation of the SG filter with
zero-crossing boundary detection and percentile-based filtering.
Includes fallback for short signals."
```

---

## Task 2: Semantic Split Function (P1 core)

**Files:**
- Modify: `src/codrag/core/chunking.py`
- Create: `tests/test_semantic_chunking.py`

- [ ] **Step 1: Write the failing tests for `_semantic_split`**

Create `tests/test_semantic_chunking.py`:

```python
"""Tests for semantic markdown chunking (Phase 93 P1)."""

from __future__ import annotations

import pytest

from codrag.core.chunking import chunk_markdown, _split_long_text
from codrag.core.embedder import FakeEmbedder


class TestSemanticSplitBackwardCompat:
    """chunk_markdown without embedder must produce identical output to before."""

    def test_no_embedder_unchanged(self):
        """Without embedder, oversized sections split at paragraph boundaries."""
        text = "# Title\n\n" + "First paragraph. " * 60 + "\n\n" + "Second paragraph. " * 60
        chunks_without = chunk_markdown(text, source_path="test.md", max_chars=500)
        # Should work without embedder
        assert len(chunks_without) >= 2
        for ch in chunks_without:
            assert len(ch.content) <= 500 * 1.5  # paragraph merging can slightly exceed

    def test_small_section_not_affected(self):
        """Sections within max_chars are never semantically split."""
        text = "# Title\n\nShort section content."
        chunks = chunk_markdown(text, source_path="test.md", embedder=FakeEmbedder())
        assert len(chunks) == 1


class TestSemanticSplitWithEmbedder:
    """Semantic splitting when embedder is provided."""

    def test_oversized_section_split_semantically(self):
        """An oversized section should be split into multiple chunks."""
        # Build a long section with two distinct topics
        topic1 = "Machine learning models are trained on large datasets. " * 15
        topic2 = "Database indexing improves query performance significantly. " * 15
        text = f"# Research\n\n{topic1}\n\n{topic2}"

        embedder = FakeEmbedder(dim=384)
        chunks = chunk_markdown(text, source_path="test.md", max_chars=800, embedder=embedder)
        assert len(chunks) >= 2
        # Each chunk should be non-empty
        for ch in chunks:
            assert len(ch.content.strip()) > 0

    def test_few_sentences_falls_back(self):
        """With fewer than 5 sentences, should fall back to paragraph splitting."""
        text = "# Title\n\n" + "Very long sentence one. " * 40 + "Short two. Short three."
        embedder = FakeEmbedder(dim=384)
        chunks = chunk_markdown(text, source_path="test.md", max_chars=500, embedder=embedder)
        # Should still produce chunks (fallback works)
        assert len(chunks) >= 1

    def test_chunk_metadata_preserved(self):
        """Chunks from semantic split should still carry correct metadata."""
        topic1 = "First topic about network protocols. " * 20
        topic2 = "Second topic about compiler design. " * 20
        text = f"# Deep Dive\n\n{topic1}\n\n{topic2}"

        embedder = FakeEmbedder(dim=384)
        chunks = chunk_markdown(text, source_path="doc.md", max_chars=600, embedder=embedder)
        for ch in chunks:
            assert ch.metadata["source_path"] == "doc.md"
            assert "section" in ch.metadata
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_semantic_chunking.py -v`
Expected: FAIL — `chunk_markdown() got an unexpected keyword argument 'embedder'`

- [ ] **Step 3: Implement `_semantic_split` and update `chunk_markdown`**

Add to `src/codrag/core/chunking.py`. First, add the import at the top of the file:

```python
# Add after existing imports (line 11):
from typing import Any, Dict, Generator, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .embedder import Embedder
```

Add the `_semantic_split` function after `_split_long_text` (after line 104):

```python
def _split_sentences(text: str) -> List[str]:
    """Split text into sentences at punctuation and paragraph boundaries."""
    # First split on paragraph boundaries
    paragraphs = re.split(r"\n\n+", text)
    sentences: List[str] = []
    for para in paragraphs:
        # Split on sentence-ending punctuation followed by space
        parts = re.split(r"(?<=[.!?])\s+", para.strip())
        sentences.extend(p.strip() for p in parts if p.strip())
    return sentences


def _semantic_split(
    text: str,
    max_chars: int,
    embedder: "Embedder",
    min_chars: int = 350,
) -> List[str]:
    """Split oversized text at semantic boundaries using embedding similarity.

    Uses the Savitzky-Golay filter to find natural topic boundaries in
    the embedding similarity curve between adjacent sentences.

    Falls back to _split_long_text() when there aren't enough sentences
    for meaningful signal processing (< 5 sentences).

    Args:
        text: Oversized text to split.
        max_chars: Target maximum chunk size.
        embedder: Embedder instance for sentence-level embedding.
        min_chars: Minimum chunk size for merging small groups.

    Returns:
        List of text chunks split at semantic boundaries.
    """
    import numpy as np
    from .sg_filter import find_boundaries

    sentences = _split_sentences(text)

    # Guard: not enough sentences for semantic analysis
    if len(sentences) < 5:
        return _split_long_text(text, max_chars)

    # Embed all sentences in one batch call
    results = embedder.embed_batch(sentences)
    vectors = np.array([r.vector for r in results], dtype=np.float32)

    # Compute cosine similarities between adjacent sentences
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-8, norms)
    normed = vectors / norms

    similarities = np.array([
        float(np.dot(normed[i], normed[i + 1]))
        for i in range(len(normed) - 1)
    ], dtype=np.float64)

    # Find topic boundaries
    boundaries = find_boundaries(similarities, percentile_threshold=20.0, min_distance=2)

    if not boundaries:
        return _split_long_text(text, max_chars)

    # Group sentences at boundaries
    groups: List[List[str]] = []
    prev = 0
    for b in boundaries:
        # Boundary index is in the similarities array (between sentence b and b+1)
        # So we split: sentences[prev:b+1] and sentences[b+1:]
        group = sentences[prev:b + 1]
        if group:
            groups.append(group)
        prev = b + 1
    # Remaining sentences
    if prev < len(sentences):
        groups.append(sentences[prev:])

    # Merge small groups with neighbors
    merged: List[str] = []
    pending = ""
    for group in groups:
        chunk_text = " ".join(group)
        if pending:
            candidate = pending + " " + chunk_text
            if len(candidate) <= max_chars:
                pending = candidate
                continue
            else:
                merged.append(pending)
                pending = ""

        if len(chunk_text) < min_chars:
            pending = chunk_text
        else:
            merged.append(chunk_text)

    if pending:
        if merged and len(merged[-1]) + len(pending) + 1 <= max_chars:
            merged[-1] = merged[-1] + " " + pending
        else:
            merged.append(pending)

    # Post-process: recursively split any oversized chunks
    final: List[str] = []
    for chunk in merged:
        if len(chunk) > int(max_chars * 1.5):
            final.extend(_split_long_text(chunk, max_chars))
        else:
            final.append(chunk)

    return final if final else _split_long_text(text, max_chars)
```

Update `chunk_markdown` signature and the oversized section handling. Change the function signature (line 107):

```python
def chunk_markdown(
    text: str,
    source_path: str,
    xref_id: Optional[str] = None,
    name: Optional[str] = None,
    max_chars: int = 1800,
    min_chars: int = 350,
    embedder: Optional["Embedder"] = None,
) -> List[Chunk]:
```

Replace the oversized section loop (line 192-195):

```python
        # Old:
        # for part in _split_long_text(section_text, max_chars):
        #     emit(part, section_meta, idx)
        #     idx += 1

        # New:
        if embedder is not None:
            parts = _semantic_split(section_text, max_chars, embedder, min_chars)
        else:
            parts = _split_long_text(section_text, max_chars)
        for part in parts:
            emit(part, section_meta, idx)
            idx += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_semantic_chunking.py tests/test_sg_filter.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/chunking.py tests/test_semantic_chunking.py
git commit -m "feat(P1): add semantic boundary detection for oversized markdown sections

chunk_markdown() now accepts an optional embedder param. When provided,
oversized sections are split at topic boundaries detected via SG filter
on sentence embedding similarities. Falls back to paragraph splitting
when embedder is None or fewer than 5 sentences."
```

---

## Task 3: Wire P1 Into the Build Pipeline

**Files:**
- Modify: `src/codrag/core/index.py:560-563`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_semantic_chunking.py`:

```python
class TestBuildPipelineIntegration:
    """Verify that CodeIndex.build() passes embedder to chunk_markdown."""

    def test_chunk_markdown_receives_embedder(self, monkeypatch):
        """build() should pass self.embedder to chunk_markdown for .md files."""
        captured_kwargs = {}

        original_chunk_markdown = chunk_markdown

        def spy_chunk_markdown(*args, **kwargs):
            captured_kwargs.update(kwargs)
            # Call without embedder to avoid actual embedding in test
            kwargs.pop("embedder", None)
            return original_chunk_markdown(*args, **kwargs)

        monkeypatch.setattr("codrag.core.index.chunk_markdown", spy_chunk_markdown)

        from codrag.core.index import CodeIndex
        from codrag.core.embedder import FakeEmbedder
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            index_dir = Path(tmpdir) / "index"
            index_dir.mkdir()
            repo_dir = Path(tmpdir) / "repo"
            repo_dir.mkdir()
            # Create a markdown file large enough to trigger splitting
            md_file = repo_dir / "big.md"
            md_file.write_text("# Title\n\n" + "Content paragraph. " * 200)

            idx = CodeIndex(index_dir=index_dir, embedder=FakeEmbedder())
            idx.build(repo_root=repo_dir, include_globs=["**/*.md"])

            assert "embedder" in captured_kwargs
            assert captured_kwargs["embedder"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_semantic_chunking.py::TestBuildPipelineIntegration -v`
Expected: FAIL — `assert "embedder" in captured_kwargs`

- [ ] **Step 3: Pass embedder to chunk_markdown in build()**

In `src/codrag/core/index.py`, modify line 561:

```python
            # Old (line 560-561):
            if file_path.suffix.lower() in (".md", ".markdown"):
                chunks = chunk_markdown(raw, source_path=rel_path)

            # New:
            if file_path.suffix.lower() in (".md", ".markdown"):
                chunks = chunk_markdown(raw, source_path=rel_path, embedder=self.embedder)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_semantic_chunking.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/codrag/core/index.py
git commit -m "feat(P1): wire semantic chunking into CodeIndex.build()

build() now passes self.embedder to chunk_markdown() for markdown files,
enabling SG-based semantic boundary detection for oversized sections."
```

---

## Task 4: Contextual Retrieval Tier 1 — Synopsis Prefix (P2)

**Files:**
- Modify: `src/codrag/core/index.py:1840-1852` and `594-596`
- Create: `tests/test_contextual_retrieval.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_contextual_retrieval.py`:

```python
"""Tests for contextual retrieval (Phase 93 P2)."""

from __future__ import annotations

from codrag.core.chunking import Chunk
from codrag.core.index import CodeIndex
from codrag.core.embedder import FakeEmbedder


class TestTier1SynopsisPrefix:
    """P2 Tier 1: file synopsis prepended to chunk embedding text."""

    def test_synopsis_included_in_embedding_text(self):
        """When file_synopsis is provided, it appears in the formatted text."""
        idx = CodeIndex.__new__(CodeIndex)  # avoid __init__ side effects
        chunk = Chunk(
            chunk_id="abc123",
            content="for ch in chunks: text = self._format(ch)",
            metadata={"source_path": "src/codrag/core/index.py", "section": "build"},
        )
        result = idx._format_chunk_for_embedding(
            chunk, file_hash="deadbeef",
            file_synopsis="File: src/codrag/core/index.py\nPurpose: Core search index\nClasses: CodeIndex"
        )
        assert "File context:" in result
        assert "Core search index" in result
        assert "for ch in chunks" in result

    def test_no_synopsis_unchanged(self):
        """Without file_synopsis, output is identical to previous behavior."""
        idx = CodeIndex.__new__(CodeIndex)
        chunk = Chunk(
            chunk_id="abc123",
            content="some code here",
            metadata={"source_path": "foo.py", "section": ""},
        )
        result_without = idx._format_chunk_for_embedding(chunk, file_hash="deadbeef")
        result_empty = idx._format_chunk_for_embedding(chunk, file_hash="deadbeef", file_synopsis="")
        assert result_without == result_empty
        assert "File context:" not in result_without

    def test_meta_synopsis_chunk_excluded(self):
        """META_SYNOPSIS chunks should NOT get the synopsis prefix (circular)."""
        idx = CodeIndex.__new__(CodeIndex)
        chunk = Chunk(
            chunk_id="abc123",
            content="File: index.py\nPurpose: search",
            metadata={"source_path": "index.py", "section": "META_SYNOPSIS"},
        )
        result = idx._format_chunk_for_embedding(
            chunk, file_hash="deadbeef",
            file_synopsis="File: index.py\nPurpose: search"
        )
        assert "File context:" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_contextual_retrieval.py::TestTier1SynopsisPrefix -v`
Expected: FAIL — `TypeError: _format_chunk_for_embedding() got an unexpected keyword argument 'file_synopsis'`

- [ ] **Step 3: Add file_synopsis parameter to `_format_chunk_for_embedding`**

In `src/codrag/core/index.py`, modify the method at line 1840:

```python
    def _format_chunk_for_embedding(self, chunk: Chunk, file_hash: str,
                                     file_synopsis: str = "") -> str:
        """Format a chunk for embedding, optionally with file-level context."""
        meta = chunk.metadata
        bits: List[str] = []
        if meta.get("name"):
            bits.append(f"Name: {meta['name']}")
        bits.append(f"Path: {meta.get('source_path', '')}")
        if meta.get("section"):
            bits.append(f"Section: {meta['section']}")
        # P2 Tier 1: prepend file synopsis for contextual awareness
        if file_synopsis and meta.get("section") != "META_SYNOPSIS":
            bits.append(f"File context: {file_synopsis}")
        bits.append(f"Hash: {file_hash}")
        bits.append("")
        bits.append(chunk.content)
        return "\n".join(bits)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_contextual_retrieval.py::TestTier1SynopsisPrefix -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Thread synopsis through the build loop**

In `src/codrag/core/index.py`, modify the build loop. The synopsis is already computed at line 567. Thread it to the chunk embedding loop.

Change the block starting at line 565:

```python
            # Phase 73: Inject meta-chunk for multi-chunk files.
            file_synopsis = ""
            if len(chunks) > 1:
                synopsis = extract_file_synopsis(raw, rel_path)
                file_synopsis = synopsis  # Save for Tier 1 context
                meta_chunk_id = stable_file_hash(rel_path + ":meta_synopsis")
                meta_text = self._format_chunk_for_embedding(
                    Chunk(
                        chunk_id=meta_chunk_id,
                        content=synopsis,
                        metadata={"source_path": rel_path, "section": "META_SYNOPSIS"},
                    ),
                    file_hash,
                )
                meta_emb = self.embedder.embed(meta_text).vector
                docs.append({
                    "id": meta_chunk_id,
                    "source_path": rel_path,
                    "file_hash": file_hash,
                    "role": role,
                    "section": "META_SYNOPSIS",
                    "span": None,
                    "content": synopsis,
                })
                vectors.append(meta_emb)
                chunks_embedded += 1
                if is_doc:
                    chunks_docs += 1
                else:
                    chunks_code += 1

            for ch in chunks:
                text_for_embed = self._format_chunk_for_embedding(
                    ch, file_hash, file_synopsis=file_synopsis
                )
                emb = self.embedder.embed(text_for_embed).vector
```

- [ ] **Step 6: Run full test suite for regressions**

Run: `.venv/bin/pytest tests/test_contextual_retrieval.py tests/test_semantic_chunking.py tests/test_sg_filter.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/codrag/core/index.py tests/test_contextual_retrieval.py
git commit -m "feat(P2): add Tier 1 contextual retrieval — synopsis prefix in embeddings

_format_chunk_for_embedding() now accepts file_synopsis param. For
multi-chunk files, the file synopsis is prepended to each chunk's
embedding text, giving the embedding awareness of the file's overall
purpose. META_SYNOPSIS chunks are excluded to avoid circular reference."
```

---

## Task 5: Contextual Retrieval Tier 2 — Epistemic Context (P2)

**Files:**
- Modify: `src/codrag/core/knowledge.py:315-346`
- Add to: `tests/test_contextual_retrieval.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_contextual_retrieval.py`:

```python
import json
import tempfile
from pathlib import Path


class TestTier2EpistemicContext:
    """P2 Tier 2: epistemic metadata synthesized as context prefix."""

    def _make_epistemic_file(self, tmpdir: Path, entries: list) -> Path:
        """Helper: write a trace_epistemic.jsonl file."""
        path = tmpdir / "trace_epistemic.jsonl"
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return path

    def _make_augmented_file(self, tmpdir: Path, entries: list) -> Path:
        """Helper: write a trace_augmented.jsonl file."""
        path = tmpdir / "trace_augmented.jsonl"
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return path

    def test_epistemic_context_in_document_content(self):
        """Epistemic docs should include synthesized context prefix."""
        from codrag.core.knowledge import KnowledgeIndex
        from codrag.core.embedder import FakeEmbedder

        with tempfile.TemporaryDirectory() as tmpdir:
            idx_dir = Path(tmpdir)
            self._make_augmented_file(idx_dir, [
                {"node_id": "src/foo.py", "summary": "Handles requests", "role": "handler"},
            ])
            self._make_epistemic_file(idx_dir, [
                {
                    "node_id": "src/foo.py",
                    "extended_summary": "Request handler for the API gateway",
                    "domain_tags": ["api", "networking"],
                    "architecture_layer": "presentation",
                    "subsystem": "gateway",
                    "design_patterns": ["adapter", "facade"],
                },
            ])

            ki = KnowledgeIndex(index_dir=idx_dir, embedder=FakeEmbedder())
            result = ki.build()

            assert result["count"] > 0
            # Find the epistemic doc
            ep_docs = [d for d in ki._documents if d["type"] == "epistemic"]
            assert len(ep_docs) == 1
            content = ep_docs[0]["content"]
            assert "presentation" in content.lower() or "Architecture" in content
            assert "gateway" in content.lower() or "Subsystem" in content
            assert "adapter" in content.lower() or "Patterns" in content

    def test_missing_fields_graceful(self):
        """Epistemic entry with missing optional fields should still work."""
        from codrag.core.knowledge import KnowledgeIndex
        from codrag.core.embedder import FakeEmbedder

        with tempfile.TemporaryDirectory() as tmpdir:
            idx_dir = Path(tmpdir)
            self._make_augmented_file(idx_dir, [
                {"node_id": "src/bar.py", "summary": "Utility functions", "role": "util"},
            ])
            self._make_epistemic_file(idx_dir, [
                {
                    "node_id": "src/bar.py",
                    "extended_summary": "Collection of utility functions",
                    "domain_tags": ["utilities"],
                    "architecture_layer": "infrastructure",
                    # No subsystem, no design_patterns
                },
            ])

            ki = KnowledgeIndex(index_dir=idx_dir, embedder=FakeEmbedder())
            result = ki.build()

            ep_docs = [d for d in ki._documents if d["type"] == "epistemic"]
            assert len(ep_docs) == 1
            content = ep_docs[0]["content"]
            # Should still have the layer context
            assert "infrastructure" in content.lower() or "Architecture" in content
            # Should not crash on missing fields
            assert "None" not in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_contextual_retrieval.py::TestTier2EpistemicContext -v`
Expected: FAIL — assertions about "presentation"/"gateway"/"adapter" in content will fail because current code doesn't include subsystem/patterns

- [ ] **Step 3: Add context prefix to epistemic document assembly**

In `src/codrag/core/knowledge.py`, replace the epistemic text_parts block (lines 329-334):

```python
                            # Synthesize contextual prefix from epistemic metadata
                            context_parts = []
                            layer = entry.get("architecture_layer")
                            if layer and layer != "unknown":
                                context_parts.append(f"Architecture: {layer} layer")
                            subsystem = entry.get("subsystem")
                            if subsystem:
                                context_parts.append(f"Subsystem: {subsystem}")
                            patterns = entry.get("design_patterns")
                            if patterns:
                                context_parts.append(f"Patterns: {', '.join(patterns)}")

                            # Construct rich text representation for embedding
                            text_parts = []
                            if context_parts:
                                text_parts.append(f"Context: {'. '.join(context_parts)}")
                            text_parts.extend([
                                f"File: {node_id}",
                                f"Domain: {', '.join(entry.get('domain_tags', []))}",
                                f"Layer: {entry.get('architecture_layer', 'unknown')}",
                                f"Summary: {summary}"
                            ])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_contextual_retrieval.py -v`
Expected: All 5 tests PASS (3 Tier 1 + 2 Tier 2)

- [ ] **Step 5: Run full test suite for regressions**

Run: `.venv/bin/pytest tests/test_sg_filter.py tests/test_semantic_chunking.py tests/test_contextual_retrieval.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/codrag/core/knowledge.py tests/test_contextual_retrieval.py
git commit -m "feat(P2): add Tier 2 contextual retrieval — epistemic context prefix

KnowledgeIndex.build() now synthesizes a context prefix from existing
epistemic metadata (architecture layer, subsystem, design patterns)
and prepends it to document content before embedding. Zero additional
LLM calls — uses data already produced by the enrichment pipeline."
```

---

## Task 6: Broader Regression Testing

**Files:**
- No new files — run existing test suite

- [ ] **Step 1: Run all existing chunking-adjacent tests**

Run: `.venv/bin/pytest tests/test_incremental_rebuild.py tests/test_manifest_ids.py tests/test_adaptive_k.py tests/test_mmr_diversity.py tests/test_knowledge_surrogate.py -v`
Expected: All PASS (no regressions from our changes)

- [ ] **Step 2: Run the new Phase 93 tests together**

Run: `.venv/bin/pytest tests/test_sg_filter.py tests/test_semantic_chunking.py tests/test_contextual_retrieval.py -v`
Expected: All PASS

- [ ] **Step 3: Run the full test suite**

Run: `.venv/bin/pytest tests/ -v --timeout=120 -x`
Expected: No new failures. If pre-existing failures exist, they should not be in files we modified.

- [ ] **Step 4: Final commit with any fixups**

If any regressions were found and fixed:
```bash
git add -u
git commit -m "fix: address Phase 93 regressions from broader test suite"
```

If no regressions:
```bash
echo "No regressions found. Phase 93 implementation complete."
```
