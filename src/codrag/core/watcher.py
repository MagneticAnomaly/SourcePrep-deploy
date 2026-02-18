from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .repo_policy import ensure_repo_policy, load_repo_policy, policy_path_for_index


class AutoRebuildWatcher:
    def __init__(
        self,
        repo_root: Path,
        index_dir: Path,
        on_trigger_build: Callable[[List[str]], bool],
        is_building: Callable[[], bool],
        debounce_ms: int = 5000,
        min_rebuild_gap_ms: int = 2000,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.index_dir = Path(index_dir).resolve()
        self.debounce_ms = int(debounce_ms)
        self.min_rebuild_gap_ms = int(min_rebuild_gap_ms)

        self._on_trigger_build = on_trigger_build
        self._is_building = is_building

        self._lock = threading.Lock()
        self._enabled = False
        self._state: str = "disabled"
        self._pending_paths: Set[str] = set()
        self._timer: Optional[threading.Timer] = None
        self._observer: Optional[Observer] = None
        self._last_event_at: Optional[str] = None
        self._last_rebuild_at: Optional[str] = None
        self._last_trigger_at_epoch: Optional[float] = None
        self._next_rebuild_at: Optional[str] = None
        self._stale_since: Optional[str] = None  # ISO timestamp when index became stale

        self._extra_exclude_globs: List[str] = [
            "**/.codrag",
            "**/.codrag/*",
            "**/.codrag/**/*",
        ]

        try:
            rel_index_dir = self.index_dir.relative_to(self.repo_root)
        except Exception:
            rel_index_dir = None

        if rel_index_dir is not None:
            rel_posix = rel_index_dir.as_posix().rstrip("/")
            if rel_posix:
                self._extra_exclude_globs.append(rel_posix)
                self._extra_exclude_globs.append(rel_posix + "/*")
                self._extra_exclude_globs.append(rel_posix + "/**/*")

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

            handler = _AutoRebuildEventHandler(self)
            observer = Observer()
            observer.schedule(handler, str(self.repo_root), recursive=True)
            observer.start()

            self._observer = observer

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

            with self._lock:
                self._pending_paths.update(paths)
                self._state = "debouncing"
                delay = max(0.1, self.debounce_ms / 1000.0)
                self._next_rebuild_at = (datetime.now(timezone.utc) + _seconds(delay)).isoformat()
                self._timer = threading.Timer(delay, self._on_debounce_fire)
                self._timer.daemon = True
                self._timer.start()
            return

        with self._lock:
            self._state = "building"
            self._last_trigger_at_epoch = time.time()

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
        path = policy_path_for_index(self.index_dir)
        pol = load_repo_policy(path)
        if not pol or str(pol.get("repo_root") or "") != str(self.repo_root):
            pol = ensure_repo_policy(self.index_dir, self.repo_root)

        inc = pol.get("include_globs")
        exc = pol.get("exclude_globs")

        include_globs = [x for x in inc if isinstance(x, str) and x.strip()] if isinstance(inc, list) else []
        exclude_globs = [x for x in exc if isinstance(x, str) and x.strip()] if isinstance(exc, list) else []
        return include_globs, exclude_globs

    @staticmethod
    def _is_relevant(rel_posix: str, include_globs: List[str], exclude_globs: List[str]) -> bool:
        p = Path(rel_posix)

        for pat in exclude_globs:
            try:
                if p.match(pat):
                    return False
            except Exception:
                continue

        if not include_globs:
            return True

        for pat in include_globs:
            try:
                if p.match(pat):
                    return True
            except Exception:
                continue

        return False


class _AutoRebuildEventHandler(FileSystemEventHandler):
    def __init__(self, watcher: AutoRebuildWatcher) -> None:
        super().__init__()
        self._watcher = watcher

    def on_any_event(self, event: FileSystemEvent) -> None:
        self._watcher.on_event(event)


def _seconds(sec: float) -> "datetime.timedelta":
    from datetime import timedelta

    return timedelta(seconds=float(sec))
