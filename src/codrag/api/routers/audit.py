"""
CoDRAG Audit Router — Phase 43
================================

REST endpoints for the AutoAudit system.

Endpoints:
  POST /projects/{id}/audit          — Trigger a full audit (Tier 1 + optional Tier 2)
  GET  /projects/{id}/audit/status   — Check audit status / last run metadata
  GET  /projects/{id}/audit/findings — Get raw structured findings
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

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["audit"])


def _srv():
    import codrag.server as _s
    return _s


class AuditRequest(BaseModel):
    synthesize: bool = False
    categories: Optional[List[str]] = None


# Track running audits per project
_audit_threads: Dict[str, threading.Thread] = {}
_audit_errors: Dict[str, str] = {}


@router.post("/projects/{project_id}/audit")
def trigger_audit(project_id: str, req: Optional[AuditRequest] = None) -> Dict[str, Any]:
    """Trigger a codebase audit for a project.

    Tier 1 (analyzers) always runs. Set ``synthesize=true`` to also
    generate LLM-based report documents (Tier 2).
    """
    from codrag.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    # Check if already running
    t = _audit_threads.get(proj.id)
    if t is not None and t.is_alive():
        return ok({"status": "already_running", "message": "An audit is already in progress."})

    # Clear previous errors
    _audit_errors.pop(proj.id, None)

    synthesize = req.synthesize if req else False
    categories = req.categories if req else None

    from codrag.core.project_registry import project_index_dir
    index_dir = project_index_dir(proj)

    def _run():
        try:
            from codrag.core.audit import run_audit, save_findings, save_documents
            from codrag.core.audit.context import load_audit_context
            from codrag.core.audit.synthesizer import AuditSynthesizer

            result = run_audit(
                index_dir=index_dir,
                project_root=Path(proj.path),
                categories=categories,
            )
            save_findings(result, index_dir)

            if synthesize and result.findings:
                from codrag.server import _get_llm_client_for_task
                llm_client = _get_llm_client_for_task("audit")
                if llm_client:
                    ctx = load_audit_context(index_dir, Path(proj.path))
                    synth = AuditSynthesizer(
                        llm_client=llm_client,
                        project_name=proj.name or proj.id,
                    )
                    docs = synth.synthesize_all(result, ctx)
                    save_documents(docs, index_dir)
                    result.documents = docs

                    # Update manifest with document info
                    if result.manifest:
                        result.manifest.documents = [d.name for d in docs]
                        result.manifest.document_count = len(docs)
                        save_findings(result, index_dir)
                else:
                    logger.info("No LLM configured — skipping Tier 2 synthesis")

            logger.info("Audit complete for %s: %d findings", proj.id, result.finding_count)
        except Exception as e:
            logger.error("Audit failed for %s: %s", proj.id, e)
            _audit_errors[proj.id] = str(e)

    thread = threading.Thread(target=_run, daemon=True, name=f"audit-{proj.id}")
    _audit_threads[proj.id] = thread
    thread.start()

    return ok({
        "status": "started",
        "synthesize": synthesize,
        "message": "Audit started. Use GET /audit/status to check progress.",
    })


@router.get("/projects/{project_id}/audit/status")
def get_audit_status(project_id: str) -> Dict[str, Any]:
    """Check audit status and last run metadata."""
    proj = _srv()._require_project(project_id)

    # Check if running
    t = _audit_threads.get(proj.id)
    running = t is not None and t.is_alive()
    error = _audit_errors.get(proj.id)

    from codrag.core.project_registry import project_index_dir
    from codrag.core.audit import load_findings
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

    from codrag.core.project_registry import project_index_dir
    from codrag.core.audit import load_findings
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


@router.get("/projects/{project_id}/audit/reports")
def list_audit_reports(project_id: str) -> Dict[str, Any]:
    """List generated audit report documents."""
    proj = _srv()._require_project(project_id)

    from codrag.core.project_registry import project_index_dir
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

    from codrag.core.project_registry import project_index_dir
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
