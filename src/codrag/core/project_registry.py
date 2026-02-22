from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProjectRegistryError(Exception):
    pass


class ProjectAlreadyExists(ProjectRegistryError):
    pass


class ProjectNotFound(ProjectRegistryError):
    pass


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    path: str
    mode: str
    config: Dict[str, Any]
    created_at: str
    updated_at: str


def codrag_data_dir() -> Path:
    return Path.home() / ".local" / "share" / "codrag"


def default_registry_db_path() -> Path:
    return codrag_data_dir() / "registry.db"


def project_index_dir(project: Project) -> Path:
    if project.mode == "custom":
        idx_path = project.config.get("index_path")
        if idx_path:
            return Path(idx_path).expanduser().resolve()
    
    project_root = Path(project.path).expanduser().resolve()
    if project.mode == "embedded":
        return project_root / ".codrag"
    
    return codrag_data_dir() / "projects" / project.id


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectRegistry:
    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path is not None else default_registry_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except Exception:
            pass
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    mode TEXT DEFAULT 'standalone',
                    config TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS builds (
                    id TEXT PRIMARY KEY,
                    project_id TEXT REFERENCES projects(id),
                    status TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    stats TEXT,
                    error TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        cfg_raw = row["config"]
        cfg: Dict[str, Any] = {}
        if isinstance(cfg_raw, str) and cfg_raw.strip():
            try:
                parsed = json.loads(cfg_raw)
                if isinstance(parsed, dict):
                    cfg = parsed
            except Exception:
                cfg = {}

        return Project(
            id=str(row["id"]),
            name=str(row["name"]),
            path=str(row["path"]),
            mode=str(row["mode"] or "standalone"),
            config=cfg,
            created_at=str(row["created_at"] or ""),
            updated_at=str(row["updated_at"] or ""),
        )

    def add_project(
        self,
        *,
        path: str | Path,
        name: Optional[str] = None,
        mode: str = "standalone",
        config: Optional[Dict[str, Any]] = None,
    ) -> Project:
        abs_path = str(Path(path).expanduser().resolve())
        project_id = str(uuid.uuid4())
        now = _now_iso()

        final_name = (name or Path(abs_path).name or project_id).strip() or project_id
        cfg_json = json.dumps(config or {})

        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO projects (id, name, path, mode, config, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (project_id, final_name, abs_path, mode, cfg_json, now, now),
                )
        except sqlite3.IntegrityError as e:
            raise ProjectAlreadyExists(abs_path) from e

        return Project(
            id=project_id,
            name=final_name,
            path=abs_path,
            mode=mode,
            config=config or {},
            created_at=now,
            updated_at=now,
        )

    def get_project(self, project_id: str) -> Optional[Project]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, path, mode, config, created_at, updated_at FROM projects WHERE id = ?",
                (str(project_id),),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_project(row)

    def list_projects(self) -> List[Project]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, path, mode, config, created_at, updated_at FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def update_project(
        self,
        project_id: str,
        *,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Project:
        existing = self.get_project(project_id)
        if existing is None:
            raise ProjectNotFound(project_id)

        new_name = existing.name if name is None else str(name)
        new_config = existing.config if config is None else dict(config)
        now = _now_iso()

        with self._connect() as conn:
            conn.execute(
                "UPDATE projects SET name = ?, config = ?, updated_at = ? WHERE id = ?",
                (new_name, json.dumps(new_config), now, str(project_id)),
            )

        updated = self.get_project(project_id)
        if updated is None:
            raise ProjectNotFound(project_id)
        return updated

    def remove_project(self, project_id: str, *, purge: bool = False) -> None:
        proj = self.get_project(project_id)
        if proj is None:
            raise ProjectNotFound(project_id)

        if purge:
            idx_dir = project_index_dir(proj)
            resolved = idx_dir.expanduser().resolve()
            if proj.mode == "embedded":
                proj_root = Path(proj.path).expanduser().resolve()
                if not resolved.is_relative_to(proj_root):
                    raise RuntimeError("Refusing to purge index outside project root")
            else:
                base = (codrag_data_dir() / "projects").expanduser().resolve()
                if not resolved.is_relative_to(base):
                    raise RuntimeError("Refusing to purge index outside CoDRAG data dir")

            if resolved.exists() and resolved.is_dir():
                shutil.rmtree(resolved)

        with self._connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (str(project_id),))

    def prune_orphans(self) -> List[Project]:
        """Remove projects whose paths no longer exist on disk.

        Returns the list of removed projects (for logging).
        """
        removed: List[Project] = []
        for proj in self.list_projects():
            if not Path(proj.path).exists():
                with self._connect() as conn:
                    conn.execute("DELETE FROM projects WHERE id = ?", (proj.id,))
                removed.append(proj)
        return removed
