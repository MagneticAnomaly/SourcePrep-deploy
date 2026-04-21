"""
Tests for pipeline_budget.py — BudgetThrottle + ScheduleEvaluator (Phase 26)
"""

import time
import threading
from unittest.mock import patch, MagicMock

import pytest

from prep.services.pipeline_budget import BudgetThrottle, ScheduleEvaluator


# ── BudgetThrottle Tests ─────────────────────────────────────────


class TestBudgetThrottle:
    """Tests for the sliding-window token budget enforcer."""

    def setup_method(self):
        self.throttle = BudgetThrottle()

    def test_unlimited_budget_always_allowed(self):
        """When max_tokens=0 (unlimited), check_allowed always returns True."""
        with patch.object(BudgetThrottle, '_get_budget_config', return_value=(0, 5)):
            assert self.throttle.check_allowed("proj-1") is True
            self.throttle.record_usage("proj-1", 999999)
            assert self.throttle.check_allowed("proj-1") is True

    def test_budget_enforcement_basic(self):
        """Usage under budget is allowed; usage at/over budget is blocked."""
        with patch.object(BudgetThrottle, '_get_budget_config', return_value=(1000, 5)):
            assert self.throttle.check_allowed("proj-1") is True

            self.throttle.record_usage("proj-1", 500)
            assert self.throttle.check_allowed("proj-1") is True

            self.throttle.record_usage("proj-1", 500)
            assert self.throttle.check_allowed("proj-1") is False

    def test_budget_accumulates(self):
        """Multiple record_usage calls accumulate within the window."""
        with patch.object(BudgetThrottle, '_get_budget_config', return_value=(100, 5)):
            for _ in range(10):
                self.throttle.record_usage("proj-1", 10)
            assert self.throttle.check_allowed("proj-1") is False

    def test_window_reset(self):
        """After the window expires, budget resets and allows again."""
        with patch.object(BudgetThrottle, '_get_budget_config', return_value=(100, 1)):
            self.throttle.record_usage("proj-1", 100)
            assert self.throttle.check_allowed("proj-1") is False

            # Simulate window expiry by backdating the window_start
            with self.throttle._lock:
                state = self.throttle._windows["proj-1"]
                state.window_start = time.time() - 120  # 2 minutes ago (window is 1 min)

            assert self.throttle.check_allowed("proj-1") is True

    def test_per_project_isolation(self):
        """Budget tracking is per-project."""
        with patch.object(BudgetThrottle, '_get_budget_config', return_value=(100, 5)):
            self.throttle.record_usage("proj-1", 100)
            assert self.throttle.check_allowed("proj-1") is False
            assert self.throttle.check_allowed("proj-2") is True

    def test_get_usage_empty(self):
        """get_usage returns zeroed state for unknown project."""
        with patch.object(BudgetThrottle, '_get_budget_config', return_value=(1000, 5)):
            usage = self.throttle.get_usage("proj-new")
            assert usage["tokens_used"] == 0
            assert usage["max_tokens"] == 1000
            assert usage["remaining"] == 1000
            assert usage["window_resets_in"] == 0

    def test_get_usage_with_data(self):
        """get_usage reflects recorded token consumption."""
        with patch.object(BudgetThrottle, '_get_budget_config', return_value=(1000, 5)):
            self.throttle.record_usage("proj-1", 300)
            usage = self.throttle.get_usage("proj-1")
            assert usage["tokens_used"] == 300
            assert usage["remaining"] == 700
            assert usage["window_minutes"] == 5
            assert usage["window_resets_in"] > 0

    def test_get_usage_unlimited(self):
        """get_usage shows remaining=-1 when budget is unlimited."""
        with patch.object(BudgetThrottle, '_get_budget_config', return_value=(0, 5)):
            usage = self.throttle.get_usage("proj-1")
            assert usage["remaining"] == -1

    def test_thread_safety(self):
        """Concurrent record_usage calls don't lose data."""
        with patch.object(BudgetThrottle, '_get_budget_config', return_value=(0, 5)):
            errors = []

            def record():
                try:
                    for _ in range(100):
                        self.throttle.record_usage("proj-1", 1)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=record) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
            usage = self.throttle.get_usage("proj-1")
            assert usage["tokens_used"] == 1000


# ── ScheduleEvaluator Tests ──────────────────────────────────────


class TestScheduleEvaluator:
    """Tests for the scheduled deep enrichment trigger."""

    def setup_method(self):
        self.evaluator = ScheduleEvaluator()

    def teardown_method(self):
        self.evaluator.stop()

    def test_record_run_updates_timestamp(self):
        """record_run stores a timestamp for the project."""
        self.evaluator.record_run("proj-1")
        with self.evaluator._lock:
            assert "proj-1" in self.evaluator._last_run
            assert self.evaluator._last_run["proj-1"] > 0

    def test_stop_cancels_timer(self):
        """stop() cancels any pending timer."""
        callback = MagicMock(return_value=True)
        self.evaluator.start(callback, check_interval=3600)
        assert self.evaluator._running is True

        self.evaluator.stop()
        assert self.evaluator._running is False

    def test_evaluate_skips_manual_mode(self):
        """When mode is 'manual', no projects are triggered."""
        callback = MagicMock(return_value=True)
        self.evaluator._run_callback = callback

        with patch.object(ScheduleEvaluator, '_get_schedule_config', return_value={
            "mode": "manual", "interval_minutes": 1, "threshold_percent": 0,
        }):
            self.evaluator._do_evaluate()

        callback.assert_not_called()

    def test_evaluate_triggers_on_interval(self):
        """When scheduled mode + interval elapsed, callback fires."""
        callback = MagicMock(return_value=True)
        self.evaluator._run_callback = callback

        mock_project = MagicMock()
        mock_project.id = "proj-1"

        import prep.server
        with patch.object(ScheduleEvaluator, '_get_schedule_config', return_value={
            "mode": "scheduled", "interval_minutes": 1, "threshold_percent": 0,
        }), patch.object(codrag.server, '_registry') as mock_reg:
            mock_reg.list_projects.return_value = [mock_project]
            # No last run recorded → elapsed is very large → should trigger
            self.evaluator._do_evaluate()

        callback.assert_called_once_with("proj-1")

    def test_evaluate_respects_recent_run(self):
        """If a run happened recently, interval trigger doesn't fire."""
        callback = MagicMock(return_value=True)
        self.evaluator._run_callback = callback
        self.evaluator.record_run("proj-1")  # Just ran

        mock_project = MagicMock()
        mock_project.id = "proj-1"

        import prep.server
        with patch.object(ScheduleEvaluator, '_get_schedule_config', return_value={
            "mode": "scheduled", "interval_minutes": 60, "threshold_percent": 0,
        }), patch.object(codrag.server, '_registry') as mock_reg:
            mock_reg.list_projects.return_value = [mock_project]
            self.evaluator._do_evaluate()

        callback.assert_not_called()

    def test_evaluate_triggers_on_threshold(self):
        """When stale percentage exceeds threshold, callback fires."""
        callback = MagicMock(return_value=True)
        self.evaluator._run_callback = callback
        self.evaluator.record_run("proj-1")  # Recent run (blocks interval trigger)

        mock_project = MagicMock()
        mock_project.id = "proj-1"

        import prep.server
        with patch.object(ScheduleEvaluator, '_get_schedule_config', return_value={
            "mode": "scheduled", "interval_minutes": 0, "threshold_percent": 10,
        }), patch.object(ScheduleEvaluator, '_get_stale_percent', return_value=25.0), \
             patch.object(codrag.server, '_registry') as mock_reg:
            mock_reg.list_projects.return_value = [mock_project]
            self.evaluator._do_evaluate()

        callback.assert_called_once_with("proj-1")
