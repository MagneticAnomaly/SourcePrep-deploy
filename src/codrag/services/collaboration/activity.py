"""ActivityStore — append-only agent action log.

Records what agents do and when. Queryable by time range.
Auto-prunes entries older than 30 days.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_ENTRIES_BEFORE_PRUNE = 1000


@dataclass
class ActivityEntry:
    """A single agent action record."""

    id: str
    project_id: str
    agent_role: str
    action: str
    summary: str
    details: Optional[Dict[str, Any]] = None
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "project_id": self.project_id,
            "agent_role": self.agent_role,
            "action": self.action,
            "summary": self.summary,
            "created_at": self.created_at,
        }
        if self.details:
            d["details"] = self.details
        return d


class ActivityStore:
    """SQLite-backed append-only agent activity log."""

    def __init__(self, db_path: Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False,
            isolation_level="DEFERRED",
            timeout=10,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=DELETE")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_activity (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                action TEXT NOT NULL,
                summary TEXT NOT NULL,
                details_json TEXT,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_activity_project_time
                ON agent_activity(project_id, created_at DESC);
        """)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def log(
        self,
        project_id: str,
        agent_role: str,
        action: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Append an activity entry. Returns the entry ID."""
        entry_id = uuid.uuid4().hex[:12]
        now = time.time()
        details_json = json.dumps(details) if details else None

        with self._lock:
            self._conn.execute(
                """INSERT INTO agent_activity
                   (id, project_id, agent_role, action, summary,
                    details_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (entry_id, project_id, agent_role, action,
                 summary, details_json, now),
            )
            self._conn.commit()

            # Lazy prune when table gets large
            count = self._conn.execute(
                "SELECT COUNT(*) FROM agent_activity WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            if count > MAX_ENTRIES_BEFORE_PRUNE:
                self._prune_locked(project_id, max_age_days=30)

        return entry_id

    def get_recent(
        self,
        project_id: str,
        limit: int = 50,
        since: Optional[float] = None,
    ) -> List[ActivityEntry]:
        """Return recent activity entries, newest first."""
        conditions = ["project_id = ?"]
        params: list = [project_id]

        if since is not None:
            conditions.append("created_at > ?")
            params.append(since)

        where = " AND ".join(conditions)
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM agent_activity WHERE {where}"
                " ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._row_to_entry(r) for r in rows]

    def prune(self, project_id: str, max_age_days: int = 30) -> int:
        """Remove entries older than max_age_days. Returns count deleted."""
        with self._lock:
            return self._prune_locked(project_id, max_age_days)

    def _prune_locked(self, project_id: str, max_age_days: int) -> int:
        cutoff = time.time() - (max_age_days * 86400)
        cur = self._conn.execute(
            "DELETE FROM agent_activity"
            " WHERE project_id = ? AND created_at < ?",
            (project_id, cutoff),
        )
        self._conn.commit()
        return cur.rowcount

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> ActivityEntry:
        details = None
        if row["details_json"]:
            try:
                details = json.loads(row["details_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        return ActivityEntry(
            id=row["id"],
            project_id=row["project_id"],
            agent_role=row["agent_role"],
            action=row["action"],
            summary=row["summary"],
            details=details,
            created_at=row["created_at"],
        )
