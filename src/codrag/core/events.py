"""
Event Bus and Progress Tracking for CoDRAG.

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
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProgressManager, cls).__new__(cls)
            cls._instance.bus = get_event_bus()
            cls._instance.active_tasks = {}
        return cls._instance

    def start_task(self, task_type: str, project_id: str) -> str:
        """Start a new task and return its ID."""
        task_id = f"{task_type}:{project_id}:{uuid.uuid4().hex[:8]}"
        self.active_tasks[task_id] = {"type": task_type, "project_id": project_id}
        self.bus.emit("task_start", {"task_id": task_id, "type": task_type, "project_id": project_id})
        return task_id

    def update(self, task_id: str, message: str, current: int, total: int) -> None:
        """Update progress for a task."""
        self.bus.emit_progress(task_id, message, current, total)

    def finish_task(self, task_id: str, success: bool = True, message: str = "") -> None:
        """Mark a task as finished."""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
            self.bus.emit("task_finish", {"task_id": task_id, "success": success, "message": message})

# Singleton accessor
_progress_manager = None
def get_progress_manager() -> ProgressManager:
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressManager()
    return _progress_manager
