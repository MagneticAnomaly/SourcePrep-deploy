"""
Prep Opportunities Router — Phase 63
========================================

REST endpoints for the Opportunity Console.

Endpoints:
  POST /projects/{id}/opportunities/refresh     — Run full scan and merge
  GET  /projects/{id}/opportunities              — Query opportunities (filtered)
  GET  /projects/{id}/opportunities/summary      — Aggregate stats
  POST /projects/{id}/opportunities/{item_id}/dismiss  — Dismiss an opportunity
  POST /projects/{id}/opportunities/{item_id}/restore  — Restore a dismissed item
  GET  /projects/{id}/opportunities/export       — Export in various formats

A2A Protocol:
  GET  /.well-known/agent.json                   — Agent Card discovery
  POST /a2a                                       — JSON-RPC 2.0 task handler
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from prep.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["opportunities"])


def _srv():
    import prep.server as _s
    return _s


# ── Request models ──────────────────────────────────────────────────

class RefreshRequest(BaseModel):
    categories: Optional[List[str]] = None


# ── Opportunity endpoints ───────────────────────────────────────────

@router.post("/projects/{project_id}/opportunities/refresh")
def refresh_opportunities(
    project_id: str,
    req: Optional[RefreshRequest] = None,
) -> Dict[str, Any]:
    """Run all scanners and merge results into the opportunity list.

    This triggers Health Scanner (11 analyzers) + Spaghetti Scorer
    and merges results with existing opportunities. Dismissed items
    stay dismissed.
    """
    from prep.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit.opportunity_manager import OpportunityManager

    index_dir = project_index_dir(proj)
    mgr = OpportunityManager(index_dir)

    # Phase 65: Load user Exclude Tree patterns so the health scanner
    # respects the same exclusions as the trace pipeline.
    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    trace_ignore = (trace_cfg or {}).get("ignore_patterns", [])
    extra_excludes = [str(p) for p in trace_ignore] if isinstance(trace_ignore, list) else []
    # Also merge project-level exclude_globs (from project settings)
    project_excludes = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    if isinstance(project_excludes, list):
        extra_excludes.extend(str(g) for g in project_excludes if g)

    categories = req.categories if req else None
    items = mgr.refresh(
        project_root=Path(proj.path),
        categories=categories,
        extra_exclude_globs=extra_excludes or None,
    )

    return ok({
        "item_count": len(items),
        "summary": mgr.get_summary(),
        "items": [item.to_dict() for item in items],
    })


@router.get("/projects/{project_id}/opportunities")
def get_opportunities(
    project_id: str,
    category: Optional[str] = Query(None, description="Filter by category"),
    min_priority: Optional[str] = Query(None, description="Min priority (P0=highest)"),
    source: Optional[str] = Query(None, description="Filter by source"),
    include_dismissed: bool = Query(False, description="Include dismissed items"),
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    """Query opportunities with optional filters."""
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit.opportunity_manager import OpportunityManager

    index_dir = project_index_dir(proj)
    mgr = OpportunityManager(index_dir)

    items = mgr.get_opportunities(
        categories=[category] if category else None,
        min_priority=min_priority,
        sources=[source] if source else None,
        include_dismissed=include_dismissed,
    )

    items = items[:limit]

    return ok({
        "item_count": len(items),
        "items": [item.to_dict() for item in items],
    })


@router.get("/projects/{project_id}/opportunities/summary")
def opportunities_summary(project_id: str) -> Dict[str, Any]:
    """Return aggregate stats for the opportunity list."""
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit.opportunity_manager import OpportunityManager

    index_dir = project_index_dir(proj)
    mgr = OpportunityManager(index_dir)

    return ok(mgr.get_summary())


@router.post("/projects/{project_id}/opportunities/{item_id}/dismiss")
def dismiss_opportunity(project_id: str, item_id: str) -> Dict[str, Any]:
    """Dismiss an opportunity (hide from active list)."""
    from prep.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit.opportunity_manager import OpportunityManager

    index_dir = project_index_dir(proj)
    mgr = OpportunityManager(index_dir)

    found = mgr.dismiss(item_id)
    if not found:
        raise ApiException(
            status_code=404,
            code="ITEM_NOT_FOUND",
            message=f"Opportunity '{item_id}' not found.",
        )

    return ok({"dismissed": item_id})


@router.post("/projects/{project_id}/opportunities/{item_id}/restore")
def restore_opportunity(project_id: str, item_id: str) -> Dict[str, Any]:
    """Restore a dismissed opportunity."""
    from prep.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit.opportunity_manager import OpportunityManager

    index_dir = project_index_dir(proj)
    mgr = OpportunityManager(index_dir)

    found = mgr.restore(item_id)
    if not found:
        raise ApiException(
            status_code=404,
            code="ITEM_NOT_FOUND",
            message=f"Opportunity '{item_id}' not found.",
        )

    return ok({"restored": item_id})


@router.get("/projects/{project_id}/opportunities/export")
def export_opportunities(
    project_id: str,
    format: str = Query("json", description="Export format: json, sarif, csv, md, ai_prompt"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_priority: Optional[str] = Query(None, description="Min priority (P0=highest)"),
    source: Optional[str] = Query(None, description="Filter by source"),
) -> Response:
    """Export opportunities in various formats.

    Returns:
        json      → application/json
        sarif     → application/json (SARIF 2.1.0)
        csv       → text/csv
        md        → text/markdown
        ai_prompt → text/plain (paste-ready for AI agents)
    """
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit.opportunity_manager import OpportunityManager

    index_dir = project_index_dir(proj)
    mgr = OpportunityManager(index_dir)

    filters: Dict[str, Any] = {}
    if category:
        filters["categories"] = [category]
    if min_priority:
        filters["min_priority"] = min_priority
    if source:
        filters["sources"] = [source]

    content = mgr.export(format=format, **filters)

    media_types = {
        "json": "application/json",
        "sarif": "application/json",
        "csv": "text/csv",
        "md": "text/markdown",
        "markdown": "text/markdown",
        "ai_prompt": "text/plain",
    }
    media_type = media_types.get(format, "text/plain")

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="prep-opportunities.{format}"',
        },
    )


# ── Prep Address Resolution (Phase 65) ──────────────────────────

@router.get("/projects/{project_id}/opportunities/{item_id}/context")
def resolve_codrag_address(
    project_id: str,
    item_id: str,
) -> Dict[str, Any]:
    """Resolve a Prep address to live context.

    This is the endpoint Paperclip agents call when they pick up an
    issue with a prep:// address. Returns:
    - Current item status (still active? or resolved?)
    - Full item details with code context
    - Impact analysis (what files are affected, what depends on them)
    - Ready-to-use MCP command for deeper investigation

    This ensures agents work with FRESH context, not stale push-time data.
    """
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.audit.opportunity_manager import OpportunityManager

    index_dir = project_index_dir(proj)
    mgr = OpportunityManager(index_dir)

    # Search all items (including dismissed) to give accurate status
    all_items = mgr.get_opportunities(include_dismissed=True)
    target = None
    for item in all_items:
        if item.id == item_id:
            target = item
            break

    if target is None:
        # Item not found — may have been resolved
        return ok({
            "status": "resolved",
            "message": f"Item {item_id} is no longer in the findings list. It may have been fixed.",
            "prep_address": f"prep://{project_id}/{item_id}",
        })

    # Build rich context
    context: Dict[str, Any] = {
        "status": target.state,
        "prep_address": target.prep_address(project_id),
        "item": target.to_pm_export(project_id),
        "is_active": target.state != "dismissed",
    }

    # Try to get impact analysis for the primary affected file
    if target.affected_files:
        try:
            from prep.core.project_registry import load_project_graph
            graph = load_project_graph(proj)
            if graph:
                primary_file = target.affected_files[0]
                dependents = []
                dependencies = []
                for node_id, node_data in graph.get("nodes", {}).items():
                    if not isinstance(node_data, dict):
                        continue
                    label = node_data.get("label", "")
                    if label == primary_file or node_id == primary_file:
                        imports = node_data.get("imports", [])
                        dependencies = imports[:10]
                        break
                context["impact"] = {
                    "primary_file": primary_file,
                    "total_affected_files": len(target.affected_files),
                    "dependencies_sample": dependencies,
                }
        except Exception:
            pass  # Impact analysis is best-effort

    return ok(context)


# ── A2A Protocol endpoints ─────────────────────────────────────────

@router.get("/.well-known/agent.json")
def agent_card() -> Dict[str, Any]:
    """Serve the A2A Agent Card for protocol discovery.

    Any A2A-compliant orchestrator (Paperclip, CrewAI, etc.) can
    discover Prep's capabilities by fetching this endpoint.
    """
    from prep.a2a.handler import load_agent_card
    return load_agent_card()


@router.post("/a2a")
def a2a_handler(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle A2A JSON-RPC 2.0 task requests.

    Supports:
        tasks/send   — Create and execute a task
        tasks/get    — Get task status
        tasks/cancel — Cancel a running task
    """
    from prep.a2a.handler import A2AHandler
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import get_registry

    def _get_index_dir(project_id: Optional[str]) -> Path:
        reg = get_registry()
        if project_id:
            proj = reg.get(project_id)
            if proj:
                return project_index_dir(proj)
        # Default to first project
        projects = reg.list_projects()
        if projects:
            return project_index_dir(projects[0])
        raise ValueError("No projects registered")

    def _get_project_root(project_id: Optional[str]) -> Optional[Path]:
        reg = get_registry()
        if project_id:
            proj = reg.get(project_id)
            if proj:
                return Path(proj.path)
        projects = reg.list_projects()
        if projects:
            return Path(projects[0].path)
        return None

    handler = A2AHandler(
        get_index_dir=_get_index_dir,
        get_project_root=_get_project_root,
    )
    return handler.handle(request)
