"""
AuditContext loader for CoDRAG (Phase 43).

Reads all trace graph data into memory once, providing a unified
context object that all analyzers share.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import AuditContext

logger = logging.getLogger(__name__)


def load_audit_context(
    index_dir: Path,
    project_root: Optional[Path] = None,
) -> AuditContext:
    """Load all graph data from disk into an AuditContext.

    Reads:
      - trace_nodes.jsonl
      - trace_edges.jsonl + trace_inferred_edges.jsonl + trace_lsp_edges.jsonl
      - trace_augmented.jsonl
      - trace_epistemic.jsonl
      - trace_modules.jsonl
      - atlas.json
      - trace_manifest.json (for file_hashes)
    """
    index_dir = Path(index_dir).resolve()
    ctx = AuditContext(
        project_root=Path(project_root).resolve() if project_root else None,
        index_dir=index_dir,
    )

    # Nodes
    nodes_path = index_dir / "trace_nodes.jsonl"
    if nodes_path.exists():
        ctx.nodes = _load_jsonl_dict(nodes_path, key="id")
        logger.debug("Loaded %d nodes", len(ctx.nodes))

    # Edges (static + inferred + LSP)
    edges: List[Dict[str, Any]] = []
    for edge_file in ("trace_edges.jsonl", "trace_inferred_edges.jsonl", "trace_lsp_edges.jsonl"):
        p = index_dir / edge_file
        if p.exists():
            file_edges = _load_jsonl_list(p)
            edges.extend(file_edges)
            logger.debug("Loaded %d edges from %s", len(file_edges), edge_file)
    ctx.edges = edges

    # Augmentations
    aug_path = index_dir / "trace_augmented.jsonl"
    if aug_path.exists():
        ctx.augmentations = _load_jsonl_dict(aug_path, key="node_id")
        logger.debug("Loaded %d augmentations", len(ctx.augmentations))

    # Epistemic enrichment
    epi_path = index_dir / "trace_epistemic.jsonl"
    if epi_path.exists():
        ctx.epistemic = _load_jsonl_dict(epi_path, key="node_id")
        logger.debug("Loaded %d epistemic entries", len(ctx.epistemic))

    # Modules
    mod_path = index_dir / "trace_modules.jsonl"
    if mod_path.exists():
        ctx.modules = _load_jsonl_list(mod_path)
        logger.debug("Loaded %d modules", len(ctx.modules))

    # Atlas
    atlas_path = index_dir / "atlas.json"
    if atlas_path.exists():
        try:
            with open(atlas_path, "r", encoding="utf-8") as f:
                ctx.atlas = json.load(f)
            logger.debug("Loaded atlas")
        except Exception as e:
            logger.warning("Failed to load atlas: %s", e)

    # File hashes from manifest
    manifest_path = index_dir / "trace_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            ctx.file_hashes = manifest.get("file_hashes") or {}
            logger.debug("Loaded %d file hashes", len(ctx.file_hashes))
        except Exception as e:
            logger.warning("Failed to load manifest: %s", e)

    return ctx


def _load_jsonl_dict(path: Path, key: str) -> Dict[str, Dict[str, Any]]:
    """Load a JSONL file into a dict keyed by the given field."""
    result: Dict[str, Dict[str, Any]] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    k = obj.get(key, "")
                    if k:
                        result[k] = obj
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.warning("Failed to load %s: %s", path, e)
    return result


def _load_jsonl_list(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    result: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    result.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.warning("Failed to load %s: %s", path, e)
    return result
