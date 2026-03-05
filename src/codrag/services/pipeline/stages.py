"""
Pipeline stage definitions, mappings, and group constants.
"""
from __future__ import annotations

import enum
from typing import Dict, List, Optional

from codrag.services.build_orchestrator import BuildType


class StageId(str, enum.Enum):
    """The 11 pipeline stages, matching the UI's EnrichmentStageId."""
    STRUCTURAL = "structural"
    INFERRED_EDGES = "inferred_edges"
    CATALOGUE = "catalogue"
    VALIDATION = "validation"
    KNOWLEDGE = "knowledge"
    ENRICHMENT = "enrichment"
    GROUP_REASONING = "group_reasoning"
    CLUSTERING = "clustering"
    ATLAS = "atlas"
    DEEPENING = "deepening"
    DEEP_KNOWLEDGE = "deep_knowledge"


# Map StageId → BuildType for dispatch to the orchestrator
STAGE_BUILD_TYPE: Dict[StageId, BuildType] = {
    StageId.STRUCTURAL: BuildType.TRACE,
    StageId.INFERRED_EDGES: BuildType.INFERRED_EDGES,
    StageId.CATALOGUE: BuildType.AUGMENT,
    StageId.VALIDATION: BuildType.VALIDATE,
    StageId.KNOWLEDGE: BuildType.KNOWLEDGE,
    StageId.ENRICHMENT: BuildType.EPISTEMIC,
    StageId.GROUP_REASONING: BuildType.GROUP_REASONING,
    StageId.CLUSTERING: BuildType.CLUSTER,
    StageId.ATLAS: BuildType.ATLAS,
    StageId.DEEPENING: BuildType.DEEPENING,
    StageId.DEEP_KNOWLEDGE: BuildType.KNOWLEDGE,  # Same build type, re-runs with richer data
}

FAST_SYNC_STAGES: List[StageId] = [
    StageId.STRUCTURAL,
    StageId.INFERRED_EDGES,
    StageId.CATALOGUE,
    StageId.VALIDATION,
    StageId.KNOWLEDGE,
]

DEEP_ENRICHMENT_STAGES: List[StageId] = [
    StageId.ENRICHMENT,
    StageId.GROUP_REASONING,
    StageId.CLUSTERING,
    StageId.ATLAS,
    StageId.DEEPENING,
    StageId.DEEP_KNOWLEDGE,
]


# ── Task ID Mapping (Phase 44) ──────────────────────────────────────
# Which CodragTaskId each stage uses.  None = no LLM needed.
# Used by the VRAM lifecycle manager and the unified LLM resolver.

STAGE_TASK_ID: Dict[StageId, Optional[str]] = {
    StageId.STRUCTURAL:      None,
    StageId.INFERRED_EDGES:  "inferred_edges",
    StageId.CATALOGUE:       "catalogue",
    StageId.VALIDATION:      None,
    StageId.KNOWLEDGE:       None,      # embedding only
    StageId.ENRICHMENT:      "enrichment",
    StageId.GROUP_REASONING: "group_reasoning",
    StageId.CLUSTERING:      "clustering",
    StageId.ATLAS:           "atlas",
    StageId.DEEPENING:       "deepening",
    StageId.DEEP_KNOWLEDGE:  None,      # embedding only
}

# Backward-compat alias — kept so any external code referencing this still works.
STAGE_MODEL_SLOT: Dict[StageId, Optional[str]] = {
    StageId.STRUCTURAL:     None,
    StageId.INFERRED_EDGES: "code",
    StageId.CATALOGUE:      "small",
    StageId.VALIDATION:     None,
    StageId.KNOWLEDGE:      None,
    StageId.ENRICHMENT:     "large",
    StageId.GROUP_REASONING: "large",
    StageId.CLUSTERING:     "large",
    StageId.ATLAS:          "large",
    StageId.DEEPENING:      "large",
    StageId.DEEP_KNOWLEDGE: None,
}
