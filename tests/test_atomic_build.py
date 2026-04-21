"""
Tests for atomic build and recovery in CodeIndex.

Run with: pytest tests/test_atomic_build.py -v
"""

import json
import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

from prep.core import CodeIndex, FakeEmbedder


@pytest.fixture
def index_setup(tmp_path: Path):
    """Setup a repo and index directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass")
    
    idx_dir = tmp_path / "index"
    embedder = FakeEmbedder()
    
    return repo, idx_dir, embedder


def test_atomic_build_success(index_setup):
    """Build should succeed and create index files in the target directory."""
    repo, idx_dir, embedder = index_setup
    
    idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
    manifest = idx.build(repo_root=repo)
    
    # Verify files exist in the final directory
    assert (idx_dir / "documents.json").exists()
    assert (idx_dir / "embeddings.npy").exists()
    assert (idx_dir / "manifest.json").exists()
    assert (idx_dir / "fts.sqlite3").exists()
    
    # Verify manifest matches
    assert manifest["build"]["files_total"] == 1
    
    # Verify no temp dirs left
    temp_dirs = list(idx_dir.parent.glob(".index_build_*"))
    assert len(temp_dirs) == 0


def test_atomic_build_failure_cleanup(index_setup):
    """If build fails, temp directory should be cleaned up and original index preserved."""
    repo, idx_dir, embedder = index_setup
    
    # Create an initial index
    idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
    idx.build(repo_root=repo)
    
    original_mtime = (idx_dir / "manifest.json").stat().st_mtime
    
    # Force a failure during manifest build (which happens after writing docs/embeddings)
    # This ensures we test the cleanup logic
    with patch('prep.core.index.build_manifest', side_effect=Exception("Boom")):
        with pytest.raises(Exception, match="Boom"):
            idx.build(repo_root=repo)
            
    # Verify original index is untouched (mtime matches)
    assert (idx_dir / "manifest.json").exists()
    assert (idx_dir / "manifest.json").stat().st_mtime == original_mtime
    
    # Verify no temp dirs left
    temp_dirs = list(idx_dir.parent.glob(".index_build_*"))
    assert len(temp_dirs) == 0


def test_cleanup_stale_builds(index_setup):
    """Init should clean up stale build directories older than 1 hour."""
    repo, idx_dir, embedder = index_setup
    
    # Create some fake stale dirs
    stale_build = idx_dir.parent / ".index_build_old"
    stale_build.mkdir()
    (stale_build / "garbage").touch()
    
    stale_backup = idx_dir.parent / ".index_backup_old"
    stale_backup.mkdir()
    
    fresh_build = idx_dir.parent / ".index_build_new"
    fresh_build.mkdir()
    
    # Mock stat to make old ones look old (2 hours ago)
    # and fresh one look new
    now = time.time()
    old_time = now - 7200
    
    # We can't easily mock Path.stat() for specific paths globally, 
    # so we rely on the implementation calling .stat().st_mtime
    
    # Instead of complex mocking, let's just use the fact that os.utime can set mtime
    import os
    os.utime(stale_build, (old_time, old_time))
    os.utime(stale_backup, (old_time, old_time))
    os.utime(fresh_build, (now, now))
    
    # Initialize index, which triggers cleanup
    CodeIndex(index_dir=idx_dir, embedder=embedder)
    
    # Check what remains
    assert not stale_build.exists()
    assert not stale_backup.exists()
    assert fresh_build.exists()  # Should remain as it's fresh


def test_swap_replaces_existing(index_setup):
    """Atomic swap should replace existing index directory."""
    repo, idx_dir, embedder = index_setup
    
    # First build
    idx = CodeIndex(index_dir=idx_dir, embedder=embedder)
    idx.build(repo_root=repo)
    
    # Modify repo to verify change
    (repo / "new.py").write_text("def new(): pass")
    
    # Second build
    idx.build(repo_root=repo)
    
    # Verify updated content
    with open(idx_dir / "documents.json") as f:
        docs = json.load(f)
    
    paths = [d["source_path"] for d in docs]
    assert "main.py" in paths
    assert "new.py" in paths
    
    # Verify backups are cleaned up
    backups = list(idx_dir.parent.glob(".index_backup_*"))
    assert len(backups) == 0
