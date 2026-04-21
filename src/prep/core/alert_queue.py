"""Alert queue for the codebase immune system.

Antibodies that fire add alerts to this queue. The ambient context
handler (`prep()`) drains the queue and injects alerts into responses.
Max 3 alerts per drain, deduplicated per session.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import List


@dataclass
class Alert:
    antibody_id: str
    antibody_name: str
    severity: str       # inform | warn | review
    message: str
    file_path: str
    created_at: float = field(default_factory=time.time)


class AlertQueue:
    """In-memory alert queue (single-threaded, used from async context)."""

    def __init__(self, max_per_drain: int = 3):
        self._queue: deque[Alert] = deque(maxlen=100)
        self._seen_this_session: set = set()  # dedup by (antibody_id, file_path)
        self.max_per_drain = max_per_drain

    def push(self, alert: Alert) -> bool:
        """Add an alert. Returns False if deduplicated (already seen this session)."""
        key = (alert.antibody_id, alert.file_path)
        if key in self._seen_this_session:
            return False
        self._seen_this_session.add(key)
        self._queue.append(alert)
        return True

    def drain(self) -> List[Alert]:
        """Pop up to max_per_drain alerts, sorted by severity (review > warn > inform).

        Alerts beyond max_per_drain are re-queued for the next drain.
        """
        severity_order = {"review": 0, "warn": 1, "inform": 2}
        pending = list(self._queue)
        self._queue.clear()
        pending.sort(key=lambda a: severity_order.get(a.severity, 99))
        result = pending[:self.max_per_drain]
        # Re-queue alerts that didn't make the cut
        for alert in pending[self.max_per_drain:]:
            self._queue.append(alert)
        return result

    def pending_count(self) -> int:
        return len(self._queue)

    def reset_session(self) -> None:
        """Clear session dedup tracking (call at start of new session)."""
        self._seen_this_session.clear()


# Global singleton
alert_queue = AlertQueue()
