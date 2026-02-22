"""
Tests for LayeredCodeIndex and delta staleness pruning (P06-S21).
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from codrag.core.index import CodeIndex, SearchResult
from codrag.core.layered_index import (
    LayeredCodeIndex,
    prune_stale_deltas,
)


# ── Helpers ───────────────────────────────────────────────────


def _make_index(tmp: Path, name: str, docs: List[Dict[str, Any]], dim: int = 4) -> Path:
    """Create a minimal index directory with documents and embeddings."""
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "documents.json").write_text(json.dumps(docs))
    emb = np.random.randn(len(docs), dim).astype(np.float32)
    # Normalize for cosine similarity
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    emb = emb / norms
    np.save(d / "embeddings.npy", emb)
    return d


def _mock_embedder():
    """Create a mock embedder that returns random vectors."""
    from codrag.core.embedder import EmbeddingResult

    embedder = MagicMock()
    embedder.embed.return_value = EmbeddingResult(
        vector=np.random.randn(4).tolist(),
        model="test",
    )
    embedder.embed_query = embedder.embed
    return embedder


# ── LayeredCodeIndex ──────────────────────────────────────────


class TestLayeredCodeIndex:
    def test_remote_only(self, tmp_path):
        """When there's no delta, search uses remote only."""
        remote_docs = [
            {"source_path": "src/a.py", "content": "def hello(): pass", "section": ""},
            {"source_path": "src/b.py", "content": "def world(): pass", "section": ""},
        ]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        embedder = _mock_embedder()

        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote, delta_index=None)

        assert layered.is_loaded()
        stats = layered.stats()
        assert stats["remote_chunks"] == 2
        assert stats["delta_chunks"] == 0
        assert stats["tombstoned_files"] == 0

    def test_delta_masks_remote(self, tmp_path):
        """Delta documents for a file should mask the remote version."""
        remote_docs = [
            {"source_path": "src/a.py", "content": "old version", "section": ""},
            {"source_path": "src/b.py", "content": "untouched", "section": ""},
        ]
        delta_docs = [
            {"source_path": "src/a.py", "content": "new version", "section": ""},
        ]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        delta_dir = _make_index(tmp_path, "delta", delta_docs)
        embedder = _mock_embedder()

        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        delta = CodeIndex(index_dir=delta_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote, delta_index=delta)

        tombstones = layered._get_tombstone_paths()
        assert "src/a.py" in tombstones
        assert "src/b.py" not in tombstones

        stats = layered.stats()
        assert stats["tombstoned_files"] == 1

    def test_invalidate_tombstones(self, tmp_path):
        """Tombstone cache can be invalidated."""
        remote_docs = [{"source_path": "src/a.py", "content": "x", "section": ""}]
        delta_docs = [{"source_path": "src/a.py", "content": "y", "section": ""}]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        delta_dir = _make_index(tmp_path, "delta", delta_docs)
        embedder = _mock_embedder()

        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        delta = CodeIndex(index_dir=delta_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote, delta_index=delta)

        assert len(layered._get_tombstone_paths()) == 1
        layered.invalidate_tombstones()
        assert layered._tombstone_paths is None
        # Re-compute
        assert len(layered._get_tombstone_paths()) == 1

    def test_from_dirs_no_delta(self, tmp_path):
        """from_dirs works when delta directory has no documents."""
        remote_docs = [{"source_path": "src/a.py", "content": "x", "section": ""}]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        delta_dir = tmp_path / "delta"
        delta_dir.mkdir()
        embedder = _mock_embedder()

        layered = LayeredCodeIndex.from_dirs(remote_dir, delta_dir, embedder)
        assert layered.remote.is_loaded()
        assert layered.delta is None


# ── Delta staleness pruning ───────────────────────────────────


class TestPruneStaleDelta:
    def test_prune_merged_files(self, tmp_path):
        """Files that appear in the remote manifest should be pruned from deltas."""
        # Remote manifest has src/a.py
        manifest = {"file_hashes": {"src/a.py": "hash_a", "src/b.py": "hash_b"}}
        manifest_path = tmp_path / "trace_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # Delta has src/a.py (now stale) and src/c.py (still local only)
        delta_dir = tmp_path / "delta"
        delta_dir.mkdir()
        delta_docs = [
            {"source_path": "src/a.py", "content": "old local edit"},
            {"source_path": "src/c.py", "content": "still editing"},
        ]
        (delta_dir / "documents.json").write_text(json.dumps(delta_docs))
        np.save(delta_dir / "embeddings.npy", np.zeros((2, 4), dtype=np.float32))

        pruned = prune_stale_deltas(manifest_path, delta_dir)
        assert pruned == 1

        # Verify remaining docs
        with open(delta_dir / "documents.json") as f:
            remaining = json.load(f)
        assert len(remaining) == 1
        assert remaining[0]["source_path"] == "src/c.py"

    def test_prune_nothing_when_no_overlap(self, tmp_path):
        """No pruning when delta files aren't in the remote manifest."""
        manifest = {"file_hashes": {"src/x.py": "hash_x"}}
        manifest_path = tmp_path / "trace_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        delta_dir = tmp_path / "delta"
        delta_dir.mkdir()
        delta_docs = [{"source_path": "src/y.py", "content": "local only"}]
        (delta_dir / "documents.json").write_text(json.dumps(delta_docs))

        pruned = prune_stale_deltas(manifest_path, delta_dir)
        assert pruned == 0

    def test_prune_with_no_manifest(self, tmp_path):
        """No crash when manifest doesn't exist."""
        delta_dir = tmp_path / "delta"
        delta_dir.mkdir()
        pruned = prune_stale_deltas(tmp_path / "nonexistent.json", delta_dir)
        assert pruned == 0

    def test_prune_with_no_delta(self, tmp_path):
        """No crash when delta dir has no documents."""
        manifest_path = tmp_path / "trace_manifest.json"
        manifest_path.write_text(json.dumps({"file_hashes": {}}))
        pruned = prune_stale_deltas(manifest_path, tmp_path / "empty")
        assert pruned == 0
