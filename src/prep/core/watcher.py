from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .repo_policy import (
    effective_excludes,
    ensure_repo_policy,
    load_repo_policy,
    policy_path_for_index,
)


class AutoRebuildWatcher:
    # Phase 48-F8: Periodic coverage check interval (seconds).
    # Fires independently of filesystem events to detect files that
    # exist on disk but aren't in the trace graph.
    _COVERAGE_CHECK_INTERVAL = 300.0  # 5 minutes

    # After triggering a coverage-gap rebuild, suppress re-triggers
    # for this many seconds to prevent the every-5-minute loop.
    _COVERAGE_COOLDOWN_SECONDS = 1800  # 30 minutes

    # Phase 145: loop-guard backoff cap for the coverage check.  When a
    # coverage-triggered rebuild leaves the untraced set UNCHANGED, the
    # files are untraceable-in-practice (parser/worker drops them) —
    # back off exponentially instead of rebuilding every cooldown.
    _COVERAGE_LOOP_BACKOFF_CAP_SECONDS = 6 * 3600  # 6 hours

    # Phase 145: backoff cap for the debounce re-queue when
    # run_fast_sync refuses to start (returns started=False).  Without
    # a cap the watcher would re-fire every debounce_ms forever,
    # spamming the log and hammering the orchestrator's guard checks.
    _TRIGGER_FAILURE_BACKOFF_CAP_SECONDS = 300.0  # 5 minutes

    def __init__(
        self,
        repo_root: Path,
        index_dir: Path,
        on_trigger_build: Callable[[List[str]], bool],
        is_building: Callable[[], bool],
        debounce_ms: int = 5000,
        min_rebuild_gap_ms: int = 2000,
        project_id: Optional[str] = None,
        on_coverage_gap: Optional[Callable[[], None]] = None,
        on_files_changed: Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.index_dir = Path(index_dir).resolve()
        self.debounce_ms = int(debounce_ms)
        self.min_rebuild_gap_ms = int(min_rebuild_gap_ms)
        self.project_id = project_id

        self._on_trigger_build = on_trigger_build
        self._is_building = is_building
        self._on_coverage_gap = on_coverage_gap
        self._on_files_changed = on_files_changed

        self._lock = threading.Lock()
        self._enabled = False
        self._state: str = "disabled"
        self._pending_paths: Set[str] = set()
        self._timer: Optional[threading.Timer] = None
        self._coverage_timer: Optional[threading.Timer] = None
        self._observer: Optional[Observer] = None
        self._last_event_at: Optional[str] = None
        self._last_rebuild_at: Optional[str] = None
        self._last_trigger_at_epoch: Optional[float] = None
        self._next_rebuild_at: Optional[str] = None
        self._stale_since: Optional[str] = None  # ISO timestamp when index became stale
        self._last_coverage_check_at: Optional[str] = None
        self._last_coverage_trigger_at: float = 0.0  # epoch when we last triggered a coverage rebuild
        # Phase 145: consecutive run_fast_sync refusals (started=False)
        # drive the debounce re-queue backoff; reset on any successful
        # trigger.
        self._consecutive_trigger_failures: int = 0
        # Phase 145: coverage loop-guard state.  The signature is the
        # untraced path set at the last successful coverage trigger;
        # if a later check sees the identical set, the previous rebuild
        # did not resolve those files (untraceable) → back off.
        self._last_coverage_trigger_sig: frozenset | None = None
        self._coverage_loop_skips: int = 0
        self._coverage_suppress_until: float = 0.0

        # L1 (repo_profile.DEFAULT_EXCLUDE_DIR_NAMES) already covers the
        # default `.sourceprep/` index dirs. Only add an
        # extra guard when the project uses a non-standard index_dir
        # outside the Prep-owned names — otherwise watcher events on
        # our own output would trigger rebuilds.
        self._extra_exclude_globs: List[str] = []

        def _add_repo_relative_exclude(candidate: Path) -> None:
            try:
                rel = candidate.relative_to(self.repo_root)
            except Exception:
                return
            rel_posix = rel.as_posix().rstrip("/")
            if not rel_posix:
                return
            self._extra_exclude_globs.append(rel_posix)
            self._extra_exclude_globs.append(rel_posix + "/*")
            self._extra_exclude_globs.append(rel_posix + "/**/*")

        _add_repo_relative_exclude(self.index_dir)

        # Phase 113: if the daemon-wide data dir ($PREP_DATA_DIR or
        # XDG default) happens to be inside this watched repo, exclude
        # it too. Rare — normally data_dir() is ~/.local/share/sourceprep
        # which no one indexes — but an env-var override pointing
        # inside the repo would otherwise create a feedback loop on
        # every SQLite WAL checkpoint.
        try:
            from prep.core.paths import data_dir as _resolve_data_dir
            _add_repo_relative_exclude(_resolve_data_dir())
        except Exception:
            pass

    def start(self) -> None:
        with self._lock:
            if self._enabled:
                return

            ensure_repo_policy(self.index_dir, self.repo_root)

            self._enabled = True
            self._state = "idle"
            self._pending_paths = set()
            self._last_event_at = None
            self._last_rebuild_at = None
            self._next_rebuild_at = None
            self._stale_since = None
            self._consecutive_trigger_failures = 0

            handler = _AutoRebuildEventHandler(self)
            observer = Observer()
            observer.schedule(handler, str(self.repo_root), recursive=True)
            observer.start()

            self._observer = observer

        # Phase 48-F8: Start periodic coverage check timer.
        # Runs independently of filesystem events to catch files
        # that exist on disk but were never traced.
        self._schedule_coverage_check()

    def stop(self) -> None:
        with self._lock:
            self._enabled = False
            self._state = "disabled"
            self._pending_paths = set()
            self._next_rebuild_at = None

            if self._timer is not None:
                try:
                    self._timer.cancel()
                except Exception:
                    pass
                self._timer = None

            if self._coverage_timer is not None:
                try:
                    self._coverage_timer.cancel()
                except Exception:
                    pass
                self._coverage_timer = None

            observer = self._observer
            self._observer = None

        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=2)
            except Exception:
                pass

    def status(self) -> Dict[str, Any]:
        with self._lock:
            enabled = self._enabled
            state = self._state
            pending_paths_count = len(self._pending_paths)
            debounce_ms = self.debounce_ms
            next_rebuild_at = self._next_rebuild_at
            last_event_at = self._last_event_at
            last_rebuild_at = self._last_rebuild_at
            stale_since = self._stale_since

        if enabled and self._is_building():
            state = "building"

        # Index is stale if there are pending paths OR if changes were detected
        # after the last rebuild completed (stale_since is set)
        is_stale = pending_paths_count > 0 or stale_since is not None

        return {
            "enabled": enabled,
            "state": state,
            "debounce_ms": debounce_ms,
            "stale": is_stale,
            "stale_since": stale_since,
            "pending": pending_paths_count > 0,
            "pending_paths_count": pending_paths_count,
            "next_rebuild_at": next_rebuild_at,
            "last_event_at": last_event_at,
            "last_rebuild_at": last_rebuild_at,
        }

    def clear_pending_state(self, reason: str = "external_rebuild") -> Dict[str, Any]:
        """Clear queued paths and the staleness marker.

        Called when an externally-invoked rebuild (e.g. user clicked
        Rebuild on the dashboard, hitting ``/pipeline/rebuild``)
        consumes whatever changes the watcher had queued. Without
        this, the watcher's ``stale_since`` and ``pending_paths_count``
        survive the rebuild and the UI keeps showing "stale" even
        though the rebuild already covered the changes.

        Returns the cleared state for logging.
        """
        with self._lock:
            cleared = {
                "reason": reason,
                "pending_paths_count": len(self._pending_paths),
                "stale_since": self._stale_since,
                "had_timer": self._timer is not None,
            }
            self._pending_paths = set()
            self._stale_since = None
            self._next_rebuild_at = None
            self._consecutive_trigger_failures = 0
            if self._timer is not None:
                try:
                    self._timer.cancel()
                except Exception:
                    pass
                self._timer = None
            if self._enabled and self._state in ("debouncing", "throttled"):
                self._state = "idle"
        return cleared

    def on_event(self, event: FileSystemEvent) -> None:
        if getattr(event, "is_directory", False):
            return

        if not getattr(event, "src_path", None):
            return

        try:
            src_path = Path(str(event.src_path)).resolve()
        except Exception:
            return

        self._queue_path(src_path)

        dest = getattr(event, "dest_path", None)
        if dest:
            try:
                dest_path = Path(str(dest)).resolve()
            except Exception:
                dest_path = None

            if dest_path is not None:
                self._queue_path(dest_path)

    def _queue_path(self, abs_path: Path) -> None:
        try:
            rel = abs_path.relative_to(self.repo_root)
        except Exception:
            return

        rel_posix = rel.as_posix()
        include_globs, exclude_globs = self._load_policy_globs()
        exclude_globs = exclude_globs + self._extra_exclude_globs

        if not self._is_relevant(rel_posix, include_globs, exclude_globs):
            return

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        with self._lock:
            if not self._enabled:
                return

            self._pending_paths.add(rel_posix)
            self._last_event_at = now_iso
            
            # Mark as stale if not already
            if self._stale_since is None:
                self._stale_since = now_iso

            if self._is_building() or self._state == "building":
                self._state = "building"
                return

            self._state = "debouncing"

            if self._timer is not None:
                try:
                    self._timer.cancel()
                except Exception:
                    pass
                self._timer = None

            delay = max(0.1, self.debounce_ms / 1000.0)
            self._next_rebuild_at = (now + _seconds(delay)).isoformat()
            self._timer = threading.Timer(delay, self._on_debounce_fire)
            self._timer.daemon = True
            self._timer.start()

    def _on_debounce_fire(self) -> None:
        with self._lock:
            self._timer = None
            if not self._enabled:
                return

            if not self._pending_paths:
                self._state = "idle"
                self._next_rebuild_at = None
                return

            paths = sorted(self._pending_paths)
            self._pending_paths = set()
            self._next_rebuild_at = None

        # Notify listeners about changed files (e.g. concept staleness)
        if self._on_files_changed and paths:
            try:
                self._on_files_changed(paths)
            except Exception:
                logger.debug("on_files_changed callback failed", exc_info=True)

        # 2026-06-08 P5: clear guard-rejection markers when real file
        # activity arrives. A new file change is the signal that the
        # workload has actually changed; the previously-rejected stage
        # output may now be different. Without this clear, the selfheal
        # defer (P5) would stay in effect until the 30-min TTL even after
        # the user fixed the issue.
        if paths:
            try:
                from prep.services.pipeline.recovery import clear_guard_rejection
                from prep.services.pipeline.stages import (
                    DEEP_ENRICHMENT_STAGES,
                    FAST_SYNC_STAGES,
                    FINALIZE_STAGES,
                )
                # 2026-06-08: clear markers for every stage group, not just deep
                # enrichment. record_guard_rejection fires from the orchestrator's
                # checkpoint-restore branch for ANY stage; restricting the clear
                # loop to DEEP_ENRICHMENT_STAGES left fast-sync (validation) and
                # finalize (concepts, audit, antibodies) markers stuck for the
                # full 30-min TTL even after the user fixed the underlying issue.
                for stage_group in (FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES, FINALIZE_STAGES):
                    for s in stage_group:
                        clear_guard_rejection(self.index_dir, s.value)
            except Exception:
                pass  # Non-fatal — selfheal will still eventually proceed via TTL.

        if self._is_building():
            with self._lock:
                self._pending_paths.update(paths)
                self._state = "building"
            return

        now_epoch = time.time()
        last_epoch = self._last_trigger_at_epoch
        min_gap_s = max(0.0, float(self.min_rebuild_gap_ms) / 1000.0)
        if last_epoch is not None and (now_epoch - last_epoch) < min_gap_s:
            remaining = min_gap_s - (now_epoch - last_epoch)
            with self._lock:
                self._pending_paths.update(paths)
                self._state = "throttled"
                self._next_rebuild_at = (datetime.now(timezone.utc) + _seconds(remaining)).isoformat()
                self._timer = threading.Timer(max(0.1, remaining), self._on_debounce_fire)
                self._timer.daemon = True
                self._timer.start()
            return

        started = False
        try:
            started = bool(self._on_trigger_build(paths))
        except Exception:
            started = False

        if not started:
            if self._is_building():
                with self._lock:
                    self._pending_paths.update(paths)
                    self._state = "building"
                return

            # Phase 145 (§2q/RC#2): the trigger was REFUSED (e.g.
            # run_fast_sync's downstream guard) — re-queue the paths so
            # they are not silently dropped, and back off exponentially
            # so a permanently-refusing gate doesn't re-fire every
            # debounce_ms forever.  Counter resets on the next
            # successful trigger, start(), or clear_pending_state().
            with self._lock:
                self._pending_paths.update(paths)
                self._consecutive_trigger_failures += 1
                failures = self._consecutive_trigger_failures
                self._state = "debouncing"
                base_delay = max(0.1, self.debounce_ms / 1000.0)
                delay = min(
                    base_delay * (2 ** (failures - 1)),
                    self._TRIGGER_FAILURE_BACKOFF_CAP_SECONDS,
                )
                self._next_rebuild_at = (datetime.now(timezone.utc) + _seconds(delay)).isoformat()
                self._timer = threading.Timer(delay, self._on_debounce_fire)
                self._timer.daemon = True
                self._timer.start()
            logger.warning(
                "Watcher: build trigger refused for %s (started=False) — "
                "%d pending paths re-queued, retry #%d in %.0fs. "
                "See the orchestrator log for the refusing gate's reason.",
                self.project_id, len(paths), failures, delay,
            )
            return

        with self._lock:
            self._state = "building"
            self._last_trigger_at_epoch = time.time()
            self._consecutive_trigger_failures = 0

        t = threading.Thread(target=self._wait_for_build_complete, daemon=True)
        t.start()

    def _wait_for_build_complete(self) -> None:
        while True:
            with self._lock:
                enabled = self._enabled
            if not enabled:
                return

            if not self._is_building():
                break

            time.sleep(0.25)

        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            if not self._enabled:
                return

            self._last_rebuild_at = now_iso

            if self._pending_paths:
                # Still have pending changes - remain stale but continue debouncing
                self._state = "debouncing"
                delay = max(0.1, self.debounce_ms / 1000.0)
                self._next_rebuild_at = (datetime.now(timezone.utc) + _seconds(delay)).isoformat()
                self._timer = threading.Timer(delay, self._on_debounce_fire)
                self._timer.daemon = True
                self._timer.start()
            else:
                # No pending changes - index is now up-to-date
                self._state = "idle"
                self._next_rebuild_at = None
                self._stale_since = None  # Clear staleness

    def _load_policy_globs(self) -> tuple[list[str], list[str]]:
        # Includes come from per-project L2 policy; excludes go through
        # effective_excludes() which unions L1 (code defaults) + L2 (policy
        # file) + L3 (runtime trace.ignore_patterns, auto-resolved via the
        # .sourceprep/project.json pointer so the watcher honours live user
        # edits without a trace rebuild).
        path = policy_path_for_index(self.index_dir)
        pol = load_repo_policy(path)
        if not pol or str(pol.get("repo_root") or "") != str(self.repo_root):
            pol = ensure_repo_policy(self.index_dir, self.repo_root)

        inc = pol.get("include_globs")
        include_globs = [x for x in inc if isinstance(x, str) and x.strip()] if isinstance(inc, list) else []

        from prep.core.project_registry import trace_ignore_patterns_for_index
        l3 = trace_ignore_patterns_for_index(self.index_dir) or None

        exclude_globs = effective_excludes(
            index_dir=self.index_dir,
            repo_root=self.repo_root,
            trace_ignore_patterns=l3,
        )
        return include_globs, exclude_globs

    @staticmethod
    def _is_relevant(rel_posix: str, include_globs: List[str], exclude_globs: List[str]) -> bool:
        # F-40: pathlib.Path.match() does NOT support the recursive ** wildcard
        # the way fnmatch/gitignore-style globs do — for example:
        #   Path(".claude/worktrees/x/y.py").match("**/.claude/**") -> False
        # That broke every directory-level exclude pattern (.claude, .git,
        # .prep, node_modules, etc.) and let the watcher report changes
        # in worktrees as "relevant", which then triggered delta builds that
        # walked the duplicated repo.  Use pathspec (gitwildmatch) instead —
        # the rest of the codebase already uses it for the same purpose.
        import pathspec
        if exclude_globs:
            try:
                if pathspec.PathSpec.from_lines("gitignore", exclude_globs).match_file(rel_posix):
                    return False
            except Exception:
                pass
        if not include_globs:
            return True
        try:
            return pathspec.PathSpec.from_lines("gitignore", include_globs).match_file(rel_posix)
        except Exception:
            return False

    # ── Phase 48-F8: Periodic Coverage Gap Detection ──────────

    def _schedule_coverage_check(self) -> None:
        """Schedule the next periodic coverage check."""
        with self._lock:
            if not self._enabled:
                return
            if self._coverage_timer is not None:
                try:
                    self._coverage_timer.cancel()
                except Exception:
                    pass
            self._coverage_timer = threading.Timer(
                self._COVERAGE_CHECK_INTERVAL,
                self._on_coverage_check,
            )
            self._coverage_timer.daemon = True
            self._coverage_timer.start()

    def _on_coverage_check(self) -> None:
        """Periodic check for untraced/stale files.

        Runs independently of filesystem events.  If files exist on disk
        that aren't in the trace graph, triggers a pipeline run.  This
        catches:
        - Files that existed before the watcher started
        - Files missed by a failed Rust engine build
        - Files added in bulk (e.g. git pull) that the watcher might miss

        Guards against spurious retriggering:
        - Manual mode → skip
        - Pipeline already running → skip (stale runs are force-reset first)
        - Recently triggered → cooldown
        - Untraced set unchanged since last coverage-triggered rebuild →
          escalating loop-guard backoff (untraceable files)
        """
        with self._lock:
            if not self._enabled:
                return

        # Respect the pipeline mode: if fast sync is set to Manual,
        # don't proactively trigger builds via coverage checks.
        # Per-project auto_config is the only authority — see
        # PipelineOrchestrator._is_fast_sync_auto for the regression
        # class this guards against (stale global silently overriding
        # per-project Manual).
        if self.project_id:
            try:
                from prep.services.pipeline_orchestrator import pipeline_orchestrator
                if not pipeline_orchestrator._is_fast_sync_auto(self.project_id):
                    logger.debug("Coverage check skipped — fast sync is Manual for %s", self.project_id)
                    self._schedule_coverage_check()
                    return
            except Exception:
                pass  # Orchestrator unavailable — proceed with check

        # Don't check while a build is in progress (legacy BuildManager)
        if self._is_building():
            logger.debug("Coverage check skipped — build in progress")
            self._schedule_coverage_check()
            return

        # Don't check while the PipelineOrchestrator has an active run
        if self.project_id:
            try:
                from prep.services.pipeline_orchestrator import pipeline_orchestrator
                po_status = pipeline_orchestrator.status(self.project_id)
                if po_status.get("any_running"):
                    # Phase 145 (§2q/RC#3): a stale/abandoned run (worker
                    # crashed, or a queued run whose capacity notification
                    # never fired) reports any_running forever — which
                    # suppresses this backstop AND the heartbeat watchdog
                    # below indefinitely.  force_reset_stale_runs only
                    # resets runs whose stage build slot is idle and whose
                    # age exceeds the staleness window, so a genuinely
                    # active run is untouched.
                    reset = pipeline_orchestrator.force_reset_stale_runs(self.project_id)
                    if reset:
                        logger.warning(
                            "Coverage check: force-reset stale pipeline runs "
                            "for %s: %s",
                            self.project_id, reset,
                        )
                        po_status = pipeline_orchestrator.status(self.project_id)
                if po_status.get("any_running"):
                    logger.debug(
                        "Coverage check skipped — pipeline active for %s",
                        self.project_id,
                    )
                    self._schedule_coverage_check()
                    return
            except Exception:
                pass

        # Cooldown: don't retrigger within _COVERAGE_COOLDOWN_SECONDS
        # of the last coverage-gap trigger. Prevents the loop where
        # the same N untraced files trigger rebuilds every 5 minutes.
        elapsed_since_trigger = time.time() - self._last_coverage_trigger_at
        if elapsed_since_trigger < self._COVERAGE_COOLDOWN_SECONDS:
            logger.debug(
                "Coverage check skipped — cooldown (%.0fs remaining)",
                self._COVERAGE_COOLDOWN_SECONDS - elapsed_since_trigger,
            )
            self._schedule_coverage_check()
            return

        # Phase 145: loop-guard suppression.  When a coverage-triggered
        # rebuild leaves the untraced set unchanged (untraceable files),
        # the suppress-until timestamp pushes the next attempt out with
        # an escalating backoff.
        suppress_remaining = self._coverage_suppress_until - time.time()
        if suppress_remaining > 0:
            logger.debug(
                "Coverage check skipped — untraceable-set backoff (%.0fs remaining)",
                suppress_remaining,
            )
            self._schedule_coverage_check()
            return

        # Don't check while there are pending debounced events
        with self._lock:
            if self._pending_paths:
                logger.debug(
                    "Coverage check skipped — %d pending paths",
                    len(self._pending_paths),
                )
                self._schedule_coverage_check()
                return

        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            if self._on_coverage_gap is not None:
                # Preferred path: delegate to the caller's coverage gap
                # handler (which calls PipelineOrchestrator.check_coverage_gap
                # and triggers a pipeline run if needed).
                self._on_coverage_gap()
                self._last_coverage_check_at = now_iso
            elif self.project_id:
                # Fallback: use PipelineOrchestrator directly.
                # include_paths=True so the loop guard can compare the
                # actual untraced set across cycles.
                from prep.services.pipeline_orchestrator import pipeline_orchestrator
                gap = pipeline_orchestrator.check_coverage_gap(
                    self.project_id, include_paths=True,
                )
                self._last_coverage_check_at = now_iso

                untraced = gap.get("untraced", 0)
                stale = gap.get("stale", 0)
                coverage_pct = gap.get("coverage_pct", 0.0)

                if gap.get("needs_rebuild"):
                    # Phase 145 (§2q/RC#1): the pre-145 "close enough"
                    # gate suppressed high-coverage repos with ≤20
                    # untraced files on the assumption they were
                    # binary/generated/excluded.  That assumption is
                    # false: compute_trace_coverage only reports
                    # *eligible* files as untraced (binary/generated/
                    # excluded files never appear in the list), so the
                    # gate silently starved legitimate source files
                    # (observed live: 9 untraced .py/.md files skipped
                    # every 5 min for days).
                    #
                    # The gate is replaced by a loop guard targeting the
                    # real risk — eligible-but-untraceable files (the
                    # parser/worker keeps dropping them, so the untraced
                    # set never shrinks).  If the untraced set is
                    # IDENTICAL to the set at the last coverage-triggered
                    # rebuild, the rebuild demonstrably did not resolve
                    # those files: suppress with an escalating backoff.
                    # Stale files (content changed) always re-trigger —
                    # they are re-runnable by definition.
                    untraced_sig = (
                        frozenset(gap.get("changed_paths") or ())
                        if stale == 0 else None
                    )
                    if (untraced_sig is not None
                            and self._last_coverage_trigger_sig is not None
                            and untraced_sig == self._last_coverage_trigger_sig):
                        self._coverage_loop_skips += 1
                        backoff = min(
                            self._COVERAGE_COOLDOWN_SECONDS * (2 ** self._coverage_loop_skips),
                            self._COVERAGE_LOOP_BACKOFF_CAP_SECONDS,
                        )
                        self._coverage_suppress_until = time.time() + backoff
                        logger.info(
                            "Watcher coverage check for %s: %d untraced files "
                            "(%.1f%% coverage) unchanged since the last "
                            "coverage-triggered rebuild — treating as "
                            "untraceable, backing off %.0fs (skip #%d). "
                            "Sample: %s",
                            self.project_id, untraced, coverage_pct, backoff,
                            self._coverage_loop_skips,
                            ", ".join(sorted(untraced_sig)[:5]),
                        )
                    else:
                        logger.info(
                            "Watcher coverage check for %s: %d untraced + %d stale "
                            "files (%.1f%% coverage) — triggering rebuild",
                            self.project_id, untraced, stale, coverage_pct,
                        )
                        # Trigger via the normal build path so all guards apply
                        try:
                            started = bool(self._on_trigger_build(["__coverage_gap__"]))
                        except Exception:
                            started = False
                        if started:
                            # Only consume the cooldown when a build
                            # actually started — a refused trigger retries
                            # on the next 5-min cycle instead of being
                            # silently eaten behind a 30-min cooldown.
                            self._last_coverage_trigger_at = time.time()
                            self._last_coverage_trigger_sig = untraced_sig
                            self._coverage_loop_skips = 0
                        else:
                            logger.warning(
                                "Watcher coverage check for %s: rebuild trigger "
                                "refused (started=False) — will retry next cycle. "
                                "See the orchestrator log for the refusing "
                                "gate's reason.",
                                self.project_id,
                            )
                else:
                    logger.debug(
                        "Watcher coverage check for %s: %.1f%% coverage — OK",
                        self.project_id,
                        coverage_pct,
                    )
        except Exception:
            logger.debug("Coverage check failed", exc_info=True)

        # Phase 61B: Heartbeat watchdog — check for stuck pipelines.
        # Piggybacks on the existing coverage check timer (every 5 minutes)
        # so we don't need a separate thread.
        if self.project_id:
            try:
                from prep.services.pipeline_metadata import check_heartbeat_stale, reset_stale_metadata
                from prep.core.project_registry import project_index_dir
                from prep.services.project_helpers import require_project
                project = require_project(self.project_id)
                idx_dir = project_index_dir(project)

                stale_info = check_heartbeat_stale(idx_dir)
                if stale_info:
                    logger.warning(
                        "Watchdog: detected %s pipeline for %s "
                        "(heartbeat_age=%.0fs) — resetting and re-triggering",
                        stale_info["status"], self.project_id,
                        stale_info.get("heartbeat_age_seconds", 0),
                    )
                    # Log to pipeline file logger
                    try:
                        from prep.services.pipeline_logger import get_pipeline_logger
                        pfl = get_pipeline_logger(idx_dir)
                        pfl.selfheal("heartbeat_stale", f"Watchdog detected {stale_info['status']} pipeline", stale_info)
                    except Exception:
                        pass

                    # Reset the stale metadata
                    reset_stale_metadata(idx_dir, reason="watchdog_heartbeat_stale")

                    # Cancel any stuck in-memory state
                    try:
                        from prep.services.pipeline_orchestrator import pipeline_orchestrator
                        reset = pipeline_orchestrator.force_reset_stale_runs(self.project_id)
                        if reset:
                            logger.info("Watchdog: force-reset stale runs: %s", reset)
                    except Exception:
                        pass

                    # Re-trigger the pipeline
                    try:
                        self._on_trigger_build(["__selfheal_watchdog__"])
                    except Exception:
                        pass
                else:
                    logger.debug(
                        "Watchdog: pipeline heartbeat OK for %s",
                        self.project_id,
                    )
            except Exception:
                logger.debug("Watchdog: heartbeat check failed", exc_info=True)

        # Phase 72: Deep enrichment completion check.
        # If fast_sync is fully complete but deep enrichment has incomplete
        # stages, auto-start deep enrichment to finish them.  This catches
        # the case where auto-chain didn't fire (server restart, budget
        # exhaustion, etc.) and stages 6-11 sit incomplete indefinitely.
        if self.project_id:
            self._check_incomplete_deep_enrichment()

        # Schedule next check
        self._schedule_coverage_check()


    def _check_incomplete_deep_enrichment(self) -> None:
        """Auto-start deep enrichment if fast_sync is done but deep stages are incomplete.

        Guards:
        - Deep enrichment must be in auto mode
        - Pipeline must not already be running
        - Fast sync must be fully complete (all 5 stages have manifests)
        - At least one deep enrichment stage must be incomplete
        """
        try:
            from prep.services.pipeline_orchestrator import pipeline_orchestrator
            from prep.services.pipeline.stages import FAST_SYNC_STAGES, DEEP_ENRICHMENT_STAGES
            from prep.services.pipeline.manifest_store import ManifestStore
            from prep.core.project_registry import project_index_dir
            from prep.services.project_helpers import require_project

            pid = self.project_id

            # Guard: only if deep enrichment is in auto mode
            if not pipeline_orchestrator._is_deep_enrichment_auto(pid):
                return

            # Guard: pipeline not currently active
            po_status = pipeline_orchestrator.status(pid)
            if po_status.get("any_running"):
                return

            project = require_project(pid)
            idx_dir = Path(project_index_dir(project))
            store = ManifestStore(idx_dir)

            # Guard: fast_sync must be fully complete
            for stage in FAST_SYNC_STAGES:
                if not store.provenance_exists(stage):
                    return  # Fast sync not done — don't start deep yet

            # Check deep enrichment stages
            incomplete = [
                stage for stage in DEEP_ENRICHMENT_STAGES
                if not store.provenance_exists(stage)
            ]
            if not incomplete:
                return  # All done

            logger.info(
                "Selfheal: deep enrichment incomplete for %s — "
                "%d/%d stages missing (%s). Auto-starting.",
                pid, len(incomplete), len(DEEP_ENRICHMENT_STAGES),
                ", ".join(s.value for s in incomplete),
            )

            try:
                from prep.services.pipeline_logger import get_pipeline_logger
                pfl = get_pipeline_logger(str(idx_dir))
                pfl.selfheal(
                    "deep_enrichment_incomplete",
                    f"Watcher detected {len(incomplete)} incomplete deep stages "
                    f"({', '.join(s.value for s in incomplete)}) — auto-starting",
                    {},
                )
            except Exception:
                pass

            pipeline_orchestrator.run_deep_enrichment(pid)

        except Exception:
            logger.debug("Deep enrichment completion check failed", exc_info=True)


class _AutoRebuildEventHandler(FileSystemEventHandler):
    def __init__(self, watcher: AutoRebuildWatcher) -> None:
        super().__init__()
        self._watcher = watcher

    def on_any_event(self, event: FileSystemEvent) -> None:
        self._watcher.on_event(event)


def _seconds(sec: float) -> "datetime.timedelta":
    from datetime import timedelta

    return timedelta(seconds=float(sec))
