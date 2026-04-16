"""
Cluster Synthesis for CoDRAG (Pass 3).

Groups enriched file nodes into subsystem clusters based on domain_tags
and graph connectivity. For each cluster, generates a module-level
summary using the deep reasoning model.

Creates virtual `module:*` nodes in the graph that represent subsystem-level
understanding — answering questions like "what is the ad-framework subsystem?"
without needing to enumerate individual files.

See docs/Phase22_trace-epistomology/PATH_FORWARD.md Sprint 5.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from codrag.core.context_config import PipelineTask, compute_optimal_settings
from codrag.core.llm_client import TASK_MAX_CHARS, batched_max_chars
from codrag.services.pipeline.workers import WorkerFactory

from .epistemic_score import EpistemicEntry
from .llm_client import LLMClient, _get_llm_concurrency, _parse_confidence, _parse_json_response
from .swarm_orchestrator import SwarmOrchestrator, SwarmResult, WorkerAssignment, WorkItem
from .swarm_registry import get_min_groups_threshold, get_swarm_tier

logger = logging.getLogger(__name__)

# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class ModuleEntry:
    """A synthesized module representing a subsystem cluster."""
    module_id: str
    name: str
    summary: str
    member_files: List[str]
    domain_tags: List[str]
    architecture_layers: List[str]
    component_status: str
    data_flow: Optional[str] = None
    dependencies: Optional[List[str]] = None
    tech_debt_summary: Optional[str] = None
    file_count: int = 0
    avg_epistemic_confidence: float = 0.0
    synthesized_at: str = ""
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "module_id": self.module_id,
            "name": self.name,
            "summary": self.summary,
            "member_files": self.member_files,
            "domain_tags": self.domain_tags,
            "architecture_layers": self.architecture_layers,
            "component_status": self.component_status,
            "file_count": self.file_count,
            "avg_epistemic_confidence": round(self.avg_epistemic_confidence, 3),
            "synthesized_at": self.synthesized_at,
            "model": self.model,
        }
        if self.data_flow:
            d["data_flow"] = self.data_flow
        if self.dependencies:
            d["dependencies"] = self.dependencies
        if self.tech_debt_summary:
            d["tech_debt_summary"] = self.tech_debt_summary
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModuleEntry":
        return cls(
            module_id=d["module_id"],
            name=d.get("name", ""),
            summary=d.get("summary", ""),
            member_files=d.get("member_files", []),
            domain_tags=d.get("domain_tags", []),
            architecture_layers=d.get("architecture_layers", []),
            component_status=d.get("component_status", "unknown"),
            data_flow=d.get("data_flow"),
            dependencies=d.get("dependencies"),
            tech_debt_summary=d.get("tech_debt_summary"),
            file_count=int(d.get("file_count", 0)),
            avg_epistemic_confidence=_parse_confidence(d.get("avg_epistemic_confidence"), 0.0),
            synthesized_at=d.get("synthesized_at", ""),
            model=d.get("model", ""),
        )


@dataclass
class Cluster:
    """An intermediate cluster before synthesis."""
    cluster_id: str
    primary_tag: str
    member_node_ids: List[str]
    all_tags: Set[str] = field(default_factory=set)


# ── Prompt templates ─────────────────────────────────────────────────

MODULE_SYNTHESIS_SYSTEM = """You are an expert software architect synthesizing a high-level understanding of a subsystem.
You produce structured, accurate module-level summaries grounded in the enriched file descriptions.
You MUST respond with valid JSON only."""

MODULE_SYNTHESIS_PROMPT = """Synthesize a module-level understanding of this subsystem cluster.

Cluster name: {cluster_name}
Domain tags: {domain_tags}
File count: {file_count}

Member files and their enriched summaries:
{member_summaries}

Inter-cluster dependencies (files outside this cluster that members reference):
{external_deps}

Respond with this exact JSON format:
{{"name": "human-readable subsystem name",
"summary": "2-4 sentence description of what this subsystem does, its role in the codebase, and its current state",
"component_status": "complete|partial|stubbed|deprecated",
"data_flow": "brief description of how data flows through this subsystem",
"dependencies": ["other-subsystem-1", "other-subsystem-2"],
"tech_debt_summary": "brief summary of tech debt across the subsystem, or null if none"}}

NAMING RULES for "name":
- Must be SPECIFIC and DESCRIPTIVE.
- For clusters with 1-3 files, derive the name from the most prominent file's purpose.
- Each module name must be UNIQUE — no two modules should have similar names.

GOOD name examples:
- "LLM Concurrency Scheduler" (not "Core Module")
- "Pipeline Stage Orchestrator" (not "Pipeline Subsystem")
- "Trace Graph Builder" (not "Data Processing")
- "VS Code RAG Integration" (not "Extension")
- "Architecture Diagram React Components" (not "UI Subsystem")

ANTI-PATTERNS (never produce these):
- Generic labels: "UI Subsystem", "Config Module", "Data Layer", "Testing Framework"
- Numbered clones: "UI Subsystem #2", "Config (Packages) #3"
- Single-word names: "Dashboard", "Pipeline", "Utils"
- Names that restate the directory path: "Packages UI" for packages/ui/

SUMMARY RULES:
- Lead with WHAT the subsystem does, not what files it contains.
- Bad: "Contains 15 TypeScript files related to UI components."
- Good: "Renders the interactive architecture diagram with semantic zoom, breadcrumb navigation, and annotation overlays. Built on React Flow with custom layout algorithms."

EXAMPLE — given a cluster with 4 files (scheduler.py, worker_pool.py, job_queue.py, priority.py) in a pipeline domain, a good response is:
{{"name": "Pipeline Job Scheduler & Worker Pool",
"summary": "Manages concurrent pipeline job execution with priority queuing and worker lifecycle. Distributes enrichment tasks across a configurable thread pool, enforces per-stage ordering constraints, and provides graceful shutdown with in-flight job draining.",
"component_status": "complete",
"data_flow": "Jobs enter via job_queue → priority sorting → worker_pool dispatches to available workers → scheduler monitors completion and triggers dependent stages",
"dependencies": ["pipeline-orchestrator", "llm-client"],
"tech_debt_summary": "Worker pool size is hardcoded; should be configurable per deployment."}}

Where component_status describes the overall implementation completeness of this subsystem.

JSON response:"""


# ── Clustering algorithm ─────────────────────────────────────────────

# Maximum fraction of project files a single cluster may contain before splitting
MAX_CLUSTER_FRACTION = 0.40
# Absolute cap — any cluster above this size gets split regardless of project size
MAX_CLUSTER_ABS = 50


def build_clusters(
    epistemic_entries: Dict[str, EpistemicEntry],
    edges: List[Dict[str, Any]],
    min_cluster_size: int = 2,
    max_cluster_fraction: float = MAX_CLUSTER_FRACTION,
    max_cluster_abs: int = MAX_CLUSTER_ABS,
) -> List[Cluster]:
    """Group enriched file nodes into clusters by domain_tags + connectivity.

    Algorithm:
    1. Group nodes by their primary domain tag (first tag in domain_tags).
    2. Within each tag group, run connected-component analysis using
       structural + inferred edges to split disconnected subgroups.
    3. Merge small clusters (< min_cluster_size) into nearest neighbor.
    4. Split oversized clusters that exceed max_cluster_fraction or max_cluster_abs (CL-2).

    Returns list of Cluster objects.
    """
    # Step 1: Group by primary domain tag
    tag_groups: Dict[str, List[str]] = defaultdict(list)
    for node_id, entry in epistemic_entries.items():
        if not node_id.startswith("file:"):
            continue
        if entry.domain_tags:
            primary = entry.domain_tags[0]
        else:
            primary = "uncategorized"
        tag_groups[primary].append(node_id)

    # Build adjacency for connectivity analysis
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    file_ids = set(epistemic_entries.keys())
    for e in edges:
        src, tgt = e.get("source", ""), e.get("target", "")
        if src in file_ids and tgt in file_ids:
            adjacency[src].add(tgt)
            adjacency[tgt].add(src)

    # Step 2: Connected components within each tag group
    clusters: List[Cluster] = []
    cluster_idx = 0

    for tag, node_ids in tag_groups.items():
        components = _connected_components(node_ids, adjacency)
        for component in components:
            # Collect all tags for this component
            all_tags: Set[str] = set()
            for nid in component:
                entry = epistemic_entries.get(nid)
                if entry and entry.domain_tags:
                    all_tags.update(entry.domain_tags)

            clusters.append(Cluster(
                cluster_id=f"cluster:{tag}:{cluster_idx}",
                primary_tag=tag,
                member_node_ids=sorted(component),
                all_tags=all_tags,
            ))
            cluster_idx += 1

    # Step 3: Merge small clusters
    merged = _merge_small_clusters(clusters, adjacency, min_cluster_size)

    # Step 4 (CL-2): Split oversized clusters
    total_files = sum(1 for nid in epistemic_entries if nid.startswith("file:"))
    max_size = min(max_cluster_abs, max(min_cluster_size + 1, int(total_files * max_cluster_fraction)))
    split = _split_large_clusters(merged, adjacency, epistemic_entries, max_size)

    return split


def _connected_components(
    node_ids: List[str],
    adjacency: Dict[str, Set[str]],
) -> List[List[str]]:
    """Find connected components within a subset of nodes."""
    node_set = set(node_ids)
    visited: Set[str] = set()
    components: List[List[str]] = []

    for start in node_ids:
        if start in visited:
            continue
        # BFS
        component: List[str] = []
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neighbor in adjacency.get(node, set()):
                if neighbor in node_set and neighbor not in visited:
                    queue.append(neighbor)
        if component:
            components.append(component)

    return components


def _merge_small_clusters(
    clusters: List[Cluster],
    adjacency: Dict[str, Set[str]],
    min_size: int,
) -> List[Cluster]:
    """Merge clusters smaller than min_size into the nearest larger cluster."""
    if not clusters:
        return clusters

    large = [c for c in clusters if len(c.member_node_ids) >= min_size]
    small = [c for c in clusters if len(c.member_node_ids) < min_size]

    if not large:
        # All clusters are small — just return them as-is
        return clusters

    for sc in small:
        # Find the large cluster with the most edges to this small cluster
        best_cluster = None
        best_edges = 0
        sc_set = set(sc.member_node_ids)

        for lc in large:
            lc_set = set(lc.member_node_ids)
            edge_count = sum(
                1 for nid in sc.member_node_ids
                for neighbor in adjacency.get(nid, set())
                if neighbor in lc_set
            )
            if edge_count > best_edges:
                best_edges = edge_count
                best_cluster = lc

        if best_cluster:
            best_cluster.member_node_ids.extend(sc.member_node_ids)
            best_cluster.all_tags.update(sc.all_tags)
        else:
            # No connection — merge into the largest cluster
            largest = max(large, key=lambda c: len(c.member_node_ids))
            largest.member_node_ids.extend(sc.member_node_ids)
            largest.all_tags.update(sc.all_tags)

    return large


def _split_large_clusters(
    clusters: List[Cluster],
    adjacency: Dict[str, Set[str]],
    epistemic_entries: Dict[str, EpistemicEntry],
    max_size: int,
) -> List[Cluster]:
    """Recursively split clusters that exceed max_size (CL-2).

    Uses secondary domain tags to find natural split points within
    oversized clusters. Falls back to connected-component bisection
    if tag-based splitting doesn't reduce the size.
    """
    result: List[Cluster] = []
    split_idx = 0

    for cluster in clusters:
        if len(cluster.member_node_ids) <= max_size:
            result.append(cluster)
            continue

        # Try splitting by secondary domain tag
        sub_groups = _split_by_secondary_tag(cluster, epistemic_entries)

        if len(sub_groups) < 2:
            # Fallback: split by connected components within the cluster
            sub_groups = _connected_components(cluster.member_node_ids, adjacency)

        if len(sub_groups) < 2:
            # Cannot split further — keep as-is (rare edge case)
            result.append(cluster)
            continue

        for sub in sub_groups:
            sub_tags: Set[str] = set()
            for nid in sub:
                entry = epistemic_entries.get(nid)
                if entry and entry.domain_tags:
                    sub_tags.update(entry.domain_tags)

            # Determine a distinguishing tag for the sub-cluster
            primary = cluster.primary_tag
            extra_tags = sub_tags - {primary}
            if extra_tags:
                secondary = sorted(extra_tags)[0]
                sub_id = f"{cluster.cluster_id}:{secondary}:{split_idx}"
            else:
                sub_id = f"{cluster.cluster_id}:part{split_idx}"

            sub_cluster = Cluster(
                cluster_id=sub_id,
                primary_tag=primary,
                member_node_ids=sorted(sub),
                all_tags=sub_tags,
            )
            split_idx += 1

            # Recurse if still too large
            if len(sub_cluster.member_node_ids) > max_size:
                result.extend(
                    _split_large_clusters([sub_cluster], adjacency, epistemic_entries, max_size)
                )
            else:
                result.append(sub_cluster)

    return result


def _split_by_secondary_tag(
    cluster: Cluster,
    epistemic_entries: Dict[str, EpistemicEntry],
) -> List[List[str]]:
    """Split a cluster's members by their secondary (2nd) domain tag.

    Returns a list of member-ID groups. If all members share the same
    secondary tag (or have none), returns a single group (no split).
    """
    groups: Dict[str, List[str]] = defaultdict(list)
    for nid in cluster.member_node_ids:
        entry = epistemic_entries.get(nid)
        if entry and len(entry.domain_tags) >= 2:
            secondary = entry.domain_tags[1]
        elif entry and entry.domain_tags:
            secondary = entry.domain_tags[0]
        else:
            secondary = "_none"
        groups[secondary].append(nid)

    if len(groups) < 2:
        return [cluster.member_node_ids]
    return list(groups.values())


# ── Leiden-Based Clustering (CL-1, CL-3, CL-4, CL-5) ───────────────

# CL-5: Architecture layer classification patterns
_TEST_PATTERNS = {"test", "tests", "spec", "specs", "__tests__", "__test__", "e2e", "integration"}
_CONFIG_PATTERNS = {"config", "configs", "configuration", ".github", ".circleci"}
_DOCS_PATTERNS = {"docs", "doc", "documentation", "wiki"}


def _classify_layer(file_path: str) -> str:
    """CL-5: Classify a file into an architecture layer."""
    parts = file_path.lower().replace("\\", "/").split("/")
    for p in parts:
        if p in _TEST_PATTERNS or p.startswith("test_") or p.endswith("_test"):
            return "test"
        if p in _CONFIG_PATTERNS:
            return "config"
        if p in _DOCS_PATTERNS:
            return "docs"
    # Check file name patterns
    basename = parts[-1] if parts else ""
    if basename.startswith("test_") or basename.endswith("_test.py") or basename.endswith(".test.ts") or basename.endswith(".test.js") or basename.endswith(".spec.ts") or basename.endswith(".spec.js"):
        return "test"
    return "impl"


def _directory_distance(path_a: str, path_b: str) -> int:
    """CL-4: Compute directory distance between two file paths."""
    import os.path as osp
    dir_a = osp.dirname(path_a).split("/")
    dir_b = osp.dirname(path_b).split("/")
    # Find common prefix length
    common = 0
    for a_part, b_part in zip(dir_a, dir_b):
        if a_part == b_part:
            common += 1
        else:
            break
    return (len(dir_a) - common) + (len(dir_b) - common)


def _tag_jaccard(tags_a: List[str], tags_b: List[str]) -> float:
    """CL-3: Compute Jaccard similarity between two tag sets."""
    if not tags_a or not tags_b:
        return 0.0
    set_a, set_b = set(tags_a), set(tags_b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


def _leiden_available() -> bool:
    """Check if igraph + leidenalg are installed."""
    try:
        import igraph  # noqa: F401
        import leidenalg  # noqa: F401
        return True
    except ImportError:
        return False


def build_clusters_leiden(
    epistemic_entries: Dict[str, EpistemicEntry],
    edges: List[Dict[str, Any]],
    min_cluster_size: int = 2,
    max_cluster_fraction: float = MAX_CLUSTER_FRACTION,
    max_cluster_abs: int = MAX_CLUSTER_ABS,
    resolution: float = 1.0,
    dir_penalty_lambda: float = 0.3,
    tag_weight: float = 0.4,
    edge_weight: float = 0.6,
) -> List[Cluster]:
    """Leiden-based clustering with multi-tag affinity and structural priors.

    Integrates:
    - CL-1: Leiden algorithm for community detection
    - CL-3: Multi-tag Jaccard affinity as edge weights
    - CL-4: Directory distance penalty
    - CL-5: Architecture layer separation (test/impl/config/docs)

    Falls back to build_clusters() if igraph/leidenalg unavailable.
    """
    import math

    if not _leiden_available():
        logger.info("CL-1: igraph/leidenalg not available, falling back to tag-based clustering")
        return build_clusters(
            epistemic_entries, edges, min_cluster_size,
            max_cluster_fraction, max_cluster_abs,
        )

    import igraph as ig
    import leidenalg

    # Collect file nodes
    file_nodes = [
        nid for nid in epistemic_entries
        if nid.startswith("file:")
    ]
    if len(file_nodes) < 2:
        return []

    total_files = len(file_nodes)
    max_size = min(max_cluster_abs, max(min_cluster_size + 1, int(total_files * max_cluster_fraction)))
    node_to_idx = {nid: i for i, nid in enumerate(file_nodes)}

    # CL-5: Separate into architecture layers
    layer_map: Dict[str, str] = {}
    for nid in file_nodes:
        fp = nid[5:] if nid.startswith("file:") else nid
        layer_map[nid] = _classify_layer(fp)

    # Group by layer
    layer_groups: Dict[str, List[str]] = defaultdict(list)
    for nid in file_nodes:
        layer_groups[layer_map[nid]].append(nid)

    # Run Leiden per layer
    all_clusters: List[Cluster] = []
    cluster_idx = 0

    for layer, layer_nodes in layer_groups.items():
        if len(layer_nodes) < 2:
            # Single file — make its own cluster
            entry = epistemic_entries.get(layer_nodes[0])
            tag = entry.domain_tags[0] if entry and entry.domain_tags else "uncategorized"
            all_clusters.append(Cluster(
                cluster_id=f"cluster:{tag}:{layer}:{cluster_idx}",
                primary_tag=tag,
                member_node_ids=layer_nodes,
                all_tags=set(entry.domain_tags) if entry and entry.domain_tags else set(),
            ))
            cluster_idx += 1
            continue

        # Build weighted graph for this layer
        layer_set = set(layer_nodes)
        layer_idx = {nid: i for i, nid in enumerate(layer_nodes)}
        n = len(layer_nodes)

        # Start with edge-based adjacency
        edge_pairs: Dict[Tuple[int, int], float] = {}

        for e in edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            if src in layer_set and tgt in layer_set and src != tgt:
                i, j = layer_idx[src], layer_idx[tgt]
                if i > j:
                    i, j = j, i
                conf = _parse_confidence(e.get("metadata", {}).get("confidence", 0.5) if isinstance(e.get("metadata"), dict) else 0.5, 0.5)
                edge_pairs[(i, j)] = max(edge_pairs.get((i, j), 0.0), conf)

        # CL-3 + CL-4: Add tag affinity and directory prior edges
        # Only compute for nearby files to avoid O(n²) for large projects
        if n <= 200:
            for a_idx in range(n):
                nid_a = layer_nodes[a_idx]
                entry_a = epistemic_entries.get(nid_a)
                fp_a = nid_a[5:] if nid_a.startswith("file:") else nid_a
                tags_a = entry_a.domain_tags if entry_a and entry_a.domain_tags else []

                for b_idx in range(a_idx + 1, n):
                    nid_b = layer_nodes[b_idx]
                    entry_b = epistemic_entries.get(nid_b)
                    fp_b = nid_b[5:] if nid_b.startswith("file:") else nid_b
                    tags_b = entry_b.domain_tags if entry_b and entry_b.domain_tags else []

                    # CL-3: Tag affinity
                    tj = _tag_jaccard(tags_a, tags_b)

                    # CL-4: Directory distance penalty
                    dd = _directory_distance(fp_a, fp_b)
                    dir_factor = math.exp(-dir_penalty_lambda * dd)

                    # Combined affinity
                    existing_edge_w = edge_pairs.get((a_idx, b_idx), 0.0)
                    affinity = (
                        edge_weight * existing_edge_w +
                        tag_weight * tj * dir_factor
                    )

                    if affinity > 0.05:
                        edge_pairs[(a_idx, b_idx)] = affinity

        # Build igraph Graph
        g = ig.Graph(n=n, directed=False)
        if edge_pairs:
            sorted_edges = sorted(edge_pairs.keys())
            weights = [edge_pairs[e] for e in sorted_edges]
            g.add_edges(sorted_edges)
            g.es["weight"] = weights
        else:
            # No edges — fall back to connected components (each node is its own cluster)
            for nid in layer_nodes:
                entry = epistemic_entries.get(nid)
                tag = entry.domain_tags[0] if entry and entry.domain_tags else "uncategorized"
                all_clusters.append(Cluster(
                    cluster_id=f"cluster:{tag}:{layer}:{cluster_idx}",
                    primary_tag=tag,
                    member_node_ids=[nid],
                    all_tags=set(entry.domain_tags) if entry and entry.domain_tags else set(),
                ))
                cluster_idx += 1
            continue

        # Run Leiden
        try:
            partition = leidenalg.find_partition(
                g,
                leidenalg.RBConfigurationVertexPartition,
                weights="weight",
                resolution_parameter=resolution,
                n_iterations=-1,
            )
        except Exception as e:
            logger.warning("CL-1: Leiden failed for layer %s: %s, falling back", layer, e)
            # Fallback: each node is its own cluster
            for nid in layer_nodes:
                entry = epistemic_entries.get(nid)
                tag = entry.domain_tags[0] if entry and entry.domain_tags else "uncategorized"
                all_clusters.append(Cluster(
                    cluster_id=f"cluster:{tag}:{layer}:{cluster_idx}",
                    primary_tag=tag,
                    member_node_ids=[nid],
                    all_tags=set(entry.domain_tags) if entry and entry.domain_tags else set(),
                ))
                cluster_idx += 1
            continue

        # Convert partition to clusters
        for community in partition:
            member_nids = [layer_nodes[i] for i in community]
            if not member_nids:
                continue

            # Determine primary tag from majority vote
            tag_counts: Dict[str, int] = defaultdict(int)
            all_tags: Set[str] = set()
            for nid in member_nids:
                entry = epistemic_entries.get(nid)
                if entry and entry.domain_tags:
                    for t in entry.domain_tags:
                        tag_counts[t] += 1
                    all_tags.update(entry.domain_tags)

            primary_tag = max(tag_counts, key=tag_counts.get) if tag_counts else "uncategorized"

            # CL-5: Append layer suffix for non-impl layers
            layer_suffix = f" ({layer})" if layer != "impl" else ""

            all_clusters.append(Cluster(
                cluster_id=f"cluster:{primary_tag}{layer_suffix}:{cluster_idx}",
                primary_tag=primary_tag,
                member_node_ids=sorted(member_nids),
                all_tags=all_tags,
            ))
            cluster_idx += 1

    # Merge small clusters
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    file_ids = set(epistemic_entries.keys())
    for e in edges:
        src, tgt = e.get("source", ""), e.get("target", "")
        if src in file_ids and tgt in file_ids:
            adjacency[src].add(tgt)
            adjacency[tgt].add(src)

    merged = _merge_small_clusters(all_clusters, adjacency, min_cluster_size)

    # CL-2: Split oversized clusters (reuse existing logic)
    split = _split_large_clusters(merged, adjacency, epistemic_entries, max_size)

    logger.info(
        "CL-1: Leiden clustering produced %d clusters from %d files (%d layers)",
        len(split), total_files, len(layer_groups),
    )

    return split


# ── LLM-Free Structural Clustering Fallback (CL-10) ─────────────────

# Edge kind → weight for structural clustering (no LLM tags needed)
_STRUCTURAL_EDGE_WEIGHTS = {
    "imports": 1.0,
    "calls": 0.8,
    "inherits": 0.9,
    "implements": 0.9,
    "co_changes": 0.6,
    "co_located": 0.3,
    "contains": 0.0,  # file→symbol edges are not inter-file
}


def build_clusters_structural(
    file_paths: List[str],
    edges: List[Dict[str, Any]],
    min_cluster_size: int = 2,
    max_cluster_abs: int = MAX_CLUSTER_ABS,
    resolution: float = 0.8,
) -> List[Cluster]:
    """LLM-free clustering using only edge structure + directory naming.

    Usable before epistemic enrichment completes. Requires no domain tags.
    Uses Leiden if available, otherwise connected-components.

    Args:
        file_paths: List of repo-relative file paths.
        edges: Trace edges (dicts with source, target, kind, metadata).
        min_cluster_size: Merge clusters smaller than this.
        max_cluster_abs: Maximum cluster size before splitting.
        resolution: Leiden resolution parameter (lower = larger clusters).

    Returns:
        List of Cluster objects with directory-based names.
    """
    if len(file_paths) < 2:
        return []

    file_node_ids = [f"file:{fp}" for fp in file_paths]
    file_set = set(file_node_ids)
    node_to_idx = {nid: i for i, nid in enumerate(file_node_ids)}
    n = len(file_node_ids)

    # CL-5: Layer separation
    layer_map: Dict[str, str] = {}
    for fp in file_paths:
        layer_map[f"file:{fp}"] = _classify_layer(fp)

    layer_groups: Dict[str, List[str]] = defaultdict(list)
    for nid in file_node_ids:
        layer_groups[layer_map[nid]].append(nid)

    # Build weighted edge pairs
    all_clusters: List[Cluster] = []
    cluster_idx = 0

    for layer, layer_nodes in layer_groups.items():
        if len(layer_nodes) < 2:
            fp = layer_nodes[0][5:]
            import os.path as osp
            dir_name = osp.dirname(fp).split("/")[-1] or osp.splitext(osp.basename(fp))[0]
            all_clusters.append(Cluster(
                cluster_id=f"cluster:{dir_name}:{layer}:{cluster_idx}",
                primary_tag=dir_name,
                member_node_ids=layer_nodes,
                all_tags=set(),
            ))
            cluster_idx += 1
            continue

        layer_set = set(layer_nodes)
        layer_idx = {nid: i for i, nid in enumerate(layer_nodes)}
        ln = len(layer_nodes)

        edge_pairs: Dict[Tuple[int, int], float] = {}
        for e in edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            if src in layer_set and tgt in layer_set and src != tgt:
                i, j = layer_idx[src], layer_idx[tgt]
                if i > j:
                    i, j = j, i
                kind = e.get("kind", "")
                w = _STRUCTURAL_EDGE_WEIGHTS.get(kind, 0.3)
                conf = _parse_confidence(e.get("metadata", {}).get("confidence", 0.7) if isinstance(e.get("metadata"), dict) else 0.7, 0.7)
                edge_pairs[(i, j)] = max(edge_pairs.get((i, j), 0.0), w * conf)

        # Add directory-proximity implicit edges (CL-4 style)
        import math
        import os.path as osp
        for a_idx in range(min(ln, 200)):
            fp_a = layer_nodes[a_idx][5:]
            for b_idx in range(a_idx + 1, min(ln, 200)):
                fp_b = layer_nodes[b_idx][5:]
                dd = _directory_distance(fp_a, fp_b)
                if dd == 0:
                    # Same directory: add implicit proximity edge
                    existing = edge_pairs.get((a_idx, b_idx), 0.0)
                    edge_pairs[(a_idx, b_idx)] = max(existing, 0.25)

        if not edge_pairs:
            # No edges at all — group by directory
            dir_groups: Dict[str, List[str]] = defaultdict(list)
            for nid in layer_nodes:
                fp = nid[5:]
                d = osp.dirname(fp) or "root"
                dir_groups[d].append(nid)
            for d, members in dir_groups.items():
                dir_name = d.split("/")[-1] or "root"
                layer_suffix = f" ({layer})" if layer != "impl" else ""
                all_clusters.append(Cluster(
                    cluster_id=f"cluster:{dir_name}{layer_suffix}:{cluster_idx}",
                    primary_tag=dir_name,
                    member_node_ids=sorted(members),
                    all_tags=set(),
                ))
                cluster_idx += 1
            continue

        # Try Leiden, fall back to connected components
        communities: List[List[int]] = []
        if _leiden_available():
            import igraph as ig
            import leidenalg
            g = ig.Graph(n=ln, directed=False)
            sorted_ep = sorted(edge_pairs.keys())
            weights = [edge_pairs[ep] for ep in sorted_ep]
            g.add_edges(sorted_ep)
            g.es["weight"] = weights
            try:
                partition = leidenalg.find_partition(
                    g, leidenalg.RBConfigurationVertexPartition,
                    weights="weight", resolution_parameter=resolution,
                    n_iterations=-1,
                )
                communities = list(partition)
            except Exception:
                communities = []

        if not communities:
            # Fallback: connected components
            adjacency: Dict[str, Set[str]] = defaultdict(set)
            for (i, j) in edge_pairs:
                adjacency[layer_nodes[i]].add(layer_nodes[j])
                adjacency[layer_nodes[j]].add(layer_nodes[i])
            cc = _connected_components(layer_nodes, adjacency)
            communities = [[layer_nodes.index(nid) for nid in comp] for comp in cc]

        for community in communities:
            member_nids = [layer_nodes[i] for i in community]
            if not member_nids:
                continue

            # Name from majority directory
            dir_counts: Dict[str, int] = defaultdict(int)
            for nid in member_nids:
                fp = nid[5:]
                d = osp.dirname(fp).split("/")[-1] or osp.splitext(osp.basename(fp))[0]
                dir_counts[d] += 1
            primary_dir = max(dir_counts, key=dir_counts.get) if dir_counts else "misc"

            layer_suffix = f" ({layer})" if layer != "impl" else ""
            all_clusters.append(Cluster(
                cluster_id=f"cluster:{primary_dir}{layer_suffix}:{cluster_idx}",
                primary_tag=primary_dir,
                member_node_ids=sorted(member_nids),
                all_tags=set(),
            ))
            cluster_idx += 1

    # Merge small clusters
    adjacency_all: Dict[str, Set[str]] = defaultdict(set)
    for e in edges:
        src, tgt = e.get("source", ""), e.get("target", "")
        if src in file_set and tgt in file_set:
            adjacency_all[src].add(tgt)
            adjacency_all[tgt].add(src)

    merged = _merge_small_clusters(all_clusters, adjacency_all, min_cluster_size)

    logger.info("CL-10: Structural clustering produced %d clusters from %d files", len(merged), len(file_paths))
    return merged


# ── Name Deduplication (CL-9) ────────────────────────────────────────

def _deduplicate_module_names(modules: Dict[str, "ModuleEntry"]) -> None:
    """Detect and resolve duplicate module names by appending distinguishing suffixes.

    Mutates modules in-place. For duplicates, appends the most distinguishing
    characteristic: majority directory, architecture layer, or primary domain tag.
    """
    # Group by name
    name_groups: Dict[str, List[str]] = defaultdict(list)
    for mod_id, mod in modules.items():
        name_groups[mod.name].append(mod_id)

    for name, mod_ids in name_groups.items():
        if len(mod_ids) < 2:
            continue

        # Find distinguishing characteristic for each duplicate
        for mod_id in mod_ids:
            mod = modules[mod_id]

            # Try: majority directory of member files
            if mod.member_files:
                import os.path as osp
                dir_counts: Dict[str, int] = defaultdict(int)
                for fp in mod.member_files:
                    parent = osp.dirname(fp) or "."
                    # Use the top-level directory for clarity
                    top = parent.split("/")[0] if "/" in parent else parent
                    dir_counts[top] += 1
                majority_dir = max(dir_counts, key=dir_counts.get)
                suffix = majority_dir.replace("_", " ").replace("-", " ").title()
            elif mod.architecture_layers:
                suffix = mod.architecture_layers[0].replace("_", " ").title()
            elif mod.domain_tags:
                # Use a secondary tag that's not the name itself
                non_name_tags = [t for t in mod.domain_tags if t.lower() != name.lower()]
                suffix = (non_name_tags[0] if non_name_tags else mod.domain_tags[0]).replace("_", " ").title()
            else:
                suffix = mod.module_id.split(":")[-1]

            mod.name = f"{name} ({suffix})"

    # Check for remaining duplicates after first pass (rare)
    seen_names: Dict[str, int] = {}
    for mod in modules.values():
        if mod.name in seen_names:
            seen_names[mod.name] += 1
            mod.name = f"{mod.name} #{seen_names[mod.name]}"
        else:
            seen_names[mod.name] = 1


# ── Synthesis engine ─────────────────────────────────────────────────

class ClusterSynthesizer:
    """Pass 3 cluster synthesis engine.

    Groups enriched nodes into subsystem clusters, then generates
    module-level summaries via the deep reasoning model.
    """

    def __init__(
        self,
        llm: LLMClient,
        index_dir: Path,
        batch_profile: Optional[Any] = None,
    ):
        self.llm = llm
        self.index_dir = index_dir
        self._batch_profile = batch_profile
        self.modules_path = index_dir / "trace_modules.jsonl"

    def _get_swarm_enabled(self) -> bool:
        """Check if swarm is enabled in pipeline settings."""
        try:
            from codrag.services.settings_store import settings
            return bool(settings.get("swarm_enabled", True))
        except Exception:
            return True

    def load_epistemic(self) -> Dict[str, EpistemicEntry]:
        """Load epistemic entries from trace_epistemic.jsonl."""
        entries: Dict[str, EpistemicEntry] = {}
        path = self.index_dir / "trace_epistemic.jsonl"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            d = json.loads(line)
                            entry = EpistemicEntry.from_dict(d)
                            entries[entry.node_id] = entry
                        except (json.JSONDecodeError, KeyError):
                            continue
        return entries

    def load_edges(self) -> List[Dict[str, Any]]:
        """Load all trace edges."""
        edges: List[Dict[str, Any]] = []
        for fname in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
            path = self.index_dir / fname
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            edges.append(json.loads(line))
        return edges

    def load_existing_modules(self) -> Dict[str, ModuleEntry]:
        """Load existing module entries."""
        entries: Dict[str, ModuleEntry] = {}
        if self.modules_path.exists():
            with open(self.modules_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            d = json.loads(line)
                            entry = ModuleEntry.from_dict(d)
                            entries[entry.module_id] = entry
                        except (json.JSONDecodeError, KeyError):
                            continue
        return entries

    def _build_member_summaries(
        self,
        cluster: Cluster,
        epistemic: Dict[str, EpistemicEntry],
        max_files: int = 30,
    ) -> str:
        """Build a formatted string of member file summaries for the prompt."""
        parts: List[str] = []
        # Sort by importance (e.g. file path length or connectivity) if possible
        # For now, just take the first N
        for nid in cluster.member_node_ids[:max_files]:
            entry = epistemic.get(nid)
            file_path = nid.replace("file:", "", 1) if nid.startswith("file:") else nid
            if entry:
                summary = entry.extended_summary or "(no summary)"
                layer = entry.architecture_layer or "unknown"
                subsystem = entry.subsystem or ""
                tech = ", ".join(str(t) if not isinstance(t, str) else t for t in (entry.tech_debt or [])) if entry.tech_debt else ""
                line = f"- {file_path} [{layer}]: {summary}"
                if tech:
                    line += f" (tech debt: {tech})"
                parts.append(line)
            else:
                parts.append(f"- {file_path}: (not enriched)")
        
        if len(cluster.member_node_ids) > max_files:
            parts.append(f"... and {len(cluster.member_node_ids) - max_files} more files.")
            
        return "\n".join(parts)

    def _build_external_deps(
        self,
        cluster: Cluster,
        edges: List[Dict[str, Any]],
        epistemic: Dict[str, EpistemicEntry],
    ) -> str:
        """Find files outside this cluster that members depend on."""
        member_set = set(cluster.member_node_ids)
        external: Set[str] = set()
        for e in edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            if src in member_set and tgt not in member_set and tgt.startswith("file:"):
                external.add(tgt)
            elif tgt in member_set and src not in member_set and src.startswith("file:"):
                external.add(src)

        if not external:
            return "(none)"

        parts: List[str] = []
        for nid in sorted(external)[:15]:
            fp = nid.replace("file:", "", 1)
            entry = epistemic.get(nid)
            if entry and entry.subsystem:
                parts.append(f"- {fp} (subsystem: {entry.subsystem})")
            else:
                parts.append(f"- {fp}")
        return "\n".join(parts)

    def synthesize_cluster(
        self,
        cluster: Cluster,
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
    ) -> Optional[ModuleEntry]:
        """Synthesize a module entry for a cluster using the deep reasoning model."""
        
        # Helper to generate prompt with specific file limit
        def _generate_with_limit(limit: int) -> Optional[Dict[str, Any]]:
            member_summaries = self._build_member_summaries(cluster, epistemic, max_files=limit)
            external_deps = self._build_external_deps(cluster, edges, epistemic)
            
            prompt = MODULE_SYNTHESIS_PROMPT.format(
                cluster_name=cluster.primary_tag.replace("_", " ").replace("-", " ").title(),
                domain_tags=", ".join(sorted(cluster.all_tags)),
                file_count=len(cluster.member_node_ids),
                member_summaries=member_summaries,
                external_deps=external_deps,
            )
            
            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, warnings = compute_optimal_settings(
                task=PipelineTask.CLUSTER,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=False,
            )

            text, tokens = self.llm.generate(
                prompt, system=MODULE_SYNTHESIS_SYSTEM, num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, think=False,
                max_chars=TASK_MAX_CHARS["augmentation"],
            )
            return _parse_json_response(text)

        cluster_name = cluster.primary_tag.replace("_", " ").replace("-", " ").title()
        parsed = None
        
        # Attempt 1: Standard context (30 files)
        try:
            parsed = _generate_with_limit(30)
        except Exception as e:
            logger.warning("Deep reasoning LLM call failed for cluster %s (full context): %s", cluster.cluster_id, e)
            
            # Attempt 2: Reduced context (10 files)
            try:
                logger.info("Retrying cluster %s with reduced context (10 files)...", cluster.cluster_id)
                parsed = _generate_with_limit(10)
            except Exception as e2:
                logger.warning("Deep reasoning LLM call failed for cluster %s (reduced context): %s", cluster.cluster_id, e2)

        # Fallback 3: Basic entry
        if not parsed:
            logger.warning("Failed to synthesize cluster %s after retries — using fallback", cluster.cluster_id)
            parsed = {
                "name": f"{cluster_name} Subsystem",
                "summary": f"Cluster of {len(cluster.member_node_ids)} files related to {cluster.primary_tag}. (Automatic synthesis failed)",
                "component_status": "unknown",
                "data_flow": None,
                "dependencies": [],
                "tech_debt_summary": None,
            }

        # Use cluster_id (e.g. "cluster:ui:0") for unique module_id
        module_id = f"module:{cluster.cluster_id.replace('cluster:', '')}"

        # Compute average epistemic confidence across cluster members
        confs = [
            epistemic[nid].epistemic_confidence
            for nid in cluster.member_node_ids
            if nid in epistemic
        ]
        avg_conf = sum(confs) / len(confs) if confs else 0.0

        return ModuleEntry(
            module_id=module_id,
            name=str(parsed.get("name", cluster_name))[:200],
            summary=str(parsed.get("summary", ""))[:1000],
            member_files=[
                nid.replace("file:", "", 1) for nid in cluster.member_node_ids
            ],
            domain_tags=sorted(cluster.all_tags),
            architecture_layers=sorted(parsed.get("architecture_layers", [])),
            component_status=parsed.get("component_status", "unknown"),
            data_flow=parsed.get("data_flow"),
            dependencies=parsed.get("dependencies"),
            tech_debt_summary=parsed.get("tech_debt_summary"),
            file_count=len(cluster.member_node_ids),
            avg_epistemic_confidence=avg_conf,
            synthesized_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
        )

    def synthesize_cluster_with_angle(
        self,
        cluster: Cluster,
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
        naming_guidance: str,
        analysis_angle: str,
        naming_constraints: List[str],
    ) -> Optional[ModuleEntry]:
        """Synthesize a cluster with coordinator-assigned scoping."""
        member_summaries = self._build_member_summaries(cluster, epistemic, max_files=30)
        external_deps = self._build_external_deps(cluster, edges, epistemic)

        prompt = MODULE_SYNTHESIS_PROMPT.format(
            cluster_name=cluster.primary_tag.replace("_", " ").replace("-", " ").title(),
            domain_tags=", ".join(sorted(cluster.all_tags)),
            file_count=len(cluster.member_node_ids),
            member_summaries=member_summaries,
            external_deps=external_deps,
        )

        # Append coordinator guidance
        constraints_text = ", ".join(naming_constraints) if naming_constraints else "none"
        prompt += (
            f"\n\n## Coordinator Guidance\n"
            f"Naming direction: {naming_guidance}\n"
            f"Analysis focus: {analysis_angle}\n"
            f"Names to AVOID (already used by other modules): {constraints_text}"
        )

        prompt_tokens = len(prompt) // 4
        num_predict, num_ctx, warnings = compute_optimal_settings(
            task=PipelineTask.CLUSTER,
            prompt_tokens=prompt_tokens,
            model=self.llm.model,
            think=False,
        )

        parsed = None

        # Attempt 1: Full context (30 files)
        try:
            text, tokens = self.llm.generate(
                prompt, system=MODULE_SYNTHESIS_SYSTEM,
                num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, think=False,
                max_chars=TASK_MAX_CHARS["augmentation"],
            )
            parsed = _parse_json_response(text)
        except Exception as e:
            logger.warning("[Cluster/Swarm] Worker failed for %s (full context): %s", cluster.cluster_id, e)

            # Attempt 2: Reduced context (10 files)
            try:
                reduced_summaries = self._build_member_summaries(cluster, epistemic, max_files=10)
                reduced_prompt = MODULE_SYNTHESIS_PROMPT.format(
                    cluster_name=cluster.primary_tag.replace("_", " ").replace("-", " ").title(),
                    domain_tags=", ".join(sorted(cluster.all_tags)),
                    file_count=len(cluster.member_node_ids),
                    member_summaries=reduced_summaries,
                    external_deps=external_deps,
                )
                reduced_prompt += (
                    f"\n\n## Coordinator Guidance\n"
                    f"Naming direction: {naming_guidance}\n"
                    f"Analysis focus: {analysis_angle}\n"
                    f"Names to AVOID (already used by other modules): {constraints_text}"
                )
                r_tokens = len(reduced_prompt) // 4
                r_predict, r_ctx, _ = compute_optimal_settings(
                    task=PipelineTask.CLUSTER, prompt_tokens=r_tokens,
                    model=self.llm.model, think=False,
                )
                text, tokens = self.llm.generate(
                    reduced_prompt, system=MODULE_SYNTHESIS_SYSTEM,
                    num_predict=r_predict, num_ctx=r_ctx,
                    json_mode=False, think=False,
                    max_chars=TASK_MAX_CHARS["augmentation"],
                )
                parsed = _parse_json_response(text)
            except Exception as e2:
                logger.warning("[Cluster/Swarm] Worker failed for %s (reduced context): %s", cluster.cluster_id, e2)

        if parsed is None:
            logger.warning("[Cluster/Swarm] Unparseable response for %s", cluster.cluster_id)
            return None

        module_id = f"module:{cluster.cluster_id.replace('cluster:', '')}"
        confs = [
            epistemic[nid].epistemic_confidence
            for nid in cluster.member_node_ids
            if nid in epistemic
        ]
        avg_conf = sum(confs) / len(confs) if confs else 0.0

        return ModuleEntry(
            module_id=module_id,
            name=str(parsed.get("name", cluster.primary_tag))[:200],
            summary=str(parsed.get("summary", ""))[:1000],
            member_files=[nid.replace("file:", "", 1) for nid in cluster.member_node_ids],
            domain_tags=sorted(cluster.all_tags),
            architecture_layers=sorted(parsed.get("architecture_layers", [])),
            component_status=parsed.get("component_status", "unknown"),
            data_flow=parsed.get("data_flow"),
            dependencies=parsed.get("dependencies"),
            tech_debt_summary=parsed.get("tech_debt_summary"),
            file_count=len(cluster.member_node_ids),
            avg_epistemic_confidence=avg_conf,
            synthesized_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
        )

    def _run_swarm(
        self,
        to_synthesize: List[Cluster],
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
        progress_callback: Optional[Callable[..., None]] = None,
        cancel_token: Optional[Any] = None,
    ) -> Dict[str, ModuleEntry]:
        """Run swarm-orchestrated cluster synthesis.

        Returns dict of module_id -> ModuleEntry.
        Empty dict signals the caller to fall back to standard path.
        """
        concurrency = 1
        try:
            from codrag.services.pipeline.scheduler import pipeline_scheduler
            full = pipeline_scheduler.full_budget_for_swarm(
                self.llm.provider, self.llm.model,
            )
            if full is not None:
                concurrency = full
        except (ImportError, Exception) as exc:
            logger.debug("Swarm full budget unavailable: %s", exc)
        if concurrency <= 1:
            try:
                from codrag.core.batch_profiles import get_batch_concurrency
                concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)
            except Exception:
                concurrency = 1
        logger.info("[Cluster/Swarm] Using concurrency=%d for fan-out", concurrency)

        # Phase 112: coord and worker decoupled — coord uses the
        # coordinator_llm slot (defaults to Gemini 3 Flash via inherit
        # fallback), worker uses self.llm (Kimi).  Resolves Phase79-DualModel.
        # Phase 112 fix 3: use shared _is_cloud_endpoint helper so
        # non-Ollama cloud providers (openai/anthropic/google) also get
        # the short cloud timeouts (matches atlas, concept_seeder, group_reasoning).
        from codrag.core.llm_client import _is_cloud_endpoint
        is_cloud = _is_cloud_endpoint(self.llm)
        orch = SwarmOrchestrator(
            coordinator_llm=WorkerFactory._get_coordinator_llm_client(),
            worker_llm=self.llm,
            concurrency=concurrency,
            coordinator_timeout_s=10.0 if is_cloud else 90.0,
            synthesis_timeout_s=120.0 if is_cloud else 180.0,
            worker_timeout_s=180.0 if is_cloud else 300.0,
            max_wall_time_s=900.0 if is_cloud else 1800.0,
        )

        # Build WorkItems
        items: List[WorkItem] = []
        cluster_by_id: Dict[str, Cluster] = {}
        for cluster in to_synthesize:
            cluster_by_id[cluster.cluster_id] = cluster

            paths = [
                nid.replace("file:", "", 1)
                for nid in cluster.member_node_ids[:5]
            ]
            summary = f"{cluster.primary_tag}: {', '.join(paths)}"
            if len(cluster.member_node_ids) > 5:
                summary += f" (+{len(cluster.member_node_ids) - 5} more)"

            member_summaries = self._build_member_summaries(cluster, epistemic, max_files=30)
            external_deps = self._build_external_deps(cluster, edges, epistemic)
            full_context = json.dumps({
                "cluster_name": cluster.primary_tag,
                "domain_tags": sorted(cluster.all_tags),
                "file_count": len(cluster.member_node_ids),
                "member_summaries": member_summaries,
                "external_deps": external_deps,
            })

            items.append(WorkItem(id=cluster.cluster_id, summary=summary, full_context=full_context))

        coordinator_prompt = (
            "You are coordinating parallel module synthesis for {n} code clusters.\n"
            "Each cluster is a group of related files that should become one named module.\n\n"
            "Clusters:\n{{group_summaries}}\n\n"
            "For EACH cluster, assign:\n"
            '- "analysis_angle": what aspect to emphasize in the synthesis\n'
            '- "priority_concerns": naming guidance and names to avoid\n\n'
            "Respond with JSON:\n"
            '{{"assignments": [{{"item_id": "cluster:...", '
            '"analysis_angle": "...", '
            '"priority_concerns": ["naming_guidance: ...", "avoid_names: ..."]'
            "}}]}}"
        ).format(n=len(items))

        synthesis_prompt = (
            "Below are module synthesis results from {n} parallel cluster analyses.\n\n"
            "{{worker_outputs}}\n\n"
            "Assess the set of modules as a whole:\n"
            '{{"naming_consistency": "are module names coherent as a set?", '
            '"cross_cluster_deps": ["shared dependencies across clusters"], '
            '"architectural_layering": "do clusters map cleanly to layers?", '
            '"redundancy_flags": ["any clusters that seem to be the same module"], '
            '"key_insight": "most important observation about the module structure"}}'
        ).format(n=len(items))

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
            cluster = cluster_by_id.get(item.id)
            if cluster is None:
                return None

            naming_guidance = assignment.analysis_angle
            naming_constraints = []
            for concern in assignment.priority_concerns:
                if concern.startswith("naming_guidance:"):
                    naming_guidance = concern.replace("naming_guidance:", "").strip()
                elif concern.startswith("avoid_names:"):
                    naming_constraints.append(concern.replace("avoid_names:", "").strip())

            module = self.synthesize_cluster_with_angle(
                cluster, epistemic, edges,
                naming_guidance=naming_guidance,
                analysis_angle=assignment.analysis_angle,
                naming_constraints=naming_constraints,
            )
            if module is None:
                return None
            return json.dumps(module.to_dict())

        def progress_fn(done: int, total: int) -> None:
            if progress_callback:
                progress_callback("cluster_synthesis", done, len(to_synthesize), 0)

        result = orch.execute(
            items=items,
            coordinator_prompt=coordinator_prompt,
            worker_fn=worker_fn,
            synthesis_prompt=synthesis_prompt,
            progress_fn=progress_fn,
        )

        if result is None:
            return {}

        modules: Dict[str, ModuleEntry] = {}
        for wr in result.worker_results:
            if wr.success and wr.parsed:
                try:
                    entry = ModuleEntry.from_dict(wr.parsed)
                    modules[entry.module_id] = entry
                except (KeyError, ValueError) as exc:
                    logger.warning("Failed to parse cluster worker result for %s: %s", wr.item_id, exc)

        if result.synthesis:
            self._write_cluster_synthesis(result)

        return modules

    def _write_cluster_synthesis(self, result: SwarmResult) -> None:
        """Write swarm synthesis artifact to disk."""
        artifact = {
            "stage": "cluster_synthesis_swarm",
            "model": self.llm.model,
            "clusters_analyzed": result.stats.total_items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "synthesis": result.synthesis,
            "stats": {
                "workers_succeeded": result.stats.workers_succeeded,
                "workers_failed": result.stats.workers_failed,
                "wall_clock_seconds": round(result.stats.wall_clock_seconds, 1),
            },
        }
        path = self.index_dir / "trace_cluster_swarm_synthesis.json"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
        logger.info("[Cluster/Swarm] Synthesis written to %s", path)

    @staticmethod
    def _cluster_fingerprint(member_node_ids: List[str]) -> str:
        """Stable fingerprint for a cluster's membership (sorted node IDs)."""
        import hashlib
        key = "\n".join(sorted(member_node_ids))
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def run(
        self,
        progress_callback: Optional[Callable[..., None]] = None,
        min_cluster_size: int = 2,
        cancel_token: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Run Pass 3 cluster synthesis.

        Incremental: reuses existing module entries for clusters whose
        membership hasn't changed, only calling the LLM for new or
        modified clusters.

        Steps:
        1. Load epistemic entries and edges.
        2. Build clusters by domain_tags + connectivity.
        3. Load existing modules and build fingerprint map for reuse.
        4. Synthesize only new/changed clusters via deep reasoning model.
        5. Write trace_modules.jsonl.

        If *cancel_token* is provided, the loop checks it periodically and
        flushes partial results before raising.
        """
        start = time.monotonic()

        epistemic = self.load_epistemic()
        edges = self.load_edges()

        if not epistemic:
            logger.info("No epistemic entries found, skipping cluster synthesis")
            return {"clusters": 0, "synthesized": 0, "skipped": True}

        # Build clusters
        clusters = build_clusters(epistemic, edges, min_cluster_size=min_cluster_size)
        logger.info("Built %d clusters from %d enriched nodes", len(clusters), len(epistemic))

        # Load existing modules for incremental reuse
        existing_modules = self.load_existing_modules()
        # Build TWO lookup maps for matching:
        # 1. fingerprint → ModuleEntry (content-based, stable across runs)
        # 2. module_id → (fingerprint, ModuleEntry) (name-based, for exact ID match)
        fp_to_module: Dict[str, ModuleEntry] = {}
        existing_fp: Dict[str, tuple] = {}
        for mod_id, mod in existing_modules.items():
            fp = self._cluster_fingerprint(
                [f"file:{f}" if not f.startswith("file:") else f for f in mod.member_files]
            )
            fp_to_module[fp] = mod
            existing_fp[mod_id] = (fp, mod)

        total_work = len(clusters)
        modules: Dict[str, ModuleEntry] = {}
        failed = 0
        reused = 0
        synthesized = 0

        # Separate reusable clusters from those needing synthesis.
        # Match by FINGERPRINT first (handles unstable cluster_idx counter),
        # then fall back to module_id match.
        to_synthesize: List[Cluster] = []
        for cluster in clusters:
            module_id = f"module:{cluster.cluster_id.replace('cluster:', '')}"
            new_fp = self._cluster_fingerprint(cluster.member_node_ids)

            # Primary: content-based match — same members = reuse
            if new_fp in fp_to_module:
                old_module = fp_to_module[new_fp]
                # Adopt the existing synthesis but assign the new module_id
                # so the output file uses the current cluster naming scheme
                reused_mod = ModuleEntry(
                    module_id=module_id,
                    name=old_module.name,
                    summary=old_module.summary,
                    member_files=old_module.member_files,
                    domain_tags=old_module.domain_tags,
                    architecture_layers=old_module.architecture_layers,
                    component_status=old_module.component_status,
                    data_flow=old_module.data_flow,
                    dependencies=old_module.dependencies,
                    tech_debt_summary=old_module.tech_debt_summary,
                    file_count=old_module.file_count,
                    avg_epistemic_confidence=old_module.avg_epistemic_confidence,
                    synthesized_at=old_module.synthesized_at,
                    model=old_module.model,
                )
                modules[module_id] = reused_mod
                reused += 1
                continue

            # Fallback: exact module_id match (for stable cluster IDs)
            if module_id in existing_fp:
                old_fp, old_module = existing_fp[module_id]
                if old_fp == new_fp:
                    modules[module_id] = old_module
                    reused += 1
                    continue

            to_synthesize.append(cluster)

        logger.info(
            "Cluster reuse: %d total, %d reused (fingerprint match), %d to synthesize, "
            "%d existing modules on disk, %d unique fingerprints",
            total_work, reused, len(to_synthesize), len(existing_modules), len(fp_to_module),
        )

        # ── Swarm decision ──────────────────────────────────────────
        swarm_tier = get_swarm_tier(self.llm.provider, self.llm.model)
        swarm_enabled = self._get_swarm_enabled()
        min_threshold = get_min_groups_threshold()
        use_swarm = (
            swarm_tier.can_coordinate
            and swarm_enabled
            and len(to_synthesize) >= min_threshold
        )

        if use_swarm:
            logger.info(
                "Cluster synthesis: using SWARM orchestration (%s, %d clusters, tier=%s)",
                self.llm.model, len(to_synthesize), swarm_tier.value,
            )
            swarm_modules = self._run_swarm(
                to_synthesize, epistemic, edges, progress_callback, cancel_token,
            )
            if swarm_modules:
                modules.update(swarm_modules)
                synthesized = len(swarm_modules)
                failed = len(to_synthesize) - synthesized

                _deduplicate_module_names(modules)
                self._write_modules(modules)

                duration_ms = (time.monotonic() - start) * 1000
                if progress_callback:
                    progress_callback("cluster_complete", total_work, total_work, reused)
                return {
                    "clusters": total_work,
                    "synthesized": synthesized,
                    "reused": reused,
                    "failed": failed,
                    "total_files_clustered": sum(
                        len(m.member_files) for m in modules.values()
                    ),
                    "duration_ms": round(duration_ms, 1),
                    "swarm": True,
                }
            else:
                logger.info("Cluster swarm coordinator failed — falling back to standard path")

        # Decide: batched (BYOK) or sequential (local)
        use_batching = (
            self._batch_profile is not None
            and self._batch_profile.name.value != "off"
            and len(to_synthesize) > 1
        )

        if use_batching:
            from .batch_profiles import BatchStage
            from .batch_prompts import (
                BATCHED_CLUSTER_SYSTEM,
                build_batched_cluster_prompt,
                get_structured_schema,
            )
            from .batch_strategy import BatchedResponseParser

            batch_size = self._batch_profile.batch_size(BatchStage.CLUSTERING)
            logger.info(
                "BATCHED cluster synthesis: %d clusters, batch_size=%d (%s profile)",
                len(to_synthesize), batch_size, self._batch_profile.name.value,
            )

            schema = get_structured_schema("clustering")

            for batch_start in range(0, len(to_synthesize), batch_size):
                batch = to_synthesize[batch_start:batch_start + batch_size]
                items = []
                for cluster in batch:
                    member_summaries = self._build_member_summaries(cluster, epistemic, max_files=30)
                    external_deps = self._build_external_deps(cluster, edges, epistemic)
                    items.append({
                        "cluster_name": cluster.primary_tag.replace("_", " ").replace("-", " ").title(),
                        "domain_tags": ", ".join(sorted(cluster.all_tags)),
                        "file_count": len(cluster.member_node_ids),
                        "member_summaries": member_summaries,
                        "external_deps": external_deps,
                        "_cluster": cluster,
                    })

                prompt = build_batched_cluster_prompt(items)
                try:
                    prompt_tokens = len(prompt) // 4
                    num_predict, num_ctx, warnings = compute_optimal_settings(
                        task=PipelineTask.CLUSTER,
                        prompt_tokens=prompt_tokens,
                        model=self.llm.model,
                        think=False,
                    )

                    text, tokens = self.llm.generate(
                        prompt, system=BATCHED_CLUSTER_SYSTEM,
                        num_predict=num_predict, num_ctx=num_ctx,
                        response_schema=schema,
                        max_chars=batched_max_chars("augmentation", len(items)),
                    )
                    results_list = BatchedResponseParser.parse(text, expected_count=len(items))
                except Exception as e:
                    logger.warning("Batched cluster synthesis failed for %d items: %s", len(items), e)
                    results_list = []

                for idx, item in enumerate(items):
                    cluster = item["_cluster"]
                    cluster_name = item["cluster_name"]
                    parsed = results_list[idx] if idx < len(results_list) else None

                    if not parsed:
                        parsed = {
                            "name": f"{cluster_name} Subsystem",
                            "summary": f"Cluster of {len(cluster.member_node_ids)} files related to {cluster.primary_tag}. (Batch synthesis failed)",
                            "component_status": "unknown",
                        }

                    module_id = f"module:{cluster.cluster_id.replace('cluster:', '')}"
                    confs = [
                        epistemic[nid].epistemic_confidence
                        for nid in cluster.member_node_ids
                        if nid in epistemic
                    ]
                    avg_conf = sum(confs) / len(confs) if confs else 0.0

                    module = ModuleEntry(
                        module_id=module_id,
                        name=str(parsed.get("name", cluster_name))[:200],
                        summary=str(parsed.get("summary", ""))[:1000],
                        member_files=[nid.replace("file:", "", 1) for nid in cluster.member_node_ids],
                        domain_tags=sorted(cluster.all_tags),
                        architecture_layers=sorted(parsed.get("architecture_layers", [])),
                        component_status=parsed.get("component_status", "unknown"),
                        data_flow=parsed.get("data_flow"),
                        dependencies=parsed.get("dependencies"),
                        tech_debt_summary=parsed.get("tech_debt_summary"),
                        file_count=len(cluster.member_node_ids),
                        avg_epistemic_confidence=avg_conf,
                        synthesized_at=datetime.now(timezone.utc).isoformat(),
                        model=self.llm.model,
                    )
                    modules[module.module_id] = module
                    synthesized += 1

                if progress_callback:
                    progress_callback("cluster_synthesis", reused + synthesized + failed, total_work, reused)

        else:
            # Local model: sequential or concurrent
            concurrency = _get_llm_concurrency("deep")
            logger.info("Cluster synthesis: %d clusters to synthesize, concurrency=%d", len(to_synthesize), concurrency)

            if concurrency <= 1:
                # Sequential: one cluster at a time
                for i, cluster in enumerate(to_synthesize):
                    # Cooperative cancellation check
                    if cancel_token and cancel_token.is_cancelled:
                        logger.info("Cluster synthesis paused/cancelled at %d/%d — flushing partial results", synthesized, len(to_synthesize))
                        self._write_modules(modules)
                        cancel_token.raise_if_cancelled()

                    if progress_callback:
                        progress_callback("cluster_synthesis", reused + i, total_work, reused)

                    module = self.synthesize_cluster(cluster, epistemic, edges)
                    if module:
                        modules[module.module_id] = module
                        synthesized += 1
                    else:
                        failed += 1

                    # Periodic checkpoint to avoid losing progress on crash
                    if synthesized > 0 and synthesized % 10 == 0:
                        self._write_modules(modules)
                        logger.info("Cluster checkpoint saved at %d/%d clusters", synthesized, len(to_synthesize))
            else:
                # Concurrent LLM calls via thread pool
                lock = threading.Lock()
                done_count = 0
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    futures = {
                        pool.submit(self.synthesize_cluster, cluster, epistemic, edges): cluster
                        for cluster in to_synthesize
                    }
                    for future in as_completed(futures):
                        try:
                            module = future.result()
                            with lock:
                                if module:
                                    modules[module.module_id] = module
                                    synthesized += 1
                                else:
                                    failed += 1
                                done_count += 1
                                if progress_callback:
                                    progress_callback("cluster_synthesis", reused + done_count, total_work, reused)
                        except Exception as e:
                            logger.warning("Cluster synthesis failed: %s", e)
                            with lock:
                                failed += 1
                                done_count += 1

        # CL-9: Deduplicate module names
        _deduplicate_module_names(modules)

        # Write atomically
        self._write_modules(modules)

        duration_ms = (time.monotonic() - start) * 1000

        if progress_callback:
            progress_callback("cluster_complete", total_work, total_work, reused)

        stats = {
            "clusters": len(clusters),
            "synthesized": synthesized,
            "reused": reused,
            "failed": failed,
            "total_files_clustered": sum(len(c.member_node_ids) for c in clusters),
            "duration_ms": round(duration_ms, 1),
        }

        logger.info(
            "Cluster synthesis complete: %d clusters, %d synthesized, %d reused, %d failed in %.1fs",
            len(clusters), synthesized, reused, failed, duration_ms / 1000,
        )

        return stats

    def _write_modules(self, modules: Dict[str, ModuleEntry]) -> None:
        """Write module entries atomically."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        sorted_modules = sorted(modules.values(), key=lambda m: m.module_id)

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", dir=self.index_dir, delete=False, encoding="utf-8",
        )
        try:
            for module in sorted_modules:
                tmp.write(json.dumps(module.to_dict(), sort_keys=True) + "\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.modules_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise
