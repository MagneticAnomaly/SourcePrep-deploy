"""
Roadmap contender mining from Prep graph data — Phase 59D.

Reads existing pipeline outputs (audit findings, orphan modules, hotspots,
and planning-intent keywords) to surface roadmap candidates.

This runs AFTER the atlas stage and reads already-computed graph data —
it doesn't re-analyze files. Think of it as a "roadmap lens" on existing data.

Usage:
    from prep.core.roadmap_miner import mine_roadmap_contenders
    nodes = mine_roadmap_contenders(index_dir, project_root)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from prep.core.goalposts_models import RoadmapNode

logger = logging.getLogger(__name__)

# ── Roadmap-Intent Keywords ──────────────────────────────────────────

ROADMAP_KEYWORDS = [
    "roadmap", "milestone", "planned", "upcoming", "future work",
    "phase", "sprint", "backlog", "next steps", "deprecat",
    "migration", "v2", "v3", "rewrite", "refactor plan",
    "breaking change", "rfc", "proposal", "design doc",
]

# File patterns most likely to contain planning info
PLANNING_FILE_PATTERNS = [
    "README*", "CHANGELOG*", "ROADMAP*", "TODO*",
    "CONTRIBUTING*", "MIGRATION*", "UPGRADE*",
    "docs/**/README*", "docs/**/PLAN*", "docs/**/DESIGN*",
    "*.md",  # All markdown in docs directories
]

# ── Contender ID Generation ──────────────────────────────────────────

def _make_miner_id(source: str, key: str) -> str:
    """Deterministic ID for a mined roadmap contender."""
    h = hashlib.sha256(f"mine:{source}:{key}".encode()).hexdigest()[:8]
    return f"RM-{h}"


# ── Audit Finding Mining ─────────────────────────────────────────────

def _mine_audit_findings(index_dir: Path) -> List[RoadmapNode]:
    """Read audit findings and convert high-severity ones to roadmap nodes.

    Reads from the Prep audit cache if available.
    """
    nodes: List[RoadmapNode] = []

    # Try reading cached audit findings
    audit_cache = index_dir / "audit_cache.json"
    if not audit_cache.exists():
        return nodes

    try:
        data = json.loads(audit_cache.read_text(encoding="utf-8"))
        findings = data.get("findings", [])

        for f in findings:
            severity = f.get("severity", "info")
            if severity not in ("warning", "error", "critical"):
                continue  # Only surface significant findings

            finding_id = f.get("id", "")
            title = f.get("title", f.get("message", "Audit finding"))
            category_map = {
                "size": "architecture",
                "architecture": "architecture",
                "quality": "tech_debt",
                "naming": "tech_debt",
                "testing": "feature",
                "coverage": "feature",
            }
            category = category_map.get(f.get("category", ""), "architecture")
            priority = "P1" if severity in ("error", "critical") else "P2"

            nodes.append(RoadmapNode(
                id=_make_miner_id("audit", finding_id),
                title=f"Fix: {title}",
                description=f.get("description", "")[:500],
                tier="proposed",
                source="ai_proposed",
                source_ref=f"audit:{finding_id}",
                category=category,
                priority=priority,
                state="proposed",
            ))

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to read audit cache: %s", e)

    return nodes


# ── Orphan Module Mining ─────────────────────────────────────────────

def _mine_orphan_modules(index_dir: Path) -> List[RoadmapNode]:
    """Identify modules with no imports in/out from graph data.

    These are refactoring candidates — either dead code or missing integrations.
    """
    nodes: List[RoadmapNode] = []

    # Read module data from atlas or cluster output
    modules_file = index_dir / "modules.json"
    if not modules_file.exists():
        return nodes

    try:
        data = json.loads(modules_file.read_text(encoding="utf-8"))
        modules = data if isinstance(data, list) else data.get("modules", [])

        for mod in modules:
            name = mod.get("name", "")
            files = mod.get("files", [])
            imports_in = mod.get("imports_in", 0)
            imports_out = mod.get("imports_out", 0)

            # Orphan = no external imports in either direction
            if imports_in == 0 and imports_out == 0 and len(files) > 1:
                nodes.append(RoadmapNode(
                    id=_make_miner_id("orphan", name),
                    title=f"Refactor: orphan module '{name}'",
                    description=f"Module '{name}' has {len(files)} files but no imports in/out. Consider integrating or removing.",
                    tier="proposed",
                    source="ai_proposed",
                    source_ref=f"module:{name}",
                    category="architecture",
                    priority="P3",
                    state="proposed",
                ))

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to read modules data: %s", e)

    return nodes


# ── Hotspot Mining ───────────────────────────────────────────────────

def _mine_hotspots(index_dir: Path) -> List[RoadmapNode]:
    """Identify high-complexity files from graph metadata.

    Files with very high import counts or line counts are decomposition targets.
    """
    nodes: List[RoadmapNode] = []

    # Read trace/graph data
    graph_file = index_dir / "trace" / "graph.json"
    if not graph_file.exists():
        return nodes

    try:
        data = json.loads(graph_file.read_text(encoding="utf-8"))
        graph_nodes = data.get("nodes", {})

        for node_id, node_data in graph_nodes.items():
            if not isinstance(node_data, dict):
                continue

            kind = node_data.get("kind", "")
            if kind != "file":
                continue

            loc = node_data.get("loc", 0)
            imports = len(node_data.get("imports", []))

            # Flag files with >500 LoC or >15 imports as hotspots
            if loc > 500 or imports > 15:
                label = node_data.get("label", node_id)
                reason = []
                if loc > 500:
                    reason.append(f"{loc} LoC")
                if imports > 15:
                    reason.append(f"{imports} imports")

                nodes.append(RoadmapNode(
                    id=_make_miner_id("hotspot", node_id),
                    title=f"Decompose: {label}",
                    description=f"High-complexity file ({', '.join(reason)}). Consider splitting into smaller modules.",
                    tier="proposed",
                    source="ai_proposed",
                    source_ref=f"file:{node_id}",
                    category="architecture",
                    priority="P2",
                    state="proposed",
                ))

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to read graph data: %s", e)

    return nodes


# ── Keyword Mining ───────────────────────────────────────────────────

def _mine_roadmap_keywords(
    project_root: Path,
    *,
    max_results: int = 20,
) -> List[RoadmapNode]:
    """Scan docs/README files for planning-intent keywords.

    Uses ripgrep for speed, falls back to Python if rg is not available.
    """
    nodes: List[RoadmapNode] = []

    # Build regex pattern from keywords
    pattern = "|".join(re.escape(kw) for kw in ROADMAP_KEYWORDS)

    # Target directories most likely to have planning docs
    search_dirs = []
    for d in ["docs", "doc", "."]:
        candidate = project_root / d
        if candidate.is_dir():
            search_dirs.append(str(candidate))
    if not search_dirs:
        return nodes

    # Build --glob exclusion flags for vendor/dependency directories
    try:
        from prep.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES
        skip_dirs = DEFAULT_EXCLUDE_DIR_NAMES
    except ImportError:
        skip_dirs = {
            "node_modules", "vendor", "Pods", "bundle", "bower_components",
            ".git", ".runprep", "DerivedData", "Carthage",
        }
    glob_flags: list[str] = []
    for d in sorted(skip_dirs):
        glob_flags.extend(["--glob", f"!{d}/**"])
    glob_flags.extend(["--glob", "!.*/**"])

    # Try ripgrep first
    try:
        cmd = [
            "rg", "--ignore-case", "--no-heading", "--line-number",
            "--type", "md",  # Only markdown files
            "--max-count", "1",  # One match per file (we just need to identify the file)
            *glob_flags,
            "-e", pattern,
        ] + search_dirs

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            cwd=str(project_root),
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue

                # Parse rg output: file:line:content
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue

                file_path = parts[0]
                text = parts[2].strip()

                # Extract the most specific keyword match
                matched_kw = ""
                for kw in ROADMAP_KEYWORDS:
                    if kw.lower() in text.lower():
                        matched_kw = kw
                        break

                # Make a descriptive title
                rel_path = file_path
                try:
                    rel_path = str(Path(file_path).relative_to(project_root))
                except ValueError:
                    pass

                node_id = _make_miner_id("keyword", f"{rel_path}:{matched_kw}")
                nodes.append(RoadmapNode(
                    id=node_id,
                    title=f"Review: {matched_kw} in {Path(rel_path).name}",
                    description=f"Found planning keyword '{matched_kw}' in {rel_path}: \"{text[:200]}\"",
                    tier="proposed",
                    source="ai_proposed",
                    source_ref=f"file:{rel_path}",
                    category="product",
                    priority="P3",
                    state="proposed",
                ))

                if len(nodes) >= max_results:
                    break

    except FileNotFoundError:
        logger.debug("ripgrep not found, skipping keyword mining")
    except subprocess.TimeoutExpired:
        logger.warning("Keyword scan timed out")
    except Exception as e:
        logger.warning("Keyword scan error: %s", e)

    return nodes


# ── Main Entry Point ─────────────────────────────────────────────────

def mine_roadmap_contenders(
    index_dir: Path,
    project_root: Path,
    *,
    existing_ids: Optional[Set[str]] = None,
    max_results: int = 50,
) -> List[RoadmapNode]:
    """Mine the Prep graph and codebase for roadmap contenders.

    Combines 4 mining sources:
    1. Audit findings (severity >= warning)
    2. Orphan modules (no imports in/out)
    3. Hotspot files (high LoC or import count)
    4. Roadmap keywords in docs/READMEs

    Args:
        index_dir: Prep index directory (contains graph, audit, module data).
        project_root: Project source directory.
        existing_ids: Node IDs to skip (dedup against existing roadmap).
        max_results: Maximum contenders to return.

    Returns:
        List of RoadmapNode entries with source="ai_proposed" and tier="proposed".
    """
    existing = existing_ids or set()
    all_nodes: List[RoadmapNode] = []

    # Mine each source
    sources = [
        ("audit", _mine_audit_findings(index_dir)),
        ("orphans", _mine_orphan_modules(index_dir)),
        ("hotspots", _mine_hotspots(index_dir)),
        ("keywords", _mine_roadmap_keywords(project_root)),
    ]

    for source_name, source_nodes in sources:
        for node in source_nodes:
            if node.id not in existing and len(all_nodes) < max_results:
                all_nodes.append(node)
                existing.add(node.id)

        logger.info(
            "Roadmap miner [%s]: found %d contenders",
            source_name, len(source_nodes),
        )

    logger.info(
        "Roadmap miner: total %d contenders (deduped) from %s",
        len(all_nodes), project_root,
    )
    return all_nodes
