"""
Prep Antibody Store — Phase 87.1 (Persistence)
==================================================

Persistent SQLite store for codebase immune system antibodies.

Antibodies are (trigger, response) pairs derived from concepts that detect
architectural violations when files change. This store persists them so they
survive across daemon restarts and MCP sessions.

**Design:**
  - Uses the shared ``prep_settings.db`` SQLite database (same pattern as
    concept_store and settings_store).
  - Dedicated ``antibodies`` table with JSON-encoded trigger/response columns.
  - CRUD operations: save, get, list, update_status, record_trigger,
    record_dismiss, delete.
  - Thread-safe via threading.Lock (same pattern as ConceptStore).

**Usage:**
  ``from prep.services.antibody_store import antibody_store``

  ``antibody_store.save("proj-1", antibody)``
  ``antibody_store.list_antibodies("proj-1", status="active")``
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional

from prep.core.antibodies import Antibody, Trigger, Response, Severity

logger = logging.getLogger(__name__)


class AntibodyStore:
    """SQLite-backed antibody persistence store."""

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    # ── Lifecycle ────────────────────────────────────────────────

    def init(self, db_path: Path) -> None:
        """Initialize the store. Reuses the settings DB file."""
        with self._lock:
            if self._conn is not None:
                return
            self._conn = sqlite3.connect(
                str(db_path),
                check_same_thread=False,
                isolation_level="DEFERRED",
                timeout=30,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=DELETE")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
            self._create_tables()
            logger.info("Antibody store initialized: %s", db_path)

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS antibodies (
                id                TEXT PRIMARY KEY,
                project_id        TEXT NOT NULL,
                name              TEXT NOT NULL,
                source_concept_id TEXT NOT NULL DEFAULT '',
                trigger_json      TEXT NOT NULL,
                response_json     TEXT NOT NULL,
                severity          TEXT NOT NULL DEFAULT 'warn',
                status            TEXT NOT NULL DEFAULT 'testing',
                created_at        REAL NOT NULL,
                last_triggered    REAL,
                trigger_count     INTEGER NOT NULL DEFAULT 0,
                dismiss_count     INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_antibody_project
                ON antibodies (project_id);
            CREATE INDEX IF NOT EXISTS idx_antibody_status
                ON antibodies (project_id, status);
        """)
        self._conn.commit()

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError(
                "AntibodyStore not initialized. Call antibody_store.init(db_path) first."
            )
        return self._conn

    # ── Write Operations ─────────────────────────────────────────

    def save(self, project_id: str, antibody: Antibody) -> None:
        """Save an antibody. Upserts by antibody.id."""
        conn = self._require_conn()
        with self._lock:
            conn.execute(
                """INSERT OR REPLACE INTO antibodies
                   (id, project_id, name, source_concept_id,
                    trigger_json, response_json, severity, status,
                    created_at, last_triggered, trigger_count, dismiss_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    antibody.id,
                    project_id,
                    antibody.name,
                    antibody.source_concept_id,
                    json.dumps(antibody.trigger.to_dict()),
                    json.dumps(antibody.response.to_dict()),
                    antibody.severity.value,
                    antibody.status,
                    antibody.created_at,
                    antibody.last_triggered,
                    antibody.trigger_count,
                    antibody.dismiss_count,
                ),
            )
            conn.commit()

    def save_many(self, project_id: str, antibodies: List[Antibody]) -> int:
        """Batch-save antibodies in a single transaction.

        F-37: per-antibody commits hit writer-lock contention on the
        shared settings.db (each save took ~10s busy_timeout). One
        transaction holds the lock once for the whole batch.
        """
        if not antibodies:
            return 0
        conn = self._require_conn()
        rows = [
            (
                ab.id,
                project_id,
                ab.name,
                ab.source_concept_id,
                json.dumps(ab.trigger.to_dict()),
                json.dumps(ab.response.to_dict()),
                ab.severity.value,
                ab.status,
                ab.created_at,
                ab.last_triggered,
                ab.trigger_count,
                ab.dismiss_count,
            )
            for ab in antibodies
        ]
        with self._lock:
            conn.executemany(
                """INSERT OR REPLACE INTO antibodies
                   (id, project_id, name, source_concept_id,
                    trigger_json, response_json, severity, status,
                    created_at, last_triggered, trigger_count, dismiss_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            conn.commit()
        return len(rows)

    def update_status(self, antibody_id: str, status: str) -> bool:
        """Update the status of an antibody. Returns True if it existed."""
        conn = self._require_conn()
        with self._lock:
            cur = conn.execute(
                "UPDATE antibodies SET status = ? WHERE id = ?",
                (status, antibody_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def record_trigger(self, antibody_id: str) -> bool:
        """Increment trigger_count and set last_triggered. Returns True if found."""
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            cur = conn.execute(
                """UPDATE antibodies
                   SET trigger_count = trigger_count + 1, last_triggered = ?
                   WHERE id = ?""",
                (now, antibody_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def record_dismiss(self, antibody_id: str) -> bool:
        """Increment dismiss_count. Returns True if found."""
        conn = self._require_conn()
        with self._lock:
            cur = conn.execute(
                """UPDATE antibodies
                   SET dismiss_count = dismiss_count + 1
                   WHERE id = ?""",
                (antibody_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def delete(self, antibody_id: str) -> bool:
        """Delete an antibody. Returns True if it existed."""
        conn = self._require_conn()
        with self._lock:
            cur = conn.execute(
                "DELETE FROM antibodies WHERE id = ?",
                (antibody_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def clear_project(self, project_id: str) -> int:
        """Delete every antibody for a project. Returns rows deleted.

        Called by Reset All / Reset Enrichment / Reset Finalize so the
        derived immune-system state doesn't survive a reset. Antibodies
        are fully regenerated by the antibodies stage from concepts with
        assertions, so wiping them is always safe.
        """
        conn = self._require_conn()
        with self._lock:
            cur = conn.execute(
                "DELETE FROM antibodies WHERE project_id = ?",
                (project_id,),
            )
            conn.commit()
            return cur.rowcount

    # ── Read Operations ──────────────────────────────────────────

    def get(self, antibody_id: str) -> Optional[Antibody]:
        """Get a single antibody by ID."""
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                "SELECT * FROM antibodies WHERE id = ?",
                (antibody_id,),
            ).fetchone()
        return self._row_to_antibody(row) if row else None

    def list_antibodies(
        self,
        project_id: str,
        status: Optional[str] = None,
    ) -> List[Antibody]:
        """List antibodies for a project, optionally filtered by status."""
        conn = self._require_conn()
        sql = "SELECT * FROM antibodies WHERE project_id = ?"
        params: list = [project_id]

        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY created_at DESC"

        with self._lock:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_antibody(r) for r in rows]

    # ── Internal ─────────────────────────────────────────────────

    @staticmethod
    def _row_to_antibody(row: sqlite3.Row) -> Antibody:
        """Convert a database row to an Antibody dataclass."""
        trigger_dict = json.loads(row["trigger_json"])
        response_dict = json.loads(row["response_json"])
        return Antibody(
            id=row["id"],
            name=row["name"],
            source_concept_id=row["source_concept_id"],
            trigger=Trigger.from_dict(trigger_dict),
            response=Response.from_dict(response_dict),
            severity=Severity(row["severity"]),
            status=row["status"],
            created_at=row["created_at"],
            last_triggered=row["last_triggered"],
            trigger_count=row["trigger_count"],
            dismiss_count=row["dismiss_count"],
        )


# ── Singleton ───────────────────────────────────────────────────

antibody_store = AntibodyStore()
