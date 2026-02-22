"""Structured logging configuration and formatters."""

import logging
import json
import sys
from datetime import datetime
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: Use JSON formatter for structured logging
        log_file: Optional file path for log output
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.FileHandler(log_file) if log_file else logging.StreamHandler(sys.stderr)
    formatter = JSONFormatter() if json_output else logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    return root


class AuditLogger:
    """Log security-sensitive operations for compliance auditing."""

    def __init__(self, logger_name: str = "audit"):
        self._logger = logging.getLogger(logger_name)

    def log_login(self, user_id: str, success: bool, ip_address: str):
        self._logger.info("LOGIN user=%s success=%s ip=%s", user_id, success, ip_address)

    def log_permission_change(self, admin_id: str, target_user: str, new_role: str):
        self._logger.warning(
            "PERMISSION_CHANGE admin=%s target=%s new_role=%s",
            admin_id, target_user, new_role,
        )

    def log_data_export(self, user_id: str, record_count: int):
        self._logger.info("DATA_EXPORT user=%s records=%d", user_id, record_count)
