"""Tests for RecoveryManager — Phase 72 Stage 2."""
from unittest.mock import MagicMock, patch

import pytest

from codrag.services.pipeline.recovery import RecoveryManager
from codrag.services.pipeline.stages import (
    DEEP_ENRICHMENT_STAGES,
    FAST_SYNC_STAGES,
    StageId,
)
from codrag.services.pipeline.state_machine import (
    PipelineState,
)


class TestHydratePausedRuns:
    def test_creates_paused_state_machine_at_resume_point(self):
        """When resume point is mid-pipeline, creates a PAUSED SM at that point."""
        registered = {}

        def detect_resume(pid, stages, skip_mtime):
            return 2

        def register_run(pid, group, sm):
            registered[(pid, group)] = sm

        mock_project = MagicMock()
        mock_project.id = "proj-1"

        # Guard that always allows transitions (no project activity check)
        guard = MagicMock()
        guard.check.return_value = None

        with patch("codrag.services.project_helpers.get_registry") as mock_reg, \
             patch("codrag.services.settings_store.settings") as mock_settings:
            mock_reg.return_value.list_projects.return_value = [mock_project]
            mock_settings.get.return_value = {}

            RecoveryManager.hydrate_paused_runs_from_disk(
                detect_resume_fn=detect_resume,
                register_run_fn=register_run,
                is_run_active_fn=lambda pid: False,
                default_guard=guard,
            )

        assert ("proj-1", "fast_sync") in registered
        assert ("proj-1", "deep_enrichment") in registered

        sm = registered[("proj-1", "fast_sync")]
        assert sm.state == PipelineState.PAUSED
        assert sm.current_stage_index == 2
        assert sm.stage_results[FAST_SYNC_STAGES[0].value] == "completed"
        assert sm.stage_results[FAST_SYNC_STAGES[1].value] == "completed"

    def test_skips_auto_mode_groups(self):
        """Groups in AUTO mode should not be hydrated."""
        registered = {}

        mock_project = MagicMock()
        mock_project.id = "proj-1"

        with patch("codrag.services.project_helpers.get_registry") as mock_reg, \
             patch("codrag.services.settings_store.settings") as mock_settings:
            mock_reg.return_value.list_projects.return_value = [mock_project]
            mock_settings.get.return_value = {
                "fast_sync": {"auto": True},
                "deep_enrichment": {"mode": "auto"},
            }

            RecoveryManager.hydrate_paused_runs_from_disk(
                detect_resume_fn=lambda pid, stages, skip: 2,
                register_run_fn=lambda pid, group, sm: registered.update({(pid, group): sm}),
                is_run_active_fn=lambda pid: False,
                default_guard=MagicMock(),
            )

        assert len(registered) == 0

    def test_skips_complete_pipelines(self):
        """When all stages are complete, skip hydration."""
        registered = {}

        mock_project = MagicMock()
        mock_project.id = "proj-1"

        with patch("codrag.services.project_helpers.get_registry") as mock_reg, \
             patch("codrag.services.settings_store.settings") as mock_settings:
            mock_reg.return_value.list_projects.return_value = [mock_project]
            mock_settings.get.return_value = {}

            RecoveryManager.hydrate_paused_runs_from_disk(
                detect_resume_fn=lambda pid, stages, skip: len(stages),
                register_run_fn=lambda pid, group, sm: registered.update({(pid, group): sm}),
                is_run_active_fn=lambda pid: False,
                default_guard=MagicMock(),
            )

        assert len(registered) == 0

    def test_skips_active_projects(self):
        """Projects with active runs should not be hydrated."""
        registered = {}

        mock_project = MagicMock()
        mock_project.id = "proj-1"

        with patch("codrag.services.project_helpers.get_registry") as mock_reg, \
             patch("codrag.services.settings_store.settings") as mock_settings:
            mock_reg.return_value.list_projects.return_value = [mock_project]
            mock_settings.get.return_value = {}

            RecoveryManager.hydrate_paused_runs_from_disk(
                detect_resume_fn=lambda pid, stages, skip: 2,
                register_run_fn=lambda pid, group, sm: registered.update({(pid, group): sm}),
                is_run_active_fn=lambda pid: True,
                default_guard=MagicMock(),
            )

        assert len(registered) == 0


class TestStartupRecovery:
    def test_calls_phases_in_order(self):
        """startup_recovery should call hydrate, then auto_recover."""
        call_order = []

        with patch("codrag.services.pipeline_journal.journal") as mock_journal:
            mock_journal.recover_crashed_runs.return_value = []

            RecoveryManager.startup_recovery(
                hydrate_fn=lambda: call_order.append("hydrate"),
                auto_recover_fn=lambda: call_order.append("auto_recover"),
                set_crashed_runs=lambda runs: None,
            )

        assert call_order == ["hydrate", "auto_recover"]

    def test_continues_on_hydrate_failure(self):
        """If hydrate fails, auto_recover should still run."""
        call_order = []

        def bad_hydrate():
            raise RuntimeError("hydrate boom")

        with patch("codrag.services.pipeline_journal.journal") as mock_journal:
            mock_journal.recover_crashed_runs.return_value = []

            RecoveryManager.startup_recovery(
                hydrate_fn=bad_hydrate,
                auto_recover_fn=lambda: call_order.append("auto_recover"),
                set_crashed_runs=lambda runs: None,
            )

        assert "auto_recover" in call_order


class TestCrashedRunManagement:
    def test_discard_crashed_run_delegates_to_journal(self):
        with patch("codrag.services.pipeline_journal.journal") as mock_journal:
            mock_journal.resolve_crashed_run.return_value = True
            assert RecoveryManager.discard_crashed_run("run-123") is True
            mock_journal.resolve_crashed_run.assert_called_once_with("run-123", "discarded")

    def test_get_crashed_runs_handles_import_failure(self):
        """Should return empty list if journal is unavailable."""
        with patch.dict("sys.modules", {"codrag.services.pipeline_journal": None}):
            result = RecoveryManager.get_crashed_runs()
            assert result == []
