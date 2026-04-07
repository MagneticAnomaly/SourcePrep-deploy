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

ALL_DATA_FILES = TRACE_FILES + INDEX_FILES


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
