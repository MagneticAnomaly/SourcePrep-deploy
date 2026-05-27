"""Regression tests for the journal-on-WriteGuardBlocked path.

2026-05-26 incident: ``_attempt_write_guard_recovery`` returned True on
a phantom restore (10 unrelated files "RESTORED" while the actually
shrunken file was untouched).  Even if recovery had returned False —
which Fix #2 now ensures it does — the ``_WriteGuardBlocked`` handler
called ``_journal_run_completed`` instead of marking the run failed.
That helper:

  1. Wrote ``status='completed'`` to the journal (lie #1).
  2. If the group was ``deep_enrichment``, promoted the on-disk state
     to ``_golden/`` (lie #2 — saved a corrupted snapshot as
     known-good).

Fix #4 added ``_journal_run_failed`` which calls
``journal.stage_failed`` and explicitly does NOT promote a golden.
These tests pin the corrected behavior.
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch


def test_journal_run_failed_exists_on_orchestrator():
    """The helper introduced by Fix #4 must exist."""
    from prep.services.pipeline.orchestrator import PipelineOrchestrator
    assert hasattr(PipelineOrchestrator, "_journal_run_failed"), (
        "PipelineOrchestrator._journal_run_failed missing — Fix #4 regressed"
    )


def test_journal_run_failed_calls_stage_failed():
    """The helper must call journal.stage_failed with stage + error.

    A correct implementation never calls journal.run_completed on the
    failure path — that was the 2026-05-26 bug.
    """
    from prep.services.pipeline.orchestrator import PipelineOrchestrator
    from prep.services.pipeline.stages import StageId

    # Construct a fake run with the minimum the helper touches.
    run = MagicMock()
    run.journal_run_id = "run-abc123"

    with patch("prep.services.pipeline_journal.journal") as mock_journal:
        # The helper is bound to ``self`` but doesn't actually use it,
        # so we can call it as an unbound function with a sentinel self.
        PipelineOrchestrator._journal_run_failed(
            MagicMock(),  # self
            run,
            StageId.GROUP_REASONING,
            "WRITE GUARD BLOCKED: shrank 166→61",
        )

    mock_journal.stage_failed.assert_called_once_with(
        "run-abc123",
        "group_reasoning",
        "WRITE GUARD BLOCKED: shrank 166→61",
    )
    # The cardinal sin Fix #4 prevents: NEVER call run_completed on
    # the failure path.
    assert not mock_journal.run_completed.called, (
        "journal.run_completed must NOT be called from the "
        "write-guard-blocked path — see Fix #4."
    )


def test_journal_run_failed_does_not_create_golden_checkpoint():
    """Fix #4 critical invariant: the failure path must not promote
    a golden checkpoint.  ``_journal_run_completed`` DOES create a
    golden when the group is deep_enrichment; the new
    ``_journal_run_failed`` must NOT.
    """
    from prep.services.pipeline.orchestrator import PipelineOrchestrator
    from prep.services.pipeline.stages import StageId

    run = MagicMock()
    run.journal_run_id = "run-abc123"
    run.group = "deep_enrichment"

    # Patch both modules so we can detect ANY call to checkpoint helpers.
    with patch("prep.services.pipeline_journal.journal"), \
         patch("prep.services.pipeline_checkpoint.create_golden_checkpoint") as gold, \
         patch("prep.services.pipeline_checkpoint.cleanup_checkpoint") as cleanup, \
         patch("prep.services.pipeline_checkpoint.prune_old_checkpoints") as prune:
        PipelineOrchestrator._journal_run_failed(
            MagicMock(),
            run,
            StageId.GROUP_REASONING,
            "WRITE GUARD BLOCKED: shrank 166→61",
        )

    assert not gold.called, (
        "create_golden_checkpoint must NOT be called on the failure "
        "path — promoting corrupted state to golden was the 2026-05-26 "
        "data-poisoning bug."
    )
    # The run checkpoint should also be preserved (not cleaned up) so the
    # user has a recovery option.
    assert not cleanup.called, (
        "Run checkpoint should not be deleted on the failure path — "
        "preserve it for inspection / manual recovery."
    )
    assert not prune.called


def test_write_guard_blocked_handler_uses_failed_path():
    """Static check: the ``except _WriteGuardBlocked`` block must call
    ``_journal_run_failed`` and NOT ``_journal_run_completed``.

    A static check rather than a behavioral one because instantiating
    the full PipelineOrchestrator for an end-to-end trigger is
    high-cost.  The two helpers are pin-tested separately above; this
    test verifies the wiring.
    """
    import prep.services.pipeline.orchestrator as orch_mod

    src = inspect.getsource(orch_mod.PipelineOrchestrator)
    # Slice out the block between the try/except for WriteGuardBlocked
    # and the next except. This is the failure handler.
    marker = "except _WriteGuardBlocked"
    assert marker in src, f"missing '{marker}' in PipelineOrchestrator"
    after = src.split(marker, 1)[1]
    handler = after.split("except Exception", 1)[0]

    # Strip comments and docstrings so we don't trip on rationale text
    # that mentions the helper names.
    code_lines = []
    for line in handler.splitlines():
        stripped = line.split("#", 1)[0]  # drop trailing comments
        code_lines.append(stripped)
    code = "\n".join(code_lines)

    assert "self._journal_run_failed(" in code, (
        "WriteGuardBlocked handler must call self._journal_run_failed(...)"
    )
    assert "self._journal_run_completed(" not in code, (
        "WriteGuardBlocked handler must NOT call self._journal_run_completed(...) "
        "— doing so writes status='completed' for a failed stage AND "
        "promotes a golden checkpoint from corrupted state (2026-05-26 bug)"
    )
