"""
CoDRAG Concept Store — Phase 74 (Epistemic Concepts)
=====================================================

Persistent store for codebase concepts — high-level knowledge about
*why* the code is the way it is, business context, design decisions,
brand guidelines, and domain vocabulary.

Concepts are heavier than observations:
  - They have richer metadata (categories, anchors, status lifecycle)
  - They are LLM-seeded and user-curated (seeds → active → archived)
  - They bridge the gap between structural intelligence and understanding

**Design:**
  - Uses the shared ``codrag_settings.db`` SQLite database.
  - Dedicated ``concepts`` table with FTS5 virtual table for search.
  - Concepts are linked to files via ``anchors`` (JSON array of paths).
  - When anchored files change, linked concepts are marked stale.
  - Separate ``concept_questions`` table for clarifying questions.

**Usage:**
  ``from codrag.services.concept_store import concept_store``

  ``cid = concept_store.save(proj_id, "JWT Authentication", "The auth module uses...", category="technical")``
  ``results = concept_store.search(proj_id, "authentication")``
  ``concept_store.mark_stale_batch(proj_id, ["src/auth.py"], "file modified")``
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

# Maximum concepts per project (concepts are heavier than observations)
MAX_CONCEPTS_PER_PROJECT = 200

# Maximum content length for a single concept
MAX_CONCEPT_CHARS = 4000

# Valid categories
VALID_CATEGORIES = {
    "architecture",  # System design, pipeline topologies, overarching structural intent
    "domain",        # Core business logic and rules
    "product",       # UX goals, user journeys, feature prioritization logic
    "epistemic",     # Knowledge representation, agentic reasoning models, cognitive pipelines
    "process",       # CI/CD workflows, operational playbooks, agent operations
    "brand",         # Visual identity, typography, UI/UX feel, tone of voice
    "security",      # Authentication flows, privacy boundaries, data isolation
    "technical",     # Specific implementation constraints, library choices
    "pattern",       # Recurrent code structures and design patterns
    "constraint",    # Performance limits, API restrictions, legacy compatibility
    "decision",      # ADRs, trade-off rationale, why X was chosen over Y
}

# Valid statuses
VALID_STATUSES = {"seed", "active", "archived"}


# ── Data Classes ────────────────────────────────────────────────

@dataclass
class Concept:
    """A single codebase concept."""
    id: str
    project_id: str
    title: str
    content: str
    category: str = "technical"
    status: str = "seed"  # seed → active → archived
    confidence: float = 0.0  # 0.0-1.0, set by seeder
    anchors: List[str] = field(default_factory=list)  # file paths
    tags: List[str] = field(default_factory=list)
    cluster_id: Optional[str] = None
    created_at: float = 0.0
    updated_at: Optional[float] = None
    stale: bool = False
    stale_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "status": self.status,
            "confidence": self.confidence,
            "anchors": self.anchors,
            "tags": self.tags,
            "created_at": self.created_at,
            "stale": self.stale,
        }
        if self.cluster_id:
            d["cluster_id"] = self.cluster_id
        if self.updated_at:
            d["updated_at"] = self.updated_at
        if self.stale_reason:
            d["stale_reason"] = self.stale_reason
        return d

    @staticmethod
    def from_row(row: sqlite3.Row) -> Concept:
        anchors_raw = row["anchors"]
        tags_raw = row["tags"]
        return Concept(
            id=row["id"],
            project_id=row["project_id"],
            title=row["title"],
            content=row["content"],
            category=row["category"],
            status=row["status"],
            confidence=row["confidence"],
            anchors=json.loads(anchors_raw) if anchors_raw else [],
            tags=json.loads(tags_raw) if tags_raw else [],
            cluster_id=row["cluster_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            stale=bool(row["stale"]),
            stale_reason=row["stale_reason"],
        )


@dataclass
class ConceptQuestion:
    """A clarifying question to elicit missing conceptual knowledge."""
    id: str
    project_id: str
    question: str
    context: str  # Why we're asking this question
    suggested_category: str = "technical"
    target_module: Optional[str] = None  # Module the question targets
    answered: bool = False
    answer: Optional[str] = None
    created_concept_id: Optional[str] = None  # ID of concept created from answer
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "project_id": self.project_id,
            "question": self.question,
            "context": self.context,
            "suggested_category": self.suggested_category,
            "answered": self.answered,
            "created_at": self.created_at,
        }
        if self.target_module:
            d["target_module"] = self.target_module
        if self.answer:
            d["answer"] = self.answer
        if self.created_concept_id:
            d["created_concept_id"] = self.created_concept_id
        return d

    @staticmethod
    def from_row(row: sqlite3.Row) -> ConceptQuestion:
        return ConceptQuestion(
            id=row["id"],
            project_id=row["project_id"],
            question=row["question"],
            context=row["context"],
            suggested_category=row["suggested_category"],
            target_module=row["target_module"],
            answered=bool(row["answered"]),
            answer=row["answer"],
            created_concept_id=row["created_concept_id"],
            created_at=row["created_at"],
        )


# ── Concept Store ───────────────────────────────────────────────

class ConceptStore:
    """SQLite-backed concept store with FTS5 search."""

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
            logger.info("Concept store initialized: %s", db_path)

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _create_tables(self) -> None:
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS concepts (
                id             TEXT PRIMARY KEY,
                project_id     TEXT NOT NULL,
                title          TEXT NOT NULL,
                content        TEXT NOT NULL,
                category       TEXT NOT NULL DEFAULT 'technical',
                status         TEXT NOT NULL DEFAULT 'seed',
                confidence     REAL NOT NULL DEFAULT 0.0,
                anchors        TEXT DEFAULT '[]',
                tags           TEXT DEFAULT '[]',
                cluster_id     TEXT,
                created_at     REAL NOT NULL,
                updated_at     REAL,
                stale          INTEGER NOT NULL DEFAULT 0,
                stale_reason   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_concept_project
                ON concepts (project_id);
            CREATE INDEX IF NOT EXISTS idx_concept_status
                ON concepts (project_id, status);
            CREATE INDEX IF NOT EXISTS idx_concept_category
                ON concepts (project_id, category);
            CREATE INDEX IF NOT EXISTS idx_concept_stale
                ON concepts (project_id, stale);

            CREATE TABLE IF NOT EXISTS concept_questions (
                id                 TEXT PRIMARY KEY,
                project_id         TEXT NOT NULL,
                question           TEXT NOT NULL,
                context            TEXT NOT NULL DEFAULT '',
                suggested_category TEXT NOT NULL DEFAULT 'technical',
                target_module      TEXT,
                answered           INTEGER NOT NULL DEFAULT 0,
                answer             TEXT,
                created_concept_id TEXT,
                created_at         REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cq_project
                ON concept_questions (project_id);
            CREATE INDEX IF NOT EXISTS idx_cq_unanswered
                ON concept_questions (project_id, answered);
        """)
        # FTS5 virtual table for content search (title + content)
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS concepts_fts
                USING fts5(title, content, id UNINDEXED, content_rowid='rowid')
            """)
        except sqlite3.OperationalError:
            logger.debug("FTS5 not available for concepts; falling back to LIKE search")
        self._conn.commit()

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError(
                "ConceptStore not initialized. Call concept_store.init(db_path) first."
            )
        return self._conn

    # ── Write Operations ─────────────────────────────────────────

    def save(
        self,
        project_id: str,
        title: str,
        content: str,
        category: str = "technical",
        status: str = "seed",
        confidence: float = 0.0,
        anchors: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        cluster_id: Optional[str] = None,
    ) -> str:
        """Save a concept.  Returns the concept ID.

        If title matches an existing non-archived concept for the same
        project, the existing concept is updated instead of creating a dup.
        """
        conn = self._require_conn()

        # Validate
        title = title.strip()
        if not title:
            raise ValueError("Concept title cannot be empty")
        content = content.strip()
        if not content:
            raise ValueError("Concept content cannot be empty")
        if len(content) > MAX_CONCEPT_CHARS:
            content = content[:MAX_CONCEPT_CHARS]
        if category not in VALID_CATEGORIES:
            category = "technical"
        if status not in VALID_STATUSES:
            status = "seed"

        anchors_json = json.dumps(anchors or [])
        tags_json = json.dumps(tags or [])

        with self._lock:
            # Dedup: check for existing concept with same title
            existing = conn.execute(
                """SELECT id FROM concepts
                   WHERE project_id = ? AND title = ? AND status != 'archived'
                   LIMIT 1""",
                (project_id, title),
            ).fetchone()
            if existing:
                # Update existing concept
                now = time.time()
                conn.execute(
                    """UPDATE concepts
                       SET content = ?, category = ?, confidence = ?,
                           anchors = ?, tags = ?, cluster_id = ?,
                           updated_at = ?, stale = 0, stale_reason = NULL
                       WHERE id = ?""",
                    (content, category, confidence, anchors_json,
                     tags_json, cluster_id, now, existing["id"]),
                )
                # Update FTS
                try:
                    conn.execute(
                        "DELETE FROM concepts_fts WHERE id = ?",
                        (existing["id"],),
                    )
                    conn.execute(
                        "INSERT INTO concepts_fts (title, content, id) VALUES (?, ?, ?)",
                        (title, content, existing["id"]),
                    )
                except sqlite3.OperationalError:
                    pass
                conn.commit()
                return existing["id"]

            # Enforce per-project limit — evict oldest archived first
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM concepts WHERE project_id = ?",
                (project_id,),
            ).fetchone()["cnt"]
            if count >= MAX_CONCEPTS_PER_PROJECT:
                self._evict_oldest(conn, project_id, count - MAX_CONCEPTS_PER_PROJECT + 1)

            concept_id = uuid.uuid4().hex[:12]
            now = time.time()
            conn.execute(
                """INSERT INTO concepts
                   (id, project_id, title, content, category, status,
                    confidence, anchors, tags, cluster_id, created_at, stale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (concept_id, project_id, title, content, category, status,
                 confidence, anchors_json, tags_json, cluster_id, now),
            )
            # FTS insert
            try:
                conn.execute(
                    "INSERT INTO concepts_fts (title, content, id) VALUES (?, ?, ?)",
                    (title, content, concept_id),
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()

        logger.debug("Saved concept %s for %s: %s", concept_id, project_id, title)
        return concept_id

    def update(
        self,
        concept_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        anchors: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Update a concept.  Returns True if it existed."""
        conn = self._require_conn()
        updates: List[str] = []
        params: List[Any] = []

        if title is not None:
            title = title.strip()
            if not title:
                raise ValueError("Concept title cannot be empty")
            updates.append("title = ?")
            params.append(title)
        if content is not None:
            content = content.strip()
            if len(content) > MAX_CONCEPT_CHARS:
                content = content[:MAX_CONCEPT_CHARS]
            updates.append("content = ?")
            params.append(content)
        if category is not None and category in VALID_CATEGORIES:
            updates.append("category = ?")
            params.append(category)
        if status is not None and status in VALID_STATUSES:
            updates.append("status = ?")
            params.append(status)
        if anchors is not None:
            updates.append("anchors = ?")
            params.append(json.dumps(anchors))
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(time.time())
        # Clear staleness on edit
        updates.append("stale = 0")
        updates.append("stale_reason = NULL")

        params.append(concept_id)

        with self._lock:
            cur = conn.execute(
                f"UPDATE concepts SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            if cur.rowcount > 0 and (title is not None or content is not None):
                # Refresh FTS
                row = conn.execute(
                    "SELECT title, content FROM concepts WHERE id = ?",
                    (concept_id,),
                ).fetchone()
                if row:
                    try:
                        conn.execute("DELETE FROM concepts_fts WHERE id = ?", (concept_id,))
                        conn.execute(
                            "INSERT INTO concepts_fts (title, content, id) VALUES (?, ?, ?)",
                            (row["title"], row["content"], concept_id),
                        )
                    except sqlite3.OperationalError:
                        pass
            conn.commit()
            return cur.rowcount > 0

    def delete(self, concept_id: str) -> bool:
        """Delete a single concept.  Returns True if it existed."""
        conn = self._require_conn()
        with self._lock:
            cur = conn.execute("DELETE FROM concepts WHERE id = ?", (concept_id,))
            try:
                conn.execute("DELETE FROM concepts_fts WHERE id = ?", (concept_id,))
            except sqlite3.OperationalError:
                pass
            conn.commit()
            return cur.rowcount > 0

    def clear_project(self, project_id: str) -> int:
        """Delete all concepts and questions for a project."""
        conn = self._require_conn()
        with self._lock:
            ids = [
                r["id"] for r in
                conn.execute(
                    "SELECT id FROM concepts WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            ]
            cur = conn.execute(
                "DELETE FROM concepts WHERE project_id = ?",
                (project_id,),
            )
            for cid in ids:
                try:
                    conn.execute("DELETE FROM concepts_fts WHERE id = ?", (cid,))
                except sqlite3.OperationalError:
                    pass
            conn.execute(
                "DELETE FROM concept_questions WHERE project_id = ?",
                (project_id,),
            )
            conn.commit()
            return cur.rowcount

    def mark_stale_batch(
        self,
        project_id: str,
        file_paths: List[str],
        reason: str = "file modified",
    ) -> int:
        """Mark concepts stale when their anchored files change.

        Scans the anchors JSON array for each concept and marks it stale
        if any anchor matches a changed file path.
        """
        if not file_paths:
            return 0
        conn = self._require_conn()
        now = time.time()
        total = 0
        with self._lock:
            # Get all non-stale concepts for this project that have anchors
            rows = conn.execute(
                """SELECT id, anchors FROM concepts
                   WHERE project_id = ? AND stale = 0 AND anchors != '[]'""",
                (project_id,),
            ).fetchall()
            for row in rows:
                try:
                    concept_anchors = json.loads(row["anchors"])
                except (json.JSONDecodeError, TypeError):
                    continue
                # Check if any anchor matches a changed file
                if any(fp in concept_anchors for fp in file_paths):
                    conn.execute(
                        """UPDATE concepts
                           SET stale = 1, stale_reason = ?, updated_at = ?
                           WHERE id = ?""",
                        (reason, now, row["id"]),
                    )
                    total += 1
            conn.commit()
        if total > 0:
            logger.info(
                "Marked %d concept(s) stale for %s (%d files changed)",
                total, project_id, len(file_paths),
            )
        return total

    # ── Read Operations ──────────────────────────────────────────

    def get(self, concept_id: str) -> Optional[Concept]:
        """Get a single concept by ID."""
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                "SELECT * FROM concepts WHERE id = ?", (concept_id,),
            ).fetchone()
        return Concept.from_row(row) if row else None

    def list_concepts(
        self,
        project_id: str,
        status: Optional[str] = None,
        category: Optional[str] = None,
        include_stale: bool = True,
        include_archived: bool = False,
    ) -> List[Concept]:
        """List concepts for a project with optional filters."""
        conn = self._require_conn()
        sql = "SELECT * FROM concepts WHERE project_id = ?"
        params: list = [project_id]

        if status:
            sql += " AND status = ?"
            params.append(status)
        elif not include_archived:
            sql += " AND status != 'archived'"

        if category:
            sql += " AND category = ?"
            params.append(category)

        if not include_stale:
            sql += " AND stale = 0"

        sql += " ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'seed' THEN 1 ELSE 2 END, created_at DESC"

        with self._lock:
            rows = conn.execute(sql, params).fetchall()
        return [Concept.from_row(r) for r in rows]

    @staticmethod
    def _fts_query(query: str) -> str:
        """Convert a natural language query to FTS5 OR query."""
        cleaned = query.replace('"', " ").replace("*", " ").replace("-", " ")
        terms = [t for t in cleaned.split() if len(t) >= 2]
        if not terms:
            return query
        return " OR ".join(f'"{t}"' for t in terms)

    def search(
        self,
        project_id: str,
        query: str,
        limit: int = 10,
        include_archived: bool = False,
    ) -> List[Concept]:
        """Search concepts by title and content.  Uses FTS5 if available."""
        conn = self._require_conn()
        results: List[Concept] = []

        with self._lock:
            try:
                fts_query = self._fts_query(query)
                fts_sql = """
                    SELECT c.* FROM concepts c
                    JOIN concepts_fts f ON c.id = f.id
                    WHERE f.concepts_fts MATCH ? AND c.project_id = ?
                """
                if not include_archived:
                    fts_sql += " AND c.status != 'archived'"
                fts_sql += " ORDER BY rank LIMIT ?"
                rows = conn.execute(fts_sql, (fts_query, project_id, limit)).fetchall()
                results = [Concept.from_row(r) for r in rows]
            except sqlite3.OperationalError:
                # FTS not available — fall back to LIKE
                like_sql = """
                    SELECT * FROM concepts
                    WHERE project_id = ? AND (title LIKE ? OR content LIKE ?)
                """
                if not include_archived:
                    like_sql += " AND status != 'archived'"
                like_sql += " ORDER BY created_at DESC LIMIT ?"
                rows = conn.execute(
                    like_sql, (project_id, f"%{query}%", f"%{query}%", limit),
                ).fetchall()
                results = [Concept.from_row(r) for r in rows]

        return results

    def get_for_anchors_directory(
        self,
        project_id: str,
        directory: str,
        include_stale: bool = True,
        include_archived: bool = False,
        limit: int = 20,
    ) -> List[Concept]:
        """Get concepts anchored to files under a directory prefix.

        Scans the JSON anchors array for each concept and returns those
        with at least one anchor matching the directory prefix. This is
        the L2 (on-demand scoped) retrieval layer for concepts.
        """
        conn = self._require_conn()
        prefix = directory.rstrip("/") + "/"

        # SQLite JSON: use LIKE on the anchors text column to find
        # concepts with at least one anchor under the directory.
        sql = """SELECT * FROM concepts
                 WHERE project_id = ? AND anchors LIKE ?"""
        params: list = [project_id, f"%{prefix}%"]

        if not include_stale:
            sql += " AND stale = 0"
        if not include_archived:
            sql += " AND status != 'archived'"

        sql += """ ORDER BY
            CASE status WHEN 'active' THEN 0 WHEN 'seed' THEN 1 ELSE 2 END,
            created_at DESC
            LIMIT ?"""
        params.append(limit)

        with self._lock:
            rows = conn.execute(sql, params).fetchall()

        # Post-filter: verify at least one anchor actually starts with prefix
        # (the LIKE on JSON text can false-match on content or other anchors)
        results = []
        for row in rows:
            concept = Concept.from_row(row)
            if any(a.startswith(prefix) or a.rstrip("/") + "/" == prefix
                   for a in concept.anchors):
                results.append(concept)

        return results[:limit]

    def get_stats(self, project_id: str) -> Dict[str, Any]:
        """Get concept statistics for the project."""
        conn = self._require_conn()
        with self._lock:
            total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM concepts WHERE project_id = ?",
                (project_id,),
            ).fetchone()["cnt"]
            by_status = conn.execute(
                """SELECT status, COUNT(*) AS cnt FROM concepts
                   WHERE project_id = ? GROUP BY status""",
                (project_id,),
            ).fetchall()
            by_category = conn.execute(
                """SELECT category, COUNT(*) AS cnt FROM concepts
                   WHERE project_id = ? AND status != 'archived'
                   GROUP BY category""",
                (project_id,),
            ).fetchall()
            stale = conn.execute(
                "SELECT COUNT(*) AS cnt FROM concepts WHERE project_id = ? AND stale = 1",
                (project_id,),
            ).fetchone()["cnt"]
            pending_questions = conn.execute(
                "SELECT COUNT(*) AS cnt FROM concept_questions WHERE project_id = ? AND answered = 0",
                (project_id,),
            ).fetchone()["cnt"]

        status_dict = {r["status"]: r["cnt"] for r in by_status}
        return {
            "total": total,
            "active": status_dict.get("active", 0),
            "seeds": status_dict.get("seed", 0),
            "archived": status_dict.get("archived", 0),
            "stale": stale,
            "by_category": {r["category"]: r["cnt"] for r in by_category},
            "pending_questions": pending_questions,
        }

    # ── Question Operations ──────────────────────────────────────

    def save_question(
        self,
        project_id: str,
        question: str,
        context: str = "",
        suggested_category: str = "technical",
        target_module: Optional[str] = None,
    ) -> str:
        """Save a clarifying question.  Returns the question ID."""
        conn = self._require_conn()
        q_id = uuid.uuid4().hex[:12]
        now = time.time()

        with self._lock:
            conn.execute(
                """INSERT INTO concept_questions
                   (id, project_id, question, context, suggested_category,
                    target_module, answered, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                (q_id, project_id, question, context, suggested_category,
                 target_module, now),
            )
            conn.commit()
        return q_id

    def list_questions(
        self,
        project_id: str,
        unanswered_only: bool = True,
    ) -> List[ConceptQuestion]:
        """List clarifying questions."""
        conn = self._require_conn()
        sql = "SELECT * FROM concept_questions WHERE project_id = ?"
        params: list = [project_id]
        if unanswered_only:
            sql += " AND answered = 0"
        sql += " ORDER BY created_at DESC"

        with self._lock:
            rows = conn.execute(sql, params).fetchall()
        return [ConceptQuestion.from_row(r) for r in rows]

    def answer_question(
        self,
        question_id: str,
        answer: str,
        created_concept_id: Optional[str] = None,
    ) -> bool:
        """Mark a question as answered.  Returns True if it existed."""
        conn = self._require_conn()
        with self._lock:
            cur = conn.execute(
                """UPDATE concept_questions
                   SET answered = 1, answer = ?, created_concept_id = ?
                   WHERE id = ?""",
                (answer, created_concept_id, question_id),
            )
            conn.commit()
            return cur.rowcount > 0

    # ── Internal ─────────────────────────────────────────────────

    def _evict_oldest(self, conn: sqlite3.Connection, project_id: str, count: int) -> None:
        """Evict oldest concepts, preferring archived then stale."""
        ids_to_delete = conn.execute(
            """SELECT id FROM concepts WHERE project_id = ?
               ORDER BY
                 CASE status WHEN 'archived' THEN 0 WHEN 'seed' THEN 2 ELSE 1 END,
                 stale DESC,
                 created_at ASC
               LIMIT ?""",
            (project_id, count),
        ).fetchall()
        for row in ids_to_delete:
            conn.execute("DELETE FROM concepts WHERE id = ?", (row["id"],))
            try:
                conn.execute("DELETE FROM concepts_fts WHERE id = ?", (row["id"],))
            except sqlite3.OperationalError:
                pass
        logger.debug("Evicted %d concept(s) for %s", len(ids_to_delete), project_id)


# ── Singleton ───────────────────────────────────────────────────

concept_store = ConceptStore()
