"""Fix #6: integrity guard tolerates shrinkage proportional to user deletions.

A user who deletes 30% of their source files SHOULD see downstream
trace records shrink proportionally — that is not data loss, it's
the expected outcome of their action.  Before Fix #6, the integrity
guard had no Changeset awareness and would flag this case as
MAJOR_SHRINK, refusing to advance the stage.

These tests pin the new behavior:

  - With ``allowed_shrink_ratio=0`` (no deletions): any shrink blocks.
  - With ``allowed_shrink_ratio=0.30``: post >= 70% of pre is OK.
  - Even with a large allowance, catastrophic shrink (>95%) still blocks.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from prep.services.pipeline_integrity import (
    FileSnapshot,
    IntegrityGuard,
    StageSnapshot,
)


def _guard_with_pre(pre_records: int) -> IntegrityGuard:
    """Build a guard whose pre-flight snapshot has ``pre_records`` records."""
    guard = IntegrityGuard()
    pre = StageSnapshot(project_id="proj", stage_id="structural")
    pre.files["trace_nodes.jsonl"] = FileSnapshot(
        path="/tmp/trace_nodes.jsonl",
        exists=True,
        size_bytes=1_000_000,
        record_count=pre_records,
    )
    guard._snapshots[("proj", "structural")] = pre
    return guard


def _post(post_records: int) -> dict[str, FileSnapshot]:
    return {
        "trace_nodes.jsonl": FileSnapshot(
            path="/tmp/trace_nodes.jsonl",
            exists=True,
            size_bytes=500_000,
            record_count=post_records,
        )
    }


def test_no_deletions_any_shrink_blocks():
    """With no deletions, the guard is strict — any shrink blocks."""
    guard = _guard_with_pre(1000)
    blocked, reason = guard.should_block_stage_completion(
        "proj", "structural", _post(995),
        allowed_shrink_ratio=0.0,
    )
    assert blocked is True
    assert "1000" in reason and "995" in reason


def test_30pct_deletions_30pct_shrink_allowed():
    """User deleted 30% of files → 30% record shrink is expected, allowed."""
    guard = _guard_with_pre(1000)
    blocked, _reason = guard.should_block_stage_completion(
        "proj", "structural", _post(700),
        # 30% deletion → allowance = 0.30 * 1.5 + 0.10 = 0.55
        allowed_shrink_ratio=0.55,
    )
    assert blocked is False


def test_30pct_deletions_excess_shrink_still_blocks():
    """Even with 30% deletions (allowance 0.55), 80% shrinkage exceeds
    the budget and must block — this is the 'is this catastrophic data
    loss?' line that protects against the swarm-truncation case.
    """
    guard = _guard_with_pre(1000)
    blocked, reason = guard.should_block_stage_completion(
        "proj", "structural", _post(150),  # 85% loss, allowance is 55%
        allowed_shrink_ratio=0.55,
    )
    assert blocked is True
    # The reason should mention the allowance so it's obvious what
    # tolerance was applied.
    assert "deletion" in reason.lower() or "allowed" in reason.lower()


def test_extreme_allowance_still_blocks_catastrophic_loss():
    """The internal clamp to 0.95 means the guard never fully disables."""
    guard = _guard_with_pre(1000)
    blocked, _reason = guard.should_block_stage_completion(
        "proj", "structural", _post(10),  # 99% loss
        allowed_shrink_ratio=10.0,  # absurd allowance, gets clamped
    )
    assert blocked is True


def test_deletion_does_not_apply_to_growth():
    """An allowance only affects shrink — growth is always fine."""
    guard = _guard_with_pre(1000)
    blocked, _reason = guard.should_block_stage_completion(
        "proj", "structural", _post(1500),  # grew
        allowed_shrink_ratio=0.50,
    )
    assert blocked is False


def test_default_zero_allowance_preserves_legacy_behavior():
    """Callers that don't pass allowed_shrink_ratio get the old behavior."""
    guard = _guard_with_pre(1000)
    blocked, _ = guard.should_block_stage_completion(
        "proj", "structural", _post(800),
        # No allowed_shrink_ratio kwarg
    )
    assert blocked is True


# ── _compute_allowed_shrink_ratio helper ───────────────────────────


def _write_changeset(idx_dir: Path, *, added=(), modified=(), deleted=(), unchanged=()):
    import json
    payload = {
        "version": 1,
        "run_id": "run-test",
        "base_run_id": "run-base",
        "added": list(added),
        "modified": list(modified),
        "deleted": list(deleted),
        "unchanged": list(unchanged),
    }
    (idx_dir / "changeset.json").write_text(json.dumps(payload))


def _orch():
    from prep.services.pipeline.orchestrator import PipelineOrchestrator
    return PipelineOrchestrator.__new__(PipelineOrchestrator)


def test_compute_allowed_shrink_no_changeset(tmp_path):
    """No changeset on disk → baseline tolerance (2026-06-08 fix).

    Previously returned 0.0 (strict), but that caused the clustering
    revert loop: consolidation stages that shrink by a few percent were
    reverted even though no data was lost.  The baseline floor ensures
    natural consolidation passes the guard.
    """
    orch = _orch()
    assert orch._compute_allowed_shrink_ratio(tmp_path) >= 0.10


def test_compute_allowed_shrink_zero_deletions(tmp_path):
    """Changeset with no deletions → baseline tolerance (2026-06-08 fix).

    Previously returned 0.0, but consolidation stages (clustering,
    dedup) legitimately produce slightly fewer records than input even
    with no user deletions.  The baseline floor covers this case.
    """
    _write_changeset(tmp_path, added=["a.py"], modified=["b.py"], unchanged=["c.py"])
    orch = _orch()
    assert orch._compute_allowed_shrink_ratio(tmp_path) >= 0.10


def test_compute_allowed_shrink_proportional_to_deletions(tmp_path):
    """1 of 4 prior files deleted (25%) → allowance = 0.25 * 1.5 + 0.10 = 0.475."""
    _write_changeset(
        tmp_path,
        added=[],
        modified=[],
        deleted=["dead.py"],
        unchanged=["live1.py", "live2.py", "live3.py"],
    )
    # prior = unchanged(3) + deleted(1) = 4; ratio = 1/4 = 0.25
    orch = _orch()
    result = orch._compute_allowed_shrink_ratio(tmp_path)
    assert abs(result - (0.25 * 1.5 + 0.10)) < 0.001


def test_compute_allowed_shrink_handles_large_deletions(tmp_path):
    """50% of prior files deleted → allowance = 0.5 * 1.5 + 0.10 = 0.85."""
    _write_changeset(
        tmp_path,
        deleted=["d1.py", "d2.py", "d3.py", "d4.py", "d5.py"],
        unchanged=["u1.py", "u2.py", "u3.py", "u4.py", "u5.py"],
    )
    orch = _orch()
    result = orch._compute_allowed_shrink_ratio(tmp_path)
    assert abs(result - 0.85) < 0.001


def test_compute_allowed_shrink_malformed_changeset(tmp_path):
    """Corrupted changeset.json → fall through with baseline tolerance.

    Previously returned 0.0 (strict).  After the 2026-06-08 fix,
    the baseline floor applies even on parse errors, so consolidation
    stages are not spuriously reverted when the changeset is unreadable.
    """
    (tmp_path / "changeset.json").write_text("{not valid json")
    orch = _orch()
    assert orch._compute_allowed_shrink_ratio(tmp_path) >= 0.10
