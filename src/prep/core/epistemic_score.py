"""
Epistemic Scoring System for CoDRAG.

Computes a composite score (0.0-1.0) representing how well the trace
understands a node in the context of the entire codebase. This is
fundamentally different from the 3b model's self-reported confidence —
it measures contextual understanding, not summary accuracy.

Components:
  1. Summary confidence (0.20) — 3b model's self-reported certainty
  2. Validation status  (0.15) — has a larger model verified the summary?
  3. Neighbor coverage  (0.20) — are connected nodes also enriched?
  4. Cross-ref density  (0.15) — doc↔code bidirectional references
  5. Enrichment depth   (0.15) — how many passes has this node been through?
  6. Staleness check    (0.15) — has the source changed since enrichment?

See docs/Phase22_trace-epistomology/EPISTEMOLOGY_SCORING.md for full design.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ── Weights ──────────────────────────────────────────────────────────

SCORE_WEIGHTS = {
    "summary_confidence": 0.20,
    "validation_status": 0.15,
    "neighbor_coverage": 0.20,
    "cross_reference_density": 0.15,
    "enrichment_depth": 0.15,
    "staleness_check": 0.15,
}


# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class EpistemicScore:
    """Computed epistemic score with component breakdown."""
    node_id: str
    composite: float
    summary_confidence: float
    validation_status: float
    neighbor_coverage: float
    cross_reference_density: float
    enrichment_depth: float
    staleness_check: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "composite": round(self.composite, 3),
            "components": {
                "summary_confidence": round(self.summary_confidence, 3),
                "validation_status": round(self.validation_status, 3),
                "neighbor_coverage": round(self.neighbor_coverage, 3),
                "cross_reference_density": round(self.cross_reference_density, 3),
                "enrichment_depth": round(self.enrichment_depth, 3),
                "staleness_check": round(self.staleness_check, 3),
            },
        }


@dataclass
class EpistemicEntry:
    """Per-node epistemic enrichment produced by the 14b model (Pass 2+)."""
    node_id: str
    extended_summary: str
    domain_tags: List[str]
    architecture_layer: str
    subsystem: Optional[str] = None
    design_patterns: Optional[List[str]] = None
    cross_references: Optional[List[str]] = None
    tech_debt: Optional[List[str]] = None
    staleness_risk: Optional[str] = None
    epistemic_confidence: float = 0.5
    pass_number: int = 2
    enriched_at: str = ""
    model: str = ""

    # Doc-specific fields
    doc_type: Optional[str] = None
    doc_status: Optional[str] = None
    decision_chains: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "node_id": self.node_id,
            "extended_summary": self.extended_summary,
            "domain_tags": self.domain_tags,
            "architecture_layer": self.architecture_layer,
            "epistemic_confidence": round(self.epistemic_confidence, 3),
            "pass_number": self.pass_number,
            "enriched_at": self.enriched_at,
            "model": self.model,
        }
        if self.subsystem:
            d["subsystem"] = self.subsystem
        if self.design_patterns:
            d["design_patterns"] = self.design_patterns
        if self.cross_references:
            d["cross_references"] = self.cross_references
        if self.tech_debt:
            d["tech_debt"] = self.tech_debt
        if self.staleness_risk:
            d["staleness_risk"] = self.staleness_risk
        if self.doc_type:
            d["doc_type"] = self.doc_type
        if self.doc_status:
            d["doc_status"] = self.doc_status
        if self.decision_chains:
            d["decision_chains"] = self.decision_chains
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EpistemicEntry":
        def _str_list(val: Any) -> Optional[List[str]]:
            """Coerce a list field to List[str]; LLMs sometimes return dicts."""
            if val is None:
                return None
            if not isinstance(val, list):
                return [str(val)]
            return [str(v) if not isinstance(v, str) else v for v in val]

        return cls(
            node_id=d["node_id"],
            extended_summary=d.get("extended_summary", ""),
            domain_tags=_str_list(d.get("domain_tags")) or [],
            architecture_layer=str(d.get("architecture_layer", "unknown")),
            subsystem=d.get("subsystem"),
            design_patterns=_str_list(d.get("design_patterns")),
            cross_references=_str_list(d.get("cross_references")),
            tech_debt=_str_list(d.get("tech_debt")),
            staleness_risk=d.get("staleness_risk"),
            epistemic_confidence=float(d.get("epistemic_confidence", 0.5)),
            pass_number=int(d.get("pass_number", 2)),
            enriched_at=d.get("enriched_at", ""),
            model=d.get("model", ""),
            doc_type=d.get("doc_type"),
            doc_status=d.get("doc_status"),
            decision_chains=_str_list(d.get("decision_chains")),
        )


# ── Score computation ────────────────────────────────────────────────

def compute_epistemic_score(
    node_id: str,
    augmentation: Optional[Dict[str, Any]],
    epistemic: Optional[EpistemicEntry],
    neighbor_ids: Set[str],
    enriched_node_ids: Set[str],
    cross_ref_count: int,
    current_file_hashes: Dict[str, str],
) -> EpistemicScore:
    """Compute the composite epistemic score for a node.

    Args:
        node_id: The node to score.
        augmentation: The AugmentationEntry.to_dict() for this node (from Pass 1).
        epistemic: The EpistemicEntry for this node (from Pass 2+), or None.
        neighbor_ids: Set of node IDs connected to this node via edges.
        enriched_node_ids: Set of all node IDs that have epistemic entries.
        cross_ref_count: Number of doc↔code cross-references for this node.
        current_file_hashes: Current file hashes from trace manifest.

    Returns:
        EpistemicScore with composite and per-component breakdown.
    """
    # 1. Summary confidence
    if augmentation:
        c1 = float(augmentation.get("confidence", 0.0))
    else:
        c1 = 0.0

    # 2. Validation status
    # If we have an epistemic entry (Pass 2+), the node has been processed by the 14b model,
    # which counts as high-quality validation.
    if epistemic:
        c2 = 1.0
    elif augmentation and augmentation.get("validated"):
        validated_by = augmentation.get("validated_by", "")
        c2 = 1.0 if "14b" in str(validated_by) else 0.6
    else:
        c2 = 0.0

    # 3. Neighbor coverage
    # Only consider neighbors that are file nodes, since we only enrich files
    file_neighbors = {n for n in neighbor_ids if n.startswith("file:")}
    if not file_neighbors:
        c3 = 0.5  # isolated node, neutral
    else:
        enriched = sum(1 for n in file_neighbors if n in enriched_node_ids)
        c3 = enriched / len(file_neighbors)

    # 4. Cross-reference density (sigmoid-like: saturates at 4)
    c4 = min(1.0, cross_ref_count / 4.0)

    # 5. Enrichment depth
    if epistemic is None:
        c5 = 0.0
    elif epistemic.pass_number >= 4:
        c5 = 1.0
    elif epistemic.pass_number >= 3:
        c5 = 0.75
    else:
        c5 = 0.5  # Pass 2

    # 6. Staleness check
    file_path = node_id.replace("file:", "", 1) if node_id.startswith("file:") else ""
    aug_hash = augmentation.get("file_hash") if augmentation else None
    current_hash = current_file_hashes.get(file_path)
    if aug_hash and current_hash:
        c6 = 1.0 if aug_hash == current_hash else 0.0
    else:
        c6 = 0.3  # unknown

    # Weighted sum
    composite = (
        SCORE_WEIGHTS["summary_confidence"] * c1
        + SCORE_WEIGHTS["validation_status"] * c2
        + SCORE_WEIGHTS["neighbor_coverage"] * c3
        + SCORE_WEIGHTS["cross_reference_density"] * c4
        + SCORE_WEIGHTS["enrichment_depth"] * c5
        + SCORE_WEIGHTS["staleness_check"] * c6
    )

    return EpistemicScore(
        node_id=node_id,
        composite=round(composite, 3),
        summary_confidence=c1,
        validation_status=c2,
        neighbor_coverage=round(c3, 3),
        cross_reference_density=round(c4, 3),
        enrichment_depth=c5,
        staleness_check=c6,
    )


# ── Decay mechanics ──────────────────────────────────────────────────

DECAY_SOURCE_CHANGED = 0.0
DECAY_NEIGHBOR_ENRICHED = 0.95
DECAY_DOC_UPDATED = 0.90
DECAY_TRACE_REBUILT = 0.80
DECAY_MODULE_RESYNTHESIZED = 0.97


def apply_decay(current_score: float, event: str) -> float:
    """Apply a decay factor to an epistemic score based on an event.

    Args:
        current_score: The current composite epistemic score.
        event: One of "source_changed", "neighbor_enriched", "doc_updated",
               "trace_rebuilt", "module_resynthesized".

    Returns:
        The decayed score.
    """
    factors = {
        "source_changed": DECAY_SOURCE_CHANGED,
        "neighbor_enriched": DECAY_NEIGHBOR_ENRICHED,
        "doc_updated": DECAY_DOC_UPDATED,
        "trace_rebuilt": DECAY_TRACE_REBUILT,
        "module_resynthesized": DECAY_MODULE_RESYNTHESIZED,
    }
    factor = factors.get(event)
    if factor is None:
        return current_score
    if factor == 0.0:
        return 0.0
    return round(current_score * factor, 3)
