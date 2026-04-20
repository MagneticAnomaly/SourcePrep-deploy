"""
Pipeline History API — Phase 49 (Process Info)
===============================================

Endpoints for querying pipeline run history and data provenance.

Routes:
    GET /projects/{id}/pipeline/history     — List recent runs
    GET /projects/{id}/pipeline/runs/{rid}  — Get full run metadata
    GET /projects/{id}/pipeline/provenance  — Current data provenance
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_index_dir(project_id: str) -> Path:
    """Resolve project index directory."""
    from codrag.services.project_helpers import require_project
    from codrag.core.project_registry import project_index_dir
    project = require_project(project_id)
    return project_index_dir(project)


@router.get("/projects/{project_id}/pipeline/history")
async def get_pipeline_history(
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    group: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """List recent pipeline runs for a project.

    Query params:
        limit: max number of runs to return (default 20)
        group: filter by group ("fast_sync" or "deep_enrichment")
        status: filter by status ("completed", "failed", etc.)
    """
    try:
        from codrag.services.pipeline_history import history
        runs = history.get_project_runs(
            project_id,
            limit=limit,
            group=group,
            status=status,
        )
        return {
            "success": True,
            "data": {
                "runs": [r.to_dict() for r in runs],
                "total": len(runs),
            },
        }
    except RuntimeError as e:
        # History not initialized
        return {
            "success": True,
            "data": {"runs": [], "total": 0},
        }
    except Exception as e:
        logger.exception("Failed to get pipeline history for %s", project_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/pipeline/runs/{run_id}")
async def get_pipeline_run(
    project_id: str,
    run_id: str,
) -> Dict[str, Any]:
    """Get full metadata for a specific pipeline run.

    First tries the history DB for a summary, then loads the full
    metadata JSON file from the index directory if available.
    """
    try:
        # Try loading the full metadata file first
        idx_dir = _get_index_dir(project_id)
        from codrag.services.pipeline_metadata import load_run_metadata
        meta = load_run_metadata(idx_dir)
        if meta and meta.run_id == run_id:
            return {
                "success": True,
                "data": meta.to_dict(),
            }

        # Fall back to history DB
        from codrag.services.pipeline_history import history
        entry = history.get_run(run_id)
        if entry:
            return {
                "success": True,
                "data": entry.to_dict(),
            }

        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get run %s", run_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/pipeline/runs/{run_id}/stages/{stage_id}/manifest")
async def get_stage_manifest(
    project_id: str,
    run_id: str,
    stage_id: str,
) -> Dict[str, Any]:
    """Get the enhanced stage manifest for a specific stage in a run."""
    try:
        from codrag.services.pipeline.stages import StageId, STAGE_MANIFEST_FILE
        from codrag.core.stage_manifest import load_stage_manifest

        idx_dir = _get_index_dir(project_id)

        # Map stage_id to manifest filename
        try:
            stage = StageId(stage_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown stage: {stage_id}")

        manifest_file = STAGE_MANIFEST_FILE.get(stage)
        if not manifest_file:
            raise HTTPException(status_code=404, detail=f"No manifest for stage: {stage_id}")

        manifest = load_stage_manifest(idx_dir / manifest_file)
        if not manifest:
            raise HTTPException(status_code=404, detail=f"Manifest not found for stage: {stage_id}")

        return {
            "success": True,
            "data": manifest.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get stage manifest %s/%s", run_id, stage_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/pipeline/provenance")
async def get_data_provenance(
    project_id: str,
) -> Dict[str, Any]:
    """Get current data provenance — which run/model produced each data file.

    Reads all stage manifest files and returns a summary of which model
    generated each piece of data, when it was generated, and its quality.
    """
    try:
        from codrag.services.pipeline.stages import StageId, STAGE_MANIFEST_FILE, STAGE_OUTPUT_FILE
        from codrag.core.stage_manifest import load_stage_manifest
        import time

        idx_dir = _get_index_dir(project_id)

        current_data: Dict[str, Any] = {}
        oldest_age_days: Optional[float] = None
        now = time.time()

        for stage in StageId:
            manifest_file = STAGE_MANIFEST_FILE.get(stage)
            output_file = STAGE_OUTPUT_FILE.get(stage)
            if not manifest_file:
                continue

            manifest = load_stage_manifest(idx_dir / manifest_file)
            if not manifest:
                continue

            # Determine age. Prefer finished_at (real run); fall back to
            # restored_at for selfheal stubs so the UI still has a timestamp.
            age_ref = manifest.finished_at or manifest.restored_at
            age_days: Optional[float] = None
            if age_ref:
                try:
                    from datetime import datetime
                    ref = datetime.fromisoformat(age_ref.replace("Z", "+00:00"))
                    age_days = (now - ref.timestamp()) / 86400.0
                    age_days = round(age_days, 1)
                    if oldest_age_days is None or age_days > oldest_age_days:
                        oldest_age_days = age_days
                except Exception:
                    pass

            entry: Dict[str, Any] = {
                "stage_id": stage.value,
                "run_id": manifest.run_id,
                "codrag_version": manifest.codrag_version,
                "generated_at": age_ref,
                "age_days": age_days,
            }

            # Recovery markers — let the dashboard distinguish a real run
            # from a selfheal stub or crash-recovery placeholder.
            if manifest.restored is not None:
                entry["restored"] = manifest.restored
            if manifest.source:
                entry["source"] = manifest.source
            if manifest.backup_type:
                entry["backup_type"] = manifest.backup_type
            if manifest.restored_at:
                entry["restored_at"] = manifest.restored_at
            if manifest.recovered is not None:
                entry["recovered"] = manifest.recovered
            if manifest.recovery_note:
                entry["recovery_note"] = manifest.recovery_note

            # Model info
            if manifest.model:
                if isinstance(manifest.model, dict):
                    entry["model"] = manifest.model.get("model_name", "unknown")
                    entry["provider"] = manifest.model.get("provider", "unknown")
                else:
                    entry["model"] = str(manifest.model)
                    entry["provider"] = "unknown"

            # Quality
            if manifest.quality:
                entry["quality"] = {
                    k: manifest.quality[k]
                    for k in ("avg_confidence", "success_rate", "total_items")
                    if k in manifest.quality
                }
                # Multi-model breakdown (Phase 49: mid-stage model swap detection)
                if "model_breakdown" in manifest.quality:
                    entry["model_breakdown"] = manifest.quality["model_breakdown"]

            # Elapsed
            if manifest.elapsed_seconds is not None:
                entry["elapsed_seconds"] = manifest.elapsed_seconds

            # Always key by stage_id to avoid collisions when two stages
            # share an output file (e.g. enrichment + deepening both write
            # trace_epistemic.jsonl).  Frontend lookupProvenance() handles
            # both stage_id keys and output-file keys.
            current_data[stage.value] = entry

        # Also load run-level metadata if available
        from codrag.services.pipeline_metadata import load_run_metadata
        run_meta = load_run_metadata(idx_dir)
        last_run = run_meta.to_dict() if run_meta else None

        return {
            "success": True,
            "data": {
                "current_data": current_data,
                "last_run": last_run,
                "oldest_data_age_days": oldest_age_days,
                "staleness_warning": oldest_age_days is not None and oldest_age_days > 30,
            },
        }
    except Exception as e:
        logger.exception("Failed to get data provenance for %s", project_id)
        raise HTTPException(status_code=500, detail=str(e))
