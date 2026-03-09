"""
CoDRAG Pipeline Budget Throttle — Phase 26 (S-26.5 + S-26.3)
=============================================================

Token-budget enforcement for Auto and Scheduled deep enrichment modes.

**Budget Throttle (S-26.5):**
  Prevents runaway API costs in Auto mode by capping token usage per
  sliding time window.  Before auto-chaining deep enrichment, the
  orchestrator calls ``budget.check_allowed()`` — if the budget is
  exhausted, the run is deferred until the window resets.

**Scheduled Mode (S-26.3):**
  A background timer that periodically evaluates whether deep enrichment
  should run based on:
    - Time since last run (interval trigger)
    - Accumulated stale/pending chunk percentage (threshold trigger)

**Configuration (via settings_store):**

  pipeline_config.deep_enrichment.budget:
    max_tokens:   100000   # max tokens per window (0 = unlimited)
    window_minutes: 5      # sliding window duration

  pipeline_config.deep_enrichment.schedule:
    interval_minutes: 60   # 0 = disabled
    threshold_percent: 20  # % of chunks stale before triggering (0 = disabled)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


# ── Budget Throttle ──────────────────────────────────────────────

@dataclass
class _WindowState:
    """Tracks token usage within a sliding time window."""
    tokens_used: int = 0
    window_start: float = 0.0


class BudgetThrottle:
    """Per-project token budget enforcement for deep enrichment.

    Thread-safe.  Resets on process restart (in-memory tracking).
    For persistent tracking across restarts, call ``load_from_settings()``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: Dict[str, _WindowState] = {}

    def check_allowed(self, project_id: str) -> bool:
        """Return True if the project has budget remaining in the current window."""
        max_tokens, window_minutes = self._get_budget_config()
        if max_tokens <= 0:
            return True  # Unlimited

        window_seconds = window_minutes * 60
        now = time.time()

        with self._lock:
            state = self._windows.get(project_id)
            if state is None:
                return True  # No usage yet

            # Window expired → reset
            if now - state.window_start > window_seconds:
                return True

            return state.tokens_used < max_tokens

    def record_usage(self, project_id: str, tokens: int) -> None:
        """Record token usage for a project.  Resets window if expired."""
        _, window_minutes = self._get_budget_config()
        window_seconds = window_minutes * 60
        now = time.time()

        with self._lock:
            state = self._windows.get(project_id)
            if state is None or (now - state.window_start > window_seconds):
                state = _WindowState(tokens_used=0, window_start=now)
                self._windows[project_id] = state
            state.tokens_used += tokens

        logger.debug(
            "Budget: project=%s tokens_used=%d (+%d)",
            project_id, state.tokens_used, tokens,
        )

    def get_usage(self, project_id: str) -> Dict[str, Any]:
        """Get current budget usage for a project."""
        max_tokens, window_minutes = self._get_budget_config()
        window_seconds = window_minutes * 60
        now = time.time()

        with self._lock:
            state = self._windows.get(project_id)

        if state is None or (now - state.window_start > window_seconds):
            return {
                "tokens_used": 0,
                "max_tokens": max_tokens,
                "window_minutes": window_minutes,
                "remaining": max_tokens if max_tokens > 0 else -1,
                "window_resets_in": 0,
            }

        remaining = max(0, max_tokens - state.tokens_used) if max_tokens > 0 else -1
        resets_in = max(0, window_seconds - (now - state.window_start))
        return {
            "tokens_used": state.tokens_used,
            "max_tokens": max_tokens,
            "window_minutes": window_minutes,
            "remaining": remaining,
            "window_resets_in": round(resets_in),
        }

    @staticmethod
    def _get_budget_config() -> tuple[int, int]:
        """Read budget config from settings store. Returns (max_tokens, window_minutes).

        The settings router saves budget to ``pipeline_config.budgets``
        with keys ``max_tokens_per_run`` and ``max_minutes_per_run``.
        """
        try:
            from codrag.services.settings_store import settings
            config = settings.get("pipeline_config") or {}
            budgets = config.get("budgets") or {}
            return (
                int(budgets.get("max_tokens_per_run", 0)),
                int(budgets.get("max_minutes_per_run", 5)),
            )
        except Exception:
            return (0, 5)  # Unlimited by default


# ── Schedule Evaluator ───────────────────────────────────────────

class ScheduleEvaluator:
    """Evaluates whether a scheduled deep enrichment run should trigger.

    Tracks per-project last-run timestamps and delegates to the
    PipelineOrchestrator when conditions are met.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_run: Dict[str, float] = {}  # project_id → epoch
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self._run_callback: Optional[Callable[[str], bool]] = None

    def start(self, run_callback: Callable[[str], bool], check_interval: float = 60.0) -> None:
        """Start periodic schedule evaluation.

        Args:
            run_callback: Called with project_id when a scheduled run should start.
                          Should return True if run was started.
            check_interval: How often to check (seconds).
        """
        self._run_callback = run_callback
        self._running = True
        self._check_interval = check_interval
        self._schedule_next()
        logger.info("Schedule evaluator started (check every %.0fs)", check_interval)

    def stop(self) -> None:
        """Stop the schedule evaluator."""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def record_run(self, project_id: str) -> None:
        """Record that deep enrichment ran for a project."""
        with self._lock:
            self._last_run[project_id] = time.time()

    def _schedule_next(self) -> None:
        if not self._running:
            return
        self._timer = threading.Timer(self._check_interval, self._evaluate)
        self._timer.daemon = True
        self._timer.start()

    def _evaluate(self) -> None:
        """Check all projects with scheduled mode and trigger if conditions met."""
        try:
            self._do_evaluate()
        except Exception:
            logger.debug("Schedule evaluation failed", exc_info=True)
        finally:
            self._schedule_next()

    def _do_evaluate(self) -> None:
        config = self._get_schedule_config()
        mode = config.get("mode", "manual")

        # Phase 48 (P48-F6): Handle both 'scheduled' and 'auto' modes.
        # In auto mode, periodically check if there's unconverged deepening
        # work that needs more passes (the watcher handles file changes,
        # but this handles convergence-only re-triggers).
        if mode == "auto":
            interval_minutes = 2  # Check every 2 minutes in auto mode
            threshold_percent = 0
        elif mode == "scheduled":
            interval_minutes = config.get("interval_minutes", 60)
            threshold_percent = config.get("threshold_percent", 20)
        else:
            return  # manual mode — nothing to evaluate

        if interval_minutes <= 0 and threshold_percent <= 0 and mode != "auto":
            return  # Nothing to trigger

        # Get all projects
        try:
            from codrag.server import _registry
            if _registry is None:
                return
            projects = _registry.list_projects()
        except Exception:
            return

        now = time.time()
        for project in projects:
            pid = project.id

            # Skip inactive / frozen / locked projects
            try:
                from codrag.services.project_helpers import get_project_activity_status
                status = get_project_activity_status(pid)
                if status != "active":
                    continue
            except Exception:
                continue

            should_run = False
            reason = ""

            # Time-based trigger
            if interval_minutes > 0:
                with self._lock:
                    last = self._last_run.get(pid, 0)
                elapsed = (now - last) / 60
                if elapsed >= interval_minutes:
                    should_run = True
                    reason = f"interval ({elapsed:.0f}m >= {interval_minutes}m)"

            # Threshold-based trigger (check stale percentage)
            if not should_run and threshold_percent > 0:
                stale_pct = self._get_stale_percent(pid)
                if stale_pct >= threshold_percent:
                    should_run = True
                    reason = f"threshold ({stale_pct:.1f}% >= {threshold_percent}%)"

            if should_run and self._run_callback:
                logger.info("Schedule trigger for %s: %s", pid, reason)
                try:
                    started = self._run_callback(pid)
                    if started:
                        self.record_run(pid)
                except Exception:
                    logger.debug("Scheduled run failed for %s", pid, exc_info=True)

    @staticmethod
    def _get_schedule_config() -> Dict[str, Any]:
        """Read schedule config from settings store."""
        try:
            from codrag.services.settings_store import settings
            config = settings.get("pipeline_config") or {}
            deep = config.get("deep_enrichment") or {}
            return {
                "mode": deep.get("mode", "manual"),
                "interval_minutes": int(deep.get("schedule", {}).get("interval_minutes", 60)),
                "threshold_percent": int(deep.get("schedule", {}).get("threshold_percent", 20)),
            }
        except Exception:
            return {"mode": "manual", "interval_minutes": 60, "threshold_percent": 20}

    @staticmethod
    def _get_stale_percent(project_id: str) -> float:
        """Get the percentage of stale trace nodes for a project."""
        try:
            from codrag.services.build_manager import build_manager
            from codrag.services.project_helpers import require_project
            project = require_project(project_id)
            trace_idx = build_manager.get_project_trace_index(project)
            if not trace_idx.exists():
                return 0.0
            total = trace_idx.node_count()
            if total == 0:
                return 0.0
            stale = trace_idx.stale_count() if hasattr(trace_idx, 'stale_count') else 0
            return (stale / total) * 100
        except Exception:
            return 0.0


# ── Module Singletons ────────────────────────────────────────────

budget = BudgetThrottle()
schedule = ScheduleEvaluator()
