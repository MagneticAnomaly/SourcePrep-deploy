"""Regression test: paused pipeline runs must survive daemon restart.

User-visible bug: pause mid-stage, restart the server, and the pipeline
auto-resumed past the paused stage instead of staying paused. The user
expectation — restated by the user — is:

    "What SHOULD happen is after the server restarted it should STILL be
     paused (or if the server crashed without me pausing it it should ALSO
     begin paused as a safety mechanism)."

Two failure modes were stacked:

1. `_auto_recover_stale_pipelines._is_active` excluded paused runs, so the
   recovery path's "skip if active" short-circuit failed to fire and
   `clear_paused_runs_fn` deleted the user's pause before triggering a
   fresh deep enrichment. (orchestrator.py:4063, recovery.py:1300)

2. `_start_group` only blocked on `is_active`, not `is_paused`. So even
   with #1 fixed, the parallel `_startup_auto_run` path could still call
   `run_deep_enrichment` and silently overwrite the hydrated pause with a
   fresh state machine. (orchestrator.py:1697-1699)

This test pins both invariants:

  A. With a paused run in `_runs`, `_start_group` for the same group must
     refuse and leave the paused state intact.
  B. With a paused run in `_runs`, `_auto_recover_stale_pipelines._is_active`
     must return True so the recovery path skips clear-and-resume.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from prep.services.pipeline.state_machine import (
    Event,
    PipelineGroupStateMachine,
)
from prep.services.pipeline_orchestrator import pipeline_orchestrator


def _make_paused_run(project_id: str, group: str, stage_index: int) -> PipelineGroupStateMachine:
    """Build a PipelineGroupStateMachine and drive it to PAUSED.

    Mirrors the user-paused path: START → PAUSE → STAGE_FLUSHED.
    """
    sm = PipelineGroupStateMachine(
        project_id=project_id,
        group=group,
        stages=["enrichment", "group_reasoning", "clustering", "deepening", "deep_knowledge"],
    )
    assert sm.transition(Event.START)
    sm.current_stage_index = stage_index
    assert sm.transition(Event.PAUSE)
    assert sm.transition(Event.STAGE_FLUSHED)
    assert sm.is_paused
    # Mark journal_run_id so the orchestrator doesn't classify this as a
    # synthetic-paused snapshot from hydration. We're modelling a real
    # user pause that survives restart.
    sm.journal_run_id = "test-journal-id"
    return sm


@pytest.fixture()
def clean_orchestrator():
    """Snapshot/restore _runs so tests don't leak state across each other."""
    snapshot = dict(pipeline_orchestrator._runs)
    pipeline_orchestrator._runs.clear()
    try:
        yield pipeline_orchestrator
    finally:
        pipeline_orchestrator._runs.clear()
        pipeline_orchestrator._runs.update(snapshot)


def test_start_group_refuses_to_overwrite_paused_run(clean_orchestrator):
    """Bug #2: _start_group must NOT silently overwrite a paused run.

    Under the old logic, hydration created a paused run, then the parallel
    _startup_auto_run path called run_deep_enrichment → _start_group →
    fresh state machine replaced the pause and the pipeline auto-resumed.
    """
    pid = "test-project-paused-restart"
    paused_run = _make_paused_run(pid, "deep_enrichment", stage_index=0)
    clean_orchestrator._runs[(pid, "deep_enrichment")] = paused_run

    # Bypass the project-active gate so the test focuses on the paused
    # check itself rather than registry bookkeeping.
    with patch.object(pipeline_orchestrator, "_check_project_active", return_value=True):
        # Calling _start_group directly with the same group must refuse.
        from prep.services.pipeline.stages import DEEP_ENRICHMENT_STAGES
        started = clean_orchestrator._start_group(
            pid, "deep_enrichment", DEEP_ENRICHMENT_STAGES, resume_from=0,
        )

    assert started is False, (
        "_start_group must refuse when the same group has a paused run — "
        "otherwise the hydrated pause is silently overwritten on restart"
    )
    # And critically, the paused run must still be in _runs.
    assert clean_orchestrator._runs[(pid, "deep_enrichment")] is paused_run
    assert clean_orchestrator._runs[(pid, "deep_enrichment")].is_paused


def test_auto_recover_is_active_callback_includes_paused(clean_orchestrator):
    """Bug #1: the auto-recover path's _is_active must include paused runs.

    Without this, `clear_paused_runs_fn` deletes the user's pause and
    `run_deep_enrichment_fn` starts a fresh resume. The two _is_active
    callbacks (hydrate's and auto_recover's) must agree on the definition
    so they don't contradict each other.
    """
    pid = "test-project-recover-skip"
    paused_run = _make_paused_run(pid, "deep_enrichment", stage_index=0)
    clean_orchestrator._runs[(pid, "deep_enrichment")] = paused_run

    # Capture the auto_recover callbacks by intercepting RecoveryManager.
    captured: dict = {}
    from prep.services.pipeline.recovery import RecoveryManager

    def _capture(**kwargs):
        captured.update(kwargs)

    with patch.object(RecoveryManager, "auto_recover_stale_pipelines", side_effect=_capture):
        clean_orchestrator._auto_recover_stale_pipelines()

    assert "is_run_active_fn" in captured, (
        "_auto_recover_stale_pipelines must pass an is_run_active_fn"
    )
    is_active = captured["is_run_active_fn"]
    assert is_active(pid) is True, (
        "_is_active must return True for paused runs so auto-recovery "
        "skips them — otherwise clear_paused_runs deletes the pause"
    )


def test_auto_recover_is_active_returns_false_for_unknown_project(clean_orchestrator):
    """Sanity check — auto-recovery still proceeds for projects with no runs."""
    from prep.services.pipeline.recovery import RecoveryManager

    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)

    with patch.object(RecoveryManager, "auto_recover_stale_pipelines", side_effect=_capture):
        clean_orchestrator._auto_recover_stale_pipelines()

    is_active = captured["is_run_active_fn"]
    assert is_active("project-with-no-runs") is False


# ── User pause marker → hydration → restart-paused chain ────────

def test_pause_writes_user_pause_marker(tmp_path, monkeypatch):
    """`_pause_group` must drop a marker so the next restart honors it.

    Without the marker, hydration in auto mode skips PAUSED creation
    (the Phase 118 U13 fast-path) and the pipeline auto-resumes —
    overriding the user's explicit pause intent.
    """
    from prep.services.pipeline import recovery as recovery_mod

    project_id = "test-pause-marker-write"
    fake_idx_dir = tmp_path / "idx"
    fake_idx_dir.mkdir()

    def _fake_resolve(pid):
        assert pid == project_id
        return fake_idx_dir

    monkeypatch.setattr(recovery_mod, "_resolve_idx_dir", _fake_resolve)

    written = recovery_mod.RecoveryManager.write_user_pause_marker(
        project_id, "deep_enrichment", stage="clustering",
    )
    assert written
    assert recovery_mod.RecoveryManager.check_user_pause_marker(project_id, "deep_enrichment")
    payload = recovery_mod.RecoveryManager.read_user_pause_marker(project_id, "deep_enrichment")
    assert payload["group"] == "deep_enrichment"
    assert payload["stage"] == "clustering"
    assert payload["user_initiated"] is True


def test_resume_clears_user_pause_marker(tmp_path, monkeypatch):
    """Resume must clear the marker so a subsequent restart does not
    re-pause a run the user just chose to continue."""
    from prep.services.pipeline import recovery as recovery_mod

    project_id = "test-pause-marker-clear"
    fake_idx_dir = tmp_path / "idx"
    fake_idx_dir.mkdir()
    monkeypatch.setattr(recovery_mod, "_resolve_idx_dir", lambda pid: fake_idx_dir)

    recovery_mod.RecoveryManager.write_user_pause_marker(
        project_id, "deep_enrichment", stage="clustering",
    )
    assert recovery_mod.RecoveryManager.check_user_pause_marker(project_id, "deep_enrichment")
    cleared = recovery_mod.RecoveryManager.clear_user_pause_marker(project_id, "deep_enrichment")
    assert cleared
    assert not recovery_mod.RecoveryManager.check_user_pause_marker(project_id, "deep_enrichment")


def test_hydration_creates_paused_run_when_user_pause_marker_present(
    tmp_path, monkeypatch, clean_orchestrator,
):
    """User-pause marker must override the auto-mode hydration skip.

    Reproduces the user's exact scenario: auto mode is on, the user
    paused mid-stage, the daemon restarted. Hydration MUST create a
    PAUSED state machine for the group so:

    1. The user sees the run as paused in the UI.
    2. _start_group's paused check (the previous fix) blocks
       _startup_auto_run from silently resuming.
    """
    from prep.services.pipeline import recovery as recovery_mod
    from prep.services.pipeline.recovery import RecoveryManager
    from prep.services.pipeline.stages import (
        DEEP_ENRICHMENT_STAGES,
        FAST_SYNC_STAGES,
    )

    project_id = "test-paused-hydration"
    fake_idx_dir = tmp_path / "idx"
    fake_idx_dir.mkdir()

    # Patch the recovery module's idx-dir resolver and project list.
    monkeypatch.setattr(recovery_mod, "_resolve_idx_dir", lambda pid: fake_idx_dir)

    class _FakeProject:
        id = project_id

    class _FakeRegistry:
        def list_projects(self):
            return [_FakeProject()]

    class _FakeSettings:
        def get(self, key):
            if key == "pipeline_config":
                # Auto mode ON for both groups — this is the exact
                # configuration that previously bypassed hydration.
                return {
                    "fast_sync": {"auto": True},
                    "deep_enrichment": {"mode": "auto"},
                }
            return None

    monkeypatch.setattr(
        "prep.services.project_helpers.get_registry",
        lambda: _FakeRegistry(),
    )
    monkeypatch.setattr(
        "prep.services.settings_store.settings",
        _FakeSettings(),
    )
    monkeypatch.setattr(
        "prep.services.project_helpers.get_project_activity_status",
        lambda pid: "active",
    )

    # User paused mid-stage (clustering = index 2 of DEEP_ENRICHMENT_STAGES).
    paused_stage_index = 2
    RecoveryManager.write_user_pause_marker(
        project_id, "deep_enrichment", stage=DEEP_ENRICHMENT_STAGES[paused_stage_index].value,
    )

    registered: list = []

    def _detect_resume(pid, stages, skip_mtime):
        # Simulate the resume detector finding partial state at the
        # paused stage for deep_enrichment, complete for fast_sync.
        if stages == list(FAST_SYNC_STAGES):
            return len(FAST_SYNC_STAGES)  # complete
        return paused_stage_index

    def _register(pid, group, sm):
        registered.append((pid, group, sm))

    RecoveryManager.hydrate_paused_runs_from_disk(
        detect_resume_fn=_detect_resume,
        register_run_fn=_register,
        is_run_active_fn=lambda pid: False,
        default_guard=clean_orchestrator._default_guard,
    )

    deep_runs = [r for r in registered if r[1] == "deep_enrichment"]
    assert len(deep_runs) == 1, (
        "Hydration must create exactly one paused deep_enrichment run "
        f"when the user-pause marker is present. Got registered={registered}"
    )
    pid_back, group_back, sm = deep_runs[0]
    assert pid_back == project_id
    assert group_back == "deep_enrichment"
    assert sm.is_paused
    assert sm.current_stage_index == paused_stage_index


def test_hydration_creates_paused_run_when_shutdown_was_unclean(
    tmp_path, monkeypatch, clean_orchestrator,
):
    """Safety mechanism: a partial run with no clean-shutdown marker
    surfaces as PAUSED so the user must explicitly resume after a crash.
    """
    from prep.services.pipeline import recovery as recovery_mod
    from prep.services.pipeline.stages import (
        DEEP_ENRICHMENT_STAGES,
        FAST_SYNC_STAGES,
    )

    project_id = "test-crash-safety"
    fake_idx_dir = tmp_path / "idx"
    fake_idx_dir.mkdir()
    # Note: NO clean-shutdown marker, NO user-pause marker.

    monkeypatch.setattr(recovery_mod, "_resolve_idx_dir", lambda pid: fake_idx_dir)

    class _FakeProject:
        id = project_id

    class _FakeRegistry:
        def list_projects(self):
            return [_FakeProject()]

    class _FakeSettings:
        def get(self, key):
            if key == "pipeline_config":
                return {
                    "fast_sync": {"auto": True},
                    "deep_enrichment": {"mode": "auto"},
                }
            return None

    monkeypatch.setattr(
        "prep.services.project_helpers.get_registry",
        lambda: _FakeRegistry(),
    )
    monkeypatch.setattr(
        "prep.services.settings_store.settings",
        _FakeSettings(),
    )
    monkeypatch.setattr(
        "prep.services.project_helpers.get_project_activity_status",
        lambda pid: "active",
    )

    paused_stage_index = 1

    def _detect_resume(pid, stages, skip_mtime):
        if stages == list(FAST_SYNC_STAGES):
            return len(FAST_SYNC_STAGES)
        return paused_stage_index

    registered: list = []
    recovery_mod.RecoveryManager.hydrate_paused_runs_from_disk(
        detect_resume_fn=_detect_resume,
        register_run_fn=lambda pid, group, sm: registered.append((pid, group, sm)),
        is_run_active_fn=lambda pid: False,
        default_guard=clean_orchestrator._default_guard,
    )

    deep_runs = [r for r in registered if r[1] == "deep_enrichment"]
    assert len(deep_runs) == 1, (
        "Crash safety: a partial run with no clean-shutdown marker "
        "must surface as PAUSED on restart. "
        f"registered={registered}"
    )
    assert deep_runs[0][2].is_paused


def test_hydration_pauses_partial_state_even_on_clean_shutdown(
    tmp_path, monkeypatch, clean_orchestrator,
):
    """Per direct user request: PAUSED is the default state after server
    restart. ANY partial state hydrates as PAUSED, even when shutdown was
    clean and there's no user-pause marker. The previous behavior (let
    auto-mode silently restart on clean-shutdown + partial) was the
    "stages keep getting skipped after restart" report; this test pins
    the simpler always-paused rule.
    """
    from prep.services.pipeline import recovery as recovery_mod
    from prep.services.pipeline.recovery import RecoveryManager
    from prep.services.pipeline.stages import (
        DEEP_ENRICHMENT_STAGES,
        FAST_SYNC_STAGES,
    )

    project_id = "test-clean-shutdown-still-paused"
    fake_idx_dir = tmp_path / "idx"
    fake_idx_dir.mkdir()
    monkeypatch.setattr(recovery_mod, "_resolve_idx_dir", lambda pid: fake_idx_dir)

    class _FakeProject:
        id = project_id

    class _FakeRegistry:
        def list_projects(self):
            return [_FakeProject()]

    class _FakeSettings:
        def get(self, key):
            if key == "pipeline_config":
                return {
                    "fast_sync": {"auto": True},
                    "deep_enrichment": {"mode": "auto"},
                }
            return None

    monkeypatch.setattr(
        "prep.services.project_helpers.get_registry",
        lambda: _FakeRegistry(),
    )
    monkeypatch.setattr(
        "prep.services.settings_store.settings",
        _FakeSettings(),
    )
    monkeypatch.setattr(
        "prep.services.project_helpers.get_project_activity_status",
        lambda pid: "active",
    )

    # Simulate a clean shutdown — the marker IS present.
    RecoveryManager.write_clean_shutdown_marker(project_id)

    paused_stage_index = 2

    def _detect_resume(pid, stages, skip_mtime):
        if stages == list(FAST_SYNC_STAGES):
            return len(FAST_SYNC_STAGES)
        return paused_stage_index

    registered: list = []
    RecoveryManager.hydrate_paused_runs_from_disk(
        detect_resume_fn=_detect_resume,
        register_run_fn=lambda pid, group, sm: registered.append((pid, group, sm)),
        is_run_active_fn=lambda pid: False,
        default_guard=clean_orchestrator._default_guard,
    )

    deep_runs = [r for r in registered if r[1] == "deep_enrichment"]
    assert len(deep_runs) == 1, (
        "Clean shutdown + partial state must still hydrate as PAUSED — "
        "auto mode does not silently resume incomplete work after restart"
    )
    assert deep_runs[0][2].is_paused
    assert deep_runs[0][2].current_stage_index == paused_stage_index


def test_hydration_pauses_at_stage_zero_when_user_marker_present(
    tmp_path, monkeypatch, clean_orchestrator,
):
    """Edge case: user paused at the very first stage of a group before any
    manifest was written (resume detector returns 0). Without the marker
    this looks identical to a fresh project; with the marker we must still
    hydrate as PAUSED at stage 0 so the user's intent is honored.
    """
    from prep.services.pipeline import recovery as recovery_mod
    from prep.services.pipeline.recovery import RecoveryManager
    from prep.services.pipeline.stages import (
        DEEP_ENRICHMENT_STAGES,
        FAST_SYNC_STAGES,
    )

    project_id = "test-pause-at-stage-zero"
    fake_idx_dir = tmp_path / "idx"
    fake_idx_dir.mkdir()
    monkeypatch.setattr(recovery_mod, "_resolve_idx_dir", lambda pid: fake_idx_dir)

    class _FakeProject:
        id = project_id

    class _FakeRegistry:
        def list_projects(self):
            return [_FakeProject()]

    class _FakeSettings:
        def get(self, key):
            return None

    monkeypatch.setattr("prep.services.project_helpers.get_registry", lambda: _FakeRegistry())
    monkeypatch.setattr("prep.services.settings_store.settings", _FakeSettings())
    monkeypatch.setattr(
        "prep.services.project_helpers.get_project_activity_status",
        lambda pid: "active",
    )

    # User paused at the FIRST stage — no completed work, no manifest.
    RecoveryManager.write_user_pause_marker(
        project_id, "deep_enrichment", stage=DEEP_ENRICHMENT_STAGES[0].value,
    )

    def _detect_resume(pid, stages, skip_mtime):
        if stages == list(FAST_SYNC_STAGES):
            return len(FAST_SYNC_STAGES)
        return 0  # nothing completed yet

    registered: list = []
    RecoveryManager.hydrate_paused_runs_from_disk(
        detect_resume_fn=_detect_resume,
        register_run_fn=lambda pid, group, sm: registered.append((pid, group, sm)),
        is_run_active_fn=lambda pid: False,
        default_guard=clean_orchestrator._default_guard,
    )

    deep_runs = [r for r in registered if r[1] == "deep_enrichment"]
    assert len(deep_runs) == 1, (
        "User-pause marker at stage 0 must still hydrate as PAUSED — "
        f"otherwise paused-at-first-stage gets silently auto-started. registered={registered}"
    )
    assert deep_runs[0][2].is_paused
    assert deep_runs[0][2].current_stage_index == 0


def test_hydration_clears_stale_marker_when_group_complete(
    tmp_path, monkeypatch, clean_orchestrator,
):
    """If the marker is present but the group is fully complete (e.g. user
    paused, resumed, completed all stages — but the resume path failed to
    clear the marker), the hydration loop must clear the stale marker and
    NOT create a paused run on a finished group.
    """
    from prep.services.pipeline import recovery as recovery_mod
    from prep.services.pipeline.recovery import RecoveryManager
    from prep.services.pipeline.stages import (
        DEEP_ENRICHMENT_STAGES,
        FAST_SYNC_STAGES,
    )

    project_id = "test-stale-marker-cleanup"
    fake_idx_dir = tmp_path / "idx"
    fake_idx_dir.mkdir()
    monkeypatch.setattr(recovery_mod, "_resolve_idx_dir", lambda pid: fake_idx_dir)

    class _FakeProject:
        id = project_id

    class _FakeRegistry:
        def list_projects(self):
            return [_FakeProject()]

    class _FakeSettings:
        def get(self, key):
            return None

    monkeypatch.setattr("prep.services.project_helpers.get_registry", lambda: _FakeRegistry())
    monkeypatch.setattr("prep.services.settings_store.settings", _FakeSettings())
    monkeypatch.setattr(
        "prep.services.project_helpers.get_project_activity_status",
        lambda pid: "active",
    )

    RecoveryManager.write_user_pause_marker(
        project_id, "deep_enrichment", stage="clustering",
    )
    assert RecoveryManager.check_user_pause_marker(project_id, "deep_enrichment")

    def _detect_resume(pid, stages, skip_mtime):
        return len(stages)  # everything complete

    registered: list = []
    RecoveryManager.hydrate_paused_runs_from_disk(
        detect_resume_fn=_detect_resume,
        register_run_fn=lambda pid, group, sm: registered.append((pid, group, sm)),
        is_run_active_fn=lambda pid: False,
        default_guard=clean_orchestrator._default_guard,
    )

    assert registered == [], "Stale marker on a complete group must NOT hydrate"
    assert not RecoveryManager.check_user_pause_marker(project_id, "deep_enrichment"), (
        "Stale marker must be cleaned up so it does not keep producing "
        "ghost paused runs on every restart"
    )


def test_resume_writes_rebuild_barrier_for_visual_styling(
    tmp_path, monkeypatch, clean_orchestrator,
):
    """Pin the rebuild-styling fix: resume_paused must write a rebuild
    barrier (when one isn't already active) so the dashboard renders
    the run with the rebuild progress styling. The barrier auto-clears
    on group completion via maybe_clear_scoped_barrier so this is
    self-cleaning.
    """
    from prep.services.pipeline import recovery as recovery_mod
    from prep.services.pipeline.recovery import RecoveryManager
    from prep.services.pipeline_orchestrator import pipeline_orchestrator

    project_id = "test-resume-writes-barrier"
    fake_idx_dir = tmp_path / "idx"
    fake_idx_dir.mkdir()
    monkeypatch.setattr(recovery_mod, "_resolve_idx_dir", lambda pid: fake_idx_dir)

    paused_run = _make_paused_run(project_id, "deep_enrichment", stage_index=2)
    clean_orchestrator._runs[(project_id, "deep_enrichment")] = paused_run

    # Sanity: no barrier active before resume.
    assert RecoveryManager.check_clean_shutdown_marker(project_id) is False

    advanced: list = []
    monkeypatch.setattr(
        pipeline_orchestrator, "_advance_pipeline",
        lambda run: advanced.append(run),
    )

    ok = pipeline_orchestrator.resume_paused(project_id, "deep_enrichment")
    assert ok
    assert len(advanced) == 1, "_advance_pipeline must fire on resume"

    from prep.services.pipeline.recovery import read_reset_barrier
    barrier = read_reset_barrier(project_id)
    assert barrier is not None, "resume must write a rebuild barrier"
    assert barrier["reason"] == "rebuild"
    assert barrier["scope"] == "enrichment"


def test_hydration_skips_when_no_partial_state(
    tmp_path, monkeypatch, clean_orchestrator,
):
    """Cleanly-idle projects (no partial state) must NOT hydrate as paused —
    auto mode is still allowed to trigger fresh runs on idle projects.
    """
    from prep.services.pipeline import recovery as recovery_mod
    from prep.services.pipeline.stages import (
        DEEP_ENRICHMENT_STAGES,
        FAST_SYNC_STAGES,
    )

    project_id = "test-fully-idle"
    fake_idx_dir = tmp_path / "idx"
    fake_idx_dir.mkdir()
    monkeypatch.setattr(recovery_mod, "_resolve_idx_dir", lambda pid: fake_idx_dir)

    class _FakeProject:
        id = project_id

    class _FakeRegistry:
        def list_projects(self):
            return [_FakeProject()]

    class _FakeSettings:
        def get(self, key):
            return None

    monkeypatch.setattr(
        "prep.services.project_helpers.get_registry",
        lambda: _FakeRegistry(),
    )
    monkeypatch.setattr(
        "prep.services.settings_store.settings",
        _FakeSettings(),
    )
    monkeypatch.setattr(
        "prep.services.project_helpers.get_project_activity_status",
        lambda pid: "active",
    )

    # Resume detector reports "all complete" — nothing to do.
    def _detect_resume(pid, stages, skip_mtime):
        return len(stages)

    registered: list = []
    recovery_mod.RecoveryManager.hydrate_paused_runs_from_disk(
        detect_resume_fn=_detect_resume,
        register_run_fn=lambda pid, group, sm: registered.append((pid, group, sm)),
        is_run_active_fn=lambda pid: False,
        default_guard=clean_orchestrator._default_guard,
    )

    assert registered == [], (
        "Fully-idle projects must not hydrate paused runs — that would "
        "create ghost paused runs the user never started"
    )
