"""Regression test for the 2026-06-08 cluster-revert loop.

Clustering legitimately produced 836 modules from 861 prior
records (2.9% shrink, no user file deletions). The Write Guard
reverted the output via checkpoint restore because
_compute_allowed_shrink_ratio returned 0.0 (no changeset
deletions). Selfheal then saw the orphan manifest on the next
scan, kicked clustering again, same revert, infinite loop.

Fix: baseline shrink tolerance independent of deletion ratio.
"""
from __future__ import annotations

from prep.services.pipeline_integrity import FileSnapshot, IntegrityGuard, StageSnapshot


def _snap(records: int, size: int = 1000) -> FileSnapshot:
    return FileSnapshot(
        path="dummy",
        exists=True,
        size_bytes=size,
        modified_at=0.0,
        record_count=records,
    )


def _seed_snapshot(
    guard: IntegrityGuard,
    project_id: str,
    stage: str,
    files: dict,
) -> None:
    """Insert a real StageSnapshot pre-flight entry for ``(project_id, stage)``.

    Uses the actual dataclass rather than an anonymous mock so the
    test stays correct if the guard starts reading additional fields
    (is_incremental, taken_at, etc) in the future.
    """
    snap = StageSnapshot(project_id=project_id, stage_id=stage, files=files)
    guard._snapshots[(project_id, stage)] = snap


def test_clustering_three_percent_shrink_allowed_by_default():
    """The 2026-06-08 scenario: 836/861 records (2.9% shrink) must
    pass when the orchestrator's allowed_shrink_ratio reaches the
    guard."""
    g = IntegrityGuard()
    _seed_snapshot(g, "pid", "clustering", {"trace_modules.jsonl": _snap(861)})
    post = {"trace_modules.jsonl": _snap(836)}
    blocked, reason = g.should_block_stage_completion(
        "pid", "clustering", post,
        allowed_shrink_ratio=0.10,
    )
    assert not blocked, (
        f"clustering 836/861 shrunk only 2.9% — should pass with 10% baseline. "
        f"reason={reason}"
    )


def test_destructive_50pct_shrink_still_blocked():
    """The guard must still catch real data loss even with the 10%
    baseline tolerance."""
    g = IntegrityGuard()
    _seed_snapshot(g, "pid", "clustering", {"trace_modules.jsonl": _snap(800)})
    post = {"trace_modules.jsonl": _snap(400)}
    blocked, reason = g.should_block_stage_completion(
        "pid", "clustering", post,
        allowed_shrink_ratio=0.10,
    )
    assert blocked, f"50% shrink should always block. reason={reason}"


def test_baseline_used_when_no_changeset_deletions():
    """Unit test for the orchestrator helper itself: with no changeset
    (most common case for incremental work), the returned ratio must be
    at least the baseline, NOT 0.0."""
    from prep.services.pipeline.orchestrator import PipelineOrchestrator

    po = PipelineOrchestrator.__new__(PipelineOrchestrator)  # bypass __init__
    # When there's no changeset on disk, the helper should still return
    # >= 0.10 so consolidation stages aren't reverted.
    from pathlib import Path
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        ratio = po._compute_allowed_shrink_ratio(Path(tmp))
    assert ratio == 0.10, (
        f"_compute_allowed_shrink_ratio returned {ratio} for an empty "
        f"index_dir — should be exactly 0.10 baseline."
    )


def test_single_record_file_cannot_be_erased():
    """A pre_records=1 file must not be erasable via the baseline
    allowance. int(1 * (1.0 - 0.10)) truncates to 0; without a
    max(1, ...) floor the guard would accept 0 records and silently
    delete the file."""
    g = IntegrityGuard()
    _seed_snapshot(g, "pid", "clustering", {"trace_modules.jsonl": _snap(1)})
    post = {"trace_modules.jsonl": _snap(0)}
    blocked, reason = g.should_block_stage_completion(
        "pid", "clustering", post,
        allowed_shrink_ratio=0.10,
    )
    assert blocked, (
        f"single-record file dropping to 0 must be blocked even with "
        f"10% baseline allowance. reason={reason}"
    )
