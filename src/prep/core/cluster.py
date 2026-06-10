"""
Cluster Synthesis for Prep (Pass 3).

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
import re
import tempfile
import threading
import time
from collections import defaultdict
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
    as_completed,
)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import networkx as nx

from prep.core.context_config import PipelineTask, compute_optimal_settings
from prep.core.llm_client import TASK_MAX_CHARS, batched_max_chars
from prep.services.pipeline.holds import (
    HoldPausedError,
    hold_paused_for_llm,
    raise_hold_paused_for_llm,
)
from prep.services.pipeline.recovery import is_reuse_blocked
from prep.services.pipeline.thread_pool import llm_pool
from prep.services.pipeline.workers import WorkerFactory
from prep.services.pipeline.workers.base import Worker

from .epistemic_score import EpistemicEntry
from .llm_client import LLMClient, _get_llm_concurrency, _parse_confidence, _parse_json_response
from .swarm_orchestrator import (
    SwarmOrchestrator,
    SwarmResult,
    WorkerAssignment,
    WorkItem,
    compute_swarm_wall_budget,
)
from .swarm_registry import get_min_groups_threshold, get_swarm_tier

logger = logging.getLogger(__name__)

# Phase 136 Part 13b — symmetric Jaccard threshold for cluster reuse
# fallback.  Mirrors Part 12's `_JACCARD_THRESHOLD` in group_reasoning.
# 0.7 means both halves of the overlap (new∩old / new, new∩old / old)
# must clear 70 % for the cached ModuleEntry to be reused.
_CLUSTER_REUSE_JACCARD_THRESHOLD = 0.7


def _find_overlapping_module(
    new_member_files: List[str],
    existing_modules: Dict[str, "ModuleEntry"],
) -> Optional["ModuleEntry"]:
    """Locate a prior ModuleEntry whose member set has high Jaccard
    overlap with ``new_member_files``.  Returns ``None`` when no
    cached module clears the threshold.

    Phase 136 Part 13b: fallback used when the exact-frozenset lookup
    misses.  Pre-Phase-136 a single file joining or leaving a cluster
    would invalidate the cached module synthesis (frozenset mismatch);
    on an incremental rebuild this cascaded across most modules and
    produced "Module Synthesis: rebuilding" behavior even though the
    user only changed a few files.  See
    ``docs/Phase136_Dogfood-fixes/Part13_SwarmResourceContention/``
    "Part 13b" follow-up section for the original finding.

    Symmetric Jaccard: both halves must clear the threshold so a
    small new cluster can't match its giant cached parent (and vice
    versa)."""
    new_set = frozenset(new_member_files)
    if not new_set:
        return None
    best_score = _CLUSTER_REUSE_JACCARD_THRESHOLD
    best: Optional[ModuleEntry] = None
    for mod in existing_modules.values():
        old_set = frozenset(mod.member_files or ())
        if not old_set:
            continue
        intersection = len(new_set & old_set)
        if intersection == 0:
            continue
        new_overlap = intersection / len(new_set)
        old_overlap = intersection / len(old_set)
        score = min(new_overlap, old_overlap)
        if score > best_score:
            best_score = score
            best = mod
    return best


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

SUMMARY SHAPE (FIX-16-4):
- Sentence 1: concrete verb + concrete object — what an agent can *do* in this module. Start with a doing-verb (Renders, Parses, Schedules, Persists), not "Provides", "Implements", "Bridges", "Serves as".
- Sentence 2 (optional): how it connects to the rest of the codebase — name the upstream/downstream subsystem.
- Sentence 3 (optional, only if true): one specific caveat or in-flight work item.
- Hard cap: 3 sentences, ~40 words total.

BANNED PHRASES — never emit:
- "central nervous system"
- "Bridges X with Y" / "Bridges X and Y"
- "serves as the [foo] backbone" / "serves as the central"
- "currently in active transition" / "currently in active development"
- "end-to-end" (use the actual scope instead — "from request parse to response serialization")
- "while maintaining" (almost always padding)
- "tiered" without a specific tier list
- "robust", "comprehensive", "seamless" (consulting filler)

EXAMPLE — given a cluster with 4 files (scheduler.py, worker_pool.py, job_queue.py, priority.py) in a pipeline domain, a good response is:
{{"name": "Pipeline Job Scheduler & Worker Pool",
"summary": "Manages concurrent pipeline job execution with priority queuing and worker lifecycle. Distributes enrichment tasks across a configurable thread pool, enforces per-stage ordering constraints, and provides graceful shutdown with in-flight job draining.",
"component_status": "complete",
"data_flow": "Jobs enter via job_queue → priority sorting → worker_pool dispatches to available workers → scheduler monitors completion and triggers dependent stages",
"dependencies": ["pipeline-orchestrator", "llm-client"],
"tech_debt_summary": "Worker pool size is hardcoded; should be configurable per deployment."}}

Where component_status describes the overall implementation completeness of this subsystem.

JSON response:"""


# ── Summary lint (FIX-16-4) ──────────────────────────────────────────

# Banned consulting-deck phrases. Mirrors the BANNED PHRASES section of
# MODULE_SYNTHESIS_PROMPT so synthesis output can be checked after the LLM
# returns. Used today as an advisory log; a follow-up will wire this into
# a re-prompt loop on detection.
_BANNED_SUMMARY_PHRASES: tuple[str, ...] = (
    "central nervous system",
    "bridges ",  # matches "Bridges X with Y" / "Bridges X and Y"
    "serves as the central",
    "serves as the backbone",
    "backbone for",
    "currently in active transition",
    "currently in active development",
    "end-to-end",
    "while maintaining",
    "robust ",
    "comprehensive ",
    "seamless ",
)


def lint_module_summary(text: str) -> list[str]:
    """Return a list of banned-phrase findings in a module summary.

    Pure function — case-insensitive substring matching. Used to flag
    consulting-deck phrasing in synthesized module summaries
    (FIX-16-4, see docs/Phase82_MCP-Dogfooding/17_Followup_2026-05-08.md).
    Empty list means the summary passes the lint.
    """
    if not text:
        return []
    lowered = text.lower()
    return [phrase.strip() for phrase in _BANNED_SUMMARY_PHRASES if phrase in lowered]


# ── Legacy `#N` suffix migration (FIX-16-3 follow-up) ────────────────

_POUND_N_SUFFIX_RE = re.compile(r"\s*#\d+\s*$")


def strip_legacy_pound_n_suffix(name: str, module_id: str) -> str:
    """Rewrite a legacy `Foo (Packages) #2` into `Foo (Packages) [<idx>]`.

    Modules synthesized before FIX-16-3 carried `#N` suffixes when first-pass
    distinguishers collided. The new dedup logic emits `[<module_id idx>]`
    instead. This helper migrates a single name in-place — pure function so
    callers can decide whether to apply it lazily at load time or eagerly via
    a CLI cleanup command.
    """
    if not name or not _POUND_N_SUFFIX_RE.search(name):
        return name
    base = _POUND_N_SUFFIX_RE.sub("", name).rstrip()
    disc = (module_id.split(":")[-1] if module_id else "") or module_id
    if not disc:
        return base
    return f"{base} [{disc}]"


def strip_legacy_pound_n_suffixes(
    modules: Dict[str, "ModuleEntry"],
) -> int:
    """Rewrite legacy `#N` suffixes across an in-memory module dict.

    Returns the number of names rewritten. Idempotent — calling twice has
    no effect on already-migrated names.
    """
    rewritten = 0
    for mod_id, mod in modules.items():
        new_name = strip_legacy_pound_n_suffix(mod.name, mod_id)
        if new_name != mod.name:
            mod.name = new_name
            rewritten += 1
    return rewritten


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

    # Louvain via networkx (BSD-3-Clause). Previously Leiden via
    # igraph+leidenalg (GPL); swapped 2026-06-10 to clear Phase 144
    # blocker #1. See docs/superpowers/specs/2026-06-08-gpl-dependency-replacement-design.md

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

        # Build networkx Graph. add_nodes_from preserves isolated
        # nodes (igraph.Graph(n=n) did this implicitly).
        g = nx.Graph()
        g.add_nodes_from(range(n))
        if edge_pairs:
            sorted_edges = sorted(edge_pairs.keys())
            weights = [edge_pairs[e] for e in sorted_edges]
            g.add_weighted_edges_from(
                [(i, j, w) for (i, j), w in zip(sorted_edges, weights)]
            )
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

        # Run Louvain. Deterministic via seed=42; networkx Louvain
        # runs iterative refinement until convergence (no equivalent
        # of leidenalg's n_iterations=-1 is needed).
        try:
            partition = nx.algorithms.community.louvain_communities(
                g,
                weight="weight",
                resolution=resolution,
                seed=42,
            )
        except Exception as e:
            logger.warning("CL-1: Louvain failed for layer %s: %s, falling back", layer, e)
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

    # Check for remaining duplicates after first pass (rare).
    #
    # FIX-16-3 (docs/Phase82_MCP-Dogfooding/17_Followup_2026-05-08.md):
    # The previous fallback emitted "Foo #2", "Foo #3" when first-pass
    # parenthetical distinguishers also collided. The `#N` suffix reads as
    # a synthesizer giveaway in the atlas and is the smell the dogfood
    # critique flagged. Replace with a module_id-derived discriminator so
    # duplicates remain distinguishable without signalling failure, and
    # log a warning so the underlying clustering miss stays visible.
    name_to_ids: Dict[str, List[str]] = defaultdict(list)
    for mod_id, mod in modules.items():
        name_to_ids[mod.name].append(mod_id)
    for dup_name, dup_ids in name_to_ids.items():
        if len(dup_ids) < 2:
            continue
        logger.warning(
            "_deduplicate_module_names: %d modules still share name %r after "
            "first-pass distinguishers — appending module_id discriminator. "
            "This usually indicates a clustering near-duplicate that should "
            "be merged or re-clustered.",
            len(dup_ids), dup_name,
        )
        for mod_id in dup_ids:
            mod = modules[mod_id]
            disc = mod.module_id.split(":")[-1] or mod.module_id
            mod.name = f"{mod.name} [{disc}]"


# ── Synthesis engine ─────────────────────────────────────────────────

class ClusterSynthesizer(Worker):
    """Pass 3 cluster synthesis engine.

    Groups enriched nodes into subsystem clusters, then generates
    module-level summaries via the deep reasoning model.
    """

    def __init__(
        self,
        llm: LLMClient,
        index_dir: Path,
        batch_profile: Optional[Any] = None,
        project_id: str = "",
    ):
        self.llm = llm
        self.index_dir = index_dir
        self._batch_profile = batch_profile
        self.modules_path = index_dir / "trace_modules.jsonl"
        self.project_id = project_id
        # Phase 127: stash slots for swarm pause signaling.  Initialized
        # here (instead of relying on getattr fallbacks at the read site)
        # so a "never set" foot-gun can't silently mask a regression.
        # Updated by _run_swarm() after each swarm execution.
        self._last_swarm_paused: bool = False
        self._last_swarm_pause_info: Dict[str, str] = {}
        # 2026-05-27 (Phase 141): incomplete-swarm signaling — same
        # rationale as group_reasoning.py.  Set when the swarm wall-cap
        # or stall fires and pending workers are cancelled.  The caller
        # raises rather than writing a truncated modules file.
        self._last_swarm_incomplete: bool = False
        self._last_swarm_incomplete_info: Dict[str, Any] = {}

    def _get_swarm_enabled(self) -> bool:
        """Check if swarm is enabled in pipeline settings."""
        try:
            from prep.services.settings_store import settings
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
        """Load existing module entries.

        Returns an empty dict if a reset barrier is active for this project
        and its scope blocks deep_enrichment reuse — reset semantics require
        clustering to treat all prior data as nonexistent.
        """
        entries: Dict[str, ModuleEntry] = {}
        if self.project_id and is_reuse_blocked(self.project_id, stage_group="deep_enrichment"):
            logger.info(
                "Cluster reuse blocked by reset barrier for project %s — "
                "treating prior trace_modules.jsonl as empty",
                self.project_id,
            )
            return entries
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
                # tech_debt items may be strings (legacy) or dicts (Phase 140 structured)
                def _td_str(t):
                    if isinstance(t, dict):
                        sev = t.get("severity", "")
                        name = t.get("item", "")
                        return f"[{sev}] {name}" if sev else name
                    return str(t)
                tech = ", ".join(_td_str(t) for t in (entry.tech_debt or [])) if entry.tech_debt else ""
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
        def _generate_with_limit(
            limit: int, extra_instruction: str = "",
        ) -> Optional[Dict[str, Any]]:
            member_summaries = self._build_member_summaries(cluster, epistemic, max_files=limit)
            external_deps = self._build_external_deps(cluster, edges, epistemic)

            prompt = MODULE_SYNTHESIS_PROMPT.format(
                cluster_name=cluster.primary_tag.replace("_", " ").replace("-", " ").title(),
                domain_tags=", ".join(sorted(cluster.all_tags)),
                file_count=len(cluster.member_node_ids),
                member_summaries=member_summaries,
                external_deps=external_deps,
            )
            if extra_instruction:
                prompt = f"{prompt}\n\nADDITIONAL CONSTRAINT:\n{extra_instruction}"

            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, warnings = compute_optimal_settings(
                task=PipelineTask.CLUSTER,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=False,
            )

            if hold_paused_for_llm(self.llm, self.project_id, logger):
                raise_hold_paused_for_llm(self.llm, self.project_id)
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
        except HoldPausedError:
            raise
        except Exception as e:
            logger.warning("Deep reasoning LLM call failed for cluster %s (full context): %s", cluster.cluster_id, e)

            # Attempt 2: Reduced context (10 files)
            try:
                logger.info("Retrying cluster %s with reduced context (10 files)...", cluster.cluster_id)
                parsed = _generate_with_limit(10)
            except HoldPausedError:
                raise
            except Exception as e2:
                logger.warning("Deep reasoning LLM call failed for cluster %s (reduced context): %s", cluster.cluster_id, e2)

        # FIX-16-4 follow-up: re-prompt loop on consulting-deck phrasing.
        # If the synthesizer emitted a summary containing banned phrases,
        # spend one extra LLM call asking it to rewrite without them.
        # Best-effort — failures fall back to the original parsed response.
        if parsed and isinstance(parsed.get("summary"), str):
            findings = lint_module_summary(parsed["summary"])
            if findings:
                phrases_list = ", ".join(f'"{p}"' for p in findings)
                instruction = (
                    "Your previous summary contained banned phrases: "
                    f"{phrases_list}. Rewrite the JSON object so the 'summary' "
                    "field does not contain any of those phrases. Lead with a "
                    "concrete doing-verb and stay under 40 words / 3 sentences."
                )
                logger.info(
                    "FIX-16-4: re-prompting cluster %s after lint flagged %d phrases: %s",
                    cluster.cluster_id, len(findings), findings,
                )
                try:
                    retry = _generate_with_limit(30, extra_instruction=instruction)
                    if retry and isinstance(retry.get("summary"), str):
                        parsed = retry
                except HoldPausedError:
                    raise
                except Exception as e:
                    logger.warning(
                        "FIX-16-4 re-prompt failed for cluster %s: %s — keeping original",
                        cluster.cluster_id, e,
                    )

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
            if hold_paused_for_llm(self.llm, self.project_id, logger):
                raise_hold_paused_for_llm(self.llm, self.project_id)
            text, tokens = self.llm.generate(
                prompt, system=MODULE_SYNTHESIS_SYSTEM,
                num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, think=False,
                max_chars=TASK_MAX_CHARS["augmentation"],
            )
            parsed = _parse_json_response(text)
        except HoldPausedError:
            raise
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
                if hold_paused_for_llm(self.llm, self.project_id, logger):
                    raise_hold_paused_for_llm(self.llm, self.project_id)
                text, tokens = self.llm.generate(
                    reduced_prompt, system=MODULE_SYNTHESIS_SYSTEM,
                    num_predict=r_predict, num_ctx=r_ctx,
                    json_mode=False, think=False,
                    max_chars=TASK_MAX_CHARS["augmentation"],
                )
                parsed = _parse_json_response(text)
            except HoldPausedError:
                raise
            except Exception as e2:
                logger.warning("[Cluster/Swarm] Worker failed for %s (reduced context): %s", cluster.cluster_id, e2)

        if parsed is None:
            logger.warning("[Cluster/Swarm] Unparseable response for %s", cluster.cluster_id)
            return None

        # FIX-16-4 follow-up: re-prompt loop on consulting-deck phrasing.
        # Same pattern as synthesize_cluster — one extra LLM call when the
        # summary contains banned phrases. Best-effort; failures keep
        # the original response.
        if isinstance(parsed.get("summary"), str):
            findings = lint_module_summary(parsed["summary"])
            if findings:
                phrases_list = ", ".join(f'"{p}"' for p in findings)
                instruction = (
                    "Your previous summary contained banned phrases: "
                    f"{phrases_list}. Rewrite the JSON object so the 'summary' "
                    "field does not contain any of those phrases. Lead with a "
                    "concrete doing-verb and stay under 40 words / 3 sentences."
                )
                logger.info(
                    "FIX-16-4: re-prompting (with-angle) cluster %s after lint flagged %d phrases",
                    cluster.cluster_id, len(findings),
                )
                try:
                    retry_prompt = f"{prompt}\n\nADDITIONAL CONSTRAINT:\n{instruction}"
                    if hold_paused_for_llm(self.llm, self.project_id, logger):
                        raise_hold_paused_for_llm(self.llm, self.project_id)
                    rt_text, _ = self.llm.generate(
                        retry_prompt, system=MODULE_SYNTHESIS_SYSTEM,
                        num_predict=num_predict, num_ctx=num_ctx,
                        json_mode=False, think=False,
                        max_chars=TASK_MAX_CHARS["augmentation"],
                    )
                    retry_parsed = _parse_json_response(rt_text)
                    if retry_parsed and isinstance(retry_parsed.get("summary"), str):
                        parsed = retry_parsed
                except HoldPausedError:
                    raise
                except Exception as e:
                    logger.warning(
                        "FIX-16-4 (with-angle) re-prompt failed for %s: %s — keeping original",
                        cluster.cluster_id, e,
                    )

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
            from prep.services.pipeline.scheduler import pipeline_scheduler
            full = pipeline_scheduler.full_budget_for_swarm(
                self.llm.provider, self.llm.model,
            )
            if full is not None:
                concurrency = full
        except (ImportError, Exception) as exc:
            logger.debug("Swarm full budget unavailable: %s", exc)
        if concurrency <= 1:
            try:
                from prep.core.batch_profiles import get_batch_concurrency
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
        from prep.core.llm_client import _is_cloud_endpoint
        is_cloud = _is_cloud_endpoint(self.llm)
        # 2026-05-27 (Phase 141): scale wall budget with workload.
        # See compute_swarm_wall_budget docstring for rationale.
        wall_budget = compute_swarm_wall_budget(
            n_items=len(to_synthesize), concurrency=concurrency, is_cloud=is_cloud,
        )
        orch = SwarmOrchestrator(
            coordinator_llm=WorkerFactory._get_coordinator_llm_client(),
            worker_llm=self.llm,
            concurrency=concurrency,
            # Cloud coord/synth timeouts: 10s → 60s → 120s/180s → 180s/240s.
            # See group_reasoning.py for rationale — larger repos need
            # ~50% more time than PowerMate's 111s coord / 169s synth.
            coordinator_timeout_s=180.0 if is_cloud else 90.0,
            synthesis_timeout_s=240.0 if is_cloud else 180.0,
            worker_timeout_s=180.0 if is_cloud else 300.0,
            max_wall_time_s=wall_budget,
            # Phase 127: pass project_id so the swarm honors soft-holds
            # at coord→fanout / fanout→synth boundaries.  Empty string
            # is fine — hold check is a no-op without a project key.
            project_id=self.project_id or None,
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
            project_id=self.project_id or None,
            # Phase 127 (P127-F9): forward cancel_token so the swarm
            # honors user-pause at phase boundaries and inside fanout's
            # as_completed loop.
            cancel_token=cancel_token,
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

        # Phase 127: stash pause signal on self so the calling stage
        # can short-circuit instead of falling through to the
        # sequential/batched path (which would re-engage the held
        # endpoint).  Partial modules are still returned to the caller
        # for incremental write; the next run resumes the rest.
        if result.paused:
            self._last_swarm_paused = True
            self._last_swarm_pause_info = result.pause_info or {}
            info = result.pause_info or {}
            logger.info(
                "[Swarm/Cluster] paused on soft-hold "
                "(project=%s endpoint=%s) — %d/%d clusters completed at pause",
                info.get("project_id", "?"), info.get("endpoint_id", "?"),
                len(modules), len(items),
            )
        else:
            self._last_swarm_paused = False
            self._last_swarm_pause_info = {}

        # 2026-05-27 (Phase 141): detect partial swarm completion.
        # See group_reasoning.py:_run_swarm for the full rationale.
        attempted = len(result.worker_results)
        total_items = len(items)
        if not result.paused and attempted < total_items:
            self._last_swarm_incomplete = True
            self._last_swarm_incomplete_info = {
                "attempted": attempted,
                "total": total_items,
                "parsed_entries": len(modules),
                "wall_clock_seconds": result.stats.wall_clock_seconds,
            }
            logger.error(
                "[Swarm/Cluster] INCOMPLETE: only %d of %d workers attempted "
                "(rest cancelled by wall-time cap or stall) — wall_clock=%.0fs. "
                "Refusing to overwrite cache with truncated results.",
                attempted, total_items, result.stats.wall_clock_seconds,
            )
        else:
            self._last_swarm_incomplete = False
            self._last_swarm_incomplete_info = {}

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

    def _cluster_is_stale(self, member_node_ids: List[str]) -> bool:
        """A cluster is stale iff any member's underlying file is in
        changeset.modified | deleted. Phase 135.5b: lazy-loads the
        changeset from disk when not explicitly injected so API
        endpoints and non-pipeline callers get correct answers instead
        of the defensive 'all stale' fallback."""
        cs = self._resolve_changeset()
        if cs is None:
            return True
        for nid in member_node_ids:
            file_path = nid.replace("file:", "", 1) if nid.startswith("file:") else nid
            if file_path in cs.modified or file_path in cs.deleted:
                return True
        return False

    def _synthesize_batched(
        self,
        *,
        clusters: list,
        epistemic: dict,
        edges: list,
        modules: dict,
        progress_callback: Optional[Callable[..., None]],
        reused: int,
        total_work: int,
        synthesized_start: int,
        cancel_token: Optional[Any] = None,
    ) -> Tuple[int, int]:
        """Parallel batched-BYOK cluster synthesis via shared llm_pool.

        Submits all batches to the shared bounded ``llm_pool`` and collects
        results via ``as_completed``. The AIMD gate inside
        ``LLMClient.generate`` (PipelineScheduler.acquire_request) is the
        real throttle; fanning out here lets the gate discover the real
        per-provider concurrency ceiling instead of pinning in_flight=1.

        Returns ``(synthesized_delta, failed_delta)`` — caller aggregates
        into its own counters.
        """
        from .batch_profiles import BatchStage
        from .batch_prompts import (
            BATCHED_CLUSTER_SYSTEM,
            build_batched_cluster_prompt,
            get_structured_schema,
        )
        from .batch_strategy import BatchedResponseParser

        batch_size = self._batch_profile.batch_size(BatchStage.CLUSTERING)
        logger.info(
            "BATCHED cluster synthesis: %d clusters, batch_size=%d (%s profile) — parallel",
            len(clusters), batch_size, self._batch_profile.name.value,
        )
        schema = get_structured_schema("clustering")

        # Build per-batch work items up front so the LLM calls can fan out.
        batches: list[list[dict]] = []
        for batch_start in range(0, len(clusters), batch_size):
            batch = clusters[batch_start:batch_start + batch_size]
            items: list[dict] = []
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
            batches.append(items)

        def _call_batch(items: list[dict]) -> Tuple[list[dict], list[dict]]:
            prompt = build_batched_cluster_prompt(items)
            try:
                prompt_tokens = len(prompt) // 4
                num_predict, num_ctx, _warnings = compute_optimal_settings(
                    task=PipelineTask.CLUSTER,
                    prompt_tokens=prompt_tokens,
                    model=self.llm.model,
                    think=False,
                )
                if hold_paused_for_llm(self.llm, self.project_id, logger):
                    raise_hold_paused_for_llm(self.llm, self.project_id)
                text, _tokens = self.llm.generate(
                    prompt,
                    system=BATCHED_CLUSTER_SYSTEM,
                    num_predict=num_predict,
                    num_ctx=num_ctx,
                    response_schema=schema,
                    think=False,
                    max_chars=batched_max_chars("augmentation", len(items)),
                )
                results_list = BatchedResponseParser.parse(text, expected_count=len(items))
            except HoldPausedError:
                raise
            except Exception as e:
                logger.warning("Batched cluster synthesis failed for %d items: %s", len(items), e)
                results_list = []
            return items, results_list

        lock = threading.Lock()
        synthesized_delta = 0
        failed_delta = 0
        done_count = 0

        batch_timeout_sec = float(
            os.environ.get("PREP_CLUSTER_BATCH_TIMEOUT", "900")
        )

        pool = llm_pool
        futures = {pool.submit(_call_batch, items): items for items in batches}

        try:
            for future in as_completed(futures, timeout=batch_timeout_sec):
                if cancel_token and cancel_token.is_cancelled:
                    logger.info(
                        "Cluster synthesis cancelled after %d/%d batches — flushing partial results",
                        done_count, len(batches),
                    )
                    with lock:
                        self._write_modules(modules)
                    cancel_token.raise_if_cancelled()

                try:
                    items, results_list = future.result()
                except HoldPausedError:
                    raise
                except Exception as e:
                    logger.warning("Batched cluster future failed: %s", e)
                    with lock:
                        failed_delta += len(futures[future])
                        done_count += 1
                    continue

                for idx, item in enumerate(items):
                    cluster = item["_cluster"]
                    cluster_name = item["cluster_name"]
                    parsed = results_list[idx] if idx < len(results_list) else None
                    if not parsed:
                        parsed = {
                            "name": f"{cluster_name} Subsystem",
                            "summary": (
                                f"Cluster of {len(cluster.member_node_ids)} files related to "
                                f"{cluster.primary_tag}. (Batch synthesis failed)"
                            ),
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
                    with lock:
                        modules[module.module_id] = module
                        synthesized_delta += 1
                        total_synth = synthesized_start + synthesized_delta
                        if total_synth > 0 and total_synth % 10 == 0:
                            self._write_modules(modules)
                            logger.info(
                                "Cluster checkpoint saved at %d/%d clusters",
                                total_synth, total_work,
                            )

                with lock:
                    done_count += 1
                    if progress_callback:
                        progress_callback(
                            "cluster_synthesis",
                            reused + synthesized_delta + failed_delta,
                            total_work,
                            reused,
                        )
        except FutureTimeoutError:
            pending = [futures[f] for f in futures if not f.done()]
            logger.error(
                "Cluster batched synthesis timed out after %.0fs: %d/%d batches pending, "
                "cancelling and continuing.",
                batch_timeout_sec, len(pending), len(futures),
            )
            with lock:
                failed_delta += sum(len(pending_items) for pending_items in pending)
        finally:
            # Cancel pending futures unconditionally so an unhandled
            # exception (cancel_token raise, OOM, bug) does not orphan
            # worker slots on the shared pool.
            for f in futures:
                if not f.done():
                    f.cancel()
            # Shared pool — do NOT shut it down.

        return synthesized_delta, failed_delta

    def run(
        self,
        progress_callback: Optional[Callable[..., None]] = None,
        min_cluster_size: int = 2,
        cancel_token: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Run Pass 3 cluster synthesis.

        Incremental: reuses existing module entries for clusters whose
        member files are not in the current Changeset (modified | deleted),
        only calling the LLM for new or changed clusters.

        Steps:
        1. Load epistemic entries and edges.
        2. Build clusters by domain_tags + connectivity.
        3. Load existing modules; gate reuse via changeset (Phase 135).
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

        # Phase 135: reuse a cluster iff none of its member files is in
        # changeset.modified | deleted. No fingerprints — the changeset
        # is the canonical source of truth for "what changed."
        total_work = len(clusters)
        modules: Dict[str, ModuleEntry] = {}
        failed = 0
        reused = 0
        synthesized = 0

        # Phase 135: index existing modules by their member set, not module_id.
        # cluster_idx is a fresh monotonic counter each run, so module_ids
        # can collide across runs with DIFFERENT member sets (e.g., after a
        # file deletion shifts cluster numbering). Keying by membership
        # identity ensures we only reuse a ModuleEntry whose stored members
        # match the new cluster exactly — the Changeset.modified|deleted
        # check then verifies none of those members had content changes.
        #
        # Phase 136 Part 13b: the exact-membership lookup misses whenever
        # a cluster gains/loses even one member.  Adding the Jaccard
        # overlap fallback (mirrors Part 12 for group_reasoning) so a
        # cluster that's mostly the same as a cached one carries forward.
        # Without this, adding one file to a 20-file cluster invalidates
        # the entire cached module synthesis — the same cache-cliff
        # behavior that drove Module Synthesis to look like "rebuilding"
        # in the dashboard on incremental runs.
        existing_by_members: Dict[frozenset, ModuleEntry] = {
            frozenset(mod.member_files): mod for mod in existing_modules.values()
        }

        to_synthesize: List[Cluster] = []
        for cluster in clusters:
            module_id = f"module:{cluster.cluster_id.replace('cluster:', '')}"
            member_files = [
                nid.replace("file:", "", 1) if nid.startswith("file:") else nid
                for nid in cluster.member_node_ids
            ]
            ex = existing_by_members.get(frozenset(member_files))
            if ex is None:
                # Part 13b fallback — symmetric Jaccard match.
                ex = _find_overlapping_module(member_files, existing_modules)
            if ex is not None and not self._cluster_is_stale(cluster.member_node_ids):
                # Adopt the existing synthesis under the current module_id
                # so the output reflects this run's cluster naming.
                reused_mod = ModuleEntry(
                    module_id=module_id,
                    name=ex.name,
                    summary=ex.summary,
                    member_files=ex.member_files,
                    domain_tags=ex.domain_tags,
                    architecture_layers=ex.architecture_layers,
                    component_status=ex.component_status,
                    data_flow=ex.data_flow,
                    dependencies=ex.dependencies,
                    tech_debt_summary=ex.tech_debt_summary,
                    file_count=ex.file_count,
                    avg_epistemic_confidence=ex.avg_epistemic_confidence,
                    synthesized_at=ex.synthesized_at,
                    model=ex.model,
                )
                modules[module_id] = reused_mod
                reused += 1
                continue
            to_synthesize.append(cluster)

        logger.info(
            "Cluster reuse: %d total, %d reused (per changeset), %d to synthesize",
            total_work, reused, len(to_synthesize),
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

        # Phase 136 Part 13: gate on scheduler ownership of the swarm
        # window.  Pre-Phase-136 cluster.py and group_reasoning.py both
        # made an INDEPENDENT decision to use swarm based solely on
        # capability + enable + count — without asking whether the
        # scheduler had granted THIS stage exclusive endpoint access.
        # Result: two SwarmOrchestrators could run concurrently on the
        # same project (Module Synthesis 4× + Group Reasoning 6× on
        # the same Thinking endpoint), defeating the capacity
        # reservation.  If the scheduler has not granted this stage
        # the window, fall back to non-swarm dispatch.
        if use_swarm:
            from prep.services.pipeline.scheduler import pipeline_scheduler
            from prep.services.pipeline.stages import StageId
            if not pipeline_scheduler.is_my_swarm_window(
                self.project_id or "", StageId.CLUSTERING,
            ):
                logger.info(
                    "Cluster synthesis: scheduler did not grant swarm window "
                    "(another stage owns it or it failed to open) — falling "
                    "back to non-swarm dispatch",
                )
                use_swarm = False

        if use_swarm:
            logger.info(
                "Cluster synthesis: using SWARM orchestration (%s, %d clusters, tier=%s)",
                self.llm.model, len(to_synthesize), swarm_tier.value,
            )
            swarm_modules = self._run_swarm(
                to_synthesize, epistemic, edges, progress_callback, cancel_token,
            )
            # Phase 127: if the swarm paused on a soft-hold, persist
            # whatever partial modules we collected and return
            # ``paused=True`` immediately — DO NOT fall through to the
            # batched/sequential paths, which would re-engage the same
            # held endpoint.
            if getattr(self, "_last_swarm_paused", False):
                if swarm_modules:
                    modules.update(swarm_modules)
                    _deduplicate_module_names(modules)
                    self._write_modules(modules)
                synthesized = len(swarm_modules)
                duration_ms = (time.monotonic() - start) * 1000
                return {
                    "clusters": total_work,
                    "synthesized": synthesized,
                    "reused": reused,
                    "failed": 0,
                    "remaining": len(to_synthesize) - synthesized,
                    "total_files_clustered": sum(
                        len(m.member_files) for m in modules.values()
                    ),
                    "duration_ms": round(duration_ms, 1),
                    "swarm": True,
                    "paused": True,
                    "pause_info": getattr(self, "_last_swarm_pause_info", {}),
                }
            # 2026-05-27 (Phase 141): refuse to overwrite trace_modules.jsonl
            # with truncated results when the swarm completed only a
            # subset of clusters (wall-cap or stall fired).  See
            # group_reasoning.py for the parallel guard and rationale.
            if getattr(self, "_last_swarm_incomplete", False):
                info = getattr(self, "_last_swarm_incomplete_info", {})
                attempted = info.get("attempted", "?")
                total_items = info.get("total", "?")
                wall = info.get("wall_clock_seconds", 0.0)
                msg = (
                    f"Cluster synthesis swarm incomplete: only "
                    f"{attempted}/{total_items} workers attempted "
                    f"(wall_clock={wall:.0f}s).  Refusing to overwrite "
                    f"trace_modules.jsonl with truncated results — "
                    f"previous cache preserved.  Likely cause: swarm "
                    f"wall-time cap fired or stall detected.  Retry the "
                    f"stage; if it persists, check LLM endpoint latency "
                    f"or raise the wall budget."
                )
                logger.error(msg)
                raise RuntimeError(msg)
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
            synth_delta, fail_delta = self._synthesize_batched(
                clusters=to_synthesize,
                epistemic=epistemic,
                edges=edges,
                modules=modules,
                progress_callback=progress_callback,
                reused=reused,
                total_work=total_work,
                synthesized_start=synthesized,
                cancel_token=cancel_token,
            )
            synthesized += synth_delta
            failed += fail_delta

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
                        except HoldPausedError:
                            raise
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
