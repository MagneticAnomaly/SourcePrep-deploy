"""
Cluster Synthesis for CoDRAG (Pass 3).

Groups enriched file nodes into subsystem clusters based on domain_tags
and graph connectivity. For each cluster, generates a module-level
summary using the 14b model.

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
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .augmenter import LLMClient, _parse_json_response
from .epistemic_score import EpistemicEntry

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
            avg_epistemic_confidence=float(d.get("avg_epistemic_confidence", 0.0)),
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

Where component_status describes the overall implementation completeness of this subsystem.

JSON response:"""


# ── Clustering algorithm ─────────────────────────────────────────────

def build_clusters(
    epistemic_entries: Dict[str, EpistemicEntry],
    edges: List[Dict[str, Any]],
    min_cluster_size: int = 2,
) -> List[Cluster]:
    """Group enriched file nodes into clusters by domain_tags + connectivity.

    Algorithm:
    1. Group nodes by their primary domain tag (first tag in domain_tags).
    2. Within each tag group, run connected-component analysis using
       structural + inferred edges to split disconnected subgroups.
    3. Merge small clusters (< min_cluster_size) into nearest neighbor.

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

    return merged


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


# ── Synthesis engine ─────────────────────────────────────────────────

class ClusterSynthesizer:
    """Pass 3 cluster synthesis engine.

    Groups enriched nodes into subsystem clusters, then generates
    module-level summaries via the 14b model.
    """

    def __init__(
        self,
        llm: LLMClient,
        index_dir: Path,
    ):
        self.llm = llm
        self.index_dir = index_dir
        self.modules_path = index_dir / "trace_modules.jsonl"

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
    ) -> str:
        """Build a formatted string of member file summaries for the prompt."""
        parts: List[str] = []
        for nid in cluster.member_node_ids[:30]:  # cap at 30 files per prompt
            entry = epistemic.get(nid)
            file_path = nid.replace("file:", "", 1) if nid.startswith("file:") else nid
            if entry:
                summary = entry.extended_summary or "(no summary)"
                layer = entry.architecture_layer or "unknown"
                subsystem = entry.subsystem or ""
                tech = ", ".join(entry.tech_debt or []) if entry.tech_debt else ""
                line = f"- {file_path} [{layer}]: {summary}"
                if tech:
                    line += f" (tech debt: {tech})"
                parts.append(line)
            else:
                parts.append(f"- {file_path}: (not enriched)")
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
        """Synthesize a module entry for a cluster using the 14b model."""
        member_summaries = self._build_member_summaries(cluster, epistemic)
        external_deps = self._build_external_deps(cluster, edges, epistemic)

        # Compute avg epistemic confidence
        confidences = [
            epistemic[nid].epistemic_confidence
            for nid in cluster.member_node_ids
            if nid in epistemic
        ]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        # Collect architecture layers
        layers: Set[str] = set()
        for nid in cluster.member_node_ids:
            entry = epistemic.get(nid)
            if entry:
                layers.add(entry.architecture_layer)

        cluster_name = cluster.primary_tag.replace("_", " ").replace("-", " ").title()

        prompt = MODULE_SYNTHESIS_PROMPT.format(
            cluster_name=cluster_name,
            domain_tags=", ".join(sorted(cluster.all_tags)),
            file_count=len(cluster.member_node_ids),
            member_summaries=member_summaries,
            external_deps=external_deps,
        )

        try:
            text, tokens = self.llm.generate(prompt, system=MODULE_SYNTHESIS_SYSTEM, num_predict=2048)
        except Exception as e:
            logger.warning("14b LLM call failed for cluster %s: %s", cluster.cluster_id, e)
            return None

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Failed to parse 14b response for cluster %s", cluster.cluster_id)
            return None

        module_id = f"module:{cluster.primary_tag}"

        return ModuleEntry(
            module_id=module_id,
            name=str(parsed.get("name", cluster_name))[:200],
            summary=str(parsed.get("summary", ""))[:1000],
            member_files=[
                nid.replace("file:", "", 1) for nid in cluster.member_node_ids
            ],
            domain_tags=sorted(cluster.all_tags),
            architecture_layers=sorted(layers),
            component_status=parsed.get("component_status", "unknown"),
            data_flow=parsed.get("data_flow"),
            dependencies=parsed.get("dependencies"),
            tech_debt_summary=parsed.get("tech_debt_summary"),
            file_count=len(cluster.member_node_ids),
            avg_epistemic_confidence=avg_conf,
            synthesized_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
        )

    def run(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        min_cluster_size: int = 2,
    ) -> Dict[str, Any]:
        """Run Pass 3 cluster synthesis.

        Steps:
        1. Load epistemic entries and edges.
        2. Build clusters by domain_tags + connectivity.
        3. Synthesize each cluster into a module entry via 14b.
        4. Write trace_modules.jsonl.
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

        total_work = len(clusters)
        modules: Dict[str, ModuleEntry] = {}
        failed = 0

        for i, cluster in enumerate(clusters):
            if progress_callback:
                progress_callback("cluster_synthesis", i, total_work)

            module = self.synthesize_cluster(cluster, epistemic, edges)
            if module:
                modules[module.module_id] = module
            else:
                failed += 1

        # Write atomically
        self._write_modules(modules)

        duration_ms = (time.monotonic() - start) * 1000

        if progress_callback:
            progress_callback("cluster_complete", total_work, total_work)

        stats = {
            "clusters": len(clusters),
            "synthesized": len(modules),
            "failed": failed,
            "total_files_clustered": sum(len(c.member_node_ids) for c in clusters),
            "duration_ms": round(duration_ms, 1),
        }

        logger.info(
            "Cluster synthesis complete: %d clusters, %d modules synthesized in %.1fs",
            len(clusters), len(modules), duration_ms / 1000,
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
