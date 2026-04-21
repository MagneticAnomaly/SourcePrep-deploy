"""Pipeline health aggregator — Phase 114.

Pulls together barrier status, per-stage manifest presence, backup
availability, and stuck journal rows into one payload for the dashboard
health badge and the GET /pipeline/health endpoint.

Pure reads. Does not mutate any state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from prep.services.pipeline_checkpoint import STAGE_OUTPUTS
from prep.services.pipeline.recovery import read_reset_barrier
from prep.services.pipeline.stages import stage_manifest_name

# Module-private alias so existing in-module call sites continue to work.
_stage_manifest_name = stage_manifest_name

_STAGE_ORDER = [
    "structural", "inferred_edges", "catalogue", "validation", "knowledge",
    "enrichment", "group_reasoning", "clustering", "deepening", "deep_knowledge",
    "atlas", "rules", "concepts", "audit", "antibodies",
]

_STALE_BARRIER_SECONDS = 60 * 60  # 1 hour


def _count_backups_for_stage(idx_dir: Path, stage_id: str) -> int:
    """Count available backups (golden + branch snapshots) for a stage.

    Run checkpoints are ephemeral (pruned to 3) and aren't reliable
    recovery sources — we only count stable backups.
    """
    manifest = _stage_manifest_name(stage_id)
    count = 0
    golden = idx_dir / ".checkpoints" / "_golden" / manifest
    if golden.is_file():
        count += 1
    branch_root = idx_dir / ".branch_snapshots"
    if branch_root.is_dir():
        for snap in branch_root.iterdir():
            if snap.is_dir() and (snap / manifest).is_file():
                count += 1
    return count


def _count_stuck_runs(project_id: str) -> int:
    """Count journal rows with status='running' older than 30 minutes.

    Defensive: if PipelineJournal doesn't expose count_stuck_runs yet,
    return 0 rather than raising. The method can be added later without
    breaking this endpoint.
    """
    try:
        from prep.services.pipeline_journal import PipelineJournal
        journal = PipelineJournal()
        if hasattr(journal, "count_stuck_runs"):
            return journal.count_stuck_runs(project_id, older_than_seconds=30 * 60)
        return 0
    except Exception:
        return 0


def collect_pipeline_health(project_id: str, idx_dir: Path) -> Dict[str, Any]:
    """Assemble the /pipeline/health payload for one project."""
    barrier_info = read_reset_barrier(project_id)
    barrier = {
        "active": barrier_info is not None,
        "age_seconds": barrier_info["age_seconds"] if barrier_info else None,
        "reason": barrier_info["reason"] if barrier_info else None,
        "written_at": barrier_info["written_at"] if barrier_info else None,
    }

    stages: List[Dict[str, Any]] = []
    for stage_id in _STAGE_ORDER:
        manifest_name = _stage_manifest_name(stage_id)
        manifest_path = idx_dir / manifest_name
        outputs = [n for n in STAGE_OUTPUTS.get(stage_id, []) if not n.endswith("_manifest.json")]
        output_exists = True if not outputs else all((idx_dir / n).is_file() for n in outputs)

        stages.append({
            "stage_id": stage_id,
            "manifest_exists": manifest_path.is_file(),
            "output_exists": output_exists,
            "provenance": None,  # Phase 115 will persist this in manifests
            "backup_count": _count_backups_for_stage(idx_dir, stage_id),
        })

    stuck_runs = _count_stuck_runs(project_id)

    warnings: List[str] = []
    if barrier["active"] and (barrier["age_seconds"] or 0) > _STALE_BARRIER_SECONDS:
        warnings.append(
            f"reset barrier has been active for {int(barrier['age_seconds'] // 60)} min — "
            "may be stale from an interrupted rebuild"
        )
    if stuck_runs > 0:
        warnings.append(f"{stuck_runs} stuck run(s) in journal")

    return {
        "project_id": project_id,
        "barrier": barrier,
        "stages": stages,
        "stuck_runs": stuck_runs,
        "warnings": warnings,
    }
