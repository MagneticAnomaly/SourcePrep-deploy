"""Database module — connection pooling, queries, and migrations."""

import sqlite3
import threading
from typing import Any, Dict, List, Optional
from contextlib import contextmanager


class Pool:
    """A simple connection pool for SQLite databases.

    Maintains a fixed number of reusable connections to avoid
    the overhead of opening/closing connections on every query.
    """

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._connections: List[sqlite3.Connection] = []
        self._lock = threading.Lock()

        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._connections.append(conn)

    @contextmanager
    def acquire(self):
        """Acquire a connection from the pool."""
        conn = None
        with self._lock:
            if self._connections:
                conn = self._connections.pop()

        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row

        try:
            yield conn
        finally:
            with self._lock:
                if len(self._connections) < self.pool_size:
                    self._connections.append(conn)
                else:
                    conn.close()

    def close_all(self):
        """Close all connections in the pool."""
        with self._lock:
            for conn in self._connections:
                conn.close()
            self._connections.clear()


def connect(db_path: str) -> sqlite3.Connection:
    """Create a new database connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a SQL query and return results as a list of dicts."""
    cursor = conn.execute(sql, params)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def execute(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    """Execute a SQL statement and return the number of affected rows."""
    cursor = conn.execute(sql, params)
    conn.commit()
    return cursor.rowcount


MIGRATIONS = [
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        token TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS permissions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        resource TEXT NOT NULL,
        action TEXT NOT NULL,
        UNIQUE(user_id, resource, action)
    )""",
]


def migrate(conn: sqlite3.Connection) -> int:
    """Run all pending database migrations.

    Returns the number of migrations applied.
    """
    applied = 0
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
            applied += 1
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return applied
