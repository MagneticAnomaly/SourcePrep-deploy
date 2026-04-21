"""Tests for MMR (Maximal Marginal Relevance) diversity reranking (Wave 1.3).

Verifies that CodeIndex._mmr_rerank correctly balances relevance
with diversity when selecting results.
"""

from __future__ import annotations

import numpy as np
import pytest

from prep.core.index import CodeIndex, SearchResult


def _make_results(scores: list[float]) -> list[SearchResult]:
    """Helper: create SearchResult objects with given scores."""
    return [
        SearchResult(doc={"source_path": f"file_{i}.py", "content": f"chunk {i}"}, score=s)
        for i, s in enumerate(scores)
    ]


def _make_embeddings(vectors: list[list[float]]) -> np.ndarray:
    """Helper: create a normalized embedding matrix."""
    emb = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-8, norms)
    return emb / norms


class TestMMRRerank:
    """Tests for CodeIndex._mmr_rerank static method."""

    def test_single_result_unchanged(self):
        """A single result should be returned as-is."""
        results = _make_results([0.9])
        emb = _make_embeddings([[1.0, 0.0, 0.0]])
        top_idx = np.array([0])

        reranked = CodeIndex._mmr_rerank(results, emb, top_idx, mmr_lambda=0.7, k=5)
        assert len(reranked) == 1
        assert reranked[0].score == 0.9

    def test_diverse_results_preserved(self):
        """Diverse (orthogonal) results should all be kept in order."""
        results = _make_results([0.9, 0.85, 0.80])
        emb = _make_embeddings([
            [1.0, 0.0, 0.0],  # orthogonal
            [0.0, 1.0, 0.0],  # orthogonal
            [0.0, 0.0, 1.0],  # orthogonal
        ])
        top_idx = np.array([0, 1, 2])

        reranked = CodeIndex._mmr_rerank(results, emb, top_idx, mmr_lambda=0.7, k=5)
        assert len(reranked) == 3
        # First result always stays first
        assert reranked[0].score == 0.9

    def test_near_duplicate_demoted(self):
        """Near-identical embeddings should cause one to be demoted."""
        results = _make_results([0.9, 0.88, 0.70])
        emb = _make_embeddings([
            [1.0, 0.0, 0.0],   # file_0: highest score
            [0.99, 0.01, 0.0],  # file_1: near-duplicate of file_0
            [0.0, 1.0, 0.0],    # file_2: diverse, lower score
        ])
        top_idx = np.array([0, 1, 2])

        reranked = CodeIndex._mmr_rerank(results, emb, top_idx, mmr_lambda=0.5, k=3)
        assert len(reranked) == 3
        # First result stays first
        assert reranked[0].doc["source_path"] == "file_0.py"
        # The diverse result (file_2) should be promoted over the duplicate (file_1)
        assert reranked[1].doc["source_path"] == "file_2.py"
        assert reranked[2].doc["source_path"] == "file_1.py"

    def test_lambda_one_preserves_order(self):
        """With mmr_lambda=1.0, order should be identical to input (pure relevance)."""
        results = _make_results([0.9, 0.85, 0.80, 0.75])
        emb = _make_embeddings([
            [1.0, 0.0, 0.0],
            [0.99, 0.01, 0.0],  # near-duplicate
            [0.98, 0.02, 0.0],  # near-duplicate
            [0.0, 1.0, 0.0],    # diverse
        ])
        top_idx = np.array([0, 1, 2, 3])

        reranked = CodeIndex._mmr_rerank(results, emb, top_idx, mmr_lambda=1.0, k=4)
        assert len(reranked) == 4
        # With lambda=1.0, diversity term is 0, so pure relevance order
        assert [r.score for r in reranked] == [0.9, 0.85, 0.80, 0.75]

    def test_respects_k_limit(self):
        """Should not return more than k results."""
        results = _make_results([0.9, 0.85, 0.80, 0.75, 0.70])
        emb = _make_embeddings([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.5, 0.5, 0.0],
            [0.0, 0.5, 0.5],
        ])
        top_idx = np.array([0, 1, 2, 3, 4])

        reranked = CodeIndex._mmr_rerank(results, emb, top_idx, mmr_lambda=0.7, k=3)
        assert len(reranked) == 3

    def test_empty_input(self):
        """Empty candidates should return empty."""
        reranked = CodeIndex._mmr_rerank(
            [], np.zeros((0, 3), dtype=np.float32), np.array([]), mmr_lambda=0.7, k=5
        )
        assert reranked == []

    def test_all_identical_embeddings(self):
        """All identical embeddings: should still return k results."""
        results = _make_results([0.9, 0.85, 0.80])
        emb = _make_embeddings([
            [1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
        ])
        top_idx = np.array([0, 1, 2])

        reranked = CodeIndex._mmr_rerank(results, emb, top_idx, mmr_lambda=0.7, k=3)
        # All identical → diversity doesn't help, but should still return 3
        assert len(reranked) == 3
        # First result always first
        assert reranked[0].score == 0.9


class TestSearchIntegration:
    """Integration tests verifying Adaptive K and MMR work together in search()."""

    def test_search_with_defaults_returns_results(self, mini_repo, fake_embedder, tmp_path):
        """Search with default params (including new adaptive_k and mmr) should work."""
        from prep.core import CodeIndex

        index_dir = tmp_path / "idx"
        idx = CodeIndex(index_dir=index_dir, embedder=fake_embedder)
        idx.build(repo_root=mini_repo)

        results = idx.search("hello world", k=5)
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_mmr_disabled(self, mini_repo, fake_embedder, tmp_path):
        """search() with mmr_lambda=1.0 should behave like pure relevance."""
        from prep.core import CodeIndex

        index_dir = tmp_path / "idx"
        idx = CodeIndex(index_dir=index_dir, embedder=fake_embedder)
        idx.build(repo_root=mini_repo)

        results_default = idx.search("hello world", k=5, mmr_lambda=1.0)
        assert len(results_default) >= 1
        # Scores should be in descending order (pure relevance)
        scores = [r.score for r in results_default]
        assert scores == sorted(scores, reverse=True)

    def test_search_adaptive_k_disabled(self, mini_repo, fake_embedder, tmp_path):
        """search() with score_drop_ratio=0.0 should return up to k results."""
        from prep.core import CodeIndex

        index_dir = tmp_path / "idx"
        idx = CodeIndex(index_dir=index_dir, embedder=fake_embedder)
        idx.build(repo_root=mini_repo)

        results = idx.search("hello world", k=5, score_drop_ratio=0.0, mmr_lambda=1.0)
        assert len(results) >= 1
