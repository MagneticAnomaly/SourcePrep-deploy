"""ConflictStore + ConflictDetector — cross-agent disagreement detection.

Two detection strategies:
1. Observation-level: Same file_path, different created_by agents.
2. Push-level: Same root_file in ConsolidatedGroups with contradictory
   ActionItem categories. Push-level is called from PushEngine.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from codrag.services.observation_store import Observation

logger = logging.getLogger(__name__)


@dataclass
class AgentConflict:
    """A disagreement between two agents about the same file."""

    id: str
    project_id: str
    file_path: str
    agent_a: str
    agent_a_assessment: str
    agent_b: str
    agent_b_assessment: str
    conflict_type: str = "contradictory"
    resolution: str = "deferred"
    detected_at: float = 0.0
    resolved_at: Optional[float] = None


class ConflictStore:
    """SQLite-backed conflict store."""

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
            CREATE TABLE IF NOT EXISTS agent_conflicts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                agent_a TEXT NOT NULL,
                agent_a_assessment TEXT NOT NULL,
                agent_b TEXT NOT NULL,
                agent_b_assessment TEXT NOT NULL,
                conflict_type TEXT NOT NULL DEFAULT 'contradictory',
                resolution TEXT DEFAULT 'deferred',
                detected_at REAL NOT NULL,
                resolved_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_conflicts_project
                ON agent_conflicts(project_id, resolution);
        """)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def save(self, conflict: AgentConflict) -> str:
        """Persist a conflict. Returns the conflict ID."""
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO agent_conflicts
                   (id, project_id, file_path,
                    agent_a, agent_a_assessment,
                    agent_b, agent_b_assessment,
                    conflict_type, resolution,
                    detected_at, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (conflict.id, conflict.project_id, conflict.file_path,
                 conflict.agent_a, conflict.agent_a_assessment,
                 conflict.agent_b, conflict.agent_b_assessment,
                 conflict.conflict_type, conflict.resolution,
                 conflict.detected_at, conflict.resolved_at),
            )
            self._conn.commit()
        return conflict.id

    def get_active(self, project_id: str) -> List[AgentConflict]:
        """Return unresolved conflicts."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM agent_conflicts
                   WHERE project_id = ? AND resolution = 'deferred'
                   ORDER BY detected_at DESC""",
                (project_id,),
            ).fetchall()
        return [self._row_to_conflict(r) for r in rows]

    def resolve(self, conflict_id: str, resolution: str) -> bool:
        """Resolve a conflict. Returns True if it existed."""
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                """UPDATE agent_conflicts
                   SET resolution = ?, resolved_at = ?
                   WHERE id = ?""",
                (resolution, now, conflict_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    @staticmethod
    def _row_to_conflict(row: sqlite3.Row) -> AgentConflict:
        return AgentConflict(
            id=row["id"],
            project_id=row["project_id"],
            file_path=row["file_path"],
            agent_a=row["agent_a"],
            agent_a_assessment=row["agent_a_assessment"],
            agent_b=row["agent_b"],
            agent_b_assessment=row["agent_b_assessment"],
            conflict_type=row["conflict_type"],
            resolution=row["resolution"],
            detected_at=row["detected_at"],
            resolved_at=row["resolved_at"],
        )


class ConflictDetector:
    """Detects contradictions between agent observations.

    Observation-level strategy: Two different agents with observations
    on the same file_path is a potential conflict. The content of both
    observations is surfaced for human review.
    """

    def detect_from_observations(
        self,
        project_id: str,
        observations: List[Observation],
    ) -> List[AgentConflict]:
        """Detect conflicts from attributed observations.

        Groups by file_path. If two or more distinct agents have
        observations on the same file, that's a potential conflict.
        """
        by_file: Dict[str, Dict[str, List[Any]]] = defaultdict(
            lambda: defaultdict(list),
        )
        for obs in observations:
            if obs.file_path and obs.created_by:
                by_file[obs.file_path][obs.created_by].append(obs)

        conflicts: List[AgentConflict] = []
        for file_path, agents in by_file.items():
            agent_names = list(agents.keys())
            if len(agent_names) < 2:
                continue

            for i in range(len(agent_names)):
                for j in range(i + 1, len(agent_names)):
                    a_name = agent_names[i]
                    b_name = agent_names[j]
                    a_obs = agents[a_name][-1]
                    b_obs = agents[b_name][-1]

                    conflicts.append(AgentConflict(
                        id=uuid.uuid4().hex[:12],
                        project_id=project_id,
                        file_path=file_path,
                        agent_a=a_name,
                        agent_a_assessment=a_obs.content[:200],
                        agent_b=b_name,
                        agent_b_assessment=b_obs.content[:200],
                        conflict_type="contradictory",
                        detected_at=time.time(),
                    ))

        return conflicts
