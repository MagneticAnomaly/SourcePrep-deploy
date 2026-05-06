"""Phase 128 Task 4: build-success marker primitives.

The clean-shutdown marker (.pipeline_clean_shutdown) is only written from the
FastAPI lifespan shutdown handler — it captures graceful daemon termination,
not build success. After kill -9 / USB eject / sleep / crash, the marker is
absent even when the on-disk data is healthy.

The build-success marker (.pipeline_last_success) records that a complete
pipeline run finished. It survives ungraceful daemon termination and is the
durable signal Phase 61B will consult to skip recovery.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def fake_idx(tmp_path: Path) -> Path:
    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    return idx


def test_write_creates_marker(fake_idx: Path) -> None:
    from prep.services.pipeline.recovery import RecoveryManager

    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=fake_idx,
    ):
        assert RecoveryManager.write_build_success_marker("proj-1") is True

    assert (fake_idx / ".pipeline_last_success").exists()


def test_check_returns_true_when_present(fake_idx: Path) -> None:
    from prep.services.pipeline.recovery import RecoveryManager

    (fake_idx / ".pipeline_last_success").write_text("123.0")
    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=fake_idx,
    ):
        assert RecoveryManager.check_build_success_marker("proj-1") is True


def test_check_returns_false_when_absent(fake_idx: Path) -> None:
    from prep.services.pipeline.recovery import RecoveryManager

    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=fake_idx,
    ):
        assert RecoveryManager.check_build_success_marker("proj-1") is False


def test_marker_independent_of_clean_shutdown_marker(fake_idx: Path) -> None:
    """Build-success marker survives even if clean-shutdown marker is absent.

    This is the whole point — the existing clean-shutdown marker only fires
    on SIGTERM. A successful build followed by kill -9 must still be
    recognizable as healthy via the build-success marker alone.
    """
    from prep.services.pipeline.recovery import RecoveryManager

    (fake_idx / ".pipeline_last_success").write_text("123.0")
    # NO clean-shutdown marker on disk

    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=fake_idx,
    ):
        assert RecoveryManager.check_build_success_marker("proj-1") is True
        assert RecoveryManager.check_clean_shutdown_marker("proj-1") is False


def test_mtime_returns_marker_mtime(fake_idx: Path) -> None:
    """build_success_marker_mtime returns the file's mtime so Phase 61B can
    compare it against structural mtime."""
    from prep.services.pipeline.recovery import RecoveryManager

    marker = fake_idx / ".pipeline_last_success"
    marker.write_text("ts")
    import os
    os.utime(marker, (1000.5, 1000.5))

    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=fake_idx,
    ):
        assert RecoveryManager.build_success_marker_mtime("proj-1") == 1000.5


def test_mtime_returns_none_when_absent(fake_idx: Path) -> None:
    from prep.services.pipeline.recovery import RecoveryManager

    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=fake_idx,
    ):
        assert RecoveryManager.build_success_marker_mtime("proj-1") is None


def test_invalidate_removes_marker(fake_idx: Path) -> None:
    from prep.services.pipeline.recovery import RecoveryManager

    (fake_idx / ".pipeline_last_success").write_text("123.0")
    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=fake_idx,
    ):
        assert RecoveryManager.invalidate_build_success_marker("proj-1") is True

    assert not (fake_idx / ".pipeline_last_success").exists()


def test_invalidate_idempotent(fake_idx: Path) -> None:
    """Invalidating a non-existent marker returns False, no error."""
    from prep.services.pipeline.recovery import RecoveryManager

    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=fake_idx,
    ):
        assert RecoveryManager.invalidate_build_success_marker("proj-1") is False
