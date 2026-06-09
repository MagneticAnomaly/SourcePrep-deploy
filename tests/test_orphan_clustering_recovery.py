"""Regression test: when a stage's output is rejected by the Write
Guard and restored from checkpoint, the next selfheal scan must NOT
immediately re-trigger that stage. The Guard rejection is a semantic
signal that the output was wrong; running it again without a new
input signal will hit the same rejection.

Approach: record a 'guard_rejected_until' marker that suppresses
selfheal resurrection until either:
  - a file in the project changes (watcher emits a new signal), OR
  - the user explicitly triggers a manual run, OR
  - 30 minutes elapse (defensive timeout for transient guard bugs).
"""
from __future__ import annotations

import time
from pathlib import Path

from prep.services.pipeline.recovery import (
    clear_guard_rejection,
    record_guard_rejection,
    should_defer_selfheal_resurrection,
)


def test_guard_rejection_suppresses_immediate_resurrection(tmp_path: Path):
    record_guard_rejection(tmp_path, stage="clustering", reason="MAJOR_SHRINK")
    assert should_defer_selfheal_resurrection(tmp_path, "clustering")


def test_guard_rejection_expires_after_timeout(tmp_path: Path, monkeypatch):
    record_guard_rejection(tmp_path, stage="clustering", reason="MAJOR_SHRINK")
    # Fast-forward time past the 30-min TTL.
    future = time.time() + 30 * 60 + 1
    monkeypatch.setattr(
        "prep.services.pipeline.recovery.time.time", lambda: future
    )
    assert not should_defer_selfheal_resurrection(tmp_path, "clustering")


def test_other_stages_not_suppressed(tmp_path: Path):
    record_guard_rejection(tmp_path, stage="clustering", reason="x")
    assert not should_defer_selfheal_resurrection(tmp_path, "deepening")


def test_clear_rejection_removes_marker(tmp_path: Path):
    """The watcher calls clear_guard_rejection when real file activity
    arrives, so the next selfheal scan can resurrect."""
    record_guard_rejection(tmp_path, stage="clustering", reason="x")
    assert should_defer_selfheal_resurrection(tmp_path, "clustering")
    clear_guard_rejection(tmp_path, "clustering")
    assert not should_defer_selfheal_resurrection(tmp_path, "clustering")


def test_no_marker_means_proceed_normally(tmp_path: Path):
    """Absence of the marker file is the default — selfheal proceeds."""
    assert not should_defer_selfheal_resurrection(tmp_path, "clustering")


def test_clear_unknown_stage_is_silent_noop(tmp_path: Path):
    """clear is called speculatively from the watcher — must tolerate
    being called for stages that were never rejected."""
    clear_guard_rejection(tmp_path, "deepening")  # no marker exists
    # No raise. No assertion needed; the test passes if no exception.


def test_clear_one_stage_preserves_others(tmp_path: Path):
    """When multiple stages are recorded, clearing one must not
    accidentally drop the others. Exercises the shared key-value
    store invariant under the watcher's concurrent-clear path."""
    record_guard_rejection(tmp_path, stage="clustering", reason="x")
    record_guard_rejection(tmp_path, stage="deepening", reason="y")
    clear_guard_rejection(tmp_path, "clustering")
    assert not should_defer_selfheal_resurrection(tmp_path, "clustering")
    assert should_defer_selfheal_resurrection(tmp_path, "deepening")
