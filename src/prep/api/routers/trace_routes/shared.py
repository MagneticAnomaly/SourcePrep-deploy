"""
Shared state, constants, and Pydantic models for the trace router subpackage.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Module-level state (thread tracking) ─────────────────────────
# These were formerly globals in server.py.  Phase 24 (SM-6) will
# replace them with a PipelineOrchestrator per-project.

_deep_analysis_state: Dict[str, Dict[str, Any]] = {}
_epistemic_state: Dict[str, Dict[str, Any]] = {}
_cluster_state: Dict[str, Dict[str, Any]] = {}
_deepening_state: Dict[str, Dict[str, Any]] = {}


# ── Constants ────────────────────────────────────────────────────

TRACE_FILES = [
    "trace_manifest.json",
    "trace_nodes.jsonl",
    "trace_edges.jsonl",
    "trace_augmented.jsonl",
    "trace_augment_manifest.json",
    "trace_inferred_edges.jsonl",
    "trace_inferred_manifest.json",
    "trace_inferred_hashes.json",
    "trace_epistemic.jsonl",
    "trace_epistemic_manifest.json",
    "trace_modules.jsonl",
    "trace_modules_manifest.json",
    "trace_group_reasoning.jsonl",
    "group_reasoning_manifest.json",
    "trace_cluster_swarm_synthesis.json",
    "validation_manifest.json",
    "deepening_manifest.json",
    "deep_knowledge_manifest.json",
    # Codebase Atlas (Phase 29)
    "atlas.json",
    "atlas_prev.json",
    "atlas_manifest.json",
    "atlas_segments_manifest.json",
    # Atlas Routing (Phase 29B)
    "atlas_routing.json",
    "atlas_routing_embeddings.npy",
    # Phase 81: Previously missing from destroy list — leftover files
    # caused the resume detector to think skipped stages were complete.
    "atlas_updated.signal",
    "pipeline_run_metadata.json",
    # F-78: Finalize-group manifests (stages 12-15). Previously orphaned
    # by full-reset so stub manifests survived; selfheal then resurrected
    # them from existing output data and the UI showed phantom greens.
    "rules_manifest.json",
    "concepts_manifest.json",
    "audit_manifest.json",
    "antibodies_manifest.json",
    # 2026-05-17 regression fix (sibling to F-78). Phase 134 introduced
    # the centralized Changeset (stage 1 → all downstream workers); the
    # destroy list was never updated. Surviving a full reset, the stale
    # changeset re-classifies every file as `cs.modified` (because the
    # last rebuild marked them so) — coverage.py:101 maps that to
    # `stale_set` and the Graph Scope panel paints "74 stale" on a
    # freshly-wiped project. Files should appear as `untraced` after
    # reset, not stale.
    "changeset.json",
    # 2026-05-17 audit sweep — sync TRACE_FILES with STAGE_OUTPUTS
    # entries that accreted post-F-78 but were never propagated here.
    # Each was producing leftover state on /index/destroy:
    #   - catalogue.jsonl / catalogue_manifest.json (Stage 3 outputs)
    #   - trace_swarm_synthesis.json (Stage 8 cluster swarm output)
    #   - atlas_swarm_synthesis.json + atlas_markdown_links.json
    #     (Phase 124 T2 atlas artifacts)
    #   - concept_generate_manifest.json (concept-gen swarm progress;
    #     sub-artifact of stage 13 Concepts)
    #   - docs_grounding.json (concept-gen dedup cache, recomputable)
    # See `STAGE_OUTPUTS` in src/prep/services/pipeline/stages.py — the
    # parity test below pins ALL_DATA_FILES against that source-of-truth
    # so the next stage output added to STAGE_OUTPUTS triggers a CI fail
    # here unless it is either added or explicitly excluded.
    "catalogue.jsonl",
    "catalogue_manifest.json",
    "trace_swarm_synthesis.json",
    "atlas_swarm_synthesis.json",
    "atlas_markdown_links.json",
    "concept_generate_manifest.json",
    "docs_grounding.json",
    # Sub-artifacts written by core engines that are NOT declared in
    # STAGE_OUTPUTS (the parity test does not cover them — they live
    # outside the formal stage list as supporting/intermediate state):
    #   - concept_synthesis_manifest.json (concept_synthesizer.py:693)
    #   - deep_analysis_manifest.json (deep_analysis.py — independent
    #     background job, sibling to the 15-stage pipeline)
    "concept_synthesis_manifest.json",
    "deep_analysis_manifest.json",
    "trace_lsp_edges.jsonl",
    "trace_external_edges.jsonl",
]

INDEX_FILES = [
    "documents.json",
    "embeddings.npy",
    "manifest.json",
    "fts.sqlite3",
    "knowledge_documents.json",
    "knowledge_embeddings.npy",
    "knowledge_manifest.json",
]

# Phase 118 G2: clean-shutdown marker (F-65) must also be wiped on
# /index/destroy so the post-destroy state is a true blank slate.
# Otherwise the marker survives and confuses any later "is this project
# fresh?" check that relies on its absence.
# Phase 118 U11: pipeline_state.json is the orchestrator's serialized
# state-machine snapshot. The destroy didn't list it; surviving past a
# full reset, it carries pre-reset stage indices that confuse the
# next run's resume detection. Same root-cause class as the
# .pipeline_clean_shutdown marker.
#
# 2026-06-08 P5: .guard_rejections.json holds Write-Guard rejection
# markers with a 30-min TTL. Surviving a full destroy would let a
# stale marker silently defer selfheal on the fresh index for up to
# 30 minutes — same lifecycle bug as the other markers above.
RECOVERY_MARKERS = [
    ".pipeline_clean_shutdown",
    "pipeline_state.json",
    ".guard_rejections.json",
]

ALL_DATA_FILES = TRACE_FILES + INDEX_FILES + RECOVERY_MARKERS


# ── Pydantic models ─────────────────────────────────────────────

class TraceSearchRequest(BaseModel):
    query: str
    kinds: Optional[List[str]] = None
    limit: int = 20


class TraceIgnoreRequest(BaseModel):
    action: str  # "add" | "remove"
    patterns: List[str]


class AugmentRequest(BaseModel):
    max_items: Optional[int] = None


class DeepAnalysisRequest(BaseModel):
    max_items: Optional[int] = None
    max_tokens: Optional[int] = None
    max_minutes: Optional[int] = None


class EpistemicRunRequest(BaseModel):
    max_items: Optional[int] = None


class DeepeningRunRequest(BaseModel):
    max_iterations: Optional[int] = 10
    batch_size: Optional[int] = 20


class LSPEdge(BaseModel):
    source: str
    target: str
    kind: str = "calls"
    metadata: Optional[Dict[str, Any]] = None


class LSPEdgesRequest(BaseModel):
    edges: List[LSPEdge]


class ExternalEdge(BaseModel):
    source: str
    target: str
    kind: str
    origin: str = "external"
    metadata: Optional[Dict[str, Any]] = None


class ExternalEdgesRequest(BaseModel):
    edges: List[ExternalEdge]
    replace_origin: Optional[str] = None
