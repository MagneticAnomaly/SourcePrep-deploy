"""Stage 6b: Group Deep Reasoning.

Analyzes groups of related files together using deep reasoning (think=True)
to discover cross-file architectural patterns, data flow, coupling risks,
and blast radius that per-file analysis misses.

Pipeline position: runs after Stage 6a (per-file epistemic enrichment)
and before Stage 7 (clustering/module synthesis).

Incremental strategy:
  - Groups are defined by trace graph connectivity (dependency clusters)
  - A group is "stale" if ANY member file's epistemic entry changed since
    the group was last analyzed
  - Single-file changes still trigger full group re-analysis (the value is
    in cross-file reasoning, not per-file)
  - Groups with < 2 members are skipped (no cross-file reasoning needed)

Output: trace_group_reasoning.jsonl — one entry per group with:
  - group_id, member_node_ids, pattern, data_flow, coupling_risks,
    blast_radius, architectural_insight, analyzed_at, model
"""

import json
import logging
import os
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from codrag.core.context_config import PipelineTask, compute_optimal_settings
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .llm_client import LLMClient, _parse_json_response
from .epistemic_score import EpistemicEntry
from .swarm_registry import get_swarm_tier, get_min_groups_threshold
from .swarm_orchestrator import SwarmOrchestrator, WorkItem, WorkerAssignment, SwarmResult

logger = logging.getLogger(__name__)

# ── Data Model ───────────────────────────────────────────────────

@dataclass
class GroupReasoningEntry:
    """Cross-file architectural analysis for a group of related files."""
    group_id: str
    member_node_ids: List[str]
    pattern: str  # e.g. "Request Pipeline", "Repository Pattern", "Event Bus"
    data_flow: str  # How data moves through the group
    coupling_risks: List[str]  # What could break
    blast_radius: List[str]  # Files affected by changes to this group
    architectural_insight: str  # Free-form deep reasoning about the group
    confidence: float = 0.7
    analyzed_at: str = ""
    model: str = ""
    # Fingerprint: hash of member epistemic entries for staleness detection
    member_fingerprint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "group_id": self.group_id,
            "member_node_ids": self.member_node_ids,
            "pattern": self.pattern,
            "data_flow": self.data_flow,
            "coupling_risks": self.coupling_risks,
            "blast_radius": self.blast_radius,
            "architectural_insight": self.architectural_insight,
            "confidence": round(self.confidence, 3),
            "analyzed_at": self.analyzed_at,
            "model": self.model,
            "member_fingerprint": self.member_fingerprint,
        }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GroupReasoningEntry":
        return cls(
            group_id=d["group_id"],
            member_node_ids=d.get("member_node_ids", []),
            pattern=d.get("pattern", ""),
            data_flow=d.get("data_flow", ""),
            coupling_risks=d.get("coupling_risks", []),
            blast_radius=d.get("blast_radius", []),
            architectural_insight=d.get("architectural_insight", ""),
            confidence=float(d.get("confidence", 0.7)),
            analyzed_at=d.get("analyzed_at", ""),
            model=d.get("model", ""),
            member_fingerprint=d.get("member_fingerprint", ""),
        )


# ── Prompts ──────────────────────────────────────────────────────

GROUP_REASONING_SYSTEM = """You are an expert software architect performing deep cross-file analysis.
You are given a group of related source files that are connected by imports, calls, or data flow.
Your job is to identify the architectural PATTERN that connects them, trace how DATA FLOWS
through the group, identify COUPLING RISKS, and assess BLAST RADIUS of changes.

Respond with valid JSON only. No markdown, no explanation outside the JSON."""

GROUP_REASONING_PROMPT = """Analyze this group of {file_count} related files as a connected architectural unit.

## Group Members:
{member_details}

## Dependency Edges Between Members:
{internal_edges}

## Task:
Look at these files TOGETHER as an architectural unit. What pattern connects them?
How does data flow through them? What are the coupling risks?

Respond with JSON:
{{
  "pattern": "Name of the architectural pattern (e.g. Request Pipeline, Repository Pattern, Observer, MVC Layer, Event Bus, Middleware Chain)",
  "data_flow": "Describe how data moves through these files, step by step",
  "coupling_risks": ["List specific coupling risks between these files"],
  "blast_radius": ["List files (by path) that would be affected if any member changes"],
  "architectural_insight": "2-3 sentences of deep insight about this group's design quality, potential improvements, or hidden dependencies",
  "confidence": 0.0-1.0
}}"""


# ── Group Builder ────────────────────────────────────────────────

def build_dependency_groups(
    epistemic: Dict[str, EpistemicEntry],
    edges: List[Dict[str, Any]],
    min_group_size: int = 2,
    max_group_size: int = 15,
) -> List[List[str]]:
    """Build groups of related files from the trace graph.

    Uses connected components of file-level edges, then splits large
    components into sub-groups based on edge density.

    Returns list of groups, where each group is a list of node_ids.
    """
    # Build adjacency for file nodes only
    file_ids = set(epistemic.keys())
    adj: Dict[str, Set[str]] = defaultdict(set)

    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src in file_ids and tgt in file_ids and src != tgt:
            adj[src].add(tgt)
            adj[tgt].add(src)

    # Find connected components via BFS
    visited: Set[str] = set()
    components: List[List[str]] = []

    for node_id in sorted(file_ids):
        if node_id in visited:
            continue
        # BFS
        component: List[str] = []
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        if len(component) >= min_group_size:
            components.append(component)

    # Split large components into sub-groups of max_group_size
    groups: List[List[str]] = []
    for comp in components:
        if len(comp) <= max_group_size:
            groups.append(comp)
        else:
            # Split by taking connected sub-clusters of max_group_size
            # Simple greedy: pick a seed, BFS up to max_group_size
            remaining = set(comp)
            while remaining:
                seed = min(remaining)
                sub: List[str] = []
                sub_queue = [seed]
                while sub_queue and len(sub) < max_group_size:
                    current = sub_queue.pop(0)
                    if current not in remaining:
                        continue
                    remaining.discard(current)
                    sub.append(current)
                    for neighbor in adj.get(current, set()):
                        if neighbor in remaining:
                            sub_queue.append(neighbor)
                if len(sub) >= min_group_size:
                    groups.append(sub)

    return groups


def compute_group_fingerprint(
    member_ids: List[str],
    epistemic: Dict[str, EpistemicEntry],
) -> str:
    """Compute a fingerprint for a group based on member epistemic entries.

    Changes when any member's enriched_at timestamp changes.
    """
    import hashlib
    parts = []
    for nid in sorted(member_ids):
        entry = epistemic.get(nid)
        if entry:
            parts.append(f"{nid}:{entry.enriched_at}")
        else:
            parts.append(f"{nid}:none")
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]


# ── Main Engine ──────────────────────────────────────────────────

class GroupReasoningEngine:
    """Stage 6b: Group Deep Reasoning.

    Analyzes groups of related files together using deep reasoning
    to discover cross-file architectural patterns.
    """

    def __init__(
        self,
        llm: LLMClient,
        index_dir: Path,
    ):
        self.llm = llm
        self.index_dir = index_dir
        self.output_path = index_dir / "trace_group_reasoning.jsonl"

    def load_existing(self) -> Dict[str, GroupReasoningEntry]:
        """Load existing group reasoning entries."""
        entries: Dict[str, GroupReasoningEntry] = {}
        if self.output_path.exists():
            with open(self.output_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            d = json.loads(line)
                            entry = GroupReasoningEntry.from_dict(d)
                            entries[entry.group_id] = entry
                        except (json.JSONDecodeError, KeyError):
                            continue
        return entries

    def load_epistemic(self) -> Dict[str, EpistemicEntry]:
        """Load epistemic entries."""
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
        """Load trace edges."""
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

    def _build_member_details(
        self,
        member_ids: List[str],
        epistemic: Dict[str, EpistemicEntry],
    ) -> str:
        """Build a context string with each member's epistemic summary."""
        parts: List[str] = []
        for nid in member_ids:
            entry = epistemic.get(nid)
            if entry:
                fp = nid.replace("file:", "", 1) if nid.startswith("file:") else nid
                tags = ", ".join(entry.domain_tags) if entry.domain_tags else "none"
                debt = "; ".join(entry.tech_debt[:2]) if entry.tech_debt else "none identified"
                parts.append(
                    f"- **{fp}** ({entry.architecture_layer})\n"
                    f"  Summary: {entry.extended_summary[:200]}\n"
                    f"  Domain: [{tags}] | Tech debt: {debt}"
                )
        return "\n".join(parts) if parts else "(no epistemic data)"

    def _build_internal_edges(
        self,
        member_ids: List[str],
        edges: List[Dict[str, Any]],
    ) -> str:
        """Build a string showing edges between group members."""
        member_set = set(member_ids)
        internal: List[str] = []
        for e in edges:
            src = e.get("source", "")
            tgt = e.get("target", "")
            if src in member_set and tgt in member_set:
                kind = e.get("kind", e.get("type", "unknown"))
                src_short = src.replace("file:", "", 1) if src.startswith("file:") else src
                tgt_short = tgt.replace("file:", "", 1) if tgt.startswith("file:") else tgt
                internal.append(f"  {src_short} --[{kind}]--> {tgt_short}")
        return "\n".join(internal[:20]) if internal else "(no direct edges between members)"

    # ── Swarm helpers ───────────────────────────────────────────────

    def _get_swarm_enabled(self) -> bool:
        """Check if swarm is enabled in pipeline settings."""
        try:
            from codrag.services.settings_store import settings
            return bool(settings.get("swarm_enabled", True))
        except Exception:
            return True  # Default to enabled

    def analyze_group_with_angle(
        self,
        group_id: str,
        member_ids: List[str],
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
        analysis_angle: str,
        priority_concerns: List[str],
    ) -> Optional[GroupReasoningEntry]:
        """Variant of analyze_group that accepts coordinator-assigned scoping."""
        member_details = self._build_member_details(member_ids, epistemic)
        internal_edges = self._build_internal_edges(member_ids, edges)

        prompt = GROUP_REASONING_PROMPT.format(
            file_count=len(member_ids),
            member_details=member_details,
            internal_edges=internal_edges,
        )

        # Append coordinator guidance
        concerns_text = "\n".join(f"- {c}" for c in priority_concerns) if priority_concerns else "None specified"
        prompt += (
            f"\n\n## Coordinator Guidance\n"
            f"Analysis angle: {analysis_angle}\n"
            f"Priority concerns:\n{concerns_text}"
        )

        import time as _time
        _start = _time.monotonic()
        logger.info(
            "[GroupReasoning] Analyzing group %s with angle (%d files, prompt=%d chars)",
            group_id, len(member_ids), len(prompt),
        )

        try:
            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, warnings = compute_optimal_settings(
                task=PipelineTask.GROUP_REASONING,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=True,
            )

            from codrag.core.llm_client import TASK_MAX_CHARS
            text, tokens = self.llm.generate(
                prompt,
                system=GROUP_REASONING_SYSTEM,
                num_predict=num_predict,
                num_ctx=num_ctx,
                json_mode=True,
                temperature=0.6,
                think=True,
                max_chars=TASK_MAX_CHARS["group_reasoning"],
            )
            elapsed = _time.monotonic() - _start
            logger.info(
                "[GroupReasoning] Group %s (angled) responded in %.1fs (%d tokens)",
                group_id, elapsed, tokens,
            )
        except Exception as e:
            elapsed = _time.monotonic() - _start
            logger.warning(
                "[GroupReasoning] LLM call failed for group %s (angled) after %.1fs: %s",
                group_id, elapsed, e,
            )
            return None

        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning(
                "[GroupReasoning] Failed to parse angled response for group %s — raw: %.200s",
                group_id, text,
            )
            return None

        fingerprint = compute_group_fingerprint(member_ids, epistemic)

        return GroupReasoningEntry(
            group_id=group_id,
            member_node_ids=member_ids,
            pattern=str(parsed.get("pattern", "unknown"))[:200],
            data_flow=str(parsed.get("data_flow", ""))[:500],
            coupling_risks=[str(r) for r in parsed.get("coupling_risks", [])][:10],
            blast_radius=[str(r) for r in parsed.get("blast_radius", [])][:20],
            architectural_insight=str(parsed.get("architectural_insight", ""))[:500],
            confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.7)))),
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
            member_fingerprint=fingerprint,
        )

    def _run_swarm(
        self,
        to_analyze: List[Tuple[str, List[str]]],
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
        progress_callback: Optional[Callable[..., None]] = None,
        cancel_token: Optional[Any] = None,
    ) -> Dict[str, GroupReasoningEntry]:
        """Run swarm-orchestrated group reasoning.

        Returns a dict of group_id -> GroupReasoningEntry.
        Empty dict signals the caller to fall back to standard path.
        """
        # Phase 79: Swarm stages bypass the scheduler's fair-share division
        # to get the full concurrency budget. The stage still waits its turn
        # in the queue — only the worker parallelism is maximized.
        concurrency = 1
        try:
            from codrag.services.pipeline.scheduler import pipeline_scheduler
            full = pipeline_scheduler.full_budget_for_swarm(
                self.llm.provider, self.llm.model,
            )
            if full is not None:
                concurrency = full
        except (ImportError, Exception) as exc:
            logger.debug("Swarm full budget unavailable, trying batch concurrency: %s", exc)
        if concurrency <= 1:
            # Fallback: use the standard fair-share path
            try:
                from codrag.core.batch_profiles import get_batch_concurrency
                concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)
            except Exception:
                concurrency = 1
        # F-59: Cap concurrency for cloud-proxied models.
        is_cloud = ":cloud" in self.llm.model.lower() or self.llm.provider in ("openai", "anthropic", "google")
        if is_cloud and concurrency > 3:
            logger.info("[GroupReasoning] Capping concurrency %d → 3 for cloud model %s", concurrency, self.llm.model)
            concurrency = 3
        logger.info("[Swarm] Using concurrency=%d for fan-out", concurrency)

        orch = SwarmOrchestrator(
            llm=self.llm,
            concurrency=concurrency,
            coordinator_timeout_s=10.0 if is_cloud else 90.0,
            synthesis_timeout_s=120.0,
        )

        # Build WorkItem list
        items: List[WorkItem] = []
        gid_to_members: Dict[str, List[str]] = {}
        for gid, members in to_analyze:
            gid_to_members[gid] = members
            # Summary: file paths (capped at 5) with architecture layers
            paths = []
            for nid in members[:5]:
                fp = nid.replace("file:", "", 1) if nid.startswith("file:") else nid
                entry = epistemic.get(nid)
                layer = entry.architecture_layer if entry else "unknown"
                paths.append(f"{fp} ({layer})")
            if len(members) > 5:
                paths.append(f"... and {len(members) - 5} more")
            summary = "; ".join(paths)

            # Full context: JSON with member_details and internal_edges
            member_details = self._build_member_details(members, epistemic)
            internal_edges = self._build_internal_edges(members, edges)
            full_context = json.dumps({
                "member_details": member_details,
                "internal_edges": internal_edges,
                "file_count": len(members),
            })

            items.append(WorkItem(id=gid, summary=summary, full_context=full_context))

        coordinator_prompt = (
            "You are coordinating parallel analysis of {n} code groups.\n"
            "Each group is a connected component of related files.\n\n"
            "Groups:\n{{group_summaries}}\n\n"
            "For EACH group, assign a specific analysis_angle (what aspect to focus on)\n"
            "and priority_concerns (what risks to look for).\n\n"
            "Respond with JSON:\n"
            '{{"assignments": [{{"item_id": "group:...", "analysis_angle": "...", '
            '"priority_concerns": ["..."]}}]}}'
        ).format(n=len(items))

        synthesis_prompt = (
            "Below are the analysis results from {n} parallel group analyses.\n\n"
            "{{worker_outputs}}\n\n"
            "Synthesize cross-group patterns:\n"
            '{{"cross_group_patterns": ["..."], '
            '"shared_risks": ["..."], '
            '"architectural_recommendations": ["..."], '
            '"overall_health": "good|moderate|concerning"}}'
        ).format(n=len(items))

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> Optional[str]:
            member_ids = gid_to_members.get(item.id, [])
            entry = self.analyze_group_with_angle(
                item.id, member_ids, epistemic, edges,
                assignment.analysis_angle, assignment.priority_concerns,
            )
            if entry is None:
                return None
            return json.dumps(entry.to_dict())

        def progress_fn(done: int, total: int) -> None:
            if progress_callback:
                progress_callback("group_reasoning", done, len(to_analyze), 0)

        result = orch.execute(
            items=items,
            coordinator_prompt=coordinator_prompt,
            worker_fn=worker_fn,
            synthesis_prompt=synthesis_prompt,
            progress_fn=progress_fn,
        )

        if result is None:
            return {}

        # Convert WorkerResults to GroupReasoningEntry objects
        entries: Dict[str, GroupReasoningEntry] = {}
        for wr in result.worker_results:
            if wr.success and wr.parsed:
                try:
                    entry = GroupReasoningEntry.from_dict(wr.parsed)
                    entries[entry.group_id] = entry
                except (KeyError, ValueError) as exc:
                    logger.warning("Failed to parse worker result for %s: %s", wr.item_id, exc)

        # Write synthesis artifact (only if synthesis succeeded)
        if result.synthesis:
            self._write_synthesis(result)

        return entries

    def _write_synthesis(self, result: SwarmResult) -> None:
        """Write swarm synthesis artifact to disk."""
        artifact = {
            "stage": "group_reasoning_swarm",
            "model": self.llm.model,
            "groups_analyzed": result.stats.total_items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "synthesis": result.synthesis,
            "stats": {
                "coordinator_tokens": result.stats.coordinator_tokens,
                "worker_tokens": result.stats.worker_tokens,
                "synthesis_tokens": result.stats.synthesis_tokens,
                "workers_succeeded": result.stats.workers_succeeded,
                "workers_failed": result.stats.workers_failed,
                "wall_clock_seconds": round(result.stats.wall_clock_seconds, 2),
            },
        }
        path = self.index_dir / "trace_swarm_synthesis.json"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2)
        logger.info("[Swarm] Synthesis written to %s", path)

    def analyze_group(
        self,
        group_id: str,
        member_ids: List[str],
        epistemic: Dict[str, EpistemicEntry],
        edges: List[Dict[str, Any]],
    ) -> Optional[GroupReasoningEntry]:
        """Analyze a single group using deep reasoning (think=True)."""
        member_details = self._build_member_details(member_ids, epistemic)
        internal_edges = self._build_internal_edges(member_ids, edges)

        prompt = GROUP_REASONING_PROMPT.format(
            file_count=len(member_ids),
            member_details=member_details,
            internal_edges=internal_edges,
        )

        import time as _time
        _start = _time.monotonic()
        logger.info(
            "[GroupReasoning] Analyzing group %s (%d files, prompt=%d chars)",
            group_id, len(member_ids), len(prompt),
        )

        try:
            # think=True: This is where deep reasoning adds genuine value.
            # The model reasons about relationships BETWEEN files, not just
            # individual file descriptions.
            prompt_tokens = len(prompt) // 4
            num_predict, num_ctx, warnings = compute_optimal_settings(
                task=PipelineTask.GROUP_REASONING,
                prompt_tokens=prompt_tokens,
                model=self.llm.model,
                think=True,
            )

            from codrag.core.llm_client import TASK_MAX_CHARS
            text, tokens = self.llm.generate(
                prompt,
                system=GROUP_REASONING_SYSTEM,
                num_predict=num_predict,
                num_ctx=num_ctx,
                json_mode=True,
                temperature=0.6,
                think=True,
                max_chars=TASK_MAX_CHARS["group_reasoning"],
            )
            elapsed = _time.monotonic() - _start
            logger.info(
                "[GroupReasoning] Group %s responded in %.1fs (%d tokens)",
                group_id, elapsed, tokens,
            )
        except Exception as e:
            elapsed = _time.monotonic() - _start
            logger.warning(
                "[GroupReasoning] LLM call failed for group %s after %.1fs: %s",
                group_id, elapsed, e,
            )
            return None

        parsed = _parse_json_response(text)
        if parsed is None:
            logger.warning(
                "[GroupReasoning] Failed to parse response for group %s — raw: %.200s",
                group_id, text,
            )
            return None

        fingerprint = compute_group_fingerprint(member_ids, epistemic)

        return GroupReasoningEntry(
            group_id=group_id,
            member_node_ids=member_ids,
            pattern=str(parsed.get("pattern", "unknown"))[:200],
            data_flow=str(parsed.get("data_flow", ""))[:500],
            coupling_risks=[str(r) for r in parsed.get("coupling_risks", [])][:10],
            blast_radius=[str(r) for r in parsed.get("blast_radius", [])][:20],
            architectural_insight=str(parsed.get("architectural_insight", ""))[:500],
            confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.7)))),
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            model=self.llm.model,
            member_fingerprint=fingerprint,
        )

    def run(
        self,
        progress_callback: Optional[Callable[..., None]] = None,
        cancel_token: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Run group deep reasoning on all dependency groups.

        Steps:
        1. Load epistemic entries and edges.
        2. Build dependency groups from the trace graph.
        3. Check staleness: skip groups whose member fingerprint hasn't changed.
        4. Analyze stale/new groups with deep reasoning (think=True).
        5. Write trace_group_reasoning.jsonl atomically.

        If *cancel_token* is provided, the loop checks it periodically and
        flushes partial results before raising.
        """
        start = time.monotonic()

        epistemic = self.load_epistemic()
        edges = self.load_edges()
        existing = self.load_existing()

        if not epistemic:
            logger.info("No epistemic entries found, skipping group reasoning")
            return {"total_groups": 0, "analyzed": 0, "skipped": 0, "failed": 0}

        # Build groups from dependency graph
        groups = build_dependency_groups(epistemic, edges)
        logger.info(
            "Group reasoning: %d dependency groups from %d epistemic entries",
            len(groups), len(epistemic),
        )

        if not groups:
            logger.info("No dependency groups with 2+ members, skipping group reasoning")
            return {"total_groups": 0, "analyzed": 0, "skipped": 0, "failed": 0}

        # Assign stable group IDs based on sorted member set
        group_map: Dict[str, List[str]] = {}
        for i, members in enumerate(groups):
            # Stable ID: hash of sorted member IDs
            import hashlib
            gid = "group:" + hashlib.md5(
                "|".join(sorted(members)).encode()
            ).hexdigest()[:10]
            group_map[gid] = members

        # Check staleness
        to_analyze: List[Tuple[str, List[str]]] = []
        reuse: Dict[str, GroupReasoningEntry] = {}

        for gid, members in group_map.items():
            fingerprint = compute_group_fingerprint(members, epistemic)
            ex = existing.get(gid)
            if ex and ex.member_fingerprint == fingerprint:
                # Group hasn't changed, reuse
                reuse[gid] = ex
            else:
                to_analyze.append((gid, members))

        total_groups = len(group_map)
        logger.info(
            "Group reasoning: %d groups total, %d to analyze, %d reused (unchanged)",
            total_groups, len(to_analyze), len(reuse),
        )

        if progress_callback:
            progress_callback("group_reasoning", len(reuse), total_groups, len(reuse))

        analyzed = 0
        failed = 0
        results: Dict[str, GroupReasoningEntry] = dict(reuse)

        # ── Swarm decision ──────────────────────────────────────────
        swarm_tier = get_swarm_tier(self.llm.provider, self.llm.model)
        swarm_enabled = self._get_swarm_enabled()
        min_threshold = get_min_groups_threshold()
        use_swarm = (
            swarm_tier.can_coordinate
            and swarm_enabled
            and len(to_analyze) >= min_threshold
        )

        if use_swarm:
            logger.info(
                "Group reasoning: using SWARM orchestration (%s, %d groups, tier=%s)",
                self.llm.model, len(to_analyze), swarm_tier.value,
            )
            swarm_entries = self._run_swarm(
                to_analyze, epistemic, edges, progress_callback, cancel_token,
            )
            if swarm_entries:
                results.update(swarm_entries)
                analyzed = len(swarm_entries)
                self._write_results(results)
                elapsed = time.monotonic() - start
                if progress_callback:
                    progress_callback("group_reasoning_complete", total_groups, total_groups, len(reuse))
                return {
                    "total_groups": total_groups,
                    "analyzed": analyzed,
                    "reused": len(reuse),
                    "failed": len(to_analyze) - analyzed,
                    "duration_ms": round(elapsed * 1000, 1),
                    "swarm": True,
                }
            else:
                logger.info("Swarm coordinator failed — falling back to standard path")
                # Fall through to existing concurrent/sequential logic below

        # Phase 72: Use the scheduler's batch concurrency budget to
        # process multiple groups in parallel.  Cloud endpoints can
        # handle concurrent requests; local models fall back to 1.
        try:
            from codrag.core.batch_profiles import get_batch_concurrency
            concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)
        except Exception as exc:
            logger.warning("get_batch_concurrency failed, falling back to sequential: %s", exc)
            concurrency = 1

        logger.info(
            "Group reasoning: processing %d groups with concurrency=%d",
            len(to_analyze), concurrency,
        )

        if concurrency > 1 and len(to_analyze) > 1:
            # ── Concurrent path ─────────────────────────────────────
            import threading
            from concurrent.futures import ThreadPoolExecutor, as_completed

            lock = threading.Lock()
            done_count = 0

            def _analyze_one(gid_members):
                gid, members = gid_members
                return gid, self.analyze_group(gid, members, epistemic, edges)

            with ThreadPoolExecutor(max_workers=min(concurrency, len(to_analyze))) as pool:
                futures = {
                    pool.submit(_analyze_one, (gid, members)): gid
                    for gid, members in to_analyze
                }
                for future in as_completed(futures):
                    gid = futures[future]
                    try:
                        _, entry = future.result()
                    except Exception as exc:
                        logger.warning(
                            "[GroupReasoning] Group %s raised exception: %s", gid, exc,
                        )
                        entry = None

                    with lock:
                        if entry:
                            results[gid] = entry
                            analyzed += 1
                        else:
                            failed += 1
                        done_count += 1

                        if progress_callback:
                            progress_callback(
                                "group_reasoning",
                                len(reuse) + done_count,
                                total_groups,
                                len(reuse),
                            )

                        # Periodic checkpoint
                        if analyzed > 0 and analyzed % 10 == 0:
                            self._write_results(results)
                            logger.info(
                                "Group reasoning checkpoint saved at %d/%d groups",
                                analyzed, len(to_analyze),
                            )

                    # Cooperative cancellation
                    if cancel_token and cancel_token.is_cancelled:
                        logger.info(
                            "Group reasoning cancelled at %d/%d — flushing partial results",
                            done_count, len(to_analyze),
                        )
                        pool.shutdown(wait=False, cancel_futures=True)
                        self._write_results(results)
                        cancel_token.raise_if_cancelled()
        else:
            # ── Sequential path (local model or single group) ───────
            for gid, members in to_analyze:
                # Cooperative cancellation check
                if cancel_token and cancel_token.is_cancelled:
                    logger.info("Group reasoning paused/cancelled at %d/%d — flushing partial results", analyzed, len(to_analyze))
                    self._write_results(results)
                    cancel_token.raise_if_cancelled()

                entry = self.analyze_group(gid, members, epistemic, edges)
                if entry:
                    results[gid] = entry
                    analyzed += 1
                else:
                    failed += 1

                if progress_callback:
                    progress_callback(
                        "group_reasoning",
                        len(reuse) + analyzed + failed,
                        total_groups,
                        len(reuse),
                    )

                # Periodic checkpoint to avoid losing progress on crash
                if analyzed > 0 and analyzed % 10 == 0:
                    self._write_results(results)
                    logger.info("Group reasoning checkpoint saved at %d/%d groups", analyzed, len(to_analyze))

        # Write atomically
        self._write_results(results)

        duration_ms = (time.monotonic() - start) * 1000

        if progress_callback:
            progress_callback("group_reasoning_complete", total_groups, total_groups, len(reuse))

        stats = {
            "total_groups": total_groups,
            "analyzed": analyzed,
            "reused": len(reuse),
            "failed": failed,
            "concurrency": concurrency,
            "duration_ms": round(duration_ms, 1),
        }

        logger.info(
            "Group reasoning complete: %d analyzed, %d reused, %d failed, concurrency=%d in %.1fs",
            analyzed, len(reuse), failed, concurrency, duration_ms / 1000,
        )

        return stats

    def _write_results(self, entries: Dict[str, GroupReasoningEntry]) -> None:
        """Write group reasoning entries atomically."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        sorted_entries = sorted(entries.values(), key=lambda e: e.group_id)

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", dir=self.index_dir, delete=False, encoding="utf-8",
        )
        try:
            for entry in sorted_entries:
                tmp.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.rename(tmp.name, self.output_path)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise
