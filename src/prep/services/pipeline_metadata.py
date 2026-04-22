"""
Pipeline Run Metadata — Phase 49 (Process Info)
================================================

Captures run-level metadata for pipeline executions:
- Prep/engine version
- Per-stage timing, models, quality metrics
- Overall quality summary
- Configuration snapshot

Written to ``<index_dir>/pipeline_run_metadata.json`` and updated
after each stage completes.  The orchestrator calls helpers here
from ``_start_group()``, ``_on_build_transition()``, and
``_advance_pipeline()``.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

METADATA_FILENAME = "pipeline_run_metadata.json"


@dataclass
class StageRecord:
    """Summary of a single stage within a run."""
    stage_id: str
    status: str = "pending"  # pending | running | completed | failed | skipped
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    model: Optional[Dict[str, Any]] = None
    manifest_file: Optional[str] = None
    quality: Optional[Dict[str, Any]] = None
    worker_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "stage_id": self.stage_id,
            "status": self.status,
        }
        if self.started_at:
            d["started_at"] = self.started_at
        if self.finished_at:
            d["finished_at"] = self.finished_at
        if self.elapsed_seconds is not None:
            d["elapsed_seconds"] = round(self.elapsed_seconds, 2)
        if self.model:
            d["model"] = self.model
        if self.manifest_file:
            d["manifest_file"] = self.manifest_file
        if self.quality:
            d["quality"] = self.quality
        if self.worker_result:
            d["worker_result"] = self.worker_result
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StageRecord":
        return cls(
            stage_id=d["stage_id"],
            status=d.get("status", "pending"),
            started_at=d.get("started_at"),
            finished_at=d.get("finished_at"),
            elapsed_seconds=d.get("elapsed_seconds"),
            model=d.get("model"),
            manifest_file=d.get("manifest_file"),
            quality=d.get("quality"),
            worker_result=d.get("worker_result"),
        )


@dataclass
class PipelineRunMetadata:
    """Metadata for an entire pipeline run (fast_sync or deep_enrichment)."""
    run_id: str = ""
    project_id: str = ""
    group: str = ""

    # Provenance
    prep_version: str = ""
    engine_version: Optional[str] = None
    engine_backend: str = "python"

    # Timing
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    elapsed_seconds: Optional[float] = None

    # Phase 61B: Heartbeat — active stages update this periodically
    heartbeat_at: Optional[str] = None

    # Status
    status: str = "running"  # running | completed | failed | cancelled | interrupted

    # Stages
    stages: List[StageRecord] = field(default_factory=list)

    # Models used across all stages (task_id → model info)
    models_used: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Overall quality summary (aggregated after completion)
    quality_summary: Optional[Dict[str, Any]] = None

    # Configuration snapshot
    config_snapshot: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "format_version": "1.0",
            "run_id": self.run_id,
            "project_id": self.project_id,
            "group": self.group,
            "status": self.status,
            "prep_version": self.prep_version,
        }
        if self.engine_version:
            d["engine_version"] = self.engine_version
        d["engine_backend"] = self.engine_backend
        if self.started_at:
            d["started_at"] = self.started_at
        if self.finished_at:
            d["finished_at"] = self.finished_at
        if self.elapsed_seconds is not None:
            d["elapsed_seconds"] = round(self.elapsed_seconds, 2)
        if self.heartbeat_at:
            d["heartbeat_at"] = self.heartbeat_at
        d["stages"] = [s.to_dict() for s in self.stages]
        if self.models_used:
            d["models_used"] = self.models_used
        if self.quality_summary:
            d["quality_summary"] = self.quality_summary
        if self.config_snapshot:
            d["config_snapshot"] = self.config_snapshot
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PipelineRunMetadata":
        return cls(
            run_id=d.get("run_id", ""),
            project_id=d.get("project_id", ""),
            group=d.get("group", ""),
            prep_version=d.get("prep_version", ""),
            engine_version=d.get("engine_version"),
            engine_backend=d.get("engine_backend", "python"),
            started_at=d.get("started_at"),
            finished_at=d.get("finished_at"),
            elapsed_seconds=d.get("elapsed_seconds"),
            heartbeat_at=d.get("heartbeat_at"),
            status=d.get("status", "running"),
            stages=[StageRecord.from_dict(s) for s in d.get("stages", [])],
            models_used=d.get("models_used", {}),
            quality_summary=d.get("quality_summary"),
            config_snapshot=d.get("config_snapshot"),
        )


# ── Helpers ────────────────────────────────────────────────────────


def create_run_metadata(
    run_id: str,
    project_id: str,
    group: str,
    stage_ids: List[str],
) -> PipelineRunMetadata:
    """Create initial PipelineRunMetadata at the start of a run."""
    from prep.core.provenance import get_prep_version, get_engine_version, get_engine_backend

    # Capture config snapshot
    config_snapshot = _capture_config_snapshot()

    meta = PipelineRunMetadata(
        run_id=run_id,
        project_id=project_id,
        group=group,
        prep_version=get_prep_version(),
        engine_version=get_engine_version(),
        engine_backend=get_engine_backend(),
        started_at=datetime.now(timezone.utc).isoformat(),
        status="running",
        stages=[StageRecord(stage_id=sid) for sid in stage_ids],
        config_snapshot=config_snapshot,
    )
    return meta


def mark_stage_started(meta: PipelineRunMetadata, stage_id: str) -> None:
    """Mark a stage as started in the run metadata."""
    for s in meta.stages:
        if s.stage_id == stage_id:
            s.status = "running"
            s.started_at = datetime.now(timezone.utc).isoformat()
            return


def mark_stage_completed(
    meta: PipelineRunMetadata,
    stage_id: str,
    worker_result: Optional[Dict[str, Any]] = None,
    manifest_file: Optional[str] = None,
) -> None:
    """Mark a stage as completed in the run metadata.

    Extracts ``_model_info`` and ``_stage_timing`` from the worker result
    if present (these are private keys added by the worker functions).
    """
    for s in meta.stages:
        if s.stage_id == stage_id:
            s.status = "completed"
            s.finished_at = datetime.now(timezone.utc).isoformat()
            s.manifest_file = manifest_file

            if worker_result:
                # Extract timing
                timing = worker_result.get("_stage_timing")
                if timing:
                    s.elapsed_seconds = timing.get("elapsed")

                # Extract model info
                model_info = worker_result.get("_model_info")
                if model_info:
                    s.model = model_info
                    # Also add to run-level models_used
                    task_id = stage_id  # Use stage_id as key
                    meta.models_used[task_id] = model_info

                # Store sanitized worker result (remove private keys)
                clean_result = {
                    k: v for k, v in worker_result.items()
                    if not k.startswith("_")
                }
                s.worker_result = clean_result
            return


def mark_stage_failed(
    meta: PipelineRunMetadata,
    stage_id: str,
    error: str,
) -> None:
    """Mark a stage as failed in the run metadata."""
    for s in meta.stages:
        if s.stage_id == stage_id:
            s.status = "failed"
            s.finished_at = datetime.now(timezone.utc).isoformat()
            s.worker_result = {"error": error}
            return


def finalize_run_metadata(
    meta: PipelineRunMetadata,
    status: str = "completed",
    index_dir: Optional[Path] = None,
) -> None:
    """Finalize run metadata on completion/failure.

    Aggregates quality metrics from stage manifests if index_dir is provided.
    """
    meta.status = status
    meta.finished_at = datetime.now(timezone.utc).isoformat()

    if meta.started_at:
        try:
            start = datetime.fromisoformat(meta.started_at)
            end = datetime.fromisoformat(meta.finished_at)
            meta.elapsed_seconds = (end - start).total_seconds()
        except Exception:
            pass

    # Aggregate quality metrics from stage manifests
    if index_dir and status == "completed":
        meta.quality_summary = _aggregate_run_quality(meta, index_dir)


def save_run_metadata(meta: PipelineRunMetadata, index_dir: Path) -> None:
    """Write run metadata to the index directory."""
    path = index_dir / METADATA_FILENAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta.to_dict(), f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.debug("Failed to save run metadata: %s", e)


# ── Phase 61B: Heartbeat + Staleness Detection ────────────────────

_HEARTBEAT_STALE_SECONDS = 300.0  # 5 minutes without heartbeat = stuck
_STARTUP_STALE_SECONDS = 3600.0   # 1 hour old "running" metadata on startup = zombie


def update_heartbeat(index_dir: Path) -> None:
    """Write a fresh heartbeat timestamp to pipeline_run_metadata.json.

    Called periodically by active pipeline stages (~60s intervals) so
    the watchdog can distinguish a genuinely running pipeline from a
    zombie left behind by a crashed process.
    """
    meta = load_run_metadata(index_dir)
    if meta is None or meta.status != "running":
        return
    meta.heartbeat_at = datetime.now(timezone.utc).isoformat()
    save_run_metadata(meta, index_dir)


def check_heartbeat_stale(index_dir: Path) -> Optional[Dict[str, Any]]:
    """Check if pipeline_run_metadata.json has a stale heartbeat.

    Returns None if healthy, or a diagnostic dict if stale/zombie:
    {
        "status": "zombie" | "stale_heartbeat",
        "started_at": "...",
        "heartbeat_at": "...",
        "age_seconds": 12345,
        "heartbeat_age_seconds": 600,
        "group": "deep_enrichment",
        "run_id": "run-...",
    }
    """
    meta = load_run_metadata(index_dir)
    if meta is None or meta.status != "running":
        return None  # No active run or already completed/failed

    now = datetime.now(timezone.utc)
    age_seconds = 0.0
    heartbeat_age_seconds = 0.0

    if meta.started_at:
        try:
            started = datetime.fromisoformat(meta.started_at)
            age_seconds = (now - started).total_seconds()
        except Exception:
            pass

    if meta.heartbeat_at:
        try:
            hb = datetime.fromisoformat(meta.heartbeat_at)
            heartbeat_age_seconds = (now - hb).total_seconds()
        except Exception:
            pass
    else:
        # No heartbeat ever written — use started_at age as heartbeat age
        heartbeat_age_seconds = age_seconds

    result: Dict[str, Any] = {
        "run_id": meta.run_id,
        "group": meta.group,
        "started_at": meta.started_at,
        "heartbeat_at": meta.heartbeat_at,
        "age_seconds": round(age_seconds, 1),
        "heartbeat_age_seconds": round(heartbeat_age_seconds, 1),
    }

    # Zombie: "running" for over 1 hour with no heartbeat
    if age_seconds > _STARTUP_STALE_SECONDS and not meta.heartbeat_at:
        result["status"] = "zombie"
        return result

    # Stale heartbeat: last heartbeat was over 5 minutes ago
    if heartbeat_age_seconds > _HEARTBEAT_STALE_SECONDS:
        result["status"] = "stale_heartbeat"
        return result

    return None  # Healthy


def reset_stale_metadata(index_dir: Path, reason: str = "startup_recovery") -> bool:
    """Reset stale 'running' metadata to 'interrupted'.

    Returns True if the metadata was reset, False if already clean.
    """
    meta = load_run_metadata(index_dir)
    if meta is None or meta.status != "running":
        return False
    meta.status = "interrupted"
    meta.finished_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "Phase 61B: Reset stale pipeline_run_metadata.json for %s/%s "
        "(run_id=%s, started=%s, reason=%s)",
        meta.project_id, meta.group, meta.run_id,
        meta.started_at, reason,
    )
    save_run_metadata(meta, index_dir)
    return True


def load_run_metadata(index_dir: Path) -> Optional[PipelineRunMetadata]:
    """Load run metadata from the index directory."""
    path = index_dir / METADATA_FILENAME
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PipelineRunMetadata.from_dict(data)
    except Exception as e:
        logger.debug("Failed to load run metadata: %s", e)
        return None


def is_stage_pending_in_interrupted_run(index_dir: Path, stage_id: str) -> bool:
    """True when the last recorded run did NOT complete and this stage was
    pending/running/failed (i.e. not marked completed) in that run.

    Used by selfheal and resume-point detection to recognize that a data
    file on disk is legitimate in-progress work from a paused run, not
    genuinely orphan output that should be resurrected via a stub manifest.
    Without this guard, pausing mid-enrichment leaves a partial
    ``trace_epistemic.jsonl`` that selfheal claims as "complete," and the
    resume detector then skips the stage entirely on the next run.
    """
    meta = load_run_metadata(index_dir)
    if meta is None:
        return False
    if meta.status == "completed":
        return False
    for sr in meta.stages:
        if sr.stage_id == stage_id:
            return sr.status != "completed"
    return False


# ── Private Helpers ────────────────────────────────────────────────


def _capture_config_snapshot() -> Dict[str, Any]:
    """Capture relevant pipeline configuration for provenance."""
    snapshot: Dict[str, Any] = {}
    try:
        from prep.server import _load_ui_config
        ui_cfg = _load_ui_config()
        llm_cfg = ui_cfg.get("llm_config") or {}
        snapshot["assignment_mode"] = llm_cfg.get("assignment_mode", "structured")
    except Exception:
        pass
    return snapshot


def _aggregate_run_quality(
    meta: PipelineRunMetadata,
    index_dir: Path,
) -> Dict[str, Any]:
    """Aggregate quality metrics across all completed stages."""
    from prep.services.pipeline.stages import (
        StageId, STAGE_OUTPUT_FILE, STAGE_CONFIDENCE_FIELD,
    )

    total_files_processed = 0
    confidence_sum = 0.0
    confidence_count = 0
    completed_stages = 0
    failed_stages = 0

    for sr in meta.stages:
        if sr.status == "completed":
            completed_stages += 1
        elif sr.status == "failed":
            failed_stages += 1

        # Try to aggregate quality from output files
        try:
            stage = StageId(sr.stage_id)
            output_file = STAGE_OUTPUT_FILE.get(stage)
            conf_field = STAGE_CONFIDENCE_FIELD.get(stage)
            if output_file and conf_field:
                from prep.core.provenance import aggregate_quality_metrics
                path = index_dir / output_file
                if path.exists():
                    q = aggregate_quality_metrics(path, conf_field)
                    if q:
                        sr.quality = q
                        total_files_processed += q.get("total_items", 0)
                        avg = q.get("avg_confidence")
                        count = q.get("processed", 0)
                        if avg is not None and count > 0:
                            confidence_sum += avg * count
                            confidence_count += count
        except Exception:
            pass

    summary: Dict[str, Any] = {
        "completed_stages": completed_stages,
        "failed_stages": failed_stages,
        "total_stages": len(meta.stages),
        "total_files_processed": total_files_processed,
    }

    if confidence_count > 0:
        summary["avg_confidence"] = round(confidence_sum / confidence_count, 3)

    return summary
