"""GraphSnapshotStore — persist graph state and compute structural deltas.

Captures hub files and module structure at index rebuild time.
Diffs two snapshots to produce a StructuralDelta showing what changed.

Note: Cycles and cross-cutting concerns are NOT captured — no structured
data source exists for these yet (see Issues 1+2 in next_steps.md).
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


@dataclass
class GraphSnapshot:
    """Lightweight graph state for delta computation."""

    id: str
    project_id: str
    hubs: List[Dict[str, Any]]
    modules: List[Dict[str, Any]]
    created_at: float


@dataclass
class StructuralDelta:
    """Result of diffing two graph snapshots."""

    since: float
    until: float
    hub_changes: List[Dict[str, Any]] = field(default_factory=list)
    module_changes: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.hub_changes and not self.module_changes


class GraphSnapshotStore:
    """SQLite-backed graph snapshot store."""

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
            CREATE TABLE IF NOT EXISTS graph_snapshots (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshot_project_time
                ON graph_snapshots(project_id, created_at DESC);
        """)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def capture(
        self,
        project_id: str,
        hubs: List[Dict[str, Any]],
        modules: List[Dict[str, Any]],
    ) -> str:
        """Capture current graph state. Returns snapshot ID."""
        snap_id = uuid.uuid4().hex[:12]
        now = time.time()
        payload = json.dumps({"hubs": hubs, "modules": modules})

        with self._lock:
            self._conn.execute(
                """INSERT INTO graph_snapshots
                   (id, project_id, snapshot_json, created_at)
                   VALUES (?, ?, ?, ?)""",
                (snap_id, project_id, payload, now),
            )
            self._conn.commit()

        return snap_id

    def get_latest(self, project_id: str) -> Optional[GraphSnapshot]:
        """Return the most recent snapshot, or None."""
        with self._lock:
            row = self._conn.execute(
                """SELECT * FROM graph_snapshots
                   WHERE project_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id,),
            ).fetchone()

        if not row:
            return None
        return self._row_to_snapshot(row)

    def compute_delta(
        self, project_id: str, since: float,
    ) -> StructuralDelta:
        """Diff the snapshot closest to `since` against the latest."""
        with self._lock:
            old_row = self._conn.execute(
                """SELECT * FROM graph_snapshots
                   WHERE project_id = ? AND created_at <= ?
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id, since),
            ).fetchone()

            new_row = self._conn.execute(
                """SELECT * FROM graph_snapshots
                   WHERE project_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id,),
            ).fetchone()

        if not old_row or not new_row:
            return StructuralDelta(since=since, until=time.time())

        old_snap = self._row_to_snapshot(old_row)
        new_snap = self._row_to_snapshot(new_row)

        if old_snap.id == new_snap.id:
            return StructuralDelta(
                since=since, until=new_snap.created_at,
            )

        return StructuralDelta(
            since=old_snap.created_at,
            until=new_snap.created_at,
            hub_changes=self._diff_hubs(old_snap.hubs, new_snap.hubs),
            module_changes=self._diff_modules(
                old_snap.modules, new_snap.modules,
            ),
        )

    def prune(self, project_id: str, keep: int = 10) -> int:
        """Keep only the N most recent snapshots. Returns count deleted."""
        with self._lock:
            row = self._conn.execute(
                """SELECT created_at FROM graph_snapshots
                   WHERE project_id = ?
                   ORDER BY created_at DESC
                   LIMIT 1 OFFSET ?""",
                (project_id, keep),
            ).fetchone()

            if not row:
                return 0

            cutoff = row["created_at"]
            cur = self._conn.execute(
                """DELETE FROM graph_snapshots
                   WHERE project_id = ? AND created_at <= ?""",
                (project_id, cutoff),
            )
            self._conn.commit()
            return cur.rowcount

    # ── Diff helpers ────────────────────────────────────────────

    @staticmethod
    def _diff_hubs(
        old_hubs: List[Dict[str, Any]],
        new_hubs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        old_by_path = {h["path"]: h for h in old_hubs}
        new_by_path = {h["path"]: h for h in new_hubs}
        changes: List[Dict[str, Any]] = []

        for path in new_by_path:
            if path not in old_by_path:
                h = new_by_path[path]
                changes.append({
                    "path": path, "change": "new",
                    "dependents_count": h.get("dependents_count", 0),
                    "rank": h.get("rank", 0),
                })

        for path in old_by_path:
            if path not in new_by_path:
                changes.append({"path": path, "change": "removed"})

        for path in new_by_path:
            if path in old_by_path:
                old_rank = old_by_path[path].get("rank", 0)
                new_rank = new_by_path[path].get("rank", 0)
                if abs(old_rank - new_rank) > 1:
                    changes.append({
                        "path": path, "change": "rank_changed",
                        "old_rank": old_rank, "new_rank": new_rank,
                    })

        return changes

    @staticmethod
    def _diff_modules(
        old_modules: List[Dict[str, Any]],
        new_modules: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        old_by_name = {m["name"]: m for m in old_modules}
        new_by_name = {m["name"]: m for m in new_modules}
        changes: List[Dict[str, Any]] = []

        for name in new_by_name:
            if name not in old_by_name:
                m = new_by_name[name]
                changes.append({
                    "name": name, "change": "new",
                    "file_count": m.get("file_count", 0),
                })

        for name in old_by_name:
            if name not in new_by_name:
                changes.append({"name": name, "change": "removed"})

        for name in new_by_name:
            if name in old_by_name:
                old_count = old_by_name[name].get("file_count", 0)
                new_count = new_by_name[name].get("file_count", 0)
                if old_count > 0:
                    pct = abs(new_count - old_count) / old_count
                    if pct > 0.2:
                        changes.append({
                            "name": name, "change": "size_changed",
                            "old_file_count": old_count,
                            "new_file_count": new_count,
                        })

        return changes

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> GraphSnapshot:
        data = json.loads(row["snapshot_json"])
        return GraphSnapshot(
            id=row["id"],
            project_id=row["project_id"],
            hubs=data.get("hubs", []),
            modules=data.get("modules", []),
            created_at=row["created_at"],
        )
