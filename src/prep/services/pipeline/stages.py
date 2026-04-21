"""
Pipeline stage definitions, mappings, and group constants.
"""
from __future__ import annotations

import enum
from typing import Dict, List, Optional

from prep.services.build_orchestrator import BuildType


class StageId(str, enum.Enum):
    """The 15 pipeline stages in 3 groups of 5."""
    # ── Sync (1-5) ──
    STRUCTURAL = "structural"
    INFERRED_EDGES = "inferred_edges"
    CATALOGUE = "catalogue"
    VALIDATION = "validation"
    KNOWLEDGE = "knowledge"
    # ── Enrich (6-10) ──
    ENRICHMENT = "enrichment"
    GROUP_REASONING = "group_reasoning"
    CLUSTERING = "clustering"
    DEEPENING = "deepening"
    DEEP_KNOWLEDGE = "deep_knowledge"
    # ── Finalize (11-15) ──
    ATLAS = "atlas"
    RULES = "rules"
    CONCEPTS = "concepts"
    AUDIT = "audit"
    ANTIBODIES = "antibodies"


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
    StageId.RULES: BuildType.RULES,
    StageId.CONCEPTS: BuildType.CONCEPTS,
    StageId.AUDIT: BuildType.AUDIT,
    StageId.ANTIBODIES: BuildType.ANTIBODIES,
}

FAST_SYNC_STAGES: List[StageId] = [
    StageId.STRUCTURAL,
    StageId.INFERRED_EDGES,
    StageId.CATALOGUE,
    StageId.VALIDATION,
    StageId.KNOWLEDGE,
]
SYNC_STAGES = FAST_SYNC_STAGES

ENRICH_STAGES: List[StageId] = [
    StageId.ENRICHMENT,
    StageId.GROUP_REASONING,
    StageId.CLUSTERING,
    StageId.DEEPENING,
    StageId.DEEP_KNOWLEDGE,
]
DEEP_ENRICHMENT_STAGES = ENRICH_STAGES

FINALIZE_STAGES: List[StageId] = [
    StageId.ATLAS,
    StageId.RULES,
    StageId.CONCEPTS,
    StageId.AUDIT,
    StageId.ANTIBODIES,
]


# ── Stage Input/Output Files (Phase 70B) ───────────────────────────
# Which output files each stage depends on (its inputs).
# Used by the freshness check to skip already-current stages.

STAGE_INPUT_FILES: Dict[StageId, List[str]] = {
    StageId.STRUCTURAL:      [],  # depends on source files, not pipeline files
    StageId.INFERRED_EDGES:  ["trace_augmented.jsonl"],
    StageId.CATALOGUE:       ["trace_nodes.jsonl"],
    StageId.VALIDATION:      ["trace_edges.jsonl", "trace_inferred_edges.jsonl"],
    StageId.KNOWLEDGE:       ["trace_augmented.jsonl"],
    StageId.ENRICHMENT:      ["trace_augmented.jsonl"],
    StageId.GROUP_REASONING: ["trace_epistemic.jsonl"],
    StageId.CLUSTERING:      ["trace_epistemic.jsonl"],
    StageId.ATLAS:           ["trace_modules.jsonl"],
    StageId.DEEPENING:       ["trace_epistemic.jsonl", "trace_modules.jsonl"],
    StageId.DEEP_KNOWLEDGE:  ["trace_epistemic.jsonl", "trace_modules.jsonl"],
    StageId.RULES:           [],
    StageId.CONCEPTS:        [],
    StageId.AUDIT:           ["trace_nodes.jsonl", "trace_edges.jsonl", "trace_epistemic.jsonl"],
    StageId.ANTIBODIES:      [],
}

# Which stages are deterministic / cheap to re-run (Rust/embedding only)
STAGE_IS_DETERMINISTIC: Dict[StageId, bool] = {
    StageId.STRUCTURAL:      True,   # Rust engine — seconds
    StageId.INFERRED_EDGES:  False,  # LLM
    StageId.CATALOGUE:       False,  # LLM
    StageId.VALIDATION:      True,   # Rust engine
    StageId.KNOWLEDGE:       True,   # Embedding only
    StageId.ENRICHMENT:      False,  # LLM
    StageId.GROUP_REASONING: False,  # LLM
    StageId.CLUSTERING:      False,  # LLM
    StageId.ATLAS:           False,  # LLM
    StageId.DEEPENING:       False,  # LLM
    StageId.DEEP_KNOWLEDGE:  True,   # Embedding only
    StageId.RULES:           True,
    StageId.CONCEPTS:        False,
    StageId.AUDIT:           False,
    StageId.ANTIBODIES:      True,
}


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
    StageId.RULES:           None,
    StageId.CONCEPTS:        "concepts",
    StageId.AUDIT:           "audit",
    StageId.ANTIBODIES:      None,
}

# ── Queue Type Mapping (Phase 45) ─────────────────────────────────
# Which compute queue each stage belongs to.
# - RUST: CPU-only, no GPU contention, runs immediately
# - EMBEDDING: Independent ONNX path (CoreML/CUDA), not LLM server
# - LLM: Competes for LLM server slots (Ollama/LM Studio/cloud)
#
# NativeEmbedder uses CoreML/CUDA via ONNX — completely separate from
# the LLM inference server.  Embedding stages can run in parallel with
# LLM stages on the same machine without contention.
#
# Exception: if user configures OllamaEmbedder, embedding stages DO
# compete for the same Ollama server.  The scheduler detects this.

class QueueType(str, enum.Enum):
    LLM = "llm"
    EMBEDDING = "embedding"
    RUST = "rust"

STAGE_QUEUE_TYPE: Dict[StageId, QueueType] = {
    StageId.STRUCTURAL:      QueueType.RUST,
    StageId.INFERRED_EDGES:  QueueType.LLM,
    StageId.CATALOGUE:       QueueType.LLM,
    StageId.VALIDATION:      QueueType.RUST,
    StageId.KNOWLEDGE:       QueueType.EMBEDDING,
    StageId.ENRICHMENT:      QueueType.LLM,
    StageId.GROUP_REASONING: QueueType.LLM,
    StageId.CLUSTERING:      QueueType.LLM,
    StageId.ATLAS:           QueueType.LLM,
    StageId.DEEPENING:       QueueType.LLM,
    StageId.DEEP_KNOWLEDGE:  QueueType.EMBEDDING,
    StageId.RULES:           QueueType.RUST,
    StageId.CONCEPTS:        QueueType.LLM,
    StageId.AUDIT:           QueueType.LLM,
    StageId.ANTIBODIES:      QueueType.RUST,
}


# Backward-compat alias — kept so any external code referencing this still works.
# ── Manifest File Mapping (Phase 49) ─────────────────────────────
# Which manifest file each stage writes to (in the project's index dir).
# These enhanced manifests capture model provenance, timing, and quality.

STAGE_MANIFEST_FILE: Dict[StageId, str] = {
    StageId.STRUCTURAL:      "trace_manifest.json",
    StageId.INFERRED_EDGES:  "trace_inferred_manifest.json",
    StageId.CATALOGUE:       "trace_augment_manifest.json",
    StageId.VALIDATION:      "validation_manifest.json",
    StageId.KNOWLEDGE:       "knowledge_manifest.json",
    StageId.ENRICHMENT:      "trace_epistemic_manifest.json",
    StageId.GROUP_REASONING: "group_reasoning_manifest.json",
    StageId.CLUSTERING:      "trace_modules_manifest.json",
    StageId.ATLAS:           "atlas_manifest.json",
    StageId.DEEPENING:       "deepening_manifest.json",
    StageId.DEEP_KNOWLEDGE:  "deep_knowledge_manifest.json",
    StageId.RULES:           "rules_manifest.json",
    StageId.CONCEPTS:        "concepts_manifest.json",
    StageId.AUDIT:           "audit_manifest.json",
    StageId.ANTIBODIES:      "antibodies_manifest.json",
}

# ── Stage Output Files (Phase 49) ────────────────────────────────
# Primary output file for each stage (used for quality metric aggregation).
# None = no primary JSONL output (e.g., Rust stages, pass-through stages).

STAGE_OUTPUT_FILE: Dict[StageId, Optional[str]] = {
    StageId.STRUCTURAL:      "trace_nodes.jsonl",
    StageId.INFERRED_EDGES:  "trace_inferred_edges.jsonl",
    StageId.CATALOGUE:       "trace_augmented.jsonl",
    StageId.VALIDATION:      None,
    StageId.KNOWLEDGE:       None,
    StageId.ENRICHMENT:      "trace_epistemic.jsonl",
    StageId.GROUP_REASONING: "trace_group_reasoning.jsonl",
    StageId.CLUSTERING:      "trace_modules.jsonl",
    StageId.ATLAS:           None,
    StageId.DEEPENING:       "trace_epistemic.jsonl",
    StageId.DEEP_KNOWLEDGE:  None,
    StageId.RULES:           None,
    StageId.CONCEPTS:        None,
    StageId.AUDIT:           None,
    StageId.ANTIBODIES:      None,
}

# ── Confidence Field per Stage (Phase 49) ────────────────────────
# Which JSON field holds the confidence score in each stage's output.

STAGE_CONFIDENCE_FIELD: Dict[StageId, Optional[str]] = {
    StageId.STRUCTURAL:      None,
    StageId.INFERRED_EDGES:  "confidence",
    StageId.CATALOGUE:       "confidence",
    StageId.VALIDATION:      None,
    StageId.KNOWLEDGE:       None,
    StageId.ENRICHMENT:      "epistemic_confidence",
    StageId.GROUP_REASONING: None,
    StageId.CLUSTERING:      None,
    StageId.ATLAS:           None,
    StageId.DEEPENING:       "epistemic_confidence",
    StageId.DEEP_KNOWLEDGE:  None,
    StageId.RULES:           None,
    StageId.CONCEPTS:        None,
    StageId.AUDIT:           None,
    StageId.ANTIBODIES:      None,
}

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
    StageId.RULES:          None,
    StageId.CONCEPTS:       "large",
    StageId.AUDIT:          "large",
    StageId.ANTIBODIES:     None,
}

FINALIZE_WAVES: List[List[StageId]] = [
    [StageId.ATLAS],
    [StageId.RULES, StageId.CONCEPTS, StageId.AUDIT],
    [StageId.ANTIBODIES],
]


def stage_manifest_name(stage_id: str) -> str:
    """Canonical manifest filename for a stage.

    Uses the authoritative STAGE_MANIFEST_FILE map. Falls back to
    {stage_id}_manifest.json only for unknown stage ids (keeps the
    health endpoint and backup picker robust against future additions).
    """
    try:
        return STAGE_MANIFEST_FILE[StageId(stage_id)]
    except (KeyError, ValueError):
        return f"{stage_id}_manifest.json"
