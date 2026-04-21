"""Shared trace-output loaders.

Readers of `trace_nodes.jsonl` must apply the live `effective_excludes()`
so that an upgraded policy (e.g. a new default added in a later CoDRAG
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
