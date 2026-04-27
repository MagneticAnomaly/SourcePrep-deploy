"""
Event Bus and Progress Tracking for Prep.

Handles real-time broadcasting of logs and task progress to the frontend via SSE.
Uses stdlib ``queue.Queue`` (thread-safe) so that background build threads
can emit events that are reliably picked up by the async SSE generator.
"""
import asyncio
import logging
import json
import queue as _queue
import uuid
import time
import threading
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict

# Global event bus instance
_event_bus: Optional['EventBus'] = None

def get_event_bus() -> 'EventBus':
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

@dataclass
class ProgressEvent:
    task_id: str
    message: str
    current: int
    total: int
    percent: float
    status: str = "running"  # running, completed, failed

class EventBus:
    """
    Central hub for broadcasting events to connected clients.

    Each SSE subscriber gets a ``queue.Queue`` (stdlib, thread-safe).
    ``emit()`` pushes to every subscriber queue from any thread.
    The async SSE generator polls with ``asyncio.sleep`` so it doesn't
    block the event loop.
    """
    def __init__(self):
        self._queues: List[_queue.Queue] = []
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Kept for API compat — no longer needed."""
        pass

    def subscribe(self) -> _queue.Queue:
        """Add a new subscriber queue (thread-safe stdlib queue)."""
        q: _queue.Queue = _queue.Queue(maxsize=2000)
        with self._lock:
            self._queues.append(q)
        return q

    def unsubscribe(self, q: _queue.Queue) -> None:
        """Remove a subscriber queue."""
        with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Emit an event to all subscribers.  Thread-safe — can be called
        from any thread (build workers, logging handlers, main thread).
        """
        payload = {
            "type": event_type,
            "timestamp": time.time(),
            "data": data
        }

        with self._lock:
            targets = list(self._queues)

        for q in targets:
            try:
                q.put_nowait(payload)
            except _queue.Full:
                # Slow consumer — drop oldest and retry
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    pass

    def emit_log(self, record: logging.LogRecord) -> None:
        """Emit a log record."""
        self.emit("log", {
            "timestamp": record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "created": record.created
        })

    def emit_progress(self, task_id: str, message: str, current: int, total: int) -> None:
        """Emit a progress update."""
        percent = (current / total * 100) if total > 0 else 0
        self.emit("progress", {
            "task_id": task_id,
            "message": message,
            "current": current,
            "total": total,
            "percent": round(percent, 1),
            "status": "running" if current < total else "completed"
        })

class BroadcastLogHandler(logging.Handler):
    """
    Logging handler that pushes records to the EventBus.
    """
    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.event_bus.emit_log(record)
        except Exception:
            self.handleError(record)

class ProgressManager:
    """
    Singleton to manage active tasks and report progress.

    Active tasks are the single source of truth for "what's running outside
    the pipeline orchestrator" — index/trace/knowledge/delta builds. The
    sidebar pipeline queue surfaces every entry here so the user always sees
    what the daemon is actually doing, and ``request_cancel`` is the
    matching cancel mechanism the queue's X button drives.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProgressManager, cls).__new__(cls)
            cls._instance.bus = get_event_bus()
            cls._instance.active_tasks = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def start_task(self, task_type: str, project_id: str) -> str:
        """Start a new task and return its ID."""
        task_id = f"{task_type}:{project_id}:{uuid.uuid4().hex[:8]}"
        with self._lock:
            self.active_tasks[task_id] = {
                "type": task_type,
                "project_id": project_id,
                "started_at": time.time(),
                "cancel_event": None,
                "current": 0,
                "total": 0,
                "message": "",
            }
        self.bus.emit("task_start", {"task_id": task_id, "type": task_type, "project_id": project_id})
        return task_id

    def register_cancel_event(self, task_id: str, event: threading.Event) -> None:
        """Attach a threading.Event the worker checks for cancellation.

        Workers create their own Event, register it here so cancel requests
        can flip it, and check ``event.is_set()`` at safe boundaries (e.g.
        between files in the index/trace builders). Calling this on an
        unknown task is a no-op — the worker may have finished racing the
        registration.
        """
        with self._lock:
            entry = self.active_tasks.get(task_id)
            if entry is not None:
                entry["cancel_event"] = event

    def update(self, task_id: str, message: str, current: int, total: int) -> None:
        """Update progress for a task."""
        with self._lock:
            entry = self.active_tasks.get(task_id)
            if entry is not None:
                entry["message"] = message
                entry["current"] = current
                entry["total"] = total
        self.bus.emit_progress(task_id, message, current, total)

    def finish_task(self, task_id: str, success: bool = True, message: str = "") -> None:
        """Mark a task as finished."""
        with self._lock:
            existed = task_id in self.active_tasks
            if existed:
                del self.active_tasks[task_id]
        if existed:
            self.bus.emit("task_finish", {"task_id": task_id, "success": success, "message": message})

    def request_cancel(self, project_id: str, task_type: Optional[str] = None) -> List[str]:
        """Request cancellation for active tasks matching project (and type).

        Sets the worker's cancel_event when one was registered, and emits
        a ``task_cancel_requested`` event so the queue panel updates
        immediately. The task entry itself is NOT removed here — workers
        clean up via ``finish_task`` once they actually unwind. This keeps
        zombie state visible (a task that ignores cancellation continues
        to show up) instead of silently disappearing from the queue.

        Returns the list of task_ids the request was delivered to.
        """
        delivered: List[str] = []
        with self._lock:
            for task_id, entry in self.active_tasks.items():
                if entry.get("project_id") != project_id:
                    continue
                if task_type is not None and entry.get("type") != task_type:
                    continue
                evt = entry.get("cancel_event")
                if evt is not None:
                    evt.set()
                delivered.append(task_id)
        for task_id in delivered:
            self.bus.emit("task_cancel_requested", {"task_id": task_id, "project_id": project_id})
        return delivered

    def list_active(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Snapshot of active tasks; safe to read without holding the lock."""
        with self._lock:
            entries = []
            for task_id, entry in self.active_tasks.items():
                if project_id is not None and entry.get("project_id") != project_id:
                    continue
                entries.append({
                    "task_id": task_id,
                    "type": entry.get("type"),
                    "project_id": entry.get("project_id"),
                    "started_at": entry.get("started_at"),
                    "current": entry.get("current", 0),
                    "total": entry.get("total", 0),
                    "message": entry.get("message", ""),
                    "cancel_requested": bool(entry.get("cancel_event") and entry["cancel_event"].is_set()),
                    "cancellable": entry.get("cancel_event") is not None,
                })
        return entries

# Singleton accessor
_progress_manager = None
def get_progress_manager() -> ProgressManager:
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressManager()
    return _progress_manager
