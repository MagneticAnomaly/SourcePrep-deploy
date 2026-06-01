"""Stage 6b: Group Deep Reasoning.

Analyzes groups of related files together using deep reasoning (think=True)
to discover cross-file architectural patterns, data flow, coupling risks,
and blast radius that per-file analysis misses.

Pipeline position: runs after Stage 6a (per-file epistemic enrichment)
and before Stage 7 (clustering/module synthesis).

Incremental strategy:
  - Groups are defined by trace graph connectivity (dependency clusters)
  - A group is "stale" if ANY member file is in the pipeline's
    Changeset.modified | deleted (emitted by stage 1)
  - Single-file changes still trigger full group re-analysis (the value is
    in cross-file reasoning, not per-file)
  - Groups with < 2 members are skipped (no cross-file reasoning needed)

Output: trace_group_reasoning.jsonl — one entry per group with:
  - group_id, member_node_ids, pattern, data_flow, coupling_risks,
    blast_radius, architectural_insight, analyzed_at, model
"""

import hashlib
import json
import logging
import os
import tempfile
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any  # also re-imported below; placed early for module-level helpers


# Phase 136 Part 12 — Group identity is BOTH hash-stable AND fuzzy-matchable.
#
# The group_id stays a hash of the FULL sorted member set (preserves
# format compatibility with the on-disk trace_group_reasoning.jsonl
# and the existing fast-path lookup).  When the exact-match lookup
# misses, callers fall back to `_find_overlapping_entry`, which
# returns a prior entry whose member set has ≥ JACCARD_THRESHOLD
# overlap with the new group.  This catches the common case of
# "existing group gained a peripheral new file" without forcing a
# full re-analysis.
#
# Dogfood evidence (2026-05-18, SourcePrep): a 54-added-file
# incremental run produced 98 of 109 groups marked "new" because
# every cached gid mismatched the recomputed one.  With the Jaccard
# fallback, those 98 groups are now correctly carried forward.

_JACCARD_THRESHOLD = 0.7  # ≥70% overlap → same group


def _stable_group_id(members: list[str]) -> str:
    """Group id = hash of sorted full member set.

    This is the legacy formula (unchanged for format compatibility).
    Stability across small membership shifts is provided by
    ``_find_overlapping_entry`` as a fallback, not by the id itself."""
    return "group:" + hashlib.md5(
        "|".join(sorted(members)).encode()
    ).hexdigest()[:10]


def _find_overlapping_entry(
    new_members: list[str],
    existing: dict[str, Any],
) -> tuple[str | None, Any]:
    """Locate a prior entry whose member set has high Jaccard overlap
    with ``new_members``.  Returns ``(old_gid, entry)`` or ``(None, None)``.

    Used as a fallback when the exact-gid lookup misses on an incremental
    rebuild — adding even one new member to a group changes the
    full-member hash, but the cached analysis is still substantively
    valid if ≥ ``_JACCARD_THRESHOLD`` of members are shared.  Both
    directions must clear the threshold (the new group must be mostly
    the old group AND vice versa) to avoid matching unrelated supersets.

    O(N) per lookup; the enclosing loop is O(N²) which is fine at
    typical scales (~100 groups for SourcePrep, ~1000 for very large
    projects)."""
    new_set = frozenset(new_members)
    if not new_set:
        return None, None
    best_score = _JACCARD_THRESHOLD
    best_gid: str | None = None
    best_entry: Any = None
    for gid, entry in existing.items():
        old_members = getattr(entry, "member_node_ids", None) or []
        old_set = frozenset(old_members)
        if not old_set:
            continue
        intersection = len(new_set & old_set)
        if intersection == 0:
            continue
        # Symmetric Jaccard: both sides must clear the threshold so a
        # tiny new group can't "match" a giant old group via 1-member
        # overlap, and vice versa.
        new_overlap = intersection / len(new_set)
        old_overlap = intersection / len(old_set)
        score = min(new_overlap, old_overlap)
        if score > best_score:
            best_score = score
            best_gid = gid
            best_entry = entry
    return best_gid, best_entry
from typing import Any

from prep.core.context_config import PipelineTask, compute_optimal_settings
from prep.services.pipeline.holds import (
    HoldPausedError,
    hold_paused_for_llm,
    raise_hold_paused_for_llm,
)
from prep.services.pipeline.recovery import is_reuse_blocked
from prep.services.pipeline.workers import WorkerFactory
from prep.services.pipeline.workers.base import Worker

from .epistemic_score import EpistemicEntry
from .llm_client import LLMClient, _parse_json_response
from .swarm_orchestrator import (
    SwarmOrchestrator,
    SwarmResult,
    WorkerAssignment,
    WorkItem,
    compute_swarm_wall_budget,
)
from .swarm_registry import get_min_groups_threshold, get_swarm_tier

logger = logging.getLogger(__name__)

# ── Data Model ───────────────────────────────────────────────────

@dataclass
class GroupReasoningEntry:
    """Cross-file architectural analysis for a group of related files."""
    group_id: str
    member_node_ids: list[str]
    pattern: str  # e.g. "Request Pipeline", "Repository Pattern", "Event Bus"
    data_flow: str  # How data moves through the group
    coupling_risks: list[str]  # What could break
    blast_radius: list[str]  # Files affected by changes to this group
    architectural_insight: str  # Free-form deep reasoning about the group
    confidence: float = 0.7
    analyzed_at: str = ""
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
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
        }
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GroupReasoningEntry":
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
    epistemic: dict[str, EpistemicEntry],
    edges: list[dict[str, Any]],
    min_group_size: int = 2,
    max_group_size: int = 15,
) -> list[list[str]]:
    """Build groups of related files from the trace graph.

    Uses connected components of file-level edges, then splits large
    components into sub-groups based on edge density.

    Returns list of groups, where each group is a list of node_ids.
    """
    # Build adjacency for file nodes only
    file_ids = set(epistemic.keys())
    adj: dict[str, set[str]] = defaultdict(set)

    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src in file_ids and tgt in file_ids and src != tgt:
            adj[src].add(tgt)
            adj[tgt].add(src)

    # Find connected components via BFS
    visited: set[str] = set()
    components: list[list[str]] = []

    for node_id in sorted(file_ids):
        if node_id in visited:
            continue
        # BFS
        component: list[str] = []
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
    groups: list[list[str]] = []
    for comp in components:
        if len(comp) <= max_group_size:
            groups.append(comp)
        else:
            # Split by taking connected sub-clusters of max_group_size
            # Simple greedy: pick a seed, BFS up to max_group_size
            remaining = set(comp)
            while remaining:
                seed = min(remaining)
                sub: list[str] = []
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


# ── Main Engine ──────────────────────────────────────────────────

class GroupReasoningEngine(Worker):
    """Stage 6b: Group Deep Reasoning.

    Analyzes groups of related files together using deep reasoning
    to discover cross-file architectural patterns.
    """

    def __init__(
        self,
        llm: LLMClient,
        index_dir: Path,
        project_id: str = "",
    ):
        self.llm = llm
        self.index_dir = index_dir
        self.project_id = project_id
        self.output_path = index_dir / "trace_group_reasoning.jsonl"
        # Phase 127: stash slots for swarm pause signaling.  Initialized
        # here (instead of relying on getattr fallbacks at the read site)
        # so a "never set" foot-gun can't silently mask a regression.
        # Updated by _run_swarm() after each swarm execution.
        self._last_swarm_paused: bool = False
        self._last_swarm_pause_info: dict[str, str] = {}
        # 2026-05-27 (Phase 141): incomplete-swarm signaling.  Set when
        # the swarm fan-out cancels pending futures (wall-cap, stall)
        # and ``len(result.worker_results) < len(items)``.  The caller
        # (``run``) checks this and refuses to overwrite the cache
        # with truncated results — the file remains at its pre-stage
        # state and the stage fails so the user retries.  Without this
        # guard, the 2026-05-26 incident shrunk trace_group_reasoning.jsonl
        # from 166 to 61 records when 99/160 workers were silently
        # cancelled by the 900s wall cap.
        self._last_swarm_incomplete: bool = False
        self._last_swarm_incomplete_info: dict[str, Any] = {}

    def _group_is_stale(self, member_node_ids: list[str]) -> bool:
        """A group is stale iff any member's underlying file is in
        changeset.modified | deleted. Phase 135.5b: lazy-loads the
        changeset from disk when not explicitly injected so API
        endpoints and non-pipeline callers get correct answers instead
        of the defensive 'all stale' fallback."""
        cs = self._resolve_changeset()
        if cs is None:
            return True
        for nid in member_node_ids:
            file_path = nid[len("file:"):] if nid.startswith("file:") else nid
            if file_path in cs.modified or file_path in cs.deleted:
                return True
        return False

    def load_existing(self) -> dict[str, GroupReasoningEntry]:
        """Load existing group reasoning entries.

        Returns an empty dict if a reset barrier is active for this project
        and its scope blocks deep_enrichment reuse — reset semantics require
        group_reasoning to treat all prior entries as nonexistent.
        """
        entries: dict[str, GroupReasoningEntry] = {}
        if self.project_id and is_reuse_blocked(self.project_id, stage_group="deep_enrichment"):
            logger.info(
                "Group reasoning reuse blocked by reset barrier for project %s — "
                "treating prior trace_group_reasoning.jsonl as empty",
                self.project_id,
            )
            return entries
        if self.output_path.exists():
            with open(self.output_path, encoding="utf-8") as f:
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

    def load_epistemic(self) -> dict[str, EpistemicEntry]:
        """Load epistemic entries."""
        entries: dict[str, EpistemicEntry] = {}
        path = self.index_dir / "trace_epistemic.jsonl"
        if path.exists():
            with open(path, encoding="utf-8") as f:
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

    def load_edges(self) -> list[dict[str, Any]]:
        """Load trace edges."""
        edges: list[dict[str, Any]] = []
        for fname in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
            path = self.index_dir / fname
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            edges.append(json.loads(line))
        return edges

    def _build_member_details(
        self,
        member_ids: list[str],
        epistemic: dict[str, EpistemicEntry],
    ) -> str:
        """Build a context string with each member's epistemic summary."""
        parts: list[str] = []
        for nid in member_ids:
            entry = epistemic.get(nid)
            if entry:
                fp = nid.replace("file:", "", 1) if nid.startswith("file:") else nid
                tags = ", ".join(entry.domain_tags) if entry.domain_tags else "none"
                # tech_debt items may be strings (legacy) or dicts with item/severity/context
                # (Phase 140 structured shape) — render to readable string per element.
                def _td_str(item):
                    if isinstance(item, dict):
                        sev = item.get("severity", "")
                        name = item.get("item", "")
                        return f"[{sev}] {name}" if sev else name
                    return str(item)
                debt = "; ".join(_td_str(t) for t in entry.tech_debt[:2]) if entry.tech_debt else "none identified"
                parts.append(
                    f"- **{fp}** ({entry.architecture_layer})\n"
                    f"  Summary: {entry.extended_summary[:200]}\n"
                    f"  Domain: [{tags}] | Tech debt: {debt}"
                )
        return "\n".join(parts) if parts else "(no epistemic data)"

    def _build_internal_edges(
        self,
        member_ids: list[str],
        edges: list[dict[str, Any]],
    ) -> str:
        """Build a string showing edges between group members."""
        member_set = set(member_ids)
        internal: list[str] = []
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
            from prep.services.settings_store import settings
            return bool(settings.get("swarm_enabled", True))
        except Exception:
            return True  # Default to enabled

    def analyze_group_with_angle(
        self,
        group_id: str,
        member_ids: list[str],
        epistemic: dict[str, EpistemicEntry],
        edges: list[dict[str, Any]],
        analysis_angle: str,
        priority_concerns: list[str],
    ) -> GroupReasoningEntry | None:
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

            from prep.core.llm_client import TASK_MAX_CHARS
            if hold_paused_for_llm(self.llm, self.project_id, logger):
                raise_hold_paused_for_llm(self.llm, self.project_id)
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
        except HoldPausedError:
            raise
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

        return GroupReasoningEntry(
            group_id=group_id,
            member_node_ids=member_ids,
            pattern=str(parsed.get("pattern", "unknown"))[:200],
            data_flow=str(parsed.get("data_flow", ""))[:500],
            coupling_risks=[str(r) for r in parsed.get("coupling_risks", [])][:10],
            blast_radius=[str(r) for r in parsed.get("blast_radius", [])][:20],
            architectural_insight=str(parsed.get("architectural_insight", ""))[:500],
            confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.7)))),
            analyzed_at=datetime.now(UTC).isoformat(),
            model=self.llm.model,
        )

    def _run_swarm(
        self,
        to_analyze: list[tuple[str, list[str]]],
        epistemic: dict[str, EpistemicEntry],
        edges: list[dict[str, Any]],
        progress_callback: Callable[..., None] | None = None,
        cancel_token: Any | None = None,
    ) -> dict[str, GroupReasoningEntry]:
        """Run swarm-orchestrated group reasoning.

        Returns a dict of group_id -> GroupReasoningEntry.
        Empty dict signals the caller to fall back to standard path.
        """
        # Phase 79: Swarm stages bypass the scheduler's fair-share division
        # to get the full concurrency budget. The stage still waits its turn
        # in the queue — only the worker parallelism is maximized.
        concurrency = 1
        try:
            from prep.services.pipeline.scheduler import pipeline_scheduler
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
                from prep.core.batch_profiles import get_batch_concurrency
                concurrency = get_batch_concurrency(self.llm.provider, model=self.llm.model)
            except Exception:
                concurrency = 1
        # Phase 112: plan-tier enforcement happens upstream in
        # scheduler.full_budget_for_swarm() / batch_profiles.get_batch_concurrency().
        # F-59 (daemon hang) resolved 2026-04-12 — no defensive cap needed here.
        from prep.core.llm_client import _is_cloud_endpoint
        is_cloud = _is_cloud_endpoint(self.llm)
        logger.info("[Swarm] Using concurrency=%d for fan-out (cloud=%s)", concurrency, is_cloud)

        # F-59 rework: cloud models process requests sequentially and
        # use the large-slot 600s HTTP timeout.  Set per-worker and
        # overall wall-time caps so the swarm doesn't appear to hang.
        # Phase 112: coord and worker decoupled — coord uses coordinator_llm slot.
        # 2026-05-27 (Phase 141): scale wall budget with workload.
        # Previous fixed 900s (cloud) tripped on the legitimate 160-group
        # full-rebuild path that needed ~1170-1750s.  See
        # ``compute_swarm_wall_budget`` for the sizing rationale.
        wall_budget = compute_swarm_wall_budget(
            n_items=len(to_analyze), concurrency=concurrency, is_cloud=is_cloud,
        )
        orch = SwarmOrchestrator(
            coordinator_llm=WorkerFactory._get_coordinator_llm_client(),
            worker_llm=self.llm,
            concurrency=concurrency,
            # Cloud coord/synth timeouts: 10s → 60s → 120s/180s → 180s/240s.
            # PowerMate (24 items) needed 111s coord and 169s synth at
            # 120s/180s budgets.  Larger repos (CoDRAG ~300 files,
            # potentially 50-100 clusters) scale roughly linearly with
            # coord prompt size.  Bumping coord 120s→180s and synth
            # 180s→240s gives ~50% headroom over PowerMate's actuals
            # while still failing fast on a dead endpoint.
            coordinator_timeout_s=180.0 if is_cloud else 90.0,
            synthesis_timeout_s=240.0 if is_cloud else 180.0,
            worker_timeout_s=180.0 if is_cloud else 300.0,
            max_wall_time_s=wall_budget,
            # Phase 127: pass project_id so the swarm honors soft-holds
            # at coord→fanout / fanout→synth boundaries.  Empty string
            # is fine — hold check is a no-op without a project key.
            project_id=self.project_id or None,
        )

        # Build WorkItem list
        items: list[WorkItem] = []
        gid_to_members: dict[str, list[str]] = {}
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
            f"You are coordinating parallel analysis of {len(items)} code groups.\n"
            "Each group is a connected component of related files.\n\n"
            "Groups:\n{group_summaries}\n\n"
            "For EACH group, assign a specific analysis_angle (what aspect to focus on)\n"
            "and priority_concerns (what risks to look for).\n\n"
            "Respond with JSON:\n"
            '{"assignments": [{"item_id": "group:...", "analysis_angle": "...", '
            '"priority_concerns": ["..."]}]}'
        )

        synthesis_prompt = (
            f"Below are the analysis results from {len(items)} parallel group analyses.\n\n"
            "{worker_outputs}\n\n"
            "Synthesize cross-group patterns:\n"
            '{"cross_group_patterns": ["..."], '
            '"shared_risks": ["..."], '
            '"architectural_recommendations": ["..."], '
            '"overall_health": "good|moderate|concerning"}'
        )

        def worker_fn(item: WorkItem, assignment: WorkerAssignment) -> str | None:
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
            project_id=self.project_id or None,
            # Phase 127 (P127-F9): forward cancel_token so the swarm
            # honors user-pause at phase boundaries and inside fanout's
            # as_completed loop.  Without this, the fanout pool keeps
            # dispatching its 10 parallel workers even after the
            # pipeline state machine flips to PAUSED.
            cancel_token=cancel_token,
        )

        if result is None:
            return {}

        # Convert WorkerResults to GroupReasoningEntry objects
        entries: dict[str, GroupReasoningEntry] = {}
        for wr in result.worker_results:
            if wr.success and wr.parsed:
                try:
                    entry = GroupReasoningEntry.from_dict(wr.parsed)
                    entries[entry.group_id] = entry
                except (KeyError, ValueError) as exc:
                    logger.warning("Failed to parse worker result for %s: %s", wr.item_id, exc)

        # Phase 127: if the swarm paused on a soft-hold, stash the
        # signal on self so the calling stage can short-circuit instead
        # of falling through to the sequential path (which would
        # re-engage the same held endpoint).  Partial entries are
        # preserved — they get written to disk and the next run resumes
        # the remaining groups.
        if result.paused:
            self._last_swarm_paused = True
            self._last_swarm_pause_info = result.pause_info or {}
            info = result.pause_info or {}
            logger.info(
                "[Swarm/GroupReasoning] paused on soft-hold "
                "(project=%s endpoint=%s) — %d/%d groups completed at pause",
                info.get("project_id", "?"), info.get("endpoint_id", "?"),
                len(entries), len(items),
            )
        else:
            self._last_swarm_paused = False
            self._last_swarm_pause_info = {}

        # 2026-05-27 (Phase 141): detect partial swarm completion.
        # When the wall-time cap or stall-detection fires, the swarm
        # cancels pending futures (swarm_orchestrator.py:609) and
        # returns with ``len(worker_results) < len(items)``.  Per-worker
        # failures (HTTP errors, unparseable JSON) still produce a
        # WorkerResult with ``success=False`` — those count as ATTEMPTED
        # even if they didn't yield an entry.  So the test for
        # "incomplete" is whether the orchestrator dispatched all items,
        # which is exactly ``len(result.worker_results) < len(items)``.
        #
        # The 2026-05-26 silent shrink was: 99 of 160 workers cancelled
        # by the 900s wall cap, ``_run_swarm`` returned 61 parsed entries,
        # the caller wrote them over a 166-record file.  Now we surface
        # the incomplete signal so the caller refuses to write.
        attempted = len(result.worker_results)
        total_items = len(items)
        if not result.paused and attempted < total_items:
            self._last_swarm_incomplete = True
            self._last_swarm_incomplete_info = {
                "attempted": attempted,
                "total": total_items,
                "parsed_entries": len(entries),
                "wall_clock_seconds": result.stats.wall_clock_seconds,
            }
            logger.error(
                "[Swarm/GroupReasoning] INCOMPLETE: only %d of %d workers "
                "attempted (rest cancelled by wall-time cap or stall) — "
                "wall_clock=%.0fs.  Refusing to overwrite cache with "
                "truncated results.",
                attempted, total_items, result.stats.wall_clock_seconds,
            )
        else:
            self._last_swarm_incomplete = False
            self._last_swarm_incomplete_info = {}

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
            "timestamp": datetime.now(UTC).isoformat(),
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
        member_ids: list[str],
        epistemic: dict[str, EpistemicEntry],
        edges: list[dict[str, Any]],
    ) -> GroupReasoningEntry | None:
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

            from prep.core.llm_client import TASK_MAX_CHARS
            if hold_paused_for_llm(self.llm, self.project_id, logger):
                raise_hold_paused_for_llm(self.llm, self.project_id)
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
        except HoldPausedError:
            raise
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

        return GroupReasoningEntry(
            group_id=group_id,
            member_node_ids=member_ids,
            pattern=str(parsed.get("pattern", "unknown"))[:200],
            data_flow=str(parsed.get("data_flow", ""))[:500],
            coupling_risks=[str(r) for r in parsed.get("coupling_risks", [])][:10],
            blast_radius=[str(r) for r in parsed.get("blast_radius", [])][:20],
            architectural_insight=str(parsed.get("architectural_insight", ""))[:500],
            confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.7)))),
            analyzed_at=datetime.now(UTC).isoformat(),
            model=self.llm.model,
        )

    def run(
        self,
        progress_callback: Callable[..., None] | None = None,
        cancel_token: Any | None = None,
    ) -> dict[str, Any]:
        """Run group deep reasoning on all dependency groups.

        Steps:
        1. Load epistemic entries and edges.
        2. Build dependency groups from the trace graph.
        3. Check staleness via Changeset: skip groups whose members are all unchanged per stage 1's Changeset.
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

        # Assign stable group IDs anchored on a STABLE SUBSET of members.
        # Phase 136 Part 12: pre-Phase-136 the id was the hash of the
        # ENTIRE sorted member list — adding even one new file changed
        # the hash, invalidated the prior entry, and forced full
        # re-analysis.  Observed dogfooding: 54 added files caused
        # 98 of 109 groups to re-analyze (90% cache miss) on what
        # should have been a near-no-op incremental run.
        #
        # Anchor on the 3 lexicographically-smallest members.  Adding
        # higher-sort members → anchors unchanged → id stable → entry
        # carried forward via `existing.get(gid)`.  Small-group cases
        # (< 3 members) anchor on the full set, which is fine —
        # tiny groups change less often by virtue of having less
        # surface area for new files to join.
        group_map: dict[str, list[str]] = {}
        for members in groups:
            group_map[_stable_group_id(members)] = members

        # Phase 135: a group is stale iff any member file is in
        # changeset.modified | deleted. No fingerprint computation —
        # the changeset is the canonical source of truth.
        #
        # Phase 136 Part 12: fall back to a Jaccard-overlap match when
        # the exact gid lookup misses — incremental runs that add a
        # peripheral file to an existing group produce a new gid
        # (hash includes the new member), but the prior analysis is
        # still valid if member sets are mostly identical.
        to_analyze: list[tuple[str, list[str]]] = []
        reuse: dict[str, GroupReasoningEntry] = {}

        for gid, members in group_map.items():
            ex = existing.get(gid)
            if ex is None:
                # Fast-path miss — try fuzzy match before giving up.
                _legacy_gid, ex = _find_overlapping_entry(members, existing)
            if ex is not None and not self._group_is_stale(members):
                reuse[gid] = ex
            else:
                to_analyze.append((gid, members))

        total_groups = len(group_map)
        logger.info(
            "Group reasoning: %d groups total, %d to analyze, %d reused (unchanged per changeset)",
            total_groups, len(to_analyze), len(reuse),
        )

        if progress_callback:
            progress_callback("group_reasoning", len(reuse), total_groups, len(reuse))

        analyzed = 0
        failed = 0
        results: dict[str, GroupReasoningEntry] = dict(reuse)

        # ── Swarm decision ──────────────────────────────────────────
        swarm_tier = get_swarm_tier(self.llm.provider, self.llm.model)
        swarm_enabled = self._get_swarm_enabled()
        min_threshold = get_min_groups_threshold()
        use_swarm = (
            swarm_tier.can_coordinate
            and swarm_enabled
            and len(to_analyze) >= min_threshold
        )

        # Phase 136 Part 13: gate on scheduler ownership.  Without this
        # check, both Module Synthesis and Group Reasoning could launch
        # SwarmOrchestrators concurrently on the same project / endpoint,
        # racing for capacity that swarm was designed to reserve.  If
        # the scheduler hasn't granted this stage the window, fall back
        # to sequential dispatch.
        if use_swarm:
            from prep.services.pipeline.scheduler import pipeline_scheduler
            from prep.services.pipeline.stages import StageId
            if not pipeline_scheduler.is_my_swarm_window(
                self.project_id or "", StageId.GROUP_REASONING,
            ):
                logger.info(
                    "Group reasoning: scheduler did not grant swarm window "
                    "(another stage owns it or it failed to open) — falling "
                    "back to sequential dispatch",
                )
                use_swarm = False

        if use_swarm:
            logger.info(
                "Group reasoning: using SWARM orchestration (%s, %d groups, tier=%s)",
                self.llm.model, len(to_analyze), swarm_tier.value,
            )
            swarm_entries = self._run_swarm(
                to_analyze, epistemic, edges, progress_callback, cancel_token,
            )
            # Phase 127: if the swarm paused on a soft-hold, persist
            # whatever partial entries we collected and return
            # ``paused=True`` immediately — DO NOT fall through to the
            # sequential path, which would re-engage the same held
            # endpoint and burn calls against it.
            if getattr(self, "_last_swarm_paused", False):
                if swarm_entries:
                    results.update(swarm_entries)
                    self._write_results(results)
                analyzed = len(swarm_entries)
                elapsed = time.monotonic() - start
                return {
                    "total_groups": total_groups,
                    "analyzed": analyzed,
                    "reused": len(reuse),
                    "failed": 0,
                    "remaining": len(to_analyze) - analyzed,
                    "duration_ms": round(elapsed * 1000, 1),
                    "swarm": True,
                    "paused": True,
                    "pause_info": getattr(self, "_last_swarm_pause_info", {}),
                }
            # 2026-05-27 (Phase 141): refuse to overwrite the cache with
            # a truncated result.  When the swarm fan-out wall cap (or
            # stall detection) fires, pending workers are cancelled and
            # the returned entries cover only a fraction of the work
            # the stage was asked to do.  Writing that partial result
            # over the existing file is the silent-shrink vector the
            # 2026-05-26 incident demonstrated (166 → 61 records).
            #
            # Defense-in-depth: even though Fix #3 (workload-scaled
            # wall budget) makes this unlikely on the happy path,
            # transient rate-limits, network failures, or future
            # workload growth could still trip the cap.  Fail loudly
            # here so the user retries; the on-disk file is preserved
            # in its pre-stage state.
            if getattr(self, "_last_swarm_incomplete", False):
                info = getattr(self, "_last_swarm_incomplete_info", {})
                attempted = info.get("attempted", "?")
                total_items = info.get("total", "?")
                wall = info.get("wall_clock_seconds", 0.0)
                msg = (
                    f"Group reasoning swarm incomplete: only "
                    f"{attempted}/{total_items} workers attempted "
                    f"(wall_clock={wall:.0f}s).  Refusing to overwrite "
                    f"trace_group_reasoning.jsonl with truncated results — "
                    f"previous cache preserved.  Likely cause: swarm "
                    f"wall-time cap fired or stall detected.  Retry the "
                    f"stage; if it persists, check the LLM endpoint "
                    f"latency or raise the wall budget."
                )
                logger.error(msg)
                raise RuntimeError(msg)
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
            from prep.core.batch_profiles import get_batch_concurrency
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

    def _write_results(self, entries: dict[str, GroupReasoningEntry]) -> None:
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
