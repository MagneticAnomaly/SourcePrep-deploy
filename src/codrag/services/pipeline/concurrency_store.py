"""Persistence for Phase 82 discovered concurrency ceilings.

The AIMD scheduler learns each provider's real ceiling at runtime via
latency-aware discovery. Without persistence, every daemon restart
replays the jumpstart from seed=5 — wasteful when the user has already
been running for hours and the ceiling is known to be, say, 40.

Only the *ceiling* survives restart. Mode (jumpstart vs
congestion_avoidance), success streak, and last-backoff timestamp all
reset, because they're hot-loop state with no meaning across a restart
boundary.

Storage: single SQLite file at ``<data_dir>/concurrency_store.db``.
DELETE journal mode (WAL is unreliable on USB per project policy).
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS discovered_ceilings (
    node_id TEXT NOT NULL,
    model_family TEXT NOT NULL,
    ceiling INTEGER NOT NULL,
    updated_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    PRIMARY KEY (node_id, model_family)
)
"""


class ConcurrencyStore:
    """Persisted AIMD ceilings keyed by (node_id, model_family)."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode = DELETE")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def load(self, node_id: str, model_family: str) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ceiling FROM discovered_ceilings "
                "WHERE node_id = ? AND model_family = ?",
                (node_id, model_family),
            ).fetchone()
        return int(row[0]) if row else None

    def save(self, node_id: str, model_family: str, *, ceiling: int) -> None:
        if ceiling < 1:
            raise ValueError(f"ceiling must be >= 1, got {ceiling!r}")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO discovered_ceilings (node_id, model_family, ceiling) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(node_id, model_family) DO UPDATE SET "
                "ceiling = excluded.ceiling, "
                "updated_at = strftime('%s', 'now')",
                (node_id, model_family, int(ceiling)),
            )
            conn.commit()

    def clear(self, node_id: str, model_family: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM discovered_ceilings "
                "WHERE node_id = ? AND model_family = ?",
                (node_id, model_family),
            )
            conn.commit()


_store: ConcurrencyStore | None = None


def concurrency_store() -> ConcurrencyStore:
    """Return the daemon-wide ConcurrencyStore singleton.

    Stored at ``<data_dir>/concurrency_store.db``. See
    ``codrag.core.paths.data_dir`` for the resolution rules.
    """
    global _store
    if _store is None:
        from codrag.core.paths import data_dir
        _store = ConcurrencyStore(data_dir() / "concurrency_store.db")
    return _store
