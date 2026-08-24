"""Shared trace-output loaders.

Readers of `trace_nodes.jsonl` must apply the live `effective_excludes()`
so that an upgraded policy (e.g. a new default added in a later Prep
version) takes effect immediately, without waiting for the trace builder
to rewrite the .jsonl.

Three callers share this contract:
- `core/augmenter.py::Augmenter.load_trace_nodes`
- `core/epistemic_enrichment.py::EpistemicEnricher.load_trace_nodes`
- `api/routers/projects/search.py::_load_trace_nodes_for_project`

Plus a fallback path in `core/atlas/role_projection.py::_load_trace_nodes`.

Keep the filter body in one place so a future policy contract change
lands at every callsite at once.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


def load_filtered_trace_nodes(
    index_dir: Path,
    repo_root: Path,
    *,
    trace_ignore_patterns: Optional[Iterable[str]] = None,
    warn_label: str = "trace_nodes",
) -> List[Dict[str, Any]]:
    """Load `trace_nodes.jsonl` and drop nodes matching current excludes.

    When `trace_ignore_patterns` is None the loader auto-resolves L3 via
    `project_registry.trace_ignore_patterns_for_index(index_dir)`. Pass
    an empty list explicitly to opt out (e.g. to avoid a registry lookup
    in a hot path where L3 is already known to be unset).

    `warn_label` tags the log line so the reader sees which loader
    surfaced the stale content.
    """
    import pathspec

    from prep.core.repo_policy import effective_excludes

    nodes_path = Path(index_dir) / "trace_nodes.jsonl"
    nodes: List[Dict[str, Any]] = []
    if not nodes_path.exists():
        return nodes

    if trace_ignore_patterns is None:
        from prep.core.project_registry import trace_ignore_patterns_for_index
        extra = trace_ignore_patterns_for_index(Path(index_dir)) or None
    else:
        extra = list(trace_ignore_patterns) or None

    exclude_globs = effective_excludes(
        index_dir=Path(index_dir),
        repo_root=Path(repo_root),
        trace_ignore_patterns=extra,
    )
    spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_globs)

    dropped = 0
    with open(nodes_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            node = json.loads(line)
            path = node.get("path") or node.get("file_path") or ""
            if path and spec.match_file(path):
                dropped += 1
                continue
            nodes.append(node)

    if dropped:
        logger.info(
            "%s: dropped %d node(s) matching current exclude globs "
            "(trace_nodes.jsonl predates current policy — will reconcile on next rebuild)",
            warn_label,
            dropped,
        )
    return nodes


# ── Build-time edge loading (scrutiny C2, 2026-08-24) ──────────

# Edge files the build pipeline reads, in load order. External edges are
# LAST so their origin tag can't be confused with pipeline-produced edges.
_BUILD_EDGE_FILES = ("trace_edges.jsonl", "trace_inferred_edges.jsonl")
_EXTERNAL_EDGES_FILE = "trace_external_edges.jsonl"

# Tag key marking which file an edge dict came from. Leading underscore:
# reserved, never emitted by the parsers; the external-edges endpoint's own
# top-level "origin" field (e.g. "config") is left untouched.
EDGE_SOURCE_FILE_KEY = "_edge_source_file"


def load_all_build_edges(index_dir: Path) -> List[Dict[str, Any]]:
    """Load every edge the build pipeline reasons over.

    Reads ``trace_edges.jsonl`` + ``trace_inferred_edges.jsonl`` +
    ``trace_external_edges.jsonl`` from ``index_dir`` and returns them as
    one list, each dict tagged with ``EDGE_SOURCE_FILE_KEY`` naming its
    origin file.

    Why this exists: before 2026-08-24 NO build stage read the external
    file — external edges were a write/query-time-only feature (consumed by
    ``TraceIndex`` for retrieval). Files with no grammar (system config:
    .service/.conf/.plist/fstab) have no structural edges, so their ONLY
    graph connections are pushed externally — and clustering /
    group_reasoning never saw them, leaving every such file a singleton
    cluster dropped by min_group_size (scrutiny C2/C3).

    Parse policy differs by file ownership:
    - The two pipeline-owned files keep STRICT parsing (json.loads raises
      on a malformed line) — they're written atomically by the pipeline, so
      a corrupt line signals real damage and should fail loudly, exactly
      as the per-engine loaders behaved before this consolidation.
    - The external file is TOLERANT — malformed lines are skipped with a
      warning. It is rewritten/extended by the (non-atomic) ingestion
      endpoint, so a partial write must not take down clustering.
    """
    index_dir = Path(index_dir)
    edges: List[Dict[str, Any]] = []

    for fname in _BUILD_EDGE_FILES:
        path = index_dir / fname
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                edge = json.loads(line)  # strict — see docstring
                if isinstance(edge, dict):
                    edge[EDGE_SOURCE_FILE_KEY] = fname
                    edges.append(edge)

    ext_path = index_dir / _EXTERNAL_EDGES_FILE
    if ext_path.exists():
        bad = 0
        with open(ext_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    edge = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                if not isinstance(edge, dict):
                    bad += 1
                    continue
                edge[EDGE_SOURCE_FILE_KEY] = _EXTERNAL_EDGES_FILE
                edges.append(edge)
        if bad:
            logger.warning(
                "load_all_build_edges: skipped %d malformed line(s) in %s "
                "(possible partial write by the ingestion endpoint)",
                bad, ext_path,
            )

    return edges

