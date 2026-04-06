"""
CoDRAG Observation Store — Phase 39 (Session Continuity)
=========================================================

Persistent store for agent observations linked to files and symbols
in the trace graph.  Survives process restarts and enables cross-session
continuity — the agent remembers what it learned.

**Design:**
  - Uses the shared ``codrag_settings.db`` SQLite database.
  - Dedicated ``observations`` table with FTS5 virtual table for search.
  - Observations are linked to files/symbols via ``file_path`` and
    ``symbol_fqn`` columns.
  - When files change (detected by ScopeOrchestrator), linked observations
    are automatically marked stale.
  - No feature gate — observations work on all tiers (Free, Pro, etc.).

**Usage:**
  ``from codrag.services.observation_store import observation_store``

  ``obs_id = observation_store.save("proj-1", "Auth uses JWT tokens", file_path="src/auth.py")``
  ``results = observation_store.get_for_query("proj-1", "authentication")``
  ``observation_store.mark_stale_batch("proj-1", ["src/auth.py"], "file modified")``
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Maximum observations per project (prevents unbounded growth)
MAX_OBSERVATIONS_PER_PROJECT = 500

# Maximum content length for a single observation
MAX_OBSERVATION_CHARS = 2000

# Categories
VALID_CATEGORIES = {"note", "decision", "bug", "pattern", "assumption"}


# ── Data Classes ────────────────────────────────────────────────

@dataclass
class Observation:
    """A single agent observation."""
    id: str
    project_id: str
    content: str
    file_path: Optional[str] = None
    symbol_fqn: Optional[str] = None
    trace_node_id: Optional[str] = None
    category: str = "note"
    created_at: float = 0.0
    updated_at: Optional[float] = None
    stale: bool = False
    stale_reason: Optional[str] = None
    created_by: Optional[str] = None
    visibility: str = "shared"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "project_id": self.project_id,
            "content": self.content,
            "category": self.category,
            "created_at": self.created_at,
            "stale": self.stale,
        }
        if self.file_path:
            d["file_path"] = self.file_path
        if self.symbol_fqn:
            d["symbol_fqn"] = self.symbol_fqn
        if self.trace_node_id:
            d["trace_node_id"] = self.trace_node_id
        if self.updated_at:
            d["updated_at"] = self.updated_at
        if self.stale_reason:
            d["stale_reason"] = self.stale_reason
        if self.created_by:
            d["created_by"] = self.created_by
        if self.visibility != "shared":
            d["visibility"] = self.visibility
        return d

    @staticmethod
    def from_row(row: sqlite3.Row) -> Observation:
        keys = row.keys()
        return Observation(
            id=row["id"],
            project_id=row["project_id"],
            content=row["content"],
            file_path=row["file_path"],
            symbol_fqn=row["symbol_fqn"],
            trace_node_id=row["trace_node_id"],
            category=row["category"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            stale=bool(row["stale"]),
            stale_reason=row["stale_reason"],
            created_by=row["created_by"] if "created_by" in keys else None,
            visibility=row["visibility"] if "visibility" in keys else "shared",
        )


# ── Observation Store ───────────────────────────────────────────

class ObservationStore:
    """SQLite-backed observation store with FTS5 search."""

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    # ── Lifecycle ────────────────────────────────────────────────

    def init(self, db_path: Path) -> None:
        """Initialize the store.  Reuses the settings DB file."""
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
            logger.info("Observation store initialized: %s", db_path)

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS observations (
                id             TEXT PRIMARY KEY,
                project_id     TEXT NOT NULL,
                content        TEXT NOT NULL,
                file_path      TEXT,
                symbol_fqn     TEXT,
                trace_node_id  TEXT,
                category       TEXT NOT NULL DEFAULT 'note',
                created_at     REAL NOT NULL,
                updated_at     REAL,
                stale          INTEGER NOT NULL DEFAULT 0,
                stale_reason   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_obs_project
                ON observations (project_id);
            CREATE INDEX IF NOT EXISTS idx_obs_file
                ON observations (project_id, file_path);
            CREATE INDEX IF NOT EXISTS idx_obs_stale
                ON observations (project_id, stale);
        """)
        # FTS5 virtual table for content search
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts
                USING fts5(content, id UNINDEXED, content_rowid='rowid')
            """)
        except sqlite3.OperationalError:
            # FTS5 not available — search will fall back to LIKE
            logger.debug("FTS5 not available for observations; falling back to LIKE search")
        self._conn.commit()

        # Phase 73.5: Add collaboration columns (safe to run repeatedly)
        for col, default in [("created_by", "NULL"), ("visibility", "'shared'")]:
            try:
                self._conn.execute(
                    f"ALTER TABLE observations ADD COLUMN {col} TEXT DEFAULT {default}"
                )
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError(
                "ObservationStore not initialized. Call observation_store.init(db_path) first."
            )
        return self._conn

    # ── Write Operations ─────────────────────────────────────────

    def save(
        self,
        project_id: str,
        content: str,
        file_path: Optional[str] = None,
        symbol_fqn: Optional[str] = None,
        trace_node_id: Optional[str] = None,
        category: str = "note",
        created_by: Optional[str] = None,
        visibility: str = "shared",
    ) -> str:
        """Save an observation.  Returns the observation ID.

        If content matches an existing non-stale observation for the same
        project+file, the existing observation is returned (dedup).
        """
        conn = self._require_conn()

        # Validate
        content = content.strip()
        if not content:
            raise ValueError("Observation content cannot be empty")
        if len(content) > MAX_OBSERVATION_CHARS:
            content = content[:MAX_OBSERVATION_CHARS]
        if category not in VALID_CATEGORIES:
            category = "note"

        with self._lock:
            # Dedup: check for existing non-stale observation with same content+file
            existing = conn.execute(
                """SELECT id FROM observations
                   WHERE project_id = ? AND content = ? AND stale = 0
                   AND COALESCE(file_path, '') = COALESCE(?, '')
                   LIMIT 1""",
                (project_id, content, file_path),
            ).fetchone()
            if existing:
                return existing["id"]

            # Enforce per-project limit — evict oldest stale first, then oldest
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM observations WHERE project_id = ?",
                (project_id,),
            ).fetchone()["cnt"]
            if count >= MAX_OBSERVATIONS_PER_PROJECT:
                self._evict_oldest(conn, project_id, count - MAX_OBSERVATIONS_PER_PROJECT + 1)

            obs_id = uuid.uuid4().hex[:12]
            now = time.time()
            conn.execute(
                """INSERT INTO observations
                   (id, project_id, content, file_path, symbol_fqn,
                    trace_node_id, category, created_at, stale,
                    created_by, visibility)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                (obs_id, project_id, content, file_path, symbol_fqn,
                 trace_node_id, category, now, created_by, visibility),
            )
            # FTS insert
            try:
                conn.execute(
                    "INSERT INTO observations_fts (content, id) VALUES (?, ?)",
                    (content, obs_id),
                )
            except sqlite3.OperationalError:
                pass  # FTS not available
            conn.commit()

        logger.debug("Saved observation %s for %s (file=%s)", obs_id, project_id, file_path)
        return obs_id

    def delete(self, observation_id: str) -> bool:
        """Delete a single observation.  Returns True if it existed."""
        conn = self._require_conn()
        with self._lock:
            cur = conn.execute(
                "DELETE FROM observations WHERE id = ?", (observation_id,),
            )
            try:
                conn.execute(
                    "DELETE FROM observations_fts WHERE id = ?", (observation_id,),
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()
            return cur.rowcount > 0

    def clear_project(self, project_id: str) -> int:
        """Delete all observations for a project.  Returns count deleted."""
        conn = self._require_conn()
        with self._lock:
            # Get IDs for FTS cleanup
            ids = [
                r["id"] for r in
                conn.execute(
                    "SELECT id FROM observations WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            ]
            cur = conn.execute(
                "DELETE FROM observations WHERE project_id = ?",
                (project_id,),
            )
            for obs_id in ids:
                try:
                    conn.execute(
                        "DELETE FROM observations_fts WHERE id = ?", (obs_id,),
                    )
                except sqlite3.OperationalError:
                    pass
            conn.commit()
            return cur.rowcount

    def mark_stale_batch(
        self,
        project_id: str,
        file_paths: List[str],
        reason: str = "file modified",
    ) -> int:
        """Mark all observations linked to the given files as stale.

        Returns the number of observations marked stale.
        """
        if not file_paths:
            return 0
        conn = self._require_conn()
        now = time.time()
        total = 0
        with self._lock:
            for fp in file_paths:
                cur = conn.execute(
                    """UPDATE observations
                       SET stale = 1, stale_reason = ?, updated_at = ?
                       WHERE project_id = ? AND file_path = ? AND stale = 0""",
                    (reason, now, project_id, fp),
                )
                total += cur.rowcount
            conn.commit()
        if total > 0:
            logger.info(
                "Marked %d observation(s) stale for %s (%d files changed)",
                total, project_id, len(file_paths),
            )
        return total

    # ── Read Operations ──────────────────────────────────────────

    def get_for_file(
        self,
        project_id: str,
        file_path: str,
        include_stale: bool = True,
    ) -> List[Observation]:
        """Get observations linked to a specific file."""
        conn = self._require_conn()
        sql = "SELECT * FROM observations WHERE project_id = ? AND file_path = ?"
        params: list = [project_id, file_path]
        if not include_stale:
            sql += " AND stale = 0"
        sql += " ORDER BY created_at DESC"
        with self._lock:
            rows = conn.execute(sql, params).fetchall()
        return [Observation.from_row(r) for r in rows]

    @staticmethod
    def _fts_query(query: str) -> str:
        """Convert a natural language query to FTS5 OR query.

        FTS5 defaults to AND for multi-word queries.  For observation
        search we want OR so "JWT authentication" matches observations
        containing *either* word.  Also strips FTS5 special chars.
        """
        # Strip FTS5 operators and special chars
        cleaned = query.replace('"', " ").replace("*", " ").replace("-", " ")
        terms = [t for t in cleaned.split() if len(t) >= 2]
        if not terms:
            return query
        return " OR ".join(f'"{t}"' for t in terms)

    def get_for_query(
        self,
        project_id: str,
        query: str,
        limit: int = 5,
        include_stale: bool = True,
    ) -> List[Observation]:
        """Search observations by content.  Uses FTS5 if available, else LIKE."""
        conn = self._require_conn()
        results: List[Observation] = []

        with self._lock:
            # Try FTS5 first
            try:
                fts_query = self._fts_query(query)
                fts_sql = """
                    SELECT o.* FROM observations o
                    JOIN observations_fts f ON o.id = f.id
                    WHERE f.content MATCH ? AND o.project_id = ?
                """
                if not include_stale:
                    fts_sql += " AND o.stale = 0"
                fts_sql += " ORDER BY rank LIMIT ?"
                rows = conn.execute(fts_sql, (fts_query, project_id, limit)).fetchall()
                results = [Observation.from_row(r) for r in rows]
            except sqlite3.OperationalError:
                # FTS not available — fall back to LIKE
                like_sql = """
                    SELECT * FROM observations
                    WHERE project_id = ? AND content LIKE ?
                """
                if not include_stale:
                    like_sql += " AND stale = 0"
                like_sql += " ORDER BY created_at DESC LIMIT ?"
                rows = conn.execute(
                    like_sql, (project_id, f"%{query}%", limit),
                ).fetchall()
                results = [Observation.from_row(r) for r in rows]

        return results

    def get_recent(
        self,
        project_id: str,
        limit: int = 10,
        include_stale: bool = True,
    ) -> List[Observation]:
        """Get the most recent observations for a project."""
        conn = self._require_conn()
        sql = "SELECT * FROM observations WHERE project_id = ?"
        params: list = [project_id]
        if not include_stale:
            sql += " AND stale = 0"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = conn.execute(sql, params).fetchall()
        return [Observation.from_row(r) for r in rows]

    def get_stats(self, project_id: str) -> Dict[str, Any]:
        """Get observation statistics for a project."""
        conn = self._require_conn()
        with self._lock:
            total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM observations WHERE project_id = ?",
                (project_id,),
            ).fetchone()["cnt"]
            stale = conn.execute(
                "SELECT COUNT(*) AS cnt FROM observations WHERE project_id = ? AND stale = 1",
                (project_id,),
            ).fetchone()["cnt"]
            # Category breakdown
            cats = conn.execute(
                """SELECT category, COUNT(*) AS cnt FROM observations
                   WHERE project_id = ? GROUP BY category""",
                (project_id,),
            ).fetchall()
        return {
            "total": total,
            "stale": stale,
            "fresh": total - stale,
            "by_category": {r["category"]: r["cnt"] for r in cats},
        }

    # ── Internal ─────────────────────────────────────────────────

    def _evict_oldest(self, conn: sqlite3.Connection, project_id: str, count: int) -> None:
        """Evict oldest observations, preferring stale ones first."""
        # Stale first, then oldest
        ids_to_delete = conn.execute(
            """SELECT id FROM observations WHERE project_id = ?
               ORDER BY stale DESC, created_at ASC LIMIT ?""",
            (project_id, count),
        ).fetchall()
        for row in ids_to_delete:
            conn.execute("DELETE FROM observations WHERE id = ?", (row["id"],))
            try:
                conn.execute("DELETE FROM observations_fts WHERE id = ?", (row["id"],))
            except sqlite3.OperationalError:
                pass
        logger.debug("Evicted %d observation(s) for %s", len(ids_to_delete), project_id)


# ── Singleton ───────────────────────────────────────────────────

observation_store = ObservationStore()
