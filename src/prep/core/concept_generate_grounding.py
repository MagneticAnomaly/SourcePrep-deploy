"""Phase 125c T2a — deterministic helpers for the Generate swarm.

The Generate swarm fans out per-category (or per-axis, depending on
swarm size) and each worker receives a scoped grounding payload.
This module provides the **CPU-only** pieces:

- ``build_worker_scopes(swarm_size)`` — partitions VALID_CATEGORIES
  across 1, 3, or 11 workers (sizes 1/3/10).
- ``tier_docs_grounding(...)`` — splits a DiscoveredDoc list into
  "full excerpt" tier and "headings only" tier by score thresholds.
- ``filter_rationale_by_scope(...)`` — narrows a rationale list to
  rows whose category falls in the scope's category set.

T2b will compose these into per-worker prompts and hand off to
``SwarmOrchestrator``. Keeping the helpers separate makes them
testable without an LLM and reusable by the Validate swarm (T3).

See ``docs/Phase125c_QualityCheckedConceptSwarm/README.md`` §3.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from prep.services.concept_store import VALID_CATEGORIES

from .docs_grounding import DiscoveredDoc


# ── Axis-3 partition (swarm_size=3) ─────────────────────────────────
#
# Per Phase 125c README §3, the 3-worker fan-out groups categories
# by claim type, not by atlas segment. Three axes:
#
#   intent         — what the codebase is FOR
#   rules          — what is REQUIRED / FORBIDDEN
#   implementation — HOW the code expresses both
#
# These are mutually exclusive and together cover all 11 VALID_CATEGORIES.

AXIS_3_INTENT = ("architecture", "domain", "product")
AXIS_3_RULES = ("security", "constraint", "decision")
AXIS_3_IMPLEMENTATION = (
    "technical", "pattern", "process", "epistemic", "brand",
)


@dataclass(frozen=True)
class WorkerScope:
    """Defines what categories one Generate worker is responsible for.

    `categories` is a tuple (not list) so two scopes with identical
    contents compare equal — useful when keying by scope in tests.
    """
    worker_id: str
    label: str
    categories: tuple[str, ...]


def build_worker_scopes(swarm_size: int) -> list[WorkerScope]:
    """Partition VALID_CATEGORIES into N scopes for the Generate swarm.

    Supported sizes: 1, 3, 10.

    - 1  → 1 scope spanning every category (single-call fallback).
    - 3  → 3 scopes along the intent / rules / implementation axes.
    - 10 → 11 scopes (one per category — the "10" label denotes the
      bucket size, not a literal count, since VALID_CATEGORIES has
      11 members. README §3 documents this.)
    """
    if swarm_size == 1:
        return [WorkerScope(
            worker_id="all",
            label="all-categories",
            categories=tuple(sorted(VALID_CATEGORIES)),
        )]
    if swarm_size == 3:
        return [
            WorkerScope("intent", "intent", AXIS_3_INTENT),
            WorkerScope("rules", "rules", AXIS_3_RULES),
            WorkerScope(
                "implementation", "implementation",
                AXIS_3_IMPLEMENTATION,
            ),
        ]
    if swarm_size == 10:
        return [
            WorkerScope(worker_id=cat, label=cat, categories=(cat,))
            for cat in sorted(VALID_CATEGORIES)
        ]
    raise ValueError(
        f"swarm_size must be one of 1, 3, 10; got {swarm_size}"
    )


# ── Doc-grounding tiering ───────────────────────────────────────────


def tier_docs_grounding(
    docs: Iterable[DiscoveredDoc],
    *,
    full_threshold: float = 0.5,
    headings_threshold: float = 0.3,
) -> tuple[list[DiscoveredDoc], list[DiscoveredDoc]]:
    """Split discovered docs into two grounding tiers.

    - **Full**: score ≥ ``full_threshold`` — worker prompt gets the
      excerpt + headings.
    - **Headings only**: ``headings_threshold`` ≤ score < ``full_threshold``
      — worker prompt gets the path + heading list (no excerpt).
    - Below ``headings_threshold``: dropped.

    Returns ``(full_tier, headings_tier)`` lists, both ordered by
    descending score (input order is preserved within each tier when
    scores tie).
    """
    if full_threshold <= headings_threshold:
        raise ValueError(
            f"full_threshold ({full_threshold}) must exceed "
            f"headings_threshold ({headings_threshold})"
        )
    full: list[DiscoveredDoc] = []
    headings: list[DiscoveredDoc] = []
    for d in docs:
        if d.score >= full_threshold:
            full.append(d)
        elif d.score >= headings_threshold:
            headings.append(d)
    return full, headings


# ── Rationale filtering ─────────────────────────────────────────────


def filter_rationale_by_scope(
    rationale: Iterable[dict],
    scope: WorkerScope,
    *,
    default_category: str = "technical",
) -> list[dict]:
    """Return only rationale rows whose category is in ``scope.categories``.

    Rows missing a ``category`` field default to ``default_category``
    (matches the seeder default). This keeps technical-bucket workers
    from missing legacy rationale that lacked categorization.
    """
    allowed = set(scope.categories)
    return [
        r for r in rationale
        if r.get("category", default_category) in allowed
    ]
