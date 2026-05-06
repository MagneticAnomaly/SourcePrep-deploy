"""
Prep Concept Store — Phase 74 (Epistemic Concepts)
=====================================================

Persistent store for codebase concepts — high-level knowledge about
*why* the code is the way it is, business context, design decisions,
brand guidelines, and domain vocabulary.

Concepts are heavier than observations:
  - They have richer metadata (categories, anchors, status lifecycle)
  - They are LLM-seeded and user-curated (seeds → active → archived)
  - They bridge the gap between structural intelligence and understanding

**Design:**
  - Uses the shared ``prep_settings.db`` SQLite database.
  - Dedicated ``concepts`` table with FTS5 virtual table for search.
  - Concepts are linked to files via ``anchors`` (JSON array of paths).
  - When anchored files change, linked concepts are marked stale.
  - Separate ``concept_questions`` table for clarifying questions.

**Usage:**
  ``from prep.services.concept_store import concept_store``

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

# Phase 125b: per-kind caps replacing the legacy single global cap.
#
# History: the original ``MAX_CONCEPTS_PER_PROJECT = 200`` was set in the
# single-layer era, when concepts were noisy and manually curated. With
# Phase 125b's two-layer split, that cap was actively destroying the
# rationale foundation (a CoDRAG run with 2,430 rationale + 21 concepts
# was silently trimmed to 200 total — losing 92% of the rationale layer).
#
# Caps are sized as defensive ceilings, not budgets. The real lever for
# quality is the **prompt**: Phase 125b worker prompts ask for "0-3
# load-bearing rationale" per module (was "3-8"), with explicit
# permission to emit nothing when the WHY is obvious. Synthesizer
# self-caps at MAX_SYNTHESIZED_CONCEPTS=150.
#
# Expected steady-state: 200-800 rationale (depending on codebase
# size, ~1.2 rationale per module avg), 30-100 concepts. The caps
# below should rarely fire in practice.
MAX_CONCEPTS_PER_PROJECT_PER_KIND = {
    "concept": 500,            # ~5 synthesizer runs worth of accumulation
    "module_rationale": 2000,  # ~3000-file codebase ceiling
}
# Backward-compat alias used by callers that don't yet differentiate.
# Sum of per-kind caps; only invoked as a hard ceiling on truly runaway
# saves (e.g., test fixtures, future bugs).
MAX_CONCEPTS_PER_PROJECT = sum(MAX_CONCEPTS_PER_PROJECT_PER_KIND.values())

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
VALID_STATUSES = {
    "seed",
    "active",
    "archived",
    "superseded",
    "proposed",
    "deprecated",
    # Phase 125: multi-pass concept promotion lifecycle
    "shadow",            # near-duplicate of a cluster representative (Pass 2)
    "triage_pending",    # passed Pass 3 refine but below auto-active threshold (Pass 4)
}


# Phase 125b: two-layer concept architecture.
# Per-module rationale (the ~2,000-3,000 raw entries from the swarm
# seeder) is structurally different from cross-cutting concepts
# (~30-100 high-level architectural axioms / decisions / tradeoffs).
# Both live in this table, distinguished by ``kind``:
#   * ``module_rationale`` — fine-grained, per-module observations.
#     Searchable via ``prep_search`` but NOT shown via ``prep_concepts``.
#   * ``concept`` — true cross-cutting concepts. Surfaced via
#     ``prep_concepts`` and AGENTS.md ambient context.
# Default is ``module_rationale`` for backward compatibility — the
# legacy seeder produced module-level entries that should keep that
# label after migration.
VALID_KINDS = {"concept", "module_rationale"}
DEFAULT_KIND_FOR_LEGACY_ROWS = "module_rationale"


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
    valid_from: Optional[float] = None   # epoch when concept became valid
    valid_to: Optional[float] = None     # epoch when concept was invalidated (None = current)
    assertion: str = ""                  # testable statement for violation detection
    doc_links: List[Dict[str, str]] = field(default_factory=list)  # [{path, label, type}]
    superseded_by: Optional[str] = None  # concept ID that replaces this one
    # Phase 125b: layer discriminator. ``concept`` is the small,
    # cross-cutting layer (~30-100 per project, surfaced via prep_concepts).
    # ``module_rationale`` is the per-module observation layer
    # (~thousands per project, surfaced via prep_search).
    kind: str = "module_rationale"

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
        if self.valid_from is not None:
            d["valid_from"] = self.valid_from
        if self.valid_to is not None:
            d["valid_to"] = self.valid_to
        # Phase 84: always include new fields for API consistency
        d["assertion"] = self.assertion
        d["doc_links"] = self.doc_links
        d["superseded_by"] = self.superseded_by
        # Phase 125b: kind is always present
        d["kind"] = self.kind
        return d

    @staticmethod
    def from_row(row: sqlite3.Row) -> Concept:
        anchors_raw = row["anchors"]
        tags_raw = row["tags"]
        keys = row.keys()
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
            valid_from=row["valid_from"] if "valid_from" in keys else None,
            valid_to=row["valid_to"] if "valid_to" in keys else None,
            assertion=row["assertion"] if "assertion" in keys and row["assertion"] else "",
            doc_links=json.loads(row["doc_links"]) if "doc_links" in keys and row["doc_links"] else [],
            superseded_by=row["superseded_by"] if "superseded_by" in keys else None,
            # Phase 125b
            kind=row["kind"] if "kind" in keys and row["kind"] else "module_rationale",
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
                # Phase 96 / F-36: Bumped from 10s to 30s.  The previous
                # 10s timeout fired during sustained busy periods (e.g.
                # swarm finalize writes 26+ concepts in tight succession
                # while pipeline_journal, pipeline_metadata, observation_
                # store, audit_log are all writing to the same DB).
                # 30s gives the busy_timeout enough room to wait through
                # cross-store contention without raising SQLITE_BUSY.
                timeout=30,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=DELETE")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            # Phase 96 / F-36: Explicit busy_timeout pragma reinforces
            # the connection-level timeout above.  SQLite uses the
            # smaller of the two; setting both keeps behavior explicit.
            self._conn.execute("PRAGMA busy_timeout=30000")
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
                stale_reason   TEXT,
                -- Phase 125b: discriminator between fine-grained
                -- per-module rationale (legacy default) and true
                -- cross-cutting concepts (the small curated layer).
                kind           TEXT NOT NULL DEFAULT 'module_rationale'
            );

            CREATE INDEX IF NOT EXISTS idx_concept_project
                ON concepts (project_id);
            CREATE INDEX IF NOT EXISTS idx_concept_status
                ON concepts (project_id, status);
            CREATE INDEX IF NOT EXISTS idx_concept_category
                ON concepts (project_id, category);
            CREATE INDEX IF NOT EXISTS idx_concept_stale
                ON concepts (project_id, stale);
            -- NOTE: idx_concept_kind is intentionally NOT here.
            -- Legacy DBs don't have the `kind` column yet; creating
            -- an index on it inside this executescript would fail
            -- BEFORE the ALTER TABLE below adds the column. The index
            -- gets created after the ALTER (search this file for
            -- "idx_concept_kind").

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

        # Phase 80: Add temporal validity columns (safe to run repeatedly)
        for col in ("valid_from", "valid_to"):
            try:
                self._conn.execute(
                    f"ALTER TABLE concepts ADD COLUMN {col} REAL DEFAULT NULL"
                )
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Backfill: set valid_from = created_at for existing rows
        self._conn.execute(
            "UPDATE concepts SET valid_from = created_at WHERE valid_from IS NULL"
        )
        self._conn.commit()

        # Phase 84: Add assertion, doc_links, superseded_by columns
        for col, coltype in [
            ("assertion", "TEXT DEFAULT ''"),
            ("doc_links", "TEXT DEFAULT '[]'"),
            ("superseded_by", "TEXT DEFAULT NULL"),
        ]:
            try:
                self._conn.execute(
                    f"ALTER TABLE concepts ADD COLUMN {col} {coltype}"
                )
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Phase 125b: Add `kind` column. Idempotent — existing DBs
        # get the column added; new DBs got it via CREATE TABLE.
        # Backfill: legacy rows are per-module rationale by definition.
        try:
            self._conn.execute(
                "ALTER TABLE concepts ADD COLUMN kind TEXT NOT NULL "
                "DEFAULT 'module_rationale'"
            )
            self._conn.commit()
            logger.info(
                "concept_store: added kind column; legacy rows backfilled "
                "to 'module_rationale' via DEFAULT"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists
        # Index for the kind discriminator (idempotent)
        try:
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_concept_kind "
                "ON concepts (project_id, kind)"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass

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
        assertion: str = "",
        doc_links: Optional[List[Dict[str, str]]] = None,
        superseded_by: Optional[str] = None,
        kind: str = "module_rationale",  # Phase 125b: layer discriminator
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
        if kind not in VALID_KINDS:
            kind = "module_rationale"

        anchors_json = json.dumps(anchors or [])
        tags_json = json.dumps(tags or [])
        doc_links_json = json.dumps(doc_links or [])

        with self._lock:
            # Dedup: check for existing concept with same title.
            # Phase 125b: scope dedup to within the same kind. A
            # synthesizer-emitted "concept" and a per-module
            # "module_rationale" with identical titles are NOT
            # duplicates — they live in different layers.
            existing = conn.execute(
                """SELECT id FROM concepts
                   WHERE project_id = ? AND title = ? AND status != 'archived'
                     AND kind = ?
                   LIMIT 1""",
                (project_id, title, kind),
            ).fetchone()
            if existing:
                # Update existing concept
                now = time.time()
                conn.execute(
                    """UPDATE concepts
                       SET content = ?, category = ?, confidence = ?,
                           anchors = ?, tags = ?, cluster_id = ?,
                           updated_at = ?, stale = 0, stale_reason = NULL,
                           valid_from = ?, valid_to = NULL,
                           assertion = ?, doc_links = ?, superseded_by = ?
                       WHERE id = ?""",
                    (content, category, confidence, anchors_json,
                     tags_json, cluster_id, now, now,
                     assertion, doc_links_json, superseded_by, existing["id"]),
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

            # Phase 125b: per-kind cap — evict only within over-cap kind.
            self._evict_over_cap_for_kind(conn, project_id, kind, incoming=1)

            concept_id = uuid.uuid4().hex[:12]
            now = time.time()
            conn.execute(
                """INSERT INTO concepts
                   (id, project_id, title, content, category, status,
                    confidence, anchors, tags, cluster_id, created_at, stale, valid_from,
                    assertion, doc_links, superseded_by, kind)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)""",
                (concept_id, project_id, title, content, category, status,
                 confidence, anchors_json, tags_json, cluster_id, now, now,
                 assertion, doc_links_json, superseded_by, kind),
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

    def save_many(
        self,
        project_id: str,
        concepts: List[Dict[str, Any]],
    ) -> tuple[int, int]:
        """Phase 96 / F-36: Batch-save N concepts in a single transaction.

        Resolves the SQLITE_BUSY contention that hit the swarm path:
        previously each save() call opened its own transaction, and 26
        rapid-fire transactions during a finalize stage collided with
        cross-store writes (pipeline_journal, pipeline_metadata, etc.)
        Now all concepts in one swarm batch land in a single BEGIN..
        COMMIT pair, holding the writer lock once for the whole batch.

        Each concept dict should have at minimum ``title`` and
        ``content`` keys.  Optional keys: ``category``, ``status``,
        ``confidence``, ``anchors``, ``tags``, ``cluster_id``,
        ``assertion``, ``doc_links``.

        Returns (saved_count, skipped_count).  Concepts with empty
        title or content are skipped (logged at WARNING).  Concepts
        whose title matches an existing non-archived entry for the
        project are updated in place (same dedup behavior as save()).

        Wraps the entire batch in a retry loop for transient SQLITE_BUSY:
        if the batch fails because of database lock, it sleeps briefly
        and retries up to 3 times.
        """
        if not concepts:
            return (0, 0)

        conn = self._require_conn()

        # Pre-validate and normalize so the transaction body is fast.
        normalized: List[Dict[str, Any]] = []
        skipped = 0
        for raw in concepts:
            title = (raw.get("title") or "").strip()
            content = (raw.get("content") or "").strip()
            if not title or not content:
                skipped += 1
                logger.warning(
                    "save_many skipped a concept with empty title or content",
                )
                continue
            if len(content) > MAX_CONCEPT_CHARS:
                content = content[:MAX_CONCEPT_CHARS]
            category = raw.get("category", "technical")
            if category not in VALID_CATEGORIES:
                category = "technical"
            status = raw.get("status", "seed")
            if status not in VALID_STATUSES:
                status = "seed"
            # Phase 125b: kind discriminator (default 'module_rationale')
            kind = raw.get("kind", "module_rationale")
            if kind not in VALID_KINDS:
                kind = "module_rationale"
            normalized.append({
                "title": title,
                "content": content,
                "category": category,
                "status": status,
                "confidence": float(raw.get("confidence") or 0.0),
                "anchors_json": json.dumps(raw.get("anchors") or []),
                "tags_json": json.dumps(raw.get("tags") or []),
                "cluster_id": raw.get("cluster_id"),
                "assertion": raw.get("assertion") or "",
                "doc_links_json": json.dumps(raw.get("doc_links") or []),
                "kind": kind,
            })

        if not normalized:
            return (0, skipped)

        saved = 0
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self._lock:
                    saved = self._save_many_locked(conn, project_id, normalized)
                break  # success
            except sqlite3.OperationalError as e:
                if "locked" not in str(e).lower() or attempt == max_retries - 1:
                    logger.error(
                        "save_many failed after %d attempts: %s",
                        attempt + 1, e,
                    )
                    raise
                wait = 0.25 * (2 ** attempt)  # 0.25, 0.5, 1.0
                logger.warning(
                    "save_many hit database lock (attempt %d/%d) — "
                    "retrying in %.2fs",
                    attempt + 1, max_retries, wait,
                )
                time.sleep(wait)

        logger.info(
            "save_many: saved %d concept(s), skipped %d for project %s",
            saved, skipped, project_id,
        )
        return (saved, skipped)

    def _save_many_locked(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        normalized: List[Dict[str, Any]],
    ) -> int:
        """Inner save_many body — assumes self._lock is held.

        Performs the entire batch in one transaction.  Concepts whose
        title matches an existing non-archived entry are updated;
        the rest are inserted with new UUIDs.
        """
        saved = 0
        now = time.time()

        # Phase 125b: per-kind cap. Group incoming by kind, evict over-cap
        # kinds independently so a 2,400-rationale batch doesn't trigger
        # eviction of the 21-row concept layer.
        from collections import Counter
        incoming_by_kind = Counter(
            (e.get("kind") or "module_rationale") for e in normalized
        )
        for kind_, n_incoming in incoming_by_kind.items():
            self._evict_over_cap_for_kind(conn, project_id, kind_, incoming=n_incoming)

        for entry in normalized:
            title = entry["title"]
            content = entry["content"]

            # Dedup: title match against existing non-archived.
            # Phase 125b: scope to same kind so concept layer and
            # rationale layer don't accidentally collide.
            existing = conn.execute(
                """SELECT id FROM concepts
                   WHERE project_id = ? AND title = ? AND status != 'archived'
                     AND kind = ?
                   LIMIT 1""",
                (project_id, title, entry["kind"]),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE concepts
                       SET content = ?, category = ?, confidence = ?,
                           anchors = ?, tags = ?, cluster_id = ?,
                           updated_at = ?, stale = 0, stale_reason = NULL,
                           valid_from = ?, valid_to = NULL,
                           assertion = ?, doc_links = ?, superseded_by = NULL
                       WHERE id = ?""",
                    (
                        content, entry["category"], entry["confidence"],
                        entry["anchors_json"], entry["tags_json"],
                        entry["cluster_id"], now, now,
                        entry["assertion"], entry["doc_links_json"],
                        existing["id"],
                    ),
                )
                try:
                    conn.execute(
                        "DELETE FROM concepts_fts WHERE id = ?",
                        (existing["id"],),
                    )
                    conn.execute(
                        "INSERT INTO concepts_fts (title, content, id) "
                        "VALUES (?, ?, ?)",
                        (title, content, existing["id"]),
                    )
                except sqlite3.OperationalError:
                    pass
            else:
                concept_id = uuid.uuid4().hex[:12]
                conn.execute(
                    """INSERT INTO concepts
                       (id, project_id, title, content, category, status,
                        confidence, anchors, tags, cluster_id, created_at,
                        stale, valid_from, assertion, doc_links, superseded_by, kind)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, NULL, ?)""",
                    (
                        concept_id, project_id, title, content,
                        entry["category"], entry["status"], entry["confidence"],
                        entry["anchors_json"], entry["tags_json"],
                        entry["cluster_id"], now, now,
                        entry["assertion"], entry["doc_links_json"],
                        entry["kind"],
                    ),
                )
                try:
                    conn.execute(
                        "INSERT INTO concepts_fts (title, content, id) "
                        "VALUES (?, ?, ?)",
                        (title, content, concept_id),
                    )
                except sqlite3.OperationalError:
                    pass
            saved += 1

        # Single commit for the whole batch — this is the whole point
        # of save_many vs N independent save() calls.
        conn.commit()
        return saved

    def update(
        self,
        concept_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        anchors: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        assertion: Optional[str] = None,
        doc_links: Optional[List[Dict[str, str]]] = None,
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
        # Phase 84: new fields
        if assertion is not None:
            updates.append("assertion = ?")
            params.append(assertion)
        if doc_links is not None:
            updates.append("doc_links = ?")
            params.append(json.dumps(doc_links))

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
        """Delete a single concept.  Returns True if it existed.

        Phase 104: also cleans up any role pins referencing this concept
        so anonymous MCP callers don't receive stale pin IDs.
        """
        conn = self._require_conn()
        with self._lock:
            # Look up project_id before deleting so we can scope the pin
            # cleanup to the right project's settings namespace.
            row = conn.execute(
                "SELECT project_id FROM concepts WHERE id = ?", (concept_id,),
            ).fetchone()
            project_id = row["project_id"] if row else None

            cur = conn.execute("DELETE FROM concepts WHERE id = ?", (concept_id,))
            try:
                conn.execute("DELETE FROM concepts_fts WHERE id = ?", (concept_id,))
            except sqlite3.OperationalError:
                pass
            conn.commit()
            deleted = cur.rowcount > 0

        if deleted and project_id:
            # Lazy import avoids a circular dependency between the two
            # service stores at import time.
            try:
                from prep.services.role_overrides_store import (
                    role_overrides_store,
                )
                role_overrides_store.unpin_concept_from_all_roles(
                    project_id, concept_id,
                )
            except Exception as e:
                logger.debug(
                    "Pin cleanup failed for concept %s in %s: %s",
                    concept_id, project_id, e,
                )
        return deleted

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
                           SET stale = 1, stale_reason = ?, updated_at = ?, valid_to = ?
                           WHERE id = ?""",
                        (reason, now, now, row["id"]),
                    )
                    total += 1
            conn.commit()
        if total > 0:
            logger.info(
                "Marked %d concept(s) stale for %s (%d files changed)",
                total, project_id, len(file_paths),
            )
        return total

    def supersede(self, old_id: str, new_id: str) -> bool:
        """Mark a concept as superseded by another concept.

        Sets the old concept's status to 'superseded' and records the
        new concept's ID in superseded_by.  Returns True if the old
        concept existed and was updated.  Raises ValueError if old_id
        does not exist.
        """
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            # Verify old concept exists
            exists = conn.execute(
                "SELECT 1 FROM concepts WHERE id = ?", (old_id,)
            ).fetchone()
            if not exists:
                raise ValueError(f"Cannot supersede: concept {old_id} not found")
            cur = conn.execute(
                """UPDATE concepts
                   SET status = 'superseded', superseded_by = ?, updated_at = ?, valid_to = ?
                   WHERE id = ?""",
                (new_id, now, now, old_id),
            )
            conn.commit()
            return cur.rowcount > 0

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
        as_of: Optional[float] = None,
        kind: Optional[str] = "concept",
    ) -> List[Concept]:
        """List concepts for a project with optional filters.

        Phase 125b: ``kind`` defaults to ``"concept"`` so the canonical
        consumer surface (``prep_concepts``, ``prep()`` ambient block)
        sees only the small curated layer. Pass ``kind="module_rationale"``
        to browse the per-module rationale layer; pass ``kind=None`` to
        return both kinds.

        If ``as_of`` is provided (Unix epoch float), only concepts that were
        valid at that point in time are returned (valid_from <= as_of and
        valid_to is NULL or valid_to > as_of).  The ``include_stale`` filter
        is skipped when ``as_of`` is set because the temporal filter handles
        currency.
        """
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

        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)

        if as_of is not None:
            sql += " AND (valid_from IS NULL OR valid_from <= ?)"
            sql += " AND (valid_to IS NULL OR valid_to > ?)"
            params.extend([as_of, as_of])
        elif not include_stale:
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
        """Get concept statistics for the project.

        Phase 125b: ``total`` continues to count ALL rows (both
        ``kind='concept'`` and ``kind='module_rationale'``) for
        backward compat with the existence-guard at workers.py:1089.
        New top-level fields ``concepts_count`` and
        ``module_rationale_count`` distinguish the layers so
        consumers (dashboard, ambient context) can show the small
        curated layer without scanning every row.
        """
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
                     AND kind = 'concept'
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
            # Phase 125b: per-kind counts
            by_kind = conn.execute(
                """SELECT kind, COUNT(*) AS cnt FROM concepts
                   WHERE project_id = ? AND status != 'archived'
                   GROUP BY kind""",
                (project_id,),
            ).fetchall()
            # Phase 125b wrap-up: per-kind × per-status breakdown so the
            # MCP trailer can show e.g. "21 concepts (17 active, 4 seed)
            # + 180 rationale (180 seed)" without conflating layers.
            by_kind_status = conn.execute(
                """SELECT COALESCE(kind, 'module_rationale') AS kind,
                          status, COUNT(*) AS cnt
                   FROM concepts
                   WHERE project_id = ? AND status != 'archived'
                   GROUP BY kind, status""",
                (project_id,),
            ).fetchall()

        status_dict = {r["status"]: r["cnt"] for r in by_status}
        kind_dict = {r["kind"]: r["cnt"] for r in by_kind}
        kind_status: Dict[str, Dict[str, int]] = {}
        for r in by_kind_status:
            kind_status.setdefault(r["kind"], {})[r["status"]] = r["cnt"]
        return {
            "total": total,
            "active": status_dict.get("active", 0),
            "seeds": status_dict.get("seed", 0),
            "archived": status_dict.get("archived", 0),
            "stale": stale,
            "by_category": {r["category"]: r["cnt"] for r in by_category},
            "pending_questions": pending_questions,
            # Phase 125b
            "concepts_count": kind_dict.get("concept", 0),
            "module_rationale_count": kind_dict.get("module_rationale", 0),
            "concepts_active": kind_status.get("concept", {}).get("active", 0),
            "concepts_seeds": kind_status.get("concept", {}).get("seed", 0),
            "module_rationale_active": kind_status.get("module_rationale", {}).get("active", 0),
            "module_rationale_seeds": kind_status.get("module_rationale", {}).get("seed", 0),
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

    def _evict_over_cap_for_kind(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        kind: str,
        *,
        incoming: int,
    ) -> None:
        """Evict over-cap rows for a single kind.

        Phase 125b: eviction is per-kind so the rationale and concept
        layers don't compete for the same budget. ``incoming`` is the
        number of new rows about to be inserted for this kind.
        """
        cap = MAX_CONCEPTS_PER_PROJECT_PER_KIND.get(kind)
        if not cap:
            # Unknown kind: fall back to the legacy global cap as a
            # defensive ceiling (set absurdly high — see module top).
            cap = MAX_CONCEPTS_PER_PROJECT
        cur = conn.execute(
            "SELECT COUNT(*) AS cnt FROM concepts WHERE project_id = ? AND COALESCE(kind, 'module_rationale') = ?",
            (project_id, kind),
        ).fetchone()["cnt"]
        projected = cur + incoming
        if projected <= cap:
            return
        to_evict = projected - cap
        ids_to_delete = conn.execute(
            """SELECT id FROM concepts
               WHERE project_id = ?
                 AND COALESCE(kind, 'module_rationale') = ?
               ORDER BY
                 CASE WHEN status = 'archived' THEN 0
                      WHEN status = 'seed' THEN 1
                      ELSE 2 END,
                 stale DESC,
                 created_at ASC
               LIMIT ?""",
            (project_id, kind, to_evict),
        ).fetchall()
        for row in ids_to_delete:
            conn.execute("DELETE FROM concepts WHERE id = ?", (row["id"],))
            try:
                conn.execute("DELETE FROM concepts_fts WHERE id = ?", (row["id"],))
            except sqlite3.OperationalError:
                pass
        if ids_to_delete:
            logger.info(
                "Evicted %d %s row(s) over cap for %s",
                len(ids_to_delete), kind, project_id,
            )

    def _evict_oldest(self, conn: sqlite3.Connection, project_id: str, count: int) -> None:
        """Evict concepts to make room.

        Phase 125b kind-aware ordering. Eviction priority (lowest = first
        to go):
          0. archived items (any kind)
          1. module_rationale — voluminous foundation layer; individual
             entries are replaceable per-module, and there are typically
             100s-1000s of them, so they take the eviction hit first.
          2. concept-seed (T1) — low-confidence synthesizer candidates.
          3. concept-active (T2/T3) — the curated user-facing layer;
             evict last so prep_concepts and the ambient block remain
             populated under cap pressure.

        Within each priority bucket: stale first, oldest first.
        """
        ids_to_delete = conn.execute(
            """SELECT id FROM concepts WHERE project_id = ?
               ORDER BY
                 CASE
                   WHEN status = 'archived' THEN 0
                   WHEN COALESCE(kind, 'module_rationale') = 'module_rationale' THEN 1
                   WHEN COALESCE(kind, 'module_rationale') = 'concept' AND status = 'seed' THEN 2
                   ELSE 3
                 END,
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
