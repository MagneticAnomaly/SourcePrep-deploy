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
import threading
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

        # Phase 136 Part 15: periodic concurrency sampler.  Fires every
        # ``_concurrency_sample_interval_s`` while a run is active so a
        # leak that develops mid-stage shows up in the log.  Override
        # the interval via env ``PREP_PIPELINE_CONCURRENCY_SAMPLE_SEC``
        # — set to 0 to disable.
        self._concurrency_sampler_stop: Optional[Any] = None
        self._concurrency_sampler_thread: Optional[Any] = None
        try:
            self._concurrency_sample_interval_s: float = float(
                os.getenv("PREP_PIPELINE_CONCURRENCY_SAMPLE_SEC", "30")
            )
        except (TypeError, ValueError):
            self._concurrency_sample_interval_s = 30.0

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

        # Phase 136 Part 15: start periodic concurrency sampler so
        # mid-stage drift (e.g. a leak that develops over ~minutes of
        # a long stage) shows up in the log instead of only at
        # stage boundaries.  Set PREP_PIPELINE_CONCURRENCY_SAMPLE_SEC=0
        # to disable; default 30 s.
        self._start_concurrency_sampler()

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
        # Phase 136 Part 15: stop the periodic sampler BEFORE writing the
        # run_end event so the sampler can't race a snapshot in after the
        # final log line.
        self._stop_concurrency_sampler()
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

    def _start_concurrency_sampler(self) -> None:
        """Spawn a daemon thread that calls ``concurrency_snapshot``
        every ``_concurrency_sample_interval_s`` until the run ends.

        Set ``PREP_PIPELINE_CONCURRENCY_SAMPLE_SEC=0`` to disable.
        Daemon thread so process exit doesn't hang.
        """
        if self._concurrency_sample_interval_s <= 0:
            return
        if self._concurrency_sampler_thread is not None:
            return  # already running
        stop = threading.Event()
        interval = self._concurrency_sample_interval_s

        def _run():
            while not stop.wait(interval):
                try:
                    self.concurrency_snapshot(reason="periodic_sample")
                except Exception as e:
                    logger.debug(
                        "concurrency sampler: snapshot failed: %s", e,
                    )

        t = threading.Thread(
            target=_run,
            name="prep-pipeline-concurrency-sampler",
            daemon=True,
        )
        self._concurrency_sampler_stop = stop
        self._concurrency_sampler_thread = t
        t.start()

    def _stop_concurrency_sampler(self) -> None:
        """Stop the periodic concurrency sampler if it's running."""
        stop = self._concurrency_sampler_stop
        if stop is not None:
            stop.set()
        thread = self._concurrency_sampler_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._concurrency_sampler_stop = None
        self._concurrency_sampler_thread = None

    def stage_start(self, stage: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Called when a pipeline stage starts."""
        self._stage_start = time.time()
        self._write_event("stage_start", stage=stage, data=data or {})
        # Phase 136 Part 15: snapshot concurrency state at stage boundary
        # so past-run analysis can answer "how many workers were in flight
        # when stage X started" by grepping concurrency_snapshot events.
        self.concurrency_snapshot(stage=stage, reason="stage_start")

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
        # Phase 136 Part 15: snapshot at stage exit to catch leaks that
        # bridge the stage boundary (e.g. swarm_role entries that
        # outlive their stage).
        self.concurrency_snapshot(stage=stage, reason="stage_end")
        self._stage_start = None

    def concurrency_snapshot(
        self,
        stage: Optional[str] = None,
        reason: str = "",
    ) -> None:
        """Phase 136 Part 15 — write a structured concurrency snapshot.

        Records, at the moment of call:
          * Per-slot scheduler state (max_concurrent, dynamic_capacity,
            in_flight_requests, current_limit, current_load, AIMD mode,
            state, active project→stage map).
          * Per-tid token_telemetry active_requests with thread name +
            alive flag + age + swarm_role.
          * The ``in_flight_total`` vs ``active_requests_total`` delta —
            non-zero means an over-count is in progress and at least one
            tracked entry isn't matched by an in-flight scheduler request.

        Best-effort: silently no-ops if the scheduler or telemetry
        modules can't be imported.  Never blocks pipeline progress.
        """
        try:
            from prep.services.pipeline.scheduler import pipeline_scheduler
            from prep.services.token_telemetry import telemetry as _tel
        except Exception:  # pragma: no cover — import guard
            return

        slots: Dict[str, Dict[str, Any]] = {}
        in_flight_total = 0
        try:
            snapshot = pipeline_scheduler.status()
            for nid, info in snapshot.get("nodes", {}).items():
                slots[nid] = {
                    "max_concurrent": info.get("max_concurrent"),
                    "dynamic_capacity": info.get("dynamic_capacity"),
                    "current_limit": info.get("current_limit"),
                    "in_flight_requests": info.get("in_flight_requests"),
                    "current_load": info.get("current_load"),
                    "aimd_mode": info.get("aimd_mode"),
                    "state": info.get("state"),
                    "active": info.get("active", {}),
                }
                in_flight_total += int(info.get("in_flight_requests") or 0)
        except Exception as e:
            logger.debug("concurrency_snapshot: scheduler.snapshot failed: %s", e)

        active_requests: List[Dict[str, Any]] = []
        try:
            active_requests = _tel.dump_active_state()
        except Exception as e:
            logger.debug("concurrency_snapshot: dump_active_state failed: %s", e)

        delta = len(active_requests) - in_flight_total
        self._write_event("concurrency_snapshot", stage=stage, data={
            "reason": reason,
            "slots": slots,
            "active_requests": active_requests,
            "in_flight_total": in_flight_total,
            "active_requests_total": len(active_requests),
            # delta > 0: tracked entries exceed in_flight — likely leak.
            # delta < 0: scheduler ahead of telemetry — race between
            # acquire_request and _track_active("start") (small window,
            # expected).
            "tracked_minus_in_flight": delta,
        })

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
