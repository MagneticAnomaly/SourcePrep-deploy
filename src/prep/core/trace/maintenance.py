"""
Trace artifact maintenance — prune orphan entries from enrichment files.

Enrichment artifacts (trace_epistemic.jsonl, trace_augmented.jsonl,
knowledge_documents.json + knowledge_embeddings.npy) are append-only.
When the trace scope changes (files excluded/deleted), old entries
remain as orphans. This module prunes them.
"""
from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def _load_current_node_ids(index_dir: Path) -> Set[str]:
    """Load the set of node IDs from the current trace_nodes.jsonl."""
    nodes_path = index_dir / "trace_nodes.jsonl"
    if not nodes_path.exists():
        return set()
    ids: Set[str] = set()
    with open(nodes_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


def _prune_jsonl(path: Path, node_ids: Set[str], id_field: str = "node_id") -> Tuple[int, int]:
    """Remove lines from a JSONL file whose id_field is not in node_ids.

    Returns (kept, pruned) counts.
    """
    if not path.exists():
        return 0, 0

    kept_lines: list[str] = []
    pruned = 0
    seen: Set[str] = set()

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                nid = json.loads(stripped)[id_field]
            except (json.JSONDecodeError, KeyError):
                kept_lines.append(stripped)
                continue
            if nid in node_ids and nid not in seen:
                seen.add(nid)
                kept_lines.append(stripped)
            else:
                pruned += 1

    if pruned > 0:
        tmp = path.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for line in kept_lines:
                f.write(line + "\n")
        tmp.replace(path)

    return len(kept_lines), pruned


def _prune_knowledge(index_dir: Path, node_ids: Set[str]) -> Tuple[int, int]:
    """Prune knowledge_documents.json and knowledge_embeddings.npy together.

    Removes documents whose source_id doesn't map to a current node.
    Keeps embeddings positionally aligned with documents.

    Returns (kept, pruned) counts.
    """
    docs_path = index_dir / "knowledge_documents.json"
    emb_path = index_dir / "knowledge_embeddings.npy"

    if not docs_path.exists():
        return 0, 0

    with open(docs_path, "r", encoding="utf-8") as f:
        docs = json.load(f)

    has_embeddings = emb_path.exists()
    embeddings = None
    if has_embeddings:
        embeddings = np.load(emb_path)
        if embeddings.shape[0] != len(docs):
            logger.warning(
                "knowledge docs/embeddings length mismatch (%d vs %d), skipping prune",
                len(docs), embeddings.shape[0],
            )
            return len(docs), 0

    keep_indices: list[int] = []
    for i, doc in enumerate(docs):
        src = doc.get("source_id", "")
        if src in node_ids:
            keep_indices.append(i)
        elif src.startswith("file:") and f"file:{src[5:]}" not in node_ids:
            continue
        elif src.startswith("sym:"):
            at_idx = src.find("@")
            if at_idx >= 0:
                rest = src[at_idx + 1:]
                colon_idx = rest.rfind(":")
                file_path = rest[:colon_idx] if colon_idx > 0 else rest
                if f"file:{file_path}" in node_ids:
                    keep_indices.append(i)
                    continue
            continue
        else:
            keep_indices.append(i)

    pruned = len(docs) - len(keep_indices)
    if pruned == 0:
        return len(docs), 0

    new_docs = [docs[i] for i in keep_indices]

    tmp_dir = Path(tempfile.mkdtemp(dir=index_dir.parent, prefix=".prune_knowledge_"))
    try:
        with open(tmp_dir / "knowledge_documents.json", "w", encoding="utf-8") as f:
            json.dump(new_docs, f)

        if embeddings is not None:
            new_emb = embeddings[keep_indices]
            np.save(tmp_dir / "knowledge_embeddings.npy", new_emb)

        for fname in ("knowledge_documents.json", "knowledge_embeddings.npy"):
            src = tmp_dir / fname
            dst = index_dir / fname
            if src.exists():
                if dst.exists():
                    dst.unlink()
                shutil.move(str(src), str(dst))
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return len(new_docs), pruned


def prune_orphan_enrichments(index_dir: Path) -> Dict[str, Any]:
    """Prune orphan entries from all enrichment artifacts.

    Compares node_ids in each enrichment file against the current
    trace_nodes.jsonl and removes entries that reference nodes no
    longer in the graph.

    Safe to call at any time — idempotent and atomic per file.
    """
    node_ids = _load_current_node_ids(index_dir)
    if not node_ids:
        logger.info("No trace nodes found in %s, skipping prune", index_dir)
        return {"skipped": True, "reason": "no_trace_nodes"}

    results: Dict[str, Any] = {}

    epistemic_kept, epistemic_pruned = _prune_jsonl(
        index_dir / "trace_epistemic.jsonl", node_ids,
    )
    results["epistemic"] = {"kept": epistemic_kept, "pruned": epistemic_pruned}

    augmented_kept, augmented_pruned = _prune_jsonl(
        index_dir / "trace_augmented.jsonl", node_ids,
    )
    results["augmented"] = {"kept": augmented_kept, "pruned": augmented_pruned}

    knowledge_kept, knowledge_pruned = _prune_knowledge(index_dir, node_ids)
    results["knowledge"] = {"kept": knowledge_kept, "pruned": knowledge_pruned}

    total_pruned = epistemic_pruned + augmented_pruned + knowledge_pruned
    results["total_pruned"] = total_pruned

    if total_pruned > 0:
        logger.info(
            "Pruned %d orphan enrichments from %s "
            "(epistemic=%d, augmented=%d, knowledge=%d)",
            total_pruned, index_dir,
            epistemic_pruned, augmented_pruned, knowledge_pruned,
        )
    else:
        logger.debug("No orphan enrichments found in %s", index_dir)

    return results
