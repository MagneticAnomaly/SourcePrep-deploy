"""
CoDRAG Pipeline Journal — Phase 25 (Crash Protection)
======================================================

Persistent "black box" recorder for pipeline runs.  Survives process
crashes, power loss, and browser refreshes.

**Design:**
  - Uses the shared ``codrag_settings.db`` SQLite database.
  - Dedicated ``pipeline_runs`` table (not the generic key-value store).
  - Every state transition is written *before* the work begins (WAL).
  - Heartbeat column updated every ~10s by running workers.
  - On startup, any row still marked ``running`` is a crash survivor.

**Recovery protocol:**
  1. On init, scan for ``status = 'running'``.
  2. If ``last_heartbeat`` is stale (>60s old), mark as ``crashed``.
  3. Expose crashed runs via ``get_crashed_runs()`` for the UI to offer
     "Resume" or "Discard".

**Idempotency insight:**
  Each pipeline stage reads from the *previous* stage's output and
  overwrites its own.  A crash mid-stage leaves the previous stage's
  files intact.  Therefore, restarting the crashed stage is always safe.

**Checkpoint files:**
  Before stages that *modify* existing overlay files (deepening re-writes
  ``trace_epistemic.jsonl``), we copy to ``.bak``.  On corrupt detection,
  we restore from ``.bak``.

Usage::

    from codrag.services.pipeline_journal import journal

    run_id = journal.start_run("proj-1", "fast_sync", ["structural", "catalogue", ...])
    journal.stage_started(run_id, "structural")
    journal.heartbeat(run_id)
    journal.stage_completed(run_id, "structural")
    journal.run_completed(run_id)

    # On startup:
    crashed = journal.recover_crashed_runs()
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# How many seconds without a heartbeat before we consider a run crashed
HEARTBEAT_TIMEOUT_S = 60.0

# How often the heartbeat thread updates (seconds)
HEARTBEAT_INTERVAL_S = 10.0


# ── Data Classes ────────────────────────────────────────────────

@dataclass
class JournalEntry:
    """A single pipeline run record from the journal."""
    run_id: str
    project_id: str
    group: str  # "fast_sync" | "deep_enrichment"
    status: str  # "running" | "completed" | "failed" | "crashed" | "cancelled"
    stages: List[str]  # ordered stage IDs
    current_stage: Optional[str] = None
    current_stage_index: int = 0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    last_heartbeat: Optional[float] = None
    error: Optional[str] = None
    stage_results: Dict[str, str] = field(default_factory=dict)
    checkpoint_path: Optional[str] = None  # path to .bak checkpoint dir
    chain_deep: bool = False  # whether deep enrichment should chain after fast

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "group": self.group,
            "status": self.status,
            "stages": self.stages,
            "current_stage": self.current_stage,
            "current_stage_index": self.current_stage_index,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "last_heartbeat": self.last_heartbeat,
            "error": self.error,
            "stage_results": self.stage_results,
            "checkpoint_path": self.checkpoint_path,
            "chain_deep": self.chain_deep,
        }

    @staticmethod
    def from_row(row: sqlite3.Row) -> JournalEntry:
        return JournalEntry(
            run_id=row["run_id"],
            project_id=row["project_id"],
            group=row["group_name"],
            status=row["status"],
            stages=json.loads(row["stages"]),
            current_stage=row["current_stage"],
            current_stage_index=row["current_stage_index"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            last_heartbeat=row["last_heartbeat"],
            error=row["error"],
            stage_results=json.loads(row["stage_results"] or "{}"),
            checkpoint_path=row["checkpoint_path"],
            chain_deep=bool(row["chain_deep"]),
        )


# ── Pipeline Journal ────────────────────────────────────────────

class PipelineJournal:
    """SQLite-backed crash-resilient pipeline run tracker."""

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._heartbeat_threads: Dict[str, threading.Event] = {}  # run_id → stop_event

    # ── Lifecycle ────────────────────────────────────────────────

    def init(self, db_path: Path) -> None:
        """Initialize the journal.  Reuses the settings DB file."""
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
            # Immediately mark stale "running" entries as crashed while we
            # hold the only active connection — prevents zombie heartbeat
            # rows from blocking writes on other connections later.
            self._cleanup_zombies_on_init()
            logger.info("Pipeline journal initialized: %s", db_path)

    def _cleanup_zombies_on_init(self) -> None:
        """Mark any 'running' pipeline_runs with stale heartbeats as crashed.

        Called during init() so we clean up before other stores open
        connections and before crash recovery tries its own writes.
        """
        assert self._conn is not None
        try:
            cutoff = time.time() - HEARTBEAT_TIMEOUT_S
            cur = self._conn.execute(
                "UPDATE pipeline_runs SET status = 'crashed', "
                "error = 'Process terminated (cleaned on restart)' "
                "WHERE status = 'running' AND (last_heartbeat IS NULL OR last_heartbeat < ?)",
                (cutoff,),
            )
            self._conn.commit()
            if cur.rowcount > 0:
                logger.warning(
                    "Journal init: marked %d zombie pipeline run(s) as crashed",
                    cur.rowcount,
                )
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass

    def close(self) -> None:
        """Close the database and stop all heartbeat threads."""
        # Stop all heartbeat threads
        for stop_event in self._heartbeat_threads.values():
            stop_event.set()
        self._heartbeat_threads.clear()

        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id             TEXT PRIMARY KEY,
                project_id         TEXT NOT NULL,
                group_name         TEXT NOT NULL,
                status             TEXT NOT NULL DEFAULT 'running',
                stages             TEXT NOT NULL,
                current_stage      TEXT,
                current_stage_index INTEGER NOT NULL DEFAULT 0,
                started_at         REAL,
                finished_at        REAL,
                last_heartbeat     REAL,
                error              TEXT,
                stage_results      TEXT NOT NULL DEFAULT '{}',
                checkpoint_path    TEXT,
                chain_deep         INTEGER NOT NULL DEFAULT 0,
                created_at         REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_project
                ON pipeline_runs (project_id, status);
        """)
        self._conn.commit()

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("PipelineJournal not initialized. Call journal.init(db_path) first.")
        return self._conn

    # ── Write Operations ─────────────────────────────────────────

    def start_run(
        self,
        project_id: str,
        group: str,
        stages: List[str],
        chain_deep: bool = False,
    ) -> str:
        """Record a new pipeline run.  Returns the run_id."""
        conn = self._require_conn()
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        now = time.time()
        first_stage = stages[0] if stages else None

        with self._lock:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (run_id, project_id, group_name, status, stages,
                    current_stage, current_stage_index, started_at,
                    last_heartbeat, stage_results, chain_deep, created_at)
                   VALUES (?, ?, ?, 'running', ?, ?, 0, ?, ?, '{}', ?, ?)""",
                (run_id, project_id, group, json.dumps(stages),
                 first_stage, now, now, int(chain_deep), now),
            )
            conn.commit()

        logger.info("Journal: started run %s (%s/%s)", run_id, project_id, group)
        self._start_heartbeat(run_id)
        return run_id

    def stage_started(self, run_id: str, stage: str, stage_index: int) -> None:
        """Record that a stage has begun executing."""
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            conn.execute(
                """UPDATE pipeline_runs
                   SET current_stage = ?, current_stage_index = ?, last_heartbeat = ?
                   WHERE run_id = ?""",
                (stage, stage_index, now, run_id),
            )
            conn.commit()
        logger.debug("Journal: stage started %s/%s", run_id, stage)

    def stage_completed(self, run_id: str, stage: str) -> None:
        """Record that a stage finished successfully."""
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            row = conn.execute(
                "SELECT stage_results FROM pipeline_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row:
                results = json.loads(row["stage_results"] or "{}")
                results[stage] = "completed"
                conn.execute(
                    """UPDATE pipeline_runs
                       SET stage_results = ?, last_heartbeat = ?
                       WHERE run_id = ?""",
                    (json.dumps(results), now, run_id),
                )
                conn.commit()
        logger.debug("Journal: stage completed %s/%s", run_id, stage)

    def stage_failed(self, run_id: str, stage: str, error: str) -> None:
        """Record that a stage failed."""
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            row = conn.execute(
                "SELECT stage_results FROM pipeline_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row:
                results = json.loads(row["stage_results"] or "{}")
                results[stage] = "failed"
                conn.execute(
                    """UPDATE pipeline_runs
                       SET status = 'failed', stage_results = ?,
                           error = ?, finished_at = ?, last_heartbeat = ?
                       WHERE run_id = ?""",
                    (json.dumps(results), error, now, now, run_id),
                )
                conn.commit()
        self._stop_heartbeat(run_id)
        logger.info("Journal: run failed %s at stage %s: %s", run_id, stage, error)

    def run_completed(self, run_id: str) -> None:
        """Record that the entire run finished successfully."""
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            conn.execute(
                """UPDATE pipeline_runs
                   SET status = 'completed', finished_at = ?, last_heartbeat = ?
                   WHERE run_id = ?""",
                (now, now, run_id),
            )
            conn.commit()
        self._stop_heartbeat(run_id)
        logger.info("Journal: run completed %s", run_id)

    def run_cancelled(self, run_id: str) -> None:
        """Record that the run was cancelled by the user."""
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            conn.execute(
                """UPDATE pipeline_runs
                   SET status = 'cancelled', error = 'Cancelled by user',
                       finished_at = ?, last_heartbeat = ?
                   WHERE run_id = ?""",
                (now, now, run_id),
            )
            conn.commit()
        self._stop_heartbeat(run_id)
        logger.info("Journal: run cancelled %s", run_id)

    def set_checkpoint(self, run_id: str, checkpoint_path: str) -> None:
        """Record the path to a checkpoint backup directory."""
        conn = self._require_conn()
        with self._lock:
            conn.execute(
                "UPDATE pipeline_runs SET checkpoint_path = ? WHERE run_id = ?",
                (checkpoint_path, run_id),
            )
            conn.commit()

    def heartbeat(self, run_id: str) -> None:
        """Update the heartbeat timestamp for a running run."""
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            conn.execute(
                "UPDATE pipeline_runs SET last_heartbeat = ? WHERE run_id = ? AND status = 'running'",
                (now, run_id),
            )
            conn.commit()

    # ── Read Operations ──────────────────────────────────────────

    def get_run(self, run_id: str) -> Optional[JournalEntry]:
        """Get a specific run by ID."""
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return JournalEntry.from_row(row) if row else None

    def get_active_run(self, project_id: str, group: str) -> Optional[JournalEntry]:
        """Get the currently running run for a project+group, if any."""
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                """SELECT * FROM pipeline_runs
                   WHERE project_id = ? AND group_name = ? AND status = 'running'
                   ORDER BY started_at DESC LIMIT 1""",
                (project_id, group),
            ).fetchone()
        return JournalEntry.from_row(row) if row else None

    def get_latest_run(self, project_id: str, group: str) -> Optional[JournalEntry]:
        """Get the most recent run for a project+group (any status)."""
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                """SELECT * FROM pipeline_runs
                   WHERE project_id = ? AND group_name = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id, group),
            ).fetchone()
        return JournalEntry.from_row(row) if row else None

    def get_project_runs(self, project_id: str, limit: int = 20) -> List[JournalEntry]:
        """Get recent runs for a project."""
        conn = self._require_conn()
        with self._lock:
            rows = conn.execute(
                """SELECT * FROM pipeline_runs
                   WHERE project_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        return [JournalEntry.from_row(r) for r in rows]

    # ── Crash Recovery ───────────────────────────────────────────

    def recover_crashed_runs(self, timeout_s: float = HEARTBEAT_TIMEOUT_S) -> List[JournalEntry]:
        """Detect and mark crashed runs.  Called once on startup.

        Any run marked 'running' whose heartbeat is older than ``timeout_s``
        is transitioned to 'crashed'.  Returns the list of newly-crashed runs.
        """
        conn = self._require_conn()
        now = time.time()
        cutoff = now - timeout_s

        with self._lock:
            rows = conn.execute(
                """SELECT * FROM pipeline_runs
                   WHERE status = 'running' AND (last_heartbeat IS NULL OR last_heartbeat < ?)""",
                (cutoff,),
            ).fetchall()

            crashed: List[JournalEntry] = []
            for row in rows:
                entry = JournalEntry.from_row(row)
                conn.execute(
                    """UPDATE pipeline_runs
                       SET status = 'crashed', error = 'Process terminated unexpectedly'
                       WHERE run_id = ?""",
                    (entry.run_id,),
                )
                entry.status = "crashed"
                entry.error = "Process terminated unexpectedly"
                crashed.append(entry)
                logger.warning(
                    "Journal: recovered crashed run %s (%s/%s) — was at stage %s",
                    entry.run_id, entry.project_id, entry.group, entry.current_stage,
                )

            if crashed:
                conn.commit()

        return crashed

    def get_crashed_runs(self, project_id: Optional[str] = None) -> List[JournalEntry]:
        """Get all runs with status 'crashed' (not yet resolved)."""
        conn = self._require_conn()
        with self._lock:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM pipeline_runs WHERE status = 'crashed' AND project_id = ?",
                    (project_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM pipeline_runs WHERE status = 'crashed'"
                ).fetchall()
        return [JournalEntry.from_row(r) for r in rows]

    def resolve_crashed_run(self, run_id: str, action: str = "discarded") -> bool:
        """Mark a crashed run as resolved.

        ``action`` is 'resumed' (will create a new run) or 'discarded'.
        """
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            cur = conn.execute(
                """UPDATE pipeline_runs
                   SET status = ?, finished_at = ?
                   WHERE run_id = ? AND status = 'crashed'""",
                (action, now, run_id),
            )
            conn.commit()
        resolved = cur.rowcount > 0
        if resolved:
            logger.info("Journal: resolved crashed run %s → %s", run_id, action)
        return resolved

    def clear_project(self, project_id: str) -> int:
        """Delete all journal entries for a project."""
        conn = self._require_conn()
        # Stop any heartbeats for this project
        with self._lock:
            rows = conn.execute(
                "SELECT run_id FROM pipeline_runs WHERE project_id = ? AND status = 'running'",
                (project_id,),
            ).fetchall()
        for row in rows:
            self._stop_heartbeat(row["run_id"])

        with self._lock:
            cur = conn.execute(
                "DELETE FROM pipeline_runs WHERE project_id = ?", (project_id,)
            )
            conn.commit()
        return cur.rowcount

    # ── Heartbeat Thread ─────────────────────────────────────────

    def _start_heartbeat(self, run_id: str) -> None:
        """Start a background thread that updates the heartbeat for a run."""
        stop_event = threading.Event()
        self._heartbeat_threads[run_id] = stop_event

        def _beat() -> None:
            while not stop_event.wait(HEARTBEAT_INTERVAL_S):
                try:
                    self.heartbeat(run_id)
                except Exception:
                    logger.debug("Heartbeat write failed for %s", run_id, exc_info=True)
                    break

        t = threading.Thread(
            target=_beat,
            name=f"journal-heartbeat-{run_id[:16]}",
            daemon=True,
        )
        t.start()

    def _stop_heartbeat(self, run_id: str) -> None:
        """Stop the heartbeat thread for a run."""
        stop_event = self._heartbeat_threads.pop(run_id, None)
        if stop_event:
            stop_event.set()


# ── Module-level singleton ───────────────────────────────────────
journal = PipelineJournal()
