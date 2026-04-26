"""
Prep Build Orchestrator — Phase 24 (SM-4)
=============================================

Replaces the ad-hoc threading model in ``build_manager.py`` with explicit
state machines per build slot.

**Design:**
  Each project × build-type combination gets a ``BuildSlot`` with states::

      IDLE → QUEUED → RUNNING → COMPLETED
                         ↓
                       FAILED

  Transitions are guarded: you can't start a build that's already running,
  and dead threads are detected and transitioned to FAILED.

**Build types:**
  - ``index``     — CodeIndex (file tree / Knowledge Scope)
  - ``trace``     — TraceIndex (Stage 1: Structural Graph)
  - ``augment``   — Fast Catalogue (Stage 2)
  - ``validate``  — Relationship Validation (Stage 3)
  - ``knowledge`` — Knowledge Embedding (Stage 4 / Stage 8)
  - ``epistemic`` — Epistemic Enrichment (Stage 5)
  - ``cluster``   — Cluster Synthesis (Stage 6)
  - ``deepening`` — Continuous Deepening (Stage 7)

**Usage:**
  The PipelineOrchestrator (SM-6) sequences stages by calling
  ``orchestrator.start(project_id, build_type, worker_fn)`` and polling
  ``orchestrator.status(project_id, build_type)``.

  Direct callers (e.g. individual endpoint handlers) can also use it for
  one-off builds.

**Relationship to build_manager.py:**
  BuildManager still owns index caches and embedder creation.
  BuildOrchestrator owns the *lifecycle* of build threads: starting,
  monitoring, and state transitions.  BuildManager's ``start_project_*``
  methods will be refactored to delegate to this orchestrator.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from prep.services.cancellation import CancellationToken, PipelineCancelledError, PipelinePausedError

logger = logging.getLogger(__name__)


# ── Build Types ──────────────────────────────────────────────────

class BuildType(str, enum.Enum):
    """All build types managed by the orchestrator."""
    INDEX = "index"
    TRACE = "trace"
    INFERRED_EDGES = "inferred_edges"
    AUGMENT = "augment"
    VALIDATE = "validate"
    KNOWLEDGE = "knowledge"
    EPISTEMIC = "epistemic"
    CLUSTER = "cluster"
    GROUP_REASONING = "group_reasoning"
    ATLAS = "atlas"
    DEEPENING = "deepening"
    RULES = "rules"
    CONCEPTS = "concepts"
    AUDIT = "audit"
    ANTIBODIES = "antibodies"


# ── Build Phases (State Machine) ─────────────────────────────────

class BuildPhase(str, enum.Enum):
    """States for a single build slot."""
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Build Slot ───────────────────────────────────────────────────

class BuildPhaseExt(str, enum.Enum):
    """Extended phases that include paused state."""
    PAUSED = "paused"


@dataclass
class BuildSlot:
    """State machine for a single project × build-type combination.

    Thread-safe via the orchestrator's lock.  Do not mutate directly;
    use ``BuildOrchestrator`` methods.
    """
    project_id: str
    build_type: BuildType
    phase: BuildPhase = BuildPhase.IDLE
    thread: Optional[threading.Thread] = field(default=None, repr=False)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    progress_message: Optional[str] = None
    progress_current: int = 0
    progress_total: int = 0
    progress_baseline: int = 0  # Items already complete from previous runs
    cancel_token: CancellationToken = field(default_factory=CancellationToken)

    @property
    def is_active(self) -> bool:
        """True if the slot is queued or running."""
        return self.phase in (BuildPhase.QUEUED, BuildPhase.RUNNING)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Elapsed time for completed/failed builds."""
        if self.started_at is None:
            return None
        end = self.finished_at or time.time()
        return end - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses."""
        d: Dict[str, Any] = {
            "project_id": self.project_id,
            "build_type": self.build_type.value,
            "phase": self.phase.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }
        # Phase 118 Issue A: always expose progress while the slot is in
        # an active phase (running, queued, pausing, recovering) so the
        # dashboard can render an indeterminate bar even before the worker
        # has computed a total. Previously this guard was `progress_total
        # > 0`, which left the bar invisible during warmup — particularly
        # noticeable on Group Reasoning which spends 5–30s computing the
        # group set before the first batch progress callback fires.
        active_phases = {"running", "queued", "pausing", "recovering"}
        if self.progress_total > 0 or self.phase.value in active_phases:
            d["progress"] = {
                "message": self.progress_message,
                "current": self.progress_current,
                "total": self.progress_total,
                "baseline": self.progress_baseline,
            }
        return d


# ── Orchestrator ─────────────────────────────────────────────────

# Type for the worker callable: receives (slot, progress_callback) and returns result dict
WorkerFn = Callable[["BuildSlot", Callable[[str, int, int], None]], Dict[str, Any]]


class BuildOrchestrator:
    """Manages build lifecycles for all projects and build types.

    Thread-safe.  One instance per daemon process (singleton).

    Typical usage::

        def my_worker(slot, progress_cb):
            progress_cb("Scanning files", 0, 100)
            # ... do work ...
            return {"files_indexed": 42}

        started = orchestrator.start("proj-1", BuildType.TRACE, my_worker)
        status = orchestrator.status("proj-1", BuildType.TRACE)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Key: (project_id, build_type) → BuildSlot
        self._slots: Dict[Tuple[str, BuildType], BuildSlot] = {}
        # Listeners notified on phase transitions: (project_id, build_type, old_phase, new_phase)
        self._listeners: list[Callable[[str, BuildType, BuildPhase, BuildPhase], None]] = []

    # ── Public API ─────────────────────────────────────────────

    def start(
        self,
        project_id: str,
        build_type: BuildType,
        worker: WorkerFn,
    ) -> bool:
        """Start a build.  Returns True if started, False if already active.

        The *worker* callable runs in a daemon thread.  It receives:
          - ``slot``: the BuildSlot (read-only for the worker)
          - ``progress_cb(message, current, total)``: call to report progress

        The worker should return a result dict on success or raise on failure.
        """
        with self._lock:
            slot = self._get_or_create_slot(project_id, build_type)

            # Check for zombie threads
            self._check_zombie(slot)

            if slot.is_active:
                return False

            # Transition: * → QUEUED → RUNNING (immediately, since we start the thread now)
            old_phase = slot.phase
            slot.phase = BuildPhase.RUNNING
            slot.started_at = time.time()
            slot.finished_at = None
            slot.error = None
            slot.result = None
            slot.progress_message = None
            slot.progress_current = 0
            slot.progress_total = 0
            slot.cancel_token = CancellationToken()

            t = threading.Thread(
                target=self._run_worker,
                args=(slot, worker),
                name=f"build-{project_id}-{build_type.value}",
                daemon=True,
            )
            slot.thread = t
            t.start()

        self._notify(project_id, build_type, old_phase, BuildPhase.RUNNING)
        return True

    def status(self, project_id: str, build_type: BuildType) -> BuildSlot:
        """Get the current build slot (creates IDLE if none exists).

        Also detects zombie threads and transitions them to FAILED.
        """
        with self._lock:
            slot = self._get_or_create_slot(project_id, build_type)
            self._check_zombie(slot)
            return slot

    def snapshot(self, project_id: str, build_type: BuildType) -> Optional[BuildSlot]:
        """F-41: Lock-free read of an existing build slot.

        Returns None if no slot exists for (project_id, build_type) yet.
        Does NOT create a slot, does NOT run zombie detection, does NOT
        acquire ``self._lock``.

        Read-only callers (e.g. ``/pipeline/status``) should use this
        instead of ``status()`` to avoid contending with worker threads
        that briefly hold the lock for state transitions. The trade-off:
        a thread that just died will keep its stale ``RUNNING`` phase
        in the snapshot until the next ``status()``-side caller runs
        zombie detection — that's a minor UX nit, far better than
        wedging the daemon for 30+ seconds when 15 sequential
        ``status()`` calls pile up behind an active worker.

        Field reads on ``BuildSlot`` are individually atomic under the
        Python GIL, so a snapshot taken without the lock may briefly
        observe a transitional state but never a torn write.
        """
        return self._slots.get((project_id, build_type))

    def is_active(self, project_id: str, build_type: BuildType) -> bool:
        """Check if a build is queued or running."""
        with self._lock:
            key = (project_id, build_type)
            slot = self._slots.get(key)
            if slot is None:
                return False
            self._check_zombie(slot)
            return slot.is_active

    def is_any_active(self, project_id: str) -> bool:
        """Check if any build type is active for a project."""
        with self._lock:
            for (pid, _), slot in self._slots.items():
                if pid == project_id:
                    self._check_zombie(slot)
                    if slot.is_active:
                        return True
            return False

    def cancel(self, project_id: str, build_type: BuildType) -> bool:
        """Request cancellation.  Signals the CancellationToken so the
        worker can cooperatively stop and flush partial results.

        Thread interruption is not supported (Python limitation).
        The worker checks ``cancel_token.is_cancelled`` to self-terminate.
        """
        with self._lock:
            key = (project_id, build_type)
            slot = self._slots.get(key)
            if slot is None or not slot.is_active:
                return False
            old_phase = slot.phase
            slot.cancel_token.cancel()
            slot.phase = BuildPhase.FAILED
            slot.finished_at = time.time()
            slot.error = "Cancelled by user"

        self._notify(project_id, build_type, old_phase, BuildPhase.FAILED)
        return True

    def pause(self, project_id: str, build_type: BuildType) -> bool:
        """Request a graceful pause.  Signals the CancellationToken with
        pause semantics so the worker flushes partial results and stops.

        The worker raises PipelinePausedError which _run_worker catches
        and records as a paused state (not failed).
        """
        with self._lock:
            key = (project_id, build_type)
            slot = self._slots.get(key)
            if slot is None or not slot.is_active:
                return False
            slot.cancel_token.pause()
        # Don't transition phase yet — let the worker do it when it stops
        return True

    def all_slots(self, project_id: Optional[str] = None) -> list[BuildSlot]:
        """Return all slots, optionally filtered by project."""
        with self._lock:
            slots = list(self._slots.values())
            if project_id:
                slots = [s for s in slots if s.project_id == project_id]
            for s in slots:
                self._check_zombie(s)
            return slots

    def clear_project(self, project_id: str) -> None:
        """Remove all slots for a project (after project deletion)."""
        with self._lock:
            keys = [k for k in self._slots if k[0] == project_id]
            for k in keys:
                del self._slots[k]

    def add_listener(
        self,
        listener: Callable[[str, BuildType, BuildPhase, BuildPhase], None],
    ) -> None:
        """Register a callback for phase transitions.

        Signature: ``listener(project_id, build_type, old_phase, new_phase)``
        Called outside the lock, so listeners must be thread-safe.
        """
        self._listeners.append(listener)

    # ── Internal ───────────────────────────────────────────────

    def _get_or_create_slot(self, project_id: str, build_type: BuildType) -> BuildSlot:
        """Get or create a slot.  Must be called under lock."""
        key = (project_id, build_type)
        slot = self._slots.get(key)
        if slot is None:
            slot = BuildSlot(project_id=project_id, build_type=build_type)
            self._slots[key] = slot
        return slot

    def _check_zombie(self, slot: BuildSlot) -> None:
        """Detect dead threads still marked as RUNNING.  Must be called under lock."""
        if slot.phase == BuildPhase.RUNNING and slot.thread is not None:
            if not slot.thread.is_alive():
                logger.warning(
                    "Zombie build detected: %s/%s — thread died without finishing",
                    slot.project_id, slot.build_type.value,
                )
                slot.phase = BuildPhase.FAILED
                slot.finished_at = time.time()
                if not slot.error:
                    slot.error = "Build thread died unexpectedly"

    def _run_worker(self, slot: BuildSlot, worker: WorkerFn) -> None:
        """Thread target: runs the worker and transitions the slot."""
        project_id = slot.project_id
        build_type = slot.build_type

        def progress_cb(message: str, current: int, total: int, baseline: int = 0) -> None:
            slot.progress_message = message
            slot.progress_current = current
            slot.progress_total = total
            if baseline > 0:
                slot.progress_baseline = baseline

        try:
            result = worker(slot, progress_cb)
            with self._lock:
                # Check if we were cancelled while running
                if slot.phase == BuildPhase.FAILED:
                    return
                old_phase = slot.phase
                slot.phase = BuildPhase.COMPLETED
                slot.finished_at = time.time()
                slot.result = result
            self._notify(project_id, build_type, old_phase, BuildPhase.COMPLETED)

        except PipelinePausedError:
            logger.info("Build paused: %s/%s (partial results flushed)", project_id, build_type.value)
            with self._lock:
                if slot.phase == BuildPhase.FAILED:
                    return  # Cancel took priority over pause
                old_phase = slot.phase
                slot.phase = BuildPhase.FAILED  # Reuse FAILED for now; orchestrator distinguishes via cancel_token.is_pause
                slot.finished_at = time.time()
                slot.error = "Paused by user"
            self._notify(project_id, build_type, old_phase, BuildPhase.FAILED)

        except PipelineCancelledError:
            logger.info("Build cancelled cooperatively: %s/%s (partial results flushed)", project_id, build_type.value)
            # Phase already set to FAILED by cancel()

        except Exception as e:
            logger.exception("Build failed: %s/%s", project_id, build_type.value)
            with self._lock:
                if slot.phase == BuildPhase.FAILED:
                    return  # Already cancelled
                old_phase = slot.phase
                slot.phase = BuildPhase.FAILED
                slot.finished_at = time.time()
                slot.error = str(e)
            self._notify(project_id, build_type, old_phase, BuildPhase.FAILED)

    def _notify(
        self,
        project_id: str,
        build_type: BuildType,
        old_phase: BuildPhase,
        new_phase: BuildPhase,
    ) -> None:
        """Notify listeners of a phase transition.  Called outside the lock."""
        for listener in self._listeners:
            try:
                listener(project_id, build_type, old_phase, new_phase)
            except Exception:
                logger.exception("Listener error for %s/%s", project_id, build_type.value)


# ── Module-level singleton ───────────────────────────────────────
build_orchestrator = BuildOrchestrator()
