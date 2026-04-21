"""
CoDRAG Goalposts Router — Phase 57
=====================================

REST endpoints for forward-looking AI planning.

Endpoints:
  GET    /projects/{id}/goalposts           — Get current state (proposals + questions)
  POST   /projects/{id}/goalposts/generate  — Trigger on-demand planning pass
  PATCH  /projects/{id}/goalposts/proposals/{pid}  — Update proposal state (approve/dismiss)
  PUT    /projects/{id}/goalposts/intent    — Save/update product intent
  POST   /projects/{id}/goalposts/questions/{qid}/answer — Answer a design question
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from prep.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["goalposts"])


def _srv():
    import prep.server as _s
    return _s


# ── Request models ───────────────────────────────────────────────────

class IntentUpdate(BaseModel):
    product_intent: str


class ProposalUpdate(BaseModel):
    state: str  # "approved" | "dismissed"


class QuestionAnswer(BaseModel):
    answer: str


# ── Background thread tracking ──────────────────────────────────────

_generate_threads: Dict[str, threading.Thread] = {}
_generate_errors: Dict[str, str] = {}


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/goalposts")
def get_goalposts(project_id: str) -> Dict[str, Any]:
    """Get current goalposts state for a project."""
    proj = _srv()._require_project(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.goalposts_models import load_goalposts
    from prep.core.goalposts_planner import can_generate_goalposts

    index_dir = project_index_dir(proj)
    state = load_goalposts(index_dir)
    readiness = can_generate_goalposts(index_dir)

    # Check if generation is running
    t = _generate_threads.get(proj.id)
    generating = t is not None and t.is_alive()
    error = _generate_errors.get(proj.id)

    return ok({
        "generating": generating,
        "error": error,
        **readiness,
        **state.to_dict(),
    })


@router.post("/projects/{project_id}/goalposts/generate")
def trigger_generate(project_id: str) -> Dict[str, Any]:
    """Trigger an on-demand goalposts planning pass."""
    from prep.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    # Check if already running
    t = _generate_threads.get(proj.id)
    if t is not None and t.is_alive():
        return ok({"status": "already_running", "message": "Generation is already in progress."})

    # Clear previous errors
    _generate_errors.pop(proj.id, None)

    from prep.core.project_registry import project_index_dir
    index_dir = project_index_dir(proj)

    def _run():
        try:
            from prep.server import _get_llm_client_for_task
            from prep.core.goalposts_planner import GoalpostsPlanner
            from prep.core.goalposts_models import load_goalposts

            llm_client = _get_llm_client_for_task("audit")  # Uses same slot as audit
            if not llm_client:
                _generate_errors[proj.id] = "No LLM configured for planning. Configure a large model in Settings."
                return

            state = load_goalposts(index_dir)
            planner = GoalpostsPlanner(
                index_dir=index_dir,
                llm_client=llm_client,
                project_root=Path(proj.path),
            )
            planner.generate(product_intent=state.product_intent)
            logger.info("Goalposts generated for %s", proj.id)
        except Exception as e:
            logger.error("Goalposts generation failed for %s: %s", proj.id, e)
            _generate_errors[proj.id] = str(e)

    thread = threading.Thread(target=_run, daemon=True, name=f"goalposts-{proj.id}")
    _generate_threads[proj.id] = thread
    thread.start()

    return ok({
        "status": "started",
        "message": "Goalposts generation started. Poll GET /goalposts to check progress.",
    })


@router.put("/projects/{project_id}/goalposts/intent")
def update_intent(project_id: str, req: IntentUpdate) -> Dict[str, Any]:
    """Save or update the product intent text."""
    from prep.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.goalposts_models import load_goalposts, save_goalposts

    index_dir = project_index_dir(proj)
    state = load_goalposts(index_dir)
    state.product_intent = req.product_intent.strip()
    save_goalposts(state, index_dir)

    return ok({"product_intent": state.product_intent})


@router.patch("/projects/{project_id}/goalposts/proposals/{proposal_id}")
def update_proposal(project_id: str, proposal_id: str, req: ProposalUpdate) -> Dict[str, Any]:
    """Update a proposal's state (approve or dismiss)."""
    from prep.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    if req.state not in ("approved", "dismissed"):
        raise ApiException(
            status_code=400,
            code="INVALID_STATE",
            message=f"Invalid state '{req.state}'. Must be 'approved' or 'dismissed'.",
        )

    from prep.core.project_registry import project_index_dir
    from prep.core.goalposts_models import load_goalposts, save_goalposts

    index_dir = project_index_dir(proj)
    state = load_goalposts(index_dir)

    # Find and update the proposal
    found = False
    for p in state.proposals:
        if p.id == proposal_id:
            p.state = req.state
            p.decided_at = datetime.now(timezone.utc).isoformat()
            found = True
            break

    if not found:
        raise ApiException(
            status_code=404,
            code="PROPOSAL_NOT_FOUND",
            message=f"Proposal '{proposal_id}' not found.",
        )

    save_goalposts(state, index_dir)
    return ok({"id": proposal_id, "state": req.state})


@router.post("/projects/{project_id}/goalposts/questions/{question_id}/answer")
def answer_question(project_id: str, question_id: str, req: QuestionAnswer) -> Dict[str, Any]:
    """Submit an answer to a design question."""
    from prep.services.project_helpers import require_project_writable
    proj = require_project_writable(project_id)

    from prep.core.project_registry import project_index_dir
    from prep.core.goalposts_models import load_goalposts, save_goalposts

    index_dir = project_index_dir(proj)
    state = load_goalposts(index_dir)

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

    save_goalposts(state, index_dir)
    return ok({"id": question_id, "answered": True})
