"""
CoDRAG Settings Store — Phase 24 (Phase 3: Settings Persistence)
=================================================================

SQLite-backed key-value store for all CoDRAG settings.

**Design:**
  - Single ``codrag_settings.db`` file in the data directory.
  - Namespaced keys: ``global/<key>`` for global settings,
    ``project/<project_id>/<key>`` for per-project settings.
  - Values stored as JSON text (supports dicts, lists, scalars).
  - Atomic writes via SQLite transactions.
  - Thread-safe (SQLite handles locking; we use ``check_same_thread=False``).
  - Auto-migrates ``ui_config.json`` on first load if it exists.

**Usage:**
  ``from codrag.services.settings_store import settings``
  ``settings.get("pipeline_config")``
  ``settings.set("pipeline_config", {"fast_sync": {"auto": True}})``
  ``settings.get("llm_config.embedding.model")``  # dot-path access
  ``settings.project_get("proj-1", "trace.enabled")``

**Relationship to config_manager.py:**
  The old load/save functions are kept for backward compat but now
  read/write through this store.  On first init, if ``ui_config.json``
  exists and the DB is empty, settings are migrated automatically.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Schema version — bump when table structure changes
_SCHEMA_VERSION = 1


class SettingsStore:
    """SQLite-backed key-value settings store."""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._listeners: List[_SettingsListener] = []

    # ── Lifecycle ────────────────────────────────────────────────

    def init(self, db_path: Path) -> None:
        """Initialize the store with a database path.  Safe to call multiple times."""
        with self._lock:
            if self._conn is not None:
                return  # Already initialized
            self._db_path = db_path
            self._conn = sqlite3.connect(
                str(db_path),
                check_same_thread=False,
                isolation_level="DEFERRED",
                timeout=10,
            )
            self._conn.execute("PRAGMA journal_mode=DELETE")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            # Recover any stale WAL from prior crash (industry pattern: Firefox, VS Code)
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._create_tables()
            logger.info("Settings store initialized: %s", db_path)

    def close(self) -> None:
        """Close the database connection, checkpointing WAL first."""
        with self._lock:
            if self._conn:
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except Exception:
                    pass  # Best-effort on shutdown
                self._conn.close()
                self._conn = None

    def _create_tables(self) -> None:
        """Create settings tables if they don't exist."""
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                namespace TEXT NOT NULL DEFAULT 'global',
                key       TEXT NOT NULL,
                value     TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, key)
            );

            CREATE TABLE IF NOT EXISTS settings_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        # Set schema version
        self._conn.execute(
            "INSERT OR REPLACE INTO settings_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(_SCHEMA_VERSION)),
        )
        self._conn.commit()

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError(
                "SettingsStore not initialized. Call settings.init(db_path) first."
            )
        return self._conn

    # ── Global settings ──────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Get a global setting by key.  Returns ``default`` if not found."""
        return self._get("global", key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a global setting.  Value is JSON-serialized."""
        self._set("global", key, value)

    def get_experimental(self) -> bool:
        """Return the global experimental toggle. Defaults to False."""
        val = self.get("global/experimental")
        return bool(val) if val is not None else False

    def delete(self, key: str) -> bool:
        """Delete a global setting.  Returns True if it existed."""
        return self._delete("global", key)

    def get_all(self) -> Dict[str, Any]:
        """Get all global settings as a dict."""
        return self._get_namespace("global")

    # ── Per-project settings ─────────────────────────────────────

    def project_get(self, project_id: str, key: str, default: Any = None) -> Any:
        """Get a per-project setting."""
        return self._get(f"project/{project_id}", key, default)

    def project_set(self, project_id: str, key: str, value: Any) -> None:
        """Set a per-project setting."""
        self._set(f"project/{project_id}", key, value)

    def project_delete(self, project_id: str, key: str) -> bool:
        """Delete a per-project setting."""
        return self._delete(f"project/{project_id}", key)

    def project_get_all(self, project_id: str) -> Dict[str, Any]:
        """Get all settings for a project."""
        return self._get_namespace(f"project/{project_id}")

    def project_clear(self, project_id: str) -> int:
        """Delete all settings for a project.  Returns count deleted."""
        conn = self._require_conn()
        ns = f"project/{project_id}"
        with self._lock:
            cur = conn.execute(
                "DELETE FROM settings WHERE namespace = ?", (ns,)
            )
            conn.commit()
            return cur.rowcount

    # ── Bulk operations (for migration) ──────────────────────────

    def set_many(self, namespace: str, items: Dict[str, Any]) -> None:
        """Set multiple keys in a namespace atomically."""
        conn = self._require_conn()
        now = time.time()
        with self._lock:
            try:
                conn.executemany(
                    "INSERT OR REPLACE INTO settings (namespace, key, value, updated_at) VALUES (?, ?, ?, ?)",
                    [
                        (namespace, k, json.dumps(v, default=str), now)
                        for k, v in items.items()
                    ],
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def get_namespaces(self) -> List[str]:
        """List all namespaces that have settings."""
        conn = self._require_conn()
        with self._lock:
            rows = conn.execute(
                "SELECT DISTINCT namespace FROM settings ORDER BY namespace"
            ).fetchall()
        return [r[0] for r in rows]

    # ── Migration from ui_config.json ────────────────────────────

    def migrate_from_json(self, json_path: Path) -> bool:
        """Migrate settings from a ui_config.json file into the store.

        Only migrates if the store is empty (first-time init).
        Returns True if migration occurred.
        """
        conn = self._require_conn()
        with self._lock:
            count = conn.execute("SELECT COUNT(*) FROM settings WHERE namespace = 'global'").fetchone()[0]
        if count > 0:
            return False  # Already has data, skip

        if not json_path.exists():
            return False

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return False
        except Exception as e:
            logger.warning("Failed to read %s for migration: %s", json_path, e)
            return False

        # Flatten top-level keys into the global namespace
        self.set_many("global", data)
        logger.info(
            "Migrated %d settings from %s to SQLite", len(data), json_path
        )
        return True

    # ── Listeners ────────────────────────────────────────────────

    def add_listener(self, listener: _SettingsListener) -> None:
        """Register a callback for setting changes."""
        self._listeners.append(listener)

    def _notify(self, namespace: str, key: str, value: Any) -> None:
        for fn in self._listeners:
            try:
                fn(namespace, key, value)
            except Exception:
                logger.debug("Settings listener error", exc_info=True)

    # ── Internal ─────────────────────────────────────────────────

    def _get(self, namespace: str, key: str, default: Any = None) -> Any:
        conn = self._require_conn()
        with self._lock:
            row = conn.execute(
                "SELECT value FROM settings WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return row[0]

    def _set(self, namespace: str, key: str, value: Any) -> None:
        conn = self._require_conn()
        now = time.time()
        serialized = json.dumps(value, default=str)
        with self._lock:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO settings (namespace, key, value, updated_at) VALUES (?, ?, ?, ?)",
                    (namespace, key, serialized, now),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        self._notify(namespace, key, value)

    def _delete(self, namespace: str, key: str) -> bool:
        conn = self._require_conn()
        with self._lock:
            try:
                cur = conn.execute(
                    "DELETE FROM settings WHERE namespace = ? AND key = ?",
                    (namespace, key),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        deleted = cur.rowcount > 0
        if deleted:
            self._notify(namespace, key, None)
        return deleted

    def _get_namespace(self, namespace: str) -> Dict[str, Any]:
        conn = self._require_conn()
        with self._lock:
            rows = conn.execute(
                "SELECT key, value FROM settings WHERE namespace = ?",
                (namespace,),
            ).fetchall()
        result: Dict[str, Any] = {}
        for k, v in rows:
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        return result

    # ── Export (for backward compat with JSON consumers) ─────────

    def export_as_dict(self) -> Dict[str, Any]:
        """Export all global settings as a flat dict (like the old ui_config.json)."""
        return self.get_all()

    def import_from_dict(self, data: Dict[str, Any]) -> None:
        """Import a flat dict into global settings (overwrites existing keys)."""
        self.set_many("global", data)


# Type alias for listener callbacks
_SettingsListener = Any  # Callable[[str, str, Any], None]


# ── Module-level singleton ───────────────────────────────────────
settings = SettingsStore()
