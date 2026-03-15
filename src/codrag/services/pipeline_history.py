"""
Pipeline Run History — Phase 49 (Process Info)
===============================================

SQLite-backed historical registry of all pipeline runs.
Enables fast queries across runs: by project, model, quality, version.

Stored in the shared ``codrag_settings.db`` alongside the pipeline journal.

Usage::

    from codrag.services.pipeline_history import history

    history.init(db_path)
    history.record_run(metadata)

    runs = history.get_project_runs("proj-1", limit=10)
    run = history.get_run("run-abc123")
    old = history.get_runs_before(project_id, days_ago=120)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from codrag.services.pipeline_metadata import PipelineRunMetadata

logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """A single row from the pipeline_run_history table."""
    run_id: str
    project_id: str
    group: str
    status: str
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    codrag_version: Optional[str] = None
    engine_backend: Optional[str] = None
    quality_summary: Optional[Dict[str, Any]] = None
    models_used: Optional[Dict[str, Dict[str, Any]]] = None
    total_stages: int = 0
    completed_stages: int = 0
    failed_stages: int = 0
    metadata_file: Optional[str] = None
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "group": self.group,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_seconds": self.elapsed_seconds,
            "codrag_version": self.codrag_version,
            "engine_backend": self.engine_backend,
            "total_stages": self.total_stages,
            "completed_stages": self.completed_stages,
            "failed_stages": self.failed_stages,
            "created_at": self.created_at,
        }
        if self.quality_summary:
            d["quality_summary"] = self.quality_summary
        if self.models_used:
            d["models_used"] = self.models_used
        if self.metadata_file:
            d["metadata_file"] = self.metadata_file
        return d

    @staticmethod
    def from_row(row: sqlite3.Row) -> "HistoryEntry":
        return HistoryEntry(
            run_id=row["run_id"],
            project_id=row["project_id"],
            group=row["group_name"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            elapsed_seconds=row["elapsed_seconds"],
            codrag_version=row["codrag_version"],
            engine_backend=row["engine_backend"],
            quality_summary=_safe_json_loads(row["quality_summary"]),
            models_used=_safe_json_loads(row["models_used"]),
            total_stages=row["total_stages"],
            completed_stages=row["completed_stages"],
            failed_stages=row["failed_stages"],
            metadata_file=row["metadata_file"],
            created_at=row["created_at"],
        )


def _safe_json_loads(s: Optional[str]) -> Optional[Dict]:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


class PipelineRunHistory:
    """SQLite-backed historical registry of pipeline runs."""

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    def init(self, db_path: Path) -> None:
        """Initialize the history table.  Reuses the settings DB."""
        with self._lock:
            if self._conn is not None:
                return
            self._conn = sqlite3.connect(
                str(db_path),
                check_same_thread=False,
                isolation_level="DEFERRED",
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._create_tables()
            logger.info("Pipeline history initialized: %s", db_path)

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_run_history (
                run_id             TEXT PRIMARY KEY,
                project_id         TEXT NOT NULL,
                group_name         TEXT NOT NULL,
                status             TEXT NOT NULL,
                started_at         REAL,
                finished_at        REAL,
                elapsed_seconds    REAL,
                codrag_version     TEXT,
                engine_backend     TEXT,
                quality_summary    TEXT,
                models_used        TEXT,
                total_stages       INTEGER NOT NULL DEFAULT 0,
                completed_stages   INTEGER NOT NULL DEFAULT 0,
                failed_stages      INTEGER NOT NULL DEFAULT 0,
                metadata_file      TEXT,
                created_at         REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_run_history_project
                ON pipeline_run_history (project_id, started_at DESC);

            CREATE INDEX IF NOT EXISTS idx_run_history_status
                ON pipeline_run_history (status);

            CREATE INDEX IF NOT EXISTS idx_run_history_version
                ON pipeline_run_history (codrag_version);
        """)
        self._conn.commit()

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("PipelineRunHistory not initialized.")
        return self._conn

    # ── Write ─────────────────────────────────────────────────────

    def record_run(self, meta: PipelineRunMetadata, metadata_file: Optional[str] = None) -> None:
        """Insert a completed run into the history table."""
        conn = self._require_conn()

        # Parse ISO timestamps to epoch floats
        started_at = _iso_to_epoch(meta.started_at)
        finished_at = _iso_to_epoch(meta.finished_at)

        completed = sum(1 for s in meta.stages if s.status == "completed")
        failed = sum(1 for s in meta.stages if s.status == "failed")

        with self._lock:
            conn.execute(
                """INSERT OR REPLACE INTO pipeline_run_history
                   (run_id, project_id, group_name, status,
                    started_at, finished_at, elapsed_seconds,
                    codrag_version, engine_backend,
                    quality_summary, models_used,
                    total_stages, completed_stages, failed_stages,
                    metadata_file, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    meta.run_id,
                    meta.project_id,
                    meta.group,
                    meta.status,
                    started_at,
                    finished_at,
                    meta.elapsed_seconds,
                    meta.codrag_version,
                    meta.engine_backend,
                    json.dumps(meta.quality_summary) if meta.quality_summary else None,
                    json.dumps(meta.models_used) if meta.models_used else None,
                    len(meta.stages),
                    completed,
                    failed,
                    metadata_file,
                    time.time(),
                ),
            )
            conn.commit()
        logger.info("History: recorded run %s (%s/%s) — %s", meta.run_id, meta.project_id, meta.group, meta.status)

    # ── Read ──────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> Optional[HistoryEntry]:
        """Get a single run by ID."""
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                "SELECT * FROM pipeline_run_history WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return HistoryEntry.from_row(row) if row else None

    def get_project_runs(
        self,
        project_id: str,
        limit: int = 20,
        group: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[HistoryEntry]:
        """Get recent runs for a project with optional filters."""
        conn = self._require_conn()
        query = "SELECT * FROM pipeline_run_history WHERE project_id = ?"
        params: List[Any] = [project_id]

        if group:
            query += " AND group_name = ?"
            params.append(group)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = conn.execute(query, params).fetchall()
        return [HistoryEntry.from_row(r) for r in rows]

    def get_runs_by_model(self, model_name: str, limit: int = 50) -> List[HistoryEntry]:
        """Find runs that used a specific model (searches models_used JSON)."""
        conn = self._require_conn()
        with self._lock:
            rows = conn.execute(
                """SELECT * FROM pipeline_run_history
                   WHERE models_used LIKE ?
                   ORDER BY started_at DESC LIMIT ?""",
                (f"%{model_name}%", limit),
            ).fetchall()
        return [HistoryEntry.from_row(r) for r in rows]

    def get_runs_by_version(self, codrag_version: str, limit: int = 50) -> List[HistoryEntry]:
        """Find runs from a specific CoDRAG version."""
        conn = self._require_conn()
        with self._lock:
            rows = conn.execute(
                """SELECT * FROM pipeline_run_history
                   WHERE codrag_version = ?
                   ORDER BY started_at DESC LIMIT ?""",
                (codrag_version, limit),
            ).fetchall()
        return [HistoryEntry.from_row(r) for r in rows]

    def get_runs_before(self, project_id: str, days_ago: int = 90) -> List[HistoryEntry]:
        """Find runs older than N days for a project."""
        conn = self._require_conn()
        cutoff = time.time() - (days_ago * 86400)
        with self._lock:
            rows = conn.execute(
                """SELECT * FROM pipeline_run_history
                   WHERE project_id = ? AND started_at < ?
                   ORDER BY started_at DESC""",
                (project_id, cutoff),
            ).fetchall()
        return [HistoryEntry.from_row(r) for r in rows]

    def get_latest_run(self, project_id: str, group: Optional[str] = None) -> Optional[HistoryEntry]:
        """Get the most recent run for a project."""
        runs = self.get_project_runs(project_id, limit=1, group=group)
        return runs[0] if runs else None

    def count_runs(self, project_id: Optional[str] = None) -> int:
        """Count total runs (optionally for a specific project)."""
        conn = self._require_conn()
        with self._lock:
            if project_id:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM pipeline_run_history WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM pipeline_run_history"
                ).fetchone()
        return row["cnt"] if row else 0

    def clear_project(self, project_id: str) -> int:
        """Delete all history for a project."""
        conn = self._require_conn()
        with self._lock:
            cur = conn.execute(
                "DELETE FROM pipeline_run_history WHERE project_id = ?",
                (project_id,),
            )
            conn.commit()
        return cur.rowcount


def _iso_to_epoch(iso_str: Optional[str]) -> Optional[float]:
    """Convert ISO timestamp string to Unix epoch float."""
    if not iso_str:
        return None
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_str)
        return dt.timestamp()
    except Exception:
        return None


# ── Module-level singleton ────────────────────────────────────────
history = PipelineRunHistory()
