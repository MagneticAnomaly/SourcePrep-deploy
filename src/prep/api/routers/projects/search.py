"""
Project search and context endpoints — the primary value delivery path.

Contains: search, context, and all context assembly helpers
(observations, atlas prepend, LOD compression, ambient context).
"""
from __future__ import annotations

import json as _json
import logging
import re as _re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter

from prep.api.envelope import ApiException, ok
from prep.core.feature_gate import require_feature, FeatureGateError
from prep.core.project_registry import project_index_dir
from prep.core import NoopCompressor
from prep.core.query import preprocess_query as _preprocess_query

from .helpers import _srv, _get_project_globs
from .models import SearchRequest, ContextRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


@router.post("/projects/{project_id}/search")
def search_project(project_id: str, req: SearchRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)
    if not req.query.strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    idx = _srv()._get_project_layered_index(proj)
    if not idx.is_loaded():
        raise ApiException(
            status_code=409,
            code="INDEX_NOT_BUILT",
            message="Index has not been built yet",
            hint="Run a build first.",
        )

    results = idx.search(
        req.query, k=req.k, min_score=req.min_score,
        score_drop_ratio=req.score_drop_ratio, mmr_lambda=req.mmr_lambda,
        exclude_paths=req.exclude_paths or None,
    )

    # ── Phase 120: Named scope filtering (replaces Phase 67 role auto-mask) ──
    from prep.core.scope_resolver import resolve_mask, path_matches_any_scope
    _resolution = resolve_mask(project_id, scope=req.scope, role=req.role)
    _agent_mask = _resolution.mask

    out: List[Dict[str, Any]] = []
    for r in results:
        d = r.doc
        source_path = str(d.get("source_path") or "")

        if _agent_mask is not None and source_path and not path_matches_any_scope(source_path, _agent_mask):
            continue

        content = str(d.get("content") or "")
        span = d.get("span")
        if not isinstance(span, dict) or "start_line" not in span or "end_line" not in span:
            span = {"start_line": 1, "end_line": 1}
        out.append(
            {
                "chunk_id": str(d.get("id") or ""),
                "source_path": source_path,
                "span": span,
                "preview": content[:200],
                "score": float(r.score),
            }
        )

    envelope_extras: Dict[str, Any] = {
        "applied_scope": _resolution.applied_scope,
        "applied_role": req.role,
    }
    if _resolution.warning:
        envelope_extras["scope_warning"] = _resolution.warning
    return ok({"results": out, **envelope_extras})


# ── Phase 39: Observation injection ──────────────────────────────
# Append relevant observations as a [session-memory] section at the
# end of the assembled context.  Stale observations are included but
# marked so the agent knows to re-evaluate.
_OBS_MAX_CHARS = 500
_OBS_MAX_COUNT = 3


def _inject_observations(
    context_str: str,
    project_id: str,
    query: str,
) -> tuple:
    """Append relevant observations to context string.

    Returns (new_context_str, obs_meta_dict_or_None).
    """
    try:
        from prep.services.observation_store import observation_store
        observations = observation_store.get_for_query(
            project_id, query, limit=_OBS_MAX_COUNT, include_stale=True,
        )
        if not observations:
            return context_str, None

        lines: list = []
        chars = 0
        included = 0
        stale_count = 0
        for obs in observations:
            prefix = "[STALE] " if obs.stale else ""
            cat = f"({obs.category}) " if obs.category != "note" else ""
            file_ref = f" [{obs.file_path}]" if obs.file_path else ""
            line = f"- {prefix}{cat}{obs.content}{file_ref}"
            if chars + len(line) > _OBS_MAX_CHARS:
                break
            lines.append(line)
            chars += len(line)
            included += 1
            if obs.stale:
                stale_count += 1

        if not lines:
            return context_str, None

        section = "\n\n---\n\n[session-memory]\n" + "\n".join(lines)
        meta = {"observations_injected": included, "stale": stale_count}
        return context_str + section, meta

    except Exception:
        return context_str, None


def _prepend_atlas(
    context_str: str,
    project_id: str,
    file_count: int,
    source_paths: Optional[List[str]] = None,
) -> tuple:
    """Prepend the Codebase Atlas to context if available.

    If segmented atlases exist and source_paths are provided, injects
    root atlas + relevant segment atlases. Otherwise falls back to the
    single atlas.

    Returns (new_context_str, atlas_meta_dict_or_None, atlas_chars_used).
    """
    from prep.core.atlas import CodebaseAtlas, compute_atlas_budget
    from prep.core.project_registry import project_index_dir
    from prep.services.project_helpers import require_project

    budget = compute_atlas_budget(file_count)
    if budget <= 0:
        return context_str, None, 0

    try:
        project = require_project(project_id)
        idx_dir = project_index_dir(project)
        atlas = CodebaseAtlas(idx_dir)
        doc = atlas.load()
    except Exception:
        return context_str, None, 0

    if doc is None or not doc.content:
        return context_str, None, 0

    # Try segmented atlas: root + relevant segments
    segments_used: List[str] = []
    if source_paths and atlas.has_segments():
        seg_docs = atlas.select_segments(source_paths, max_segments=2)
        if seg_docs:
            # Build: root atlas (truncated to fit) + segment atlases
            root_budget = min(len(doc.content), budget // 2)
            remaining = budget - root_budget
            blocks: List[str] = [f"[ATLAS | Codebase Map]\n{doc.content[:root_budget]}"]

            for seg_doc in seg_docs:
                seg_budget = min(len(seg_doc.content), remaining)
                if seg_budget < 100:
                    break
                blocks.append(f"[ATLAS | {seg_doc.segment_name}]\n{seg_doc.content[:seg_budget]}")
                remaining -= seg_budget
                segments_used.append(seg_doc.segment_id)

            atlas_block = "\n\n".join(blocks)
            atlas_chars = len(atlas_block)

            if context_str:
                new_context = atlas_block + "\n\n---\n\n" + context_str
            else:
                new_context = atlas_block

            atlas_meta = {
                "included": True,
                "chars": atlas_chars,
                "mode": doc.mode,
                "generated_at": doc.generated_at,
                "stale": False,
                "segmented": True,
                "segments": segments_used,
            }
            return new_context, atlas_meta, atlas_chars

    # Fallback: single atlas (no segments or no source_paths)
    atlas_text = doc.content[:budget]
    atlas_block = f"[ATLAS | Codebase Map]\n{atlas_text}"
    atlas_chars = len(atlas_block)

    if context_str:
        new_context = atlas_block + "\n\n---\n\n" + context_str
    else:
        new_context = atlas_block

    atlas_meta = {
        "included": True,
        "chars": atlas_chars,
        "mode": doc.mode,
        "generated_at": doc.generated_at,
        "stale": False,
        "segmented": False,
    }

    return new_context, atlas_meta, atlas_chars


def _load_trace_nodes_for_project(proj: Any) -> List[Dict[str, Any]]:
    """Load trace_nodes.jsonl for a project with live exclude filter applied.

    Returns empty list on any error.
    """
    try:
        from prep.core.project_registry import project_index_dir
        from prep.core.trace.loaders import load_filtered_trace_nodes

        idx_dir = project_index_dir(proj)
        repo_root = Path(proj.path) if proj.path else idx_dir.parent
        return load_filtered_trace_nodes(
            index_dir=idx_dir,
            repo_root=repo_root,
            warn_label="search._load_trace_nodes_for_project",
        )
    except Exception as e:
        logger.debug("Could not load trace_nodes for LOD: %s", e)
        return []


def _apply_lod_compression(
    chunks: List[Dict[str, Any]],
    proj: Any,
    query: str,
    max_chars: int,
    context_tier: Optional[int] = None,
) -> Dict[str, Any]:
    """Apply LOD-based structural compression to structured search results.

    Each chunk's content is replaced by its file's LOD-extracted skeleton.
    The LOD level is assigned per chunk based on its search score.
    Files are deduplicated — each file appears once at its highest-fidelity LOD.
    """
    from prep.core.lod_extractor import LODExtractor, assign_lod
    from prep.core.context_tier import ContextTier, tier_from_budget

    tier = (
        ContextTier(context_tier) if context_tier is not None
        else tier_from_budget(max_chars)
    )

    repo_root = Path(proj.path) if proj.path else Path(".")
    trace_nodes = _load_trace_nodes_for_project(proj)
    extractor = LODExtractor()
    augmented: Dict[str, Any] = {}
    try:
        from prep.core.project_registry import project_index_dir
        extractor = LODExtractor(index_dir=project_index_dir(proj))
        augmented = extractor.load_augmented_data()
    except Exception:
        pass

    # Deduplicate: each file gets the LOD of its highest-scoring chunk
    file_lod: Dict[str, int] = {}  # source_path -> LOD
    file_score: Dict[str, float] = {}
    for ch in chunks:
        sp = ch.get("source_path") or ch.get("text", "")
        if not sp:
            continue
        score = float(ch.get("score", 0.0))
        is_expanded = bool(ch.get("trace_expanded", False))
        lod = assign_lod(score, is_trace_expanded=is_expanded, tier=tier)
        if sp not in file_score or score > file_score[sp]:
            file_score[sp] = score
            file_lod[sp] = lod

    parts: List[str] = []
    new_chunks: List[Dict[str, Any]] = []
    lod_distribution: Dict[str, int] = {}
    seen_paths: set = set()
    total = 0

    for ch in chunks:
        sp = ch.get("source_path") or ""
        if not sp or sp in seen_paths:
            continue
        seen_paths.add(sp)

        lod = file_lod.get(sp, 0)
        result = extractor.extract(sp, lod, trace_nodes, repo_root, augmented_data=augmented)
        content = result.content
        if not content:
            continue

        lod_key = str(result.lod)
        lod_distribution[lod_key] = lod_distribution.get(lod_key, 0) + 1

        section = ch.get("section") or ""
        header_bits = []
        if section:
            header_bits.append(section)
        header_bits.append(f"@{sp}")
        if result.lod > 0:
            header_bits.append(f"lod={result.lod}")
        header = " | ".join(header_bits)

        sep = "\n\n---\n\n" if parts else ""
        remaining = max_chars - total
        if remaining <= 0:
            break
        block = f"[{header}]\n{content}"
        if total + len(sep) + len(block) > max_chars:
            allowed = remaining - len(sep) - len(f"[{header}]\n")
            if allowed > 200:
                block = f"[{header}]\n{content[:allowed]}..."
            else:
                break

        parts.append(sep + block)
        total += len(sep) + len(block)
        new_chunks.append({
            "source_path": sp,
            "section": section,
            "score": file_score.get(sp, 0.0),
            "lod": result.lod,
            "compression_ratio": round(result.compression_ratio, 2),
            "truncated": block.endswith("..."),
        })

    context_str = "".join(parts)
    return {
        "context": context_str,
        "chunks": new_chunks,
        "total_chars": len(context_str),
        "estimated_tokens": len(context_str) // 4,
        "compression": {
            "enabled": True,
            "mode": "lod",
            "input_chars": sum(len(ch.get("text", "") or "") for ch in chunks),
            "output_chars": len(context_str),
            "lod_distribution": lod_distribution,
        },
    }


def _get_compressor(compression: str) -> "ContextCompressor":
    """Get the appropriate compressor based on the compression parameter.

    LLMLingua-2 was removed — quality testing showed unacceptable term retention
    on technical documentation. All compression now goes through LOD or noop.
    """
    return NoopCompressor()


def _migrate_legacy_module_name(m: Dict[str, Any]) -> None:
    """Rewrite legacy `Foo (Packages) #2` names to `Foo (Packages) [<idx>]`
    in a module dict, in place. Idempotent — no-op for already-migrated
    or never-suffixed names. FIX-16-3 follow-up so existing projects get
    cleaner names without forcing a full pipeline rerun.
    """
    from prep.core.cluster import strip_legacy_pound_n_suffix
    name = m.get("name") or ""
    if not name:
        return
    new_name = strip_legacy_pound_n_suffix(name, m.get("module_id") or "")
    if new_name != name:
        m["name"] = new_name


def _load_scope_modules(
    idx_dir: Path,
    included_paths: List[str],
) -> List[Dict[str, Any]]:
    """Load and filter modules from trace_modules.jsonl by scope paths."""
    scope_modules: List[Dict[str, Any]] = []
    modules_path = idx_dir / "trace_modules.jsonl"
    if not modules_path.exists():
        return scope_modules
    try:
        with open(modules_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = _json.loads(line)
                    _migrate_legacy_module_name(m)
                    member_files = m.get("member_files", [])
                    for ip in included_paths:
                        prefix = ip.rstrip("/") + "/"
                        if any(mf == ip or mf.startswith(prefix) for mf in member_files):
                            scope_modules.append(m)
                            break
                except _json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return scope_modules


def _load_all_modules(idx_dir: Path) -> List[Dict[str, Any]]:
    """Load ALL modules from trace_modules.jsonl (no scope filtering).

    Used by the KnowledgeIndex fallback path where the index covers
    all files in the codebase, not just user-selected Knowledge Scope files.
    """
    modules: List[Dict[str, Any]] = []
    modules_path = idx_dir / "trace_modules.jsonl"
    if not modules_path.exists():
        return modules
    try:
        with open(modules_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = _json.loads(line)
                    _migrate_legacy_module_name(m)
                    modules.append(m)
                except _json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return modules


def _first_sentence(text: str) -> str:
    """Return the first sentence of a summary, or the full text if no period.

    Used by `_format_module_tiers` to keep default ambient-context output
    bounded. Synthesizer-generated summaries often run 2-3 sentences of
    consulting-deck filler ("Bridges X with Y while Z…"); the first sentence
    typically carries the actionable signal.
    """
    if not text:
        return text
    idx = text.find(". ")
    if idx == -1:
        return text
    return text[: idx + 1]


def _format_module_tiers(
    scope_modules: List[Dict[str, Any]],
    context_tier: Optional["ContextTier"] = None,
    role: Optional[Any] = None,
    verbose: bool = False,
) -> str:
    """Format modules into tiered display: significant, small, tiny.

    When ``role`` (a ``RoleVector``) is provided, the *significant* tier is
    re-ranked by role-affinity score so that domain-relevant modules float
    to the top — addressing the dogfood finding that role="security" calls
    were leaking marketing modules to the front of the list. The header
    becomes "## Modules in scope (role: <display_name>)" so consumers can
    tell when a role lens is active. Small/tiny tiers are unaffected — the
    role lens only re-orders the prominent slot. ``role`` is typed as
    ``Any`` so this module doesn't pull the atlas package into its import
    graph; callers are expected to pass a ``RoleVector`` or ``None``.

    When ``verbose`` is False (default), the significant list is capped at
    ``tier.module_max_significant`` and each module's summary is truncated to
    its first sentence. ``verbose=True`` restores the original unbounded
    output (FIX-16-1).
    """
    from prep.core.context_tier import ContextTier

    tier = context_tier if context_tier is not None else ContextTier.TIER_2

    if not scope_modules:
        return ""
    significant = [
        m for m in scope_modules
        if m.get("file_count", 0) >= tier.module_min_files_significant
    ]
    small = [
        m for m in scope_modules
        if 2 <= m.get("file_count", 0) < tier.module_min_files_significant
    ]
    tiny = [m for m in scope_modules if m.get("file_count", 0) < 2]

    # Role-weighted re-rank for significant tier.
    role_label = ""
    if role is not None and significant:
        try:
            from prep.core.atlas.role_vectors import max_tag_affinity
            affinity = list(getattr(role, "domain_affinity", []) or [])
            if affinity:
                def _role_key(mod: Dict[str, Any]) -> tuple:
                    score = max_tag_affinity(
                        list(mod.get("domain_tags", []) or []),
                        affinity,
                    )
                    return (-score, -mod.get("file_count", 0))
                significant = sorted(significant, key=_role_key)
                display = getattr(role, "display_name", None) or getattr(
                    role, "role_id", "role"
                )
                role_label = f" (role: {display})"
        except Exception:
            # Role weighting is best-effort. Fall back to file-count order.
            significant = sorted(
                significant, key=lambda x: -x.get("file_count", 0)
            )
    else:
        significant = sorted(significant, key=lambda x: -x.get("file_count", 0))

    omitted_significant = 0
    if not verbose:
        cap = tier.module_max_significant
        if len(significant) > cap:
            omitted_significant = len(significant) - cap
            significant = significant[:cap]

    mod_header = f"## Modules in scope{role_label}\n"
    for m in significant:
        name = m.get("name", m.get("module_id", "?"))
        summary = m.get("summary", "")
        if summary and not verbose:
            summary = _first_sentence(summary)
        fc = m.get("file_count", 0)
        deps = ", ".join(m.get("dependencies", [])[:3])
        line = f"- **{name}** ({fc} files)"
        if summary:
            line += f": {summary}"
        if deps:
            line += f" → {deps}"
        mod_header += line + "\n"
    if omitted_significant:
        mod_header += (
            f"\n*Plus {omitted_significant} more significant modules — "
            f"call prep(verbose=true) to see all*\n"
        )
    if tier.module_show_small and small:
        mod_header += f"\n*Plus {len(small)} smaller modules (2-4 files each)*\n"
    if tier.module_show_tiny and tiny:
        mod_header += f"*Plus {len(tiny)} single-file modules*\n"
    if not tier.module_show_small and not tier.module_show_tiny:
        omitted = len(small) + len(tiny)
        if omitted:
            mod_header += f"\n*Plus {omitted} smaller modules*\n"
    return mod_header.strip()


def _resolve_hub_files(
    trace_idx: Any,
    idx: Any,
    included_paths: List[str],
    hub_count: int = 8,
) -> List[Tuple[str, int]]:
    """Resolve hub files from trace index with fallbacks."""
    hub_files: List[Tuple[str, int]] = []
    if trace_idx is not None and trace_idx.is_loaded():
        scope_set = set(included_paths) if included_paths else None
        hub_files = trace_idx.get_hub_files(scope_paths=scope_set, k=hub_count)
    if not hub_files and included_paths:
        indexed_docs = getattr(idx, '_documents', None) or []
        for ip in included_paths:
            prefix = ip.rstrip("/") + "/"
            for d in indexed_docs:
                sp = str(d.get("source_path") or "")
                if sp == ip or sp.startswith(prefix):
                    hub_files.append((sp, 0))
                    if len(hub_files) >= hub_count:
                        break
            if len(hub_files) >= hub_count:
                break
    if not hub_files:
        if trace_idx is not None and trace_idx.is_loaded():
            hub_files = trace_idx.get_hub_files(k=hub_count)
    return hub_files


def _assemble_ambient_context(
    proj,
    project_id: str,
    idx,
    trace_idx,
    included_paths: List[str],
    max_chars: int = 6000,
    context_tier: Optional[int] = None,
    role: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Assemble context from project state without a query (Phase 34 C1/C2/C3).

    Uses included_paths + trace graph hubs + module data to build structural
    context that answers "what's in my focus area and how does it connect?"

    When ``role`` is provided, the module-list header is re-ranked by the
    role's domain affinity so that domain-relevant modules float to the top
    (closes the 2026-05-02 dogfood finding that role="security" surfaced
    marketing modules first). Resolution is best-effort — unknown role
    strings degrade to the un-weighted ranking silently.
    """
    from prep.core.project_registry import project_index_dir

    parts: List[str] = []
    chunks: List[Dict[str, Any]] = []
    total_chars = 0

    idx_dir = project_index_dir(proj)

    from prep.core.context_tier import ContextTier, tier_from_budget
    tier = (
        ContextTier(context_tier) if context_tier is not None
        else tier_from_budget(max_chars)
    )

    # Resolve role string to a RoleVector for module re-ranking.
    role_vec = None
    if role:
        try:
            from prep.core.atlas.role_resolver import resolve_role
            role_vec = resolve_role(role)
        except Exception:
            role_vec = None

    # ── C2: Module-aware header ──────────────────────────────────
    scope_modules = _load_scope_modules(idx_dir, included_paths)
    mod_text = _format_module_tiers(
        scope_modules, context_tier=tier, role=role_vec, verbose=verbose,
    )
    if mod_text:
        parts.append(mod_text)
        total_chars += len(parts[-1])

    # ── C1: Hub-file extraction ──────────────────────────────────
    hub_files = _resolve_hub_files(trace_idx, idx, included_paths, hub_count=tier.hub_count)

    # ── C3: LOD-stratified assembly ──────────────────────────────
    # Hub files get full content (LOD 0), their neighbors get signatures
    indexed_docs = getattr(idx, '_documents', None) or []
    doc_by_path: Dict[str, List[Dict[str, Any]]] = {}
    for d in indexed_docs:
        sp = str(d.get("source_path") or "")
        if sp:
            doc_by_path.setdefault(sp, []).append(d)

    # Collect neighbor files via trace
    neighbor_files: Set[str] = set()
    hub_paths = {fp for fp, _ in hub_files}
    if trace_idx is not None and trace_idx.is_loaded():
        for fp, _ in hub_files[:5]:  # Only expand top-5 hubs to limit volume
            from prep.core.ids import stable_file_node_id
            file_node_id = stable_file_node_id(fp)
            try:
                neighbors = trace_idx.get_neighbors(file_node_id, direction="both", max_nodes=10)
                for node in neighbors.get("in_nodes", []) + neighbors.get("out_nodes", []):
                    nfp = node.get("file_path")
                    if nfp and nfp not in hub_paths:
                        neighbor_files.add(nfp)
            except Exception:
                pass

    # Assemble hub file content (LOD 0 — full source, budget-aware)
    chars_budget = max_chars - total_chars
    hub_budget = int(chars_budget * tier.hub_budget_pct)
    neighbor_budget = int(chars_budget * tier.neighbor_budget_pct)

    hub_lod_extractor = None
    if tier.hub_lod > 0:
        try:
            from prep.core.lod_extractor import LODExtractor
            hub_lod_extractor = LODExtractor(index_dir=idx_dir)
        except Exception:
            pass
    repo_root_path = Path(proj.path) if proj.path else None

    hub_chars = 0
    seen_hub_paths: set = set()  # Phase 73.1 Fix 2: dedup hub files
    for fp, deg in hub_files:
        if hub_chars >= hub_budget:
            break
        if fp in seen_hub_paths:  # Phase 73.1: skip duplicate file paths
            continue
        seen_hub_paths.add(fp)
        file_docs = doc_by_path.get(fp, [])

        # Tier-aware hub LOD: use LOD extraction when tier specifies LOD > 0
        content = None
        if tier.hub_lod > 0 and hub_lod_extractor is not None and repo_root_path is not None:
            try:
                trace_nodes_for_hub = []
                if trace_idx is not None and trace_idx.is_loaded():
                    for nid_key in list(getattr(trace_idx, '_nodes', {}).keys()):
                        n = trace_idx.get_node(nid_key)
                        if n and n.get("file_path") == fp:
                            trace_nodes_for_hub.append(n)
                lod_result = hub_lod_extractor.extract(
                    fp, lod=tier.hub_lod, trace_nodes=trace_nodes_for_hub,
                    repo_root=repo_root_path,
                )
                if lod_result and lod_result.content and not lod_result.error:
                    content = lod_result.content
            except Exception:
                pass

        if content is None:
            # Original document-based fallback
            if not file_docs:
                continue
            # Phase 73: Pick most representative chunk, not largest.
            # Priority: META_SYNOPSIS > first chunk (by line) > largest chunk.
            best_doc = None
            for d in file_docs:
                if d.get("section") == "META_SYNOPSIS":
                    best_doc = d
                    break
            if best_doc is None:
                by_span = sorted(
                    file_docs,
                    key=lambda d: (d.get("span") or {}).get("start_line", 9999),
                )
                best_doc = by_span[0]
            content = str(best_doc.get("content") or "")

        if hub_chars + len(content) > hub_budget and hub_chars > 0:
            continue
        section = str(best_doc.get("section") or "") if tier.hub_lod == 0 and file_docs else ""
        header = f"[hub | in-degree:{deg}"
        if tier.hub_lod > 0:
            header += f" | lod={tier.hub_lod}"
        header += f" | @{fp}"
        if section:
            header += f" § {section}"
        header += "]"
        block = f"{header}\n{content}"
        parts.append(block)
        chunks.append({
            "source_path": fp,
            "section": section,
            "score": 1.0,
            "truncated": tier.hub_lod > 0,
            "ambient_role": "hub",
        })
        hub_chars += len(block)
        total_chars += len(block)

    # Assemble neighbor content (LOD 2-4 — signatures/names only)
    # Try LOD compression; fall back to truncated content
    neighbor_chars = 0
    lod_extractor = None
    try:
        from prep.core.lod_extractor import LODExtractor
        lod_extractor = LODExtractor(index_dir=idx_dir)
    except Exception:
        pass

    repo_root = Path(proj.path) if proj.path else None

    for nfp in sorted(neighbor_files):
        if neighbor_chars >= neighbor_budget:
            break
        file_docs = doc_by_path.get(nfp, [])

        # Try LOD 2 (signatures + docstrings) via LODExtractor
        lod_content = None
        if lod_extractor is not None and repo_root is not None:
            try:
                # Load trace nodes for this file
                trace_nodes = []
                if trace_idx is not None and trace_idx.is_loaded():
                    from prep.core.ids import stable_file_node_id as _sfni
                    file_nid = _sfni(nfp)
                    fnode = trace_idx.get_node(file_nid)
                    if fnode:
                        trace_nodes = [fnode]
                    # Also get symbol nodes in this file
                    for nid_key in list(getattr(trace_idx, '_nodes', {}).keys()):
                        n = trace_idx.get_node(nid_key)
                        if n and n.get("file_path") == nfp and n.get("kind") != "file":
                            trace_nodes.append(n)

                lod_result = lod_extractor.extract(nfp, lod=tier.neighbor_lod, trace_nodes=trace_nodes, repo_root=repo_root)
                if lod_result and lod_result.content and not lod_result.error:
                    lod_content = lod_result.content
            except Exception:
                pass

        if lod_content:
            content = lod_content
            lod_label = f"LOD {tier.neighbor_lod}"
        elif file_docs:
            # Phase 73: Prefer META_SYNOPSIS over blind truncation
            meta_doc = next((d for d in file_docs if d.get("section") == "META_SYNOPSIS"), None)
            if meta_doc:
                content = str(meta_doc.get("content") or "")
                lod_label = "synopsis"
            else:
                # Phase 73: Consistent with hub selection — prefer first chunk by line
                by_span = sorted(file_docs, key=lambda d: (d.get("span") or {}).get("start_line", 9999))
                best_doc = by_span[0]
                raw = str(best_doc.get("content") or "")
                # Truncate at newline boundary, not mid-line
                if len(raw) > 500:
                    cut = raw[:500].rfind("\n")
                    if cut > 250:
                        content = raw[:cut] + "\n..."
                    else:
                        content = raw[:500] + "..."
                else:
                    content = raw
                lod_label = "truncated"
        else:
            continue

        if neighbor_chars + len(content) > neighbor_budget and neighbor_chars > 0:
            continue

        header = f"[neighbor | {lod_label} | @{nfp}]"
        block = f"{header}\n{content}"
        parts.append(block)
        chunks.append({
            "source_path": nfp,
            "section": "",
            "score": 0.5,
            "truncated": lod_label != "LOD 2",
            "ambient_role": "neighbor",
        })
        neighbor_chars += len(block)
        total_chars += len(block)

    # Phase 73: Fallback to Atlas if no structural hubs/neighbors were found
    if not parts:
        try:
            import json
            atlas_path = Path(idx_dir) / "atlas.json"
            if atlas_path.exists():
                with open(atlas_path, "r", encoding="utf-8") as f:
                    atlas_data = json.load(f)
                    if atlas_data and atlas_data.get("content"):
                        parts.append(f"## Codebase Atlas\n\n{atlas_data['content']}")
        except Exception:
            pass

    context_str = "\n\n---\n\n".join(parts) if parts else "(No context available — select files in the dashboard or build the trace index.)"
    total_chars = len(context_str)

    return ok({
        "context": context_str,
        "chunks": chunks,
        "total_chars": total_chars,
        "estimated_tokens": total_chars // 4,
        "ambient": True,
        "hub_files": len(hub_files),
        "modules_in_scope": len(scope_modules),
        "neighbor_files": len(neighbor_files),
    })


@router.post("/projects/{project_id}/context")
def context_project(project_id: str, req: ContextRequest) -> Dict[str, Any]:
    proj = _srv()._require_project(project_id)

    idx = _srv()._get_project_layered_index(proj)

    # ── KnowledgeIndex fallback: if CodeIndex isn't loaded, check if the
    # pipeline's KnowledgeIndex can serve. This covers projects where no
    # Knowledge Scope files are selected (CodeIndex was never built) or
    # where the CodeIndex build was lost (daemon crash mid-build).
    _using_knowledge_fallback = False
    if not idx.is_loaded():
        try:
            from prep.server import _get_project_knowledge_index
            know_idx = _get_project_knowledge_index(proj)
            if know_idx.is_loaded():
                _using_knowledge_fallback = True
            else:
                raise ApiException(
                    status_code=409,
                    code="INDEX_NOT_BUILT",
                    message="Index has not been built yet",
                    hint="Run a build first.",
                )
        except ApiException:
            raise
        except Exception:
            raise ApiException(
                status_code=409,
                code="INDEX_NOT_BUILT",
                message="Index has not been built yet",
                hint="Run a build first.",
            )

    # Resolve trace index for trace expansion
    # Phase 34: trace_expand defaults to True. Gracefully degrade if
    # the feature gate blocks it (free tier) or trace isn't available.
    #
    # F-50: previously gated on config.trace.enabled — same root-cause class
    # as F-39 / F-42 / F-49.  trace.enabled is the auto-build preference,
    # not a data-presence flag, so a project with a built trace graph but
    # enabled=false would silently fall back to non-expanded search results.
    # Now we just check ti.exists() — if the data is on disk, expand search
    # with it regardless of the auto-build preference.
    trace_idx = None
    if req.trace_expand:
        try:
            require_feature("mcp_trace_expand")
            try:
                ti = _srv()._get_project_srv()._trace_index(proj)
                if ti.exists():
                    if not ti.is_loaded():
                        ti.load()
                    trace_idx = ti
            except Exception:
                pass  # Graceful: fall back to non-expanded context
        except FeatureGateError:
            pass  # Phase 34: default-on means graceful fallback for free tier

    # ── KnowledgeIndex-only path ─────────────────────────────────
    # When CodeIndex isn't loaded but KnowledgeIndex is, serve context
    # from the KnowledgeIndex. For ambient (no query), build a minimal
    # structural context. For queries, search the KnowledgeIndex.
    if _using_knowledge_fallback:
        from prep.server import _get_project_knowledge_index
        from prep.core.project_registry import project_index_dir
        know_idx = _get_project_knowledge_index(proj)

        if not req.query.strip():
            # Ambient context: modules + atlas (no CodeIndex chunks needed)
            _included = (proj.config or {}).get("included_paths") or []
            idx_dir = project_index_dir(proj)
            parts: List[str] = []
            total_chars = 0

            from prep.core.context_tier import ContextTier, tier_from_budget
            tier = (
                ContextTier(req.context_tier) if req.context_tier is not None
                else tier_from_budget(req.max_chars)
            )

            # Load modules — when Knowledge Scope files are selected, filter
            # to those; otherwise load ALL modules since the KnowledgeIndex
            # covers the full codebase.
            if _included:
                scope_modules = _load_scope_modules(idx_dir, _included)
            else:
                scope_modules = _load_all_modules(idx_dir)
            # Resolve role for module re-ranking (best-effort).
            _role_vec = None
            if req.role:
                try:
                    from prep.core.atlas.role_resolver import resolve_role
                    _role_vec = resolve_role(req.role)
                except Exception:
                    _role_vec = None
            mod_text = _format_module_tiers(
                scope_modules, context_tier=tier, role=_role_vec,
                verbose=req.verbose,
            )
            if mod_text:
                parts.append(mod_text)
                total_chars += len(mod_text)

            context_text = "\n\n".join(parts)
            resp: Dict[str, Any] = ok({
                "context": context_text,
                "chunks_used": 0,
                "total_chars": total_chars,
                "estimated_tokens": total_chars // 4,
                "ambient": True,
                "hub_files": 0,
                "modules_in_scope": len(scope_modules),
                "neighbor_files": 0,
                "source": "knowledge",
            })
            # Atlas prepend
            if req.include_atlas:
                _file_count = know_idx.status().get("count", 0)
                new_ctx, atlas_meta, _ = _prepend_atlas(context_text, project_id, _file_count)
                resp["data"]["context"] = new_ctx
                if atlas_meta:
                    resp["data"]["atlas"] = atlas_meta
            return resp

        # Query-based search: use KnowledgeIndex.search()
        know_results = know_idx.search(req.query, k=req.k, min_score=req.min_score)
        chunks: List[Dict[str, Any]] = []
        context_parts: List[str] = []
        for kr in know_results:
            doc = kr.get("doc", {})
            score = float(kr.get("score", 0.0))
            source_id = doc.get("source_id", "")
            content = doc.get("content", "")
            chunks.append({
                "source_path": source_id,
                "section": doc.get("type", "knowledge"),
                "score": score,
                "text": content,
                "source": "knowledge",
            })
            context_parts.append(f"--- {source_id} (score: {score:.3f}) ---\n{content}")

        context_text = "\n\n".join(context_parts)
        total_chars = len(context_text)

        resp = {"context": context_text, "chunks": chunks, "source": "knowledge"}

        # Atlas prepend
        if req.include_atlas:
            _file_count = know_idx.status().get("count", 0)
            new_ctx, atlas_meta, _ = _prepend_atlas(context_text, project_id, _file_count)
            resp["context"] = new_ctx
            if atlas_meta:
                resp["atlas"] = atlas_meta

        # Observations injection
        resp["context"], _obs_meta = _inject_observations(resp["context"], project_id, req.query)
        if _obs_meta:
            resp["session_memory"] = _obs_meta

        return ok(resp)

    # ── Phase 34 C4: Ambient context mode (no query) ─────────────
    if not req.query.strip():
        _included = (proj.config or {}).get("included_paths") or []
        return _assemble_ambient_context(
            proj, project_id, idx, trace_idx, _included, max_chars=req.max_chars,
            context_tier=req.context_tier, role=req.role, verbose=req.verbose,
        )

    # ── Phase 34e F: Query preprocessing ─────────────────────────
    req.query = _preprocess_query(req.query)

    # Resolve file count for atlas budget (from index manifest)
    _file_count = 0
    try:
        _manifest = getattr(idx, '_manifest', None) or {}
        _file_count = (_manifest.get('stats') or {}).get('files_indexed', 0)
        if _file_count == 0:
            _file_count = len(getattr(idx, '_documents', None) or [])
    except Exception:
        pass

    # ── Scope boost (Phase 34) ───────────────────────────────────
    # Load included_paths from project config and use them as a
    # query-time scope boost.  Files under selected paths get the
    # same +boost as atlas-routed files, ensuring the user's file
    # tree selections influence retrieval — not just build scoping.
    _segment_file_paths: Optional[set] = None
    _routing_meta: Optional[Dict[str, Any]] = None
    _scope_boosted_files: int = 0
    _sr6_segment_boost: float = 0.12  # SR-6: default boost; raised to 0.30 for high-confidence routing
    try:
        _included = (proj.config or {}).get("included_paths") or []
        if _included:
            _segment_file_paths = set()
            # included_paths may be files or directories — we need to
            # resolve them against indexed documents so directory entries
            # expand to all files beneath them.
            _indexed_paths = set()
            for d in (getattr(idx, '_documents', None) or []):
                sp = d.get("source_path")
                if sp:
                    _indexed_paths.add(str(sp))
            for ip in _included:
                ip_str = str(ip)
                if ip_str in _indexed_paths:
                    _segment_file_paths.add(ip_str)
                else:
                    # Treat as directory prefix
                    prefix = ip_str.rstrip("/") + "/"
                    for idxp in _indexed_paths:
                        if idxp.startswith(prefix):
                            _segment_file_paths.add(idxp)
            _scope_boosted_files = len(_segment_file_paths)
            if _scope_boosted_files:
                _routing_meta = {
                    "scope_boosted_files": _scope_boosted_files,
                }
                logger.debug("Scope boost: %d files from %d included_paths", _scope_boosted_files, len(_included))
            else:
                _segment_file_paths = None  # No matches — don't pollute boost set
    except Exception as e:
        logger.debug("Scope boost unavailable: %s", e)

    # ── Atlas routing (Phase 29B) ────────────────────────────────
    # Route query to relevant segments BEFORE search, so search()
    # can boost files in the selected segments.
    try:
        from prep.core.atlas import CodebaseAtlas, route_query, ROUTING_SEGMENT_BOOST
        from prep.core.project_registry import project_index_dir
        from prep.services.project_helpers import require_project
        import numpy as np

        _proj = require_project(project_id)
        _idx_dir = project_index_dir(_proj)
        _atlas = CodebaseAtlas(_idx_dir)

        if _atlas.has_routing():
            descriptors, desc_embeddings = _atlas.load_routing()
            if descriptors and desc_embeddings is not None:
                # Embed query using the same embedder as the index
                _embed_fn = getattr(idx.embedder, "embed_query", idx.embedder.embed)
                _qvec = np.array(_embed_fn(req.query).vector, dtype=np.float32)

                selected = route_query(_qvec, desc_embeddings, descriptors)
                if selected:
                    _atlas_paths = _atlas.get_routed_file_paths(selected)
                    if _segment_file_paths is None:
                        _segment_file_paths = _atlas_paths
                    else:
                        _segment_file_paths = _segment_file_paths | _atlas_paths

                    # SR-6: High-confidence atlas routing → hard pre-filter
                    # When the top segment score is very high (>0.7), exclude
                    # files NOT in the routed segments from search results.
                    # This reduces noise from unrelated subsystems.
                    _top_routing_score = max(s for _, s in selected) if selected else 0.0
                    _sr6_prefilter = _top_routing_score > 0.7 and len(_atlas_paths) >= 5

                    _routing_meta = {
                        "routed": True,
                        "segments": [
                            {"id": d.segment_id, "name": d.name, "score": round(s, 3)}
                            for d, s in selected
                        ],
                        "boosted_files": len(_segment_file_paths),
                        "scope_boosted_files": _scope_boosted_files,
                        "prefiltered": _sr6_prefilter,
                    }

                    # SR-6: When pre-filtering is active, increase the segment
                    # boost so routed files dominate results. Non-routed files
                    # still appear if their embedding score is very high.
                    if _sr6_prefilter:
                        _sr6_segment_boost = 0.30  # 2.5x the default 0.12
    except Exception as e:
        logger.debug("Atlas routing unavailable: %s", e)

    # ── Knowledge routing (Phase 29C) ────────────────────────────
    # Search the KnowledgeIndex (trace-derived LLM descriptions) to
    # identify specific files whose *enriched descriptions* match the
    # query. These are unioned into the segment boost set, giving a
    # two-tier precision boost:
    #   Tier 1 (atlas)     → which subsystem?  (segment granularity)
    #   Tier 2 (knowledge) → which exact files? (node granularity)
    # Zero context cost — only shapes the boost set, adds no text.
    _knowledge_boosted_files: int = 0
    try:
        from prep.server import _get_project_knowledge_index
        from prep.services.project_helpers import require_project as _rp_know
        _know_proj = _rp_know(project_id)
        _know_idx = _get_project_knowledge_index(_know_proj)
        if _know_idx.is_loaded():
            _know_results = _know_idx.search(req.query, k=15, min_score=0.25)
            if _know_results:
                if _segment_file_paths is None:
                    _segment_file_paths = set()
                for _kr in _know_results:
                    _src = _kr["doc"].get("source_id") or ""
                    if _src.startswith("file:"):
                        _segment_file_paths.add(_src[5:])
                    elif _src.startswith("sym:"):
                        _at = _src.find("@")
                        if _at >= 0:
                            _rest = _src[_at + 1:]
                            _colon = _rest.rfind(":")
                            _segment_file_paths.add(_rest[:_colon] if _colon > 0 else _rest)
                _knowledge_boosted_files = len(_know_results)
                if _routing_meta is not None:
                    _routing_meta["knowledge_boosted_files"] = _knowledge_boosted_files
                elif _knowledge_boosted_files:
                    _routing_meta = {
                        "routed": False,
                        "knowledge_boosted_files": _knowledge_boosted_files,
                    }
    except Exception as e:
        logger.debug("Knowledge routing unavailable: %s", e)

    # ── Phase 120: Named scope filtering (replaces Phase 67 role auto-mask) ──
    from prep.core.scope_resolver import resolve_mask, path_matches_any_scope
    _ctx_resolution = resolve_mask(project_id, scope=req.scope, role=req.role)
    _agent_mask = _ctx_resolution.mask
    _agent_scope_applied = False
    if _agent_mask is not None:
        # Use path_matches_any_scope (prefix-aware) to expand into indexed docs
        _indexed_paths_for_scope: Set[str] = set()
        for d in (getattr(idx, '_documents', None) or []):
            sp = d.get("source_path")
            if sp:
                _indexed_paths_for_scope.add(str(sp))
        _expanded_mask: Set[str] = {
            p for p in _indexed_paths_for_scope
            if path_matches_any_scope(p, _agent_mask)
        }
        if _expanded_mask:
            if _segment_file_paths is not None:
                # Intersect: only boost files that are BOTH routed AND in scope
                _segment_file_paths = _segment_file_paths & _expanded_mask
            else:
                # No routing — use scope mask as the boost set directly
                _segment_file_paths = _expanded_mask
            _agent_scope_applied = True
            _sr6_segment_boost = max(_sr6_segment_boost, 0.25)
            logger.debug(
                "Scope applied: scope=%s role=%s files=%d",
                _ctx_resolution.applied_scope, req.role, len(_segment_file_paths),
            )
            if _routing_meta is None:
                _routing_meta = {}
            _routing_meta["applied_scope"] = _ctx_resolution.applied_scope
            _routing_meta["agent_scope_files"] = len(_expanded_mask)

    # Update boosted_files to total pool size after both routing tiers
    if _routing_meta is not None and _segment_file_paths:
        _routing_meta["boosted_files"] = len(_segment_file_paths)

    if not req.structured:
        ctx = idx.get_context(
            req.query,
            k=req.k,
            max_chars=req.max_chars,
            include_sources=req.include_sources,
            include_scores=req.include_scores,
            min_score=req.min_score,
            segment_file_paths=_segment_file_paths,
            segment_boost=_sr6_segment_boost,
        )

        resp: Dict[str, Any] = {"context": ctx}
        # Atlas: routing metadata (no injection) + legacy prepend fallback
        if _routing_meta:
            resp["atlas"] = _routing_meta
        elif req.include_atlas:
            new_ctx, atlas_meta, _ = _prepend_atlas(resp["context"], project_id, _file_count)
            resp["context"] = new_ctx
            if atlas_meta:
                resp["atlas"] = atlas_meta
        # Phase 39: Inject relevant observations as session-memory
        resp["context"], _obs_meta = _inject_observations(resp["context"], project_id, req.query)
        if _obs_meta:
            resp["session_memory"] = _obs_meta
        resp["applied_scope"] = _ctx_resolution.applied_scope
        resp["applied_role"] = req.role
        if _ctx_resolution.warning:
            resp["scope_warning"] = _ctx_resolution.warning
        return ok(resp)

    # ── SR-2: Knowledge Index content fallback ──────────────────
    # When CodeIndex coverage is sparse (few chunks indexed), supplement
    # search with KnowledgeIndex results. The knowledge index contains
    # LLM-enriched file descriptions that can fill gaps where source
    # code chunks aren't indexed. This is additive — knowledge results
    # appear as supplementary context, not a replacement.
    _knowledge_fallback_chunks: List[Dict[str, Any]] = []
    try:
        from prep.server import _get_project_knowledge_index
        _know_idx = _get_project_knowledge_index(proj)
        if _know_idx.is_loaded():
            _code_doc_count = len(getattr(idx, '_documents', None) or [])
            # Heuristic: if CodeIndex has fewer than 100 chunks, knowledge
            # fallback is likely valuable (sparse coverage)
            if _code_doc_count < 100:
                _know_results = _know_idx.search(req.query, k=3, min_score=0.30)
                for _kr in _know_results:
                    _kd = _kr.get("doc") if isinstance(_kr, dict) else _kr
                    if not isinstance(_kd, dict):
                        continue
                    _knowledge_fallback_chunks.append({
                        "source_path": str(_kd.get("source_path") or _kd.get("source_id") or ""),
                        "section": "knowledge-enriched",
                        "score": float(_kr.get("score", 0.0) if isinstance(_kr, dict) else 0.0),
                        "text": str(_kd.get("content") or _kd.get("text") or ""),
                        "is_knowledge_fallback": True,
                    })
    except Exception as e:
        logger.debug("SR-2 knowledge fallback unavailable: %s", e)

    # Structured context: use trace expansion if available
    if trace_idx is not None:
        # W2b: Resolve modules path for module summary injection
        _modules_path = None
        try:
            _modules_path = project_index_dir(proj) / "trace_modules.jsonl"
            if not _modules_path.exists():
                _modules_path = None
        except Exception:
            pass

        result = idx.get_context_with_trace_expansion(
            req.query,
            trace_index=trace_idx,
            k=req.k,
            max_chars=req.max_chars,
            min_score=req.min_score,
            max_additional_chars=req.trace_max_chars,
            segment_file_paths=_segment_file_paths,
            segment_boost=_sr6_segment_boost,
            modules_path=_modules_path,
        )
        # SR-2: Append knowledge fallback chunks to trace-expanded results
        if _knowledge_fallback_chunks:
            existing_chunks = result.get("chunks", [])
            existing_chunks.extend(_knowledge_fallback_chunks)
            result["chunks"] = existing_chunks

        # Phase 34c E1: LOD structural compression is always applied
        # in the structured+trace path.
        lod_result = _apply_lod_compression(
            result.get("chunks", []), proj, req.query, req.max_chars,
            context_tier=req.context_tier,
        )
        resp_data: Dict[str, Any] = {
            **lod_result,
            "trace_expanded": result.get("trace_expanded", False),
            "trace_nodes_added": result.get("trace_nodes_added", 0),
        }
        # Atlas: routing metadata (no injection) + legacy prepend fallback
        if _routing_meta:
            resp_data["atlas"] = _routing_meta
        elif req.include_atlas:
            new_ctx, atlas_meta, atlas_chars = _prepend_atlas(resp_data["context"], project_id, _file_count)
            resp_data["context"] = new_ctx
            resp_data["total_chars"] = len(new_ctx)
            resp_data["estimated_tokens"] = len(new_ctx) // 4
            if atlas_meta:
                resp_data["atlas"] = atlas_meta
        # Phase 73.5: Forward query coverage metadata
        if isinstance(result, dict) and "query_coverage" in result:
            resp_data["query_coverage"] = result["query_coverage"]
        # Phase 39: Inject relevant observations as session-memory
        resp_data["context"], _obs_meta = _inject_observations(resp_data["context"], project_id, req.query)
        if _obs_meta:
            resp_data["session_memory"] = _obs_meta
            resp_data["total_chars"] = len(resp_data["context"])
            resp_data["estimated_tokens"] = resp_data["total_chars"] // 4
        resp_data["applied_scope"] = _ctx_resolution.applied_scope
        resp_data["applied_role"] = req.role
        if _ctx_resolution.warning:
            resp_data["scope_warning"] = _ctx_resolution.warning
        return ok(resp_data)

    results = idx.search(
        req.query, k=req.k, min_score=req.min_score,
        score_drop_ratio=req.score_drop_ratio, mmr_lambda=req.mmr_lambda,
        exclude_paths=req.exclude_paths or None,
        segment_file_paths=_segment_file_paths,
        segment_boost=_sr6_segment_boost,
    )

    # Phase 34c E1: auto-LOD in structured path (no trace fallback)
    raw_chunks = [
        {
            "source_path": str(r.doc.get("source_path") or ""),
            "section": str(r.doc.get("section") or ""),
            "score": float(r.score),
            "text": str(r.doc.get("content") or ""),
        }
        for r in results
    ]
    # SR-2: Append knowledge fallback chunks to non-trace results
    if _knowledge_fallback_chunks:
        raw_chunks.extend(_knowledge_fallback_chunks)
    lod_result = _apply_lod_compression(
        raw_chunks, proj, req.query, req.max_chars,
        context_tier=req.context_tier,
    )
    resp_data: Dict[str, Any] = lod_result
    # Phase 73.5: Forward query coverage metadata
    _qc_signals = getattr(idx, "_last_query_signals", None)
    if _qc_signals and _qc_signals.keywords and results:
        _qc_content = " ".join(
            str(r.doc.get("content") or "") + " " + str(r.doc.get("source_path") or "")
            for r in results
        )
        _qc_cov = _qc_signals.compute_coverage(_qc_content)
        _qc_matched = sum(1 for v in _qc_cov.values() if v)
        resp_data["query_coverage"] = {
            "terms": _qc_cov,
            "matched": _qc_matched,
            "total": len(_qc_cov),
            "ratio": round(_qc_matched / len(_qc_cov), 2) if _qc_cov else 1.0,
        }
    if _routing_meta:
        resp_data["atlas"] = _routing_meta
    elif req.include_atlas:
        new_ctx, atlas_meta, atlas_chars = _prepend_atlas(resp_data["context"], project_id, _file_count)
        resp_data["context"] = new_ctx
        resp_data["total_chars"] = len(new_ctx)
        resp_data["estimated_tokens"] = len(new_ctx) // 4
        if atlas_meta:
            resp_data["atlas"] = atlas_meta
    # Phase 39: Inject relevant observations as session-memory
    resp_data["context"], _obs_meta = _inject_observations(resp_data["context"], project_id, req.query)
    if _obs_meta:
        resp_data["session_memory"] = _obs_meta
        resp_data["total_chars"] = len(resp_data["context"])
        resp_data["estimated_tokens"] = resp_data["total_chars"] // 4
    resp_data["applied_scope"] = _ctx_resolution.applied_scope
    resp_data["applied_role"] = req.role
    if _ctx_resolution.warning:
        resp_data["scope_warning"] = _ctx_resolution.warning
    return ok(resp_data)




