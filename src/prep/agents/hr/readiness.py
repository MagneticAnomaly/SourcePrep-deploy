"""Epistemic readiness scoring for Staffing Agent generation.

Evaluates 7 dimensions of codebase knowledge to determine whether
role generation is viable. Pure function — no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ReadinessReport:
    """Result of readiness evaluation."""

    score: float  # 0.0–1.0 composite
    dimensions: Dict[str, float] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)

    @property
    def ready_for_auto(self) -> bool:
        return self.score >= 0.7

    @property
    def ready_for_list(self) -> bool:
        return self.score >= 0.4


# Dimension weights (must sum to 1.0)
_WEIGHTS: Dict[str, float] = {
    "pipeline_completion": 0.20,
    "file_count": 0.10,
    "module_count": 0.20,
    "domain_coverage": 0.15,
    "layer_diversity": 0.15,
    "documentation": 0.10,
    "hub_files": 0.10,
}


def compute_readiness(
    modules: List[Dict[str, Any]],
    atlas_content: str,
    file_count: int,
    has_hub_files: bool = False,
    has_docs: bool = False,
) -> ReadinessReport:
    """Compute epistemic readiness score from CoDRAG data.

    Args:
        modules: Module cluster dicts from ``get_module_structure()``.
        atlas_content: Raw atlas string from ``get_atlas()``.
        file_count: Total indexed file count.
        has_hub_files: Whether hub files have been identified.
        has_docs: Whether documentation files exist in the index.

    Returns:
        ReadinessReport with composite score, per-dimension scores, and missing items.
    """
    dims: Dict[str, float] = {}
    missing: List[str] = []

    # 1. Pipeline completion — atlas exists and has content
    dims["pipeline_completion"] = min(1.0, len(atlas_content) / 100) if atlas_content else 0.0
    if dims["pipeline_completion"] < 0.5:
        missing.append("Run the CoDRAG pipeline to generate atlas data")

    # 2. File count — need ≥20 files for meaningful analysis
    dims["file_count"] = min(1.0, file_count / 20)
    if file_count < 20:
        missing.append(f"Index more files (have {file_count}, need ≥20)")

    # 3. Module count — need ≥2 modules
    module_count = len(modules)
    dims["module_count"] = min(1.0, module_count / 2)
    if module_count < 2:
        missing.append(f"Need ≥2 module clusters (have {module_count})")

    # 4. Domain tag coverage — unique tags across modules
    all_tags: set = set()
    total_files = 0
    for m in modules:
        all_tags.update(m.get("domain_tags", []))
        total_files += len(m.get("member_files", []))
    tagged_ratio = len(all_tags) / max(1, total_files) if total_files else 0.0
    dims["domain_coverage"] = min(1.0, tagged_ratio * 10)
    if len(all_tags) < 3:
        missing.append(f"Need more domain tag diversity (have {len(all_tags)} unique tags)")

    # 5. Layer diversity — distinct architecture_layer values
    layers: set = set()
    for m in modules:
        layer = m.get("architecture_layer", "")
        if layer:
            layers.add(layer)
    dims["layer_diversity"] = min(1.0, len(layers) / 3)
    if len(layers) < 3:
        missing.append(f"Need ≥3 architecture layers (have {len(layers)})")

    # 6. Documentation
    dims["documentation"] = 1.0 if has_docs else 0.0
    if not has_docs:
        missing.append("Index documentation files for richer role context")

    # 7. Hub files
    dims["hub_files"] = 1.0 if has_hub_files else 0.0
    if not has_hub_files:
        missing.append("Run deep enrichment to identify hub files")

    # Weighted composite
    score = sum(dims[k] * _WEIGHTS[k] for k in _WEIGHTS)
    score = round(min(1.0, max(0.0, score)), 3)

    return ReadinessReport(score=score, dimensions=dims, missing=missing)
