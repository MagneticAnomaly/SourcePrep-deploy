"""
Project search and context endpoints — the primary value delivery path.

Contains: search, context, and all context assembly helpers
(observations, atlas prepend, LOD compression, lingua compression, ambient context).
"""
from __future__ import annotations

import json as _json
import logging
import re as _re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter

from codrag.api.envelope import ApiException, ok
from codrag.core.feature_gate import require_feature, FeatureGateError
from codrag.core.project_registry import project_index_dir
from codrag.core import LinguaCompressor, NoopCompressor
from codrag.core.query import preprocess_query as _preprocess_query

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

    # ── Phase 67: Agent scope filtering ──────────────────────────
    _agent_mask = None
    if req.role:
        try:
            from codrag.core.agent_scope_manager import agent_scope_manager, _path_matches_scope
            _agent_mask = agent_scope_manager.get_agent_mask(project_id, req.role)
        except Exception:
            logger.debug("Agent scope filtering unavailable", exc_info=True)

    out: List[Dict[str, Any]] = []
    for r in results:
        d = r.doc
        source_path = str(d.get("source_path") or "")

        # Phase 67: Skip results outside agent's scope
        if _agent_mask is not None and source_path and not _path_matches_scope(source_path, _agent_mask):
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
    return ok({"results": out, **({"agent_scope": req.role} if req.role else {})})


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
        from codrag.services.observation_store import observation_store
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
    from codrag.core.atlas import CodebaseAtlas, compute_atlas_budget
    from codrag.core.project_registry import project_index_dir
    from codrag.services.project_helpers import require_project

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
    """Load trace_nodes.jsonl for a project. Returns empty list on any error."""
    import json
    try:
        from codrag.core.project_registry import project_index_dir
        idx_dir = project_index_dir(proj)
        nodes_path = idx_dir / "trace_nodes.jsonl"
        if not nodes_path.exists():
            return []
        nodes: List[Dict[str, Any]] = []
        with open(nodes_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    nodes.append(json.loads(line))
        return nodes
    except Exception as e:
        logger.debug("Could not load trace_nodes for LOD: %s", e)
        return []


def _apply_lod_compression(
    chunks: List[Dict[str, Any]],
    proj: Any,
    query: str,
    max_chars: int,
) -> Dict[str, Any]:
    """Apply LOD-based structural compression to structured search results.

    Each chunk's content is replaced by its file's LOD-extracted skeleton.
    The LOD level is assigned per chunk based on its search score.
    Files are deduplicated — each file appears once at its highest-fidelity LOD.
    """
    from codrag.core.lod_extractor import LODExtractor, assign_lod

    repo_root = Path(proj.path) if proj.path else Path(".")
    trace_nodes = _load_trace_nodes_for_project(proj)
    extractor = LODExtractor()
    augmented: Dict[str, Any] = {}
    try:
        from codrag.core.project_registry import project_index_dir
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
        lod = assign_lod(score, is_trace_expanded=is_expanded)
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
    """Get the appropriate compressor based on the compression parameter."""
    if compression in ("lingua", "auto"):
        return LinguaCompressor()
    return NoopCompressor()


def _apply_compression(
    context_str: str,
    req: ContextRequest,
) -> Dict[str, Any]:
    """Apply compression to context string and return compression metadata."""
    if req.compression == "none":
        return {"context": context_str, "compression": None}


    compressor = _get_compressor(req.compression)
    budget = req.compression_target_chars or req.max_chars
    result = compressor.compress(
        context_str,
        query=req.query,
        budget_chars=budget,
        level=req.compression_level,
        timeout_s=req.compression_timeout_s,
    )

    compression_meta = {
        "enabled": True,
        "mode": req.compression,
        "level": req.compression_level,
        "input_chars": result.input_chars,
        "output_chars": result.output_chars,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "compression_ratio": result.compression_ratio,
        "timing_ms": round(result.timing_ms, 1),
        "error": result.error,
    }

    return {"context": result.compressed, "compression": compression_meta}


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


def _format_module_tiers(scope_modules: List[Dict[str, Any]]) -> str:
    """Format modules into tiered display: significant, small, tiny."""
    if not scope_modules:
        return ""
    significant = [m for m in scope_modules if m.get("file_count", 0) >= 5]
    small = [m for m in scope_modules if 2 <= m.get("file_count", 0) < 5]
    tiny = [m for m in scope_modules if m.get("file_count", 0) < 2]

    mod_header = "## Modules in scope\n"
    for m in sorted(significant, key=lambda x: -x.get("file_count", 0)):
        name = m.get("name", m.get("module_id", "?"))
        summary = m.get("summary", "")
        fc = m.get("file_count", 0)
        deps = ", ".join(m.get("dependencies", [])[:3])
        line = f"- **{name}** ({fc} files)"
        if summary:
            line += f": {summary}"
        if deps:
            line += f" → {deps}"
        mod_header += line + "\n"
    if small:
        mod_header += f"\n*Plus {len(small)} smaller modules (2-4 files each)*\n"
    if tiny:
        mod_header += f"*Plus {len(tiny)} single-file modules*\n"
    return mod_header.strip()


def _resolve_hub_files(
    trace_idx: Any,
    idx: Any,
    included_paths: List[str],
) -> List[Tuple[str, int]]:
    """Resolve hub files from trace index with fallbacks."""
    hub_files: List[Tuple[str, int]] = []
    if trace_idx is not None and trace_idx.is_loaded():
        scope_set = set(included_paths) if included_paths else None
        hub_files = trace_idx.get_hub_files(scope_paths=scope_set, k=8)
    if not hub_files and included_paths:
        indexed_docs = getattr(idx, '_documents', None) or []
        for ip in included_paths:
            prefix = ip.rstrip("/") + "/"
            for d in indexed_docs:
                sp = str(d.get("source_path") or "")
                if sp == ip or sp.startswith(prefix):
                    hub_files.append((sp, 0))
                    if len(hub_files) >= 8:
                        break
            if len(hub_files) >= 8:
                break
    if not hub_files:
        if trace_idx is not None and trace_idx.is_loaded():
            hub_files = trace_idx.get_hub_files(k=8)
    return hub_files


def _assemble_ambient_context(
    proj,
    project_id: str,
    idx,
    trace_idx,
    included_paths: List[str],
    max_chars: int = 6000,
) -> Dict[str, Any]:
    """Assemble context from project state without a query (Phase 34 C1/C2/C3).

    Uses included_paths + trace graph hubs + module data to build structural
    context that answers "what's in my focus area and how does it connect?"
    """
    from codrag.core.project_registry import project_index_dir

    parts: List[str] = []
    chunks: List[Dict[str, Any]] = []
    total_chars = 0

    idx_dir = project_index_dir(proj)

    # ── C2: Module-aware header ──────────────────────────────────
    scope_modules = _load_scope_modules(idx_dir, included_paths)
    mod_text = _format_module_tiers(scope_modules)
    if mod_text:
        parts.append(mod_text)
        total_chars += len(parts[-1])

    # ── C1: Hub-file extraction ──────────────────────────────────
    hub_files = _resolve_hub_files(trace_idx, idx, included_paths)

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
            from codrag.core.ids import stable_file_node_id
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
    hub_budget = int(chars_budget * 0.7)  # 70% for hubs
    neighbor_budget = int(chars_budget * 0.3)  # 30% for neighbors

    hub_chars = 0
    seen_hub_paths: set = set()  # Phase 73.1 Fix 2: dedup hub files
    for fp, deg in hub_files:
        if hub_chars >= hub_budget:
            break
        if fp in seen_hub_paths:  # Phase 73.1: skip duplicate file paths
            continue
        seen_hub_paths.add(fp)
        file_docs = doc_by_path.get(fp, [])
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
            by_span = sorted(file_docs, key=lambda d: (d.get("span") or {}).get("start_line", 9999))
            best_doc = by_span[0]
        content = str(best_doc.get("content") or "")
        if hub_chars + len(content) > hub_budget and hub_chars > 0:
            continue
        section = str(best_doc.get("section") or "")
        header = f"[hub | in-degree:{deg} | @{fp}"
        if section:
            header += f" § {section}"
        header += "]"
        block = f"{header}\n{content}"
        parts.append(block)
        chunks.append({
            "source_path": fp,
            "section": section,
            "score": 1.0,
            "truncated": False,
            "ambient_role": "hub",
        })
        hub_chars += len(block)
        total_chars += len(block)

    # Assemble neighbor content (LOD 2-4 — signatures/names only)
    # Try LOD compression; fall back to truncated content
    neighbor_chars = 0
    lod_extractor = None
    try:
        from codrag.core.lod_extractor import LODExtractor
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
                    from codrag.core.ids import stable_file_node_id as _sfni
                    file_nid = _sfni(nfp)
                    fnode = trace_idx.get_node(file_nid)
                    if fnode:
                        trace_nodes = [fnode]
                    # Also get symbol nodes in this file
                    for nid_key in list(getattr(trace_idx, '_nodes', {}).keys()):
                        n = trace_idx.get_node(nid_key)
                        if n and n.get("file_path") == nfp and n.get("kind") != "file":
                            trace_nodes.append(n)

                lod_result = lod_extractor.extract(nfp, lod=2, trace_nodes=trace_nodes, repo_root=repo_root)
                if lod_result and lod_result.content and not lod_result.error:
                    lod_content = lod_result.content
            except Exception:
                pass

        if lod_content:
            content = lod_content
            lod_label = "LOD 2"
        elif file_docs:
            # Phase 73: Prefer META_SYNOPSIS over blind truncation
            meta_doc = next((d for d in file_docs if d.get("section") == "META_SYNOPSIS"), None)
            if meta_doc:
                content = str(meta_doc.get("content") or "")
                lod_label = "synopsis"
            else:
                best_doc = max(file_docs, key=lambda d: len(str(d.get("content") or "")))
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
    if not idx.is_loaded():
        raise ApiException(
            status_code=409,
            code="INDEX_NOT_BUILT",
            message="Index has not been built yet",
            hint="Run a build first.",
        )

    # Resolve trace index for trace expansion
    # Phase 34: trace_expand defaults to True. Gracefully degrade if
    # the feature gate blocks it (free tier) or trace isn't available.
    trace_idx = None
    if req.trace_expand:
        try:
            require_feature("mcp_trace_expand")
            cfg = proj.config or {}
            trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
            if bool((trace_cfg or {}).get("enabled", False)):
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

    # ── Phase 34 C4: Ambient context mode (no query) ─────────────
    if not req.query.strip():
        _included = (proj.config or {}).get("included_paths") or []
        return _assemble_ambient_context(
            proj, project_id, idx, trace_idx, _included, max_chars=req.max_chars,
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
        from codrag.core.atlas import CodebaseAtlas, route_query, ROUTING_SEGMENT_BOOST
        from codrag.core.project_registry import project_index_dir
        from codrag.services.project_helpers import require_project
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
        from codrag.server import _get_project_knowledge_index
        from codrag.services.project_helpers import require_project as _rp_know
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

    # ── Phase 67: Agent scope filtering ──────────────────────────
    # If a role is specified and has a configured agent scope, restrict
    # _segment_file_paths to only files within the agent's tree.
    _agent_scope_applied = False
    if req.role:
        try:
            from codrag.core.agent_scope_manager import agent_scope_manager
            _agent_mask = agent_scope_manager.get_agent_mask(project_id, req.role)
            if _agent_mask is not None:
                # Expand directory entries in the mask against indexed documents
                _expanded_mask: Set[str] = set()
                _indexed_paths = set()
                for d in (getattr(idx, '_documents', None) or []):
                    sp = d.get("source_path")
                    if sp:
                        _indexed_paths.add(str(sp))
                for mp in _agent_mask:
                    mp_str = str(mp)
                    if mp_str in _indexed_paths:
                        _expanded_mask.add(mp_str)
                    else:
                        prefix = mp_str.rstrip("/") + "/"
                        for idxp in _indexed_paths:
                            if idxp.startswith(prefix):
                                _expanded_mask.add(idxp)

                if _expanded_mask:
                    if _segment_file_paths is not None:
                        # Intersect: only boost files that are BOTH routed AND in scope
                        _segment_file_paths = _segment_file_paths & _expanded_mask
                    else:
                        # No routing — use agent mask as the boost set directly
                        _segment_file_paths = _expanded_mask
                    _agent_scope_applied = True
                    _sr6_segment_boost = max(_sr6_segment_boost, 0.25)  # Ensure strong boost for scoped agents
                    logger.debug(
                        "Agent scope applied: role=%s files=%d",
                        req.role, len(_segment_file_paths),
                    )
                    if _routing_meta is None:
                        _routing_meta = {}
                    _routing_meta["agent_scope"] = req.role
                    _routing_meta["agent_scope_files"] = len(_expanded_mask)
        except Exception:
            logger.debug("Agent scope filtering unavailable", exc_info=True)

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

        comp = _apply_compression(ctx, req)
        resp: Dict[str, Any] = {"context": comp["context"]}
        if comp["compression"] is not None:
            resp["compression"] = comp["compression"]
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
        return ok(resp)

    # ── SR-2: Knowledge Index content fallback ──────────────────
    # When CodeIndex coverage is sparse (few chunks indexed), supplement
    # search with KnowledgeIndex results. The knowledge index contains
    # LLM-enriched file descriptions that can fill gaps where source
    # code chunks aren't indexed. This is additive — knowledge results
    # appear as supplementary context, not a replacement.
    _knowledge_fallback_chunks: List[Dict[str, Any]] = []
    try:
        from codrag.server import _get_project_knowledge_index
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

        if req.compression in ("none", "lod", "auto"):
            # Phase 34c E1: auto-LOD — structural compression is always applied
            # in the structured+trace path. "none", "lod", and "auto" all trigger it.
            lod_result = _apply_lod_compression(
                result.get("chunks", []), proj, req.query, req.max_chars
            )
            resp_data: Dict[str, Any] = {
                **lod_result,
                "trace_expanded": result.get("trace_expanded", False),
                "trace_nodes_added": result.get("trace_nodes_added", 0),
            }
        else:
            # lingua — skip LOD, apply requested compression
            context_str = str(result.get("context") or "")
            comp = _apply_compression(context_str, req)
            resp_data = {
                "context": comp["context"],
                "chunks": result.get("chunks", []),
                "total_chars": len(comp["context"]),
                "estimated_tokens": len(comp["context"]) // 4,
                "trace_expanded": result.get("trace_expanded", False),
                "trace_nodes_added": result.get("trace_nodes_added", 0),
            }
            if comp["compression"] is not None:
                resp_data["compression"] = comp["compression"]
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
        # Phase 39: Inject relevant observations as session-memory
        resp_data["context"], _obs_meta = _inject_observations(resp_data["context"], project_id, req.query)
        if _obs_meta:
            resp_data["session_memory"] = _obs_meta
            resp_data["total_chars"] = len(resp_data["context"])
            resp_data["estimated_tokens"] = resp_data["total_chars"] // 4
        return ok(resp_data)

    results = idx.search(
        req.query, k=req.k, min_score=req.min_score,
        score_drop_ratio=req.score_drop_ratio, mmr_lambda=req.mmr_lambda,
        exclude_paths=req.exclude_paths or None,
        segment_file_paths=_segment_file_paths,
        segment_boost=_sr6_segment_boost,
    )

    # Phase 34c E1: auto-LOD in structured path (no trace fallback)
    if req.compression in ("none", "lod", "auto"):
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
        lod_result = _apply_lod_compression(raw_chunks, proj, req.query, req.max_chars)
        resp_data: Dict[str, Any] = lod_result
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
        return ok(resp_data)

    parts: List[str] = []
    chunks: List[Dict[str, Any]] = []
    total = 0

    for r in results:
        d = r.doc
        chunk_id = str(d.get("id") or "")
        source_path = str(d.get("source_path") or "")
        section = str(d.get("section") or "")
        span = d.get("span")
        if not isinstance(span, dict) or "start_line" not in span or "end_line" not in span:
            span = {"start_line": 1, "end_line": 1}

        header_bits: List[str] = []
        if section:
            header_bits.append(section)
        if source_path:
            header_bits.append(f"@{source_path}")
        header = " | ".join(header_bits) if header_bits else source_path

        sep = "\n\n---\n\n" if parts else ""
        remaining = int(req.max_chars) - total
        if remaining <= 0 or len(sep) >= remaining:
            break

        prefix = f"[{header}]\n" if header else ""
        allowed = remaining - len(sep)
        if len(prefix) >= allowed:
            break

        text = str(d.get("content") or "")
        if len(prefix) + len(text) > allowed:
            text_allowed = allowed - len(prefix)
            if text_allowed > 200:
                text = text[: max(0, text_allowed - 3)] + "..."
            else:
                break

        block = prefix + text
        parts.append(sep + block)
        total += len(sep) + len(block)
        chunks.append(
            {
                "chunk_id": chunk_id,
                "source_path": source_path,
                "span": span,
                "score": float(r.score),
                "text": text,
            }
        )
        if text.endswith("..."):
            break

    context_str = "".join(parts)

    comp = _apply_compression(context_str, req)
    resp_data: Dict[str, Any] = {
        "context": comp["context"],
        "chunks": chunks,
        "total_chars": len(comp["context"]),
        "estimated_tokens": len(comp["context"]) // 4,
    }
    if comp["compression"] is not None:
        resp_data["compression"] = comp["compression"]
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
    # Phase 39: Inject relevant observations as session-memory
    resp_data["context"], _obs_meta = _inject_observations(resp_data["context"], project_id, req.query)
    if _obs_meta:
        resp_data["session_memory"] = _obs_meta
        resp_data["total_chars"] = len(resp_data["context"])
        resp_data["estimated_tokens"] = resp_data["total_chars"] // 4
    return ok(resp_data)




