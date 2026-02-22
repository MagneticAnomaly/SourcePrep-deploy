"""Event system for publish/subscribe pattern within the application."""

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """Simple in-process event bus for decoupled communication."""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: List[Dict[str, Any]] = []

    def subscribe(self, event_type: str, handler: Callable):
        """Register a handler for an event type."""
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        """Remove a handler for an event type."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Publish an event to all subscribers."""
        event = {"type": event_type, "data": data or {}}
        self._history.append(event)
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error("Event handler failed for %s: %s", event_type, e)

    def get_history(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get event history, optionally filtered by type."""
        if event_type:
            return [e for e in self._history if e["type"] == event_type]
        return list(self._history)


# Common event types
USER_CREATED = "user.created"
USER_DELETED = "user.deleted"
LOGIN_SUCCESS = "auth.login.success"
LOGIN_FAILED = "auth.login.failed"
CACHE_MISS = "cache.miss"
CACHE_EVICTED = "cache.evicted"
JOB_COMPLETED = "job.completed"
JOB_FAILED = "job.failed"
