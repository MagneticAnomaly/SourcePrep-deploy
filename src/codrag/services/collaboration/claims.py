"""ClaimStore — soft file claims with auto-expiry.

Agents declare active interest in files/directories. Other agents
check claims before modifying the same area. Claims auto-expire
after a configurable TTL (default 24 hours).
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SoftClaim:
    """An agent's declaration of active interest in a file or directory."""

    id: str
    project_id: str
    agent_role: str
    path: str
    reason: str
    claimed_at: float
    expires_at: float


class ClaimStore:
    """SQLite-backed soft claim store with lazy expiry cleanup."""

    DEFAULT_TTL = 86400.0  # 24 hours

    def __init__(self, db_path: Path) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False,
            isolation_level="DEFERRED",
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS soft_claims (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                path TEXT NOT NULL,
                reason TEXT,
                claimed_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_claims_project_path
                ON soft_claims(project_id, path);
        """)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def claim(
        self,
        project_id: str,
        agent_role: str,
        path: str,
        reason: str,
        ttl: float = DEFAULT_TTL,
    ) -> str:
        """Create a soft claim on a file or directory. Returns claim ID."""
        claim_id = uuid.uuid4().hex[:12]
        now = time.time()
        expires_at = now + ttl

        with self._lock:
            self._cleanup_expired_locked(project_id)
            self._conn.execute(
                """INSERT INTO soft_claims
                   (id, project_id, agent_role, path, reason,
                    claimed_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (claim_id, project_id, agent_role, path, reason,
                 now, expires_at),
            )
            self._conn.commit()

        return claim_id

    def release(self, claim_id: str) -> bool:
        """Release a claim. Returns True if it existed."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM soft_claims WHERE id = ?", (claim_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def is_claimed(
        self,
        project_id: str,
        path: str,
        exclude_agent: Optional[str] = None,
    ) -> bool:
        """Check if a path is claimed (exact match or directory prefix)."""
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                """SELECT agent_role, path FROM soft_claims
                   WHERE project_id = ? AND expires_at > ?""",
                (project_id, now),
            ).fetchall()

        for row in rows:
            if exclude_agent and row["agent_role"] == exclude_agent:
                continue
            claim_path = row["path"]
            if claim_path == path:
                return True
            if claim_path.endswith("/") and path.startswith(claim_path):
                return True
        return False

    def get_claims_for_path(
        self, project_id: str, path: str,
    ) -> List[SoftClaim]:
        """Get all active claims that cover a specific path."""
        now = time.time()
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM soft_claims
                   WHERE project_id = ? AND expires_at > ?""",
                (project_id, now),
            ).fetchall()

        results = []
        for row in rows:
            claim_path = row["path"]
            if (claim_path == path
                    or (claim_path.endswith("/")
                        and path.startswith(claim_path))):
                results.append(self._row_to_claim(row))
        return results

    def get_active(self, project_id: str) -> List[SoftClaim]:
        """Get all active (non-expired) claims for a project."""
        now = time.time()
        with self._lock:
            self._cleanup_expired_locked(project_id)
            rows = self._conn.execute(
                """SELECT * FROM soft_claims
                   WHERE project_id = ? AND expires_at > ?
                   ORDER BY claimed_at DESC""",
                (project_id, now),
            ).fetchall()

        return [self._row_to_claim(r) for r in rows]

    def cleanup_expired(self, project_id: str) -> int:
        """Remove expired claims. Returns count deleted."""
        with self._lock:
            return self._cleanup_expired_locked(project_id)

    def _cleanup_expired_locked(self, project_id: str) -> int:
        now = time.time()
        cur = self._conn.execute(
            "DELETE FROM soft_claims"
            " WHERE project_id = ? AND expires_at <= ?",
            (project_id, now),
        )
        self._conn.commit()
        return cur.rowcount

    @staticmethod
    def _row_to_claim(row: sqlite3.Row) -> SoftClaim:
        return SoftClaim(
            id=row["id"],
            project_id=row["project_id"],
            agent_role=row["agent_role"],
            path=row["path"],
            reason=row["reason"],
            claimed_at=row["claimed_at"],
            expires_at=row["expires_at"],
        )
