"""
CoDRAG Scope Orchestrator — Phase 24 (SM-8: Knowledge Scope Pipeline)
======================================================================

Manages the Knowledge Scope (File Tree) pipeline: when users add/remove
files from the FolderTree panel, the CodeIndex needs to be rebuilt with
the updated file set.

**Design:**
  - Tracks ``pending_adds`` and ``pending_removes`` from FolderTree changes.
  - Debounce window (configurable, default 3s) to batch rapid selections.
  - Background CodeIndex rebuild with atomic swap (search stays live).
  - Tier-gated: Pro gets auto-rebuild, Free gets manual with stale indicator.
  - File change detection: if a scoped file changes on disk, mark it stale
    and queue a re-embed.

**States:**
  ``idle`` → ``debouncing`` → ``building`` → ``idle``
                                    ↓
                                ``failed``

**Relationship to BuildOrchestrator (SM-4):**
  Uses ``BuildOrchestrator.start(project_id, BuildType.INDEX, worker)``
  for the actual build, getting thread management and listener notifications
  for free.

**Relationship to existing watcher:**
  The ``AutoRebuildWatcher`` handles *file content changes* for the full
  codebase index.  ScopeOrchestrator handles *scope selection changes*
  (add/remove files from Knowledge Scope) specifically.  They are
  independent — both can trigger index rebuilds, but for different reasons.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Scope state ──────────────────────────────────────────────────

class ScopeState:
    IDLE = "idle"
    DEBOUNCING = "debouncing"
    BUILDING = "building"
    FAILED = "failed"
    STALE = "stale"  # Changes pending but auto-rebuild disabled (Free tier)


@dataclass
class ScopeChange:
    """A pending scope change."""
    added_paths: Set[str] = field(default_factory=set)
    removed_paths: Set[str] = field(default_factory=set)
    changed_paths: Set[str] = field(default_factory=set)  # On-disk file changes
    timestamp: float = field(default_factory=time.time)

    @property
    def is_empty(self) -> bool:
        return not self.added_paths and not self.removed_paths and not self.changed_paths

    @property
    def total_changes(self) -> int:
        return len(self.added_paths) + len(self.removed_paths) + len(self.changed_paths)


class ScopeOrchestrator:
    """Orchestrates Knowledge Scope rebuilds with debouncing and atomic swap."""

    def __init__(
        self,
        debounce_ms: int = 3000,
        auto_rebuild: bool = True,
    ):
        self._debounce_ms = debounce_ms
        self._auto_rebuild = auto_rebuild

        self._lock = threading.Lock()
        # Per-project scope state
        self._states: Dict[str, str] = {}  # project_id → ScopeState
        self._pending: Dict[str, ScopeChange] = {}  # project_id → pending changes
        self._timers: Dict[str, threading.Timer] = {}  # project_id → debounce timer
        self._build_fns: Dict[str, Callable] = {}  # project_id → build function
        self._errors: Dict[str, str] = {}  # project_id → last error
        self._last_rebuild_at: Dict[str, float] = {}  # project_id → timestamp
        self._stale_since: Dict[str, float] = {}  # project_id → timestamp

    # ── Configuration ────────────────────────────────────────────

    @property
    def debounce_ms(self) -> int:
        return self._debounce_ms

    @debounce_ms.setter
    def debounce_ms(self, value: int) -> None:
        self._debounce_ms = max(500, value)  # Minimum 500ms

    @property
    def auto_rebuild(self) -> bool:
        return self._auto_rebuild

    @auto_rebuild.setter
    def auto_rebuild(self, value: bool) -> None:
        self._auto_rebuild = value

    # ── Register build functions ─────────────────────────────────

    def register_build_fn(
        self,
        project_id: str,
        build_fn: Callable[[Set[str], Set[str], Set[str]], bool],
    ) -> None:
        """Register the build function for a project.

        The build function receives (added_paths, removed_paths, changed_paths)
        and returns True on success, False on failure.
        """
        with self._lock:
            self._build_fns[project_id] = build_fn
            if project_id not in self._states:
                self._states[project_id] = ScopeState.IDLE

    # ── Scope change notifications ───────────────────────────────

    def on_files_added(self, project_id: str, paths: List[str]) -> None:
        """Called when files are added to the Knowledge Scope."""
        if not paths:
            return
        with self._lock:
            change = self._pending.setdefault(project_id, ScopeChange())
            for p in paths:
                change.added_paths.add(p)
                change.removed_paths.discard(p)  # Cancel pending remove
            change.timestamp = time.time()
        self._schedule_rebuild(project_id)

    def on_files_removed(self, project_id: str, paths: List[str]) -> None:
        """Called when files are removed from the Knowledge Scope."""
        if not paths:
            return
        with self._lock:
            change = self._pending.setdefault(project_id, ScopeChange())
            for p in paths:
                change.removed_paths.add(p)
                change.added_paths.discard(p)  # Cancel pending add
            change.timestamp = time.time()
        self._schedule_rebuild(project_id)

    def on_files_changed(self, project_id: str, paths: List[str]) -> None:
        """Called when scoped files change on disk (content changed)."""
        if not paths:
            return
        with self._lock:
            change = self._pending.setdefault(project_id, ScopeChange())
            for p in paths:
                change.changed_paths.add(p)
            change.timestamp = time.time()
        self._schedule_rebuild(project_id)

    # ── Manual trigger ───────────────────────────────────────────

    def trigger_rebuild(self, project_id: str) -> bool:
        """Manually trigger a rebuild (for Free tier or force rebuild).

        Returns True if a rebuild was started, False if already building
        or no changes pending.
        """
        with self._lock:
            state = self._states.get(project_id, ScopeState.IDLE)
            if state == ScopeState.BUILDING:
                return False

            change = self._pending.get(project_id)
            if change is None or change.is_empty:
                return False

            # Cancel any pending debounce timer
            self._cancel_timer(project_id)

        self._start_build(project_id)
        return True

    # ── Status ───────────────────────────────────────────────────

    def status(self, project_id: str) -> Dict[str, Any]:
        """Get scope orchestrator status for a project."""
        with self._lock:
            state = self._states.get(project_id, ScopeState.IDLE)
            change = self._pending.get(project_id)
            error = self._errors.get(project_id)
            last_rebuild = self._last_rebuild_at.get(project_id)
            stale_since = self._stale_since.get(project_id)

        return {
            "state": state,
            "pending_adds": len(change.added_paths) if change else 0,
            "pending_removes": len(change.removed_paths) if change else 0,
            "pending_changes": len(change.changed_paths) if change else 0,
            "total_pending": change.total_changes if change else 0,
            "auto_rebuild": self._auto_rebuild,
            "debounce_ms": self._debounce_ms,
            "error": error,
            "last_rebuild_at": last_rebuild,
            "stale_since": stale_since,
            "is_stale": state == ScopeState.STALE or (change is not None and not change.is_empty),
        }

    # ── Clear ────────────────────────────────────────────────────

    def clear_project(self, project_id: str) -> None:
        """Clear all scope state for a project."""
        with self._lock:
            self._cancel_timer(project_id)
            self._states.pop(project_id, None)
            self._pending.pop(project_id, None)
            self._build_fns.pop(project_id, None)
            self._errors.pop(project_id, None)
            self._last_rebuild_at.pop(project_id, None)
            self._stale_since.pop(project_id, None)

    # ── Internal ─────────────────────────────────────────────────

    def _schedule_rebuild(self, project_id: str) -> None:
        """Schedule a debounced rebuild or mark as stale."""
        with self._lock:
            state = self._states.get(project_id, ScopeState.IDLE)

            if state == ScopeState.BUILDING:
                # Build in progress — changes will be picked up after
                return

            if not self._auto_rebuild:
                # Free tier: mark as stale, don't auto-rebuild
                self._states[project_id] = ScopeState.STALE
                if project_id not in self._stale_since:
                    self._stale_since[project_id] = time.time()
                return

            # Cancel existing timer and start a new one
            self._cancel_timer(project_id)
            self._states[project_id] = ScopeState.DEBOUNCING

            timer = threading.Timer(
                self._debounce_ms / 1000.0,
                self._on_debounce_expired,
                args=(project_id,),
            )
            timer.daemon = True
            self._timers[project_id] = timer
            timer.start()

    def _cancel_timer(self, project_id: str) -> None:
        """Cancel a pending debounce timer.  Must hold self._lock."""
        timer = self._timers.pop(project_id, None)
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass

    def _on_debounce_expired(self, project_id: str) -> None:
        """Called when the debounce window closes — time to build."""
        self._start_build(project_id)

    def _start_build(self, project_id: str) -> None:
        """Start the actual rebuild in a background thread."""
        with self._lock:
            change = self._pending.pop(project_id, None)
            if change is None or change.is_empty:
                self._states[project_id] = ScopeState.IDLE
                return

            build_fn = self._build_fns.get(project_id)
            if build_fn is None:
                logger.warning("No build function registered for %s", project_id)
                self._states[project_id] = ScopeState.FAILED
                self._errors[project_id] = "No build function registered"
                return

            self._states[project_id] = ScopeState.BUILDING
            self._errors.pop(project_id, None)

            # Snapshot the changes for the build thread
            added = set(change.added_paths)
            removed = set(change.removed_paths)
            changed = set(change.changed_paths)

        # Emit SSE so frontend picks up the BUILDING state immediately
        self._emit_status_event(project_id)

        # Run build in a daemon thread
        t = threading.Thread(
            target=self._build_worker,
            args=(project_id, build_fn, added, removed, changed),
            daemon=True,
        )
        t.start()

    def _build_worker(
        self,
        project_id: str,
        build_fn: Callable,
        added: Set[str],
        removed: Set[str],
        changed: Set[str],
    ) -> None:
        """Background thread that runs the actual build."""
        try:
            logger.info(
                "Scope rebuild for %s: +%d -%d ~%d",
                project_id, len(added), len(removed), len(changed),
            )
            success = build_fn(added, removed, changed)

            with self._lock:
                if success:
                    self._last_rebuild_at[project_id] = time.time()
                    self._stale_since.pop(project_id, None)
                    self._states[project_id] = ScopeState.IDLE
                else:
                    self._states[project_id] = ScopeState.FAILED
                    self._errors[project_id] = "Build returned failure"

        except Exception as e:
            logger.error("Scope rebuild failed for %s: %s", project_id, e)
            with self._lock:
                self._states[project_id] = ScopeState.FAILED
                self._errors[project_id] = str(e)

        # Emit SSE event so frontend detects the state change
        self._emit_status_event(project_id)

        # If changes arrived during build, re-schedule immediately
        with self._lock:
            new_change = self._pending.get(project_id)
            has_pending = new_change is not None and not new_change.is_empty
        if has_pending:
            self._schedule_rebuild(project_id)

    def _emit_status_event(self, project_id: str) -> None:
        """Emit an SSE event with the current scope status."""
        try:
            from codrag.core.events import get_event_bus
            bus = get_event_bus()
            bus.emit("scope_status", {
                "project_id": project_id,
                **self.status(project_id),
            })
        except Exception:
            logger.debug("SSE scope_status emit failed", exc_info=True)


# ── Module-level singleton ───────────────────────────────────────
scope_orchestrator = ScopeOrchestrator()
