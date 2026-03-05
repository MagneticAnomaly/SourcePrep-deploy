"""
Trace router subpackage — assembles query and enrichment sub-routers.

The composite ``router`` object replaces the original ``trace.py`` router.
"""
from fastapi import APIRouter

from . import query, enrichment

router = APIRouter()

router.include_router(query.router)
router.include_router(enrichment.router)

# ── Backward-compat re-exports ────────────────────────────────────
from .shared import (  # noqa: F401
    _deep_analysis_state,
    _epistemic_state,
    _cluster_state,
    _deepening_state,
    TRACE_FILES,
    INDEX_FILES,
    ALL_DATA_FILES,
    TraceSearchRequest,
    TraceIgnoreRequest,
    AugmentRequest,
    DeepAnalysisRequest,
    EpistemicRunRequest,
    DeepeningRunRequest,
    LSPEdge,
    LSPEdgesRequest,
)
