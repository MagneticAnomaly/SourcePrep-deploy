"""
Token Telemetry Module — Phase 56F
===================================
Tracks LLM token usage across the application using ContextVars.
"""
from __future__ import annotations

import contextvars
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import logging

logger = logging.getLogger(__name__)

# Core context variable for telemetry
_telemetry_ctx: contextvars.ContextVar[Optional[Dict[str, str]]] = contextvars.ContextVar(
    "telemetry_ctx", default=None
)

# Thread-safe fallback for Python 3.11 where ThreadPoolExecutor does NOT
# propagate ContextVars to child threads.  The pipeline processes one stage
# per project at a time, so this fallback always reflects the active stage.
_fallback_ctx: Optional[Dict[str, str]] = None
_fallback_lock = threading.Lock()

@dataclass
class ActiveLLMRequest:
    project_id: str
    task_id: str
    model: str
    provider: str
    start_time: float
    model_slot: Optional[str] = None

# Track active requests uniquely by thread ID
_active_requests: Dict[int, ActiveLLMRequest] = {}
_active_requests_lock = threading.Lock()


@contextmanager
def set_telemetry_context(project_id: str, task_id: str) -> Iterator[None]:
    """Set the telemetry context for the current thread/asyncio task.

    Any LLM generation performed within this block will automatically
    log token usage against this project and task.

    Sets both a ContextVar (correct for asyncio) and a module-level
    fallback (works in ThreadPoolExecutor child threads on Python <3.12).
    """
    global _fallback_ctx
    ctx_data = {"project_id": project_id, "task_id": task_id}
    token = _telemetry_ctx.set(ctx_data)
    with _fallback_lock:
        _fallback_ctx = ctx_data
    try:
        yield
    finally:
        _telemetry_ctx.reset(token)
        with _fallback_lock:
            _fallback_ctx = None


@dataclass
class TokenUsageRow:
    project_id: str
    task_id: str
    timestamp: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    provider: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "provider": self.provider,
        }

    @staticmethod
    def from_row(row: sqlite3.Row) -> "TokenUsageRow":
        return TokenUsageRow(
            project_id=row["project_id"],
            task_id=row["task_id"],
            timestamp=row["timestamp"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
            model=row["model"],
            provider=row["provider"],
        )


class TokenTelemetryStore:
    """Thread-safe SQLite store for LLM token usage telemetry.
    
    Uses WAL mode for concurrent read/write and autocommit to avoid
    blocking the write lock on every INSERT during concurrent pipeline.
    """

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    def init(self, db_path: Path) -> None:
        """Initialize the telemetry table. Reuses the shared settings DB."""
        with self._lock:
            if self._conn is not None:
                return
            self._conn = sqlite3.connect(
                str(db_path),
                check_same_thread=False,
                # autocommit — WAL handles durability; avoids blocking the
                # lock with a commit() on every pipeline INSERT.
                isolation_level=None,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._create_tables()

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("TokenTelemetryStore not initialized")
        return self._conn

    def _create_tables(self) -> None:
        conn = self._conn
        if conn is None:
            return
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS token_usage (
                project_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                model TEXT NOT NULL,
                provider TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage (project_id, timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_token_usage_task ON token_usage (project_id, task_id);
        """)

    def record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        model: str,
        provider: str,
    ) -> None:
        """Record usage if a telemetry context is currently active.

        Thread-safe DB write.  Checks ContextVar first (asyncio-correct),
        then falls back to the module-level fallback (works in
        ThreadPoolExecutor child threads on Python <3.12).
        """
        ctx = _telemetry_ctx.get()
        if not ctx:
            # Fallback for ThreadPoolExecutor child threads (Python 3.11)
            with _fallback_lock:
                ctx = _fallback_ctx
        if not ctx:
            return  # No active pipeline context

        project_id = ctx["project_id"]
        task_id = ctx["task_id"]
        
        # Don't record zero-token events
        if total_tokens <= 0:
            return

        with self._lock:
            if self._conn is None:
                return
            self._conn.execute(
                """INSERT INTO token_usage 
                   (project_id, task_id, timestamp, prompt_tokens, completion_tokens, total_tokens, model, provider)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    task_id,
                    time.time(),
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    model,
                    provider,
                )
            )
            # No explicit commit — autocommit mode + WAL handles durability

    def get_aggregated_usage(self, project_id: str, since_timestamp: float = 0.0) -> Dict[str, Any]:
        """
        Returns aggregated usage for a project grouped by task_id.
        Useful for building the AI Gateway metrics response.
        """
        conn = self._require_conn()
        with self._lock:
            rows = conn.execute(
                """SELECT task_id, 
                          SUM(prompt_tokens) as prompt, 
                          SUM(completion_tokens) as completion, 
                          SUM(total_tokens) as total
                   FROM token_usage
                   WHERE project_id = ? AND timestamp >= ?
                   GROUP BY task_id""",
                (project_id, since_timestamp)
            ).fetchall()

        result = {}
        for row in rows:
            result[row["task_id"]] = {
                "prompt_tokens": row["prompt"],
                "completion_tokens": row["completion"],
                "total_tokens": row["total"],
            }
        return result

    def track_active_request(self, model: str, provider: str, model_slot: Optional[str] = None) -> None:
        ctx = _telemetry_ctx.get()
        if not ctx:
            with _fallback_lock:
                ctx = _fallback_ctx
        if not ctx:
            return

        tid = threading.get_ident()
        with _active_requests_lock:
            _active_requests[tid] = ActiveLLMRequest(
                project_id=ctx["project_id"],
                task_id=ctx["task_id"],
                model=model,
                provider=provider,
                start_time=time.time(),
                model_slot=model_slot,
            )

    def untrack_active_request(self) -> None:
        tid = threading.get_ident()
        with _active_requests_lock:
            _active_requests.pop(tid, None)

    def get_active_requests(self) -> List[Dict[str, Any]]:
        with _active_requests_lock:
            now = time.time()
            return [
                {
                    "project_id": req.project_id,
                    "task_id": req.task_id,
                    "model": req.model,
                    "provider": req.provider,
                    "model_slot": req.model_slot,
                    "duration_seconds": now - req.start_time,
                }
                for req in _active_requests.values()
            ]

telemetry = TokenTelemetryStore()
