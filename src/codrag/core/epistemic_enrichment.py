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
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from codrag.core.context_config import PipelineTask, compute_optimal_settings
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .augmenter import AugmentationEntry
from .llm_client import LLMClient, _get_llm_concurrency, _parse_confidence, _parse_json_response
from .epistemic_score import EpistemicEntry, EpistemicScore, compute_epistemic_score
from codrag.core.llm_client import TASK_MAX_CHARS, batched_max_chars

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

    def load_file_hashes(self) -> Dict[str, str]:
        """Load file hashes from the trace manifest for staleness detection."""
        manifest_path = self.index_dir / "trace_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                return manifest.get("file_hashes", {})
            except Exception:
                pass
        return {}

    def _needs_enrichment(
        self,
        node: Dict[str, Any],
        existing: Dict[str, EpistemicEntry],
        augmentations: Dict[str, Dict[str, Any]],
        file_hashes: Dict[str, str],
    ) -> bool:
        """Check if a file node needs (re-)enrichment."""
        node_id = node["id"]
        # Must have a Pass 1 augmentation
        if node_id not in augmentations:
            return False
        # Not yet enriched
        if node_id not in existing:
            return True
        # Check if source file changed since last enrichment
        file_path = node.get("file_path", "")
        if file_path:
            current_hash = file_hashes.get(file_path)
            # Find the file hash that was recorded during this node's original augmentation
            # since EpistemicEntry doesn't store the hash directly.
            aug_hash = augmentations[node_id].get("file_hash")
            if current_hash and aug_hash and current_hash != aug_hash:
                return True
        # Already enriched and unchanged
        return False

    def get_pending_nodes(self, trace_idx: Any = None) -> List[Dict[str, Any]]:
        """Get a list of file nodes that need enrichment.
        Args:
            trace_idx: Optional trace index (ignored, uses disk loading for accuracy).
        """
        nodes = self.load_trace_nodes()
        file_nodes = [n for n in nodes if n.get("kind") == "file"]
        if not file_nodes:
            return []
            
        existing = self.load_existing()
        augmentations = self.load_augmentations()
        file_hashes = self.load_file_hashes()
        
        pending_nodes = []
        for node in file_nodes:
            if self._needs_enrichment(node, existing, augmentations, file_hashes):
                pending_nodes.append(node)
                
        return pending_nodes

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
        """Call the deep reasoning LLM and parse the response into an EpistemicEntry."""
        import time as _time

        # Guard: skip files with absurdly large prompts (minified bundles, etc.)
        # These crash Ollama (500 error) and waste time retrying every iteration.
        _MAX_PROMPT_CHARS = 200_000
        if len(prompt) > _MAX_PROMPT_CHARS:
            logger.warning(
                "[Epistemic] Skipping %s — prompt too large (%d chars > %d limit). "
                "Likely a minified bundle; exclude it via exclude_globs.",
                file_path, len(prompt), _MAX_PROMPT_CHARS,
            )
            return None

        _call_start = _time.monotonic()
        logger.info("[Epistemic] Sending LLM call for: %s (prompt=%d chars)", file_path, len(prompt))
        try:
            # json_mode=False: thinking models (qwen3.5, deepseek-r1, etc.)
            # return empty responses when Ollama's format:json is forced.
            # Our _parse_json_response already handles JSON extraction from
            # free-text output, including <think> tags and markdown fences.
            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, warnings = compute_optimal_settings(
                task=PipelineTask.EPISTEMIC,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=False,
            )

            text, tokens = self.llm.generate(
                prompt, system=EPISTEMIC_SYSTEM, num_predict=num_predict, num_ctx=num_ctx,
                json_mode=False, think=False,
                max_chars=TASK_MAX_CHARS["epistemic"],
            )
            _call_elapsed = _time.monotonic() - _call_start
            logger.info("[Epistemic] LLM responded for %s in %.1fs (%d tokens)", file_path, _call_elapsed, tokens)
        except Exception as e:
            _call_elapsed = _time.monotonic() - _call_start
            logger.warning("Deep reasoning LLM call failed for %s after %.1fs: %s", file_path, _call_elapsed, e)
            return None

        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning("Failed to parse deep reasoning response for %s — raw: %.200s", file_path, text)
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
            epistemic_confidence=_parse_confidence(parsed.get("epistemic_confidence"), 0.5),
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
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        current_progress: int = 0,
        total_progress: int = 0,
        cancel_token: Optional[Any] = None,
        progress_baseline: int = 0,
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

        # Phase 53: 3-way classification replaces binary is_md split
        from .content_class import ContentClass, classify_nodes

        classified = classify_nodes(tier_nodes)
        code_nodes = classified.get(ContentClass.STRUCTURED_CODE, [])
        # Both structured docs and narrative get doc enrichment path,
        # but narrative gets reduced excerpt size (handled in payload build below)
        doc_nodes = (
            classified.get(ContentClass.STRUCTURED_DOCS, [])
            + classified.get(ContentClass.UNSTRUCTURED_NARRATIVE, [])
        )
        # Track which nodes are narrative for excerpt size adjustment
        _narrative_ids = {
            n["id"] for n in classified.get(ContentClass.UNSTRUCTURED_NARRATIVE, [])
        }

        from .batch_profiles import get_batch_concurrency
        _concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)

        # Pre-build all code batch payloads
        code_batches = []
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
            code_batches.append(items)

        def _call_code_batch(items):
            prompt = build_batched_epistemic_code_prompt(items)
            try:
                prompt_tokens = len(prompt) // 4
                num_predict, num_ctx, warnings = compute_optimal_settings(
                    task=PipelineTask.EPISTEMIC,
                    prompt_tokens=prompt_tokens,
                    model=self.llm.model,
                    think=False,
                )

                if len(items) > 1:
                    num_predict = num_predict * len(items) + 500
                    from codrag.core.context_config import compute_num_ctx
                    num_ctx = compute_num_ctx(prompt_tokens, num_predict, self.llm.model)

                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_EPISTEMIC_CODE_SYSTEM,
                    num_predict=num_predict, num_ctx=num_ctx,
                    response_schema=code_schema,
                    max_chars=batched_max_chars("epistemic", len(items)),
                )
                return BatchedResponseParser.parse(text, expected_count=len(items))
            except Exception as e:
                logger.warning("Batched epistemic code failed for %d items: %s", len(items), e)
                return []

        # Dispatch code batches (sequentially for concurrency=1 to avoid thread accumulation)
        _cancelled = False

        def _iter_epi_code_results():
            if _concurrency <= 1 or len(code_batches) <= 1:
                for batch_items in code_batches:
                    try:
                        yield batch_items, _call_code_batch(batch_items)
                    except Exception as e:
                        logger.warning("Code batch failed: %s", e)
                        yield batch_items, []
            else:
                with ThreadPoolExecutor(max_workers=min(_concurrency, len(code_batches))) as pool:
                    fmap = {pool.submit(_call_code_batch, items): items for items in code_batches}
                    for future in as_completed(fmap):
                        batch_items = fmap[future]
                        try:
                            yield batch_items, future.result()
                        except Exception as e:
                            logger.warning("Code batch future failed: %s", e)
                            yield batch_items, []

        for items, results_list in _iter_epi_code_results():

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
            if progress_callback:
                progress_callback("epistemic_enrichment", current_progress + done + failed, total_progress, progress_baseline)

            # Intra-tier checkpoint: flush after every batch so a crash mid-tier
            # does not lose all the work in the active tier. Important for
            # cloud-batched profiles where a single tier can hold thousands of
            # nodes and the daemon may not survive long enough to reach the
            # post-tier checkpoint in the caller.
            try:
                self._write_epistemic(enriched)
            except Exception as ce:
                logger.warning("Intra-tier code-batch checkpoint failed: %s", ce)

            # Cooperative cancel check after each completed batch
            if cancel_token and cancel_token.is_cancelled:
                logger.info("Epistemic code batch cancelled after %d done, %d failed — returning early", done, failed)
                _cancelled = True
                break

        if _cancelled:
            return done, failed

        # Pre-build all doc batch payloads
        doc_batches = []
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
                # Phase 53: narrative files get reduced excerpt to avoid LLM overload
                _max_lines = 500 if nid in _narrative_ids else 3000
                excerpt = self._get_file_excerpt(fp, max_lines=_max_lines)
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
            doc_batches.append(items)

        def _call_doc_batch(items):
            prompt = build_batched_epistemic_doc_prompt(items)
            try:
                prompt_tokens = len(prompt) // 4
                num_predict, num_ctx, warnings = compute_optimal_settings(
                    task=PipelineTask.EPISTEMIC,
                    prompt_tokens=prompt_tokens,
                    model=self.llm.model,
                    think=False,
                )

                if len(items) > 1:
                    num_predict = num_predict * len(items) + 500
                    from codrag.core.context_config import compute_num_ctx
                    num_ctx = compute_num_ctx(prompt_tokens, num_predict, self.llm.model)

                text, tokens = self.llm.generate(
                    prompt, system=BATCHED_EPISTEMIC_DOC_SYSTEM,
                    num_predict=num_predict, num_ctx=num_ctx,
                    response_schema=doc_schema,
                    think=False,
                    max_chars=batched_max_chars("epistemic", len(items)),
                )
                return BatchedResponseParser.parse(text, expected_count=len(items))
            except Exception as e:
                logger.warning("Batched epistemic doc failed for %d items: %s", len(items), e)
                return []

        # Dispatch doc batches (sequentially for concurrency=1 to avoid thread accumulation)
        def _iter_epi_doc_results():
            if _concurrency <= 1 or len(doc_batches) <= 1:
                for batch_items in doc_batches:
                    try:
                        yield batch_items, _call_doc_batch(batch_items)
                    except Exception as e:
                        logger.warning("Doc batch failed: %s", e)
                        yield batch_items, []
            else:
                with ThreadPoolExecutor(max_workers=min(_concurrency, len(doc_batches))) as pool:
                    fmap = {pool.submit(_call_doc_batch, items): items for items in doc_batches}
                    for future in as_completed(fmap):
                        batch_items = fmap[future]
                        try:
                            yield batch_items, future.result()
                        except Exception as e:
                            logger.warning("Doc batch future failed: %s", e)
                            yield batch_items, []

        for items, results_list in _iter_epi_doc_results():

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
            if progress_callback:
                progress_callback("epistemic_enrichment", current_progress + done + failed, total_progress)

            # Intra-tier checkpoint after each doc batch (mirror of code path).
            try:
                self._write_epistemic(enriched)
            except Exception as ce:
                logger.warning("Intra-tier doc-batch checkpoint failed: %s", ce)

            # Cooperative cancel check after each completed batch
            if cancel_token and cancel_token.is_cancelled:
                logger.info("Epistemic doc batch cancelled after %d done, %d failed — returning early", done, failed)
                break

        return done, failed

    def run(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        max_items: Optional[int] = None,
        cancel_token: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Run Pass 2 epistemic enrichment on all eligible file nodes.

        Steps:
        1. Load trace graph, augmentations, existing epistemic entries.
        2. Sort file nodes in reverse-topological order (or into tiers for batching).
        3. Enrich each node with the LLM + neighbor context.
        4. Write trace_epistemic.jsonl overlay atomically.

        If *cancel_token* is provided, the loop checks it periodically and
        flushes partial results before raising PipelinePausedError or
        PipelineCancelledError.
        """
        start = time.monotonic()

        nodes = self.load_trace_nodes()
        edges = self.load_trace_edges()
        augmentations = self.load_augmentations()
        existing = self.load_existing()
        file_hashes = self.load_file_hashes()

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
        to_enrich = [n for n in file_nodes if self._needs_enrichment(n, existing, augmentations, file_hashes)]

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
            progress_callback("epistemic_enrichment", existing_count, total_file_count, existing_count)

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
                # Cooperative cancellation check between tiers
                if cancel_token and cancel_token.is_cancelled:
                    logger.info("Batched epistemic enrichment paused/cancelled at tier %d/%d — flushing partial results", tier_idx, len(tiers))
                    self._write_epistemic(enriched)
                    cancel_token.raise_if_cancelled()

                tier_done, tier_failed = self._enrich_tier_batched(
                    tier, edges, nodes_by_id, augmentations, enriched, code_batch_size, doc_batch_size,
                    progress_callback=progress_callback,
                    current_progress=existing_count + done + failed,
                    total_progress=total_file_count,
                    cancel_token=cancel_token,
                    progress_baseline=existing_count,
                )
                done += tier_done
                failed += tier_failed
                # Write checkpoint after each tier
                self._write_epistemic(enriched)
                logger.info(
                    "Tier %d/%d complete: %d enriched, %d failed (%d items in tier) — checkpoint saved",
                    tier_idx + 1, len(tiers), tier_done, tier_failed, len(tier),
                )
                if progress_callback:
                    progress_callback("epistemic_enrichment", existing_count + done + failed, total_file_count, existing_count)
        else:
            concurrency = _get_llm_concurrency("deep")

            if concurrency <= 1:
                # Sort in reverse-topological order (leaves first)
                to_enrich = topological_sort_files(to_enrich, edges)

                # Sequential by design: each node's neighbor context reads from 'enriched',
                # which accumulates results from earlier nodes in topological order.
                # Parallelizing would break the cascading context benefit.
                for node in to_enrich:
                    # Cooperative cancellation check
                    if cancel_token and cancel_token.is_cancelled:
                        logger.info("Epistemic enrichment paused/cancelled at %d/%d — flushing partial results", done, total_work)
                        self._write_epistemic(enriched)
                        cancel_token.raise_if_cancelled()

                    entry = self.enrich_node(node, edges, nodes_by_id, augmentations, enriched)
                    if entry:
                        enriched[entry.node_id] = entry
                        done += 1
                    else:
                        failed += 1

                    if progress_callback:
                        progress_callback("epistemic_enrichment", existing_count + done + failed, total_file_count, existing_count)

                    # Periodic checkpoint to avoid losing progress on crash
                    if done > 0 and done % 25 == 0:
                        self._write_epistemic(enriched)
                        logger.info("Epistemic checkpoint saved at %d/%d items", done, total_work)
            else:
                # Tier-based concurrent enrichment: nodes within a tier are independent
                # (they only depend on earlier tiers), so they can be processed in parallel.
                # After each tier completes, results merge into 'enriched' before the next tier.
                tiers = topological_sort_into_tiers(to_enrich, edges)
                logger.info(
                    "Concurrent epistemic enrichment: %d files in %d tiers, concurrency=%d",
                    total_work, len(tiers), concurrency,
                )
                for tier_idx, tier in enumerate(tiers):
                    # Cooperative cancellation check between tiers
                    if cancel_token and cancel_token.is_cancelled:
                        logger.info("Epistemic enrichment paused/cancelled at tier %d/%d — flushing partial results", tier_idx, len(tiers))
                        self._write_epistemic(enriched)
                        cancel_token.raise_if_cancelled()

                    lock = threading.Lock()
                    tier_done = 0
                    tier_failed = 0
                    last_checkpoint_count = 0
                    INTRA_TIER_CHECKPOINT_EVERY = 25
                    with ThreadPoolExecutor(max_workers=concurrency) as pool:
                        futures = {
                            pool.submit(
                                self.enrich_node, node, edges, nodes_by_id, augmentations, enriched
                            ): node
                            for node in tier
                        }
                        for future in as_completed(futures):
                            snapshot = None
                            cur_done = cur_failed = 0
                            try:
                                entry = future.result()
                                with lock:
                                    if entry:
                                        enriched[entry.node_id] = entry
                                        tier_done += 1
                                    else:
                                        tier_failed += 1
                                    cur_done, cur_failed = tier_done, tier_failed
                                    completed_in_tier = tier_done + tier_failed
                                    if completed_in_tier - last_checkpoint_count >= INTRA_TIER_CHECKPOINT_EVERY:
                                        snapshot = dict(enriched)
                                        last_checkpoint_count = completed_in_tier
                            except Exception as e:
                                logger.warning("Epistemic enrichment failed: %s", e)
                                with lock:
                                    tier_failed += 1
                                    cur_done, cur_failed = tier_done, tier_failed
                            if snapshot is not None:
                                try:
                                    self._write_epistemic(snapshot)
                                    logger.debug(
                                        "Intra-tier checkpoint: %d/%d in tier %d/%d (%d total enriched)",
                                        cur_done + cur_failed, len(tier), tier_idx + 1, len(tiers), len(snapshot),
                                    )
                                except Exception as ce:
                                    logger.warning("Intra-tier checkpoint failed: %s", ce)
                            if progress_callback:
                                progress_callback(
                                    "epistemic_enrichment",
                                    existing_count + done + cur_done + failed + cur_failed,
                                    total_file_count,
                                    existing_count,
                                )
                    done += tier_done
                    failed += tier_failed
                    # Write checkpoint after each tier
                    self._write_epistemic(enriched)
                    logger.info("Epistemic checkpoint saved after tier %d/%d (%d items so far)", tier_idx + 1, len(tiers), done)
                    if progress_callback:
                        progress_callback("epistemic_enrichment", existing_count + done + failed, total_file_count, existing_count)

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
