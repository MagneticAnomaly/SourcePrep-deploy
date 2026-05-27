"""
SourcePrep System Concept Seeder — Phase 119 Task 16
=====================================================

Seeds a small set of *built-in* concepts that document SourcePrep's own
runtime behavior so AI agents using the MCP `prep_search` tool can find
them when troubleshooting (e.g. "why is my limit not changing?",
"concurrency reset", "rate limit too high").

Unlike the LLM-driven `concept_seeder` (which extracts project-specific
concepts from atlas/modules), this seeder ships with the daemon and
seeds the same fixed set of "system" concepts into every registered
project. Concepts are upserted by title (the `concept_store.save`
dedup path), so repeated calls at startup are idempotent.

These concepts are how an AI agent discovers the discovered-ceiling
mechanism and the `POST /compute/concurrency/clear` reset action when
the user describes throttling that doesn't match their current plan.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── System concept catalog ────────────────────────────────────────
#
# Each entry is upserted into every project's concept_store at daemon
# startup. Keep entries terse (4-8 sentences max for content) so they
# fit cleanly in `prep_search` results without crowding LLM-extracted
# concepts. Tags should include search-friendly keywords that match
# the way users describe symptoms ("rate limit", "throttle", "slow").

_SYSTEM_CONCEPTS: List[Dict[str, Any]] = [
    {
        "title": "Cloud LLM concurrency ceiling lock",
        "content": (
            "SourcePrep does not assume a fixed concurrency limit for cloud "
            "LLM endpoints. On first use, each cloud node runs a latency-aware "
            "AIMD probe that grows the parallel-request budget until the "
            "provider returns a 429/503 (or latency degrades), then locks the "
            "discovered ceiling for 24 hours so it stops re-probing. Symptoms "
            "of a stale lock include throughput that does not improve after a "
            "plan upgrade (e.g. Ollama Cloud Free → Max), or a `cloud:* N/M` "
            "badge in the pipeline queue that stays well below the new plan's "
            "advertised limit. Resolution: POST /compute/concurrency/clear?node_id=cloud:<id> "
            "to invalidate the persisted record and reset the in-memory slot, "
            "or click the developer reset button in AI Gateway → Pipeline "
            "Activity. AIMD then re-probes from the Phase 82 jumpstart seed."
        ),
        "category": "constraint",
        "confidence": 1.0,
        "anchors": [
            "src/prep/services/pipeline/scheduler.py",
            "src/prep/services/pipeline/concurrency_store.py",
            "src/prep/api/routers/compute.py",
        ],
        "tags": [
            "concurrency",
            "ollama",
            "rate-limit",
            "throttle",
            "aimd",
            "phase-119",
            "ceiling",
            "reset",
        ],
        "assertion": (
            "Cloud slots discover their concurrency limit at runtime via "
            "AIMD; the limit is locked for 24h after the first backoff edge "
            "in congestion-avoidance mode. POST /compute/concurrency/clear "
            "invalidates the lock and triggers re-discovery."
        ),
        "doc_links": [
            {
                "label": "Concurrency Discovery & Locking",
                "href": "https://docs.sourceprep.io/guides/concurrency-discovery",
            },
        ],
    },
]


def seed_system_concepts(project_id: str) -> int:
    """Upsert the system concept catalog into a single project.

    Returns the number of concepts saved/updated. Errors during a single
    save are logged at WARNING and do not abort the rest of the batch —
    we never want a startup hook to take the daemon down.
    """
    from prep.services.concept_store import concept_store

    saved = 0
    for spec in _SYSTEM_CONCEPTS:
        try:
            concept_store.save(
                project_id=project_id,
                title=spec["title"],
                content=spec["content"],
                category=spec.get("category", "technical"),
                # 'verified' status keeps these out of the unverified-seed
                # noise filter that some UI surfaces apply.
                status="verified",
                confidence=spec.get("confidence", 1.0),
                anchors=spec.get("anchors", []),
                tags=spec.get("tags", []),
                assertion=spec.get("assertion", ""),
                doc_links=spec.get("doc_links", []),
            )
            saved += 1
        except Exception as e:
            logger.warning(
                "System concept seed failed for %s/%s: %s",
                project_id, spec.get("title"), e,
            )
    return saved


def seed_system_concepts_for_all_projects() -> int:
    """Seed the system concept catalog into every registered project.

    Called once at daemon startup, after concept_store.init() and after
    project registry pointer validation. Idempotent — the underlying
    concept_store.save dedupes by (project_id, title).

    Returns the total number of concepts saved across all projects.
    """
    from prep.services.project_helpers import get_registry

    total = 0
    try:
        registry = get_registry()
        projects = registry.list_projects()
    except Exception:
        logger.debug(
            "system_concept_seeder: project registry not available — skipping",
            exc_info=True,
        )
        return 0

    for project in projects:
        try:
            total += seed_system_concepts(project.id)
        except Exception:
            logger.debug(
                "system_concept_seeder: per-project seed failed for %s",
                getattr(project, "id", "?"),
                exc_info=True,
            )

    if total:
        logger.info(
            "Seeded %d system concept(s) across %d project(s)",
            total, len(projects),
        )
    return total
