"""
Phase 145 — auto-incremental gate fixes (§2q/§2s).

Covers the four fix areas from
docs/Phase145_Pipeline-UI-Reliability/PROPOSAL_auto-incremental-three-gates-v2.md:

- A1: watch.py trigger_build returns the actual run_fast_sync result
  (RC#2 — silent pending-set drop).
- A2: the coverage-check "close enough" gate is replaced by an
  unchanged-untracked-set loop guard (RC#1).
- A3: run_fast_sync's downstream guard force-resets stale blocking runs
  and only treats orphan-able partial data as a stub-extrapolation risk
  (RC#3 — the live blocker was a finalize run stuck "queued").
- A4: the watcher's debounce re-queue backs off exponentially on
  repeated trigger refusals instead of re-firing every debounce_ms.

Run with: pytest tests/test_phase145_auto_incremental_gates.py -v
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prep.core.watcher import AutoRebuildWatcher
from prep.services.pipeline.orchestrator import PipelineOrchestrator
from prep.services.pipeline.stages import (
    DEEP_ENRICHMENT_STAGES,
    FINALIZE_STAGES,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def watcher_setup(tmp_path: Path):
    """Minimal watcher with a repo policy, not started (no Observer)."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n")

    idx_dir = tmp_path / "index"
    idx_dir.mkdir()
    (idx_dir / "repo_policy.json").write_text(json.dumps({
        "version": "1.0",
        "repo_root": str(repo),
        "include_globs": ["**/*.py"],
        "exclude_globs": [],
    }))

    trigger = MagicMock(return_value=True)
    is_building = MagicMock(return_value=False)

    watcher = AutoRebuildWatcher(
        repo_root=repo,
        index_dir=idx_dir,
        on_trigger_build=trigger,
        is_building=is_building,
        debounce_ms=100,
        min_rebuild_gap_ms=50,
        project_id="test-proj",
    )
    # Enable without start() so no Observer/coverage timers spin up.
    watcher._enabled = True
    watcher._state = "idle"

    yield {
        "watcher": watcher,
        "repo": repo,
        "idx_dir": idx_dir,
        "trigger": trigger,
        "is_building": is_building,
    }
    watcher._enabled = False
    for t in (watcher._timer, watcher._coverage_timer):
        if t is not None:
            try:
                t.cancel()
            except Exception:
                pass


@pytest.fixture
def mock_orchestrator():
    """Patch the pipeline_orchestrator singleton the watcher imports lazily."""
    with patch("prep.services.pipeline_orchestrator.pipeline_orchestrator") as po:
        po._is_fast_sync_auto.return_value = True
        po.status.return_value = {"any_running": False}
        po.force_reset_stale_runs.return_value = []
        yield po


def _run_coverage_check(watcher):
    """Run one coverage-check cycle against a mocked orchestrator."""
    watcher._on_coverage_check()


# ── A1: trigger_build returns the actual started value ───────────


class _TriggerPatchStack:
    """Call-time patches the trigger_build closure needs.  The closure
    lazy-imports its dependencies on every invocation, so the patches
    must be active when it's *called*, not when the route runs."""

    def __enter__(self):
        from prep.api.routers.projects import watch as watch_mod

        self._activity = patch(
            "prep.services.project_helpers.get_project_activity_status",
            return_value="active",
        )
        self._feature = patch(
            "prep.core.feature_gate.check_feature", return_value=True,
        )
        self._orch = patch(
            "prep.services.pipeline_orchestrator.pipeline_orchestrator",
        )
        self._srv = patch.object(watch_mod, "_srv", return_value=MagicMock())

        self._activity.start()
        self._feature.start()
        po = self._orch.start()
        self._srv.start()
        return po

    def __exit__(self, *exc):
        self._srv.stop()
        self._orch.stop()
        self._feature.stop()
        self._activity.stop()
        return False


class TestA1TriggerBuildReturn:
    """watch.py trigger_build must propagate run_fast_sync's bool."""

    def _invoke_route_and_capture_trigger(self):
        """Call start_project_watch with everything mocked; return the
        on_trigger_build closure handed to AutoRebuildWatcher."""
        from prep.api.routers.projects import watch as watch_mod

        proj = MagicMock()
        proj.id = "p1"
        proj.path = "/tmp/nonexistent"
        proj.config = {
            "trace": {"enabled": True},
            "auto_config": {"fastSync": True},
        }

        srv = MagicMock()
        srv._project_watchers = {}
        idx = MagicMock()
        idx.index_dir = Path("/tmp/nonexistent-idx")
        srv._get_project_index.return_value = idx

        with (
            patch.object(watch_mod, "require_feature"),
            patch.object(watch_mod, "_srv", return_value=srv),
            patch.object(watch_mod, "_get_project_globs", return_value=([], [])),
            patch.object(watch_mod, "AutoRebuildWatcher") as watcher_cls,
            patch(
                "prep.services.project_helpers.require_project_writable",
                return_value=proj,
            ),
            patch(
                "prep.services.project_helpers.get_project_activity_status",
                return_value="active",
            ),
            patch("prep.core.feature_gate.check_feature", return_value=True),
        ):
            watcher_inst = watcher_cls.return_value
            watcher_inst.status.return_value = {"state": "idle"}
            watch_mod.start_project_watch("p1")

        return watcher_cls.call_args.kwargs["on_trigger_build"]

    def test_returns_false_when_run_fast_sync_refuses(self):
        trigger = self._invoke_route_and_capture_trigger()
        with _TriggerPatchStack() as po:
            po._is_fast_sync_auto.return_value = True
            po.run_fast_sync.return_value = False
            assert trigger(["a.py"]) is False
            po.run_fast_sync.assert_called_once_with("p1")

    def test_returns_true_when_run_fast_sync_starts(self):
        trigger = self._invoke_route_and_capture_trigger()
        with _TriggerPatchStack() as po:
            po._is_fast_sync_auto.return_value = True
            po.run_fast_sync.return_value = True
            assert trigger(["a.py"]) is True

    def test_exception_falls_back_to_legacy_and_returns_true(self):
        trigger = self._invoke_route_and_capture_trigger()
        with _TriggerPatchStack() as po:
            po._is_fast_sync_auto.return_value = True
            po.run_fast_sync.side_effect = RuntimeError("boom")
            assert trigger(["a.py"]) is True


# ── A4: debounce re-queue backoff on refused triggers ────────────


class TestA4DebounceBackoff:
    """A refused trigger must re-queue pending paths and back off."""

    def test_refused_trigger_requeues_and_backs_off(self, watcher_setup):
        watcher = watcher_setup["watcher"]
        trigger = watcher_setup["trigger"]
        trigger.return_value = False

        with patch("prep.core.watcher.threading.Timer") as timer_cls:
            watcher._pending_paths = {"a.py", "b.py"}
            watcher._on_debounce_fire()

            # Pending paths preserved, not silently dropped (RC#2).
            assert watcher._pending_paths == {"a.py", "b.py"}
            assert watcher._consecutive_trigger_failures == 1
            assert watcher._state == "debouncing"
            # First retry at base delay.
            assert timer_cls.call_args.args[0] == pytest.approx(0.1)

            # Second refusal doubles the delay.
            watcher._on_debounce_fire()
            assert watcher._consecutive_trigger_failures == 2
            assert timer_cls.call_args.args[0] == pytest.approx(0.2)

    def test_successful_trigger_resets_backoff(self, watcher_setup):
        watcher = watcher_setup["watcher"]
        trigger = watcher_setup["trigger"]

        # Patch Thread as well so _wait_for_build_complete doesn't race
        # the assertions (is_building is False, so it would immediately
        # flip the state back to idle).
        with (
            patch("prep.core.watcher.threading.Timer"),
            patch("prep.core.watcher.threading.Thread"),
        ):
            watcher._consecutive_trigger_failures = 3
            trigger.return_value = True
            watcher._pending_paths = {"a.py"}
            watcher._on_debounce_fire()

            assert watcher._consecutive_trigger_failures == 0
            assert watcher._state == "building"
            assert watcher._pending_paths == set()

    def test_backoff_caps_at_five_minutes(self, watcher_setup):
        watcher = watcher_setup["watcher"]
        watcher_setup["trigger"].return_value = False

        with patch("prep.core.watcher.threading.Timer") as timer_cls:
            watcher._consecutive_trigger_failures = 20  # way past cap
            watcher._pending_paths = {"a.py"}
            watcher._on_debounce_fire()
            delay = timer_cls.call_args.args[0]
            assert delay == watcher._TRIGGER_FAILURE_BACKOFF_CAP_SECONDS


# ── A2: coverage-check loop guard (close-enough gate removed) ────


class TestA2CoverageLoopGuard:
    """The coverage backstop must trigger for eligible untraced source
    files regardless of coverage %, and only back off when the untraced
    set is unchanged after a coverage-triggered rebuild."""

    def _gap(self, untraced=9, stale=0, pct=99.1, paths=None):
        return {
            "untraced": untraced,
            "stale": stale,
            "coverage_pct": pct,
            "needs_rebuild": (untraced + stale) > 0,
            "changed_paths": set(paths or []),
        }

    def test_high_coverage_few_untracked_source_triggers(
        self, watcher_setup, mock_orchestrator
    ):
        """The §2q scenario: 9 untraced .py/.md, 99.1% coverage, 0 stale.
        Pre-145 the close-enough gate suppressed this forever."""
        watcher = watcher_setup["watcher"]
        mock_orchestrator.check_coverage_gap.return_value = self._gap(
            paths={f"pkg/mod{i}.py" for i in range(9)},
        )
        _run_coverage_check(watcher)
        watcher_setup["trigger"].assert_called_once_with(["__coverage_gap__"])
        # Successful trigger consumes the cooldown and records the sig.
        assert watcher._last_coverage_trigger_at > 0
        assert watcher._last_coverage_trigger_sig == frozenset(
            f"pkg/mod{i}.py" for i in range(9)
        )

    def test_unchanged_untracked_set_backs_off(
        self, watcher_setup, mock_orchestrator
    ):
        """Same untraced set after a triggered rebuild → untraceable;
        suppress with escalating backoff instead of a 30-min loop."""
        watcher = watcher_setup["watcher"]
        paths = {f"pkg/mod{i}.py" for i in range(9)}
        mock_orchestrator.check_coverage_gap.return_value = self._gap(paths=paths)

        _run_coverage_check(watcher)  # triggers
        # Bypass the base cooldown to simulate the next eligible cycle.
        watcher._last_coverage_trigger_at = 0.0
        watcher_setup["trigger"].reset_mock()

        _run_coverage_check(watcher)  # same set → suppressed
        watcher_setup["trigger"].assert_not_called()
        assert watcher._coverage_loop_skips == 1
        assert watcher._coverage_suppress_until > time.time()

    def test_changed_untracked_set_retriggers(
        self, watcher_setup, mock_orchestrator
    ):
        watcher = watcher_setup["watcher"]
        mock_orchestrator.check_coverage_gap.return_value = self._gap(
            paths={"a.py"},
        )
        _run_coverage_check(watcher)
        watcher._last_coverage_trigger_at = 0.0
        watcher_setup["trigger"].reset_mock()

        # A different untraced set means progress — trigger again.
        mock_orchestrator.check_coverage_gap.return_value = self._gap(
            untraced=10, paths={"a.py", "b.py"},
        )
        _run_coverage_check(watcher)
        watcher_setup["trigger"].assert_called_once_with(["__coverage_gap__"])

    def test_stale_files_always_trigger(self, watcher_setup, mock_orchestrator):
        """stale > 0 bypasses the loop guard entirely — stale files are
        re-runnable by definition."""
        watcher = watcher_setup["watcher"]
        watcher._last_coverage_trigger_sig = frozenset({"a.py"})
        mock_orchestrator.check_coverage_gap.return_value = self._gap(
            untraced=9, stale=2, paths={"a.py", "c.py"},
        )
        _run_coverage_check(watcher)
        watcher_setup["trigger"].assert_called_once_with(["__coverage_gap__"])

    def test_refused_trigger_does_not_consume_cooldown(
        self, watcher_setup, mock_orchestrator
    ):
        """RC#2 follow-through: a refused coverage trigger must not burn
        the 30-min cooldown — the next 5-min cycle retries."""
        watcher = watcher_setup["watcher"]
        watcher_setup["trigger"].return_value = False
        mock_orchestrator.check_coverage_gap.return_value = self._gap(
            paths={"a.py"},
        )
        _run_coverage_check(watcher)
        assert watcher._last_coverage_trigger_at == 0.0
        assert watcher._last_coverage_trigger_sig is None

    def test_stale_any_running_run_is_force_reset(
        self, watcher_setup, mock_orchestrator
    ):
        """RC#3 backstop: a stale queued/orphaned run reports
        any_running forever and would suppress this check (and the
        heartbeat watchdog) indefinitely. Force-reset it and proceed."""
        watcher = watcher_setup["watcher"]
        mock_orchestrator.status.side_effect = [
            {"any_running": True},   # first look: stale run present
            {"any_running": False},  # after force-reset: clear
        ]
        mock_orchestrator.force_reset_stale_runs.return_value = ["finalize"]
        mock_orchestrator.check_coverage_gap.return_value = self._gap(
            paths={"a.py"},
        )
        _run_coverage_check(watcher)
        mock_orchestrator.force_reset_stale_runs.assert_called_once_with(
            "test-proj"
        )
        watcher_setup["trigger"].assert_called_once_with(["__coverage_gap__"])


# ── A3: run_fast_sync downstream guard ───────────────────────────


class TestA3StubExtrapolationRisk:
    """_has_stub_extrapolation_risk mirrors selfheal's orphan rule:
    dedicated output file present (>1 KiB) + no provenance manifest."""

    def _orch(self):
        # The helper touches no instance state; bypass __init__.
        return PipelineOrchestrator.__new__(PipelineOrchestrator)

    def _patch_project(self, tmp_path):
        idx_dir = tmp_path / "idx"
        idx_dir.mkdir()
        proj = MagicMock()
        proj.path = str(tmp_path)
        return (
            patch(
                "prep.services.project_helpers.require_project",
                return_value=proj,
            ),
            patch(
                "prep.core.project_registry.project_index_dir",
                return_value=str(idx_dir),
            ),
            idx_dir,
        )

    def test_antibodies_incomplete_no_outputs_not_blocking(self, tmp_path):
        """The §2n shape: finalize_resume=4 (antibodies manifest missing),
        no antibodies output files → NOT a stub-extrapolation risk."""
        orch = self._orch()
        p1, p2, _ = self._patch_project(tmp_path)
        with p1, p2:
            assert orch._has_stub_extrapolation_risk(
                "p1", FINALIZE_STAGES, 4,
            ) is False

    def test_shared_output_stage_never_blocking(self, tmp_path):
        """deep_resume=3 → deepening/deep_knowledge incomplete.  Their
        'output' (trace_epistemic.jsonl, knowledge_*) belongs to earlier
        stages — its presence must NOT count as partial data."""
        orch = self._orch()
        p1, p2, idx_dir = self._patch_project(tmp_path)
        # enrichment's complete output exists (deep_resume=3 implies it ran)
        (idx_dir / "trace_epistemic.jsonl").write_bytes(b"x" * 4096)
        with p1, p2:
            assert orch._has_stub_extrapolation_risk(
                "p1", DEEP_ENRICHMENT_STAGES, 3,
            ) is False

    def test_orphan_output_with_missing_manifest_is_blocking(self, tmp_path):
        """The real Phase 98 concern: group_reasoning's dedicated output
        exists on disk but its manifest is gone → selfheal would stub it."""
        orch = self._orch()
        p1, p2, idx_dir = self._patch_project(tmp_path)
        (idx_dir / "trace_group_reasoning.jsonl").write_bytes(b"x" * 4096)
        with p1, p2:
            assert orch._has_stub_extrapolation_risk(
                "p1", DEEP_ENRICHMENT_STAGES, 1,
            ) is True

    def test_small_orphan_output_not_blocking(self, tmp_path):
        """Selfheal's orphan rule requires >1 KiB; match it."""
        orch = self._orch()
        p1, p2, idx_dir = self._patch_project(tmp_path)
        (idx_dir / "trace_group_reasoning.jsonl").write_bytes(b"x" * 100)
        with p1, p2:
            assert orch._has_stub_extrapolation_risk(
                "p1", DEEP_ENRICHMENT_STAGES, 1,
            ) is False

    def test_error_is_conservative(self, tmp_path):
        orch = self._orch()
        with patch(
            "prep.services.project_helpers.require_project",
            side_effect=RuntimeError("no project"),
        ):
            assert orch._has_stub_extrapolation_risk(
                "p1", FINALIZE_STAGES, 4,
            ) is True


class TestA3BlockingRunLiveness:
    """A stale active downstream run (queued forever / crashed worker)
    must not block incremental fast_sync; a genuinely active or
    user-paused run still blocks."""

    def _orch(self, fast_resume=5):
        orch = PipelineOrchestrator.__new__(PipelineOrchestrator)
        orch._lock = threading.Lock()
        orch._runs = {}
        orch._force_from_start_runs = set()
        orch._changed_paths = {}
        orch._incremental_runs = set()
        orch._check_project_active = MagicMock(return_value=True)
        orch._selfheal_group = MagicMock()
        orch._detect_resume_point = MagicMock(return_value=fast_resume)
        orch._get_file_logger = MagicMock(return_value=None)
        orch._persist_incremental_flag = MagicMock()
        orch._start_group = MagicMock(return_value=True)
        orch.check_coverage_gap = MagicMock(return_value={
            "needs_rebuild": True, "stale": 1, "untraced": 0,
            "changed_paths": {"x.py"}, "coverage_pct": 99.0,
        })
        return orch

    def _fake_run(self, state_value: str):
        run = MagicMock()
        run.is_active = state_value != "paused"
        run.is_paused = state_value == "paused"
        run.state = MagicMock(value=state_value)
        return run

    def test_stale_queued_finalize_run_is_reset_and_run_proceeds(self):
        """The live §2s blocker: finalize stuck 'queued' with all
        manifests 5/5. The guard must force-reset and proceed."""
        orch = self._orch()
        orch._runs[("p1", "finalize")] = self._fake_run("queued")
        orch.force_reset_stale_runs = MagicMock(return_value=["finalize"])

        assert orch.run_fast_sync("p1") is True
        orch.force_reset_stale_runs.assert_called_once_with("p1")
        orch._start_group.assert_called_once()

    def test_genuinely_active_run_still_blocks(self):
        """force_reset_stale_runs refuses (slot busy / too fresh) →
        the run still blocks incremental fast_sync."""
        orch = self._orch()
        orch._runs[("p1", "finalize")] = self._fake_run("running")
        orch.force_reset_stale_runs = MagicMock(return_value=[])

        assert orch.run_fast_sync("p1") is False
        orch._start_group.assert_not_called()

    def test_user_paused_run_blocks_without_reset_attempt(self):
        """A paused run is deliberate user state — never force-reset."""
        orch = self._orch()
        orch._runs[("p1", "deep_enrichment")] = self._fake_run("paused")
        orch.force_reset_stale_runs = MagicMock(return_value=["deep_enrichment"])

        assert orch.run_fast_sync("p1") is False
        orch.force_reset_stale_runs.assert_not_called()
        orch._start_group.assert_not_called()

    def test_no_blocking_run_proceeds(self):
        orch = self._orch()
        orch.force_reset_stale_runs = MagicMock(return_value=[])
        assert orch.run_fast_sync("p1") is True
        orch.force_reset_stale_runs.assert_not_called()
