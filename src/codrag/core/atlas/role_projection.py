"""
Role Projection Engine for CoDRAG (Phase 64A).

Scores every indexed file against a RoleVector and assembles a
role-appropriate sub-atlas within budget.  Uses three detail levels:
  - Executive  (detail < 0.3): Module summaries only
  - Manager    (detail 0.3-0.7): Modules + key file highlights
  - Practitioner (detail > 0.7): File-level detail

All data is read from existing pipeline outputs (trace_epistemic.jsonl,
trace_modules.jsonl, trace_edges.jsonl, atlas.json).  Zero LLM calls.

Performance: O(n) file scoring + O(k log k) top-K selection.
Typical runtime: <10ms for 1000 files.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .role_vectors import RoleVector, max_tag_affinity

logger = logging.getLogger(__name__)


# ── Scoring weights ──────────────────────────────────────────────────

# How much each scoring component contributes to the final relevance score.
SCORING_WEIGHTS = {
    "layer_match": 0.30,
    "tag_affinity": 0.35,
    "centrality": 0.20,
    "confidence": 0.15,
}


# ── Per-file relevance scoring ───────────────────────────────────────

def compute_role_relevance(
    file_path: str,
    architecture_layer: str,
    domain_tags: List[str],
    epistemic_confidence: float,
    in_degree: int,
    max_degree: int,
    role: RoleVector,
) -> float:
    """Compute how relevant a file is to a given role (0.0-1.0).

    Components:
      1. Architecture layer match (0.30): role.layer_weights[file.layer]
      2. Domain tag affinity (0.35):      fuzzy match file tags vs role keywords
      3. Graph centrality (0.20):         normalized in_degree × role.centrality_weight
      4. Epistemic confidence (0.15):     prefers well-understood files

    Args:
        file_path: Repo-relative file path.
        architecture_layer: File's architecture_layer from epistemic enrichment.
        domain_tags: File's domain_tags from epistemic enrichment.
        epistemic_confidence: File's epistemic confidence (0.0-1.0).
        in_degree: Number of incoming edges to this file.
        max_degree: Maximum in_degree across all files (for normalization).
        role: The RoleVector to score against.

    Returns:
        Relevance score in [0.0, 1.0].
    """
    # 1. Layer match
    layer_score = role.layer_weights.get(architecture_layer, 0.1)

    # 2. Tag affinity
    tag_score = max_tag_affinity(domain_tags, role.domain_affinity)

    # 3. Centrality
    if max_degree > 0:
        # Normalize: top 30th percentile maps to 1.0
        norm = min(1.0, in_degree / max(1, max_degree * 0.3))
    else:
        norm = 0.0
    centrality_score = norm * role.centrality_weight

    # 4. Confidence
    confidence_score = max(0.0, min(1.0, epistemic_confidence))

    # Weighted composite
    relevance = (
        SCORING_WEIGHTS["layer_match"] * layer_score
        + SCORING_WEIGHTS["tag_affinity"] * tag_score
        + SCORING_WEIGHTS["centrality"] * centrality_score
        + SCORING_WEIGHTS["confidence"] * confidence_score
    )

    return round(min(1.0, relevance), 4)


# ── Data loading helpers ─────────────────────────────────────────────

def _load_epistemic_entries(index_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load epistemic entries as raw dicts keyed by node_id."""
    path = index_dir / "trace_epistemic.jsonl"
    entries: Dict[str, Dict[str, Any]] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        d = json.loads(line)
                        entries[d["node_id"]] = d
                    except (json.JSONDecodeError, KeyError):
                        continue
    return entries


def _load_modules(index_dir: Path) -> List[Dict[str, Any]]:
    """Load module entries from trace_modules.jsonl."""
    path = index_dir / "trace_modules.jsonl"
    modules: List[Dict[str, Any]] = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        modules.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return modules


def _compute_in_degrees(index_dir: Path) -> Dict[str, int]:
    """Compute in-degree for each file node from trace edges."""
    degrees: Dict[str, int] = defaultdict(int)
    for fname in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
        path = index_dir / fname
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            e = json.loads(line)
                            target = e.get("target", "")
                            if target.startswith("file:"):
                                degrees[target] += 1
                        except json.JSONDecodeError:
                            continue
    return dict(degrees)


def _extract_identity(atlas_content: str) -> str:
    """Extract the IDENTITY line from full atlas content."""
    if not atlas_content:
        return ""
    for line in atlas_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("IDENTITY:"):
            return stripped
    # Fallback: first non-empty line
    for line in atlas_content.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("STACK:"):
            return stripped
    return ""


def _extract_stack(atlas_content: str) -> str:
    """Extract the STACK line from full atlas content."""
    if not atlas_content:
        return ""
    for line in atlas_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("STACK:"):
            return stripped
    return ""


# ── Main projection function ─────────────────────────────────────────

def project_atlas_for_role(
    role: RoleVector,
    index_dir: Path,
    atlas_content: str = "",
) -> str:
    """Project the codebase atlas through a role-specific lens.

    Loads epistemic enrichments, scores every file against the role,
    and assembles a context string at the appropriate detail level
    within the role's char budget.

    Args:
        role: The resolved RoleVector.
        index_dir: Path to the project's index directory.
        atlas_content: The full atlas content (for identity/stack extraction).

    Returns:
        A role-filtered sub-atlas string.
    """
    # Load data
    epistemic = _load_epistemic_entries(index_dir)
    modules = _load_modules(index_dir)
    in_degrees = _compute_in_degrees(index_dir)

    if not epistemic:
        # No epistemic data — return the full atlas with a role note
        if atlas_content:
            return f"[Role: {role.display_name}]\n\n{atlas_content}"
        return f"[Role: {role.display_name}] No codebase data available."

    # Score every file
    max_degree = max(in_degrees.values()) if in_degrees else 0
    scored: List[Tuple[str, Dict[str, Any], float]] = []

    for node_id, entry in epistemic.items():
        if not node_id.startswith("file:"):
            continue

        file_path = node_id[5:]  # strip "file:" prefix
        score = compute_role_relevance(
            file_path=file_path,
            architecture_layer=entry.get("architecture_layer", "unknown"),
            domain_tags=entry.get("domain_tags", []),
            epistemic_confidence=float(entry.get("epistemic_confidence", 0.5)),
            in_degree=in_degrees.get(node_id, 0),
            max_degree=max_degree,
            role=role,
        )
        scored.append((file_path, entry, score))

    # Sort by relevance (descending)
    scored.sort(key=lambda x: -x[2])

    # Extract identity/stack from atlas
    identity = _extract_identity(atlas_content)
    stack = _extract_stack(atlas_content)

    # Route to detail-level-appropriate assembly
    if role.detail_level < 0.3:
        return _assemble_executive(role, identity, stack, modules, scored)
    elif role.detail_level <= 0.7:
        return _assemble_manager(role, identity, stack, modules, scored)
    else:
        return _assemble_practitioner(role, identity, stack, modules, scored)


# ── Assembly functions ───────────────────────────────────────────────

def _assemble_executive(
    role: RoleVector,
    identity: str,
    stack: str,
    modules: List[Dict[str, Any]],
    scored_files: List[Tuple[str, Dict[str, Any], float]],
) -> str:
    """Executive-level assembly: module summaries only.

    Output ~800-1500 chars.  No file paths.  No code.
    """
    budget = role.max_chars
    parts: List[str] = []

    # Header
    parts.append(f"[{role.display_name} View]")
    if identity:
        parts.append(identity)
    parts.append("")

    # Module summaries
    if modules:
        file_count = len(scored_files)
        parts.append(f"MODULES ({len(modules)} subsystems, {file_count} files):")
        for mod in modules:
            name = mod.get("name", "Unknown")
            summary = mod.get("summary", "")
            member_count = mod.get("file_count", len(mod.get("member_files", [])))
            status = mod.get("component_status", "")
            # Truncate summary for executive brevity
            if len(summary) > 120:
                summary = summary[:117] + "..."
            line = f"• {name} ({member_count} files): {summary}"
            if status and status != "unknown":
                line += f" Status: {status}."
            parts.append(line)
    else:
        # Fallback: summarize top files by domain
        tag_counts: Counter = Counter()
        for _, entry, score in scored_files[:50]:
            for tag in entry.get("domain_tags", []):
                tag_counts[tag] += 1
        if tag_counts:
            top_tags = ", ".join(t for t, _ in tag_counts.most_common(8))
            parts.append(f"KEY DOMAINS: {top_tags}")

    # Trim to budget
    result = "\n".join(parts)
    if len(result) > budget:
        result = result[:budget - 3] + "..."
    return result


def _assemble_manager(
    role: RoleVector,
    identity: str,
    stack: str,
    modules: List[Dict[str, Any]],
    scored_files: List[Tuple[str, Dict[str, Any], float]],
) -> str:
    """Manager-level assembly: module summaries + key file highlights.

    Output ~2000-3000 chars.
    """
    budget = role.max_chars
    parts: List[str] = []

    # Header
    parts.append(f"[{role.display_name} View]")
    if identity:
        parts.append(identity)
    if stack:
        parts.append(stack)
    parts.append("")

    # Module summaries with key files
    if modules:
        parts.append(f"MODULES ({len(modules)} subsystems):")
        for mod in modules:
            name = mod.get("name", "Unknown")
            summary = mod.get("summary", "")
            status = mod.get("component_status", "")
            member_files = mod.get("member_files", [])

            if len(summary) > 180:
                summary = summary[:177] + "..."
            line = f"• {name}: {summary}"
            if status and status != "unknown":
                line += f" [{status}]"
            parts.append(line)

            # Show top 2-3 key files from this module that rank high
            mod_file_set = set(member_files)
            key_files = [
                (fp, entry, score) for fp, entry, score in scored_files
                if fp in mod_file_set and score > 0.3
            ][:3]
            for fp, entry, score in key_files:
                basename = Path(fp).name
                brief = entry.get("extended_summary", "")
                if len(brief) > 100:
                    brief = brief[:97] + "..."
                if brief:
                    parts.append(f"  - {basename}: {brief}")

        parts.append("")

    # Top files not covered by modules
    already_shown = set()
    if modules:
        for mod in modules:
            already_shown.update(mod.get("member_files", []))

    extra_top = [
        (fp, entry, score) for fp, entry, score in scored_files[:20]
        if fp not in already_shown and score > 0.35
    ][:5]

    if extra_top:
        parts.append("KEY FILES:")
        for fp, entry, score in extra_top:
            basename = Path(fp).name
            layer = entry.get("architecture_layer", "")
            brief = entry.get("extended_summary", "")
            if len(brief) > 100:
                brief = brief[:97] + "..."
            parts.append(f"• {basename} ({layer}): {brief}")

    # Trim to budget
    result = "\n".join(parts)
    if len(result) > budget:
        # Truncate at last complete line within budget
        lines = result.split("\n")
        result = ""
        for line in lines:
            if len(result) + len(line) + 1 > budget - 20:
                break
            result += line + "\n"
        result = result.rstrip() + "\n..."
    return result


def _assemble_practitioner(
    role: RoleVector,
    identity: str,
    stack: str,
    modules: List[Dict[str, Any]],
    scored_files: List[Tuple[str, Dict[str, Any], float]],
) -> str:
    """Practitioner-level assembly: file-level detail for relevant files.

    Output ~2500-4000 chars.
    """
    budget = role.max_chars
    parts: List[str] = []

    # Header
    parts.append(f"[{role.display_name} View]")
    if identity:
        parts.append(identity)
    if stack:
        parts.append(stack)
    parts.append("")

    # Group relevant files by module if possible
    file_to_module: Dict[str, str] = {}
    if modules:
        for mod in modules:
            mod_name = mod.get("name", "Unknown")
            for fp in mod.get("member_files", []):
                file_to_module[fp] = mod_name

    # Top scored files with full detail
    parts.append("RELEVANT FILES:")
    current_module = ""
    files_shown = 0
    max_files = 30  # hard cap

    for fp, entry, score in scored_files:
        if score < 0.2 or files_shown >= max_files:
            break

        # Check budget before adding
        running = "\n".join(parts)
        if len(running) > budget - 200:
            break

        # Module header (if grouped)
        mod_name = file_to_module.get(fp, "")
        if mod_name and mod_name != current_module:
            parts.append(f"\n## {mod_name}")
            current_module = mod_name

        # File entry
        basename = Path(fp).name
        layer = entry.get("architecture_layer", "")
        tags = ", ".join(entry.get("domain_tags", [])[:3])
        summary = entry.get("extended_summary", "")

        # Trim summary based on available budget
        remaining = budget - len("\n".join(parts))
        max_summary = min(150, remaining - 100)
        if len(summary) > max_summary and max_summary > 20:
            summary = summary[:max_summary - 3] + "..."

        line = f"• {basename}"
        if layer:
            line += f" ({layer})"
        if tags:
            line += f" [{tags}]"
        parts.append(line)
        if summary:
            parts.append(f"  {summary}")

        files_shown += 1

    if files_shown == 0:
        parts.append("  (No files matched this role's criteria)")

    # Trim to budget
    result = "\n".join(parts)
    if len(result) > budget:
        lines = result.split("\n")
        result = ""
        for line in lines:
            if len(result) + len(line) + 1 > budget - 20:
                break
            result += line + "\n"
        result = result.rstrip() + "\n..."
    return result
