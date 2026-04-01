"""
Agent Concurrency Gate — Phase 66

Ensures autonomous agent LLM calls don't compete with pipeline LLM calls.

The CoDRAG pipeline is the primary consumer of LLM/GPU resources.  Agent
scenarios (Watchdog, Dispatcher, Librarian, etc.) are secondary.  This gate
enforces a simple rule:

    WHEN pipeline is running an LLM stage → Agent DEFERS
    WHEN pipeline is idle → Agent EXECUTES

The gate also prevents multiple agent tasks from running simultaneously
(one-at-a-time serialization), since they share the same model slot.

Usage:
    gate = get_agent_gate()
    if gate.can_run(project_id):
        try:
            # ... do agent LLM work ...
        finally:
            gate.release()
    else:
        logger.info("Pipeline busy, deferring agent task")
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# LLM-consuming stages — if any of these are active, agents defer.
_LLM_STAGES = frozenset({
    "inferred_edges",   # Stage 2 (code model)
    "catalogue",        # Stage 3 (fast model)
    "enrichment",       # Stage 6 (deep model)
    "group_reasoning",  # Stage 7 (deep model)
    "clustering",       # Stage 8 (deep model)
    "atlas",            # Stage 9 (deep model)
    "deepening",        # Stage 10 (deep model)
})


class AgentConcurrencyGate:
    """Prevents agent LLM calls from competing with pipeline LLM calls.

    Thread-safe.  Only one agent task can hold the gate at a time.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._agent_active: bool = False
        self._active_task: Optional[str] = None
        self._acquired_at: Optional[float] = None

    def can_run(self, project_id: str, task_name: str = "unknown") -> bool:
        """Check if an agent task can safely make LLM calls.

        Returns True and acquires the gate if:
        1. No pipeline LLM stage is currently running for this project
        2. No other agent task is currently active

        The caller MUST call ``release()`` when done (use try/finally).

        Args:
            project_id: CoDRAG project ID to check pipeline status for.
            task_name: Human-readable name for logging (e.g., "watchdog").

        Returns:
            True if the gate was acquired, False if the agent should defer.
        """
        # Check 1: Is the pipeline running an LLM stage?
        if self._pipeline_using_llm(project_id):
            logger.debug(
                "Agent gate: pipeline LLM stage active for %s — deferring %s",
                project_id, task_name,
            )
            return False

        # Check 2: Is another agent task already running?
        with self._lock:
            if self._agent_active:
                logger.debug(
                    "Agent gate: another agent task (%s) already active — deferring %s",
                    self._active_task, task_name,
                )
                return False
            self._agent_active = True
            self._active_task = task_name
            self._acquired_at = time.monotonic()
            logger.info("Agent gate: acquired for %s (project %s)", task_name, project_id)
            return True

    def release(self) -> None:
        """Release the agent gate.  Must be called after ``can_run()`` returns True."""
        with self._lock:
            task = self._active_task
            elapsed = time.monotonic() - (self._acquired_at or time.monotonic())
            self._agent_active = False
            self._active_task = None
            self._acquired_at = None
        logger.info("Agent gate: released %s (held %.1fs)", task or "unknown", elapsed)

    def is_active(self) -> bool:
        """Return True if an agent task is currently active."""
        with self._lock:
            return self._agent_active

    def status(self) -> dict:
        """Return gate status for API/dashboard."""
        with self._lock:
            return {
                "agent_active": self._agent_active,
                "active_task": self._active_task,
                "held_for_s": (
                    round(time.monotonic() - self._acquired_at, 1)
                    if self._acquired_at else None
                ),
            }

    @staticmethod
    def _pipeline_using_llm(project_id: str) -> bool:
        """Check if any pipeline run for this project is on an LLM stage."""
        try:
            from codrag.services.pipeline.orchestrator import pipeline_orchestrator
            # Check all runs for this project
            with pipeline_orchestrator._lock:
                for (pid, group), run in pipeline_orchestrator._runs.items():
                    if pid != project_id:
                        continue
                    if not run.is_active:
                        continue
                    current = run.current_stage
                    if current and current in _LLM_STAGES:
                        return True
            return False
        except Exception:
            # If we can't check, assume it's safe (fail-open for agents)
            return False


# ── Module-level singleton ───────────────────────────────────────
_gate = AgentConcurrencyGate()


def get_agent_gate() -> AgentConcurrencyGate:
    """Return the singleton agent concurrency gate."""
    return _gate
