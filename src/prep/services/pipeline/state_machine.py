"""
Pipeline State Machine — Phase 25B
====================================

Formalizes the lifecycle of a pipeline group run with explicit states,
guarded transitions, and crash recovery.  Replaces the ad-hoc
``PipelineRunPhase`` enum + magic error strings.

States:
    IDLE        — No run in progress
    QUEUED      — Waiting for compute capacity (LLM slot)
    RUNNING     — Actively executing stages
    PAUSING     — Pause signal sent, waiting for stage to flush
    PAUSED      — Stopped cleanly, checkpoint saved, can resume
    CANCELLING  — Cancel signal sent, waiting for stage to stop
    CANCELLED   — Cancelled by user
    COMPLETED   — All stages finished successfully
    FAILED      — A stage failed (actual error, not pause/cancel)
    RECOVERING  — Crash detected, restoring from checkpoint

Valid transitions::

    IDLE ──────→ RUNNING ──────→ COMPLETED
      ↑             │  ↑
      │             │  └──────── (advance to next stage)
      │             ↓
      │         PAUSING ──→ PAUSED ──→ RUNNING (resume)
      │             │           │
      │             │           └──→ CANCELLING → CANCELLED
      │             ↓
      │         CANCELLING ──→ CANCELLED
      │
      │         FAILED ←── (stage error from RUNNING)
      │
      └──── RECOVERING ──→ RUNNING (resume from checkpoint)
                   │
                   └──→ FAILED (recovery failed)
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Stage Snapshot ──────────────────────────────────────────────

@dataclass(frozen=True)
class StageSnapshot:
    """Immutable snapshot of a single stage's status.

    Updated by workers via progress callbacks. Read by the status
    endpoint without locks (snapshot pattern — read a reference).
    """
    stage_id: str = ""
    exists: bool = False
    running: bool = False
    # Data counts (from disk or worker progress)
    item_count: int = 0
    total_items: int = 0
    avg_confidence: float = 0.0
    # Progress (from BuildSlot progress callbacks)
    progress_current: int = 0
    progress_total: int = 0
    progress_baseline: int = 0
    # Extra per-stage data (flexible dict for stage-specific fields)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "stage_id": self.stage_id,
            "exists": self.exists,
            "running": self.running,
            "item_count": self.item_count,
            "total_items": self.total_items,
            "avg_confidence": self.avg_confidence,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "progress_baseline": self.progress_baseline,
        }
        if self.extra:
            d.update(self.extra)
        return d


# ── States ────────────────────────────────────────────────────────

class PipelineState(str, enum.Enum):
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERING = "recovering"


# ── Transition table ─────────────────────────────────────────────

# Maps (current_state, event) → target_state.
# If a transition is not in this table, it's invalid and will be rejected.

class Event(str, enum.Enum):
    START = "start"
    ENQUEUE = "enqueue"                    # No compute capacity → wait in queue
    CAPACITY_AVAILABLE = "capacity_available"  # Slot freed → can start running
    STAGE_COMPLETED = "stage_completed"
    ALL_STAGES_DONE = "all_stages_done"
    PAUSE = "pause"
    STAGE_FLUSHED = "stage_flushed"
    RESUME = "resume"
    CANCEL = "cancel"
    STAGE_STOPPED = "stage_stopped"
    STAGE_FAILED = "stage_failed"
    CRASH_DETECTED = "crash_detected"
    RECOVERY_SUCCEEDED = "recovery_succeeded"
    RECOVERY_FAILED = "recovery_failed"
    RESET = "reset"


_TRANSITIONS: Dict[tuple, PipelineState] = {
    # Starting — direct start if capacity available
    (PipelineState.IDLE, Event.START): PipelineState.RUNNING,

    # Queuing — no compute capacity, wait in queue
    (PipelineState.IDLE, Event.ENQUEUE): PipelineState.QUEUED,
    (PipelineState.QUEUED, Event.CAPACITY_AVAILABLE): PipelineState.RUNNING,
    (PipelineState.QUEUED, Event.CANCEL): PipelineState.CANCELLED,

    # Normal progression
    (PipelineState.RUNNING, Event.STAGE_COMPLETED): PipelineState.RUNNING,
    (PipelineState.RUNNING, Event.ALL_STAGES_DONE): PipelineState.COMPLETED,

    # Between-stage queuing — next stage needs a different compute node
    # that is currently full.  Park in QUEUED until slot frees.
    (PipelineState.RUNNING, Event.ENQUEUE): PipelineState.QUEUED,

    # Phase 48-F8: Stage completion/failure while QUEUED.
    # This happens when a build starts before the ENQUEUE transition
    # completes, or when capacity becomes available without a formal
    # CAPACITY_AVAILABLE event.  Without these, the pipeline freezes
    # in QUEUED state forever after the stage finishes.
    (PipelineState.QUEUED, Event.STAGE_COMPLETED): PipelineState.RUNNING,
    (PipelineState.QUEUED, Event.ALL_STAGES_DONE): PipelineState.COMPLETED,
    (PipelineState.QUEUED, Event.STAGE_FAILED): PipelineState.FAILED,

    # Pausing
    (PipelineState.RUNNING, Event.PAUSE): PipelineState.PAUSING,
    (PipelineState.PAUSING, Event.STAGE_FLUSHED): PipelineState.PAUSED,

    # Resuming from pause
    (PipelineState.PAUSED, Event.RESUME): PipelineState.RUNNING,

    # Self-heal: PAUSED with every stage already finished on disk collapses
    # directly to COMPLETED. Normally ALL_STAGES_DONE only fires from RUNNING,
    # but daemon restarts / external resets can leave a run at PAUSED with
    # stage_results fully populated. Without this edge, the queue + panel
    # disagree about "is this done?" (panel overrides client-side, queue shows
    # Paused forever). Added 2026-04-18 as backend half of the fix.
    (PipelineState.PAUSED, Event.ALL_STAGES_DONE): PipelineState.COMPLETED,

    # Cancelling
    (PipelineState.RUNNING, Event.CANCEL): PipelineState.CANCELLING,
    (PipelineState.PAUSED, Event.CANCEL): PipelineState.CANCELLED,
    (PipelineState.CANCELLING, Event.STAGE_STOPPED): PipelineState.CANCELLED,
    (PipelineState.PAUSING, Event.CANCEL): PipelineState.CANCELLING,

    # Failure
    (PipelineState.RUNNING, Event.STAGE_FAILED): PipelineState.FAILED,
    (PipelineState.PAUSING, Event.STAGE_FAILED): PipelineState.FAILED,

    # Crash recovery
    (PipelineState.IDLE, Event.CRASH_DETECTED): PipelineState.RECOVERING,
    (PipelineState.RECOVERING, Event.RECOVERY_SUCCEEDED): PipelineState.RUNNING,
    (PipelineState.RECOVERING, Event.RECOVERY_FAILED): PipelineState.FAILED,

    # Reset (return to idle from any terminal state)
    (PipelineState.COMPLETED, Event.RESET): PipelineState.IDLE,
    (PipelineState.FAILED, Event.RESET): PipelineState.IDLE,
    (PipelineState.CANCELLED, Event.RESET): PipelineState.IDLE,
    (PipelineState.PAUSED, Event.RESET): PipelineState.IDLE,
    (PipelineState.QUEUED, Event.RESET): PipelineState.IDLE,
}

# Terminal states — no further progression without explicit reset/resume
TERMINAL_STATES: Set[PipelineState] = {
    PipelineState.COMPLETED,
    PipelineState.FAILED,
    PipelineState.CANCELLED,
}

# Active states — pipeline is "doing something" (including waiting for capacity)
ACTIVE_STATES: Set[PipelineState] = {
    PipelineState.QUEUED,
    PipelineState.RUNNING,
    PipelineState.PAUSING,
    PipelineState.CANCELLING,
    PipelineState.RECOVERING,
}


# ── Transition record ────────────────────────────────────────────

@dataclass
class TransitionRecord:
    """Immutable record of a state transition."""
    timestamp: float
    from_state: PipelineState
    to_state: PipelineState
    event: Event
    stage_index: int
    detail: Optional[str] = None


# ── Guard functions ──────────────────────────────────────────────

class TransitionGuard:
    """Pluggable guard that can veto a transition."""

    def check(self, sm: "PipelineGroupStateMachine", event: Event, **kwargs) -> Optional[str]:
        """Return None to allow, or an error message string to block."""
        return None


class ActiveProjectGuard(TransitionGuard):
    """Blocks START if the project is not active."""

    def check(self, sm, event, **kwargs):
        if event != Event.START:
            return None
        try:
            from prep.services.project_helpers import get_project_activity_status
            status = get_project_activity_status(sm.project_id)
            if status != "active":
                return f"Project is {status} — cannot start pipeline"
        except Exception:
            pass  # Don't block if helper fails
        return None


# ── State Machine ────────────────────────────────────────────────

@dataclass
class PipelineGroupStateMachine:
    """State machine for a single pipeline group run.

    Thread-safe.  All state mutations go through ``transition()``.
    """
    project_id: str
    group: str  # "fast_sync" or "deep_enrichment"
    stages: List[str] = field(default_factory=list)

    # Current state
    state: PipelineState = PipelineState.IDLE
    current_stage_index: int = 0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    stage_results: Dict[str, str] = field(default_factory=dict)

    # Journal integration
    journal_run_id: Optional[str] = None

    # Transition history (bounded)
    history: List[TransitionRecord] = field(default_factory=list)
    _max_history: int = 100

    # Guards
    _guards: List[TransitionGuard] = field(default_factory=list)

    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # Stage snapshots — updated by workers, read by status endpoint
    _stage_snapshots: Dict[str, StageSnapshot] = field(default_factory=dict, repr=False)

    # Callbacks: called AFTER a successful transition
    _on_transition: Optional[Callable[[TransitionRecord], None]] = field(default=None, repr=False)

    def add_guard(self, guard: TransitionGuard) -> None:
        self._guards.append(guard)

    @property
    def current_stage(self) -> Optional[str]:
        if 0 <= self.current_stage_index < len(self.stages):
            return self.stages[self.current_stage_index]
        return None

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def is_paused(self) -> bool:
        return self.state == PipelineState.PAUSED

    @property
    def is_queued(self) -> bool:
        return self.state == PipelineState.QUEUED

    @property
    def is_effectively_settled(self) -> bool:
        """True when the run is PAUSED but every stage has actually finished.

        Source-of-truth reconciler: ``state`` and ``stage_results`` can drift
        across daemon restarts or external resets. When every stage in
        ``self.stages`` reports ``completed`` or ``skipped``, the run is done
        regardless of the phase label — and should be collapsed to COMPLETED so
        the queue, panel, and SSE consumers see a single consistent view.
        """
        if self.state != PipelineState.PAUSED:
            return False
        if not self.stages:
            return False
        return all(
            self.stage_results.get(stage) in ("completed", "skipped")
            for stage in self.stages
        )

    def reconcile_if_settled(self) -> bool:
        """If ``is_effectively_settled``, fire ALL_STAGES_DONE to reach COMPLETED.

        Safe to call from any read path. Returns True iff a transition fired.
        The ``transition()`` call re-checks state under the lock, so racing
        callers cannot double-transition.
        """
        if not self.is_effectively_settled:
            return False
        return self.transition(
            Event.ALL_STAGES_DONE,
            detail="reconciled: paused with all stages complete",
        )

    def can_transition(self, event: Event) -> bool:
        """Check if a transition is valid without performing it."""
        return (self.state, event) in _TRANSITIONS

    def transition(self, event: Event, detail: Optional[str] = None, **kwargs) -> bool:
        """Attempt a state transition.

        Returns True if the transition succeeded, False if rejected.
        Thread-safe.
        """
        with self._lock:
            key = (self.state, event)
            target = _TRANSITIONS.get(key)

            if target is None:
                logger.debug(
                    "Rejected transition: %s + %s (no rule) [%s/%s]",
                    self.state.value, event.value, self.project_id, self.group,
                )
                return False

            # Run guards
            for guard in self._guards:
                reason = guard.check(self, event, **kwargs)
                if reason:
                    logger.info(
                        "Guard blocked %s + %s: %s [%s/%s]",
                        self.state.value, event.value, reason,
                        self.project_id, self.group,
                    )
                    return False

            # Perform transition
            old_state = self.state
            self.state = target

            # Side effects based on event
            now = time.time()

            if event == Event.START:
                self.started_at = now
                self.finished_at = None
                self.error = None
                self.stage_results = {}

            elif event == Event.STAGE_COMPLETED:
                stage = self.current_stage
                if stage:
                    self.stage_results[stage] = "completed"
                self.current_stage_index += 1

            elif event == Event.ALL_STAGES_DONE:
                self.finished_at = now

            elif event == Event.STAGE_FLUSHED:
                self.finished_at = now

            elif event == Event.STAGE_FAILED:
                stage = self.current_stage
                if stage:
                    self.stage_results[stage] = "failed"
                self.error = detail or f"Stage {stage} failed"
                self.finished_at = now

            elif event in (Event.CANCEL, Event.STAGE_STOPPED):
                if target in TERMINAL_STATES:
                    self.error = detail or "Cancelled by user"
                    self.finished_at = now

            elif event == Event.RESUME:
                self.finished_at = None
                self.error = None

            elif event == Event.RECOVERY_FAILED:
                self.error = detail or "Crash recovery failed"
                self.finished_at = now

            elif event == Event.RESET:
                self.current_stage_index = 0
                self.started_at = None
                self.finished_at = None
                self.error = None
                self.stage_results = {}
                self.journal_run_id = None

            # Record history
            record = TransitionRecord(
                timestamp=now,
                from_state=old_state,
                to_state=target,
                event=event,
                stage_index=self.current_stage_index,
                detail=detail,
            )
            self.history.append(record)
            if len(self.history) > self._max_history:
                self.history = self.history[-self._max_history:]

            logger.info(
                "Pipeline %s/%s: %s → %s (event=%s, stage_idx=%d%s)",
                self.project_id, self.group,
                old_state.value, target.value, event.value,
                self.current_stage_index,
                f", detail={detail}" if detail else "",
            )

        # Callback outside lock
        if self._on_transition:
            try:
                self._on_transition(record)
            except Exception:
                logger.debug("Transition callback failed", exc_info=True)

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses (backward-compatible with PipelineRun.to_dict)."""
        with self._lock:
            return {
                "project_id": self.project_id,
                "group": self.group,
                "phase": self.state.value,
                "current_stage": self.current_stage,
                "current_stage_index": self.current_stage_index,
                "total_stages": len(self.stages),
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "error": self.error,
                "stage_results": dict(self.stage_results),
                "journal_run_id": self.journal_run_id,
                "is_active": self.is_active,
                "is_paused": self.is_paused,
                "is_queued": self.is_queued,
            }

    # ── Stage Snapshots ────────────────────────────────────────

    def update_stage_snapshot(self, stage_id: str, **kwargs: Any) -> None:
        """Update a stage's snapshot. Called by workers via progress callback.

        Thread-safe. Creates the snapshot if it doesn't exist.
        Uses replace() on the frozen dataclass for immutability.
        """
        with self._lock:
            old = self._stage_snapshots.get(stage_id, StageSnapshot(stage_id=stage_id))
            # Filter kwargs to only valid StageSnapshot fields, put rest in extra
            valid_fields = {f.name for f in old.__dataclass_fields__.values()} - {"extra"}
            snapshot_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
            extra_kwargs = {k: v for k, v in kwargs.items() if k not in valid_fields}
            if extra_kwargs:
                merged_extra = {**old.extra, **extra_kwargs}
                snapshot_kwargs["extra"] = merged_extra
            self._stage_snapshots[stage_id] = replace(old, **snapshot_kwargs)

    def get_stage_snapshots(self) -> Dict[str, StageSnapshot]:
        """Get a copy of all stage snapshots. Lock-free read of immutable objects."""
        with self._lock:
            return dict(self._stage_snapshots)

    def get_stage_snapshot(self, stage_id: str) -> Optional[StageSnapshot]:
        """Get a single stage's snapshot."""
        with self._lock:
            return self._stage_snapshots.get(stage_id)
