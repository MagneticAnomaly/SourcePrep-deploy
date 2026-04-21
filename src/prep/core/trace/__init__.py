"""
Trace Index subsystem for CoDRAG.

Re-exports all public symbols so that ``from codrag.core.trace import X``
continues to work after the split into a subpackage.
"""
from .models import (
    TraceNode,
    TraceEdge,
    FileError,
    TraceBuildResult,
    TRACE_MANIFEST_VERSION,
    PYTHON_EXTENSIONS,
    TYPESCRIPT_EXTENSIONS,
    GO_EXTENSIONS,
    RUST_EXTENSIONS,
    JAVA_EXTENSIONS,
    CPP_EXTENSIONS,
    SWIFT_EXTENSIONS,
    MARKDOWN_EXTENSIONS,
    KOTLIN_EXTENSIONS,
    CSHARP_EXTENSIONS,
    RUBY_EXTENSIONS,
    PHP_EXTENSIONS,
    DART_EXTENSIONS,
    SCALA_EXTENSIONS,
    SHELL_EXTENSIONS,
    LUA_EXTENSIONS,
    ZIG_EXTENSIONS,
    ELIXIR_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    SUPPORTED_LANGUAGES,
)
from .utils import _detect_language, _to_posix, _is_relevant
from .builder import TraceBuilder, build_trace
from .index import TraceIndex
from .coverage import compute_trace_coverage
from .maintenance import prune_orphan_enrichments

# Analyzers are internal but re-exported for backward compat
from .analyzers import PythonAnalyzer, SwiftAnalyzer, GenericRegexAnalyzer, JSAnalyzer

__all__ = [
    "TraceNode",
    "TraceEdge",
    "FileError",
    "TraceBuildResult",
    "TraceBuilder",
    "TraceIndex",
    "build_trace",
    "compute_trace_coverage",
    "PythonAnalyzer",
    "SwiftAnalyzer",
    "GenericRegexAnalyzer",
    "JSAnalyzer",
    "TRACE_MANIFEST_VERSION",
    "SUPPORTED_EXTENSIONS",
    "SUPPORTED_LANGUAGES",
    "_detect_language",
    "_to_posix",
    "_is_relevant",
    "prune_orphan_enrichments",
]
