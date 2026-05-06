"""Phase 128 Task 5: orchestrator writes the build-success marker on
deep_enrichment / finalize completion, and resets invalidate it.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Marker invalidation on reset ─────────────────────────────────────────────


def test_invalidate_marker_when_present(tmp_path: Path) -> None:
    """A reset must call invalidate_build_success_marker, removing the marker
    so the next start does not see stale 'healthy' state."""
    from prep.services.pipeline.recovery import RecoveryManager

    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    (idx / ".pipeline_last_success").write_text("123.0")

    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=idx,
    ):
        result = RecoveryManager.invalidate_build_success_marker("proj-1")

    assert result is True
    assert not (idx / ".pipeline_last_success").exists()


def test_invalidate_idempotent(tmp_path: Path) -> None:
    """Invalidating a non-existent marker returns False, no error raised."""
    from prep.services.pipeline.recovery import RecoveryManager

    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=idx,
    ):
        assert RecoveryManager.invalidate_build_success_marker("proj-1") is False


# ── Orchestrator marker write helper ─────────────────────────────────────────
#
# We test a small helper rather than driving the full PipelineOrchestrator —
# the helper is the seam under test, and a unit test on it documents the
# semantics ("marker is only written for deep_enrichment / finalize, not
# fast_sync") clearly.


def test_record_group_completion_writes_marker_for_deep_enrichment(
    tmp_path: Path,
) -> None:
    """deep_enrichment completion writes the marker — its outputs are exactly
    the data Phase 61B's staleness check cares about."""
    from prep.services.pipeline.recovery import (
        RecoveryManager,
        record_group_completion,
    )

    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=idx,
    ):
        record_group_completion("proj-1", "deep_enrichment")
        assert RecoveryManager.check_build_success_marker("proj-1") is True


def test_record_group_completion_writes_marker_for_finalize(tmp_path: Path) -> None:
    """finalize completion also refreshes the marker."""
    from prep.services.pipeline.recovery import (
        RecoveryManager,
        record_group_completion,
    )

    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=idx,
    ):
        record_group_completion("proj-1", "finalize")
        assert RecoveryManager.check_build_success_marker("proj-1") is True


def test_record_group_completion_skips_fast_sync(tmp_path: Path) -> None:
    """fast_sync alone is NOT enough to claim healthy data for Phase 61B's
    purposes — it doesn't produce deep_enrichment manifests. Marker must
    not be written. Otherwise a fast_sync-only run would falsely suppress
    legitimate deep_enrichment auto-recovery."""
    from prep.services.pipeline.recovery import (
        RecoveryManager,
        record_group_completion,
    )

    idx = tmp_path / ".sourceprep"
    idx.mkdir()
    with patch(
        "prep.services.pipeline.recovery._resolve_idx_dir",
        return_value=idx,
    ):
        record_group_completion("proj-1", "fast_sync")
        assert RecoveryManager.check_build_success_marker("proj-1") is False
