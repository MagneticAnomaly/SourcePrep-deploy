"""
Trace graph query endpoints — status, build, coverage, ignore, search, node,
neighbors, impact, lsp-edges, hub_files, file_edges.
"""
from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

# F-70: Dedicated thread pool for API status endpoints.
# The default anyio pool (40 threads) gets exhausted by build workers
# and cloud model calls. This pool is ONLY for fast status reads so
# they never compete with long-running LLM calls.
_api_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="api-status")

from prep.api.envelope import ApiException, ok
from prep.core.events import get_event_bus, get_progress_manager
from prep.core.project_registry import project_index_dir
from prep.core.repo_profile import DEFAULT_EXCLUDE_DIR_NAMES
from prep.core.trace import compute_trace_coverage

from .shared import TraceSearchRequest, TraceIgnoreRequest, LSPEdge, LSPEdgesRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trace"])

# Phase 60D-3: Dedicated thread pool for status/coverage endpoints.
# Prevents LLM workers from starving the API thread pool.
_status_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="trace-status")


@router.get("/projects/{project_id}/trace/status")
async def trace_status_project(project_id: str) -> Dict[str, Any]:
    import asyncio
    from prep.server import _require_project, _project_trace_status
    proj = _require_project(project_id)
    # F-70: Use dedicated _api_executor instead of the default anyio pool.
    # The default pool gets exhausted by build workers and cloud model calls,
    # causing "Loading project..." to stick in the dashboard.
    loop = asyncio.get_running_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(_api_executor, _project_trace_status, proj),
            timeout=3.0,
        )
        return ok(result)
    except asyncio.TimeoutError:
        from prep.services.build_manager import build_manager
        trace_idx = build_manager.get_project_trace_index(proj)
        return ok({
            "enabled": bool((proj.config or {}).get("trace", {}).get("enabled", False)),
            "exists": trace_idx.exists() if trace_idx else False,
            "building": False,
            "counts": {"nodes": trace_idx.node_count() if trace_idx and trace_idx.exists() else 0, "edges": 0},
        })


@router.post("/projects/{project_id}/trace/build")
def build_trace_project(project_id: str) -> Dict[str, Any]:
    from prep.server import (
        _require_project, _is_project_trace_building, _start_project_trace_build, _get_registry
    )
    from prep.services.project_helpers import require_project_writable

    proj = require_project_writable(project_id)

    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None
    if not bool((trace_cfg or {}).get("enabled", False)):
        raise ApiException(
            status_code=409,
            code="TRACE_DISABLED",
            message="Trace is disabled for this project",
            hint="Enable trace in project settings and try again.",
        )

    if _is_project_trace_building(proj.id):
        raise ApiException(status_code=409, code="TRACE_BUILD_ALREADY_RUNNING", message="Trace build already running")

    include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
    exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
    include_globs = list(include_raw) if isinstance(include_raw, list) else None
    exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else None
    max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)

    # Enforce default safety excludes
    current_excludes = set(exclude_globs or [])
    default_excludes = {f"**/{d}/**" for d in DEFAULT_EXCLUDE_DIR_NAMES}

    # Merge user trace-specific ignore patterns (from Exclude Tree / Patterns tab)
    # so they are actually honored during the build, not just in coverage display.
    trace_ignore = (trace_cfg or {}).get("ignore_patterns", [])
    if isinstance(trace_ignore, list):
        current_excludes.update(str(p) for p in trace_ignore if p)

    exclude_globs = sorted(list(current_excludes | default_excludes))

    # Auto-detect stack presets if include_globs is empty or None
    if not include_globs:
        try:
            from prep.core.repo_profile import scan_for_presets, STACK_PRESETS
            detected = scan_for_presets(Path(proj.path))
            if detected:
                logger.info(f"Auto-detected stack presets for {proj.name} during build: {detected}")
                detected_globs = []
                for preset in detected:
                    detected_globs.extend(STACK_PRESETS.get(preset, []))
                
                # Use detected globs and persist to config
                if detected_globs:
                    include_globs = sorted(list(set(detected_globs)))
                    cfg["include_globs"] = include_globs
                    from dataclasses import replace as _replace
                    proj = _replace(proj, config=cfg)
                    _get_registry().update_project(proj.id, config=cfg)
        except Exception as e:
            logger.warning(f"Failed to auto-detect stack presets during trace build: {e}")

    if proj.mode == "embedded":
        if exclude_globs is None:
            exclude_globs = []
        if "**/.runprep/**" not in exclude_globs:
            exclude_globs.append("**/.runprep/**")
        if "**/.sourceprep/**" not in exclude_globs:
            exclude_globs.append("**/.sourceprep/**")

    started = _start_project_trace_build(proj, include_globs, exclude_globs, max_file_bytes=max_file_bytes)
    if not started:
        raise ApiException(status_code=409, code="TRACE_BUILD_ALREADY_RUNNING", message="Trace build already running")
    
    return ok({"started": True, "building": True})


import time as _time

# Phase 72: Coverage result cache — keyed by project ID.
# Returns cached result if fresh enough, otherwise recomputes.
_coverage_cache: Dict[str, Dict[str, Any]] = {}
_coverage_cache_ts: Dict[str, float] = {}
_COVERAGE_CACHE_TTL = 30  # seconds


@router.get("/projects/{project_id}/trace/coverage/summary")
async def trace_coverage_summary_project(project_id: str) -> Dict[str, Any]:
    """Fast endpoint: return cached summary only (no file lists) for progress bars."""
    cached = _coverage_cache.get(project_id)
    if cached:
        return ok({
            "summary": cached.get("summary"),
            "building": cached.get("building", False),
        })
    # No cache — fall through to the full computation (first load)
    full = await trace_coverage_project(project_id)
    # Extract just the summary from the envelope
    data = full.get("data", full)
    return ok({
        "summary": data.get("summary"),
        "building": data.get("building", False),
    })


@router.get("/projects/{project_id}/trace/coverage")
async def trace_coverage_project(project_id: str) -> Dict[str, Any]:
    """Get trace coverage: traced, untraced, stale, and ignored files."""
    import asyncio
    from prep.server import _require_project, _is_project_trace_building
    proj = _require_project(project_id)

    # F-49: this is a READ endpoint — serve disk data regardless of the
    # auto-build preference flag.  Same root-cause class as F-39 (daemon
    # status), F-42 (dashboard pipeline panel): trace.enabled means
    # "auto-rebuild on", not "data exists".  Removing the gate stops the
    # Graph Scope panel from disconnecting on every project that has a
    # built graph but no auto-build flag.
    cfg = proj.config or {}
    trace_cfg = cfg.get("trace") if isinstance(cfg, dict) else None

    # Check cache freshness
    cache_age = _time.time() - _coverage_cache_ts.get(project_id, 0)
    if cache_age < _COVERAGE_CACHE_TTL and project_id in _coverage_cache:
        return ok(_coverage_cache[project_id])

    def _compute_coverage():
        include_raw = cfg.get("include_globs") if isinstance(cfg, dict) else None
        exclude_raw = cfg.get("exclude_globs") if isinstance(cfg, dict) else None
        include_globs = list(include_raw) if isinstance(include_raw, list) else None
        exclude_globs = list(exclude_raw) if isinstance(exclude_raw, list) else None

        # User-configured trace ignore patterns (shown in the "Excluded" list)
        trace_ignore = (trace_cfg or {}).get("ignore_patterns", [])
        user_exclude_globs = [str(p) for p in trace_ignore] if isinstance(trace_ignore, list) else []

        max_file_bytes = int((cfg.get("max_file_bytes") or 500_000) if isinstance(cfg, dict) else 500_000)
        idx_dir = project_index_dir(proj)

        # Get embedded paths from the KNOWLEDGE index (not the code search index).
        embedded_paths: set = set()
        knowledge_docs_path = idx_dir / "knowledge_documents.json"
        if knowledge_docs_path.exists():
            try:
                import json as _json
                with open(knowledge_docs_path, "r", encoding="utf-8") as _f:
                    for doc in _json.load(_f):
                        src = doc.get("source_id") or ""
                        if not src:
                            continue
                        if src.startswith("file:"):
                            embedded_paths.add(src[5:])
                        elif src.startswith("sym:"):
                            at_idx = src.find("@")
                            if at_idx >= 0:
                                rest = src[at_idx + 1:]
                                colon_idx = rest.rfind(":")
                                if colon_idx > 0:
                                    embedded_paths.add(rest[:colon_idx])
                                else:
                                    embedded_paths.add(rest)
                        else:
                            embedded_paths.add(src)
            except Exception:
                pass

        coverage = compute_trace_coverage(
            repo_root=Path(proj.path),
            index_dir=idx_dir,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
            user_exclude_globs=user_exclude_globs,
            max_file_bytes=max_file_bytes,
            embedded_paths=embedded_paths,
        )
        coverage["building"] = _is_project_trace_building(proj.id)
        return coverage

    loop = asyncio.get_running_loop()
    coverage = await loop.run_in_executor(_status_executor, _compute_coverage)
    # Update cache
    _coverage_cache[project_id] = coverage
    _coverage_cache_ts[project_id] = _time.time()
    return ok(coverage)


@router.post("/projects/{project_id}/trace/ignore")
def update_trace_ignore(project_id: str, req: TraceIgnoreRequest) -> Dict[str, Any]:
    """Add or remove trace-specific ignore patterns."""
    from prep.server import _require_project, _get_registry
    proj = _require_project(project_id)

    if req.action not in ("add", "remove"):
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="action must be 'add' or 'remove'")
    if not req.patterns:
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="patterns list is required")

    reg = _get_registry()

    # Atomic read-modify-write: if another endpoint (e.g. PUT
    # /included_paths) writes to this project's config concurrently, the
    # old `proj.config` snapshot + full-config replace pattern would
    # silently drop one side's field. mutate_config reads and writes
    # inside a single SQLite transaction, so only trace.ignore_patterns
    # is touched here and concurrent writers' fields survive.
    def _apply(current_cfg: Dict[str, Any]) -> Dict[str, Any]:
        new_cfg = dict(current_cfg)
        trace_cfg = dict(new_cfg.get("trace") or {})
        current_patterns: List[str] = list(trace_cfg.get("ignore_patterns") or [])
        if req.action == "add":
            for p in req.patterns:
                p = str(p).strip()
                if p and p not in current_patterns:
                    current_patterns.append(p)
        else:
            remove_set = set(str(p).strip() for p in req.patterns)
            current_patterns = [p for p in current_patterns if p not in remove_set]
        trace_cfg["ignore_patterns"] = current_patterns
        new_cfg["trace"] = trace_cfg
        return new_cfg

    reg.mutate_config(proj.id, _apply)
    # Re-read to surface the final pattern list in the response
    updated = reg.get_project(proj.id)
    current_patterns = list(
        ((updated.config if updated else {}) or {}).get("trace", {}).get("ignore_patterns") or []
    )

    # Invalidate coverage cache so next fetch reflects new exclusions
    _coverage_cache.pop(project_id, None)
    _coverage_cache_ts.pop(project_id, None)

    # P48-F34: If a pipeline is running, trigger hot scope reload so the
    # new patterns take effect immediately (pause → rebuild trace → resume).
    reload_result = None
    try:
        from prep.services.pipeline_orchestrator import pipeline_orchestrator
        reload_result = pipeline_orchestrator.hot_scope_reload(project_id)
        if reload_result.get("reloaded"):
            logger.info(
                "Hot scope reload for %s: rebuilt trace with %d nodes (was at stage %s)",
                project_id, reload_result.get("new_node_count", "?"),
                reload_result.get("paused_stage", "?"),
            )
    except Exception:
        logger.debug("Hot scope reload failed (non-fatal)", exc_info=True)

    # GS-2/GS-3: prune orphan enrichments after scope change
    prune_result = None
    try:
        from prep.core.trace import prune_orphan_enrichments
        idx_dir = project_index_dir(proj)
        prune_result = prune_orphan_enrichments(idx_dir)
    except Exception:
        logger.debug("Orphan prune after scope change failed (non-fatal)", exc_info=True)

    return ok({
        "ignore_patterns": current_patterns,
        "scope_reloaded": reload_result.get("reloaded", False) if reload_result else False,
        "orphans_pruned": prune_result.get("total_pruned", 0) if prune_result else 0,
    })


@router.get("/projects/{project_id}/trace/search")
def search_trace_project(project_id: str, query: str, kind: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    from prep.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)
    
    if not query.strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    # F-49: read endpoint — TRACE_NOT_BUILT below already covers the
    # "no data on disk" case; the auto-build preference flag isn't a
    # data-presence check (see F-39, F-42).
    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(
            status_code=409,
            code="TRACE_NOT_BUILT",
            message="Trace index has not been built yet",
            hint="Run a trace build first.",
        )

    if not trace_idx.is_loaded():
        trace_idx.load()

    results = trace_idx.search_nodes(query, kind=kind, limit=min(limit, 100))
    return ok({"nodes": results})


@router.post("/projects/{project_id}/trace/search")
def trace_search_project(project_id: str, req: TraceSearchRequest) -> Dict[str, Any]:
    from prep.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)

    if not str(req.query or "").strip():
        raise ApiException(status_code=400, code="VALIDATION_ERROR", message="query is required")

    # F-49: read endpoint — see trace_search above
    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(
            status_code=409,
            code="TRACE_NOT_BUILT",
            message="Trace index has not been built yet",
            hint="Run a trace build first.",
        )

    if not trace_idx.is_loaded():
        trace_idx.load()

    hard_cap = 100
    limit = min(int(req.limit or 0) if req.limit is not None else 20, hard_cap)
    if limit <= 0:
        limit = 20

    nodes = trace_idx.search_nodes(req.query, kind=None, limit=hard_cap)
    if isinstance(req.kinds, list) and req.kinds:
        kinds = {str(k).strip() for k in req.kinds if isinstance(k, str) and k.strip()}
        if kinds:
            nodes = [n for n in nodes if str(n.get("kind") or "") in kinds]
    nodes = nodes[:limit]

    return ok({"nodes": nodes})


@router.get("/projects/{project_id}/trace/node/{node_id:path}")
@router.get("/projects/{project_id}/trace/nodes/{node_id:path}")
def get_trace_node(project_id: str, node_id: str) -> Dict[str, Any]:
    from prep.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)

    # F-49: read endpoint — see trace_search above
    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(status_code=409, code="TRACE_NOT_BUILT", message="Trace index has not been built yet")
    
    if not trace_idx.is_loaded():
        trace_idx.load()
    
    node = trace_idx.get_node(node_id)
    if node is None:
        raise ApiException(status_code=404, code="NODE_NOT_FOUND", message=f"Node not found: {node_id}")
    
    in_degree, out_degree = trace_idx.node_degree(node_id)
    return ok({"node": node, "in_degree": in_degree, "out_degree": out_degree})


@router.get("/projects/{project_id}/trace/neighbors/{node_id:path}")
@router.get("/projects/{project_id}/trace/nodes/{node_id:path}/neighbors")
def get_trace_node_neighbors(
    project_id: str,
    node_id: str,
    direction: str = "both",
    edge_kinds: Optional[List[str]] = Query(None),
    hops: int = 1,
    max_nodes: int = 25,
    max_edges: int = 50,
) -> Dict[str, Any]:
    from prep.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)

    # F-49: read endpoint — see trace_search above
    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(status_code=409, code="TRACE_NOT_BUILT", message="Trace index has not been built yet")

    if not trace_idx.is_loaded():
        trace_idx.load()

    node = trace_idx.get_node(node_id)
    if node is None:
        raise ApiException(status_code=404, code="NODE_NOT_FOUND", message=f"Node not found: {node_id}")
    
    edge_kinds_list: Optional[List[str]] = None
    if edge_kinds:
        cleaned: List[str] = []
        for v in edge_kinds:
            for part in str(v).split(","):
                p = part.strip()
                if p:
                    cleaned.append(p)
        edge_kinds_list = cleaned or None

    if edge_kinds_list is None:
        edge_kinds_list = ["imports"]

    neighbors = trace_idx.get_neighbors(
        node_id,
        direction=direction,
        edge_kinds=edge_kinds_list,
        max_nodes=min(max_nodes, 100),
    )

    edges: List[Dict[str, Any]] = []
    seen_edges: set[str] = set()
    for e in list(neighbors.get("in_edges") or []) + list(neighbors.get("out_edges") or []):
        eid = str(e.get("id") or "")
        if eid and eid in seen_edges:
            continue
        if eid:
            seen_edges.add(eid)
        edges.append(e)

    max_edges_cap = 200
    edges = edges[: min(int(max_edges), max_edges_cap)] if int(max_edges) > 0 else edges[:50]

    nodes_out: List[Dict[str, Any]] = []
    seen_nodes: set[str] = set()
    for n in [node] + list(neighbors.get("in_nodes") or []) + list(neighbors.get("out_nodes") or []):
        nid = str((n or {}).get("id") or "")
        if not nid or nid in seen_nodes:
            continue
        seen_nodes.add(nid)
        nodes_out.append(n)

    return ok({"nodes": nodes_out, "edges": edges})


# ═════════════════════════════════════════════════════════════════
# W4a: Impact Graph (Phase 39 — "what breaks if I change X?")
# ═════════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/trace/impact/{node_id:path}")
def get_trace_impact(
    project_id: str,
    node_id: str,
    max_hops: int = 2,
    max_nodes: int = 30,
) -> Dict[str, Any]:
    """Return the reverse-dependency (impact) graph for a node.

    BFS traversal following in-edges (callers, importers) to answer
    "what depends on this?" and "what's the blast radius of changing this?"
    """
    from prep.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)

    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(status_code=409, code="TRACE_NOT_BUILT", message="Trace index has not been built yet")

    if not trace_idx.is_loaded():
        trace_idx.load()

    node = trace_idx.get_node(node_id)
    if node is None:
        raise ApiException(status_code=404, code="NODE_NOT_FOUND", message=f"Node not found: {node_id}")

    result = trace_idx.get_impact_graph(
        node_id,
        max_hops=min(max_hops, 4),
        max_nodes=min(max_nodes, 100),
    )
    return ok(result)


# ═════════════════════════════════════════════════════════════════
# W1a: LSP Edge Ingestion (Phase 39 — IDE-sourced type-resolved edges)
# ═════════════════════════════════════════════════════════════════

@router.post("/projects/{project_id}/trace/lsp-edges")
def ingest_lsp_edges(
    project_id: str,
    req: LSPEdgesRequest,
) -> Dict[str, Any]:
    """Accept type-resolved call-graph edges from the user's IDE Language Server.

    Edges are validated (source/target must be known file nodes), deduped
    against existing edges, and appended to ``trace_lsp_edges.jsonl``.
    The TraceIndex picks them up on next load.
    """
    from prep.server import _require_project, _get_project_trace_index

    proj = _require_project(project_id)
    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists():
        raise ApiException(
            status_code=409, code="TRACE_NOT_BUILT",
            message="Trace index has not been built yet",
        )
    if not trace_idx.is_loaded():
        trace_idx.load()

    idx_dir = project_index_dir(proj)
    lsp_path = idx_dir / "trace_lsp_edges.jsonl"

    # Load existing LSP edges for dedup
    existing: set = set()
    if lsp_path.exists():
        try:
            with open(lsp_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        e = json.loads(line)
                        existing.add((e.get("source", ""), e.get("target", ""), e.get("kind", "")))
        except (OSError, json.JSONDecodeError):
            pass

    accepted = 0
    rejected_unknown = 0
    rejected_dup = 0

    new_edges: List[Dict[str, Any]] = []
    for edge in req.edges:
        # Validate source/target are known nodes
        src_node = trace_idx.get_node(edge.source)
        tgt_node = trace_idx.get_node(edge.target)
        if src_node is None or tgt_node is None:
            rejected_unknown += 1
            continue

        # Dedup
        key = (edge.source, edge.target, edge.kind)
        if key in existing:
            rejected_dup += 1
            continue

        existing.add(key)
        new_edges.append({
            "source": edge.source,
            "target": edge.target,
            "kind": edge.kind,
            "origin": "lsp",
            **({"metadata": edge.metadata} if edge.metadata else {}),
        })
        accepted += 1

    # Append new edges
    if new_edges:
        with open(lsp_path, "a", encoding="utf-8") as f:
            for e in new_edges:
                f.write(json.dumps(e) + "\n")

    return ok({
        "accepted": accepted,
        "rejected_unknown_node": rejected_unknown,
        "rejected_duplicate": rejected_dup,
        "total_lsp_edges": len(existing),
    })


# ═════════════════════════════════════════════════════════════════
# Hub Files & File Edges (Phase 32 — hi_prep enhancements)
# ═════════════════════════════════════════════════════════════════

@router.get("/projects/{project_id}/trace/hub_files")
def get_trace_hub_files(
    project_id: str,
    k: int = 5,
    scope_paths: Optional[List[str]] = Query(None),
) -> Dict[str, Any]:
    """Return top-k hub files (highest in-degree) from the trace graph.

    Optionally scoped to a set of file/directory paths.
    """
    from prep.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)

    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists() or not trace_idx.is_loaded():
        return ok({"hub_files": []})

    scope_set: Optional[set] = None
    if scope_paths:
        cleaned: List[str] = []
        for v in scope_paths:
            for part in str(v).split(","):
                p = part.strip()
                if p:
                    cleaned.append(p)
        scope_set = set(cleaned) if cleaned else None

    hubs = trace_idx.get_hub_files(scope_paths=scope_set, k=min(k, 20))
    return ok({"hub_files": [{"path": p, "in_degree": d} for p, d in hubs]})


@router.get("/projects/{project_id}/trace/file_edges")
def get_trace_file_edges(
    project_id: str,
    paths: List[str] = Query(...),
    max_edges: int = 30,
) -> Dict[str, Any]:
    """Return trace edges between a set of files.

    Only returns edges where both source and target are in the given paths set.
    Used by hi_prep to show cross-file relationships.
    """
    from prep.server import _require_project, _get_project_trace_index
    proj = _require_project(project_id)

    trace_idx = _get_project_trace_index(proj)
    if not trace_idx.exists() or not trace_idx.is_loaded():
        return ok({"edges": []})

    # Normalize paths
    path_set: set = set()
    for v in paths:
        for part in str(v).split(","):
            p = part.strip()
            if p:
                path_set.add(p)

    if not path_set:
        return ok({"edges": []})

    # Read edges and filter to those between the given file set
    import json as _json
    edges: List[Dict[str, str]] = []
    for edge_file in ("trace_edges.jsonl", "trace_inferred_edges.jsonl"):
        edge_path = trace_idx.index_dir / edge_file
        if not edge_path.exists():
            continue
        try:
            with open(edge_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = _json.loads(line)
                        src = d.get("source", "")
                        tgt = d.get("target", "")
                        kind = d.get("kind", "imports")

                        # Resolve to file paths
                        src_fp = src[5:] if src.startswith("file:") else None
                        tgt_fp = tgt[5:] if tgt.startswith("file:") else None

                        if src_fp is None:
                            node = trace_idx._nodes.get(src)
                            src_fp = node.get("file_path") if node else None
                        if tgt_fp is None:
                            node = trace_idx._nodes.get(tgt)
                            tgt_fp = node.get("file_path") if node else None

                        if src_fp and tgt_fp and src_fp in path_set and tgt_fp in path_set and src_fp != tgt_fp:
                            edges.append({"source": src_fp, "target": tgt_fp, "kind": kind})
                            if len(edges) >= max_edges:
                                break
                    except _json.JSONDecodeError:
                        continue
        except OSError:
            continue
        if len(edges) >= max_edges:
            break

    # Deduplicate (same source→target pair, keep first)
    seen: set = set()
    unique: List[Dict[str, str]] = []
    for e in edges:
        key = f"{e['source']}→{e['target']}"
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return ok({"edges": unique})


# ═════════════════════════════════════════════════════════════════
# Augmentation (Pass 1)
# ═════════════════════════════════════════════════════════════════

