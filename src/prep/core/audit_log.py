"""
EA-H1: Append-only audit log for enterprise security and compliance.

Records security events, policy violations, LLM API calls, license
activations, and admin actions. Stored in a SQLite table alongside
the settings store.

This is NOT the codebase audit system (core/audit/) — this is the
activity/security event log designed in ENTERPRISE_ADMIN_DESIGN.md §13A.

Usage:
    from prep.core.audit_log import audit_log
    audit_log.record("llm_api_call", provider="google", model="gemini-2.5-flash", tokens=1500)
    audit_log.record("policy_violation", action="add_endpoint", provider="openai", blocked=True)
    entries = audit_log.query(severity="WARNING", limit=50)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1


@dataclass
class AuditEntry:
    """A single audit log entry."""
    id: int = 0
    timestamp: float = 0.0
    event_type: str = ""
    severity: str = "INFO"
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    project_id: Optional[str] = None
    user: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "project_id": self.project_id,
            "user": self.user,
        }


# Event types and their default severities
EVENT_SEVERITIES: Dict[str, str] = {
    # License events
    "license_activated": "INFO",
    "license_deactivated": "INFO",
    "license_verification_failed": "WARNING",
    "license_expired": "WARNING",
    # Policy events
    "policy_violation_blocked": "WARNING",
    "policy_violation_allowed": "INFO",
    "config_drift_detected": "WARNING",
    # LLM/DLP events
    "llm_api_call": "INFO",
    "dlp_file_blocked": "INFO",
    "dlp_provider_blocked": "WARNING",
    "dlp_secrets_redacted": "INFO",
    # Security events
    "secrets_in_config": "CRITICAL",
    "index_hash_mismatch": "CRITICAL",
    "ssrf_attempt_blocked": "WARNING",
    "mcp_rate_limit_exceeded": "WARNING",
    "suspicious_llm_output": "WARNING",
    "unicode_injection_detected": "WARNING",
    # Sync events
    "s3_endpoint_changed": "WARNING",
    "index_downloaded": "INFO",
    "index_uploaded": "INFO",
    # Admin actions
    "machine_revoked": "INFO",
    "project_quarantined": "WARNING",
    "endpoint_blocked": "WARNING",
    "config_approved": "INFO",
    "security_report_exported": "INFO",
    # Budget events
    "budget_threshold_80": "WARNING",
    "budget_threshold_100": "WARNING",
    "budget_exceeded": "WARNING",
}


class AuditLog:
    """Append-only SQLite audit log for enterprise security events."""

    def __init__(self):
        self._db_path: Optional[Path] = None
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    def init(self, db_path: Path) -> None:
        """Initialize with a database path. Safe to call multiple times."""
        with self._lock:
            if self._conn is not None:
                return
            self._db_path = db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._create_tables()
            logger.debug("Audit log initialized at %s", db_path)

    def _create_tables(self) -> None:
        assert self._conn
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'INFO',
                message TEXT NOT NULL DEFAULT '',
                details TEXT NOT NULL DEFAULT '{}',
                project_id TEXT,
                user TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type);
            CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_log(severity);
            CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_log(project_id);
        """)
        self._conn.commit()

    def _ensure_init(self) -> None:
        """Auto-initialize with default path if not already initialized."""
        if self._conn is not None:
            return
        default_path = Path.home() / ".local" / "share" / "sourceprep" / "audit_log.db"
        self.init(default_path)

    def record(
        self,
        event_type: str,
        message: str = "",
        *,
        severity: Optional[str] = None,
        project_id: Optional[str] = None,
        user: Optional[str] = None,
        **details: Any,
    ) -> int:
        """Record an audit event. Returns the entry ID.

        Args:
            event_type: Event type key (see EVENT_SEVERITIES)
            message: Human-readable description
            severity: Override severity (default: lookup from EVENT_SEVERITIES)
            project_id: Associated project ID (optional)
            user: User identifier (optional)
            **details: Additional key-value data stored as JSON
        """
        self._ensure_init()
        assert self._conn

        if severity is None:
            severity = EVENT_SEVERITIES.get(event_type, "INFO")

        now = time.time()
        details_json = json.dumps(details, default=str)

        with self._lock:
            cursor = self._conn.execute(
                """INSERT INTO audit_log (timestamp, event_type, severity, message, details, project_id, user)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (now, event_type, severity, message, details_json, project_id, user),
            )
            self._conn.commit()
            entry_id = cursor.lastrowid or 0

        logger.debug("Audit [%s] %s: %s", severity, event_type, message[:100])
        return entry_id

    def query(
        self,
        *,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        project_id: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEntry]:
        """Query audit log entries with filters.

        Returns entries ordered by timestamp descending (newest first).
        """
        self._ensure_init()
        assert self._conn

        conditions: List[str] = []
        params: List[Any] = []

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            conditions.append("timestamp <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT id, timestamp, event_type, severity, message, details, project_id, user FROM audit_log {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()

        entries: List[AuditEntry] = []
        for row in rows:
            try:
                details = json.loads(row[5]) if row[5] else {}
            except (json.JSONDecodeError, TypeError):
                details = {}
            entries.append(AuditEntry(
                id=row[0],
                timestamp=row[1],
                event_type=row[2],
                severity=row[3],
                message=row[4],
                details=details,
                project_id=row[6],
                user=row[7],
            ))
        return entries

    def count(
        self,
        *,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> int:
        """Count entries matching filters."""
        self._ensure_init()
        assert self._conn

        conditions: List[str] = []
        params: List[Any] = []
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            conditions.append("timestamp <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) FROM audit_log {where}"

        with self._lock:
            return self._conn.execute(sql, params).fetchone()[0]

    def purge_before(self, cutoff_timestamp: float) -> int:
        """Delete entries older than the cutoff. Returns count deleted.

        Used for data retention policy (EA-K4).
        """
        self._ensure_init()
        assert self._conn

        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM audit_log WHERE timestamp < ?", (cutoff_timestamp,)
            )
            self._conn.commit()
            return cursor.rowcount

    # ── EA-H3: Token usage tracking ───────────────────────────────

    def record_token_usage(
        self,
        provider: str,
        model: str,
        tokens: int,
        *,
        stage: str = "",
        project_id: Optional[str] = None,
        endpoint_url: str = "",
    ) -> int:
        """Record token usage for an LLM API call.

        Convenience wrapper around record() that standardizes the token
        usage event format for aggregation queries.
        """
        return self.record(
            "llm_api_call",
            f"{provider}/{model}: {tokens} tokens" + (f" [{stage}]" if stage else ""),
            project_id=project_id,
            provider=provider,
            model=model,
            tokens=tokens,
            stage=stage,
            endpoint_url=endpoint_url,
        )

    # ── EA-H8: CSV export ────────────────────────────────────────

    def export_csv(self, *, limit: int = 50_000) -> str:
        """Export the audit log as a CSV string.

        Used by the ``/admin/audit-log/export?format=csv`` endpoint.
        Returns a UTF-8 CSV string with headers.
        """
        import csv
        import io

        entries = self.query(limit=limit)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "timestamp", "event_type", "severity", "message", "details", "project_id", "user"])
        for e in entries:
            writer.writerow([
                e.id, e.timestamp, e.event_type, e.severity,
                e.message, json.dumps(e.details, default=str),
                e.project_id or "", e.user or "",
            ])
        return buf.getvalue()

    def get_token_usage(
        self,
        *,
        project_id: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Aggregate token usage from audit log entries.

        Returns breakdown by provider, model, and stage.
        """
        entries = self.query(
            event_type="llm_api_call",
            project_id=project_id,
            since=since,
            until=until,
            limit=10000,
        )

        total_tokens = 0
        by_provider: Dict[str, int] = {}
        by_model: Dict[str, int] = {}
        by_stage: Dict[str, int] = {}
        call_count = 0

        for e in entries:
            tokens = e.details.get("tokens", 0)
            if not isinstance(tokens, (int, float)):
                continue
            tokens = int(tokens)
            total_tokens += tokens
            call_count += 1

            provider = e.details.get("provider", "unknown")
            model = e.details.get("model", "unknown")
            stage = e.details.get("stage", "unknown")

            by_provider[provider] = by_provider.get(provider, 0) + tokens
            by_model[model] = by_model.get(model, 0) + tokens
            by_stage[stage] = by_stage.get(stage, 0) + tokens

        return {
            "total_tokens": total_tokens,
            "call_count": call_count,
            "by_provider": by_provider,
            "by_model": by_model,
            "by_stage": by_stage,
        }


# Security-relevant event types (for EA-I9 security event log filtering)
SECURITY_EVENT_TYPES = {
    "license_verification_failed", "license_expired",
    "policy_violation_blocked", "policy_violation_allowed",
    "config_drift_detected",
    "dlp_file_blocked", "dlp_provider_blocked", "dlp_secrets_redacted",
    "secrets_in_config", "index_hash_mismatch",
    "ssrf_attempt_blocked", "mcp_rate_limit_exceeded",
    "suspicious_llm_output", "unicode_injection_detected",
    "s3_endpoint_changed",
    "machine_revoked", "project_quarantined", "endpoint_blocked",
    "budget_threshold_80", "budget_threshold_100", "budget_exceeded",
}


# Singleton instance
audit_log = AuditLog()


def get_audit_log() -> AuditLog:
    """Return the global AuditLog singleton.

    Preferred accessor — callers should use this instead of importing
    the ``audit_log`` variable directly so the singleton is always
    returned regardless of import-time initialisation order.
    """
    return audit_log
