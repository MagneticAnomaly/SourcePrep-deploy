"""
TraceIndex — query interface for a built trace graph.

Dual backend: Rust TraceHandle when PREP_ENGINE=rust, else Python dicts.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

# --- Rust engine availability (set in core/__init__.py) ---
try:
    from prep.core import ENGINE as _ENGINE, _rust_engine
except ImportError:
    _ENGINE = "python"
    _rust_engine = None


class TraceIndex:
    """
    Query interface for a built trace index.
    Uses Rust TraceHandle when PREP_ENGINE=rust, else Python dicts.
    """

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir).resolve()
        self.manifest_path = self.index_dir / "trace_manifest.json"
        self.nodes_path = self.index_dir / "trace_nodes.jsonl"
        self.edges_path = self.index_dir / "trace_edges.jsonl"
        self.inferred_edges_path = self.index_dir / "trace_inferred_edges.jsonl"
        self.lsp_edges_path = self.index_dir / "trace_lsp_edges.jsonl"
        self.external_edges_path = self.index_dir / "trace_external_edges.jsonl"

        self._manifest: Optional[Dict[str, Any]] = None
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []
        self._edges_by_source: Dict[str, List[Dict[str, Any]]] = {}
        self._edges_by_target: Dict[str, List[Dict[str, Any]]] = {}
        self._loaded = False
        self._last_mtime: float = 0.0
        self._rust_handle = None  # Rust TraceHandle when using Rust engine

    def exists(self) -> bool:
        return self.manifest_path.exists() and self.nodes_path.exists() and self.edges_path.exists()

    def load(self, force: bool = False) -> bool:
        if not self.exists():
            return False
            
        # Check for staleness
        try:
            current_mtime = self.manifest_path.stat().st_mtime
            if not force and self._loaded and current_mtime <= self._last_mtime:
                return True
            self._last_mtime = current_mtime
        except OSError:
            pass

        if _ENGINE == "rust" and _rust_engine is not None:
            return self._load_rust()

        return self._load_python()

    def _load_rust(self) -> bool:
        """Load trace index via Rust engine — much faster than Python JSONL parsing."""
        try:
            self._rust_handle = _rust_engine.load_trace(str(self.index_dir))
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)
            self._loaded = True
            logger.debug("Loaded trace index via Rust engine: %d nodes", self._rust_handle.node_count())

            # Load external edges (not handled by Rust engine)
            self._edges = []
            self._edges_by_source = {}
            self._edges_by_target = {}
            if self.external_edges_path.exists():
                try:
                    with open(self.external_edges_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                edge = json.loads(line)
                                self._edges.append(edge)
                                src = edge["source"]
                                tgt = edge["target"]
                                self._edges_by_source.setdefault(src, []).append(edge)
                                self._edges_by_target.setdefault(tgt, []).append(edge)
                    # Also load nodes into Python dict for external edge resolution
                    if not self._nodes and self.nodes_path.exists():
                        with open(self.nodes_path, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    node = json.loads(line)
                                    self._nodes[node["id"]] = node
                except Exception as e:
                    logger.warning("Failed to load external edges (Rust engine): %s", e)

            return True
        except Exception as e:
            logger.error(f"Rust engine load failed, falling back to Python: {e}")
            self._rust_handle = None
            return self._load_python()

    def _load_python(self) -> bool:
        """Original Python JSONL loading — used as fallback."""
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)

            self._nodes = {}
            with open(self.nodes_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        node = json.loads(line)
                        self._nodes[node["id"]] = node

            self._edges = []
            self._edges_by_source = {}
            self._edges_by_target = {}
            with open(self.edges_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        edge = json.loads(line)
                        self._edges.append(edge)
                        src = edge["source"]
                        tgt = edge["target"]
                        self._edges_by_source.setdefault(src, []).append(edge)
                        self._edges_by_target.setdefault(tgt, []).append(edge)

            # Load LLM-inferred edges (produced by Stage 1.5)
            if self.inferred_edges_path.exists():
                try:
                    with open(self.inferred_edges_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                edge = json.loads(line)
                                self._edges.append(edge)
                                src = edge["source"]
                                tgt = edge["target"]
                                self._edges_by_source.setdefault(src, []).append(edge)
                                self._edges_by_target.setdefault(tgt, []).append(edge)
                except Exception as e:
                    logger.warning("Failed to load inferred edges: %s", e)

            # W1a: Load LSP edges (posted by IDE extensions)
            if self.lsp_edges_path.exists():
                try:
                    with open(self.lsp_edges_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                edge = json.loads(line)
                                self._edges.append(edge)
                                src = edge["source"]
                                tgt = edge["target"]
                                self._edges_by_source.setdefault(src, []).append(edge)
                                self._edges_by_target.setdefault(tgt, []).append(edge)
                except Exception as e:
                    logger.warning("Failed to load LSP edges: %s", e)

            # Load external edges (posted by external tools like Halbert's config extractor)
            if self.external_edges_path.exists():
                try:
                    with open(self.external_edges_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                edge = json.loads(line)
                                self._edges.append(edge)
                                src = edge["source"]
                                tgt = edge["target"]
                                self._edges_by_source.setdefault(src, []).append(edge)
                                self._edges_by_target.setdefault(tgt, []).append(edge)
                except Exception as e:
                    logger.warning("Failed to load external edges: %s", e)

            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to load trace index: {e}")
            return False

    def is_loaded(self) -> bool:
        return self._loaded

    def node_count(self) -> int:
        """Return total number of nodes in the graph."""
        if not self._loaded:
            self.load()
        if self._rust_handle is not None:
            return self._rust_handle.node_count()
        return len(self._nodes)

    def node_degree(self, node_id: str) -> Tuple[int, int]:
        """Return (in_degree, out_degree) for a node. Works with both Rust and Python backends."""
        if not self._loaded:
            self.load()
        if self._rust_handle is not None:
            result = self._rust_handle.get_neighbors(node_id, direction="both", max_nodes=10000)
            return (len(result.in_edges), len(result.out_edges))
        in_deg = len(self._edges_by_target.get(node_id, []))
        out_deg = len(self._edges_by_source.get(node_id, []))
        return (in_deg, out_deg)

    def status(self) -> Dict[str, Any]:
        engine = _ENGINE if _ENGINE else "python"
        base = {
            "engine": engine,
            "supported_languages": SUPPORTED_LANGUAGES,
        }

        if not self.exists():
            return {
                **base,
                "enabled": True,
                "exists": False,
                "building": False,
                "counts": {"nodes": 0, "edges": 0},
                "last_build_at": None,
                "last_error": None,
                "degraded": False,
                "degraded_reason": None,
            }

        # Always check if we need to reload (checks mtime internally)
        self.load()

        if self._rust_handle is not None:
            rust_status = self._rust_handle.status()
            rust_status.update(base)
            rust_status.setdefault("degraded", False)
            rust_status.setdefault("degraded_reason", None)
            return rust_status

        manifest = self._manifest or {}
        counts = manifest.get("counts") or {}
        node_count = counts.get("nodes", 0)
        edge_count = counts.get("edges", 0)

        # Fallback: if manifest lacks counts (e.g. Rust engine didn't write them),
        # use the actual loaded data
        if node_count == 0 and self._nodes:
            node_count = len(self._nodes)
        if edge_count == 0 and self._edges:
            edge_count = len(self._edges)

        degraded = False
        degraded_reason = None
        if node_count > 0 and edge_count == 0:
            degraded = True
            if engine == "python":
                degraded_reason = (
                    "The Python fallback analyzer only extracts relationships for .py files. "
                    "Install the Rust engine (pip install prep-engine) for full "
                    "TypeScript/JavaScript/Go/Rust/Java/C/C++ analysis."
                )
            else:
                degraded_reason = (
                    "The graph has nodes but no cross-references. "
                    "This project may not have detectable import relationships."
                )

        return {
            **base,
            "enabled": True,
            "exists": True,
            "building": False,
            "counts": {"nodes": node_count, "edges": edge_count},
            "last_build_at": manifest.get("built_at"),
            "last_error": manifest.get("last_error"),
            "degraded": degraded,
            "degraded_reason": degraded_reason,
        }

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        if not self._loaded:
            self.load()
        if self._rust_handle is not None:
            n = self._rust_handle.get_node(node_id)
            return n.to_dict() if n else None
        return self._nodes.get(node_id)

    def search_nodes(self, query: str, kind: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if not self._loaded:
            self.load()

        if self._rust_handle is not None:
            results = self._rust_handle.search(query, kind=kind, limit=limit)
            return [r.to_dict() for r in results]

        query_lower = query.lower()
        results: List[Tuple[float, Dict[str, Any]]] = []

        for node in self._nodes.values():
            if kind and node.get("kind") != kind:
                continue

            name = str(node.get("name", "")).lower()
            qualname = str(node.get("metadata", {}).get("qualname", "")).lower()

            score = 0.0
            if name == query_lower:
                score = 1.0
            elif name.startswith(query_lower):
                score = 0.8
            elif query_lower in name:
                score = 0.6
            elif query_lower in qualname:
                score = 0.4

            if score > 0:
                results.append((score, node))

        results.sort(key=lambda x: (-x[0], x[1].get("file_path", ""), x[1].get("name", "")))
        return [r[1] for r in results[:limit]]

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_kinds: Optional[List[str]] = None,
        max_nodes: int = 50,
    ) -> Dict[str, Any]:
        if not self._loaded:
            self.load()

        if self._rust_handle is not None:
            result = self._rust_handle.get_neighbors(
                node_id, direction=direction, edge_kinds=edge_kinds, max_nodes=max_nodes
            )
            in_edges = [e.to_dict() for e in result.in_edges]
            out_edges = [e.to_dict() for e in result.out_edges]
            in_nodes = [n.to_dict() for n in result.in_nodes]
            out_nodes = [n.to_dict() for n in result.out_nodes]

            # Merge external edges (not stored in Rust engine)
            if direction in ("in", "both"):
                for edge in self._edges_by_target.get(node_id, []):
                    if edge_kinds and edge["kind"] not in edge_kinds:
                        continue
                    if any(e.get("source") == edge["source"] and e.get("kind") == edge["kind"] for e in in_edges):
                        continue
                    in_edges.append(edge)
                    src_node = self._nodes.get(edge["source"])
                    if src_node:
                        in_nodes.append(src_node)
            if direction in ("out", "both"):
                for edge in self._edges_by_source.get(node_id, []):
                    if edge_kinds and edge["kind"] not in edge_kinds:
                        continue
                    if any(e.get("target") == edge["target"] and e.get("kind") == edge["kind"] for e in out_edges):
                        continue
                    out_edges.append(edge)
                    tgt_node = self._nodes.get(edge["target"])
                    if tgt_node:
                        out_nodes.append(tgt_node)

            in_edges = in_edges[:max_nodes]
            out_edges = out_edges[:max_nodes]
            in_nodes = in_nodes[:max_nodes]
            out_nodes = out_nodes[:max_nodes]

            return {
                "in_edges": in_edges,
                "out_edges": out_edges,
                "in_nodes": in_nodes,
                "out_nodes": out_nodes,
            }

        in_edges: List[Dict[str, Any]] = []
        out_edges: List[Dict[str, Any]] = []

        if direction in ("in", "both"):
            for edge in self._edges_by_target.get(node_id, []):
                if edge_kinds and edge["kind"] not in edge_kinds:
                    continue
                in_edges.append(edge)

        if direction in ("out", "both"):
            for edge in self._edges_by_source.get(node_id, []):
                if edge_kinds and edge["kind"] not in edge_kinds:
                    continue
                out_edges.append(edge)

        in_edges = in_edges[:max_nodes]
        out_edges = out_edges[:max_nodes]

        in_nodes = [self._nodes.get(e["source"]) for e in in_edges if self._nodes.get(e["source"])]
        out_nodes = [self._nodes.get(e["target"]) for e in out_edges if self._nodes.get(e["target"])]

        return {
            "in_edges": in_edges,
            "out_edges": out_edges,
            "in_nodes": in_nodes,
            "out_nodes": out_nodes,
        }

    def get_file_skeleton(self, file_path: str, max_symbols: int = 20) -> str:
        """Return a structural skeleton for a file: signatures, classes, exports.

        Uses trace node metadata (symbol_type, qualname, docstring) to build
        a compact overview without implementation bodies.  70-80% token
        reduction compared to raw source chunks.

        Returns empty string if no symbol nodes exist for the file.
        """
        if not self._loaded:
            self.load()

        # Collect symbol nodes for this file
        symbols: List[Dict[str, Any]] = []

        if self._rust_handle is not None:
            # Rust backend: _nodes is empty. Use get_neighbors on the file node
            # to find contained symbols via "contains" edges.
            from prep.core.ids import stable_file_node_id
            file_nid = stable_file_node_id(file_path)
            neighbors = self.get_neighbors(file_nid, direction="out", edge_kinds=["contains"], max_nodes=max_symbols * 2)
            for node in neighbors.get("out_nodes", []):
                if node.get("kind") == "symbol":
                    symbols.append(node)
        else:
            for nid, node_dict in self._nodes.items():
                if node_dict.get("file_path") == file_path and node_dict.get("kind") == "symbol":
                    symbols.append(node_dict)

        if not symbols:
            return ""

        # Sort by span start line for natural order
        symbols.sort(key=lambda s: (s.get("span") or {}).get("start_line", 0))

        lines: List[str] = [f"// @{file_path}"]
        for sym in symbols[:max_symbols]:
            meta = sym.get("metadata") or {}
            stype = meta.get("symbol_type", "")
            qualname = meta.get("qualname") or sym.get("name", "?")
            is_public = meta.get("is_public", True)
            is_async = meta.get("is_async", False)
            docstring = meta.get("docstring", "")

            # Skip private symbols to keep skeleton concise
            if not is_public:
                continue

            prefix = ""
            if stype == "class":
                prefix = "class "
            elif stype in ("function", "method"):
                prefix = "async " if is_async else ""
                prefix += "function " if stype == "function" else ""
            elif stype == "variable":
                prefix = "const "
            elif stype == "interface":
                prefix = "interface "

            line = f"{prefix}{qualname}"

            # Add brief docstring if available
            if docstring:
                brief = docstring.split("\n")[0][:80]
                line += f"  -- {brief}"

            lines.append(line)

        if len(symbols) > max_symbols:
            lines.append(f"... +{len(symbols) - max_symbols} more symbols")

        return "\n".join(lines)

    def get_impact_graph(
        self,
        node_id: str,
        max_hops: int = 2,
        max_nodes: int = 30,
    ) -> Dict[str, Any]:
        """BFS reverse traversal: everything that depends on ``node_id``.

        Follows in-edges only (callers, importers) up to ``max_hops`` hops.
        Returns LOD-compressed result: distance-1 nodes get full signature,
        distance-2+ nodes get file path + name only.

        Returns::

            {
                "target": {node info},
                "dependents": [{"path", "name", "kind", "distance", "signature"}],
                "total_dependents": int,
            }
        """
        if not self._loaded:
            self.load()

        target_node = self._nodes.get(node_id) or {}

        visited: Set[str] = {node_id}
        queue: List[Tuple[str, int]] = [(node_id, 0)]  # (node_id, distance)
        dependents: List[Dict[str, Any]] = []

        while queue and len(dependents) < max_nodes:
            current_id, dist = queue.pop(0)
            if dist >= max_hops:
                continue

            # Get in-edges (callers/importers of current node)
            neighbors = self.get_neighbors(current_id, direction="in", max_nodes=50)
            for edge, node in zip(
                neighbors.get("in_edges", []),
                neighbors.get("in_nodes", []),
            ):
                nid = node.get("id", "")
                if nid in visited:
                    continue
                visited.add(nid)

                fp = node.get("file_path", "")
                name = node.get("name", "")
                kind = edge.get("kind", "")
                meta = node.get("metadata") or {}
                next_dist = dist + 1

                dep_info: Dict[str, Any] = {
                    "path": fp,
                    "name": name,
                    "kind": kind,
                    "distance": next_dist,
                }

                # LOD: distance-1 gets full signature, distance-2+ gets name only
                if next_dist == 1:
                    qualname = meta.get("qualname", name)
                    stype = meta.get("symbol_type", node.get("kind", ""))
                    docstring = (meta.get("docstring") or "")[:80]
                    dep_info["signature"] = qualname
                    dep_info["symbol_type"] = stype
                    if docstring:
                        dep_info["docstring"] = docstring
                else:
                    dep_info["signature"] = name

                dependents.append(dep_info)

                if len(dependents) >= max_nodes:
                    break

                # Enqueue for further traversal
                queue.append((nid, next_dist))

        return {
            "target": {
                "id": node_id,
                "name": target_node.get("name", ""),
                "file_path": target_node.get("file_path", ""),
                "kind": target_node.get("kind", ""),
            },
            "dependents": dependents,
            "total_dependents": len(dependents),
            "max_hops": max_hops,
        }

    def get_hub_files(
        self,
        scope_paths: Optional[Set[str]] = None,
        k: int = 10,
    ) -> List[Tuple[str, int]]:
        """Return top-k hub files by in-degree, optionally scoped to a set of paths.

        Args:
            scope_paths: If provided, only consider files whose path starts with
                         one of these prefixes (files or directories).  Directories
                         should end with ``/`` or be an exact file match.
            k: Maximum number of hub files to return.

        Returns:
            List of ``(file_path, in_degree)`` tuples sorted by descending in-degree.
        """
        if not self._loaded:
            self.load()

        # Compute in-degree per file from edges.
        # Works with both Rust and Python backends by reading edges files
        # directly (Rust backend doesn't populate self._edges_by_target).
        in_degree: Dict[str, int] = {}

        for edge_file in ("trace_edges.jsonl", "trace_inferred_edges.jsonl", "trace_lsp_edges.jsonl"):
            edge_path = self.index_dir / edge_file
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
                            target = d.get("target", "")
                            if target.startswith("file:"):
                                fp = target[5:]
                            else:
                                # Symbol target — resolve to file path via node
                                node = self._nodes.get(target)
                                fp = node.get("file_path") if node else None
                            if fp:
                                in_degree[fp] = in_degree.get(fp, 0) + 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue

        # Scope filter
        if scope_paths:
            exact: Set[str] = set()
            prefixes: List[str] = []
            for sp in scope_paths:
                s = str(sp)
                if s.endswith("/"):
                    prefixes.append(s)
                else:
                    exact.add(s)
                    prefixes.append(s.rstrip("/") + "/")

            def _in_scope(fp: str) -> bool:
                if fp in exact:
                    return True
                return any(fp.startswith(pfx) for pfx in prefixes)

            in_degree = {fp: deg for fp, deg in in_degree.items() if _in_scope(fp)}

        sorted_files = sorted(in_degree.items(), key=lambda x: -x[1])
        return sorted_files[:k]
