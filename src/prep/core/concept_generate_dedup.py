"""Phase 125c T2c.1 — helpers for the Generate swarm.

Two pieces:
- ``load_or_build_docs_grounding`` — reads ``docs_grounding.json`` if
  present, otherwise builds it on the fly. Generate workers call this
  to get their planning-doc grounding.
- ``dedupe_swarm_outputs`` — when N workers each emit candidate
  concepts, two workers may produce near-duplicates (same anchors,
  similar titles). This pass clusters by anchor-overlap (reusing
  ``concept_clustering.cluster_concepts``) and picks the highest-tier
  representative per cluster.

Pure(ish) — ``load_or_build_docs_grounding`` does I/O; ``dedupe`` is
deterministic. No LLM calls anywhere.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from .concept_clustering import (
    ConceptInput,
    cluster_concepts,
)
from .concept_synthesizer import (
    TIER_TO_CONFIDENCE,
    SynthesizedConcept,
)
from .docs_grounding import (
    DocsGrounding,
    build_docs_grounding,
    write_docs_grounding,
)

logger = logging.getLogger(__name__)


# ── Docs grounding loader ───────────────────────────────────────────


def load_or_build_docs_grounding(
    project_id: str,
    *,
    idx_dir: Path,
    project_root: Path,
    rebuild_if_missing: bool = True,
    top_n: int = 30,
) -> DocsGrounding:
    """Read ``<idx_dir>/docs_grounding.json`` or build it.

    The file is the T1 output. Generate workers depend on it for
    rich planning-doc grounding. We keep the build side here so a
    fresh project with no atlas yet can still feed the synthesizer
    the convention-name and folder-concentration signals.
    """
    out_path = idx_dir / "docs_grounding.json"
    if out_path.is_file():
        try:
            import json
            data = json.loads(out_path.read_text(encoding="utf-8"))
            return _from_dict(data)
        except (OSError, ValueError) as e:
            logger.warning(
                "docs_grounding.json present but unreadable (%s); rebuilding",
                e,
            )

    if not rebuild_if_missing:
        return DocsGrounding()

    grounding = build_docs_grounding(
        project_id,
        project_root=project_root,
        idx_dir=idx_dir,
        top_n=top_n,
    )
    try:
        write_docs_grounding(grounding, idx_dir)
    except OSError as e:
        logger.warning("could not write docs_grounding.json: %s", e)
    return grounding


def _from_dict(data: dict) -> DocsGrounding:
    """Reconstruct DocsGrounding from its serialized JSON form."""
    from .docs_grounding import DiscoveredDoc
    docs = []
    for d in data.get("docs", []):
        docs.append(DiscoveredDoc(
            path=d.get("path", ""),
            score=float(d.get("score") or 0.0),
            signals=tuple(d.get("signals") or []),
            in_link_count=int(d.get("in_link_count") or 0),
            size_bytes=int(d.get("size_bytes") or 0),
            excerpt=d.get("excerpt", ""),
            headings=tuple(d.get("headings") or []),
        ))
    return DocsGrounding(
        version=int(data.get("version") or 1),
        generated_at=float(data.get("generated_at") or 0.0),
        docs=docs,
        total_candidates_considered=int(data.get("total_candidates_considered") or 0),
        selected_count=int(data.get("selected_count") or len(docs)),
    )


# ── Cross-worker dedup ──────────────────────────────────────────────


def dedupe_swarm_outputs(
    concepts: Iterable[SynthesizedConcept],
    *,
    min_shared_anchors: int = 2,
    title_jaccard_threshold: float = 0.6,
) -> list[SynthesizedConcept]:
    """Collapse near-duplicates that two workers produced independently.

    Uses ``concept_clustering.cluster_concepts`` (the existing Phase 125
    T1 primitive) on the worker outputs. Within each cluster we keep
    the highest-tier candidate (T3 > T2 > T1, ties broken by anchor
    count). Singletons pass through unchanged.

    Anchor-overlap clustering is what the Phase 125 architecture relies
    on — same logic, applied here at the worker output layer rather
    than the rationale layer.
    """
    items = list(concepts)
    if len(items) < 2:
        return items

    # Convert to ConceptInput shape (the clusterer's input format).
    # Use list index as id so we can map cluster results back.
    inputs = [
        ConceptInput(
            id=str(i),
            title=c.title,
            confidence=TIER_TO_CONFIDENCE.get(c.tier, 0.0),
            anchors=list(c.anchors),
        )
        for i, c in enumerate(items)
    ]
    report = cluster_concepts(
        inputs,
        min_shared_anchors=min_shared_anchors,
        title_jaccard_threshold=title_jaccard_threshold,
    )

    # Walk multi-member clusters. Override the clusterer's confidence-based
    # pick with our own (tier, anchor_count, title_length) pick — synthesizer
    # tier is a stronger quality signal than the float-cast confidence.
    shadows: set[str] = set()
    for cluster in report.clusters:
        if cluster.member_count < 2:
            continue
        member_ids = (cluster.representative_id, *cluster.shadow_ids)
        cluster_items = [items[int(mid)] for mid in member_ids]
        winner = max(
            cluster_items,
            key=lambda c: (
                TIER_TO_CONFIDENCE.get(c.tier, 0.0),
                len(c.anchors),
                len(c.title),
            ),
        )
        for mid in member_ids:
            if items[int(mid)] is not winner:
                shadows.add(mid)

    return [c for i, c in enumerate(items) if str(i) not in shadows]
