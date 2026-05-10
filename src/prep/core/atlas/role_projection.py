"""
Role Projection Engine for Prep (Phase 64A).

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


# ── Path-based heuristic tables (structural fallback) ────────────────
# When trace_epistemic.jsonl doesn't exist yet (Fast Path, only Stage 1),
# we infer architecture_layer and domain_tags from file paths and extensions.

PATH_LAYER_RULES: List[Tuple[Tuple[str, ...], str]] = [
    # Each rule: (tuple-of-path-keywords, architecture_layer)
    # Matched against path directory segments. Checked in order; first match wins.
    # Testing first — test directories are unambiguous and may contain files
    # with names like "test_api.py" that would otherwise match "api".
    (("test", "tests", "spec", "fixture", "__test__", "__tests__", "e2e"), "testing"),
    (("api", "routes", "endpoint", "handler", "views", "controller"), "presentation"),
    (("ui", "component", "page", "layout", "widget", "screen"), "presentation"),
    (("core", "engine", "service", "logic", "domain", "usecase"), "business_logic"),
    (("db", "model", "schema", "migration", "orm", "repository"), "data_access"),
    (("auth", "security", "permission", "rbac", "crypto", "token"), "security"),
    (("deploy", "docker", "k8s", "infra", "ci", "terraform", "helm"), "infrastructure"),
    (("config", "settings", "env", "dotenv"), "configuration"),
    (("util", "helper", "lib", "shared", "common"), "utility"),
    (("cli", "cmd", "command"), "presentation"),
    (("plugin", "extension", "addon", "middleware"), "integration"),
    (("doc", "docs", "readme", "guide"), "documentation"),
]

EXT_TAG_RULES: Dict[str, List[str]] = {
    ".tsx": ["ui", "frontend", "react"],
    ".jsx": ["ui", "frontend", "react"],
    ".vue": ["ui", "frontend", "vue"],
    ".svelte": ["ui", "frontend", "svelte"],
    ".css": ["ui", "styling"],
    ".scss": ["ui", "styling"],
    ".html": ["ui", "frontend"],
    ".py": ["backend", "python"],
    ".rs": ["backend", "systems"],
    ".go": ["backend", "go"],
    ".java": ["backend", "java"],
    ".kt": ["backend", "kotlin"],
    ".rb": ["backend", "ruby"],
    ".ts": ["backend", "typescript"],
    ".js": ["backend", "javascript"],
    ".sql": ["database", "query"],
    ".prisma": ["database", "orm"],
    ".proto": ["api", "grpc"],
    ".graphql": ["api", "graphql"],
    ".yaml": ["config", "infrastructure"],
    ".yml": ["config", "infrastructure"],
    ".toml": ["config"],
    ".json": ["config", "data"],
    ".tf": ["infrastructure", "terraform"],
    ".dockerfile": ["infrastructure", "docker"],
    ".md": ["documentation"],
    ".test.py": ["test", "backend"],
    ".test.ts": ["test", "frontend"],
    ".test.tsx": ["test", "frontend"],
    ".spec.ts": ["test", "frontend"],
    ".spec.tsx": ["test", "frontend"],
}


def _infer_layer_from_path(file_path: str) -> str:
    """Infer architecture_layer from file path using directory segment matching.

    Used as a fallback when trace_epistemic.jsonl doesn't exist yet.
    Matches keywords against path directory segments (not substrings) to
    avoid false positives like "test_api.py" matching "api".
    Returns "unknown" if no rule matches.
    """
    # Split into directory segments (exclude filename)
    parts = file_path.lower().replace("\\", "/").split("/")
    # Include directory segments (everything except the last part which is the filename)
    dir_segments = set(parts[:-1]) if len(parts) > 1 else set()
    for keywords, layer in PATH_LAYER_RULES:
        for kw in keywords:
            if kw in dir_segments:
                return layer
    return "unknown"


def _infer_tags_from_path(file_path: str) -> List[str]:
    """Infer domain_tags from file path and extension.

    Used as a fallback when trace_epistemic.jsonl doesn't exist yet.
    Combines extension-based tags with path-keyword tags.
    """
    tags: List[str] = []

    # Extension-based tags (check longer suffixes first for .test.py etc.)
    lower = file_path.lower()
    matched_ext = False
    for ext in sorted(EXT_TAG_RULES.keys(), key=len, reverse=True):
        if lower.endswith(ext):
            tags.extend(EXT_TAG_RULES[ext])
            matched_ext = True
            break

    # Path-keyword tags (add unique tags from path segments)
    parts = lower.replace("\\", "/").split("/")
    path_keywords = {
        "api": "api", "rest": "api", "graphql": "graphql",
        "auth": "auth", "security": "security",
        "test": "test", "tests": "test", "__tests__": "test",
        "deploy": "deploy", "infra": "infrastructure",
        "docker": "docker", "ci": "ci-cd",
        "config": "config", "settings": "config",
        "ui": "ui", "frontend": "frontend", "components": "ui",
        "core": "core", "engine": "engine",
        "db": "database", "models": "database",
        "migration": "database", "seed": "database",
        "docs": "documentation", "scripts": "tooling",
        "cli": "cli",
    }
    for part in parts:
        if part in path_keywords:
            tag = path_keywords[part]
            if tag not in tags:
                tags.append(tag)

    return tags[:5]  # Cap at 5 tags


def _load_trace_nodes(index_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load file entries from trace_nodes.jsonl as synthetic epistemic entries.

    Used as a fallback when trace_epistemic.jsonl doesn't exist.
    Infers architecture_layer and domain_tags from file paths. Applies the
    live `effective_excludes()` so stale leaked paths in the .jsonl (e.g.
    storybook-static, *.d.ts from a pre-Phase-115 build) don't feed back
    into the role-projection atlas.
    """
    from prep.core.repo_policy import effective_excludes, load_repo_policy, policy_path_for_index

    path = index_dir / "trace_nodes.jsonl"
    entries: Dict[str, Dict[str, Any]] = {}
    if not path.exists():
        return entries

    # Derive repo_root from the on-disk policy; this loader has no other
    # handle to the project root. If policy is missing (fresh index), skip
    # the filter — the trace builder would not have run yet either.
    pol = load_repo_policy(policy_path_for_index(index_dir))
    repo_root = Path(pol["repo_root"]) if pol and pol.get("repo_root") else None

    spec = None
    if repo_root is not None:
        try:
            import pathspec
            exclude_globs = effective_excludes(index_dir=index_dir, repo_root=repo_root)
            spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_globs)
        except Exception:
            spec = None

    dropped = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                node_id = d.get("node_id", "")
                if not node_id.startswith("file:"):
                    continue
                file_path = node_id[5:]
                if spec is not None and spec.match_file(file_path):
                    dropped += 1
                    continue
                entries[node_id] = {
                    "node_id": node_id,
                    "file_path": file_path,
                    "architecture_layer": _infer_layer_from_path(file_path),
                    "domain_tags": _infer_tags_from_path(file_path),
                    "epistemic_confidence": 0.5,  # Neutral — no real enrichment
                    "extended_summary": d.get("summary", ""),
                }
            except (json.JSONDecodeError, KeyError):
                continue
    if dropped:
        logger.debug(
            "role_projection._load_trace_nodes: filtered %d excluded-path entries", dropped
        )
    return entries


# ── Tag-to-audience heuristics (role affinity shortcut) ───────────────
# Maps common domain_tag values to the role IDs that "own" or heavily
# consume files with those tags.  Provides a small scoring bonus when a
# file's tags indicate it falls under the requesting role's domain.
# This bridges the gap between generic tag affinity and explicit ownership.

TAG_TO_AUDIENCE: Dict[str, List[str]] = {
    # Frontend / Design
    "ui": ["design", "design_engineer", "full_stack", "intern"],
    "frontend": ["design", "design_engineer", "full_stack"],
    "react": ["full_stack", "design", "design_engineer"],
    "vue": ["full_stack", "design", "design_engineer"],
    "svelte": ["full_stack", "design", "design_engineer"],
    "styling": ["design", "design_engineer"],
    "component": ["design", "design_engineer", "full_stack"],
    "design-system": ["design", "design_engineer"],
    "a11y": ["design", "design_engineer", "qa"],
    "animation": ["design", "design_engineer"],
    # Backend / Engineering
    "backend": ["engineering"],
    "core": ["engineering", "architect"],
    "engine": ["engineering", "architect"],
    "python": ["engineering"],
    "typescript": ["engineering", "full_stack"],
    "systems": ["engineering", "devops"],
    # API
    "api": ["engineering", "full_stack", "architect"],
    "graphql": ["engineering", "full_stack"],
    "grpc": ["engineering", "devops"],
    "rest": ["engineering", "full_stack"],
    # Data
    "database": ["data_engineer", "engineering"],
    "data": ["data_engineer"],
    "orm": ["data_engineer", "engineering"],
    "query": ["data_engineer"],
    "data-persistence": ["data_engineer", "engineering"],
    "schema": ["data_engineer", "engineering"],
    "analytics": ["data_engineer", "product"],
    # Security / Auth
    "auth": ["security", "devsecops", "engineering"],
    "security": ["security", "devsecops"],
    "token": ["security", "devsecops", "engineering"],
    "permission": ["security", "devsecops"],
    "encryption": ["security", "devsecops"],
    "compliance": ["security", "devsecops", "ceo"],
    # DevOps / Infra
    "infrastructure": ["devops", "devsecops"],
    "deploy": ["devops", "devsecops"],
    "docker": ["devops", "devsecops"],
    "ci-cd": ["devops", "devsecops"],
    "terraform": ["devops", "devsecops"],
    "config": ["devops", "engineering"],
    "monitoring": ["devops", "devsecops", "qa"],
    "pipeline": ["devops", "data_engineer"],
    # Testing / QA
    "test": ["qa", "engineering"],
    "testing": ["qa"],
    "coverage": ["qa"],
    "e2e": ["qa"],
    # Product / Business
    "monetization": ["product", "ceo"],
    "billing": ["product", "ceo"],
    "user-facing": ["product", "design"],
    "onboarding": ["product", "intern"],
    "feature-flag": ["product", "engineering"],
    # Documentation / Writing
    "documentation": ["writer", "intern"],
    "readme": ["writer", "intern"],
    "guide": ["writer", "intern"],
    # Architecture
    "architecture": ["architect", "cto", "ceo"],
    "integration": ["architect", "engineering"],
    "strategy": ["cto", "ceo", "product"],
    # CLI / Tooling
    "cli": ["engineering", "devops"],
    "tooling": ["engineering", "devops"],
}


def _compute_audience_bonus(
    domain_tags: List[str],
    role_id: str,
) -> float:
    """Compute a bonus score when file tags match the requesting role's domain.

    Returns 0.0-1.0 based on what fraction of the file's tags list this
    role as an audience member.
    """
    if not domain_tags:
        return 0.0
    matches = 0
    for tag in domain_tags:
        tag_lower = tag.lower().replace("_", "-")
        audience = TAG_TO_AUDIENCE.get(tag_lower, [])
        if role_id in audience:
            matches += 1
    return min(1.0, matches / max(1, len(domain_tags)))


# ── Scoring weights ──────────────────────────────────────────────────

# How much each scoring component contributes to the final relevance score.
SCORING_WEIGHTS = {
    "layer_match": 0.25,
    "tag_affinity": 0.30,
    "audience_bonus": 0.10,
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

    # 3. Audience bonus (does this file's domain "belong" to this role?)
    audience_score = _compute_audience_bonus(domain_tags, role.role_id)

    # 4. Centrality
    if max_degree > 0:
        # Normalize: top 30th percentile maps to 1.0
        norm = min(1.0, in_degree / max(1, max_degree * 0.3))
    else:
        norm = 0.0
    centrality_score = norm * role.centrality_weight

    # 5. Confidence
    confidence_score = max(0.0, min(1.0, epistemic_confidence))

    # Weighted composite
    relevance = (
        SCORING_WEIGHTS["layer_match"] * layer_score
        + SCORING_WEIGHTS["tag_affinity"] * tag_score
        + SCORING_WEIGHTS["audience_bonus"] * audience_score
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
    """Load module entries from trace_modules.jsonl.

    FIX-16-3 follow-up: rewrite legacy `Foo (Packages) #2` names to
    `Foo (Packages) [<idx>]` form on read so existing projects don't have
    to wait for a full pipeline rerun to see the cleaner module names.
    """
    from prep.core.cluster import strip_legacy_pound_n_suffix

    path = index_dir / "trace_modules.jsonl"
    modules: List[Dict[str, Any]] = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        m = json.loads(line)
                        name = m.get("name") or ""
                        if name:
                            m["name"] = strip_legacy_pound_n_suffix(
                                name, m.get("module_id") or "",
                            )
                        modules.append(m)
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

# ── Scoring implementations ──────────────────────────────────────────


def _try_rust_scoring(
    role: RoleVector,
    index_dir: Path,
) -> Optional[List[Tuple[str, Dict[str, Any], float]]]:
    """Try scoring via the Rust FFI bridge (Phase 64D).

    Returns scored list in the standard (file_path, entry_dict, score) format,
    or None if the Rust engine is unavailable or fails.
    """
    try:
        from prep_engine import score_files_for_role  # type: ignore[import-not-found]
    except ImportError:
        return None

    try:
        scored_raw = score_files_for_role(str(index_dir), role.to_json())
    except Exception as e:
        logger.warning("Rust role projection failed, falling back to Python: %s", e)
        return None

    if not scored_raw:
        return None

    # Convert Rust results back to the standard tuple format
    scored: List[Tuple[str, Dict[str, Any], float]] = []
    for item in scored_raw:
        entry = {
            "architecture_layer": item["architecture_layer"],
            "domain_tags": item["domain_tags"],
            "epistemic_confidence": item["epistemic_confidence"],
            "extended_summary": item["extended_summary"],
        }
        scored.append((item["file_path"], entry, item["score"]))

    logger.debug(
        "Role projection: Rust engine scored %d files for role '%s'",
        len(scored),
        role.role_id,
    )
    return scored


def _python_scoring(
    role: RoleVector,
    index_dir: Path,
) -> Optional[List[Tuple[str, Dict[str, Any], float]]]:
    """Pure Python scoring fallback.

    Loads epistemic JSONL, computes in-degrees, and scores all files.
    Returns scored list or None if no data is available.
    """
    epistemic = _load_epistemic_entries(index_dir)
    in_degrees = _compute_in_degrees(index_dir)

    if not epistemic:
        # Try structural fallback from trace_nodes.jsonl
        epistemic = _load_trace_nodes(index_dir)
        if not epistemic:
            return None
        logger.debug(
            "Role projection: using structural fallback (%d files from trace_nodes)",
            len(epistemic),
        )

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
    return scored


# ── Main projection function ─────────────────────────────────────────

def _format_pinned_block(
    pinned_concepts: List[Dict[str, Any]],
    budget: int,
) -> str:
    """Render a bounded 'Pinned for this role:' preamble.

    Each concept is rendered as ``- **Title**: truncated content``.
    Stops adding entries when the block would overflow ``budget`` chars.
    Returns ``""`` if ``pinned_concepts`` is empty or ``budget`` is too small.
    """
    if not pinned_concepts or budget < 80:
        return ""
    header = "[Pinned for this role]\n"
    lines: List[str] = []
    remaining = budget - len(header) - 2  # trailing blank line
    for c in pinned_concepts:
        title = str(c.get("title") or "").strip()
        content = str(c.get("content") or "").strip()
        if not title:
            continue
        # Reserve ~120 chars per concept for the preview; truncate harder if tight.
        max_preview = max(40, min(160, remaining // max(1, len(pinned_concepts))))
        preview = content.replace("\n", " ")
        if len(preview) > max_preview:
            preview = preview[: max_preview - 1].rstrip() + "…"
        entry = f"- **{title}**: {preview}\n" if preview else f"- **{title}**\n"
        if len(entry) > remaining:
            break
        lines.append(entry)
        remaining -= len(entry)
    if not lines:
        return ""
    return header + "".join(lines) + "\n"


def project_atlas_for_role(
    role: RoleVector,
    index_dir: Path,
    atlas_content: str = "",
    *,
    overrides: Optional[Any] = None,
    pinned_concepts: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Project the codebase atlas through a role-specific lens.

    Loads epistemic enrichments, scores every file against the role,
    and assembles a context string at the appropriate detail level
    within the role's char budget.

    Uses the Rust scoring engine (Phase 64D) when available for ~40x
    faster JSONL parsing + scoring.  Falls back to pure Python on
    ImportError or any Rust-side failure.

    Args:
        role: The resolved RoleVector.
        index_dir: Path to the project's index directory.
        atlas_content: The full atlas content (for identity/stack extraction).
        overrides: Optional ``RoleOverride`` (from ``role_overrides_store``)
            whose ``max_chars`` replaces the role's default budget. Typed
            loosely here so the projection layer doesn't pull the services
            layer into its import graph.
        pinned_concepts: Optional list of ``{"title": str, "content": str}``
            dicts to render as a preamble before the scored projection.
            Capped at 20% of the effective budget; honors a deterministic
            insertion order when callers sort by pinned_at.

    Returns:
        A role-filtered sub-atlas string.
    """
    # Apply max_chars override BEFORE any budget math.
    if overrides is not None:
        override_max = getattr(overrides, "max_chars", None)
        if isinstance(override_max, int) and override_max > 0:
            role = role.copy()
            role.max_chars = override_max

    # Reserve budget for the pinned block (up to 20% of effective budget).
    pin_block = ""
    if pinned_concepts:
        pin_budget = role.max_chars // 5
        pin_block = _format_pinned_block(pinned_concepts, pin_budget)
        if pin_block:
            # Shrink the role budget by the size of the pin block so the
            # final output stays under the effective max_chars. Floor at 200
            # so downstream assembly still has something to work with.
            role = role.copy()
            role.max_chars = max(200, role.max_chars - len(pin_block))

    modules = _load_modules(index_dir)

    # ── Try Rust fast path (Phase 64D) ───────────────────────────────
    scored = _try_rust_scoring(role, index_dir)

    # ── Python fallback ──────────────────────────────────────────────
    if scored is None:
        scored = _python_scoring(role, index_dir)

    if scored is None:
        # No data at all — return the full atlas with a role note
        if atlas_content:
            return pin_block + f"[Role: {role.display_name}]\n\n{atlas_content}"
        return pin_block + f"[Role: {role.display_name}] No codebase data available."

    # Drop Prep-generated / AI-tool instruction files from projection
    # results. These are already excluded at the walker level via
    # repo_profile.DEFAULT_EXCLUDE_FILE_NAMES, but older index builds can
    # still contain them — filter here so stale indexes don't leak
    # meta-content into the role atlas. Cheap post-scoring filter.
    from prep.core.repo_profile import DEFAULT_EXCLUDE_FILE_NAMES
    scored = [
        (fp, entry, score) for fp, entry, score in scored
        if Path(fp).name not in DEFAULT_EXCLUDE_FILE_NAMES
    ]

    # Extract identity/stack from atlas
    identity = _extract_identity(atlas_content)
    stack = _extract_stack(atlas_content)

    # Route to detail-level-appropriate assembly
    if role.detail_level < 0.3:
        body = _assemble_executive(role, identity, stack, modules, scored)
    elif role.detail_level <= 0.7:
        body = _assemble_manager(role, identity, stack, modules, scored)
    else:
        body = _assemble_practitioner(role, identity, stack, modules, scored)
    return pin_block + body


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
