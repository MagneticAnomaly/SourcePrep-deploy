"""
Epistemic Enrichment Engine for CoDRAG (Pass 2).

Uses a 14b model to deeply enrich each trace node with contextual
understanding: domain tags, architecture layer, subsystem, design
patterns, cross-references, tech debt signals, and epistemic confidence.

Processes nodes in reverse-topological order (leaf files first) so
that each node's neighbors already have enriched summaries when it's
processed. Inspired by RepoAgent's bottom-up documentation strategy.

See docs/Phase22_trace-epistomology/PATH_FORWARD.md Sprint 4.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .augmenter import AugmentationEntry, LLMClient, _parse_json_response
from .epistemic_score import EpistemicEntry, EpistemicScore, compute_epistemic_score

logger = logging.getLogger(__name__)

# ── Valid values ─────────────────────────────────────────────────────

VALID_ARCHITECTURE_LAYERS = frozenset({
    "presentation", "business_logic", "data", "infrastructure",
    "configuration", "testing", "documentation", "build", "unknown",
})

VALID_DOMAIN_TAGS = None  # free-form, validated by LLM

# ── Prompt templates ─────────────────────────────────────────────────

EPISTEMIC_SYSTEM = """You are an expert software architect performing deep analysis of a codebase.
You produce structured, accurate analysis grounded in the actual code and documentation.
You MUST respond with valid JSON only. No markdown, no explanation outside the JSON."""

EPISTEMIC_CODE_PROMPT = """Perform deep epistemic analysis of this code file.

File: {file_path}
Language: {language}

Pass 1 summary: {pass1_summary}
Pass 1 role: {pass1_role}

Neighbor context (already-enriched files this file connects to):
{neighbor_context}

Source excerpt:
```
{source_excerpt}
```

Respond with this exact JSON format:
{{"extended_summary": "2-4 sentence detailed description of this file's purpose, behavior, and significance in the codebase",
"domain_tags": ["tag1", "tag2"],
"architecture_layer": "business_logic",
"subsystem": "name-of-subsystem",
"design_patterns": ["singleton", "observer"],
"cross_references": ["path/to/related/doc.md"],
"tech_debt": ["explicit TODOs/FIXMEs or critical anti-patterns only; empty if none"],
"staleness_risk": "low|medium|high — how likely is this file's understanding to become stale",
"epistemic_confidence": 0.85}}

Where architecture_layer is one of: presentation, business_logic, data, infrastructure, configuration, testing, documentation, build, unknown
domain_tags: 1-4 descriptive tags for the domain this file operates in (e.g. "monetization", "auth", "ui", "data-persistence")
subsystem: the logical subsystem this file belongs to (e.g. "ad-framework", "user-auth", "trace-engine")
design_patterns: any notable patterns used (empty list if none)
cross_references: documentation files that describe or relate to this code
tech_debt: list ONLY explicit markers (TODO, FIXME) or severe architectural flaws. Do not list potential improvements or nitpicks.

JSON response:"""

EPISTEMIC_DOC_PROMPT = """Perform deep epistemic analysis of this documentation file.

File: {file_path}
Sections: {section_names}

Pass 1 summary: {pass1_summary}
Pass 1 doc_type: {pass1_doc_type}
Pass 1 doc_status: {pass1_doc_status}

File references extracted by static analysis: {file_refs}
Link targets: {link_targets}

Neighbor context (enriched files this doc references):
{neighbor_context}

Content excerpt:
```
{content_excerpt}
```

Respond with this exact JSON format:
{{"extended_summary": "2-4 sentence detailed description of what this document covers, its relationship to the codebase, and its current relevance",
"domain_tags": ["tag1", "tag2"],
"architecture_layer": "documentation",
"subsystem": "name-of-subsystem-this-doc-covers",
"doc_type": "design_spec",
"doc_status": "active",
"decision_chains": ["key decisions or conclusions documented here"],
"cross_references": ["src/path/to/code.py"],
"tech_debt": ["explicit stale content, broken references, or contradictions only; empty if none"],
"staleness_risk": "low|medium|high",
"epistemic_confidence": 0.85}}

Where doc_type is one of: research, design_spec, plan, guide, reference, changelog, readme, todo, status, analysis, overview
Where doc_status is one of: active, completed, shelved, superseded, draft, stale
tech_debt: list ONLY explicit issues found in the text. Do not hallucinate or guess.

JSON response:"""


# ── Topological ordering ─────────────────────────────────────────────

def topological_sort_files(
    file_nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Sort file nodes in reverse-topological order (leaves first).

    Uses Kahn's algorithm on the dependency graph formed by import/reference
    edges between file nodes. Files with no outbound dependencies (leaf files
    like utilities, configs) are processed first, so their enriched summaries
    are available when dependent files are processed.

    Falls back to original order for nodes in cycles.
    """
    file_ids = {n["id"] for n in file_nodes}
    file_by_id = {n["id"]: n for n in file_nodes}

    # Build adjacency: source depends on target (imports/references target)
    dependents: Dict[str, Set[str]] = defaultdict(set)  # target → set of sources that depend on it
    dependencies: Dict[str, int] = {fid: 0 for fid in file_ids}

    for e in edges:
        src, tgt = e.get("source", ""), e.get("target", "")
        kind = e.get("kind", "")
        if kind in ("imports", "references", "links_to", "inferred"):
            if src in file_ids and tgt in file_ids and src != tgt:
                dependents[tgt].add(src)
                dependencies[src] = dependencies.get(src, 0) + 1

    # Kahn's algorithm: start with nodes that have no dependencies (leaves)
    queue = deque(fid for fid, dep_count in dependencies.items() if dep_count == 0)
    result: List[Dict[str, Any]] = []

    while queue:
        node_id = queue.popleft()
        if node_id in file_by_id:
            result.append(file_by_id[node_id])
        for dependent in dependents.get(node_id, set()):
            dependencies[dependent] -= 1
            if dependencies[dependent] == 0:
                queue.append(dependent)

    # Add any remaining nodes (cycles) at the end
    processed = {n["id"] for n in result}
    for node in file_nodes:
        if node["id"] not in processed:
            result.append(node)

    return result


def topological_sort_into_tiers(
    file_nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Sort file nodes into dependency tiers for batched enrichment.

    Returns a list of tiers, where each tier is a list of nodes that can
    be processed in parallel (they only depend on nodes in earlier tiers).

    Tier 0: leaf files (no outbound dependencies)
    Tier 1: files that only depend on tier-0 files
    Tier N: files that depend on tiers 0..N-1

    Nodes in cycles are appended as a final tier.
    """
    file_ids = {n["id"] for n in file_nodes}
    file_by_id = {n["id"]: n for n in file_nodes}

    # Build adjacency: source depends on target
    dependents: Dict[str, Set[str]] = defaultdict(set)
    dependencies: Dict[str, int] = {fid: 0 for fid in file_ids}

    for e in edges:
        src, tgt = e.get("source", ""), e.get("target", "")
        kind = e.get("kind", "")
        if kind in ("imports", "references", "links_to", "inferred"):
            if src in file_ids and tgt in file_ids and src != tgt:
                dependents[tgt].add(src)
                dependencies[src] = dependencies.get(src, 0) + 1

    # Modified Kahn's: collect nodes level by level
    tiers: List[List[Dict[str, Any]]] = []
    current_queue = [fid for fid, dep in dependencies.items() if dep == 0]

    while current_queue:
        tier = [file_by_id[fid] for fid in current_queue if fid in file_by_id]
        if tier:
            tiers.append(tier)

        next_queue: List[str] = []
        for node_id in current_queue:
            for dependent in dependents.get(node_id, set()):
                dependencies[dependent] -= 1
                if dependencies[dependent] == 0:
                    next_queue.append(dependent)
        current_queue = next_queue

    # Remaining nodes (cycles) as a final tier
    processed = {n["id"] for tier in tiers for n in tier}
    cycle_nodes = [n for n in file_nodes if n["id"] not in processed]
    if cycle_nodes:
        tiers.append(cycle_nodes)

    return tiers


# ── Enrichment engine ────────────────────────────────────────────────

class EpistemicEnricher:
    """Pass 2 enrichment engine using a 14b model.

    Processes nodes in reverse-topological order, building up contextual
    understanding from leaves to roots.
    """

    def __init__(
        self,
        llm: LLMClient,
        repo_root: Path,
        index_dir: Path,
        batch_profile: Optional["BatchProfile"] = None,
    ):
        self.llm = llm
        self.repo_root = repo_root
        self.index_dir = index_dir
        self._batch_profile = batch_profile
        self.epistemic_path = index_dir / "trace_epistemic.jsonl"
        self.epistemic_manifest_path = index_dir / "trace_epistemic_manifest.json"

    def load_existing(self) -> Dict[str, EpistemicEntry]:
        """Load existing epistemic entries."""
        entries: Dict[str, EpistemicEntry] = {}
        if self.epistemic_path.exists():
            with open(self.epistemic_path, "r", encoding="utf-8") as f:
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

    def load_augmentations(self) -> Dict[str, Dict[str, Any]]:
        """Load Pass 1 augmentations as dicts."""
        aug_path = self.index_dir / "trace_augmented.jsonl"
        entries: Dict[str, Dict[str, Any]] = {}
        if aug_path.exists():
            with open(aug_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            d = json.loads(line)
                            entries[d["node_id"]] = d
                        except (json.JSONDecodeError, KeyError):
                            continue
        return entries

    def load_trace_nodes(self) -> List[Dict[str, Any]]:
        """Load trace nodes."""
        nodes_path = self.index_dir / "trace_nodes.jsonl"
        nodes: List[Dict[str, Any]] = []
        if nodes_path.exists():
            with open(nodes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        nodes.append(json.loads(line))
        return nodes

    def load_trace_edges(self) -> List[Dict[str, Any]]:
        """Load trace edges (structural + inferred)."""
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

    def _get_neighbor_context(
        self,
        node_id: str,
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        augmentations: Dict[str, Dict[str, Any]],
        epistemic_entries: Dict[str, EpistemicEntry],
        max_neighbors: int = 8,
    ) -> str:
        """Build a context string from enriched neighbors."""
        neighbor_ids: Set[str] = set()
        for e in edges:
            if e.get("source") == node_id:
                neighbor_ids.add(e["target"])
            elif e.get("target") == node_id:
                neighbor_ids.add(e["source"])

        # Only include file-level neighbors (not section or symbol nodes for context)
        file_neighbors = [
            nid for nid in neighbor_ids
            if nid.startswith("file:") and nid in nodes_by_id
        ]

        if not file_neighbors:
            return "(no enriched neighbors)"

        parts: List[str] = []
        for nid in file_neighbors[:max_neighbors]:
            node = nodes_by_id.get(nid, {})
            fp = node.get("file_path", nid)

            # Prefer epistemic extended_summary, fall back to augmentation summary
            if nid in epistemic_entries:
                ep = epistemic_entries[nid]
                summary = ep.extended_summary or "(enriched, no summary)"
                tags = ", ".join(ep.domain_tags) if ep.domain_tags else ""
                parts.append(f"- {fp}: {summary}" + (f" [{tags}]" if tags else ""))
            elif nid in augmentations:
                aug = augmentations[nid]
                summary = aug.get("summary", "(augmented, no summary)")
                parts.append(f"- {fp}: {summary} (Pass 1 only)")
            else:
                parts.append(f"- {fp}: (not yet augmented)")

        return "\n".join(parts)

    def _get_file_excerpt(self, file_path: str, max_lines: int = 150) -> str:
        """Read file excerpt for the 14b prompt."""
        try:
            full_path = self.repo_root / file_path
            if not full_path.exists():
                return ""
            text = full_path.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()[:max_lines]
            return "\n".join(lines)
        except Exception:
            return ""

    def _get_section_names(
        self,
        node_id: str,
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """Get section names for a file node."""
        names = []
        for e in edges:
            if e.get("source") == node_id and e.get("kind") == "contains":
                target = nodes_by_id.get(e["target"])
                if target and target.get("kind") == "section":
                    names.append(target.get("name", ""))
        return names

    def _get_reference_paths(
        self,
        node_id: str,
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
    ) -> Tuple[List[str], List[str]]:
        """Get file refs and link targets for a node."""
        file_refs: List[str] = []
        link_targets: List[str] = []
        for e in edges:
            if e.get("source") == node_id:
                target = nodes_by_id.get(e["target"])
                if not target:
                    continue
                fp = target.get("file_path", "")
                if e.get("kind") == "references":
                    file_refs.append(fp)
                elif e.get("kind") == "links_to":
                    link_targets.append(fp)
        return file_refs, link_targets

    def _needs_enrichment(
        self,
        node: Dict[str, Any],
        existing: Dict[str, EpistemicEntry],
        augmentations: Dict[str, Dict[str, Any]],
    ) -> bool:
        """Check if a file node needs (re-)enrichment."""
        node_id = node["id"]
        # Must have a Pass 1 augmentation
        if node_id not in augmentations:
            return False
        # Not yet enriched
        if node_id not in existing:
            return True
        # Already enriched — skip for now (re-enrichment is Pass 4+)
        return False

    def enrich_node(
        self,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        augmentations: Dict[str, Dict[str, Any]],
        epistemic_entries: Dict[str, EpistemicEntry],
    ) -> Optional[EpistemicEntry]:
        """Enrich a single file node with the 14b model."""
        file_path = node.get("file_path", "")
        node_id = node["id"]
        aug = augmentations.get(node_id, {})
        is_markdown = node.get("language") == "markdown" or file_path.endswith((".md", ".markdown"))

        # Build neighbor context
        neighbor_context = self._get_neighbor_context(
            node_id, edges, nodes_by_id, augmentations, epistemic_entries
        )

        if is_markdown:
            return self._enrich_doc(node, edges, nodes_by_id, aug, neighbor_context)
        else:
            return self._enrich_code(node, aug, neighbor_context)

    def _enrich_code(
        self,
        node: Dict[str, Any],
        aug: Dict[str, Any],
        neighbor_context: str,
    ) -> Optional[EpistemicEntry]:
        """Enrich a code file."""
        file_path = node.get("file_path", "")
        source = self._get_file_excerpt(file_path, max_lines=150)
        if not source:
            return None

        prompt = EPISTEMIC_CODE_PROMPT.format(
            file_path=file_path,
            language=node.get("language", "unknown"),
            pass1_summary=aug.get("summary", "(none)"),
            pass1_role=aug.get("role", "unknown"),
            neighbor_context=neighbor_context,
            source_excerpt=source,
        )

        return self._call_and_parse(node["id"], file_path, prompt)

    def _enrich_doc(
        self,
        node: Dict[str, Any],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        aug: Dict[str, Any],
        neighbor_context: str,
    ) -> Optional[EpistemicEntry]:
        """Enrich a documentation file."""
        file_path = node.get("file_path", "")
        # Increased from 200 to 2000 lines to capture larger scope concepts
        content = self._get_file_excerpt(file_path, max_lines=3000)
        if not content:
            return None

        section_names = self._get_section_names(node["id"], edges, nodes_by_id)
        file_refs, link_targets = self._get_reference_paths(node["id"], edges, nodes_by_id)

        prompt = EPISTEMIC_DOC_PROMPT.format(
            file_path=file_path,
            section_names=", ".join(section_names[:20]) or "(none)",
            pass1_summary=aug.get("summary", "(none)"),
            pass1_doc_type=aug.get("doc_type", "unknown"),
            pass1_doc_status=aug.get("doc_status", "unknown"),
            file_refs=", ".join(file_refs[:15]) or "(none)",
            link_targets=", ".join(link_targets[:15]) or "(none)",
            neighbor_context=neighbor_context,
            content_excerpt=content,
        )

        return self._call_and_parse(node["id"], file_path, prompt, is_doc=True)

    def _call_and_parse(
        self,
        node_id: str,
        file_path: str,
        prompt: str,
        is_doc: bool = False,
    ) -> Optional[EpistemicEntry]:
        """Call the 14b LLM and parse the response into an EpistemicEntry."""
        try:
            text, tokens = self.llm.generate(prompt, system=EPISTEMIC_SYSTEM, num_predict=2048)
        except Exception as e:
            logger.warning("14b LLM call failed for %s: %s", file_path, e)
            return None

        parsed = _parse_json_response(text)
        if not parsed:
            logger.warning("Failed to parse 14b response for %s — raw: %.200s", file_path, text)
            return None

        # Validate architecture_layer
        arch = parsed.get("architecture_layer", "unknown")
        if arch not in VALID_ARCHITECTURE_LAYERS:
            arch = "unknown"

        # Build entry
        entry = EpistemicEntry(
            node_id=node_id,
            extended_summary=str(parsed.get("extended_summary", ""))[:1000],
            domain_tags=[str(t) for t in parsed.get("domain_tags", [])][:6],
            architecture_layer=arch,
            subsystem=parsed.get("subsystem"),
            design_patterns=parsed.get("design_patterns"),
            cross_references=parsed.get("cross_references"),
            tech_debt=parsed.get("tech_debt"),
            staleness_risk=parsed.get("staleness_risk"),
            epistemic_confidence=max(0.0, min(1.0, float(parsed.get("epistemic_confidence", 0.5)))),
            pass_number=2,
            enriched_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
        )

        # Doc-specific fields
        if is_doc:
            entry.doc_type = parsed.get("doc_type")
            entry.doc_status = parsed.get("doc_status")
            entry.decision_chains = parsed.get("decision_chains")

        return entry

    def _enrich_tier_batched(
        self,
        tier_nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        augmentations: Dict[str, Dict[str, Any]],
        enriched: Dict[str, EpistemicEntry],
        code_batch_size: int,
        doc_batch_size: int,
    ) -> Tuple[int, int]:
        """Enrich a single tier of nodes using batched LLM calls.

        All nodes in a tier are independent (they only depend on earlier
        tiers), so they can be batched together.

        Returns (done_count, failed_count).
        """
        from .batch_prompts import (
            BATCHED_EPISTEMIC_CODE_SYSTEM,
            BATCHED_EPISTEMIC_DOC_SYSTEM,
            build_batched_epistemic_code_prompt,
            build_batched_epistemic_doc_prompt,
            get_structured_schema,
        )
        from .batch_strategy import BatchedResponseParser

        done = 0
        failed = 0

        code_schema = get_structured_schema("epistemic_code")
        doc_schema = get_structured_schema("epistemic_doc")

        # Split into code and doc nodes
        code_nodes = []
        doc_nodes = []
        for node in tier_nodes:
            fp = node.get("file_path", "")
            lang = node.get("language", "")
            is_md = lang == "markdown" or fp.endswith((".md", ".markdown"))
            if is_md:
                doc_nodes.append(node)
            else:
                code_nodes.append(node)

        # Batch code nodes
        for batch_start in range(0, len(code_nodes), code_batch_size):
            batch = code_nodes[batch_start:batch_start + code_batch_size]
            items = []
            for node in batch:
                fp = node.get("file_path", "")
                nid = node["id"]
                aug = augmentations.get(nid, {})
                neighbor_ctx = self._get_neighbor_context(
                    nid, edges, nodes_by_id, augmentations, enriched
                )
                excerpt = self._get_file_excerpt(fp, max_lines=150)
                items.append({
                    "file_path": fp,
                    "language": node.get("language", "unknown"),
                    "pass1_summary": aug.get("summary", "(none)"),
                    "pass1_role": aug.get("role", "unknown"),
                    "neighbor_context": neighbor_ctx,
                    "source_excerpt": excerpt,
                    "_node": node,
                    "_node_id": nid,
                })

            prompt = build_batched_epistemic_code_prompt(items)
            try:
                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_EPISTEMIC_CODE_SYSTEM,
                    num_predict=len(items) * 400,
                    response_schema=code_schema,
                )
                results_list = BatchedResponseParser.parse(text, expected_count=len(items))
            except Exception as e:
                logger.warning("Batched epistemic code failed for %d items: %s", len(items), e)
                results_list = []

            for idx, item in enumerate(items):
                nid = item["_node_id"]
                parsed = results_list[idx] if idx < len(results_list) else None
                if parsed:
                    arch = parsed.get("architecture_layer", "unknown")
                    if arch not in VALID_ARCHITECTURE_LAYERS:
                        arch = "unknown"
                    entry = EpistemicEntry(
                        node_id=nid,
                        extended_summary=str(parsed.get("extended_summary", ""))[:1000],
                        domain_tags=[str(t) for t in parsed.get("domain_tags", [])][:6],
                        architecture_layer=arch,
                        subsystem=parsed.get("subsystem"),
                        design_patterns=parsed.get("design_patterns"),
                        cross_references=parsed.get("cross_references"),
                        tech_debt=parsed.get("tech_debt"),
                        staleness_risk=parsed.get("staleness_risk"),
                        epistemic_confidence=max(0.0, min(1.0, float(parsed.get("epistemic_confidence", 0.5)))),
                        pass_number=2,
                        enriched_at=datetime.now(timezone.utc).isoformat(),
                        model=self.llm.model,
                    )
                    enriched[nid] = entry
                    done += 1
                else:
                    failed += 1

        # Batch doc nodes
        for batch_start in range(0, len(doc_nodes), doc_batch_size):
            batch = doc_nodes[batch_start:batch_start + doc_batch_size]
            items = []
            for node in batch:
                fp = node.get("file_path", "")
                nid = node["id"]
                aug = augmentations.get(nid, {})
                section_names = self._get_section_names(nid, edges, nodes_by_id)
                file_refs, link_targets = self._get_reference_paths(nid, edges, nodes_by_id)
                neighbor_ctx = self._get_neighbor_context(
                    nid, edges, nodes_by_id, augmentations, enriched
                )
                excerpt = self._get_file_excerpt(fp, max_lines=3000)
                items.append({
                    "file_path": fp,
                    "section_names": ", ".join(section_names[:20]) or "(none)",
                    "pass1_summary": aug.get("summary", "(none)"),
                    "pass1_doc_type": aug.get("doc_type", "unknown"),
                    "pass1_doc_status": aug.get("doc_status", "unknown"),
                    "file_refs": ", ".join(file_refs[:10]) or "(none)",
                    "link_targets": ", ".join(link_targets[:10]) or "(none)",
                    "neighbor_context": neighbor_ctx,
                    "content_excerpt": excerpt,
                    "_node": node,
                    "_node_id": nid,
                })

            prompt = build_batched_epistemic_doc_prompt(items)
            try:
                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_EPISTEMIC_DOC_SYSTEM,
                    num_predict=len(items) * 400,
                    response_schema=doc_schema,
                )
                results_list = BatchedResponseParser.parse(text, expected_count=len(items))
            except Exception as e:
                logger.warning("Batched epistemic doc failed for %d items: %s", len(items), e)
                results_list = []

            for idx, item in enumerate(items):
                nid = item["_node_id"]
                parsed = results_list[idx] if idx < len(results_list) else None
                if parsed:
                    arch = parsed.get("architecture_layer", "documentation")
                    if arch not in VALID_ARCHITECTURE_LAYERS:
                        arch = "documentation"
                    entry = EpistemicEntry(
                        node_id=nid,
                        extended_summary=str(parsed.get("extended_summary", ""))[:1000],
                        domain_tags=[str(t) for t in parsed.get("domain_tags", [])][:6],
                        architecture_layer=arch,
                        subsystem=parsed.get("subsystem"),
                        design_patterns=parsed.get("design_patterns"),
                        cross_references=parsed.get("cross_references"),
                        tech_debt=parsed.get("tech_debt"),
                        staleness_risk=parsed.get("staleness_risk"),
                        epistemic_confidence=max(0.0, min(1.0, float(parsed.get("epistemic_confidence", 0.5)))),
                        pass_number=2,
                        enriched_at=datetime.now(timezone.utc).isoformat(),
                        model=self.llm.model,
                        doc_type=parsed.get("doc_type"),
                        doc_status=parsed.get("doc_status"),
                        decision_chains=parsed.get("decision_chains"),
                    )
                    enriched[nid] = entry
                    done += 1
                else:
                    failed += 1

        return done, failed

    def run(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        max_items: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run Pass 2 epistemic enrichment on all eligible file nodes.

        Steps:
        1. Load trace graph, augmentations, existing epistemic entries.
        2. Sort file nodes in reverse-topological order (or into tiers for batching).
        3. Enrich each node with the LLM + neighbor context.
        4. Write trace_epistemic.jsonl overlay atomically.
        """
        start = time.monotonic()

        nodes = self.load_trace_nodes()
        edges = self.load_trace_edges()
        augmentations = self.load_augmentations()
        existing = self.load_existing()

        if not nodes:
            logger.info("No trace nodes found, skipping epistemic enrichment")
            return {"total": 0, "enriched": 0, "skipped": 0, "failed": 0}

        nodes_by_id = {n["id"]: n for n in nodes}

        # Only enrich non-empty file nodes (sections and symbols get their scores from parent)
        # We explicitly check for content to exclude empty __init__.py files from the total count.
        all_file_nodes = [n for n in nodes if n.get("kind") == "file"]
        file_nodes = []
        for n in all_file_nodes:
            fp = n.get("file_path", "")
            # Check if file has any content (reading just 1 line is enough)
            if self._get_file_excerpt(fp, max_lines=1):
                file_nodes.append(n)

        # Filter to nodes needing enrichment
        to_enrich = [n for n in file_nodes if self._needs_enrichment(n, existing, augmentations)]

        if max_items:
            to_enrich = to_enrich[:max_items]

        total_work = len(to_enrich)
        total_file_count = len(file_nodes)
        existing_count = len(existing)
        logger.info(
            "Epistemic enrichment: %d files to enrich (%d existing, %d total file nodes)",
            total_work, existing_count, total_file_count,
        )

        # Start with existing entries
        enriched = dict(existing)
        done = 0
        failed = 0

        if progress_callback:
            progress_callback("epistemic_enrichment", existing_count, total_file_count)

        # Decide: batched (BYOK) or sequential (local)
        use_batching = (
            self._batch_profile is not None
            and self._batch_profile.name.value != "off"
        )

        if use_batching and to_enrich:
            from .batch_profiles import BatchStage
            code_batch_size = self._batch_profile.batch_size(BatchStage.EPISTEMIC_CODE)
            doc_batch_size = self._batch_profile.batch_size(BatchStage.EPISTEMIC_DOC)

            # Sort into tiers for tier-based batching
            tiers = topological_sort_into_tiers(to_enrich, edges)
            logger.info(
                "BATCHED epistemic enrichment: %d files in %d tiers, code_batch_size=%d, doc_batch_size=%d (%s profile)",
                total_work, len(tiers), code_batch_size, doc_batch_size, self._batch_profile.name.value,
            )
            for tier_idx, tier in enumerate(tiers):
                tier_done, tier_failed = self._enrich_tier_batched(
                    tier, edges, nodes_by_id, augmentations, enriched, code_batch_size, doc_batch_size,
                )
                done += tier_done
                failed += tier_failed
                logger.info(
                    "Tier %d/%d complete: %d enriched, %d failed (%d items in tier)",
                    tier_idx + 1, len(tiers), tier_done, tier_failed, len(tier),
                )
                if progress_callback:
                    progress_callback("epistemic_enrichment", existing_count + done + failed, total_file_count)
        else:
            # Sort in reverse-topological order (leaves first)
            to_enrich = topological_sort_files(to_enrich, edges)

            # Sequential by design: each node's neighbor context reads from 'enriched',
            # which accumulates results from earlier nodes in topological order.
            # Parallelizing would break the cascading context benefit.
            for node in to_enrich:
                entry = self.enrich_node(node, edges, nodes_by_id, augmentations, enriched)
                if entry:
                    enriched[entry.node_id] = entry
                    done += 1
                else:
                    failed += 1

                if progress_callback:
                    progress_callback("epistemic_enrichment", existing_count + done + failed, total_file_count)

        # Write atomically
        self._write_epistemic(enriched)

        duration_ms = (time.monotonic() - start) * 1000

        if progress_callback:
            progress_callback("epistemic_complete", total_file_count, total_file_count)

        stats = {
            "total_file_nodes": len(file_nodes),
            "enriched_this_run": done,
            "failed_this_run": failed,
            "skipped": len(file_nodes) - total_work,
            "total_enriched": len(enriched),
            "duration_ms": round(duration_ms, 1),
        }

        logger.info(
            "Epistemic enrichment complete: %d enriched, %d failed in %.1fs",
            done, failed, duration_ms / 1000,
        )

        return stats

    def _write_epistemic(self, entries: Dict[str, EpistemicEntry]) -> None:
        """Write epistemic entries atomically."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        sorted_entries = sorted(entries.values(), key=lambda e: e.node_id)

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", dir=self.index_dir, delete=False, encoding="utf-8",
        )
        try:
            for entry in sorted_entries:
                tmp.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.epistemic_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    def compute_all_scores(self) -> Dict[str, EpistemicScore]:
        """Compute epistemic scores for all file nodes.

        Requires trace_nodes.jsonl, trace_edges.jsonl, trace_augmented.jsonl,
        and trace_epistemic.jsonl to all exist.
        """
        nodes = self.load_trace_nodes()
        edges = self.load_trace_edges()
        augmentations = self.load_augmentations()
        epistemic = self.load_existing()

        if not nodes:
            return {}

        nodes_by_id = {n["id"]: n for n in nodes}
        enriched_ids = set(epistemic.keys())

        # Build neighbor map
        neighbor_map: Dict[str, Set[str]] = defaultdict(set)
        for e in edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            if src in nodes_by_id and tgt in nodes_by_id:
                neighbor_map[src].add(tgt)
                neighbor_map[tgt].add(src)

        # Count cross-references per node
        cross_ref_counts: Dict[str, int] = defaultdict(int)
        for e in edges:
            if e.get("kind") in ("references", "links_to"):
                src, tgt = e.get("source", ""), e.get("target", "")
                # A reference from a doc to code (or vice versa) counts for both
                cross_ref_counts[src] += 1
                cross_ref_counts[tgt] += 1

        # Load file hashes
        manifest_path = self.index_dir / "trace_manifest.json"
        file_hashes: Dict[str, str] = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                file_hashes = manifest.get("file_hashes", {})
            except Exception:
                pass

        scores: Dict[str, EpistemicScore] = {}
        file_nodes = [n for n in nodes if n.get("kind") == "file"]

        for node in file_nodes:
            nid = node["id"]
            score = compute_epistemic_score(
                node_id=nid,
                augmentation=augmentations.get(nid),
                epistemic=epistemic.get(nid),
                neighbor_ids=neighbor_map.get(nid, set()),
                enriched_node_ids=enriched_ids,
                cross_ref_count=cross_ref_counts.get(nid, 0),
                current_file_hashes=file_hashes,
            )
            scores[nid] = score

        return scores
