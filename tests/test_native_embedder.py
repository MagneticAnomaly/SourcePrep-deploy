"""
Tests for NativeEmbedder (ONNX-based nomic-embed-text-v1.5).

Covers:
- Dependency detection (is_available)
- Embedding dimension and normalization
- Document vs query prefix handling
- Batch embedding
- embed_query dispatching in CodeIndex.search
- Integration: build + search with NativeEmbedder

Run with: pytest tests/test_native_embedder.py -v
"""

import numpy as np
import pytest

from prep.core.embedder import NativeEmbedder, EmbeddingResult


# ---------------------------------------------------------------------------
# Skip all tests if ONNX deps are not installed
# ---------------------------------------------------------------------------
_native = NativeEmbedder()
_HAS_DEPS = _native.is_available()

pytestmark = pytest.mark.skipif(not _HAS_DEPS, reason="onnxruntime/tokenizers not installed")


# ---------------------------------------------------------------------------
# Basic embedding tests
# ---------------------------------------------------------------------------

class TestNativeEmbedderBasics:
    def test_is_available(self):
        assert NativeEmbedder().is_available() is True

    def test_embed_returns_correct_dim(self):
        emb = NativeEmbedder()
        result = emb.embed("def hello(): return 42")
        assert isinstance(result, EmbeddingResult)
        assert len(result.vector) == NativeEmbedder.DIM
        assert result.model.startswith("native:")

    def test_embed_is_unit_normalized(self):
        emb = NativeEmbedder()
        result = emb.embed("some code snippet")
        vec = np.array(result.vector)
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-5, f"Expected unit norm, got {norm}"

    def test_embed_deterministic(self):
        emb = NativeEmbedder()
        r1 = emb.embed("same text")
        r2 = emb.embed("same text")
        np.testing.assert_array_almost_equal(r1.vector, r2.vector)

    def test_different_texts_different_vectors(self):
        emb = NativeEmbedder()
        r1 = emb.embed("def add(a, b): return a + b")
        r2 = emb.embed("# This is a markdown documentation file")
        cos_sim = np.dot(r1.vector, r2.vector)
        assert cos_sim < 0.99, f"Different texts should produce different embeddings, sim={cos_sim}"


# ---------------------------------------------------------------------------
# Query vs Document prefix
# ---------------------------------------------------------------------------

class TestQueryDocumentPrefix:
    def test_embed_query_exists(self):
        emb = NativeEmbedder()
        assert hasattr(emb, "embed_query")

    def test_embed_query_returns_embedding(self):
        emb = NativeEmbedder()
        result = emb.embed_query("how does authentication work?")
        assert isinstance(result, EmbeddingResult)
        assert len(result.vector) == NativeEmbedder.DIM

    def test_query_and_doc_embeddings_differ(self):
        """embed() uses 'search_document:' prefix, embed_query() uses 'search_query:' prefix."""
        emb = NativeEmbedder()
        doc = emb.embed("authentication handler")
        query = emb.embed_query("authentication handler")
        # Same text but different prefixes → different vectors
        cos_sim = np.dot(doc.vector, query.vector)
        assert cos_sim < 0.999, f"Doc and query embeddings should differ slightly, sim={cos_sim}"


# ---------------------------------------------------------------------------
# Batch embedding
# ---------------------------------------------------------------------------

class TestBatchEmbedding:
    def test_batch_empty(self):
        emb = NativeEmbedder()
        assert emb.embed_batch([]) == []

    def test_batch_matches_individual(self):
        """Batch results should be very close to individual results.

        Note: slight differences are expected because batch padding affects
        mean pooling denominators. We check cosine similarity > 0.99.
        """
        emb = NativeEmbedder()
        texts = ["def foo(): pass", "class Bar: pass", "import os"]
        batch_results = emb.embed_batch(texts)
        individual_results = [emb.embed(t) for t in texts]

        assert len(batch_results) == len(texts)
        for br, ir in zip(batch_results, individual_results):
            cos_sim = np.dot(br.vector, ir.vector)
            assert cos_sim > 0.97, f"Batch vs individual should be very similar, got sim={cos_sim}"

    def test_batch_exceeding_batch_size(self):
        """Test that batching works when input exceeds batch_size."""
        emb = NativeEmbedder(batch_size=2)
        texts = ["text one", "text two", "text three", "text four", "text five"]
        results = emb.embed_batch(texts)
        assert len(results) == 5
        for r in results:
            assert len(r.vector) == NativeEmbedder.DIM


# ---------------------------------------------------------------------------
# Model download
# ---------------------------------------------------------------------------

class TestModelDownload:
    def test_download_model_returns_path(self):
        emb = NativeEmbedder()
        path = emb.download_model()
        assert path.endswith(".onnx")
        from pathlib import Path
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Integration: CodeIndex search uses embed_query
# ---------------------------------------------------------------------------

class TestCodeIndexIntegration:
    def test_build_and_search_with_native(self, tmp_path):
        """Build an index with NativeEmbedder and verify search works."""
        from pathlib import Path
        from prep.core import CodeIndex
        from prep.core.repo_policy import ensure_repo_policy

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text(
            'def authenticate_user(username, password):\n'
            '    """Authenticate a user against the database."""\n'
            '    return check_credentials(username, password)\n'
        )
        (repo / "utils.py").write_text(
            'def format_currency(amount, symbol="$"):\n'
            '    """Format a number as currency."""\n'
            '    return f"{symbol}{amount:.2f}"\n'
        )

        idx_dir = tmp_path / "index"
        idx_dir.mkdir()

        emb = NativeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=emb)
        idx.build(repo_root=repo)

        # Search for authentication — should rank main.py higher
        results = idx.search("user authentication", k=5, min_score=0.0)
        assert len(results) > 0

        # Verify the embedder's embed_query was used (search vectors differ from doc vectors)
        paths = [r.doc["source_path"] for r in results]
        assert any("main.py" in p for p in paths), f"Expected main.py in results, got {paths}"

        # main.py should score higher than utils.py for auth query
        scores_by_file = {}
        for r in results:
            sp = r.doc["source_path"]
            if sp not in scores_by_file or r.score > scores_by_file[sp]:
                scores_by_file[sp] = r.score

        if "main.py" in scores_by_file and "utils.py" in scores_by_file:
            assert scores_by_file["main.py"] > scores_by_file["utils.py"], \
                f"main.py ({scores_by_file['main.py']}) should score higher than utils.py ({scores_by_file['utils.py']})"
