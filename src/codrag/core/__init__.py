"""
CoDRAG Core Engine.

Contains the main components:
- CodeIndex: Hybrid semantic + keyword search index
- Embedder: Embedding abstraction (OllamaEmbedder)
- Chunking: Document chunking strategies

Engine selection:
- Set CODRAG_ENGINE=rust to force the Rust engine (codrag_engine via PyO3)
- Set CODRAG_ENGINE=python to force the Python fallback
- Default: auto-detect (use Rust if available, else Python)
"""

import logging
import os

_logger = logging.getLogger(__name__)

# --- Engine detection ---
_engine_preference = os.environ.get("CODRAG_ENGINE", "auto").lower()

try:
    import codrag_engine as _rust_engine

    _RUST_AVAILABLE = True
    _RUST_VERSION = _rust_engine.version()
except ImportError:
    _RUST_AVAILABLE = False
    _RUST_VERSION = None
    _rust_engine = None

if _engine_preference == "rust" and not _RUST_AVAILABLE:
    _logger.warning("CODRAG_ENGINE=rust but codrag_engine not installed; falling back to Python")

if _engine_preference == "rust" and _RUST_AVAILABLE:
    ENGINE = "rust"
elif _engine_preference == "python":
    ENGINE = "python"
elif _engine_preference == "auto" and _RUST_AVAILABLE:
    ENGINE = "rust"
else:
    ENGINE = "python"

if ENGINE == "rust":
    _logger.info("Using Rust engine: %s", _RUST_VERSION)
else:
    if _RUST_AVAILABLE:
        _logger.info("Using Python engine (Rust available but not selected)")
    else:
        _logger.debug("Using Python engine (codrag_engine not installed)")

from .embedder import Embedder, OllamaEmbedder, NativeEmbedder, FakeEmbedder, EmbeddingResult
from .chunking import Chunk, chunk_markdown, chunk_code
from .compressor import ContextCompressor, ClaraCompressor, NoopCompressor, CompressResult
from .index import CodeIndex, SearchResult
from .trace import TraceBuilder, TraceIndex, TraceNode, TraceEdge, build_trace
from .augmenter import TraceAugmenter, LLMClient, AugmentationEntry, AugmentResult
from .deep_analysis import DeepAnalysisOrchestrator, DeepAnalysisSchedule, DeepAnalysisResult
from .epistemic_score import EpistemicScore, EpistemicEntry, compute_epistemic_score, apply_decay
from .epistemic_enrichment import EpistemicEnricher, topological_sort_files
from .cluster import ClusterSynthesizer, ModuleEntry, build_clusters
from .deepening import DeepeningLoop, EnrichmentQueue, DriftDetector, ConvergenceTracker
from .knowledge_index import KnowledgeIndex

__all__ = [
    "ENGINE",
    "CodeIndex",
    "SearchResult",
    "Embedder",
    "EpistemicEnricher",
    "ClusterSynthesizer",
    "DeepeningLoop",
    "KnowledgeIndex",
    "EmbeddingResult",
    "ContextCompressor",
    "ClaraCompressor",
    "NoopCompressor",
    "CompressResult",
    "Chunk",
    "chunk_markdown",
    "chunk_code",
    "TraceBuilder",
    "TraceIndex",
    "TraceNode",
    "TraceEdge",
    "build_trace",
    "TraceAugmenter",
    "LLMClient",
    "AugmentationEntry",
    "AugmentResult",
    "DeepAnalysisOrchestrator",
    "DeepAnalysisSchedule",
    "DeepAnalysisResult",
]
