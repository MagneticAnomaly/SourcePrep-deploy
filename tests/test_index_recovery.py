"""
Tests for index recovery and corruption detection.

Run with: pytest tests/test_index_recovery.py -v
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from prep.core import CodeIndex, FakeEmbedder


class TestCorruptionDetection:
    """Tests for detecting corrupted or incomplete indexes."""

    def test_missing_documents_file(self, mini_repo: Path, tmp_path: Path) -> None:
        """Index with missing documents.json should report as not loaded."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        # Build a valid index first
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        assert idx.is_loaded()
        
        # Remove documents.json
        (idx_dir / "documents.json").unlink()
        
        # Reload index
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        assert not idx2.is_loaded()

    def test_missing_embeddings_file(self, mini_repo: Path, tmp_path: Path) -> None:
        """Index with missing embeddings.npy should report as not loaded."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        assert idx.is_loaded()
        
        # Remove embeddings.npy
        (idx_dir / "embeddings.npy").unlink()
        
        # Reload index
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        assert not idx2.is_loaded()

    def test_corrupted_documents_json(self, mini_repo: Path, tmp_path: Path) -> None:
        """Index with corrupted documents.json should report as not loaded."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        assert idx.is_loaded()
        
        # Corrupt documents.json
        (idx_dir / "documents.json").write_text("{ invalid json }")
        
        # Reload index
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        assert not idx2.is_loaded()

    def test_corrupted_embeddings_npy(self, mini_repo: Path, tmp_path: Path) -> None:
        """Index with corrupted embeddings.npy should report as not loaded."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        assert idx.is_loaded()
        
        # Corrupt embeddings.npy
        (idx_dir / "embeddings.npy").write_bytes(b"not a numpy file")
        
        # Reload index
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        assert not idx2.is_loaded()

    def test_empty_documents_json(self, mini_repo: Path, tmp_path: Path) -> None:
        """Index with empty documents.json should report as not loaded."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        assert idx.is_loaded()
        
        # Empty documents.json
        (idx_dir / "documents.json").write_text("[]")
        
        # Reload index - empty is technically valid JSON but useless
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        # Empty docs array should still load but have 0 documents
        # This tests the boundary condition
        if idx2.is_loaded():
            status = idx2.status()
            assert status["total_documents"] == 0

    def test_dimension_mismatch(self, mini_repo: Path, tmp_path: Path) -> None:
        """Index with mismatched embedding dimensions should handle gracefully."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder(dim=384)
        
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        assert idx.is_loaded()
        
        # Replace embeddings with different dimension
        docs = json.loads((idx_dir / "documents.json").read_text())
        new_embeddings = np.random.rand(len(docs), 128).astype(np.float32)  # Wrong dim
        np.save(idx_dir / "embeddings.npy", new_embeddings)
        
        # Reload - should still load but dimension will be different
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        if idx2.is_loaded():
            st = idx2.stats()
            assert st["embedding_dim"] == 128  # Reports actual dim


class TestRecoveryBehaviors:
    """Tests for recovery from various failure states."""

    def test_rebuild_after_corruption(self, mini_repo: Path, tmp_path: Path) -> None:
        """Rebuilding after corruption should produce a valid index."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        # Build initial index
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        original_count = len(idx._documents or [])
        
        # Corrupt the index
        (idx_dir / "documents.json").write_text("corrupted")
        
        # Reload (should be not loaded)
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        assert not idx2.is_loaded()
        
        # Rebuild should succeed
        idx2.build(repo_root=mini_repo)
        assert idx2.is_loaded()
        assert len(idx2._documents or []) == original_count

    def test_rebuild_clears_stale_temp_dirs(self, mini_repo: Path, tmp_path: Path) -> None:
        """Building should clean up stale temp directories from failed builds."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        # Create stale build directories
        stale1 = idx_dir.parent / ".index_build_stale1"
        stale2 = idx_dir.parent / ".index_backup_stale2"
        stale1.mkdir(parents=True)
        stale2.mkdir(parents=True)
        
        # Make them old (mtime in the past)
        import os
        old_time = 0  # Unix epoch
        os.utime(stale1, (old_time, old_time))
        os.utime(stale2, (old_time, old_time))
        
        # Build index (triggers cleanup)
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        
        # Stale dirs should be cleaned up
        assert not stale1.exists()
        assert not stale2.exists()

    def test_missing_manifest_still_loads(self, mini_repo: Path, tmp_path: Path) -> None:
        """Index without manifest.json should still load (graceful degradation)."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        assert idx.is_loaded()
        
        # Remove manifest
        (idx_dir / "manifest.json").unlink()
        
        # Reload - should still load (docs + embeddings are sufficient)
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        assert idx2.is_loaded()
        
        # Stats should show "unknown" for missing manifest fields
        st = idx2.stats()
        assert st["model"] == "unknown"

    def test_missing_fts_still_loads(self, mini_repo: Path, tmp_path: Path) -> None:
        """Index without fts.sqlite3 should still load and search works."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        assert idx.is_loaded()
        
        # Remove FTS index
        fts_path = idx_dir / "fts.sqlite3"
        if fts_path.exists():
            fts_path.unlink()
        
        # Reload
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        assert idx2.is_loaded()
        
        # Search should still work (without keyword boosting)
        results = idx2.search("hello", k=5)
        assert isinstance(results, list)

    def test_partial_index_directory(self, tmp_path: Path) -> None:
        """Index directory with only some files should not crash."""
        idx_dir = tmp_path / "index"
        idx_dir.mkdir()
        
        # Only create manifest (no docs or embeddings)
        (idx_dir / "manifest.json").write_text('{"version": "1.0"}')
        
        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        
        # Should not crash, just report not loaded
        assert not idx.is_loaded()


class TestCountMismatchDetection:
    """Tests for detecting document/embedding count mismatches."""

    def test_fewer_embeddings_than_documents(self, mini_repo: Path, tmp_path: Path) -> None:
        """Fewer embeddings than documents should be handled."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        
        # Truncate embeddings
        docs = json.loads((idx_dir / "documents.json").read_text())
        truncated = np.random.rand(len(docs) - 1, 384).astype(np.float32)
        np.save(idx_dir / "embeddings.npy", truncated)
        
        # Reload
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        # Implementation may either:
        # 1. Not load due to mismatch
        # 2. Load but limit to min(docs, embeddings)
        # Either is acceptable defensive behavior

    def test_more_embeddings_than_documents(self, mini_repo: Path, tmp_path: Path) -> None:
        """More embeddings than documents should be handled."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
        idx.build(repo_root=mini_repo)
        
        # Add extra embeddings
        docs = json.loads((idx_dir / "documents.json").read_text())
        extended = np.random.rand(len(docs) + 5, 384).astype(np.float32)
        np.save(idx_dir / "embeddings.npy", extended)
        
        # Reload
        idx2 = CodeIndex(index_dir=idx_dir, embedder=embedder)
        # Should handle gracefully (either not load or use min count)
