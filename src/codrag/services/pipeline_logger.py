"""
Per-run pipeline file logger — writes verbose logs to .codrag/logs/
=====================================================================

Each pipeline run gets its own timestamped log file inside the project's
index directory (e.g. ``TEST/.codrag/logs/pipeline_20260215_222600.log``).

Logs are VERY verbose: every stage transition, every LLM call result,
every file processed, every error.  This is intentional — the files are
meant to be analyzed by Python scripts, not read manually.

Usage (automatic — called by PipelineOrchestrator):
    from codrag.services.pipeline_logger import PipelineFileLogger
    pfl = PipelineFileLogger(index_dir)
    pfl.start_run("fast_sync", ["structural", "catalogue", ...])
    pfl.stage_start("structural")
    pfl.log("structural", "Built 111 nodes")
    pfl.stage_end("structural", {"nodes": 111})
    pfl.end_run()
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

# ── Structured log line format ───────────────────────────────────
# Each line is JSON:  {"ts": ..., "event": ..., "stage": ..., "data": ...}


class PipelineFileLogger:
    """Writes structured per-run logs to ``<index_dir>/logs/``."""

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = Path(index_dir)
        self.logs_dir = self.index_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.log_path = self.logs_dir / f"pipeline_{ts}.log"
        self.run_id: Optional[str] = None
        self._start_time: Optional[float] = None
        self._stage_start: Optional[float] = None
        self._fh: Optional[Any] = None

        # Also attach a stdlib FileHandler to capture ALL codrag.* loggers
        self._file_handler: Optional[logging.FileHandler] = None

    def start_run(self, group: str, stages: List[str], project_id: str = "") -> None:
        """Called at the start of a pipeline run."""
        self._start_time = time.time()
        self.run_id = f"{group}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # Re-create logs dir (may have been deleted by graph reset) and
        # generate a fresh log path for this run.
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.log_path = self.logs_dir / f"pipeline_{ts}.log"

        # Set up stdlib file handler for ALL codrag loggers
        self._file_handler = logging.FileHandler(str(self.log_path), encoding="utf-8")
        self._file_handler.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._file_handler.setFormatter(fmt)

        # Attach to the root codrag logger so ALL subsystems are captured
        # (child loggers propagate up automatically — do NOT add to children too)
        codrag_root = logging.getLogger("codrag")
        codrag_root.addHandler(self._file_handler)

        self._write_event("run_start", data={
            "group": group,
            "stages": stages,
            "project_id": project_id,
            "log_file": str(self.log_path),
        })

    def end_run(self, result: str = "completed", error: Optional[str] = None) -> None:
        """Called when the pipeline run finishes."""
        elapsed = time.time() - self._start_time if self._start_time else 0
        self._write_event("run_end", data={
            "result": result,
            "error": error,
            "elapsed_seconds": round(elapsed, 2),
        })
        # Remove file handler
        if self._file_handler:
            logging.getLogger("codrag").removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None

    def stage_start(self, stage: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Called when a pipeline stage starts."""
        self._stage_start = time.time()
        self._write_event("stage_start", stage=stage, data=data or {})

    def stage_end(
        self,
        stage: str,
        result: str = "completed",
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Called when a pipeline stage finishes."""
        elapsed = time.time() - self._stage_start if self._stage_start else 0
        self._write_event("stage_end", stage=stage, data={
            "result": result,
            "error": error,
            "elapsed_seconds": round(elapsed, 2),
            **(data or {}),
        })
        self._stage_start = None

    def log(self, stage: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Log a general message within a stage."""
        self._write_event("log", stage=stage, data={
            "message": message,
            **(data or {}),
        })

    def progress(self, stage: str, current: int, total: int, detail: str = "") -> None:
        """Log a progress update."""
        self._write_event("progress", stage=stage, data={
            "current": current,
            "total": total,
            "detail": detail,
        })

    def llm_call(
        self,
        stage: str,
        node_id: str,
        success: bool,
        elapsed_ms: float,
        model: str = "",
        error: str = "",
        confidence: float = 0.0,
    ) -> None:
        """Log an individual LLM call result."""
        self._write_event("llm_call", stage=stage, data={
            "node_id": node_id,
            "success": success,
            "elapsed_ms": round(elapsed_ms, 1),
            "model": model,
            "error": error,
            "confidence": round(confidence, 3),
        })

    def transition(
        self,
        build_type: str,
        old_phase: str,
        new_phase: str,
        detail: str = "",
    ) -> None:
        """Log a build slot phase transition."""
        self._write_event("transition", data={
            "build_type": build_type,
            "old_phase": old_phase,
            "new_phase": new_phase,
            "detail": detail,
        })

    def _write_event(
        self,
        event: str,
        stage: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write a single structured JSON line to the log file."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "elapsed": round(time.time() - self._start_time, 3) if self._start_time else 0,
            "event": event,
        }
        if stage:
            entry["stage"] = stage
        if data:
            entry["data"] = data

        try:
            line = json.dumps(entry, default=str) + "\n"
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.debug("Pipeline file logger write failed: %s", e)


# ── Module-level registry ─────────────────────────────────────────
# One logger per project (keyed by index_dir)
_loggers: Dict[str, PipelineFileLogger] = {}


def get_pipeline_logger(index_dir: Path) -> PipelineFileLogger:
    """Get or create a PipelineFileLogger for the given index directory."""
    key = str(Path(index_dir).resolve())
    if key not in _loggers:
        _loggers[key] = PipelineFileLogger(index_dir)
    return _loggers[key]


def close_pipeline_logger(index_dir: Path) -> None:
    """Close and remove the logger for the given index directory."""
    key = str(Path(index_dir).resolve())
    pfl = _loggers.pop(key, None)
    if pfl:
        pfl.end_run("closed")
