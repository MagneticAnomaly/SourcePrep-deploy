"""Structural-only audit scanner for CoDRAG.

Returns ONLY CoDRAG-unique findings: coupling hotspots and import cycles.
Deliberately excludes anything a linter can already catch.
"""
from __future__ import annotations

import os
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from codrag.core.audit.recommendations import compute_risk_score, generate_recommendation

# Exact basenames that are always generated/lock files
_GENERATED_BASENAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "composer.lock", "Cargo.lock", "poetry.lock", "Pipfile.lock",
})

# Suffixes that indicate generated files
_GENERATED_SUFFIXES = (
    ".d.ts", ".min.js", ".min.css", ".pb.go", "_pb2.py",
    ".generated.ts", ".generated.py",
)

# Directory components that indicate generated content
_GENERATED_DIRS = frozenset({"__generated__", "generated", "dist", "build"})

# Minimum z-score to flag a file as a coupling hotspot
_ZSCORE_THRESHOLD = 2.0

# Minimum absolute in-degree to flag as coupling hotspot
_MIN_INDEGREE = 8


def _is_generated(file_path: str) -> bool:
    """Return True if the file path looks like a generated/lock file."""
    basename = os.path.basename(file_path)
    if basename in _GENERATED_BASENAMES:
        return True
    if any(file_path.endswith(suffix) for suffix in _GENERATED_SUFFIXES):
        return True
    parts = set(file_path.replace("\\", "/").split("/"))
    if parts & _GENERATED_DIRS:
        return True
    return False


@dataclass
class StructuralFinding:
    """A single structural audit finding (coupling hotspot or import cycle)."""

    finding_type: str           # "coupling_hotspot" | "import_cycle"
    file_path: str              # Primary file path for dedup key
    severity: str               # "critical" | "high" | "moderate" | "low" | "info"
    title: str
    description: str
    risk_score: float           # 0-1
    recommendation: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    related_concepts: List[str] = field(default_factory=list)
    related_observations: List[str] = field(default_factory=list)


def _hub_severity(in_degree: int, z_score: float) -> str:
    if z_score >= 4.0 or in_degree >= 20:
        return "critical"
    if z_score >= 3.0 or in_degree >= 15:
        return "high"
    if z_score >= 2.0 or in_degree >= 8:
        return "moderate"
    return "low"


def _cycle_severity(cycle_length: int) -> str:
    if cycle_length >= 6:
        return "high"
    if cycle_length >= 3:
        return "moderate"
    return "low"


def _related_concepts_for_file(file_path: str, concepts: List[Dict[str, Any]]) -> List[str]:
    results = []
    for c in concepts:
        title = c.get("title", "")
        anchors = c.get("anchors") or []
        category = c.get("category", "")
        if any(file_path in a for a in anchors) or file_path in title:
            results.append(f"{title} [{category}]" if category else title)
    return results


def _related_observations_for_file(file_path: str, observations: List[Dict[str, Any]]) -> List[str]:
    results = []
    for o in observations:
        obs_path = o.get("file_path", "")
        content = o.get("content", "")
        if file_path in obs_path or (obs_path and obs_path in file_path):
            results.append(content[:120] if content else obs_path)
    return results


def _compute_hub_percentile(in_degree: int, all_degrees: List[int]) -> float:
    if not all_degrees:
        return 0.0
    below = sum(1 for d in all_degrees if d < in_degree)
    return below / len(all_degrees)


def _detect_coupling_hotspots(
    hub_files: List[Tuple[str, int]],
    concepts: List[Dict[str, Any]],
    observations: List[Dict[str, Any]],
) -> List[StructuralFinding]:
    """Detect files with anomalously high in-degree (z-score >= 2.0, in_degree >= 8)."""
    # Filter generated files first
    filtered = [(fp, deg) for fp, deg in hub_files if not _is_generated(fp)]

    if len(filtered) < 2:
        # Not enough data for meaningful stats
        return []

    degrees = [deg for _, deg in filtered]
    mean = statistics.mean(degrees)
    # Use population stdev but fall back to 1.0 to avoid division-by-zero
    try:
        stdev = statistics.stdev(degrees)
    except statistics.StatisticsError:
        stdev = 1.0
    if stdev < 1e-9:
        stdev = 1.0

    findings: List[StructuralFinding] = []
    seen_files: set = set()

    all_degrees = [d for _, d in filtered]

    for file_path, in_degree in filtered:
        if file_path in seen_files:
            continue
        z_score = (in_degree - mean) / stdev
        if z_score < _ZSCORE_THRESHOLD or in_degree < _MIN_INDEGREE:
            continue

        seen_files.add(file_path)

        severity = _hub_severity(in_degree, z_score)
        hub_status = severity  # reuse severity label for generate_recommendation
        hub_percentile = _compute_hub_percentile(in_degree, all_degrees)

        rel_concepts = _related_concepts_for_file(file_path, concepts)
        rel_obs = _related_observations_for_file(file_path, observations)

        has_constraint = any("constraint" in c.lower() for c in rel_concepts)
        has_arch = any("arch" in c.lower() for c in rel_concepts)

        risk = compute_risk_score(
            hub_percentile=hub_percentile,
            has_constraint_concept=has_constraint,
            has_architecture_concept=has_arch,
            observation_score=min(1.0, len(rel_obs) * 0.25),
        )

        concept_titles = [c.split(" [")[0] for c in rel_concepts]
        obs_summaries = rel_obs[:3]

        recommendation = generate_recommendation(
            hub_status=hub_status,
            dependents=in_degree,
            concepts=concept_titles,
            observations=obs_summaries,
        )

        findings.append(
            StructuralFinding(
                finding_type="coupling_hotspot",
                file_path=file_path,
                severity=severity,
                title=f"Coupling hotspot: {file_path}",
                description=(
                    f"{file_path} has {in_degree} incoming dependencies "
                    f"(z-score {z_score:.1f}), making it a structural bottleneck."
                ),
                risk_score=risk,
                recommendation=recommendation,
                evidence={
                    "in_degree": in_degree,
                    "z_score": round(z_score, 2),
                    "mean_degree": round(mean, 2),
                    "stdev_degree": round(stdev, 2),
                    "hub_percentile": round(hub_percentile, 3),
                },
                related_concepts=rel_concepts,
                related_observations=rel_obs,
            )
        )

    return findings


def _detect_import_cycles(
    cycles: List[List[str]],
    concepts: List[Dict[str, Any]],
    observations: List[Dict[str, Any]],
) -> List[StructuralFinding]:
    """Detect import cycles and return one finding per unique cycle."""
    findings: List[StructuralFinding] = []
    seen_keys: set = set()

    for cycle in cycles:
        if not cycle:
            continue

        # Filter generated files from cycle members
        clean = [f for f in cycle if not _is_generated(f)]
        if len(clean) < 2:
            continue

        # Stable key: frozenset so order doesn't matter for dedup
        key = frozenset(clean)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        # Canonical file_path = first member (alphabetically sorted for stability)
        canonical = sorted(clean)[0]
        length = len(clean)

        severity = _cycle_severity(length)
        risk = compute_risk_score(
            hub_percentile=min(1.0, length / 10.0),
            has_constraint_concept=False,
            has_architecture_concept=False,
        )

        rel_concepts: List[str] = []
        rel_obs: List[str] = []
        for fp in clean:
            rel_concepts.extend(_related_concepts_for_file(fp, concepts))
            rel_obs.extend(_related_observations_for_file(fp, observations))
        # Deduplicate
        rel_concepts = list(dict.fromkeys(rel_concepts))
        rel_obs = list(dict.fromkeys(rel_obs))

        findings.append(
            StructuralFinding(
                finding_type="import_cycle",
                file_path=canonical,
                severity=severity,
                title=f"Import cycle ({length} files)",
                description=(
                    f"Circular import chain detected: {' → '.join(clean)} → {clean[0]}. "
                    f"Cycles prevent independent module loading and complicate refactoring."
                ),
                risk_score=risk,
                recommendation=(
                    f"Break the cycle by extracting shared dependencies into a new module "
                    f"that none of the {length} participants imports, or apply dependency inversion."
                ),
                evidence={
                    "cycle_length": length,
                    "members": clean,
                },
                related_concepts=rel_concepts,
                related_observations=rel_obs,
            )
        )

    return findings


# Map category param values to finding_type values
_CATEGORY_TO_FINDING_TYPE = {
    "coupling": {"coupling_hotspot"},
    "cycles": {"import_cycle"},
    "hub_concentration": {"coupling_hotspot"},
    "concept_violation": set(),  # Future: Phase 84
}


def run_structural_audit(
    ctx: Dict[str, Any],
    max_findings: int = 20,
    scope: Optional[str] = None,
    category: Optional[str] = None,
) -> List[StructuralFinding]:
    """Run the structural-only audit and return up to max_findings findings.

    Args:
        ctx: Dict with keys:
            - hub_files: List[Tuple[str, int]] — (file_path, in_degree)
            - cycles: List[List[str]] — import cycle members
            - modules: List[Dict] — module metadata (unused in structural scan)
            - concepts: List[Dict] — concept records for cross-referencing
            - observations: List[Dict] — observation records for cross-referencing
            - total_files: int — total file count (for context)
        max_findings: Maximum findings to return (default 20).
        scope: Optional file or directory path to limit scan to.
        category: Optional category filter ("coupling", "cycles", "hub_concentration").

    Returns:
        List of StructuralFinding sorted by risk_score descending, deduplicated
        (one entry per finding_type + file_path pair), capped at max_findings.
    """
    hub_files: List[Tuple[str, int]] = ctx.get("hub_files", [])
    cycles: List[List[str]] = ctx.get("cycles", [])
    concepts: List[Dict[str, Any]] = ctx.get("concepts", []) or []
    observations: List[Dict[str, Any]] = ctx.get("observations", []) or []

    # Apply scope filter — limit to files under the given path prefix
    if scope:
        hub_files = [(fp, deg) for fp, deg in hub_files if fp.startswith(scope)]
        cycles = [c for c in cycles if any(fp.startswith(scope) for fp in c)]

    # Determine which finding types to generate based on category filter
    allowed_types = _CATEGORY_TO_FINDING_TYPE.get(category) if category else None

    all_findings: List[StructuralFinding] = []
    if allowed_types is None or "coupling_hotspot" in allowed_types:
        all_findings.extend(_detect_coupling_hotspots(hub_files, concepts, observations))
    if allowed_types is None or "import_cycle" in allowed_types:
        all_findings.extend(_detect_import_cycles(cycles, concepts, observations))

    # Final dedup pass by (finding_type, file_path) — keeps highest risk_score
    deduped: Dict[Tuple[str, str], StructuralFinding] = {}
    for f in all_findings:
        key = (f.finding_type, f.file_path)
        existing = deduped.get(key)
        if existing is None or f.risk_score > existing.risk_score:
            deduped[key] = f

    sorted_findings = sorted(deduped.values(), key=lambda f: f.risk_score, reverse=True)
    return sorted_findings[:max_findings]
