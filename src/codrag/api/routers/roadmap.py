"""
CoDRAG Roadmap Router — Phase 59
====================================

REST endpoints for the visual roadmap timeline.

Endpoints:
  GET    /projects/{id}/roadmap                        — Get full roadmap state
  POST   /projects/{id}/roadmap/nodes                  — Create a manual node
  PATCH  /projects/{id}/roadmap/nodes/{nid}            — Update node tier/position/state
  DELETE /projects/{id}/roadmap/nodes/{nid}             — Delete a node
  POST   /projects/{id}/roadmap/generate               — Trigger LLM-based proposal generation
  PUT    /projects/{id}/roadmap/ethos                  — Save/update app ethos text
  POST   /projects/{id}/roadmap/reorder                — Batch reorder nodes within a tier
  POST   /projects/{id}/roadmap/scan-todos             — Trigger TODO/FIXME annotation scan
  POST   /projects/{id}/roadmap/questions/{qid}/answer — Answer a design question
  POST   /projects/{id}/roadmap/sync-github            — Import GitHub issues/projects (Phase 59D)
  GET    /projects/{id}/roadmap/github-status           — GitHub connection status (Phase 59D)
  POST   /projects/{id}/roadmap/mine                   — Mine pipeline data for contenders (Phase 59D)
  POST   /projects/{id}/roadmap/webhook                — Receive GitHub webhook events (Phase 59D-2)
  POST   /projects/{id}/roadmap/push-github            — Push nodes to GitHub as issues (Phase 59D-3)
  GET    /projects/{id}/roadmap/velocity               — Sprint velocity data (Phase 59D-4)
  POST   /projects/{id}/roadmap/suggest-sprint         — AI sprint suggestion (Phase 59D-4)
  POST   /projects/{id}/roadmap/nodes/{nid}/execute    — Execute node with LLM (Phase 59E)
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["roadmap"])


def _srv():
    import codrag.server as _s
    return _s


# ── Request models ───────────────────────────────────────────────────

class NodeCreate(BaseModel):
    title: str
    description: str = ""
    tier: str = "planned"          # completed | active | planned | proposed
    category: str = "feature"
    priority: str = "P2"
    ethos_alignment: str = ""
    business_impact: str = ""


class NodeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tier: Optional[str] = None
    position: Optional[int] = None
    state: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    ethos_alignment: Optional[str] = None
    business_impact: Optional[str] = None


class EthosUpdate(BaseModel):
    app_ethos: str


class TierReorder(BaseModel):
    tier: str
    node_ids: List[str]            # Ordered list of node IDs


class QuestionAnswer(BaseModel):
    answer: str


# ── Background thread tracking ──────────────────────────────────────────

_generate_threads: Dict[str, threading.Thread] = {}
_generate_errors: Dict[str, str] = {}
_scan_threads: Dict[str, threading.Thread] = {}
_scan_errors: Dict[str, str] = {}
_github_sync_threads: Dict[str, threading.Thread] = {}
_github_sync_errors: Dict[str, str] = {}
_mine_threads: Dict[str, threading.Thread] = {}
_mine_errors: Dict[str, str] = {}

# Per-project locks to prevent concurrent load/modify/save races.
# Without this, a background generate/mine thread can overwrite
# a user's promote/dismiss change.
_roadmap_locks: Dict[str, threading.Lock] = {}


def _get_roadmap_lock(project_id: str) -> threading.Lock:
    """Get or create a per-project lock for roadmap state access."""
    if project_id not in _roadmap_locks:
        _roadmap_locks[project_id] = threading.Lock()
    return _roadmap_locks[project_id]


# ── Helpers ──────────────────────────────────────────────────────────

def _get_roadmap_state(project_id: str):
    """Load roadmap state for a project, auto-migrating from goalposts if needed."""
    from codrag.core.project_registry import project_index_dir
    from codrag.core.goalposts_models import (
        load_roadmap,
        migrate_goalposts_to_roadmap,
        ROADMAP_FILENAME,
    )

    proj = _srv()._require_project(project_id)
    index_dir = project_index_dir(proj)

    # Auto-migrate if roadmap doesn't exist but goalposts does
    roadmap_path = Path(index_dir) / ROADMAP_FILENAME
    goalposts_path = Path(index_dir) / "goalposts.json"
    if not roadmap_path.exists() and goalposts_path.exists():
        return migrate_goalposts_to_roadmap(index_dir), index_dir, proj

    return load_roadmap(index_dir), index_dir, proj


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/roadmap")
def get_roadmap(project_id: str) -> Dict[str, Any]:
    """Get current roadmap state for a project."""
    state, index_dir, proj = _get_roadmap_state(project_id)

    # Check generation/scan status
    t = _generate_threads.get(proj.id)
    generating = t is not None and t.is_alive()
    s = _scan_threads.get(proj.id)
    scanning = s is not None and s.is_alive()

    # Also check github-sync and mining threads (Phase 59D)
    gh = _github_sync_threads.get(proj.id)
    mining = _mine_threads.get(proj.id)
    syncing_github = gh is not None and gh.is_alive()
    is_mining = mining is not None and mining.is_alive()

    gen_error = _generate_errors.get(proj.id)
    scan_error = _scan_errors.get(proj.id)
    gh_error = _github_sync_errors.get(proj.id)
    mine_error = _mine_errors.get(proj.id)

    # North star summary
    ns = state.north_star
    north_star = {
        "id": ns.id,
        "title": ns.title,
        "priority": ns.priority,
    } if ns else None

    return ok({
        "generating": generating or syncing_github or is_mining,
        "scanning": scanning,
        "error": gen_error or scan_error or gh_error or mine_error,
        "north_star": north_star,
        **state.to_dict(),
    })


@router.post("/projects/{project_id}/roadmap/nodes")
def create_node(project_id: str, req: NodeCreate) -> Dict[str, Any]:
    """Create a manually added roadmap node."""
    from codrag.services.project_helpers import require_project_writable
    from codrag.core.goalposts_models import RoadmapNode, load_roadmap, save_roadmap
    from codrag.core.project_registry import project_index_dir

    proj = require_project_writable(project_id)
    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)

    # Compute position (append to end of tier)
    tier_nodes = [n for n in state.nodes if n.tier == req.tier]
    position = max((n.position for n in tier_nodes), default=-1) + 1

    node = RoadmapNode(
        title=req.title,
        description=req.description,
        tier=req.tier,
        position=position,
        source="manual",
        category=req.category,
        priority=req.priority,
        state="accepted" if req.tier != "proposed" else "proposed",
        ethos_alignment=req.ethos_alignment,
        business_impact=req.business_impact,
    )

    state.nodes.append(node)
    save_roadmap(state, index_dir)

    return ok({"id": node.id, "tier": node.tier, "position": node.position})


@router.patch("/projects/{project_id}/roadmap/nodes/{node_id}")
def update_node(project_id: str, node_id: str, req: NodeUpdate) -> Dict[str, Any]:
    """Update a roadmap node's tier, position, state, or other fields."""
    from codrag.services.project_helpers import require_project_writable
    from codrag.core.goalposts_models import load_roadmap, save_roadmap
    from codrag.core.project_registry import project_index_dir

    proj = require_project_writable(project_id)
    index_dir = project_index_dir(proj)

    lock = _get_roadmap_lock(proj.id)
    with lock:
        state = load_roadmap(index_dir)

        node = state.node_by_id(node_id)
        if not node:
            raise ApiException(
                status_code=404,
                code="NODE_NOT_FOUND",
                message=f"Roadmap node '{node_id}' not found.",
            )

        old_tier = node.tier  # Capture before mutation

        # Apply updates (only non-None fields)
        if req.title is not None:
            node.title = req.title
        if req.description is not None:
            node.description = req.description
        if req.tier is not None:
            node.tier = req.tier
        if req.position is not None:
            node.position = req.position
        if req.state is not None:
            node.state = req.state
            if req.state == "completed":
                node.completed_at = datetime.now(timezone.utc).isoformat()
                node.tier = "completed"
            elif req.state in ("accepted", "active"):
                node.decided_at = datetime.now(timezone.utc).isoformat()
        if req.category is not None:
            node.category = req.category
        if req.priority is not None:
            node.priority = req.priority
        if req.ethos_alignment is not None:
            node.ethos_alignment = req.ethos_alignment
        if req.business_impact is not None:
            node.business_impact = req.business_impact

        save_roadmap(state, index_dir)

    # Bidirectional GitHub sync: push tier changes back to GitHub (Phase 59D-3)
    # (outside lock — fire-and-forget network call)
    if node.tier != old_tier and node.source_ref and "github.com" in (node.source_ref or ""):
        try:
            from codrag.core.github_sync import get_github_config
            from codrag.core.github_push import sync_tier_change_to_github
            gh_config = get_github_config(proj.config)
            if gh_config:
                threading.Thread(
                    target=sync_tier_change_to_github,
                    args=(node, gh_config["token"], gh_config["owner"], gh_config["repo"]),
                    daemon=True,
                    name=f"gh-sync-{node.id}",
                ).start()
        except Exception as e:
            logger.warning("GitHub tier sync skipped for %s: %s", node.id, e)

    return ok({"id": node_id, "tier": node.tier, "state": node.state})


@router.delete("/projects/{project_id}/roadmap/nodes/{node_id}")
def delete_node(project_id: str, node_id: str) -> Dict[str, Any]:
    """Delete a roadmap node."""
    from codrag.services.project_helpers import require_project_writable
    from codrag.core.goalposts_models import load_roadmap, save_roadmap
    from codrag.core.project_registry import project_index_dir

    proj = require_project_writable(project_id)
    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)

    original_len = len(state.nodes)
    state.nodes = [n for n in state.nodes if n.id != node_id]

    if len(state.nodes) == original_len:
        raise ApiException(
            status_code=404,
            code="NODE_NOT_FOUND",
            message=f"Roadmap node '{node_id}' not found.",
        )

    save_roadmap(state, index_dir)
    return ok({"deleted": node_id})


@router.post("/projects/{project_id}/roadmap/generate")
def trigger_generate(project_id: str) -> Dict[str, Any]:
    """Trigger LLM-based proposal generation into the proposed tier."""
    from codrag.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    t = _generate_threads.get(proj.id)
    if t is not None and t.is_alive():
        return ok({"status": "already_running", "message": "Generation is already in progress."})

    _generate_errors.pop(proj.id, None)

    from codrag.core.project_registry import project_index_dir
    index_dir = project_index_dir(proj)

    def _run():
        try:
            from codrag.server import _get_llm_client_for_task
            from codrag.core.goalposts_planner import GoalpostsPlanner
            from codrag.core.goalposts_models import load_roadmap, save_roadmap, RoadmapNode, RoadmapTask

            llm_client = _get_llm_client_for_task("audit")
            if not llm_client:
                _generate_errors[proj.id] = "No LLM configured for planning. Configure a large model in Settings."
                return

            # Lock to prevent overwriting user changes (e.g. promote)
            lock = _get_roadmap_lock(proj.id)

            # LLM call outside lock (slow operation)
            from codrag.core.goalposts_models import load_roadmap as _lr
            _pre_state = _lr(index_dir)
            planner = GoalpostsPlanner(
                index_dir=index_dir,
                llm_client=llm_client,
                project_root=Path(proj.path),
            )
            goalposts_state = planner.generate(product_intent=_pre_state.app_ethos)

            # Merge results under lock (fast operation)
            with lock:
                state = load_roadmap(index_dir)

                # Convert new proposals to RoadmapNodes
                existing_ids = {n.id for n in state.nodes}
                position = max((n.position for n in state.proposed_nodes), default=-1) + 1

                for p in goalposts_state.proposals:
                    if p.state != "proposed":
                        continue
                    # Extract P-4/P-5 fields stashed by enhanced planner
                    business_impact = getattr(p, '_business_impact', '')
                    ethos_alignment = getattr(p, '_ethos_alignment', '')
                    node = RoadmapNode(
                        title=p.title,
                        description=p.rationale,
                        tier="proposed",
                        position=position,
                        source="ai_proposed",
                        category=p.category,
                        priority=p.priority,
                        tasks=[
                            RoadmapTask(
                                description=t.description,
                                file_paths=t.file_paths,
                                effort=t.effort,
                            )
                            for t in p.tasks
                        ],
                        state="proposed",
                        business_impact=business_impact,
                        ethos_alignment=ethos_alignment,
                    )
                    if node.id not in existing_ids:
                        state.nodes.append(node)
                        existing_ids.add(node.id)
                        position += 1

                # Preserve questions
                state.questions.extend(goalposts_state.questions)
                state.last_generated_at = goalposts_state.last_generated_at
                state.model_used = goalposts_state.model_used
                state.generation_tokens = goalposts_state.generation_tokens
                state.generation_duration_ms = goalposts_state.generation_duration_ms

                save_roadmap(state, index_dir)
            logger.info("Roadmap proposals generated for %s", proj.id)

        except Exception as e:
            logger.error("Roadmap generation failed for %s: %s", proj.id, e)
            _generate_errors[proj.id] = str(e)

    thread = threading.Thread(target=_run, daemon=True, name=f"roadmap-gen-{proj.id}")
    _generate_threads[proj.id] = thread
    thread.start()

    return ok({"status": "started", "message": "Roadmap generation started. Poll GET /roadmap to check progress."})


@router.put("/projects/{project_id}/roadmap/ethos")
def update_ethos(project_id: str, req: EthosUpdate) -> Dict[str, Any]:
    """Save or update the app ethos text."""
    from codrag.services.project_helpers import require_project_writable
    from codrag.core.goalposts_models import load_roadmap, save_roadmap
    from codrag.core.project_registry import project_index_dir

    proj = require_project_writable(project_id)
    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)
    state.app_ethos = req.app_ethos.strip()
    save_roadmap(state, index_dir)

    return ok({"app_ethos": state.app_ethos})


@router.post("/projects/{project_id}/roadmap/reorder")
def reorder_nodes(project_id: str, req: TierReorder) -> Dict[str, Any]:
    """Batch reorder nodes within a tier."""
    from codrag.services.project_helpers import require_project_writable
    from codrag.core.goalposts_models import load_roadmap, save_roadmap
    from codrag.core.project_registry import project_index_dir

    proj = require_project_writable(project_id)
    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)

    # Build lookup
    id_to_node = {n.id: n for n in state.nodes}

    for position, node_id in enumerate(req.node_ids):
        node = id_to_node.get(node_id)
        if node:
            node.tier = req.tier
            node.position = position

    save_roadmap(state, index_dir)
    return ok({"tier": req.tier, "count": len(req.node_ids)})


@router.post("/projects/{project_id}/roadmap/scan-todos")
def trigger_scan_todos(project_id: str) -> Dict[str, Any]:
    """Trigger a TODO/FIXME/HACK scan of the codebase."""
    from codrag.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    s = _scan_threads.get(proj.id)
    if s is not None and s.is_alive():
        return ok({"status": "already_running", "message": "TODO scan is already in progress."})

    _scan_errors.pop(proj.id, None)

    from codrag.core.project_registry import project_index_dir
    index_dir = project_index_dir(proj)

    def _run():
        try:
            from codrag.core.todo_scanner import scan_todos
            from codrag.core.goalposts_models import load_roadmap, save_roadmap

            state = load_roadmap(index_dir)
            existing_ids = {n.id for n in state.nodes}

            new_nodes = scan_todos(
                Path(proj.path),
                existing_ids=existing_ids,
                max_results=50,
            )

            state.nodes.extend(new_nodes)
            save_roadmap(state, index_dir)
            logger.info("TODO scan complete for %s: %d new nodes", proj.id, len(new_nodes))

        except Exception as e:
            logger.error("TODO scan failed for %s: %s", proj.id, e)
            _scan_errors[proj.id] = str(e)

    thread = threading.Thread(target=_run, daemon=True, name=f"todo-scan-{proj.id}")
    _scan_threads[proj.id] = thread
    thread.start()

    return ok({"status": "started", "message": "TODO scan started. Poll GET /roadmap to check progress."})


@router.post("/projects/{project_id}/roadmap/questions/{question_id}/answer")
def answer_question(project_id: str, question_id: str, req: QuestionAnswer) -> Dict[str, Any]:
    """Submit an answer to a design question."""
    from codrag.services.project_helpers import require_project_writable
    from codrag.core.goalposts_models import load_roadmap, save_roadmap
    from codrag.core.project_registry import project_index_dir

    proj = require_project_writable(project_id)
    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)

    found = False
    for q in state.questions:
        if q.id == question_id:
            q.answer = req.answer.strip()
            q.answered = True
            found = True
            break

    if not found:
        raise ApiException(
            status_code=404,
            code="QUESTION_NOT_FOUND",
            message=f"Question '{question_id}' not found.",
        )

    save_roadmap(state, index_dir)
    return ok({"id": question_id, "answered": True})


# ── GitHub Sync (Phase 59D) ──────────────────────────────────────────


@router.post("/projects/{project_id}/roadmap/sync-github")
def trigger_sync_github(project_id: str) -> Dict[str, Any]:
    """Import issues/items from GitHub into the proposed tier."""
    from codrag.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    t = _github_sync_threads.get(proj.id)
    if t is not None and t.is_alive():
        return ok({"status": "already_running", "message": "GitHub sync is already in progress."})

    _github_sync_errors.pop(proj.id, None)

    # Check for GitHub config
    from codrag.core.github_sync import get_github_config
    gh_config = get_github_config(proj.config)
    if not gh_config:
        raise ApiException(
            status_code=400,
            code="GITHUB_NOT_CONFIGURED",
            message="GitHub is not configured. Add github_token, github_owner, and github_repo to project config.",
        )

    from codrag.core.project_registry import project_index_dir
    index_dir = project_index_dir(proj)

    def _run():
        try:
            from codrag.core.github_sync import GitHubClient, GitHubSyncState
            from codrag.core.goalposts_models import load_roadmap, save_roadmap
            from datetime import datetime, timezone

            client = GitHubClient(
                token=gh_config["token"],
                owner=gh_config["owner"],
                repo=gh_config["repo"],
            )

            state = load_roadmap(index_dir)
            existing_ids = {n.id for n in state.nodes}

            # Phase 1: Import issues
            new_nodes: List = []
            if gh_config["owner"] and gh_config["repo"]:
                issue_nodes = client.fetch_issues(
                    states=["OPEN"],
                    max_results=50,
                    existing_ids=existing_ids,
                )
                new_nodes.extend(issue_nodes)

            # Phase 2: Import ProjectV2 items (if configured)
            if gh_config.get("project_id"):
                project_nodes = client.fetch_project_items(
                    gh_config["project_id"],
                    max_results=50,
                    existing_ids=existing_ids | {n.id for n in new_nodes},
                )
                new_nodes.extend(project_nodes)

            # Assign positions within proposed tier
            proposed_max = max(
                (n.position for n in state.nodes if n.tier == "proposed"),
                default=-1,
            )
            for i, node in enumerate(new_nodes):
                if node.tier == "proposed":
                    node.position = proposed_max + 1 + i

            state.nodes.extend(new_nodes)

            # Update sync state
            state.github_sync = GitHubSyncState(
                last_synced_at=datetime.now(timezone.utc).isoformat(),
                issues_imported=len(new_nodes),
                owner=gh_config["owner"],
                repo=gh_config["repo"],
                project_id=gh_config.get("project_id", ""),
            ).to_dict()

            save_roadmap(state, index_dir)
            client.close()

            logger.info("GitHub sync complete for %s: %d new nodes", proj.id, len(new_nodes))

        except Exception as e:
            logger.error("GitHub sync failed for %s: %s", proj.id, e)
            _github_sync_errors[proj.id] = str(e)

    thread = threading.Thread(target=_run, daemon=True, name=f"github-sync-{proj.id}")
    _github_sync_threads[proj.id] = thread
    thread.start()

    return ok({"status": "started", "message": "GitHub sync started. Poll GET /roadmap to check progress."})


@router.get("/projects/{project_id}/roadmap/github-status")
def get_github_status(project_id: str) -> Dict[str, Any]:
    """Get GitHub sync connection status."""
    from codrag.core.github_sync import get_github_config
    from codrag.services.project_helpers import require_project_writable

    proj = require_project_writable(project_id)
    gh_config = get_github_config(proj.config)

    t = _github_sync_threads.get(proj.id)
    syncing = t is not None and t.is_alive()
    error = _github_sync_errors.get(proj.id)

    # Load last sync metadata from roadmap state
    from codrag.core.goalposts_models import load_roadmap
    from codrag.core.project_registry import project_index_dir
    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)

    return ok({
        "configured": gh_config is not None,
        "owner": gh_config.get("owner", "") if gh_config else "",
        "repo": gh_config.get("repo", "") if gh_config else "",
        "has_project_id": bool(gh_config.get("project_id")) if gh_config else False,
        "syncing": syncing,
        "error": error,
        "last_sync": state.github_sync,
    })


# ── Pipeline Mining (Phase 59D) ──────────────────────────────────────


@router.post("/projects/{project_id}/roadmap/mine")
def trigger_mine(project_id: str) -> Dict[str, Any]:
    """Mine CoDRAG pipeline data for roadmap contenders."""
    from codrag.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    t = _mine_threads.get(proj.id)
    if t is not None and t.is_alive():
        return ok({"status": "already_running", "message": "Mining is already in progress."})

    _mine_errors.pop(proj.id, None)

    from codrag.core.project_registry import project_index_dir
    index_dir = project_index_dir(proj)

    def _run():
        try:
            from codrag.core.roadmap_miner import mine_roadmap_contenders
            from codrag.core.goalposts_models import load_roadmap, save_roadmap

            # Mine outside lock (slow I/O operation)
            _pre_state = load_roadmap(index_dir)
            pre_ids = {n.id for n in _pre_state.nodes}

            new_nodes = mine_roadmap_contenders(
                index_dir=index_dir,
                project_root=Path(proj.path),
                existing_ids=pre_ids,
                max_results=30,
            )

            # Merge under lock (fast operation)
            lock = _get_roadmap_lock(proj.id)
            with lock:
                state = load_roadmap(index_dir)
                existing_ids = {n.id for n in state.nodes}

                # Filter out any nodes already added since pre-read
                new_nodes = [n for n in new_nodes if n.id not in existing_ids]

                # Assign positions
                proposed_max = max(
                    (n.position for n in state.nodes if n.tier == "proposed"),
                    default=-1,
                )
                for i, node in enumerate(new_nodes):
                    node.position = proposed_max + 1 + i

                state.nodes.extend(new_nodes)

                # Persist mining metadata (Track 5-3)
                state.last_mined_at = datetime.now(timezone.utc).isoformat()
                mining_counts: Dict[str, int] = {}
                for n in new_nodes:
                    ref = (n.source_ref or "").split(":")[0]  # "audit", "module", "file", etc.
                    mining_counts[ref] = mining_counts.get(ref, 0) + 1
                state.mining_stats = mining_counts

                save_roadmap(state, index_dir)

            logger.info("Roadmap mining complete for %s: %d new contenders", proj.id, len(new_nodes))

        except Exception as e:
            logger.error("Roadmap mining failed for %s: %s", proj.id, e)
            _mine_errors[proj.id] = str(e)

    thread = threading.Thread(target=_run, daemon=True, name=f"roadmap-mine-{proj.id}")
    _mine_threads[proj.id] = thread
    thread.start()

    return ok({"status": "started", "message": "Pipeline mining started. Poll GET /roadmap to check progress."})


# ── Webhook (Phase 59D-2) ────────────────────────────────────────────

class WebhookPayload(BaseModel):
    """Raw webhook payload (we pass through to handler)."""
    class Config:
        extra = "allow"


@router.post("/projects/{project_id}/roadmap/webhook")
async def receive_webhook(project_id: str, request: Request) -> Dict[str, Any]:
    """Receive GitHub webhook events and auto-promote/demote nodes.

    Reads event type and signature from HTTP headers (standard GitHub webhook
    delivery format), not from payload fields.

    Headers:
        X-GitHub-Event: event type (issues, pull_request, projects_v2_item, ping)
        X-Hub-Signature-256: HMAC-SHA256 signature (validated if webhook_secret configured)
    """
    from codrag.core.project_registry import project_index_dir
    from codrag.core.goalposts_models import load_roadmap, save_roadmap
    from codrag.core.github_webhook import process_webhook_event, verify_webhook_signature
    from codrag.core.github_sync import get_github_config

    proj = _srv()._require_project(project_id)
    index_dir = project_index_dir(proj)

    # Read headers
    event_type = request.headers.get("x-github-event", "ping")
    signature = request.headers.get("x-hub-signature-256", "")

    # Read raw body for signature verification
    body = await request.body()

    # Verify HMAC signature if webhook_secret is configured
    gh_config = get_github_config(proj.config)
    webhook_secret = gh_config.get("webhook_secret") if gh_config else None
    if webhook_secret and signature:
        if not verify_webhook_signature(body, signature, webhook_secret):
            raise ApiException(
                status_code=401,
                code="INVALID_SIGNATURE",
                message="Webhook signature verification failed.",
            )

    # Parse body as JSON
    import json as _json
    try:
        payload = _json.loads(body)
    except _json.JSONDecodeError:
        raise ApiException(
            status_code=400,
            code="INVALID_PAYLOAD",
            message="Could not parse webhook payload as JSON.",
        )

    state = load_roadmap(index_dir)
    result = process_webhook_event(event_type, payload, state)

    if result.action not in ("ignored", "pong"):
        save_roadmap(state, index_dir)
        logger.info(
            "Webhook %s for %s: %s node %s (%s → %s)",
            event_type, proj.id, result.action, result.node_id,
            result.old_tier, result.new_tier,
        )

    return ok(result.to_dict())


# ── Push to GitHub (Phase 59D-3) ─────────────────────────────────────

class PushRequest(BaseModel):
    node_ids: List[str]  # Which nodes to push to GitHub


@router.post("/projects/{project_id}/roadmap/push-github")
def push_to_github(project_id: str, req: PushRequest) -> Dict[str, Any]:
    """Push accepted roadmap nodes to GitHub as issues."""
    from codrag.services.project_helpers import require_project_writable
    from codrag.core.project_registry import project_index_dir
    from codrag.core.goalposts_models import load_roadmap, save_roadmap
    from codrag.core.github_sync import get_github_config
    from codrag.core.github_push import push_nodes_to_github

    proj = require_project_writable(project_id)
    gh_config = get_github_config(proj.config)

    if not gh_config:
        raise ApiException(
            status_code=400,
            code="GITHUB_NOT_CONFIGURED",
            message="GitHub is not configured for this project. Set github_token, github_owner, github_repo in project settings.",
        )

    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)

    # Find requested nodes
    nodes_to_push = [n for n in state.nodes if n.id in req.node_ids]
    if not nodes_to_push:
        raise ApiException(
            status_code=404,
            code="NODES_NOT_FOUND",
            message="No matching nodes found to push.",
        )

    results = push_nodes_to_github(
        nodes=nodes_to_push,
        token=gh_config["token"],
        owner=gh_config["owner"],
        repo=gh_config["repo"],
    )

    # Save updated source_refs
    save_roadmap(state, index_dir)

    return ok({
        "pushed": len([r for r in results if "error" not in r]),
        "errors": len([r for r in results if "error" in r]),
        "results": results,
    })


# ── Sprint Intelligence (Phase 59D-4) ───────────────────────────────

@router.get("/projects/{project_id}/roadmap/velocity")
def get_velocity(project_id: str) -> Dict[str, Any]:
    """Get sprint velocity data for the roadmap."""
    from codrag.core.project_registry import project_index_dir
    from codrag.core.goalposts_models import load_roadmap
    from codrag.core.sprint_intelligence import VelocityTracker

    proj = _srv()._require_project(project_id)
    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)

    tracker = VelocityTracker(state)
    snapshots = tracker.calculate_velocity(window_days=14, num_windows=6)
    avg = tracker.average_velocity(window_days=14, num_windows=4)
    burndown = tracker.burndown_data()

    return ok({
        "average_velocity": round(avg, 1),
        "snapshots": [s.to_dict() for s in snapshots],
        "burndown": burndown,
        "total_completed": len(state.completed_nodes),
        "total_active": len(state.active_nodes),
        "total_planned": len(state.planned_nodes),
        "total_proposed": len(state.proposed_nodes),
    })


@router.post("/projects/{project_id}/roadmap/suggest-sprint")
def suggest_sprint(project_id: str, use_ai: bool = True) -> Dict[str, Any]:
    """Get AI-powered sprint suggestion based on velocity and backlog.

    Args:
        use_ai: If True, use LLM-enhanced planning (falls back to heuristic).
                If False, always use heuristic-based planning.
    """
    from codrag.services.project_helpers import require_project_writable
    from codrag.core.project_registry import project_index_dir
    from codrag.core.goalposts_models import load_roadmap
    from codrag.core.sprint_intelligence import VelocityTracker, SprintPlanner

    proj = require_project_writable(project_id)
    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)

    if use_ai:
        try:
            from codrag.core.sprint_intelligence import generate_ai_sprint_plan
            import codrag.server as _s
            llm = _s._get_llm_client_for_task("goalposts")
            if llm is None:
                raise RuntimeError("No LLM configured for goalposts task")
            suggestion = generate_ai_sprint_plan(state, llm, window_days=14)
        except Exception as e:
            logger.warning("AI sprint planning unavailable, using heuristic: %s", e)
            tracker = VelocityTracker(state)
            planner = SprintPlanner(state, tracker)
            suggestion = planner.suggest_sprint(window_days=14)
    else:
        tracker = VelocityTracker(state)
        planner = SprintPlanner(state, tracker)
        suggestion = planner.suggest_sprint(window_days=14)

    # Resolve node details for the suggestion
    node_details = []
    for nid in suggestion.suggested_nodes:
        node = state.node_by_id(nid)
        if node:
            node_details.append({
                "id": node.id,
                "title": node.title,
                "priority": node.priority,
                "category": node.category,
                "tier": node.tier,
            })

    return ok({
        **suggestion.to_dict(),
        "node_details": node_details,
    })


# ── Node LLM Execution (Phase 59E) ──────────────────────────────────

@router.post("/projects/{project_id}/roadmap/nodes/{node_id}/execute")
def execute_node(project_id: str, node_id: str) -> Dict[str, Any]:
    """Execute a roadmap node with the project's configured LLM.

    Generates implementation guidance, action steps, and code-level
    suggestions for the given node.
    """
    from codrag.services.project_helpers import require_project_writable
    from codrag.core.goalposts_models import load_roadmap
    from codrag.core.project_registry import project_index_dir

    proj = require_project_writable(project_id)
    index_dir = project_index_dir(proj)
    state = load_roadmap(index_dir)

    node = state.node_by_id(node_id)
    if not node:
        raise ApiException(
            status_code=404,
            code="NODE_NOT_FOUND",
            message=f"Roadmap node '{node_id}' not found.",
        )

    import codrag.server as _s
    llm = _s._get_llm_client_for_task("goalposts")
    if not llm:
        raise ApiException(
            status_code=503,
            code="NO_LLM_CONFIGURED",
            message="No LLM configured for the goalposts task. Configure a large model in Settings.",
        )

    # Format node context for the LLM
    tasks_text = "\n".join(
        f"  - {t.description} (effort: {t.effort})"
        for t in node.tasks
    ) if node.tasks else "  (no tasks defined)"

    prompt = f"""You are a senior software engineer. Analyze this roadmap item and provide concrete implementation guidance.

## Roadmap Item: {node.title}
**Priority:** {node.priority} | **Category:** {node.category} | **Tier:** {node.tier}

### Description
{node.description or '(no description)'}

### Tasks
{tasks_text}

### Business Impact
{node.business_impact or '(not specified)'}

### Ethos Alignment
{node.ethos_alignment or '(not specified)'}

---

Please provide:
1. **Implementation Strategy** — High-level approach and architecture decisions
2. **Action Steps** — Ordered list of concrete steps to implement this
3. **Code Changes** — Which files/modules likely need modification
4. **Risks & Considerations** — Potential pitfalls or dependencies
5. **Estimated Effort** — Time estimate and complexity assessment
"""

    system = "You are a senior software engineer analyzing a roadmap item for implementation. Be concise, specific, and actionable. Focus on practical guidance."

    try:
        text, tokens = llm.generate(
            prompt=prompt,
            system=system,
            json_mode=False,
            temperature=0.3,
            num_predict=4096,
        )
        return ok({
            "node_id": node_id,
            "guidance": text,
            "tokens_used": tokens,
            "model": llm.model,
        })
    except Exception as e:
        logger.error("LLM execution failed for node %s: %s", node_id, e)
        raise ApiException(
            status_code=500,
            code="LLM_EXECUTION_FAILED",
            message=f"LLM execution failed: {e}",
        )
