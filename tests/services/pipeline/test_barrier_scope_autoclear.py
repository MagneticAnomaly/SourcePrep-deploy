"""Phase 117: verify the barrier auto-clears at the right stage boundary per scope."""
from __future__ import annotations

import pytest

from prep.services.pipeline.recovery import (
    read_reset_barrier,
    write_reset_barrier,
)


@pytest.fixture
def project_with_idx(tmp_path, monkeypatch):
    from prep.services.pipeline import recovery
    monkeypatch.setattr(recovery, "_resolve_idx_dir", lambda _pid: tmp_path)
    return "proj-test", tmp_path


def test_maybe_clear_scoped_barrier_clears_on_sync_boundary(project_with_idx):
    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="sync")

    cleared = maybe_clear_scoped_barrier(project_id, completed_group="fast_sync")
    assert cleared is True
    assert read_reset_barrier(project_id) is None


def test_maybe_clear_scoped_barrier_ignores_wrong_group(project_with_idx):
    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="sync")

    cleared = maybe_clear_scoped_barrier(project_id, completed_group="deep_enrichment")
    assert cleared is False
    assert read_reset_barrier(project_id) is not None


def test_enrichment_scope_clears_on_deep_boundary(project_with_idx):
    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="enrichment")

    cleared = maybe_clear_scoped_barrier(project_id, completed_group="deep_enrichment")
    assert cleared is True


def test_all_scope_only_clears_on_finalize(project_with_idx):
    from prep.services.pipeline.recovery import maybe_clear_scoped_barrier
    project_id, _ = project_with_idx
    write_reset_barrier(project_id, reason="rebuild", scope="all")

    assert maybe_clear_scoped_barrier(project_id, completed_group="fast_sync") is False
    assert maybe_clear_scoped_barrier(project_id, completed_group="deep_enrichment") is False
    assert maybe_clear_scoped_barrier(project_id, completed_group="finalize") is True
    assert read_reset_barrier(project_id) is None
