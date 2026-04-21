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

from prep.core.index import CodeIndex, SearchResult
from prep.core.layered_index import (
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
    from prep.core.embedder import EmbeddingResult

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


class TestLayeredCompatibility:
    """Test duck-type compatibility proxies on LayeredCodeIndex."""

    def test_index_dir_proxy(self, tmp_path):
        remote_docs = [{"source_path": "a.py", "content": "x", "section": ""}]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)
        assert layered.index_dir == remote.index_dir

    def test_embedder_proxy(self, tmp_path):
        remote_docs = [{"source_path": "a.py", "content": "x", "section": ""}]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)
        assert layered.embedder is remote.embedder

    def test_manifest_proxy(self, tmp_path):
        remote_docs = [{"source_path": "a.py", "content": "x", "section": ""}]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)
        assert layered._manifest is remote._manifest

    def test_documents_merged(self, tmp_path):
        """_documents property merges remote + delta, delta overrides remote."""
        remote_docs = [
            {"source_path": "a.py", "content": "old_a", "section": ""},
            {"source_path": "b.py", "content": "b_content", "section": ""},
        ]
        delta_docs = [
            {"source_path": "a.py", "content": "new_a", "section": ""},
        ]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        delta_dir = _make_index(tmp_path, "delta", delta_docs)
        embedder = _mock_embedder()

        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        delta = CodeIndex(index_dir=delta_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote, delta_index=delta)

        docs = layered._documents
        # Should have 2 docs total: new_a from delta + b from remote
        paths = [d["source_path"] for d in docs]
        assert "a.py" in paths
        assert "b.py" in paths
        assert len(docs) == 2
        # a.py should have delta content
        a_doc = next(d for d in docs if d["source_path"] == "a.py")
        assert a_doc["content"] == "new_a"

    def test_documents_no_delta(self, tmp_path):
        """_documents returns remote docs when no delta exists."""
        remote_docs = [{"source_path": "a.py", "content": "x", "section": ""}]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)
        assert len(layered._documents) == 1

    def test_stats_includes_layered_flag(self, tmp_path):
        """Stats should include layered=True indicator."""
        remote_docs = [{"source_path": "a.py", "content": "x", "section": ""}]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)
        layered = LayeredCodeIndex(remote_index=remote)
        stats = layered.stats()
        assert stats["layered"] is True

    def test_get_context_with_trace_expansion_delegates(self, tmp_path):
        """get_context_with_trace_expansion should delegate to remote."""
        remote_docs = [{"source_path": "a.py", "content": "x", "section": ""}]
        remote_dir = _make_index(tmp_path, "remote", remote_docs)
        embedder = _mock_embedder()
        remote = CodeIndex(index_dir=remote_dir, embedder=embedder)

        # Patch the method on the remote index
        remote.get_context_with_trace_expansion = MagicMock(return_value="test_context")
        layered = LayeredCodeIndex(remote_index=remote)

        result = layered.get_context_with_trace_expansion("query", k=5)
        remote.get_context_with_trace_expansion.assert_called_once_with("query", k=5)
        assert result == "test_context"


class TestBuildManagerLayeredIndex:
    """Test BuildManager.get_project_layered_index() wiring."""

    def test_fallback_to_plain_index(self, tmp_path):
        """When no remote index exists, returns plain CodeIndex."""
        from prep.services.build_manager import BuildManager
        from prep.core.project_registry import Project

        bm = BuildManager()
        proj = Project(
            id="test-1", name="Test", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )

        # Create the .prep dir (embedded mode)
        prep_dir = tmp_path / ".runprep"
        prep_dir.mkdir(parents=True, exist_ok=True)

        idx = bm.get_project_layered_index(proj)
        # Should be a plain CodeIndex (no remote dir)
        assert isinstance(idx, CodeIndex)
        assert not isinstance(idx, LayeredCodeIndex)

    def test_returns_layered_when_remote_exists(self, tmp_path):
        """When remote/documents.json exists, returns LayeredCodeIndex."""
        from prep.services.build_manager import BuildManager
        from prep.core.project_registry import Project

        bm = BuildManager()
        proj = Project(
            id="test-2", name="Test", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )

        # Create .prep dir with remote subdirectory
        prep_dir = tmp_path / ".runprep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        remote_dir = prep_dir / "remote"
        remote_dir.mkdir()
        # Write minimal documents.json + embeddings.npy
        (remote_dir / "documents.json").write_text(json.dumps([
            {"source_path": "src/main.py", "content": "print('hi')", "section": ""},
        ]))
        np.save(remote_dir / "embeddings.npy", np.zeros((1, 4), dtype=np.float32))

        idx = bm.get_project_layered_index(proj)
        assert isinstance(idx, LayeredCodeIndex)
        assert idx.remote.is_loaded()

    def test_layered_with_delta(self, tmp_path):
        """When both remote and local_deltas exist, creates full layered index."""
        from prep.services.build_manager import BuildManager
        from prep.core.project_registry import Project

        bm = BuildManager()
        proj = Project(
            id="test-3", name="Test", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )

        prep_dir = tmp_path / ".runprep"
        prep_dir.mkdir(parents=True, exist_ok=True)

        # Remote index
        remote_dir = prep_dir / "remote"
        remote_dir.mkdir()
        (remote_dir / "documents.json").write_text(json.dumps([
            {"source_path": "a.py", "content": "old", "section": ""},
            {"source_path": "b.py", "content": "untouched", "section": ""},
        ]))
        np.save(remote_dir / "embeddings.npy", np.zeros((2, 4), dtype=np.float32))

        # Local deltas
        delta_dir = prep_dir / "local_deltas"
        delta_dir.mkdir()
        (delta_dir / "documents.json").write_text(json.dumps([
            {"source_path": "a.py", "content": "new local version", "section": ""},
        ]))
        np.save(delta_dir / "embeddings.npy", np.zeros((1, 4), dtype=np.float32))

        idx = bm.get_project_layered_index(proj)
        assert isinstance(idx, LayeredCodeIndex)
        assert idx.delta is not None
        stats = idx.stats()
        assert stats["remote_chunks"] == 2
        assert stats["delta_chunks"] == 1
        assert stats["tombstoned_files"] == 1


class TestRemoteSyncStartup:
    """Test RemoteSyncService auto-start on daemon startup."""

    def test_sync_status_lazy_creates(self, tmp_path):
        """get_project_sync_status creates a syncer for the project."""
        from prep.services.project_helpers import get_project_sync_status
        from prep.core.project_registry import Project

        proj = Project(
            id="sync-test", name="SyncTest", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )
        syncers = {}
        status = get_project_sync_status(proj, syncers)

        assert "sync-test" in syncers
        assert status["enabled"] is False  # No team_config.json

    def test_sync_status_detects_enabled_config(self, tmp_path):
        """When team_config.json has sync.enabled=true, status reports enabled."""
        from prep.services.project_helpers import get_project_sync_status
        from prep.core.project_registry import Project

        proj = Project(
            id="sync-enabled", name="SyncEnabled", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )

        # Write team_config.json
        prep_dir = tmp_path / ".runprep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        (prep_dir / "team_config.json").write_text(json.dumps({
            "sync": {
                "enabled": True,
                "s3_endpoint": "https://example.r2.cloudflarestorage.com",
                "s3_bucket": "test-bucket",
                "s3_prefix": "test-repo",
            }
        }))

        syncers = {}
        status = get_project_sync_status(proj, syncers)
        assert status["enabled"] is True

    def test_sync_status_disabled_by_default(self, tmp_path):
        """When team_config.json has sync.enabled=false, status is disabled."""
        from prep.services.project_helpers import get_project_sync_status
        from prep.core.project_registry import Project

        proj = Project(
            id="sync-disabled", name="SyncDisabled", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )

        prep_dir = tmp_path / ".runprep"
        prep_dir.mkdir(parents=True, exist_ok=True)
        (prep_dir / "team_config.json").write_text(json.dumps({
            "sync": {"enabled": False}
        }))

        syncers = {}
        status = get_project_sync_status(proj, syncers)
        assert status["enabled"] is False


class TestBuildManagerDeltaBuild:
    """Test BuildManager delta build and cache invalidation."""

    def test_has_remote_index_false(self, tmp_path):
        """has_remote_index returns False when no remote dir."""
        from prep.services.build_manager import BuildManager
        from prep.core.project_registry import Project

        bm = BuildManager()
        proj = Project(
            id="no-remote", name="Test", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )
        prep_dir = tmp_path / ".runprep"
        prep_dir.mkdir(parents=True, exist_ok=True)

        assert bm.has_remote_index(proj) is False

    def test_has_remote_index_true(self, tmp_path):
        """has_remote_index returns True when remote/documents.json exists."""
        from prep.services.build_manager import BuildManager
        from prep.core.project_registry import Project

        bm = BuildManager()
        proj = Project(
            id="has-remote", name="Test", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )
        remote_dir = tmp_path / ".runprep" / "remote"
        remote_dir.mkdir(parents=True, exist_ok=True)
        (remote_dir / "documents.json").write_text("[]")

        assert bm.has_remote_index(proj) is True

    def test_layered_cache_invalidation(self, tmp_path):
        """invalidate_layered_cache clears the cached LayeredCodeIndex."""
        from prep.services.build_manager import BuildManager
        from prep.core.project_registry import Project

        bm = BuildManager()
        proj = Project(
            id="cache-test", name="Test", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )

        # Set up remote index
        prep_dir = tmp_path / ".runprep"
        remote_dir = prep_dir / "remote"
        remote_dir.mkdir(parents=True, exist_ok=True)
        (remote_dir / "documents.json").write_text(json.dumps([
            {"source_path": "a.py", "content": "x", "section": ""},
        ]))
        np.save(remote_dir / "embeddings.npy", np.zeros((1, 4), dtype=np.float32))

        # First call creates and caches
        idx1 = bm.get_project_layered_index(proj)
        assert isinstance(idx1, LayeredCodeIndex)
        assert "cache-test" in bm._layered_indexes

        # Second call returns cached
        idx2 = bm.get_project_layered_index(proj)
        assert idx2 is idx1

        # Invalidate clears cache
        bm.invalidate_layered_cache("cache-test")
        assert "cache-test" not in bm._layered_indexes

        # Next call creates a fresh instance
        idx3 = bm.get_project_layered_index(proj)
        assert idx3 is not idx1

    def test_cache_cleared_when_remote_disappears(self, tmp_path):
        """Cache is cleared when remote index is deleted."""
        from prep.services.build_manager import BuildManager
        from prep.core.project_registry import Project

        bm = BuildManager()
        proj = Project(
            id="vanish-test", name="Test", path=str(tmp_path),
            mode="embedded", config={}, created_at="", updated_at="",
        )

        prep_dir = tmp_path / ".runprep"
        remote_dir = prep_dir / "remote"
        remote_dir.mkdir(parents=True, exist_ok=True)
        docs_path = remote_dir / "documents.json"
        docs_path.write_text(json.dumps([
            {"source_path": "a.py", "content": "x", "section": ""},
        ]))
        np.save(remote_dir / "embeddings.npy", np.zeros((1, 4), dtype=np.float32))

        # Get layered index (cached)
        idx1 = bm.get_project_layered_index(proj)
        assert isinstance(idx1, LayeredCodeIndex)

        # Remove remote index
        docs_path.unlink()

        # Next call should return plain CodeIndex and clear cache
        idx2 = bm.get_project_layered_index(proj)
        assert isinstance(idx2, CodeIndex)
        assert not isinstance(idx2, LayeredCodeIndex)
        assert "vanish-test" not in bm._layered_indexes


class TestRemoteSyncDeltaPruning:
    """Test that RemoteSyncService auto-prunes deltas after downloading."""

    def test_prune_called_after_sync(self, tmp_path):
        """_prune_stale_deltas is called and works correctly."""
        from prep.services.remote_sync import RemoteSyncService

        svc = RemoteSyncService(tmp_path)

        # Set up remote index dir with manifest
        remote_dir = tmp_path / ".runprep" / "index" / "remote"
        remote_dir.mkdir(parents=True, exist_ok=True)
        (remote_dir / "trace_manifest.json").write_text(json.dumps({
            "file_hashes": {"src/a.py": "hash_a"},
        }))

        # Set up local deltas with a stale file
        delta_dir = tmp_path / ".runprep" / "index" / "local_deltas"
        delta_dir.mkdir(parents=True, exist_ok=True)
        (delta_dir / "documents.json").write_text(json.dumps([
            {"source_path": "src/a.py", "content": "stale local"},
            {"source_path": "src/b.py", "content": "still local"},
        ]))

        # Call the prune method directly
        svc._prune_stale_deltas()

        # Verify src/a.py was pruned (it's in the remote manifest)
        with open(delta_dir / "documents.json") as f:
            remaining = json.load(f)
        assert len(remaining) == 1
        assert remaining[0]["source_path"] == "src/b.py"

    def test_prune_noop_when_no_deltas(self, tmp_path):
        """No error when delta dir doesn't exist."""
        from prep.services.remote_sync import RemoteSyncService

        svc = RemoteSyncService(tmp_path)
        # No delta dir at all — should not raise
        svc._prune_stale_deltas()


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
