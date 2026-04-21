"""Tests for Wave 2.1+2.2: ranked trace expansion + smart chunk selection.

Verifies that get_context_with_trace_expansion():
  2.1 - Sorts neighbor paths by query relevance (not alphabetically)
  2.2 - Picks the best-matching chunk per file (not the first chunk)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from prep.core.index import CodeIndex, SearchResult
from prep.core.embedder import FakeEmbedder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_index(tmp_path, docs: List[Dict], embeddings: np.ndarray) -> CodeIndex:
    """Build a CodeIndex with pre-loaded documents and embeddings."""
    index_dir = tmp_path / "idx"
    index_dir.mkdir()
    idx = CodeIndex(index_dir=index_dir, embedder=FakeEmbedder(dim=embeddings.shape[1]))
    idx._documents = docs
    idx._embeddings = embeddings
    idx._manifest = {"config": {}}
    return idx


def _make_trace_index(neighbor_paths: List[str]) -> MagicMock:
    """Create a mock TraceIndex that returns given file paths as neighbors."""
    trace_idx = MagicMock()
    trace_idx.is_loaded.return_value = True

    out_nodes = [{"file_path": p, "id": f"node_{i}"} for i, p in enumerate(neighbor_paths)]
    trace_idx.get_neighbors.return_value = {
        "in_nodes": [],
        "out_nodes": out_nodes,
        "in_edges": [],
        "out_edges": [],
    }
    return trace_idx


# ---------------------------------------------------------------------------
# Wave 2.1: Ranked trace expansion (sort by query relevance, not alphabetically)
# ---------------------------------------------------------------------------

class TestRankedTraceExpansion:

    def test_neighbors_sorted_by_relevance_not_alphabetically(self, tmp_path):
        """Neighbors should be ordered by cosine similarity to query, not by filename."""
        # alpha.py → low relevance embedding
        # beta.py  → high relevance embedding
        # Alphabetically alpha comes first, but beta is more relevant.
        dim = 4
        query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        alpha_vec = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)  # orthogonal to query
        beta_vec  = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)  # parallel to query

        docs = [
            {"source_path": "alpha.py", "content": "alpha content", "section": ""},
            {"source_path": "beta.py",  "content": "beta content",  "section": ""},
        ]
        embeddings = np.vstack([alpha_vec, beta_vec])

        idx = _make_index(tmp_path, docs, embeddings)
        trace_idx = _make_trace_index(["alpha.py", "beta.py"])

        # Mock search to return an empty base result from a "source" file
        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "",
                "chunks": [{"source_path": "source.py"}],
                "total_chars": 0,
                "estimated_tokens": 0,
            }
            # Mock embed_query to return our known query vector
            idx.embedder = MagicMock()
            idx.embedder.embed_query.return_value = MagicMock(vector=query_vec.tolist())

            result = idx.get_context_with_trace_expansion(
                query="test query",
                trace_index=trace_idx,
                k=3,
                max_chars=10000,
                max_additional_chars=5000,
            )

        chunks = [c for c in result.get("chunks", []) if c.get("trace_expanded")]
        assert len(chunks) == 2
        # beta.py (higher score) should come before alpha.py
        assert chunks[0]["source_path"] == "beta.py"
        assert chunks[1]["source_path"] == "alpha.py"
        # Scores should be non-increasing
        assert chunks[0]["score"] >= chunks[1]["score"]

    def test_no_embeddings_falls_back_gracefully(self, tmp_path):
        """When embeddings are unavailable, expansion still works (fallback order)."""
        dim = 4
        docs = [
            {"source_path": "z_file.py", "content": "z content", "section": ""},
            {"source_path": "a_file.py", "content": "a content", "section": ""},
        ]
        idx = _make_index(tmp_path, docs, np.zeros((2, dim)))
        idx._embeddings = None  # Force no-embedding fallback

        trace_idx = _make_trace_index(["z_file.py", "a_file.py"])

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "",
                "chunks": [{"source_path": "source.py"}],
                "total_chars": 0,
                "estimated_tokens": 0,
            }
            result = idx.get_context_with_trace_expansion(
                query="test query",
                trace_index=trace_idx,
                k=3,
                max_chars=10000,
                max_additional_chars=5000,
            )

        chunks = [c for c in result.get("chunks", []) if c.get("trace_expanded")]
        assert len(chunks) == 2  # Both files included, no crash

    def test_scores_attached_to_trace_expanded_chunks(self, tmp_path):
        """Trace-expanded chunks should carry a non-zero score when embeddings exist."""
        dim = 4
        query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        rel_vec   = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)

        docs = [{"source_path": "related.py", "content": "related content", "section": ""}]
        embeddings = np.vstack([rel_vec])

        idx = _make_index(tmp_path, docs, embeddings)
        trace_idx = _make_trace_index(["related.py"])

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "",
                "chunks": [{"source_path": "source.py"}],
                "total_chars": 0,
                "estimated_tokens": 0,
            }
            idx.embedder = MagicMock()
            idx.embedder.embed_query.return_value = MagicMock(vector=query_vec.tolist())

            result = idx.get_context_with_trace_expansion(
                query="test query",
                trace_index=trace_idx,
                k=3,
                max_chars=10000,
                max_additional_chars=5000,
            )

        trace_chunks = [c for c in result.get("chunks", []) if c.get("trace_expanded")]
        assert len(trace_chunks) == 1
        assert trace_chunks[0]["score"] > 0.0

    def test_empty_related_paths_returns_base_result(self, tmp_path):
        """When no neighbor paths are found, base result is returned unchanged."""
        dim = 4
        docs = [{"source_path": "src.py", "content": "content", "section": ""}]
        idx = _make_index(tmp_path, docs, np.random.rand(1, dim).astype(np.float32))
        trace_idx = _make_trace_index([])  # No neighbors

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "base context",
                "chunks": [{"source_path": "src.py"}],
                "total_chars": 12,
                "estimated_tokens": 3,
            }
            result = idx.get_context_with_trace_expansion(
                query="test",
                trace_index=trace_idx,
            )

        assert result["context"] == "base context"
        assert result["trace_nodes_added"] == 0
        assert result["trace_expanded"] is True


# ---------------------------------------------------------------------------
# Wave 2.2: Smart chunk selection (best chunk per file, not first)
# ---------------------------------------------------------------------------

class TestSmartChunkSelection:

    def test_best_chunk_selected_not_first(self, tmp_path):
        """When a file has multiple chunks, the most relevant one should be selected."""
        dim = 4
        query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # file.py has two chunks: first is irrelevant, second is highly relevant
        chunk1_vec = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)  # irrelevant
        chunk2_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)  # highly relevant

        docs = [
            {"source_path": "file.py", "content": "irrelevant chunk (first)", "section": "imports"},
            {"source_path": "file.py", "content": "highly relevant chunk (second)", "section": "core_logic"},
        ]
        embeddings = np.vstack([chunk1_vec, chunk2_vec])

        idx = _make_index(tmp_path, docs, embeddings)
        trace_idx = _make_trace_index(["file.py"])

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "",
                "chunks": [{"source_path": "source.py"}],
                "total_chars": 0,
                "estimated_tokens": 0,
            }
            idx.embedder = MagicMock()
            idx.embedder.embed_query.return_value = MagicMock(vector=query_vec.tolist())

            result = idx.get_context_with_trace_expansion(
                query="core logic",
                trace_index=trace_idx,
                k=3,
                max_chars=10000,
                max_additional_chars=5000,
            )

        context = result.get("context", "")
        # The best chunk (second, higher relevance) should appear in context
        assert "highly relevant chunk" in context
        # The irrelevant first chunk should NOT appear
        assert "irrelevant chunk" not in context

    def test_best_chunk_score_beats_first_chunk_score(self, tmp_path):
        """Score on the expanded chunk should reflect the best chunk, not the first."""
        dim = 4
        query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        chunk1_vec = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)  # sim ≈ 0
        chunk2_vec = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)  # sim ≈ 0.99

        docs = [
            {"source_path": "file.py", "content": "chunk1", "section": ""},
            {"source_path": "file.py", "content": "chunk2", "section": ""},
        ]
        embeddings = np.vstack([chunk1_vec, chunk2_vec])

        idx = _make_index(tmp_path, docs, embeddings)
        trace_idx = _make_trace_index(["file.py"])

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "",
                "chunks": [{"source_path": "source.py"}],
                "total_chars": 0,
                "estimated_tokens": 0,
            }
            idx.embedder = MagicMock()
            idx.embedder.embed_query.return_value = MagicMock(vector=query_vec.tolist())

            result = idx.get_context_with_trace_expansion(
                query="query",
                trace_index=trace_idx,
                k=3,
                max_chars=10000,
                max_additional_chars=5000,
            )

        trace_chunks = [c for c in result.get("chunks", []) if c.get("trace_expanded")]
        assert len(trace_chunks) == 1
        # Score should reflect chunk2 (high sim), not chunk1 (low sim)
        assert trace_chunks[0]["score"] > 0.8

    def test_chars_budget_respected(self, tmp_path):
        """Trace expansion should not exceed max_additional_chars."""
        dim = 4
        query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

        docs = [
            {"source_path": f"file{i}.py", "content": "x" * 1000, "section": ""}
            for i in range(5)
        ]
        embeddings = np.random.rand(5, dim).astype(np.float32)
        embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)

        idx = _make_index(tmp_path, docs, embeddings)
        trace_idx = _make_trace_index([f"file{i}.py" for i in range(5)])

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "",
                "chunks": [{"source_path": "source.py"}],
                "total_chars": 0,
                "estimated_tokens": 0,
            }
            idx.embedder = MagicMock()
            idx.embedder.embed_query.return_value = MagicMock(vector=query_vec.tolist())

            result = idx.get_context_with_trace_expansion(
                query="query",
                trace_index=trace_idx,
                k=5,
                max_chars=10000,
                max_additional_chars=2500,  # fits at most 2 files (1000 chars each)
            )

        trace_chunks = [c for c in result.get("chunks", []) if c.get("trace_expanded")]
        # Should include at most 2 files (2 * 1000 ≤ 2500, but 3 * 1000 > 2500)
        assert len(trace_chunks) <= 2


# ---------------------------------------------------------------------------
# W2c: Skeleton Context for Trace-Expanded Neighbors (Phase 39)
# ---------------------------------------------------------------------------

class TestSkeletonContext:

    def test_skeleton_used_for_trace_expanded_neighbors(self, tmp_path):
        """When trace_index.get_file_skeleton returns content, trace-expanded
        neighbors should use the skeleton instead of raw chunk content."""
        dim = 4
        query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        neighbor_vec = np.array([0.8, 0.2, 0.0, 0.0], dtype=np.float32)

        docs = [
            {"source_path": "neighbor.py", "content": "def foo():\n    # full implementation body\n    x = 1\n    return x * 2\n", "section": ""},
        ]
        embeddings = np.vstack([neighbor_vec])

        idx = _make_index(tmp_path, docs, embeddings)

        # Create a mock trace index that returns a real skeleton string
        trace_idx = _make_trace_index(["neighbor.py"])
        skeleton_content = "def foo() -> int\nclass Bar"
        trace_idx.get_file_skeleton.return_value = skeleton_content

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "",
                "chunks": [{"source_path": "source.py"}],
                "total_chars": 0,
                "estimated_tokens": 0,
            }
            idx.embedder = MagicMock()
            idx.embedder.embed_query.return_value = MagicMock(vector=query_vec.tolist())

            result = idx.get_context_with_trace_expansion(
                query="foo function",
                trace_index=trace_idx,
                k=3,
                max_chars=10000,
                max_additional_chars=5000,
            )

        context = result.get("context", "")
        # Skeleton should appear instead of full implementation
        assert "def foo() -> int" in context
        assert "class Bar" in context
        # Full implementation body should NOT appear
        assert "full implementation body" not in context

    def test_primary_hits_not_skeletonized(self, tmp_path):
        """Primary search hits (non-trace-expanded) should still show full content."""
        dim = 4
        query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        hit_vec = np.array([0.95, 0.05, 0.0, 0.0], dtype=np.float32)

        docs = [
            {"source_path": "main.py", "content": "def main():\n    # full primary content\n    return 42\n", "section": ""},
        ]
        embeddings = np.vstack([hit_vec])

        idx = _make_index(tmp_path, docs, embeddings)
        trace_idx = MagicMock()
        trace_idx.is_loaded.return_value = True
        trace_idx.get_neighbors.return_value = {
            "in_nodes": [], "out_nodes": [], "in_edges": [], "out_edges": [],
        }

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "def main():\n    # full primary content\n    return 42\n",
                "chunks": [{"source_path": "main.py", "content": "def main():\n    # full primary content\n    return 42\n"}],
                "total_chars": 50,
                "estimated_tokens": 12,
            }
            idx.embedder = MagicMock()
            idx.embedder.embed_query.return_value = MagicMock(vector=query_vec.tolist())

            result = idx.get_context_with_trace_expansion(
                query="main function",
                trace_index=trace_idx,
                k=3,
                max_chars=10000,
                max_additional_chars=5000,
            )

        context = result.get("context", "")
        # Primary hit should retain full content
        assert "full primary content" in context


# ---------------------------------------------------------------------------
# W2b: Module Summary Injection Tests (Phase 39)
# ---------------------------------------------------------------------------

class TestModuleSummaryInjection:

    def _write_modules(self, path, modules):
        """Write trace_modules.jsonl to disk."""
        import json
        with open(path, "w") as f:
            for m in modules:
                f.write(json.dumps(m) + "\n")

    def test_broad_query_injects_module_summary(self, tmp_path):
        """When ≥60% of search hits share a module, the module summary is prepended."""
        dim = 4
        query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

        # 3 hits in module "Core Engine", 1 outside → 75% in one module
        docs = [
            {"source_path": "src/index.py", "content": "indexing code", "section": ""},
            {"source_path": "src/search.py", "content": "search code", "section": ""},
            {"source_path": "src/embedder.py", "content": "embedder code", "section": ""},
            {"source_path": "ui/App.tsx", "content": "ui code", "section": ""},
        ]
        vecs = np.random.rand(4, dim).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

        idx = _make_index(tmp_path, docs, vecs)
        trace_idx = MagicMock()
        trace_idx.is_loaded.return_value = False  # no trace expansion needed

        modules_path = tmp_path / "trace_modules.jsonl"
        self._write_modules(modules_path, [
            {
                "name": "Core Engine",
                "summary": "Main indexing and search engine for semantic code search.",
                "member_files": ["src/index.py", "src/search.py", "src/embedder.py"],
            },
            {
                "name": "Dashboard UI",
                "summary": "React dashboard for visualization.",
                "member_files": ["ui/App.tsx", "ui/Search.tsx"],
            },
        ])

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "indexing code\nsearch code\nembedder code\nui code",
                "chunks": [
                    {"source_path": "src/index.py"},
                    {"source_path": "src/search.py"},
                    {"source_path": "src/embedder.py"},
                    {"source_path": "ui/App.tsx"},
                ],
                "total_chars": 50,
                "estimated_tokens": 12,
            }
            idx.embedder = MagicMock()
            idx.embedder.embed_query.return_value = MagicMock(vector=query_vec.tolist())

            result = idx.get_context_with_trace_expansion(
                query="how does the search engine work",
                trace_index=trace_idx,
                k=5,
                max_chars=10000,
                max_additional_chars=5000,
                modules_path=modules_path,
            )

        context = result.get("context", "")
        assert "[module-context | Core Engine]" in context
        assert "Main indexing and search engine" in context
        assert result.get("module_injected") == "Core Engine"

    def test_narrow_query_no_module_injection(self, tmp_path):
        """When hits are spread across modules (no ≥60% dominance), no module summary."""
        dim = 4
        query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

        # 2 hits in "Core", 2 in "UI" → 50% each, below 60% threshold
        docs = [
            {"source_path": "src/index.py", "content": "indexing code", "section": ""},
            {"source_path": "src/search.py", "content": "search code", "section": ""},
            {"source_path": "ui/App.tsx", "content": "app code", "section": ""},
            {"source_path": "ui/Search.tsx", "content": "search ui", "section": ""},
        ]
        vecs = np.random.rand(4, dim).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

        idx = _make_index(tmp_path, docs, vecs)
        trace_idx = MagicMock()
        trace_idx.is_loaded.return_value = False

        modules_path = tmp_path / "trace_modules.jsonl"
        self._write_modules(modules_path, [
            {
                "name": "Core Engine",
                "summary": "Main indexing and search engine.",
                "member_files": ["src/index.py", "src/search.py"],
            },
            {
                "name": "Dashboard UI",
                "summary": "React dashboard for visualization.",
                "member_files": ["ui/App.tsx", "ui/Search.tsx"],
            },
        ])

        with patch.object(idx, "get_context_structured") as mock_ctx:
            mock_ctx.return_value = {
                "context": "indexing code\nsearch code\napp code\nsearch ui",
                "chunks": [
                    {"source_path": "src/index.py"},
                    {"source_path": "src/search.py"},
                    {"source_path": "ui/App.tsx"},
                    {"source_path": "ui/Search.tsx"},
                ],
                "total_chars": 50,
                "estimated_tokens": 12,
            }
            idx.embedder = MagicMock()
            idx.embedder.embed_query.return_value = MagicMock(vector=query_vec.tolist())

            result = idx.get_context_with_trace_expansion(
                query="find the search function",
                trace_index=trace_idx,
                k=5,
                max_chars=10000,
                max_additional_chars=5000,
                modules_path=modules_path,
            )

        context = result.get("context", "")
        assert "[module-context" not in context
        assert result.get("module_injected") is None
