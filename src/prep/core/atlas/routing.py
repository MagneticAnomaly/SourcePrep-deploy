"""
Atlas routing — budget computation, segment discovery, and query routing.

Contains: compute_atlas_budget, compute_segments, build_routing_descriptors,
route_query, and all segment helper functions.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .models import Segment, SegmentDescriptor

logger = logging.getLogger(__name__)


# ── Adaptive Budget ──────────────────────────────────────────────────

MIN_FILES_FOR_ATLAS = 2
MIN_ATLAS_CHARS = 1200
MAX_ATLAS_CHARS = 4000


def compute_atlas_budget(file_count: int) -> int:
    """Compute adaptive atlas budget based on project size.

    Tiered formula:
      2-50 files    → 1200 chars (minimum meaningful atlas)
      50-200 files  → 1200 + (files - 50) * 6   (linear ramp)
      200-1000 files → 2100 + (files - 200) * 1.5 (slower ramp)
      1000+ files   → 3300 + (files - 1000) * 0.35 (diminishing)
    Capped at MAX_ATLAS_CHARS (4000).
    Projects under 2 files get no atlas (returns 0).
    """
    if file_count < MIN_FILES_FOR_ATLAS:
        return 0
    if file_count <= 50:
        return MIN_ATLAS_CHARS
    if file_count <= 200:
        return min(MAX_ATLAS_CHARS, int(1200 + (file_count - 50) * 6))
    if file_count <= 1000:
        return min(MAX_ATLAS_CHARS, int(2100 + (file_count - 200) * 1.5))
    return min(MAX_ATLAS_CHARS, int(3300 + (file_count - 1000) * 0.35))


# ── Segment Discovery ───────────────────────────────────────────────

MAX_SEGMENTS = 15
MIN_SEGMENT_FILES = 10
ROOT_ATLAS_MIN_CHARS = 1200
ROOT_ATLAS_MAX_CHARS = 2500
SEGMENT_ATLAS_MIN_CHARS = 800
SEGMENT_ATLAS_MAX_CHARS = 1500

# ── Routing Configuration ──────────────────────────────────────────────
MIN_FILES_FOR_ROUTING = 20
MIN_MODULES_FOR_ROUTING = 2
ROUTING_MIN_SCORE = 0.25          # Minimum cosine sim for segment selection
ROUTING_MAX_SEGMENTS = 3          # Max segments selected per query
ROUTING_SEGMENT_BOOST = 0.12     # Additive score boost for in-segment files


def compute_root_atlas_budget(file_count: int) -> int:
    """Compute adaptive root atlas budget.

    Root atlas gets ~55% of the full atlas budget, clamped to
    [ROOT_ATLAS_MIN_CHARS, ROOT_ATLAS_MAX_CHARS]. This ensures the root
    is substantial enough for dashboard display while leaving room for
    segment atlases at query time.
    """
    full_budget = compute_atlas_budget(file_count)
    if full_budget <= 0:
        return 0
    root = int(full_budget * 0.55)
    return max(ROOT_ATLAS_MIN_CHARS, min(ROOT_ATLAS_MAX_CHARS, root))

# Directories that signal "go one level deeper" for grouping
_DEEP_DIRS = frozenset({
    "src", "lib", "pkg", "packages", "apps", "services", "modules",
    "cmd", "internal", "crates", "components", "plugins", "tools",
})

# Files that mark workspace boundaries
_WORKSPACE_MARKERS = {
    "package.json": "npm",
    "Cargo.toml": "cargo",
    "go.mod": "go",
    "pyproject.toml": "python",
    "setup.py": "python",
    "pom.xml": "maven",
    "build.gradle": "gradle",
}


def compute_segments(
    index_dir: Path,
    project_root: Optional[Path] = None,
    extra_deep_dirs: Optional[Iterable[str]] = None,
) -> List[Segment]:
    """Compute directory-based segments from indexed file paths.

    Strategy:
    1. Scan all file paths from trace_nodes.jsonl
    2. Detect workspace boundaries if project_root is available
    3. Group by directory (adaptive depth: deeper under src/, packages/,
       etc., plus any project-config ``atlas_deep_dirs``)
    4. Merge tiny groups (<MIN_SEGMENT_FILES) into nearest sibling or parent
    5. Cap at MAX_SEGMENTS — merge smallest pairs if over budget
    6. Annotate each segment with its modules' domain tags

    Returns list of Segment objects, sorted by file count descending.
    """
    # Step 1: Load all file paths
    file_paths = _load_file_paths(index_dir)
    if not file_paths:
        return []

    # Step 2: Try workspace-based segmentation first
    workspaces: Optional[Dict[str, List[str]]] = None
    if project_root:
        workspaces = _detect_workspaces(project_root, file_paths)

    # Step 3: Group by directory
    if workspaces and len(workspaces) >= 2:
        dir_groups = workspaces
    else:
        dir_groups = _group_by_directory(file_paths, extra_deep_dirs=extra_deep_dirs)

    # Step 4: Merge tiny groups
    dir_groups = _merge_tiny_groups(dir_groups, MIN_SEGMENT_FILES)

    # Step 5: Cap at MAX_SEGMENTS
    while len(dir_groups) > MAX_SEGMENTS:
        dir_groups = _merge_smallest_pair(dir_groups)

    # Step 6: Build Segment objects with module annotations
    modules = _load_modules_for_segments(index_dir)
    segments = _build_segments(dir_groups, modules)

    return sorted(segments, key=lambda s: -s.file_count)


def _load_file_paths(index_dir: Path) -> List[str]:
    """Load all unique file paths from trace_nodes.jsonl."""
    seen: Set[str] = set()
    paths: List[str] = []
    nodes_path = index_dir / "trace_nodes.jsonl"
    if not nodes_path.exists():
        return paths
    try:
        with open(nodes_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    fp = d.get("file_path", "")
                    if fp and fp not in seen:
                        seen.add(fp)
                        paths.append(fp)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return paths


def _detect_workspaces(
    project_root: Path,
    file_paths: List[str],
) -> Optional[Dict[str, List[str]]]:
    """Detect monorepo workspace boundaries and group files by workspace.

    Checks for:
    - package.json with "workspaces" field (npm/yarn/pnpm)
    - Cargo.toml with [workspace] members
    - turbo.json or pnpm-workspace.yaml packages
    - go.work modules

    Returns dict of {workspace_dir: [file_paths]} or None if not a monorepo.
    """
    import glob as glob_mod

    # Check npm/yarn/pnpm workspaces
    pkg_json = project_root / "package.json"
    if pkg_json.exists():
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                pkg = json.load(f)
            ws_globs = pkg.get("workspaces", [])
            # workspaces can be {"packages": [...]} or [...]
            if isinstance(ws_globs, dict):
                ws_globs = ws_globs.get("packages", [])
            if isinstance(ws_globs, list) and ws_globs:
                ws_dirs: List[str] = []
                for pattern in ws_globs:
                    # Resolve glob against project root
                    matches = sorted(glob_mod.glob(
                        str(project_root / pattern),
                    ))
                    for m in matches:
                        mp = Path(m)
                        if mp.is_dir():
                            ws_dirs.append(
                                str(mp.relative_to(project_root))
                            )
                if len(ws_dirs) >= 2:
                    return _assign_files_to_dirs(ws_dirs, file_paths)
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    # Check Cargo.toml workspace members
    cargo_toml = project_root / "Cargo.toml"
    if cargo_toml.exists():
        try:
            content = cargo_toml.read_text(encoding="utf-8")
            if "[workspace]" in content:
                members = _parse_cargo_workspace_members(content, project_root)
                if len(members) >= 2:
                    return _assign_files_to_dirs(members, file_paths)
        except OSError:
            pass

    return None


def _parse_cargo_workspace_members(
    content: str, project_root: Path,
) -> List[str]:
    """Extract workspace member directories from Cargo.toml content."""
    import re
    import glob as glob_mod

    members: List[str] = []
    # Simple regex to find members = ["crate1", "crate2/*"]
    match = re.search(r'members\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if not match:
        return members
    raw = match.group(1)
    for item in re.findall(r'"([^"]+)"', raw):
        matches = sorted(glob_mod.glob(str(project_root / item)))
        for m in matches:
            mp = Path(m)
            if mp.is_dir():
                members.append(str(mp.relative_to(project_root)))
    return members


def _assign_files_to_dirs(
    ws_dirs: List[str],
    file_paths: List[str],
) -> Dict[str, List[str]]:
    """Assign file paths to workspace directories. Unmatched go to '_root'."""
    groups: Dict[str, List[str]] = {d: [] for d in ws_dirs}
    groups["_root"] = []

    # Sort workspace dirs longest-first for greedy matching
    sorted_dirs = sorted(ws_dirs, key=len, reverse=True)

    for fp in file_paths:
        matched = False
        for wd in sorted_dirs:
            if fp.startswith(wd + "/") or fp == wd:
                groups[wd].append(fp)
                matched = True
                break
        if not matched:
            groups["_root"].append(fp)

    # Remove empty groups
    return {k: v for k, v in groups.items() if v}


def _group_by_directory(
    file_paths: List[str],
    *,
    extra_deep_dirs: Optional[Iterable[str]] = None,
) -> Dict[str, List[str]]:
    """Group file paths by directory with adaptive depth.

    Uses depth 2 under known deep directories (src/, packages/, etc.) and
    any project-config ``atlas_deep_dirs`` (e.g. ``knowledge`` → per-platform
    segments ``knowledge/linux``, ``knowledge/macos``), depth 1 otherwise.
    """
    groups: Dict[str, List[str]] = defaultdict(list)
    # T-S2.4: union the built-in deep dirs with the project-config extras
    # (case-insensitive). Default (no config) → byte-identical to before.
    deep_dirs: Set[str] = set(_DEEP_DIRS)
    if extra_deep_dirs:
        deep_dirs |= {str(d).lower().strip("/") for d in extra_deep_dirs if d}

    for fp in file_paths:
        parts = fp.split("/")
        if len(parts) == 1:
            # Root-level file
            groups["_root"].append(fp)
        elif parts[0].lower() in deep_dirs and len(parts) >= 3:
            # Deep directory: use depth 2 (e.g. src/prep/, packages/ui/,
            # knowledge/linux/)
            key = f"{parts[0]}/{parts[1]}"
            groups[key].append(fp)
        else:
            # Shallow: use depth 1
            groups[parts[0]].append(fp)

    return dict(groups)


def _merge_tiny_groups(
    groups: Dict[str, List[str]],
    min_files: int,
) -> Dict[str, List[str]]:
    """Merge groups with fewer than min_files into their parent or nearest sibling."""
    large: Dict[str, List[str]] = {}
    small: Dict[str, List[str]] = {}

    for key, files in groups.items():
        if len(files) >= min_files:
            large[key] = files
        else:
            small[key] = files

    if not large:
        # All groups are small — merge everything into one "_root" group
        merged: List[str] = []
        for files in groups.values():
            merged.extend(files)
        return {"_root": merged} if merged else {}

    for key, files in small.items():
        # Try to find parent directory match
        parent = key.rsplit("/", 1)[0] if "/" in key else "_root"
        if parent in large:
            large[parent].extend(files)
        else:
            # Merge into the largest group
            biggest = max(large, key=lambda k: len(large[k]))
            large[biggest].extend(files)

    return large


def _merge_smallest_pair(
    groups: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """Merge the two smallest groups together."""
    if len(groups) <= 1:
        return groups

    sorted_keys = sorted(groups.keys(), key=lambda k: len(groups[k]))
    smallest = sorted_keys[0]
    second = sorted_keys[1]

    # Merge into the one with the closer directory path
    merged_key = second  # keep the larger one's name
    groups[merged_key] = groups[second] + groups[smallest]
    del groups[smallest]
    return groups


def _load_modules_for_segments(
    index_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    """Load modules keyed by member file path for segment annotation."""
    file_to_module: Dict[str, Dict[str, Any]] = {}
    modules_path = index_dir / "trace_modules.jsonl"
    if not modules_path.exists():
        return file_to_module
    try:
        with open(modules_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = json.loads(line)
                    for fp in m.get("member_files", []):
                        file_to_module[fp] = m
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return file_to_module


def _build_segments(
    dir_groups: Dict[str, List[str]],
    file_to_module: Dict[str, Dict[str, Any]],
) -> List[Segment]:
    """Build Segment objects from directory groups, annotated with module data."""
    segments: List[Segment] = []
    seen_module_ids: Dict[str, Set[str]] = defaultdict(set)

    for dir_path, files in dir_groups.items():
        seg_id = dir_path.replace("/", "-").replace(".", "").strip("-") or "root"

        # Collect module IDs and domain tags for files in this segment
        module_ids: Set[str] = set()
        domain_tags: Counter = Counter()

        for fp in files:
            mod = file_to_module.get(fp)
            if mod:
                mid = mod.get("module_id", "")
                if mid:
                    module_ids.add(mid)
                for tag in mod.get("domain_tags", []):
                    domain_tags[tag] += 1

        # Human-readable name: last directory component, title-cased
        name_parts = dir_path.rstrip("/").split("/")
        name = name_parts[-1].replace("-", " ").replace("_", " ").title()
        if dir_path == "_root":
            name = "Project Root"

        segments.append(Segment(
            id=seg_id,
            name=name,
            dir_path=dir_path,
            file_paths=sorted(files),
            module_ids=sorted(module_ids),
            domain_tags=[t for t, _ in domain_tags.most_common(10)],
            file_count=len(files),
        ))

    return segments


# ── Routing Descriptor Builder ───────────────────────────────────────

def build_routing_descriptors(
    segments: List[Segment],
    index_dir: Path,
) -> List[SegmentDescriptor]:
    """Build routing descriptors from existing pipeline data (no LLM).

    For each segment, constructs:
      - COVERS: aggregated domain tags + module names as routing vocabulary
      - KEY FILES: top files by in-degree within the segment
      - BOUNDARIES: cross-segment edge descriptions

    Returns list of SegmentDescriptor objects.
    """
    if not segments:
        return []

    # Load edges for hub detection and boundary computation
    in_degree: Counter = Counter()
    edges: List[Tuple[str, str]] = []  # (source_path, target_path)

    for edge_file in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
        edge_path = index_dir / edge_file
        if not edge_path.exists():
            continue
        try:
            with open(edge_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        src = d.get("source", "").replace("file:", "", 1)
                        tgt = d.get("target", "").replace("file:", "", 1)
                        if src and tgt:
                            in_degree[tgt] += 1
                            edges.append((src, tgt))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    # Load module data for enriched domain vocabulary
    file_to_module: Dict[str, Dict[str, Any]] = {}
    modules_path = index_dir / "trace_modules.jsonl"
    if modules_path.exists():
        try:
            with open(modules_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        m = json.loads(line)
                        for fp in m.get("member_files", []):
                            file_to_module[fp] = m
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    # Load epistemic domain tags per file
    file_domains: Dict[str, List[str]] = {}
    epi_path = index_dir / "trace_epistemic.jsonl"
    if epi_path.exists():
        try:
            with open(epi_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        nid = d.get("node_id", "")
                        fp = nid.replace("file:", "", 1) if nid.startswith("file:") else ""
                        if fp:
                            file_domains[fp] = d.get("domain_tags", [])
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    # Build file→segment index for boundary detection
    file_to_seg: Dict[str, str] = {}
    for seg in segments:
        for fp in seg.file_paths:
            file_to_seg[fp] = seg.id

    descriptors: List[SegmentDescriptor] = []

    for segment in segments:
        seg_file_set = set(segment.file_paths)

        # KEY FILES: top files by in-degree within segment
        seg_degrees = [(fp, in_degree.get(fp, 0)) for fp in segment.file_paths]
        seg_degrees.sort(key=lambda x: -x[1])
        key_files = [fp for fp, deg in seg_degrees[:8] if deg > 0]
        if not key_files:
            key_files = sorted(segment.file_paths, key=len)[:6]

        # COVERS: aggregate domain tags + module names for routing vocabulary
        covers_parts: List[str] = []
        covers_parts.append(f"Segment: {segment.dir_path} ({segment.name})")

        all_tags: Counter = Counter()
        for fp in segment.file_paths:
            for tag in file_domains.get(fp, []):
                all_tags[tag] += 1
        for tag in segment.domain_tags:
            all_tags[tag] += 1

        if all_tags:
            tag_str = " ".join(
                t.replace("_", " ").replace("-", " ")
                for t, _ in all_tags.most_common(20)
            )
            covers_parts.append(f"Covers: {tag_str}")

        seg_module_names: Set[str] = set()
        for fp in segment.file_paths:
            m = file_to_module.get(fp)
            if m:
                seg_module_names.add(m.get("name", ""))
        if seg_module_names:
            covers_parts.append(
                f"Modules: {' '.join(n for n in sorted(seg_module_names) if n)}"
            )

        if key_files:
            file_names = " ".join(Path(fp).stem for fp in key_files)
            covers_parts.append(f"Key files: {file_names}")

        covers = "\n".join(covers_parts)

        # BOUNDARIES: cross-segment edges
        dep_counts: Counter = Counter()
        for src, tgt in edges:
            if src in seg_file_set and tgt not in seg_file_set:
                other_seg = file_to_seg.get(tgt, "")
                if other_seg:
                    dep_counts[other_seg] += 1
            elif tgt in seg_file_set and src not in seg_file_set:
                other_seg = file_to_seg.get(src, "")
                if other_seg:
                    dep_counts[other_seg] += 1

        boundary_strs = [
            f"\u2192 {seg_id} ({count} edges)"
            for seg_id, count in dep_counts.most_common(5)
        ]

        descriptors.append(SegmentDescriptor(
            segment_id=segment.id,
            dir_path=segment.dir_path,
            name=segment.name,
            covers=covers,
            key_files=key_files,
            boundaries=boundary_strs,
            file_paths=segment.file_paths,
            file_count=segment.file_count,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ))

    return descriptors


def route_query(
    query_vector: "np.ndarray",
    descriptor_embeddings: "np.ndarray",
    descriptors: List[SegmentDescriptor],
    min_score: float = ROUTING_MIN_SCORE,
    max_segments: int = ROUTING_MAX_SEGMENTS,
) -> List[Tuple[SegmentDescriptor, float]]:
    """Route a query to relevant segments via cosine similarity.

    Args:
        query_vector: Pre-computed query embedding (1D).
        descriptor_embeddings: (N, dim) matrix of descriptor embeddings.
        descriptors: Corresponding SegmentDescriptor objects.
        min_score: Minimum cosine sim for segment selection.
        max_segments: Maximum segments to return.

    Returns:
        List of (descriptor, score) tuples, sorted by score descending.
    """
    import numpy as np

    if descriptor_embeddings is None or len(descriptors) == 0:
        return []
    if descriptor_embeddings.shape[0] != len(descriptors):
        logger.warning(
            "Descriptor count (%d) != embedding count (%d)",
            len(descriptors), descriptor_embeddings.shape[0],
        )
        return []

    qn = np.linalg.norm(query_vector)
    if qn == 0.0:
        return []

    # Cosine similarity: query vs each descriptor embedding
    norms = np.linalg.norm(descriptor_embeddings, axis=1)
    norms = np.where(norms == 0.0, 1e-8, norms)
    sims = (descriptor_embeddings @ query_vector) / (norms * qn)

    # Select segments above threshold, sorted by score
    results: List[Tuple[SegmentDescriptor, float]] = []
    indices = np.argsort(sims)[::-1]
    for idx in indices[:max_segments]:
        score = float(sims[idx])
        if score < min_score:
            break
        results.append((descriptors[int(idx)], score))

    return results
