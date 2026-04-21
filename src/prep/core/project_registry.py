from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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


def prep_data_dir() -> Path:
    """Daemon-wide data directory.

    Deprecated shim — new callers should import `data_dir` from
    `prep.core.paths` directly. Kept because six internal callers
    here plus external code paths (cli.py, watcher.py, etc.) still
    import this name.
    """
    from prep.core.paths import data_dir
    return data_dir()


def default_registry_db_path() -> Path:
    return prep_data_dir() / "registry.db"


def project_index_dir(project: Project) -> Path:
    if project.mode == "custom":
        idx_path = project.config.get("index_path")
        if idx_path:
            return Path(idx_path).expanduser().resolve()

    project_root = Path(project.path).expanduser().resolve()
    if project.mode == "embedded":
        return project_root / ".prep"

    return prep_data_dir() / "projects" / project.id


def project_for_index_dir(index_dir: Path | str) -> Optional[Project]:
    """Reverse-lookup a Project given its index directory.

    Reads `<index_dir>/project.json` for the project id and queries the
    default registry. Returns None if the pointer is missing, malformed,
    or the id is no longer in the registry.

    Loaders and the watcher use this to obtain `project.config` without
    having to thread a Project handle through every caller.
    """
    try:
        pointer_path = Path(index_dir).expanduser() / _POINTER_FILENAME
        if not pointer_path.exists():
            return None
        data = json.loads(pointer_path.read_text())
        project_id = data.get("id")
        if not project_id:
            return None
        registry = ProjectRegistry()
        return registry.get_project(str(project_id))
    except Exception:
        return None


def trace_ignore_patterns_for_index(index_dir: Path | str) -> List[str]:
    """Resolve `project.config.trace.ignore_patterns` (L3) by index_dir.

    Returns `[]` when the project can't be located, the config is
    missing, or the patterns list is empty. Used by the shared trace
    loaders and the watcher so L3 reaches callers that don't already
    have a Project handle (pipeline workers resolve L3 upstream).
    """
    proj = project_for_index_dir(index_dir)
    if proj is None:
        return []
    trace_cfg = (proj.config or {}).get("trace") or {}
    patterns = trace_cfg.get("ignore_patterns") or []
    if not isinstance(patterns, list):
        return []
    return [str(p) for p in patterns if p]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_active_project_signal(project_id: str) -> None:
    """Write the ID of the last user-activated project to a global signal file."""
    signal_file = prep_data_dir() / "active_project.json"
    signal_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = {
            "id": project_id,
            "switched_at": _now_iso()
        }
        signal_file.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def read_active_project_signal() -> Optional[Dict[str, Any]]:
    """Read the global active project signal file."""
    signal_file = prep_data_dir() / "active_project.json"
    if not signal_file.is_file():
        return None
    try:
        content = signal_file.read_text(encoding="utf-8").strip()
        if content:
            return json.loads(content)
    except Exception:
        pass
    return None


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

        proj = Project(
            id=project_id,
            name=final_name,
            path=abs_path,
            mode=mode,
            config=config or {},
            created_at=now,
            updated_at=now,
        )

        # Create .prep/project.json pointer in the project root.
        # This allows MCP servers to instantly identify the project
        # without querying the daemon.
        ensure_codrag_pointer(proj)

        return proj

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
        touch: bool = True,
    ) -> Project:
        existing = self.get_project(project_id)
        if existing is None:
            raise ProjectNotFound(project_id)

        new_name = existing.name if name is None else str(name)
        new_config = existing.config if config is None else dict(config)
        now = _now_iso() if touch else existing.updated_at

        with self._connect() as conn:
            conn.execute(
                "UPDATE projects SET name = ?, config = ?, updated_at = ? WHERE id = ?",
                (new_name, json.dumps(new_config), now, str(project_id)),
            )

        updated = self.get_project(project_id)
        if updated is None:
            raise ProjectNotFound(project_id)
        return updated

    def mutate_config(
        self,
        project_id: str,
        mutator: "Any",
        *,
        touch: bool = True,
    ) -> Project:
        """Atomically read-modify-write the project's config.

        The read, the mutator call, and the write all happen inside a single
        SQLite transaction, so concurrent RMW endpoints (e.g.
        PUT /included_paths and POST /trace/ignore) cannot clobber each
        other's fields by writing based on a stale snapshot.

        `mutator(current_config: dict) -> dict` returns the new config to
        persist. The function should not mutate its input in place; return
        a new dict (or a deep-copied + modified one) to keep callers honest.

        Uses `BEGIN IMMEDIATE` to acquire a reserved lock before the SELECT
        so that two concurrent mutators cannot both read v1 and each write
        over the other. With Python's default deferred isolation the first
        SELECT does not take a write lock, which would let the race persist.
        """
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT config FROM projects WHERE id = ?",
                (str(project_id),),
            ).fetchone()
            if row is None:
                raise ProjectNotFound(project_id)
            current_cfg: Dict[str, Any] = {}
            raw = row[0]
            if raw:
                try:
                    loaded = json.loads(raw)
                    if isinstance(loaded, dict):
                        current_cfg = loaded
                except (json.JSONDecodeError, TypeError):
                    current_cfg = {}
            new_cfg = mutator(current_cfg) or {}

            now = _now_iso() if touch else None
            if now is None:
                conn.execute(
                    "UPDATE projects SET config = ? WHERE id = ?",
                    (json.dumps(new_cfg), str(project_id)),
                )
            else:
                conn.execute(
                    "UPDATE projects SET config = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(new_cfg), now, str(project_id)),
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
                base = (prep_data_dir() / "projects").expanduser().resolve()
                if not resolved.is_relative_to(base):
                    raise RuntimeError("Refusing to purge index outside Prep data dir")

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

    def validate_and_heal_pointers(self) -> Dict[str, List[str]]:
        """Validate and heal .prep/project.json pointers for all projects.

        Checks every registered project:
        1. Does the project path still exist?
        2. Does .prep/project.json exist with the correct project ID?
        3. Does the pointer ID match our registry?

        Returns a report dict:
            healed: list of project names where pointer was created/fixed
            stale: list of project names where path no longer exists
            ok: list of project names that were already correct
        """
        import logging as _logging
        _logger = _logging.getLogger(__name__)

        report: Dict[str, List[str]] = {"healed": [], "stale": [], "ok": []}

        for proj in self.list_projects():
            label = proj.name or proj.id[:8]
            project_root = Path(proj.path).expanduser().resolve()

            if not project_root.is_dir():
                report["stale"].append(label)
                _logger.debug(
                    "validate_pointers: %s — path missing: %s", label, proj.path
                )
                continue

            # Check .prep/project.json
            pointer = read_codrag_pointer(project_root)
            if pointer and pointer.get("id") == proj.id:
                report["ok"].append(label)
            else:
                # Pointer missing or wrong ID — heal it
                ensure_codrag_pointer(proj)
                _logger.info(
                    "validate_pointers: healed pointer for %s (id=%s) at %s",
                    label, proj.id[:12], proj.path,
                )
                report["healed"].append(label)

        return report


# =============================================================================
# .prep/project.json pointer
# =============================================================================

_POINTER_FILENAME = "project.json"


def ensure_codrag_pointer(
    proj: Project,
    daemon_url: str = "http://127.0.0.1:8400",
) -> None:
    """Create or update .prep/project.json in the project root.

    This pointer file allows MCP servers and tooling to instantly identify
    which Prep project a workspace belongs to, without querying the daemon.

    The file is intentionally minimal — just enough for routing:
      {
        "id": "<uuid>",
        "mode": "standalone",
        "daemon": "http://127.0.0.1:8400"
      }

    Safe to call multiple times — overwrites with current values.
    """
    try:
        project_root = Path(proj.path).expanduser().resolve()
        if not project_root.is_dir():
            return  # Project root doesn't exist (yet); skip silently

        prep_dir = project_root / ".prep"
        prep_dir.mkdir(parents=False, exist_ok=True)

        pointer = {
            "id": proj.id,
            "mode": proj.mode,
            "daemon": daemon_url,
        }

        pointer_path = prep_dir / _POINTER_FILENAME
        pointer_path.write_text(json.dumps(pointer, indent=2) + "\n")
    except Exception:
        # Non-fatal — the pointer is a convenience, not a requirement.
        # Could fail on read-only filesystems or permission issues.
        pass


def read_codrag_pointer(directory: str | Path) -> Optional[Dict[str, str]]:
    """Read .prep/project.json from a directory, if it exists.

    Returns a dict with 'id', 'mode', and 'daemon' keys, or None
    if the pointer doesn't exist or is malformed.
    """
    try:
        from prep.core.paths import _migrate_embedded_dir
        _migrate_embedded_dir(Path(directory).expanduser().resolve())
    except Exception:
        logger.debug("embedded .codrag -> .prep migration failed; continuing", exc_info=True)
    try:
        pointer_path = Path(directory).expanduser().resolve() / ".prep" / _POINTER_FILENAME
        if not pointer_path.is_file():
            return None
        data = json.loads(pointer_path.read_text())
        if isinstance(data, dict) and data.get("id"):
            return {
                "id": str(data["id"]),
                "mode": str(data.get("mode", "standalone")),
                "daemon": str(data.get("daemon", "http://127.0.0.1:8400")),
            }
    except Exception:
        pass
    return None

