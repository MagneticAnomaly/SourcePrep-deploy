"""
CoDRAG Concepts Router — Phase 74 (Epistemic Concepts)
========================================================

Exposes the concept store via HTTP endpoints for the dashboard
and MCP tools.

**Endpoints:**
  - GET    /projects/{id}/concepts              — list concepts
  - POST   /projects/{id}/concepts/initialize   — run concept seeder
  - GET    /projects/{id}/concepts/stats        — statistics
  - POST   /projects/{id}/concepts/search       — FTS search
  - GET    /projects/{id}/concepts/{cid}        — get single concept
  - PUT    /projects/{id}/concepts/{cid}        — update concept
  - PATCH  /projects/{id}/concepts/{cid}/approve  — seed → active
  - PATCH  /projects/{id}/concepts/{cid}/archive  — → archived
  - DELETE /projects/{id}/concepts/{cid}        — delete concept
  - GET    /projects/{id}/concepts/questions     — list questions
  - POST   /projects/{id}/concepts/questions/{qid}/answer — answer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from codrag.api.envelope import ApiException, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["concepts"])


# ── Request/Response Models ──────────────────────────────────────

class SaveConceptRequest(BaseModel):
    title: str
    content: str
    category: Optional[str] = "technical"
    status: Optional[str] = "active"
    anchors: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    # Phase 84: new concept fields
    assertion: Optional[str] = None
    doc_links: Optional[List[Dict[str, str]]] = None
    superseded_by: Optional[str] = None


class UpdateConceptRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    anchors: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    # Phase 84: new concept fields
    assertion: Optional[str] = None
    doc_links: Optional[List[Dict[str, str]]] = None


class SearchConceptsRequest(BaseModel):
    query: str
    limit: int = 10
    include_archived: bool = False


def _calculate_coverage(project_id: str, store) -> Dict[str, Any]:
    """Calculate what % of modules have at least one concept anchored."""
    import json as _json
    from codrag.core.project_registry import project_index_dir
    from codrag.services.project_helpers import require_project

    project = require_project(project_id)
    index_dir = project_index_dir(project)
    modules_path = index_dir / "trace_modules.jsonl"

    if not modules_path.exists():
        return {"coverage_pct": 0.0, "total_modules": 0, "covered_modules": 0}

    # Build file → module_id map
    file_to_module: Dict[str, str] = {}
    module_ids: set = set()
    with open(modules_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                mod = _json.loads(line)
                mid = mod.get("module_id") or mod.get("name", "")
                if not mid:
                    continue
                module_ids.add(mid)
                for fp in mod.get("member_files", mod.get("files", [])):
                    file_to_module[fp] = mid
            except (ValueError, KeyError):
                continue

    if not module_ids:
        return {"coverage_pct": 0.0, "total_modules": 0, "covered_modules": 0}

    # Find which modules have concepts anchored
    concepts = store.list_concepts(project_id, include_archived=False)
    covered: set = set()
    for c in concepts:
        for anchor in c.anchors:
            mid = file_to_module.get(anchor)
            if mid:
                covered.add(mid)

    total = len(module_ids)
    pct = round(len(covered) / total * 100, 1) if total > 0 else 0.0
    return {"coverage_pct": pct, "total_modules": total, "covered_modules": len(covered)}


class AnswerQuestionRequest(BaseModel):
    answer: str
    title: Optional[str] = None  # Override title for the created concept
    category: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────

def _get_store():
    """Get the concept store singleton."""
    from codrag.services.concept_store import concept_store
    return concept_store


def _require_project(project_id: str):
    """Validate project exists."""
    from codrag.services.project_helpers import require_project
    return require_project(project_id)


# ── CRUD Endpoints ───────────────────────────────────────────────

@router.get("/projects/{project_id}/concepts")
async def list_concepts(
    project_id: str,
    status: Optional[str] = None,
    category: Optional[str] = None,
    include_stale: bool = True,
    include_archived: bool = False,
    as_of: Optional[float] = None,
):
    """List concepts for a project."""
    _require_project(project_id)
    store = _get_store()
    concepts = store.list_concepts(
        project_id,
        status=status,
        category=category,
        include_stale=include_stale,
        include_archived=include_archived,
        as_of=as_of,
    )
    return ok({
        "concepts": [c.to_dict() for c in concepts],
        "count": len(concepts),
    })


@router.get("/projects/{project_id}/concepts/stats")
async def concept_stats(project_id: str):
    """Get concept statistics including module coverage."""
    _require_project(project_id)
    store = _get_store()
    stats = store.get_stats(project_id)

    # Calculate module coverage (non-fatal if modules aren't available)
    try:
        stats.update(_calculate_coverage(project_id, store))
    except Exception:
        stats.setdefault("coverage_pct", 0.0)
        stats.setdefault("total_modules", 0)
        stats.setdefault("covered_modules", 0)

    return ok(stats)


@router.post("/projects/{project_id}/concepts/search")
async def search_concepts(project_id: str, body: SearchConceptsRequest):
    """Search concepts by title and content."""
    _require_project(project_id)
    store = _get_store()
    results = store.search(
        project_id,
        query=body.query,
        limit=body.limit,
        include_archived=body.include_archived,
    )
    return ok({
        "concepts": [c.to_dict() for c in results],
        "count": len(results),
    })


# ── Initialize (Seeder) ─────────────────────────────────────────
# NOTE: This MUST be registered BEFORE the {concept_id} wildcard
# route, otherwise FastAPI matches "initialize" as a concept_id.

@router.post("/projects/{project_id}/concepts/initialize")
async def initialize_concepts(project_id: str):
    """Run the concept seeder to generate initial concept seeds.

    This reads atlas, module, and audit data to extract 20-40 concept
    seeds via LLM. Also generates 5-8 clarifying questions.
    """
    _require_project(project_id)
    store = _get_store()

    # Check if already initialized
    stats = store.get_stats(project_id)
    if stats["total"] > 0:
        return ok({
            "status": "already_initialized",
            "total": stats["total"],
            "message": "Concepts already exist. Delete them first to re-initialize.",
        })

    # Import and run seeder
    try:
        from codrag.core.concept_seeder import seed_concepts
        result = seed_concepts(project_id)
        return ok(result)
    except Exception as e:
        logger.error("Concept initialization failed for %s: %s", project_id, e, exc_info=True)
        raise ApiException(500, "SEEDER_ERROR", f"Concept generation failed: {e}")


# ── Questions ────────────────────────────────────────────────────
# NOTE: These MUST be registered BEFORE the {concept_id} wildcard
# route, otherwise FastAPI matches "questions" as a concept_id.

@router.get("/projects/{project_id}/concepts/questions")
async def list_questions(
    project_id: str,
    unanswered_only: bool = True,
):
    """List clarifying questions."""
    _require_project(project_id)
    store = _get_store()
    questions = store.list_questions(project_id, unanswered_only=unanswered_only)
    return ok({
        "questions": [q.to_dict() for q in questions],
        "count": len(questions),
    })


@router.post("/projects/{project_id}/concepts/questions/{question_id}/answer")
async def answer_question(project_id: str, question_id: str, body: AnswerQuestionRequest):
    """Answer a clarifying question and create a concept from the answer."""
    _require_project(project_id)
    store = _get_store()

    # Fetch the question
    questions = store.list_questions(project_id, unanswered_only=False)
    question = next((q for q in questions if q.id == question_id), None)
    if not question:
        raise ApiException(404, "NOT_FOUND", f"Question {question_id} not found")

    # Create concept from the answer
    title = body.title or question.question.rstrip("?").strip()
    category = body.category or question.suggested_category

    try:
        concept_id = store.save(
            project_id=project_id,
            title=title,
            content=body.answer,
            category=category,
            status="active",  # User answers are always active
            confidence=1.0,   # User-provided = full confidence
        )
    except ValueError as e:
        raise ApiException(400, "VALIDATION_ERROR", str(e))

    # Mark question as answered
    store.answer_question(question_id, body.answer, created_concept_id=concept_id)

    return ok({
        "answered": True,
        "concept_id": concept_id,
    })


# ── Single-Concept CRUD (wildcard routes) ────────────────────────
# NOTE: These {concept_id} routes MUST come AFTER all static sub-paths
# (stats, search, initialize, questions) to avoid the wildcard
# swallowing literal path segments.

@router.get("/projects/{project_id}/concepts/{concept_id}")
async def get_concept(project_id: str, concept_id: str):
    """Get a single concept."""
    _require_project(project_id)
    store = _get_store()
    concept = store.get(concept_id)
    if not concept or concept.project_id != project_id:
        raise ApiException(404, "NOT_FOUND", f"Concept {concept_id} not found")
    return ok(concept.to_dict())


@router.post("/projects/{project_id}/concepts")
async def create_concept(project_id: str, body: SaveConceptRequest):
    """Create a new concept (manual user creation)."""
    _require_project(project_id)
    store = _get_store()
    try:
        cid = store.save(
            project_id=project_id,
            title=body.title,
            content=body.content,
            category=body.category or "technical",
            status=body.status or "active",
            confidence=1.0,  # User-created concepts are full confidence
            anchors=body.anchors,
            tags=body.tags,
            assertion=body.assertion or "",
            doc_links=body.doc_links or [],
        )
    except ValueError as e:
        raise ApiException(400, "VALIDATION_ERROR", str(e))
    return ok({"id": cid, "saved": True})


@router.put("/projects/{project_id}/concepts/{concept_id}")
async def update_concept(project_id: str, concept_id: str, body: UpdateConceptRequest):
    """Update a concept."""
    _require_project(project_id)
    store = _get_store()
    existed = store.update(
        concept_id,
        title=body.title,
        content=body.content,
        category=body.category,
        status=body.status,
        anchors=body.anchors,
        tags=body.tags,
        assertion=body.assertion,
        doc_links=body.doc_links,
    )
    if not existed:
        raise ApiException(404, "NOT_FOUND", f"Concept {concept_id} not found")
    return ok({"updated": True})


@router.patch("/projects/{project_id}/concepts/{concept_id}/approve")
async def approve_concept(project_id: str, concept_id: str):
    """Promote a seed concept to active status."""
    _require_project(project_id)
    store = _get_store()
    existed = store.update(concept_id, status="active")
    if not existed:
        raise ApiException(404, "NOT_FOUND", f"Concept {concept_id} not found")
    return ok({"approved": True})


@router.patch("/projects/{project_id}/concepts/{concept_id}/archive")
async def archive_concept(project_id: str, concept_id: str):
    """Archive a concept."""
    _require_project(project_id)
    store = _get_store()
    existed = store.update(concept_id, status="archived")
    if not existed:
        raise ApiException(404, "NOT_FOUND", f"Concept {concept_id} not found")
    return ok({"archived": True})


@router.patch("/projects/{project_id}/concepts/{concept_id}/fresh")
async def mark_fresh(project_id: str, concept_id: str):
    """Clear the stale flag on a concept after user review."""
    _require_project(project_id)
    store = _get_store()
    conn = store._require_conn()
    with store._lock:
        cur = conn.execute(
            "UPDATE concepts SET stale = 0, stale_reason = NULL, updated_at = ? WHERE id = ?",
            (__import__("time").time(), concept_id),
        )
        conn.commit()
    if cur.rowcount == 0:
        raise ApiException(404, "NOT_FOUND", f"Concept {concept_id} not found")
    return ok({"fresh": True})


@router.delete("/projects/{project_id}/concepts/{concept_id}")
async def delete_concept(project_id: str, concept_id: str):
    """Delete a single concept."""
    _require_project(project_id)
    store = _get_store()
    existed = store.delete(concept_id)
    if not existed:
        raise ApiException(404, "NOT_FOUND", f"Concept {concept_id} not found")
    return ok({"deleted": True})
