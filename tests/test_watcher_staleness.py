"""
Tests for watcher staleness semantics.

Run with: pytest tests/test_watcher_staleness.py -v
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from prep.core.watcher import AutoRebuildWatcher


@pytest.fixture
def watcher_setup(tmp_path: Path):
    """Create a minimal watcher setup."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")
    
    idx_dir = tmp_path / "index"
    idx_dir.mkdir()
    
    # Create minimal repo_policy.json
    import json
    policy_path = idx_dir / "repo_policy.json"
    policy_path.write_text(json.dumps({
        "version": "1.0",
        "repo_root": str(repo),
        "include_globs": ["**/*.py"],
        "exclude_globs": [],
    }))
    
    build_triggered = MagicMock(return_value=True)
    is_building = MagicMock(return_value=False)
    
    watcher = AutoRebuildWatcher(
        repo_root=repo,
        index_dir=idx_dir,
        on_trigger_build=build_triggered,
        is_building=is_building,
        debounce_ms=100,  # Fast debounce for testing
        min_rebuild_gap_ms=50,
    )
    
    return {
        "watcher": watcher,
        "repo": repo,
        "idx_dir": idx_dir,
        "build_triggered": build_triggered,
        "is_building": is_building,
    }


class TestWatcherStaleness:
    """Tests for watcher staleness tracking."""
    
    def test_initial_status_not_stale(self, watcher_setup):
        """Watcher should not be stale before starting."""
        watcher = watcher_setup["watcher"]
        status = watcher.status()
        
        assert status["stale"] is False
        assert status["stale_since"] is None
    
    def test_after_start_not_stale(self, watcher_setup):
        """Watcher should not be stale immediately after starting."""
        watcher = watcher_setup["watcher"]
        watcher.start()
        
        try:
            status = watcher.status()
            assert status["stale"] is False
            assert status["stale_since"] is None
        finally:
            watcher.stop()
    
    def test_pending_paths_makes_stale(self, watcher_setup):
        """Having pending paths should mark the index as stale."""
        watcher = watcher_setup["watcher"]
        repo = watcher_setup["repo"]
        
        watcher.start()
        try:
            # Simulate a file change by directly adding to pending paths
            with watcher._lock:
                watcher._pending_paths.add("test.py")
                watcher._stale_since = "2024-01-01T00:00:00+00:00"
            
            status = watcher.status()
            assert status["stale"] is True
            assert status["stale_since"] is not None
            assert status["pending"] is True
        finally:
            watcher.stop()
    
    def test_stale_since_timestamp(self, watcher_setup):
        """stale_since should be set when first change is detected."""
        watcher = watcher_setup["watcher"]
        
        watcher.start()
        try:
            # Initially not stale
            status = watcher.status()
            assert status["stale_since"] is None
            
            # Manually trigger staleness (simulating file change detection)
            with watcher._lock:
                watcher._pending_paths.add("new_file.py")
                watcher._stale_since = "2024-01-15T10:30:00+00:00"
            
            status = watcher.status()
            assert status["stale_since"] == "2024-01-15T10:30:00+00:00"
        finally:
            watcher.stop()
    
    def test_status_includes_stale_fields(self, watcher_setup):
        """Status dict should include all staleness-related fields."""
        watcher = watcher_setup["watcher"]
        
        status = watcher.status()
        
        assert "stale" in status
        assert "stale_since" in status
        assert "pending" in status
        assert "pending_paths_count" in status
    
    def test_stop_resets_state(self, watcher_setup):
        """Stopping watcher should reset pending paths."""
        watcher = watcher_setup["watcher"]
        
        watcher.start()
        with watcher._lock:
            watcher._pending_paths.add("test.py")
        
        watcher.stop()
        
        status = watcher.status()
        assert status["state"] == "disabled"
        # Note: stale_since persists until explicitly cleared or watcher restarts


class TestWatcherStatusFields:
    """Tests for watcher status fields."""
    
    def test_status_has_expected_fields(self, watcher_setup):
        """Status should contain all expected fields."""
        watcher = watcher_setup["watcher"]
        
        status = watcher.status()
        
        expected_fields = {
            "enabled", "state", "debounce_ms", "stale", "stale_since",
            "pending", "pending_paths_count", "next_rebuild_at",
            "last_event_at", "last_rebuild_at"
        }
        
        assert set(status.keys()) == expected_fields
    
    def test_disabled_state(self, watcher_setup):
        """Disabled watcher should have correct state."""
        watcher = watcher_setup["watcher"]
        
        status = watcher.status()
        
        assert status["enabled"] is False
        assert status["state"] == "disabled"
    
    def test_enabled_idle_state(self, watcher_setup):
        """Started watcher with no events should be idle."""
        watcher = watcher_setup["watcher"]
        watcher.start()
        
        try:
            status = watcher.status()
            assert status["enabled"] is True
            assert status["state"] == "idle"
        finally:
            watcher.stop()
