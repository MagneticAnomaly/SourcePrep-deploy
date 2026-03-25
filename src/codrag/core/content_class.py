"""Content classification for Phase 53: Refine Code/Language Treatment.

Replaces the binary is_markdown split with a 3-class taxonomy based on
extractable structure density rather than file extension.

Classification uses metadata already populated by the Rust parser (section_count,
ref_count, link_count, line_count) — no Rust changes required.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ContentClass(str, Enum):
    """Content classification for treatment routing.

    Each class maps to a different TreatmentConfig via TreatmentRegistry.
    """

    STRUCTURED_CODE = "structured_code"
    """Source code files with AST-extractable structure (imports, symbols)."""

    STRUCTURED_DOCS = "structured_docs"
    """Documentation files with rich section hierarchy and cross-references.
    Examples: API docs, technical specs, implementation plans with many sections
    and backtick file references."""

    UNSTRUCTURED_NARRATIVE = "unstructured_narrative"
    """Minimal-structure content: marketing copy, changelogs, simple READMEs.
    These files cause batch parse failures when given complex doc prompts."""


# File extensions that are always classified as STRUCTURED_CODE regardless
# of content analysis (they're non-markdown, non-data files).
_CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".swift", ".kt", ".cs", ".rb",
    ".php", ".dart", ".scala", ".sh", ".lua", ".zig", ".ex", ".exs",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",  # config = code treatment
    ".csv", ".tsv", ".jsonl",  # data = code treatment (conservative)
})

# Thresholds for structured docs classification.
# A markdown file needs BOTH high ref_count AND high section_count
# to be classified as StructuredDocs (API docs, technical specs).
_STRUCTURED_DOCS_MIN_REF_COUNT = 3
_STRUCTURED_DOCS_MIN_SECTION_COUNT = 5


def classify_node(node: Dict[str, Any]) -> ContentClass:
    """Classify a single trace node into a ContentClass.

    Uses existing Rust-populated metadata on the node:
    - ``language``: detected language string
    - ``file_path``: repo-relative path
    - ``metadata.section_count``: number of markdown headers
    - ``metadata.ref_count``: number of backtick file references
    - ``metadata.link_count``: number of markdown links

    Args:
        node: A trace node dict from trace_nodes.jsonl.

    Returns:
        The determined ContentClass for routing to TreatmentRegistry.
    """
    lang = node.get("language", "")
    file_path = node.get("file_path", "")

    # Fast path: non-markdown files are always code
    is_md = lang == "markdown" or file_path.endswith((".md", ".markdown"))
    if not is_md:
        return ContentClass.STRUCTURED_CODE

    # Markdown files: classify by structure density from Rust metadata
    metadata = node.get("metadata", {})
    section_count = metadata.get("section_count", 0) or 0
    ref_count = metadata.get("ref_count", 0) or 0

    if (
        ref_count >= _STRUCTURED_DOCS_MIN_REF_COUNT
        and section_count >= _STRUCTURED_DOCS_MIN_SECTION_COUNT
    ):
        return ContentClass.STRUCTURED_DOCS

    return ContentClass.UNSTRUCTURED_NARRATIVE


def classify_nodes(
    nodes: List[Dict[str, Any]],
) -> Dict[ContentClass, List[Dict[str, Any]]]:
    """Classify a list of trace nodes into groups by ContentClass.

    Args:
        nodes: List of trace node dicts.

    Returns:
        Dict mapping each ContentClass to its list of nodes.
    """
    groups: Dict[ContentClass, List[Dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        cc = classify_node(node)
        groups[cc].append(node)

    if logger.isEnabledFor(logging.INFO):
        parts = [f"{cc.value}={len(ns)}" for cc, ns in sorted(groups.items(), key=lambda x: x[0].value)]
        logger.info("Content classification: %s", ", ".join(parts))

    return groups
