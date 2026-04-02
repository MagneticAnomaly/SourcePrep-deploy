"""Agent Operations API — HR, Researcher, Custodian endpoints.

Provides REST endpoints for all three CoDRAG agent engines.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents"])


def _get_engine_context(project_id: str):
    """Resolve project and return (index_dir, project_root, project_id)."""
    from codrag.services.project_helpers import require_project
    from codrag.core.project_registry import project_index_dir

    proj = require_project(project_id)
    idx_dir = project_index_dir(proj)
    project_root = Path(proj.path).expanduser().resolve()
    return idx_dir, project_root, proj.id


# ── Request Models ──────────────────────────────────────────

class HRGenerateRequest(BaseModel):
    mode: str = "list"  # list | auto | hybrid
    role_names: List[str] = []


class ResearchRunRequest(BaseModel):
    max_topics: int = 3


class CustodianRunRequest(BaseModel):
    dry_run: bool = True
    max_candidates: int = 50
    max_files: int = 20


# ── HR Endpoints ────────────────────────────────────────────

@router.get("/projects/{project_id}/agents/hr/readiness")
def hr_readiness(project_id: str) -> Dict[str, Any]:
    """Check codebase readiness for HR role generation."""
    idx_dir, _, pid = _get_engine_context(project_id)
    from codrag.agents.hr.engine import StaffingEngine
    engine = StaffingEngine(index_dir=idx_dir, project_id=pid)
    report = engine.check_readiness()
    return ok({
        "score": report.score,
        "ready_for_list": report.ready_for_list,
        "ready_for_auto": report.ready_for_auto,
        "dimensions": report.dimensions,
        "missing": report.missing,
    })


@router.get("/projects/{project_id}/agents/hr/roster")
def hr_roster(project_id: str) -> Dict[str, Any]:
    """List all generated roles in the roster."""
    idx_dir, _, pid = _get_engine_context(project_id)
    from codrag.agents.hr.roster import Roster
    roster = Roster(idx_dir)
    roles = []
    for slug in roster.list_roles():
        role = roster.get_role(slug)
        if role:
            roles.append({
                "slug": role.slug,
                "display_name": role.display_name,
                "has_agents_md": bool(role.agents_md),
                "has_soul_md": bool(role.soul_md),
                "has_knowledge_md": bool(role.knowledge_md),
            })
    return ok({"roles": roles})


@router.post("/projects/{project_id}/agents/hr/generate")
def hr_generate(project_id: str, req: HRGenerateRequest) -> Dict[str, Any]:
    """Generate agent role definitions.

    Requires a running LLM. Mode: 'list' (specify role_names),
    'auto' (LLM infers), or 'hybrid' (both).
    """
    idx_dir, _, pid = _get_engine_context(project_id)
    from codrag.agents.hr.engine import StaffingEngine
    engine = StaffingEngine(index_dir=idx_dir, project_id=pid)

    llm_fn = _get_llm_fn(pid)

    if req.mode == "list":
        if not req.role_names:
            raise ApiException(400, "MISSING_ROLES", "role_names required for list mode")
        roles = engine.generate_roles(req.role_names, llm_fn)
    elif req.mode == "auto":
        roles = engine.auto_generate_roles(llm_fn)
    elif req.mode == "hybrid":
        roles = engine.hybrid_generate_roles(req.role_names, llm_fn)
    else:
        raise ApiException(400, "INVALID_MODE", f"Unknown mode: {req.mode}")

    return ok({
        "roles_generated": len(roles),
        "slugs": [r.slug for r in roles],
    })


@router.post("/projects/{project_id}/agents/hr/audit")
def hr_audit(project_id: str) -> Dict[str, Any]:
    """Run drift detection on the current roster."""
    idx_dir, _, pid = _get_engine_context(project_id)
    from codrag.agents.hr.engine import StaffingEngine
    engine = StaffingEngine(index_dir=idx_dir, project_id=pid)
    report = engine.audit_roles()
    return ok({
        "role_fitness": [
            {"slug": rf.slug, "display_name": rf.display_name,
             "fitness_score": rf.fitness_score, "recommendation": rf.recommendation}
            for rf in report.role_fitness
        ],
        "coverage_gaps": report.coverage_gaps,
    })


# ── Researcher Endpoints ────────────────────────────────────

@router.post("/projects/{project_id}/agents/researcher/run")
def researcher_run(project_id: str, req: ResearchRunRequest) -> Dict[str, Any]:
    """Run the research pipeline: select topics, research, formulate plans."""
    idx_dir, _, pid = _get_engine_context(project_id)
    from codrag.agents.researcher.engine import ResearcherEngine
    engine = ResearcherEngine(index_dir=idx_dir, project_id=pid)

    findings = _get_audit_findings(idx_dir)
    llm_fn = _get_llm_fn(pid)

    plans = engine.run(findings, llm_fn, max_topics=req.max_topics)
    return ok({
        "plans": [p.to_dict() for p in plans],
        "count": len(plans),
    })


@router.get("/projects/{project_id}/agents/researcher/history")
def researcher_history(project_id: str) -> Dict[str, Any]:
    """Get research run history."""
    idx_dir, _, pid = _get_engine_context(project_id)
    from codrag.agents.researcher.history import ResearchHistory
    history = ResearchHistory(idx_dir)
    runs = history.list_runs()
    return ok({
        "runs": [
            {"run_id": r["run_id"], "timestamp": r["timestamp"],
             "topic_count": len(r.get("topics", [])),
             "plan_count": len(r.get("plans", []))}
            for r in runs
        ],
    })


# ── Custodian Endpoints ─────────────────────────────────────

@router.post("/projects/{project_id}/agents/custodian/run")
def custodian_run(project_id: str, req: CustodianRunRequest) -> Dict[str, Any]:
    """Run the custodian cleanup pipeline."""
    idx_dir, _, pid = _get_engine_context(project_id)
    from codrag.agents.custodian.engine import CustodianEngine
    engine = CustodianEngine(index_dir=idx_dir, project_id=pid)

    findings = _get_audit_findings(idx_dir)
    llm_fn = _get_llm_fn(pid)

    plan = engine.run(
        findings, llm_fn,
        dry_run=req.dry_run,
        max_candidates=req.max_candidates,
        max_files=req.max_files,
    )
    return ok({
        "dry_run": plan.dry_run,
        "branch_name": plan.branch_name,
        "candidate_count": len(plan.candidates),
        "candidates": [c.to_dict() for c in plan.candidates],
    })


@router.get("/projects/{project_id}/agents/custodian/manifest")
def custodian_manifest(project_id: str) -> Dict[str, Any]:
    """Get the archive manifest."""
    idx_dir, _, pid = _get_engine_context(project_id)
    from codrag.agents.custodian.manifest import ArchiveManifest
    manifest = ArchiveManifest(idx_dir)
    entries = manifest.list_entries()
    return ok({"entries": [e.to_dict() for e in entries]})


# ── Aggregate Status ────────────────────────────────────────

@router.get("/projects/{project_id}/agents/status")
def agents_status(project_id: str) -> Dict[str, Any]:
    """Get aggregate status for all three agents."""
    idx_dir, _, pid = _get_engine_context(project_id)

    from codrag.agents.hr.roster import Roster
    roster = Roster(idx_dir)
    hr_roles = roster.list_roles()

    from codrag.agents.researcher.history import ResearchHistory
    history = ResearchHistory(idx_dir)
    researcher_runs = history.list_runs()

    from codrag.agents.custodian.manifest import ArchiveManifest
    manifest = ArchiveManifest(idx_dir)
    custodian_entries = manifest.list_entries()

    return ok({
        "hr": {"role_count": len(hr_roles), "roles": hr_roles},
        "researcher": {
            "run_count": len(researcher_runs),
            "latest_run": researcher_runs[-1]["timestamp"] if researcher_runs else None,
        },
        "custodian": {"archive_count": len(custodian_entries)},
    })


# ── Helpers ─────────────────────────────────────────────────

def _get_audit_findings(idx_dir: Path) -> list:
    """Load audit findings from the opportunity manager."""
    try:
        from codrag.core.audit.opportunity_manager import OpportunityManager
        opp = OpportunityManager(idx_dir)
        items = opp.get_opportunities(include_dismissed=False)
        return [item.to_export_json() for item in items]
    except Exception as exc:
        logger.warning("Failed to load audit findings: %s", exc)
        return []


def _get_llm_fn(project_id: str):
    """Get an LLM function from pipeline config settings."""
    from codrag.services.settings_store import settings

    config = settings.get("pipeline_config") or {}
    model = config.get("model_thinking", "")
    if not model:
        raise ApiException(
            400, "NO_LLM_CONFIGURED",
            "No LLM model configured. Set up a model in the AI Gateway first.",
            hint="Configure a model via the dashboard AI Gateway panel or settings.",
        )

    provider = config.get("llm_provider", "ollama")
    endpoint_url = config.get("ollama_url", "http://localhost:11434")
    api_key = config.get("anthropic_api_key") or config.get("openai_api_key")

    if provider == "anthropic":
        endpoint_url = "https://api.anthropic.com"
    elif provider == "openai":
        endpoint_url = config.get("openai_url", "https://api.openai.com")

    from codrag.core.llm_client import LLMClient
    client = LLMClient(
        endpoint_url=endpoint_url,
        model=model,
        provider=provider,
        api_key=api_key,
        timeout=120.0,
    )

    def llm_fn(prompt: str, system: str | None = None, **kwargs):
        return client.generate(prompt, system=system, **kwargs)

    return llm_fn
