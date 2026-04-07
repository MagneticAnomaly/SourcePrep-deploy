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


def _make_core(pid: str, idx_dir: Path, project_root: Path):
    """Create an AgentCore with collaboration hub if available."""
    from codrag.agents.core import AgentCore
    from codrag.services.collaboration import get_collaboration_hub
    return AgentCore(
        project_id=pid, index_dir=idx_dir,
        project_root=project_root,
        collab_hub=get_collaboration_hub(),
    )


# ── Request Models ──────────────────────────────────────────

class HRGenerateRequest(BaseModel):
    mode: str = "list"  # list | auto | hybrid
    role_names: List[str] = []
    push: bool = False


class ResearchRunRequest(BaseModel):
    max_topics: int = 3
    push: bool = False


class CustodianRunRequest(BaseModel):
    dry_run: bool = True
    max_candidates: int = 50
    max_files: int = 20
    push: bool = False


# ── HR Endpoints ────────────────────────────────────────────

@router.get("/projects/{project_id}/agents/hr/readiness")
def hr_readiness(project_id: str) -> Dict[str, Any]:
    """Check codebase readiness for HR role generation."""
    idx_dir, project_root, pid = _get_engine_context(project_id)

    core = _make_core(pid, idx_dir, project_root)

    from codrag.agents.hr.engine import StaffingEngine
    engine = StaffingEngine(core=core)
    report = engine.check_readiness()
    logger.info("[HR API] Readiness: score=%.2f, list=%s, auto=%s", report.score, report.ready_for_list, report.ready_for_auto)
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

    Files are written to ``.agents/<slug>/AGENTS.md``, ``SOUL.md``, ``KNOWLEDGE.md``.
    If files already exist, previous content is passed to the LLM so user edits
    are preserved and expanded upon (edit-aware regeneration).
    """
    idx_dir, project_root, pid = _get_engine_context(project_id)
    logger.info("[HR API] Generate request: mode=%s, role_names=%s, project=%s", req.mode, req.role_names, pid)

    core = _make_core(pid, idx_dir, project_root)

    from codrag.agents.hr.engine import StaffingEngine
    engine = StaffingEngine(core=core)

    llm_fn = _get_llm_fn(pid)
    logger.info("[HR API] LLM function resolved, starting generation ...")

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

    # Collect written file paths
    file_paths: Dict[str, List[str]] = {}
    for role in roles:
        role_dir = engine._agents_dir() / role.slug
        written = []
        for fn in ("AGENTS.md", "SOUL.md", "KNOWLEDGE.md"):
            fp = role_dir / fn
            if fp.exists():
                written.append(str(fp))
        file_paths[role.slug] = written

    logger.info("[HR API] Generation complete: %d role(s), files written to %s", len(roles), engine._agents_dir())

    push_count = 0
    if req.push:
        try:
            engine_fresh = StaffingEngine(core=core)
            engine_fresh.push_to_paperclip(llm_fn)
            push_count = len(roles)
        except Exception as e:
            logger.warning("[HR API] Push to Paperclip failed: %s", e)

    return ok({
        "roles_generated": len(roles),
        "slugs": [r.slug for r in roles],
        "files": file_paths,
        "agents_dir": str(engine._agents_dir()),
        "push_count": push_count,
    })


@router.post("/projects/{project_id}/agents/hr/sync")
def hr_sync(project_id: str) -> Dict[str, Any]:
    """Sync generated roles to Paperclip as managed agents.

    Requires Paperclip to be configured in settings (paperclip_url, company_id, api_key).
    """
    idx_dir, project_root, pid = _get_engine_context(project_id)

    # Build AgentCore with Paperclip config
    from codrag.services.settings_store import settings
    pm_raw = settings.get("pm_push") or {}
    if not pm_raw.get("enabled"):
        raise ApiException(
            400, "PAPERCLIP_NOT_CONFIGURED",
            "Paperclip push is not enabled.",
            hint=(
                "Via CLI: codrag config pm_push.enabled true && "
                "codrag config pm_push.paperclip_url http://localhost:3100 && "
                "codrag config pm_push.paperclip_company_id <your-company-id>. "
                "Or configure in the dashboard Settings panel."
            ),
        )

    from codrag.adapters.pm_models import PMPushConfig
    pm_config = PMPushConfig(**pm_raw)

    from codrag.agents.core import AgentCore
    from codrag.services.collaboration import get_collaboration_hub
    core = AgentCore(
        project_id=pid,
        index_dir=idx_dir,
        project_root=project_root,
        pm_config=pm_config,
        collab_hub=get_collaboration_hub(),
    )

    from codrag.agents.hr.engine import StaffingEngine
    engine = StaffingEngine(core=core)
    synced = engine.push_to_paperclip()
    return ok({"synced": synced, "count": len(synced)})


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
    idx_dir, project_root, pid = _get_engine_context(project_id)

    core = _make_core(pid, idx_dir, project_root)

    from codrag.agents.researcher.engine import ResearcherEngine
    engine = ResearcherEngine(core=core)

    findings = _get_audit_findings(idx_dir)
    llm_fn = _get_llm_fn(pid)

    plans = engine.run(findings, llm_fn, max_topics=req.max_topics)
    return ok({
        "plans": [p.to_dict() for p in plans],
        "count": len(plans),
        "push_requested": req.push,
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
    idx_dir, project_root, pid = _get_engine_context(project_id)

    core = _make_core(pid, idx_dir, project_root)

    from codrag.agents.custodian.engine import CustodianEngine
    engine = CustodianEngine(core=core)

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
        "push_requested": req.push,
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


# ── Researcher Push ─────────────────────────────────────────

@router.post("/projects/{project_id}/agents/researcher/push")
def researcher_push(project_id: str) -> Dict[str, Any]:
    """Push latest research plans to Paperclip as projects/issues."""
    idx_dir, project_root, pid = _get_engine_context(project_id)

    from codrag.services.settings_store import settings
    pm_raw = settings.get("pm_push") or {}
    if not pm_raw.get("enabled"):
        raise ApiException(
            400, "PAPERCLIP_NOT_CONFIGURED",
            "Paperclip push is not enabled.",
            hint=(
                "Via CLI: codrag config pm_push.enabled true && "
                "codrag config pm_push.paperclip_url http://localhost:3100 && "
                "codrag config pm_push.paperclip_company_id <your-company-id>. "
                "Or configure in the dashboard Settings panel."
            ),
        )

    from codrag.adapters.pm_models import PMPushConfig
    pm_config = PMPushConfig(**pm_raw)

    from codrag.agents.core import AgentCore
    from codrag.services.collaboration import get_collaboration_hub
    core = AgentCore(
        project_id=pid, index_dir=idx_dir,
        project_root=project_root, pm_config=pm_config,
        collab_hub=get_collaboration_hub(),
    )

    from codrag.agents.researcher.engine import ResearcherEngine
    engine = ResearcherEngine(core=core)

    # Get latest research run
    runs = engine.history.list_runs()
    if not runs:
        raise ApiException(400, "NO_RESEARCH_RUNS", "No research runs found. Run the researcher first.")

    latest = runs[-1]
    plans = []
    from codrag.agents.shared.models import ResearchPlan
    for p in latest.get("plans", []):
        plans.append(ResearchPlan.from_dict(p))

    if not plans:
        return ok({"pushed": False, "reason": "No plans in latest run"})

    project, goals, issues = engine.package_for_push(plans)
    project_id_pc = core.push_project(project)
    pushed_issues = []
    for issue in issues:
        issue.project_id = project_id_pc
        issue_id = core.push_issue(issue)
        pushed_issues.append({"title": issue.title, "id": issue_id})

    return ok({
        "pushed": True,
        "project_id": project_id_pc,
        "issues_pushed": len(pushed_issues),
        "issues": pushed_issues,
    })


# ── Custodian Push ──────────────────────────────────────────

@router.post("/projects/{project_id}/agents/custodian/push")
def custodian_push(project_id: str) -> Dict[str, Any]:
    """Push latest cleanup plan to Paperclip as a project with issues."""
    idx_dir, project_root, pid = _get_engine_context(project_id)

    from codrag.services.settings_store import settings
    pm_raw = settings.get("pm_push") or {}
    if not pm_raw.get("enabled"):
        raise ApiException(
            400, "PAPERCLIP_NOT_CONFIGURED",
            "Paperclip push is not enabled.",
            hint=(
                "Via CLI: codrag config pm_push.enabled true && "
                "codrag config pm_push.paperclip_url http://localhost:3100 && "
                "codrag config pm_push.paperclip_company_id <your-company-id>. "
                "Or configure in the dashboard Settings panel."
            ),
        )

    from codrag.adapters.pm_models import PMPushConfig
    pm_config = PMPushConfig(**pm_raw)

    from codrag.agents.core import AgentCore
    from codrag.services.collaboration import get_collaboration_hub
    core = AgentCore(
        project_id=pid, index_dir=idx_dir,
        project_root=project_root, pm_config=pm_config,
        collab_hub=get_collaboration_hub(),
    )

    from codrag.agents.custodian.engine import CustodianEngine
    engine = CustodianEngine(core=core)

    # Run a dry-run to get the current plan
    findings = _get_audit_findings(idx_dir)
    llm_fn = _get_llm_fn(pid)
    plan = engine.run(findings, llm_fn, dry_run=True)

    if not plan.candidates:
        return ok({"pushed": False, "reason": "No cleanup candidates found"})

    project, goals, issues = engine.package_for_push(plan)
    project_id_pc = core.push_project(project)
    pushed_issues = []
    for issue in issues:
        issue.project_id = project_id_pc
        issue_id = core.push_issue(issue)
        pushed_issues.append({"title": issue.title, "id": issue_id})

    return ok({
        "pushed": True,
        "project_id": project_id_pc,
        "issues_pushed": len(pushed_issues),
        "issues": pushed_issues,
    })


# ── Paperclip Discovery ─────────────────────────────────────

class DiscoveryProbeRequest(BaseModel):
    url: str = "http://localhost:3100"


@router.get("/agents/discovery")
def agents_discovery() -> Dict[str, Any]:
    """Discover Paperclip connection status.

    Reads pm_push config and probes the configured Paperclip URL.
    Returns connection status, company info, and agent count.
    """
    from codrag.services.settings_store import settings
    pm_raw = settings.get("pm_push") or {}

    if not pm_raw.get("enabled"):
        return ok({
            "connected": False,
            "configured": False,
            "url": "",
            "reason": "Paperclip push is not enabled in settings.",
        })

    from codrag.adapters.pm_models import PMPushConfig
    if isinstance(pm_raw, dict):
        pm_config = PMPushConfig.from_dict(pm_raw) if "paperclip" in pm_raw else PMPushConfig(**pm_raw)
    else:
        pm_config = PMPushConfig()

    return ok(_probe_paperclip(pm_config.paperclip_url, pm_config.paperclip_company_id))


@router.post("/agents/discovery/probe")
def agents_discovery_probe(req: DiscoveryProbeRequest) -> Dict[str, Any]:
    """Actively probe a specific Paperclip URL for connectivity."""
    return ok(_probe_paperclip(req.url))


def _probe_paperclip(url: str, company_id: str = "") -> Dict[str, Any]:
    """Probe a Paperclip instance and return connection details."""
    import urllib.request
    import urllib.error
    import json as _json

    result: Dict[str, Any] = {
        "connected": False,
        "configured": True,
        "url": url,
        "company_id": company_id,
        "company_name": "",
        "agent_count": 0,
        "plugin_detected": False,
        "version": "",
    }

    # Step 1: Health check
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/api/health",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
            result["connected"] = body.get("status") == "ok"
            result["version"] = body.get("version", "")
    except (urllib.error.URLError, urllib.error.HTTPError, Exception) as exc:
        result["reason"] = f"Cannot reach Paperclip at {url}: {exc}"
        return result

    # Step 2: Company info (if company_id is known)
    if company_id:
        try:
            req = urllib.request.Request(
                f"{url.rstrip('/')}/api/companies/{company_id}",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                company = _json.loads(resp.read().decode("utf-8"))
                result["company_name"] = company.get("name", "")
        except Exception:
            pass

        # Step 3: Agent count
        try:
            req = urllib.request.Request(
                f"{url.rstrip('/')}/api/companies/{company_id}/agents",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                agents = _json.loads(resp.read().decode("utf-8"))
                if isinstance(agents, list):
                    result["agent_count"] = len(agents)
                elif isinstance(agents, dict):
                    result["agent_count"] = len(agents.get("agents", agents.get("data", [])))
        except Exception:
            pass

        # Step 4: Check for CoDRAG plugin
        try:
            req = urllib.request.Request(
                f"{url.rstrip('/')}/api/companies/{company_id}/plugins",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                plugins = _json.loads(resp.read().decode("utf-8"))
                plugin_list = plugins if isinstance(plugins, list) else plugins.get("plugins", [])
                for p in plugin_list:
                    if "codrag" in str(p.get("name", "")).lower() or "codrag" in str(p.get("id", "")).lower():
                        result["plugin_detected"] = True
                        break
        except Exception:
            pass

    return result


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
    """Get an LLM function for agent generation.

    Uses the server's unified task resolver. Falls back to the large model
    (model_thinking) since agent generation needs good prose quality.
    """
    from codrag.server import _get_llm_client_for_task

    # Try agent-specific task first, fall back to large model slot
    client = _get_llm_client_for_task("agent")
    if client is None:
        client = _get_llm_client_for_task("enrichment")  # maps to large slot
    if client is None:
        # Last resort: direct pipeline_config lookup (backward compat)
        from codrag.services.settings_store import settings

        config = settings.get("pipeline_config") or {}
        model = config.get("model_thinking", "")
        if not model:
            raise ApiException(
                400, "NO_LLM_CONFIGURED",
                "No LLM model configured. Agent operations require an LLM.",
                hint=(
                    "Via CLI: codrag config pipeline_config.model_thinking <model> && "
                    "codrag config pipeline_config.llm_provider <ollama|anthropic|openai>. "
                    "Or use the dashboard AI Gateway panel."
                ),
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

    logger.info("[Agent LLM] Using model=%s, provider=%s", client.model, client.provider)

    def llm_fn(prompt: str, system: str | None = None, **kwargs):
        # Allow callers to override these defaults
        j_mode = kwargs.pop("json_mode", False)
        temp = kwargs.pop("temperature", 0.3)
        n_pred = kwargs.pop("num_predict", 4096)
        return client.generate(
            prompt,
            system=system,
            json_mode=j_mode,
            temperature=temp,
            num_predict=n_pred,
            **kwargs
        )

    return llm_fn
