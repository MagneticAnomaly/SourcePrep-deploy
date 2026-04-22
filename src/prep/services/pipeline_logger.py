"""
Per-run pipeline file logger — writes verbose logs to .sourceprep/logs/
=====================================================================

Each pipeline run gets its own timestamped log file inside the project's
index directory (e.g. ``TEST/.sourceprep/logs/pipeline_20260215_222600.log``).

Logs are VERY verbose: every stage transition, every LLM call result,
every file processed, every error.  This is intentional — the files are
meant to be analyzed by Python scripts, not read manually.

Usage (automatic — called by PipelineOrchestrator):
    from prep.services.pipeline_logger import PipelineFileLogger
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

        # Also attach a stdlib FileHandler to capture ALL prep.* loggers
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

        # Set up stdlib file handler for ALL prep loggers
        self._file_handler = logging.FileHandler(str(self.log_path), encoding="utf-8")
        self._file_handler.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._file_handler.setFormatter(fmt)

        # Attach to the root prep logger so ALL subsystems are captured
        # (child loggers propagate up automatically — do NOT add to children too)
        prep_root = logging.getLogger("prep")
        prep_root.addHandler(self._file_handler)

        self._prune_old_logs()

        self._write_event("run_start", data={
            "group": group,
            "stages": stages,
            "project_id": project_id,
            "log_file": str(self.log_path),
        })

    def _prune_old_logs(self, max_logs: int = 50) -> None:
        """Keep only the `max_logs` most recent log files to prevent unbounded growth."""
        try:
            log_files = sorted(
                self.logs_dir.glob("pipeline_*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            for old_log in log_files[max_logs:]:
                try:
                    old_log.unlink()
                except Exception as e:
                    logger.debug("Failed to prune old log %s: %s", old_log, e)
        except Exception as e:
            logger.debug("Log pruning failed: %s", e)

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
            logging.getLogger("prep").removeHandler(self._file_handler)
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

    def decision(
        self,
        decision_type: str,
        choice: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a pipeline decision point.

        These are the most valuable events for diagnosing pipeline
        restart / incremental / UI issues.  Every time the orchestrator
        chooses between "restart from scratch", "incremental update",
        "resume from stage N", or "skip (up to date)", a decision event
        is logged with the full reasoning context.

        Decision types:
          - trigger_source: Who triggered this pipeline run (watcher, coverage, manual, retrigger)
          - resume_point: Which stage to start from (with per-stage justification)
          - mode_selection: Initial vs incremental vs force_from_start
          - coverage_gap: Coverage check result (stale/untraced counts)
          - deep_chain: Whether deep enrichment chains after fast sync
          - stage_skip: Why a specific stage was skipped
          - stage_invalidated: Why a specific stage was invalidated (mtime cascade, etc.)
        """
        self._write_event("decision", data={
            "decision_type": decision_type,
            "choice": choice,
            **(context or {}),
        })

    # ── Phase 61B: Self-Heal Diagnostic Events ─────────────────────

    def selfheal(
        self,
        action: str,
        detail: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a self-heal diagnostic event.

        These events form the audit trail for pipeline recovery and
        health monitoring.  They're the first place to look when
        diagnosing "why didn't the pipeline restart?"

        Actions:
          - startup_scan: Startup recovery is scanning projects
          - stale_detected: Found stale/zombie pipeline_run_metadata.json
          - metadata_reset: Reset stale metadata to 'interrupted'
          - auto_recover: Auto-triggering a pipeline run to recover
          - heartbeat_ok: Heartbeat check passed (healthy)
          - heartbeat_stale: Heartbeat watchdog detected stuck pipeline
          - heartbeat_write: Active stage wrote a heartbeat
          - coverage_gap: Coverage check found missing files at checkpoints
          - manifest_age: Per-stage manifest staleness summary
        """
        self._write_event("selfheal", data={
            "action": action,
            "detail": detail,
            **(data or {}),
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
            "elapsed": round(time.time() - self._start_time, 0) if self._start_time else 0,
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
