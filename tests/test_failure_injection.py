"""
Tests for failure injection and edge cases (disk pressure, interruptions).

Run with: pytest tests/test_failure_injection.py -v
"""

import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

import codrag.server as server
from codrag.core import CodeIndex, FakeEmbedder
from codrag.server import app
from codrag.api.envelope import ApiException

@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Create a test client with fresh state."""
    # Reset server state
    server._project_indexes.clear()
    server._project_build_threads.clear()
    server._project_last_build_result.clear()
    server._project_last_build_error.clear()
    return TestClient(app)

@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    """Create a minimal test repository."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    (repo / "main.py").write_text('print("hello")')
    return repo

class TestDiskPressure:
    """Tests for low disk space handling."""

    def test_build_fails_on_low_disk_space(self, mini_repo: Path, tmp_path: Path):
        """Build should raise INSUFFICIENT_SPACE if free space < 500MB."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)

        # Mock shutil.disk_usage to return low free space (e.g. 100MB)
        # usage(total, used, free)
        mock_usage = MagicMock()
        mock_usage.free = 100 * 1024 * 1024  # 100 MB
        
        with patch("codrag.core.index.shutil.disk_usage", return_value=mock_usage):
            with pytest.raises(ApiException) as excinfo:
                idx.build(repo_root=mini_repo)
            
            assert excinfo.value.status_code == 500
            assert excinfo.value.code == "INSUFFICIENT_SPACE"
            assert "Insufficient disk space" in excinfo.value.message

    def test_build_succeeds_on_sufficient_disk_space(self, mini_repo: Path, tmp_path: Path):
        """Build should proceed if free space >= 500MB."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)

        # Mock shutil.disk_usage to return plenty of free space (e.g. 1GB)
        mock_usage = MagicMock()
        mock_usage.free = 1024 * 1024 * 1024  # 1 GB
        
        with patch("codrag.core.index.shutil.disk_usage", return_value=mock_usage):
            # Should not raise
            idx.build(repo_root=mini_repo)
            assert idx.is_loaded()

class TestBuildInterruption:
    """Tests for build interruptions and cleanup."""

    def test_cleanup_on_build_exception(self, mini_repo: Path, tmp_path: Path):
        """Temp directory should be cleaned up if build raises an exception."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)

        # Mock embedder to raise an exception during build
        with patch.object(embedder, "embed", side_effect=ValueError("Simulated build crash")):
            with pytest.raises(ValueError, match="Simulated build crash"):
                idx.build(repo_root=mini_repo)

        # Check that no temp build directories exist
        # CodeIndex.build creates .index_build_<uuid> in the parent of index_dir
        # But wait, index_dir is 'tmp_path/index'. So parent is 'tmp_path'.
        
        # We need to ensure we are looking in the right place.
        # Implementation: temp_dir = self.index_dir.parent / f".index_build_{build_id}"
        
        temp_dirs = list(tmp_path.glob(".index_build_*"))
        assert len(temp_dirs) == 0, f"Found leaked temp dirs: {temp_dirs}"

    def test_atomic_swap_failure_recovery(self, mini_repo: Path, tmp_path: Path):
        """If atomic swap fails, we should handle it (though cleanup of new_dir happens)."""
        idx_dir = tmp_path / "index"
        embedder = FakeEmbedder()
        idx = CodeIndex(index_dir=idx_dir, embedder=embedder)

        # We want to fail during _swap_index_dir or just before it completes.
        # Ideally, we mock _swap_index_dir to fail.
        
        with patch.object(idx, "_swap_index_dir", side_effect=OSError("Disk full during swap")):
            with pytest.raises(OSError, match="Disk full during swap"):
                idx.build(repo_root=mini_repo)
        
        # Temp dir should be cleaned up because the exception propagates out of the try/except block in build()
        # which has a finally/except cleanup for temp_dir.
        temp_dirs = list(tmp_path.glob(".index_build_*"))
        assert len(temp_dirs) == 0
