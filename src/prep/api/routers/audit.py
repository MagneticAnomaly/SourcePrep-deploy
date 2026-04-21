"""
CoDRAG Audit Router — Phase 43
================================

REST endpoints for the AutoAudit system.

Endpoints:
  POST /projects/{id}/audit          — Trigger a full audit (Tier 1 + optional Tier 2)
  GET  /projects/{id}/audit/status   — Check audit status / last run metadata
  GET  /projects/{id}/audit/findings — Get raw structured findings
  GET  /projects/{id}/audit/spaghetti — Per-file refactor urgency scores (Phase 52)
  GET  /projects/{id}/audit/reports  — List generated report documents
  GET  /projects/{id}/audit/report/{name} — Read a specific report
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from prep.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])


def _srv():
    import prep.server as _s
    return _s


# Phase 105b: the direct-call POST /projects/{id}/audit handler is
# deleted. Audit runs now route through the orchestrator via
# POST /projects/{id}/pipeline/stages/audit/run, which gives the run
# queue, journal, history, and pipeline-panel state parity with the
# other finalize stages. The status/findings/reports GET endpoints
# below remain since they just read cached results from disk.
#
# _audit_threads / _audit_errors are kept as empty compat stubs so
# GET /projects/{id}/audit/status retains its existing payload shape.
# The new trigger path drives running-state through the pipeline
# status endpoint; the dashboard's useAuditSystem hook reconciles
# auditStatus.running from useStageRegenerate.
_audit_threads: Dict[str, threading.Thread] = {}
_audit_errors: Dict[str, str] = {}


@router.get("/projects/{project_id}/audit/status")
def get_audit_status(project_id: str) -> Dict[str, Any]:
    """Check audit status and last run metadata."""
    proj = _srv()._require_project(project_id)

    # Check if running
    t = _audit_threads.get(proj.id)
    running = t is not None and t.is_alive()
    error = _audit_errors.get(proj.id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit import load_findings
    index_dir = project_index_dir(proj)

    result = load_findings(index_dir)

    data: Dict[str, Any] = {
        "running": running,
        "error": error,
        "has_results": result is not None,
    }

    if result and result.manifest:
        data["last_run"] = result.manifest.to_dict()
        data["finding_count"] = result.finding_count
        data["severity_counts"] = result.severity_counts

    return ok(data)


@router.get("/projects/{project_id}/audit/findings")
def get_audit_findings(
    project_id: str,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """Get raw structured audit findings."""
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit import load_findings
    index_dir = project_index_dir(proj)

    result = load_findings(index_dir)
    if not result:
        raise ApiException(
            status_code=404,
            code="NO_AUDIT_DATA",
            message="No audit has been run yet.",
            hint="Run POST /projects/{id}/audit first.",
        )

    findings = result.findings

    if severity:
        findings = [f for f in findings if f.severity == severity]
    if category:
        findings = [f for f in findings if f.category == category]

    findings = findings[:limit]

    return ok({
        "finding_count": len(findings),
        "total_finding_count": result.finding_count,
        "severity_counts": result.severity_counts,
        "findings": [f.to_dict() for f in findings],
    })


@router.get("/projects/{project_id}/audit/spaghetti")
def get_spaghetti_scores(
    project_id: str,
    tab: Optional[str] = Query(None, description="Sort tab: worst, long, coupling, debt"),
    limit: int = Query(50, ge=1, le=500),
    refresh: bool = Query(False, description="Force re-score instead of using cached results"),
) -> Dict[str, Any]:
    """Get per-file refactor urgency scores (Spaghetti Finder).

    Each file is scored 0.0-1.0 combining static signals (line count,
    coupling, symbol density) with LLM-derived signals (tech debt,
    epistemic confidence). Only files above the info threshold (0.30)
    are returned.

    Tabs control sort order:
      - worst (default): composite score descending
      - long: estimated line count descending
      - coupling: fan_in + fan_out descending
      - debt: tech_debt_count descending, then low confidence
    """
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit import load_spaghetti, run_spaghetti_scan, save_spaghetti
    index_dir = project_index_dir(proj)

    result = None
    if not refresh:
        result = load_spaghetti(index_dir)

    if result is None:
        result = run_spaghetti_scan(index_dir, Path(proj.path))
        try:
            save_spaghetti(result, index_dir)
        except Exception as e:
            logger.warning("Failed to save spaghetti scores: %s", e)

    files = list(result.files)

    # Apply tab-specific sorting
    if tab == "long":
        files.sort(key=lambda f: -f.estimated_lines)
    elif tab == "coupling":
        files.sort(key=lambda f: -(f.fan_in + f.fan_out))
    elif tab == "debt":
        files.sort(key=lambda f: (-f.tech_debt_count, f.epistemic_confidence))
    # else: default "worst" — already sorted by composite score

    files = files[:limit]

    return ok({
        "file_count": result.file_count,
        "scored_count": result.scored_count,
        "severity_counts": result.severity_counts,
        "duration_ms": round(result.duration_ms, 1),
        "tab": tab or "worst",
        "files": [f.to_dict() for f in files],
    })


@router.get("/projects/{project_id}/audit/reports")
def list_audit_reports(project_id: str) -> Dict[str, Any]:
    """List generated audit report documents."""
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir
    index_dir = project_index_dir(proj)
    audit_dir = index_dir / "audit"

    if not audit_dir.exists():
        return ok({"reports": []})

    reports = []
    for p in sorted(audit_dir.iterdir()):
        if p.suffix == ".md":
            reports.append({
                "name": p.stem,
                "filename": p.name,
                "size_bytes": p.stat().st_size,
            })

    return ok({"reports": reports})


@router.get("/projects/{project_id}/audit/report/{report_name}")
def get_audit_report(project_id: str, report_name: str) -> Dict[str, Any]:
    """Read a specific audit report document."""
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir
    index_dir = project_index_dir(proj)

    # Sanitize name
    safe_name = report_name.replace("/", "").replace("\\", "").replace("..", "")
    report_path = index_dir / "audit" / f"{safe_name}.md"

    if not report_path.exists():
        raise ApiException(
            status_code=404,
            code="REPORT_NOT_FOUND",
            message=f"Report '{report_name}' not found.",
            hint="Use GET /audit/reports to list available reports.",
        )

    content = report_path.read_text(encoding="utf-8")

    return ok({
        "name": safe_name,
        "content": content,
        "size_bytes": len(content.encode("utf-8")),
    })
