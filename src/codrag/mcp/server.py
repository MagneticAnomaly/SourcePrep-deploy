"""
MCPServer — the main MCP server class with tool implementations,
project resolution, and protocol handling.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from logging.handlers import RotatingFileHandler
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .errors import (
    MCPError,
    MethodNotFoundError,
    InvalidParamsError,
    DaemonUnavailableError,
    DaemonError,
    IndexNotReadyError,
    BuildInProgressError,
    ProjectNotFoundError,
    ProjectSelectionAmbiguousError,
)

logger = logging.getLogger(__name__)


def configure_logging(*, debug: bool = False, log_file: Optional[str] = None) -> None:
    stderr_level = logging.DEBUG if debug else logging.WARNING
    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr:
            h.setLevel(stderr_level)

    if log_file:
        path = Path(str(log_file)).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        for h in root.handlers:
            if isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == str(path):
                break
        else:
            fh = RotatingFileHandler(str(path), maxBytes=1_000_000, backupCount=3)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            root.addHandler(fh)

    root.setLevel(logging.DEBUG if (debug or log_file) else logging.WARNING)
    logger.setLevel(logging.DEBUG if (debug or log_file) else logging.WARNING)


# =============================================================================
# MCP Protocol Constants (spec 2025-11-25)
# =============================================================================

MCP_PROTOCOL_VERSION = "2025-11-25"
JSONRPC_VERSION = "2.0"

# Error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# CoDRAG-specific error codes
DAEMON_UNAVAILABLE = -32000
INDEX_NOT_READY = -32001
BUILD_IN_PROGRESS = -32002
PROJECT_NOT_FOUND = -32003
PROJECT_SELECTION_AMBIGUOUS = -32004

MAX_SEARCH_K = 50
MAX_CONTEXT_K = 50
MAX_CONTEXT_CHARS = 20_000


from codrag.mcp_tools import TOOLS

# =============================================================================
# Tool Definitions
# =============================================================================

# Imported from mcp_tools.py


# =============================================================================
# MCP Server Implementation
# =============================================================================

class MCPServer:
    """
    CoDRAG MCP Server.
    
    Communicates with the CoDRAG daemon via HTTP API.
    """

    def __init__(
        self,
        daemon_url: str = "http://127.0.0.1:8400",
        project_id: Optional[str] = None,
        auto_detect: bool = False,
    ):
        self.daemon_url = daemon_url.rstrip("/")
        self.project_id = project_id
        self.auto_detect = auto_detect
        self._client: Optional[httpx.AsyncClient] = None
        self._resolved_project_id: Optional[str] = None
        self._resolved_project_cwd: Optional[str] = None
        self._initialize_roots: List[str] = []
        self._client_name: str = "unknown"      # Phase 50: set by handle_initialize
        self._client_version: str = ""           # Phase 50: set by handle_initialize
        self._codrag_called: bool = False        # Phase 50 Sprint 3: nudge tracker

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _unwrap_envelope(self, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        if "success" not in payload or "data" not in payload:
            return payload
        if payload.get("success") is True:
            return payload.get("data")
        err = payload.get("error")
        if isinstance(err, dict):
            code = str(err.get("code") or "ERROR")
            message = str(err.get("message") or "Request failed")
            hint = err.get("hint")
            text = f"{code}: {message}"
            if hint:
                text = f"{text} (hint: {hint})"
            if code == "PROJECT_NOT_FOUND":
                raise ProjectNotFoundError(text)
            if code in ("INDEX_NOT_BUILT", "INDEX_NOT_READY"):
                raise IndexNotReadyError(text)
            if code in ("BUILD_ALREADY_RUNNING", "TRACE_BUILD_ALREADY_RUNNING"):
                raise BuildInProgressError(text)
            raise DaemonError(text)
        raise DaemonError("Request failed")

    async def _api_get(self, path: str) -> Any:
        """GET request to daemon API."""
        client = await self._get_client()
        if not path.startswith("/"):
            path = "/" + path
        url = f"{self.daemon_url}{path}"
        logger.debug(f"GET {url}")
        
        # SECURITY: Include IPC token if daemon requires authentication
        headers: Dict[str, str] = {}
        ipc_token = os.environ.get("CODRAG_DAEMON_TOKEN")
        if ipc_token:
            headers["Authorization"] = f"Bearer {ipc_token}"
        
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.ConnectError:
            raise DaemonUnavailableError(f"Cannot connect to CoDRAG daemon at {self.daemon_url}")
        except httpx.HTTPStatusError as e:
            try:
                self._unwrap_envelope(e.response.json())
            except DaemonError as de:
                raise de
            except Exception:
                pass
            raise DaemonError(f"Daemon returned {e.response.status_code}: {e.response.text}")

        try:
            payload = resp.json()
        except Exception:
            raise DaemonError(f"Daemon returned invalid JSON: {resp.text}")
        return self._unwrap_envelope(payload)

    async def _api_post(self, path: str, payload: Dict[str, Any]) -> Any:
        """POST request to daemon API."""
        client = await self._get_client()
        if not path.startswith("/"):
            path = "/" + path
        url = f"{self.daemon_url}{path}"
        logger.debug(f"POST {url} payload_keys={list(payload.keys())}")
        
        # SECURITY: Include IPC token if daemon requires authentication
        headers: Dict[str, str] = {}
        ipc_token = os.environ.get("CODRAG_DAEMON_TOKEN")
        if ipc_token:
            headers["Authorization"] = f"Bearer {ipc_token}"
        
        try:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        except httpx.ConnectError:
            raise DaemonUnavailableError(f"Cannot connect to CoDRAG daemon at {self.daemon_url}")
        except httpx.HTTPStatusError as e:
            try:
                self._unwrap_envelope(e.response.json())
            except DaemonError as de:
                raise de
            except Exception:
                pass
            raise DaemonError(f"Daemon returned {e.response.status_code}: {e.response.text}")

        try:
            payload_out = resp.json()
        except Exception:
            raise DaemonError(f"Daemon returned invalid JSON: {resp.text}")
        return self._unwrap_envelope(payload_out)

    def _best_project_match(
        self, projects: List[Dict[str, Any]], paths: List[str]
    ) -> Optional[str]:
        """Return the project_id whose root is the longest prefix of any path, or None.

        Returns None if zero matches or if multiple projects tie at the same
        prefix length (ambiguous).
        """
        best_id: Optional[str] = None
        best_len = -1
        ambiguous = False

        for p in projects:
            pid = p.get("id")
            p_path = str(p.get("path") or "").rstrip("/")
            if not pid or not p_path:
                continue
            for check_path in paths:
                check = check_path.rstrip("/")
                if not check:
                    check = "/"
                    
                score = -1
                if check == p_path:
                    # Exact match gets highest priority
                    score = 10000 + len(p_path)
                elif check.startswith(p_path + "/"):
                    # Check path is a subfolder of the project
                    score = 1000 + len(p_path)
                elif p_path.startswith(check + "/"):
                    # Project is a subfolder of the check path
                    score = len(check)
                elif check == "/" and p_path:
                    # If check is root, all projects technically match as children
                    score = 1

                if score > -1:
                    if score > best_len:
                        best_id = str(pid)
                        best_len = score
                        ambiguous = False
                    elif score == best_len and str(pid) != best_id:
                        ambiguous = True

        if ambiguous:
            return None
        return best_id

    async def _resolve_project_id(self, override: Optional[str] = None) -> str:
        """Resolve which project to target.

        Priority:
          1. Explicit override (from tool call ``project_id`` param)
          2. Pinned project (from CLI ``--project`` flag)
          3. MCP initialize roots (workspace URIs sent by the IDE)
          4. CWD auto-detect (process working directory)
          5. Single-project shortcut
        """
        # 1. Tool-call override
        if override and override.strip():
            return override.strip()

        # 2. CLI pinned
        if self.project_id:
            return self.project_id

        # 3-4. Cache hit (roots + CWD haven't changed)
        cwd = str(Path.cwd().resolve())
        cache_key = (tuple(self._initialize_roots), cwd)
        if self._resolved_project_id and getattr(self, "_cache_key", None) == cache_key:
            return self._resolved_project_id

        # Fetch all projects from daemon
        data = await self._api_get("/projects")
        all_projects: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            raw = data.get("projects")
            if isinstance(raw, list):
                all_projects = [p for p in raw if isinstance(p, dict)]

        # Filter out locked/frozen projects — MCP only serves active projects.
        # On paid tiers all projects are "active" (unless manually deactivated).
        # On Free tier only the most recent project is "active".
        projects = [
            p for p in all_projects
            if p.get("activity_status", "active") in ("active", "inactive")
        ]

        if not projects:
            raise ProjectNotFoundError(
                "No projects configured in CoDRAG daemon. "
                "Add one with: codrag add /path/to/your/repo"
            )

        def _project_lines() -> str:
            lines: List[str] = []
            for p in projects:
                pid = str(p.get("id") or "").strip()
                if not pid:
                    continue
                name = str(p.get("name") or "").strip() or "(unnamed)"
                path = str(p.get("path") or "").strip()
                lines.append(f"  - {pid}: {name} ({path})")
            return "\n".join(lines)

        # 3. Try initialize roots (workspace URIs from the IDE)
        if self._initialize_roots:
            pid = self._best_project_match(projects, self._initialize_roots)
            if pid:
                self._resolved_project_id = pid
                self._cache_key = cache_key
                logger.debug(f"Resolved project from initialize roots: {pid}")
                return pid

        # 4. CWD auto-detect (always attempted, not gated on --auto)
        pid = self._best_project_match(projects, [cwd])
        if pid:
            self._resolved_project_id = pid
            self._cache_key = cache_key
            logger.debug(f"Auto-detected project from CWD: {pid} cwd={cwd}")
            return pid

        # 5. Single-project shortcut
        if len(projects) == 1 and projects[0].get("id"):
            pid = str(projects[0]["id"])
            self._resolved_project_id = pid
            self._cache_key = cache_key
            return pid

        # No match — return actionable error with full project list
        msg = (
            "PROJECT_SELECTION_AMBIGUOUS: Could not automatically determine which project to use.\n"
            f"cwd: {cwd}\n"
        )
        if self._initialize_roots:
            msg += f"workspace roots: {self._initialize_roots}\n"
        msg += (
            "\nAvailable projects:\n"
            + _project_lines()
            + "\n\nACTION REQUIRED: You must explicitly specify which project to use. "
            "Look at the 'Available projects' list above, find the project whose path matches the codebase you are currently working in, "
            "and call THIS EXACT SAME tool again, but this time include the 'project_id' parameter with the correct ID."
        )
        raise ProjectSelectionAmbiguousError(msg)

    # -------------------------------------------------------------------------
    # Tool Implementations
    # -------------------------------------------------------------------------

    async def tool_status(self, project_override: Optional[str] = None) -> Dict[str, Any]:
        """Get index status."""
        project_id = await self._resolve_project_id(override=project_override)
        data = await self._api_get(f"/projects/{project_id}/status")

        # Lean output for token efficiency
        index = (data or {}).get("index", {}) if isinstance(data, dict) else {}
        result: Dict[str, Any] = {
            "project_id": project_id,
            "daemon": "running",
            "index_loaded": bool(index.get("exists", False)),
            "total_documents": int(index.get("total_chunks") or 0),
            "model": index.get("embedding_model", "unknown"),
            "built_at": index.get("last_build_at"),
            "building": bool((data or {}).get("building", False) if isinstance(data, dict) else False),
            "watch_enabled": bool(
                (((data or {}).get("watch") or {}).get("enabled", False) if isinstance(data, dict) else False)
            ),
        }

        # When no project_override was given, also list all projects so the AI
        # can see what's available (useful for multi-project setups).
        if not project_override and not self.project_id:
            try:
                pdata = await self._api_get("/projects")
                plist = []
                for p in (pdata or {}).get("projects", []) if isinstance(pdata, dict) else []:
                    if isinstance(p, dict) and p.get("id"):
                        plist.append({"id": p["id"], "name": p.get("name", ""), "path": p.get("path", "")})
                if len(plist) > 1:
                    result["available_projects"] = plist
            except Exception:
                pass  # Non-critical

        return result

    async def tool_build(self, full: bool = False, project_override: Optional[str] = None) -> Dict[str, Any]:
        """Trigger index build."""
        project_id = await self._resolve_project_id(override=project_override)
        path = f"/projects/{project_id}/build"
        if full:
            path = f"{path}?full=true"

        try:
            data = await self._api_post(path, {})
        except BuildInProgressError:
            return {"status": "already_building", "message": "A build is already in progress."}

        if isinstance(data, dict) and data.get("started"):
            return {"project_id": project_id, "status": "started", "message": "Index build started. Use codrag_status to check progress."}
        return {"project_id": project_id, "status": "unknown", "data": data}

    async def tool_search(
        self,
        query: str,
        k: int = 5,
        max_chars: int = 12000,
        trace_expand: bool = True,
        compression: str = "none",
        compression_level: str = "standard",
        compression_timeout_s: float = 30.0,
        exclude_paths: Optional[List[str]] = None,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query-based context retrieval with trace expansion and routing."""
        if not query.strip():
            raise InvalidParamsError("query is required")

        try:
            k = int(k)
        except Exception:
            raise InvalidParamsError("k must be an integer")
        if k < 1:
            raise InvalidParamsError("k must be >= 1")
        if k > MAX_CONTEXT_K:
            raise InvalidParamsError(f"k too large (max {MAX_CONTEXT_K})")

        try:
            max_chars = int(max_chars)
        except Exception:
            raise InvalidParamsError("max_chars must be an integer")
        if max_chars < 1:
            raise InvalidParamsError("max_chars must be >= 1")
        if max_chars > MAX_CONTEXT_CHARS:
            raise InvalidParamsError(f"max_chars too large (max {MAX_CONTEXT_CHARS})")

        if compression not in ("none", "lingua", "auto"):
            raise InvalidParamsError("compression must be 'none', 'lingua', or 'auto'")
        if compression_level not in ("light", "standard", "aggressive"):
            raise InvalidParamsError("compression_level must be 'light', 'standard', or 'aggressive'")

        project_id = await self._resolve_project_id(override=project_override)
        # OPP-W3: Request augmented summaries alongside source content
        payload: Dict[str, Any] = {
            "query": query,
            "k": k,
            "max_chars": max_chars,
            "include_sources": True,
            "include_scores": False,
            "structured": True,
            "trace_expand": bool(trace_expand),
        }
        if compression != "none":
            payload["compression"] = compression
            payload["compression_level"] = compression_level
            payload["compression_timeout_s"] = float(compression_timeout_s)
        if exclude_paths:
            payload["exclude_paths"] = list(exclude_paths)

        data = await self._api_post(f"/projects/{project_id}/context", payload)
        result = self._format_context_response(project_id, data)

        # Phase 50 Sprint 3: Markdown output for search results.
        context_str = result.get("context", "")

        # OPP-W2: Per-subsystem deep dive. If search results cluster in
        # a specific directory, try to include a brief subsystem orientation.
        subsystem_hint = ""
        if isinstance(data, dict):
            sources = data.get("sources", [])
            if isinstance(sources, list) and sources:
                # Detect dominant directory from source paths
                dir_counts: Dict[str, int] = {}
                for src in sources:
                    path = src.get("file_path", "") if isinstance(src, dict) else ""
                    if "/" in path:
                        top_dir = path.split("/")[0]
                        dir_counts[top_dir] = dir_counts.get(top_dir, 0) + 1
                if dir_counts:
                    top_dir, top_count = max(dir_counts.items(), key=lambda x: x[1])
                    # If >60% of results are in one directory, add subsystem hint
                    if top_count >= len(sources) * 0.6 and top_count >= 2:
                        subsystem_hint = f"\n[Subsystem focus: {top_dir}/ -- {top_count}/{len(sources)} results in this area]\n"

        if context_str:
            result["_to_markdown"] = subsystem_hint + context_str if subsystem_hint else context_str
        else:
            result["_to_markdown"] = f"No results found for: {query}"

        return result

    async def tool_context(
        self,
        max_chars: int = 12000,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ambient context assembly — no query needed.

        Phase 50 ISSUE-3: If the index hasn't been built yet, returns a
        helpful onboarding response (isError=False) instead of an error.
        This prevents the AI from learning to avoid CoDRAG after a failed
        first attempt.
        """
        try:
            max_chars = int(max_chars)
        except Exception:
            raise InvalidParamsError("max_chars must be an integer")
        if max_chars < 1:
            raise InvalidParamsError("max_chars must be >= 1")
        if max_chars > MAX_CONTEXT_CHARS:
            raise InvalidParamsError(f"max_chars too large (max {MAX_CONTEXT_CHARS})")

        project_id = await self._resolve_project_id(override=project_override)
        # OPP-W1: Request extended atlas in tool response. The compact atlas
        # is always-on in rules files (~300 tok). The extended atlas (~2-4K tok)
        # is only included when the AI explicitly calls codrag, taking advantage
        # of larger context windows (200K+ tokens in modern models).
        payload: Dict[str, Any] = {
            "query": "",
            "max_chars": max_chars,
            "include_atlas": True,
        }

        try:
            data = await self._api_post(f"/projects/{project_id}/context", payload)
        except IndexNotReadyError:
            # Phase 50 ISSUE-3: Graceful first-run response.
            setup_md = (
                "## CoDRAG (setup in progress)\n\n"
                "The codebase index hasn't been built yet. "
                "CoDRAG needs to scan your code before it can provide structural context.\n\n"
                "To build the index:\n"
                "1. Open the CoDRAG dashboard (http://localhost:8400)\n"
                "2. Click 'Rebuild Knowledge Base'\n"
                "-- OR run: codrag build\n\n"
                "Once built, call `codrag` again for module structure, hub files, "
                "and structural relationships.\n\n"
                "For now, work with the code directly using read_file and grep_search."
            )
            return {
                "project_id": project_id,
                "setup_in_progress": True,
                "_to_markdown": setup_md,
            }

        result = self._format_context_response(project_id, data)
        # Add ambient-specific metadata
        if isinstance(data, dict):
            for key in ("ambient", "hub_files", "modules_in_scope", "neighbor_files"):
                if key in data:
                    result[key] = data[key]

        # Phase 50 Sprint 3: Build markdown version for AI consumption.
        # The "context" field already contains formatted text blocks from
        # the backend (_assemble_ambient_context). We wrap it with a
        # header + health footer for better AI readability.
        context_str = result.get("context", "")
        hub_count = result.get("hub_files", 0)
        mod_count = result.get("modules_in_scope", 0)
        neighbor_count = result.get("neighbor_files", 0)
        chunks = result.get("chunks_used", 0)
        total_chars = result.get("total_chars", 0)

        md_parts: List[str] = []
        md_parts.append(f"## CoDRAG Context ({chunks} chunks, {total_chars} chars)")
        if hub_count or mod_count:
            md_parts.append(f"Hubs: {hub_count} | Modules: {mod_count} | Neighbors: {neighbor_count}")
        md_parts.append("")
        if context_str:
            md_parts.append(context_str)

        result["_to_markdown"] = "\n".join(md_parts)
        return result

    @staticmethod
    def _format_context_response(project_id: str, data: Any) -> Dict[str, Any]:
        """Shared response formatting for context endpoints."""
        chunks = data.get("chunks") if isinstance(data, dict) else None
        chunks_used = len(chunks) if isinstance(chunks, list) else 0
        result: Dict[str, Any] = {
            "project_id": project_id,
            "context": (data or {}).get("context", "") if isinstance(data, dict) else "",
            "chunks_used": chunks_used,
            "total_chars": (data or {}).get("total_chars", 0) if isinstance(data, dict) else 0,
            "estimated_tokens": (data or {}).get("estimated_tokens", 0) if isinstance(data, dict) else 0,
        }
        comp_meta = (data or {}).get("compression") if isinstance(data, dict) else None
        if comp_meta:
            result["compression"] = comp_meta
        return result

    async def tool_trace_search(
        self,
        query: str,
        kind: Optional[str] = None,
        limit: int = 20,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search the trace index for symbols."""
        if not query.strip():
            raise InvalidParamsError("query is required")

        try:
            limit = int(limit)
        except Exception:
            raise InvalidParamsError("limit must be an integer")
        if limit < 1:
            raise InvalidParamsError("limit must be >= 1")
        if limit > 100:
            raise InvalidParamsError("limit too large (max 100)")

        project_id = await self._resolve_project_id(override=project_override)
        payload: Dict[str, Any] = {"query": query, "limit": limit}
        if kind:
            payload["kind"] = kind

        data = await self._api_post(f"/projects/{project_id}/trace/search", payload)

        nodes = (data or {}).get("nodes", []) if isinstance(data, dict) else []
        formatted = []
        for n in nodes:
            formatted.append({
                "id": n.get("id", ""),
                "name": n.get("name", ""),
                "kind": n.get("kind", ""),
                "path": n.get("file_path", n.get("path", "")),
                "line": n.get("start_line", n.get("line")),
            })

        # Phase 50 Sprint 3: Markdown for symbol search results
        if formatted:
            md_lines = [f"## Symbol search: {query} ({len(formatted)} results)\n"]
            for n in formatted:
                line = f"- `{n['name']}` ({n['kind']}) @ `{n['path']}`"
                if n.get("line"):
                    line += f":{n['line']}"
                md_lines.append(line)
            md_text = "\n".join(md_lines)
        else:
            md_text = f"No symbols found matching: {query}"

        return {
            "project_id": project_id,
            "query": query,
            "count": len(formatted),
            "nodes": formatted,
            "_to_markdown": md_text,
        }

    async def tool_trace_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_kinds: Optional[List[str]] = None,
        max_nodes: int = 25,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get neighbors for a trace node."""
        if not node_id.strip():
            raise InvalidParamsError("node_id is required")

        if direction not in ("in", "out", "both"):
            raise InvalidParamsError("direction must be 'in', 'out', or 'both'")

        try:
            max_nodes = int(max_nodes)
        except Exception:
            raise InvalidParamsError("max_nodes must be an integer")
        if max_nodes < 1:
            raise InvalidParamsError("max_nodes must be >= 1")
        if max_nodes > 100:
            raise InvalidParamsError("max_nodes too large (max 100)")

        project_id = await self._resolve_project_id(override=project_override)
        
        # Build query params
        params = [f"direction={direction}", f"max_nodes={max_nodes}"]
        if edge_kinds:
            params.append(f"edge_kinds={','.join(edge_kinds)}")
        query_string = "&".join(params)
        
        data = await self._api_get(f"/projects/{project_id}/trace/neighbors/{node_id}?{query_string}")

        # Format response
        center = (data or {}).get("center") if isinstance(data, dict) else None
        nodes = (data or {}).get("nodes", []) if isinstance(data, dict) else []
        edges = (data or {}).get("edges", []) if isinstance(data, dict) else []

        return {
            "project_id": project_id,
            "center": center,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes[:max_nodes],
            "edges": edges[:50],  # Cap edges for token efficiency
        }

    async def tool_trace_coverage(self, project_override: Optional[str] = None) -> Dict[str, Any]:
        """Get trace coverage statistics."""
        project_id = await self._resolve_project_id(override=project_override)
        data = await self._api_get(f"/projects/{project_id}/trace/coverage")

        # Return lean summary for token efficiency
        return {
            "project_id": project_id,
            "traced_count": (data or {}).get("traced_count", 0) if isinstance(data, dict) else 0,
            "untraced_count": (data or {}).get("untraced_count", 0) if isinstance(data, dict) else 0,
            "stale_count": (data or {}).get("stale_count", 0) if isinstance(data, dict) else 0,
            "excluded_count": (data or {}).get("excluded_count", 0) if isinstance(data, dict) else 0,
            "total_nodes": (data or {}).get("total_nodes", 0) if isinstance(data, dict) else 0,
            "total_edges": (data or {}).get("total_edges", 0) if isinstance(data, dict) else 0,
            "building": bool((data or {}).get("building", False)) if isinstance(data, dict) else False,
        }

    async def tool_impact(
        self,
        file_path: Optional[str] = None,
        symbol: Optional[str] = None,
        max_hops: int = 2,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze what depends on a file or symbol — blast radius analysis."""
        if not file_path and not symbol:
            raise InvalidParamsError("Either file_path or symbol is required")

        project_id = await self._resolve_project_id(override=project_override)

        # Resolve node_id: symbol takes precedence, else convert file_path to file node ID
        if symbol:
            node_id = symbol
        else:
            node_id = f"file:{file_path}"

        try:
            max_hops = min(int(max_hops), 4)
        except Exception:
            max_hops = 2

        data = await self._api_get(
            f"/projects/{project_id}/trace/impact/{node_id}?max_hops={max_hops}&max_nodes=30"
        )

        if not isinstance(data, dict):
            return {"project_id": project_id, "error": "No impact data available"}

        target = data.get("target", {})
        dependents = data.get("dependents", [])

        # Format as human-readable summary for the LLM
        lines = []
        target_name = target.get("name", node_id)
        target_path = target.get("file_path", "")
        lines.append(f"Impact analysis for: {target_name} ({target_path})")
        lines.append(f"Total dependents found: {len(dependents)}")
        lines.append("")

        if dependents:
            d1 = [d for d in dependents if d.get("distance") == 1]
            d2 = [d for d in dependents if d.get("distance", 0) > 1]

            if d1:
                lines.append(f"Direct dependents ({len(d1)}):")
                for dep in d1:
                    sig = dep.get("signature", dep.get("name", "?"))
                    kind = dep.get("kind", "")
                    path = dep.get("path", "")
                    doc = dep.get("docstring", "")
                    entry = f"  {sig} ({path}) [{kind}]"
                    if doc:
                        entry += f" -- {doc}"
                    lines.append(entry)

            if d2:
                lines.append(f"\nTransitive dependents ({len(d2)}):")
                for dep in d2:
                    lines.append(f"  {dep.get('name', '?')} ({dep.get('path', '')})")
        else:
            lines.append("No dependents found — this node has no reverse dependencies.")

        summary = "\n".join(lines)
        return {
            "project_id": project_id,
            "summary": summary,
            "target": target,
            "dependents": dependents,
            "total_dependents": len(dependents),
            "_to_markdown": summary,
        }

    async def tool_save_observation(
        self,
        content: str,
        file_path: Optional[str] = None,
        symbol: Optional[str] = None,
        category: str = "note",
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save an observation about the codebase for cross-session memory."""
        project_id = await self._resolve_project_id(override=project_override)
        payload = {"content": content}
        if file_path:
            payload["file_path"] = file_path
        if symbol:
            payload["symbol"] = symbol
        if category:
            payload["category"] = category
        data = await self._api_post(f"/projects/{project_id}/observations", payload)
        obs_id = (data or {}).get("id", "unknown") if isinstance(data, dict) else "unknown"
        return {
            "saved": True,
            "id": obs_id,
            "project_id": project_id,
            "message": f"Observation saved (id={obs_id}). It will persist across sessions and be flagged stale if the linked file changes.",
        }

    async def tool_get_observations(
        self,
        query: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 10,
        include_stale: bool = True,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve previous observations about the codebase."""
        project_id = await self._resolve_project_id(override=project_override)
        params = []
        if query:
            params.append(f"query={query}")
        if file_path:
            params.append(f"file_path={file_path}")
        params.append(f"limit={limit}")
        if not include_stale:
            params.append("include_stale=false")
        qs = "&".join(params)
        data = await self._api_get(f"/projects/{project_id}/observations?{qs}")

        observations = []
        if isinstance(data, dict):
            for obs in data.get("observations", []):
                entry = {
                    "content": obs.get("content", ""),
                    "category": obs.get("category", "note"),
                }
                if obs.get("file_path"):
                    entry["file_path"] = obs["file_path"]
                if obs.get("symbol_fqn"):
                    entry["symbol"] = obs["symbol_fqn"]
                if obs.get("stale"):
                    entry["stale"] = True
                    entry["stale_reason"] = obs.get("stale_reason", "file modified")
                observations.append(entry)

        return {
            "project_id": project_id,
            "count": len(observations),
            "observations": observations,
        }

    async def tool_audit(
        self,
        synthesize: bool = False,
        category: Optional[str] = None,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run or retrieve a codebase health audit."""
        project_id = await self._resolve_project_id(override=project_override)

        # First try to get existing findings
        try:
            data = await self._api_get(f"/projects/{project_id}/audit/findings")
            findings = data.get("findings", []) if isinstance(data, dict) else []
        except Exception:
            findings = []

        # If no findings exist or caller wants fresh results, trigger a new audit
        if not findings:
            try:
                payload: Dict[str, Any] = {"synthesize": synthesize}
                if category:
                    payload["categories"] = [category]
                await self._api_post(f"/projects/{project_id}/audit", payload)

                # Poll for completion (max 30s for Tier 1, should be <2s)
                import asyncio
                for _ in range(30):
                    await asyncio.sleep(1)
                    status = await self._api_get(f"/projects/{project_id}/audit/status")
                    if isinstance(status, dict) and not status.get("running", True):
                        break

                data = await self._api_get(f"/projects/{project_id}/audit/findings")
                findings = data.get("findings", []) if isinstance(data, dict) else []
            except Exception as e:
                return {"project_id": project_id, "error": f"Audit failed: {e}"}

        # Format findings for token efficiency
        severity_counts = {}
        for f in findings:
            sev = f.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Return top findings with full detail
        top_findings = []
        for f in findings[:15]:
            entry: Dict[str, Any] = {
                "severity": f.get("severity"),
                "title": f.get("title"),
                "action": f.get("suggested_action"),
            }
            if f.get("file_paths"):
                entry["files"] = f["file_paths"][:3]
            top_findings.append(entry)

        result: Dict[str, Any] = {
            "project_id": project_id,
            "total_findings": len(findings),
            "severity_counts": severity_counts,
            "findings": top_findings,
        }

        # Check if reports are available
        try:
            reports_data = await self._api_get(f"/projects/{project_id}/audit/reports")
            reports = reports_data.get("reports", []) if isinstance(reports_data, dict) else []
            if reports:
                result["available_reports"] = [r.get("name") for r in reports]
        except Exception:
            pass

        return result

    async def tool_audit_refactor(
        self,
        finding_ids: List[str],
        instructions: Optional[str] = None,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get selected audit findings with trace context for implementation."""
        if not finding_ids:
            raise InvalidParamsError("finding_ids is required and must not be empty")

        project_id = await self._resolve_project_id(override=project_override)

        # Get findings
        data = await self._api_get(f"/projects/{project_id}/audit/findings?limit=500")
        all_findings = data.get("findings", []) if isinstance(data, dict) else []

        # Filter to requested IDs
        id_set = set(finding_ids)
        selected = [f for f in all_findings if f.get("finding_id") in id_set]

        if not selected:
            return {
                "project_id": project_id,
                "error": f"No findings matched IDs: {finding_ids}. Run codrag_audit first.",
            }

        # Collect all affected file paths for context retrieval
        affected_files: List[str] = []
        for f in selected:
            affected_files.extend(f.get("file_paths", []))
        affected_files = list(dict.fromkeys(affected_files))[:20]  # dedupe, cap at 20

        lines = [
            "## Audit Findings to Address\n",
            "CRITICAL SYSTEM INSTRUCTIONS FOR AI:",
            "1. Focus strictly on resolving the findings listed below.",
            "2. If 'Relevant Code Context' is truncated (stops abruptly), focus on the first few findings, then use `codrag_search` or `codrag_trace_search` to gather the rest.",
            "3. When you finish implementing these fixes, you MUST call `codrag_audit_check` with the relevant analyzers to verify your work before telling the user you are done.\n"
        ]
        for f in selected:
            fid = f.get("finding_id", "")
            title = f.get("title", "")
            priority = f.get("priority", "")
            severity = f.get("severity", "")
            effort = f.get("effort", "")
            desc = f.get("description", "")
            action = f.get("suggested_action", "")
            files = ", ".join(f.get("file_paths", [])[:5])

            lines.append(f"### {fid}: {title} [{priority} · {severity} · {effort}]")
            lines.append(f"**Files:** {files}")
            lines.append(f"**Problem:** {desc}")
            lines.append(f"**Action:** {action}")
            lines.append("")

        if instructions:
            lines.append(f"## User Instructions\n{instructions}\n")

        # Get trace context for affected files
        context_text = ""
        if affected_files:
            try:
                query = " ".join(affected_files[:5])
                ctx_data = await self._api_post(f"/projects/{project_id}/context", {
                    "query": query,
                    "k": 10,
                    "max_chars": 8000,
                    "include_sources": True,
                    "structured": False,
                    "trace_expand": True,
                })
                context_text = ctx_data.get("context", "") if isinstance(ctx_data, dict) else ""
            except Exception:
                pass

        if context_text:
            lines.append("---\n\n## Relevant Code Context\n")
            lines.append(context_text)

        content_md = "\n".join(lines)
        return {
            "project_id": project_id,
            "finding_count": len(selected),
            "finding_ids": [f.get("finding_id") for f in selected],
            "content": content_md,
            "affected_files": affected_files,
            "_to_markdown": content_md,
        }

    async def tool_audit_check(
        self,
        analyzers: List[str],
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Re-run specific analyzers to verify fixes."""
        if not analyzers:
            raise InvalidParamsError("analyzers is required and must not be empty")

        project_id = await self._resolve_project_id(override=project_override)

        # Trigger audit with category filter
        try:
            await self._api_post(f"/projects/{project_id}/audit", {
                "synthesize": False,
            })

            # Poll for completion
            import asyncio
            for _ in range(30):
                await asyncio.sleep(1)
                status = await self._api_get(f"/projects/{project_id}/audit/status")
                if isinstance(status, dict) and not status.get("running", True):
                    break

            # Get fresh findings
            data = await self._api_get(f"/projects/{project_id}/audit/findings?limit=500")
            all_findings = data.get("findings", []) if isinstance(data, dict) else []

            # Filter to requested analyzers
            analyzer_set = set(analyzers)
            matched = [f for f in all_findings if f.get("analyzer") in analyzer_set]

            if not matched:
                return {
                    "project_id": project_id,
                    "status": "clean",
                    "message": f"No findings from analyzers: {analyzers}. The issues appear to be resolved!",
                    "analyzers_checked": analyzers,
                    "finding_count": 0,
                }

            return {
                "project_id": project_id,
                "status": "findings_remain",
                "analyzers_checked": analyzers,
                "finding_count": len(matched),
                "findings": [
                    {
                        "id": f.get("finding_id"),
                        "severity": f.get("severity"),
                        "title": f.get("title"),
                        "action": f.get("suggested_action"),
                    }
                    for f in matched[:15]
                ],
            }
        except Exception as e:
            return {"project_id": project_id, "error": f"Check failed: {e}"}

    async def tool_audit_report(
        self,
        report_name: str,
        project_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve a specific audit report document."""
        if not report_name or not report_name.strip():
            raise InvalidParamsError("report_name is required")

        project_id = await self._resolve_project_id(override=project_override)

        data = await self._api_get(f"/projects/{project_id}/audit/report/{report_name}")

        content = data.get("content", "") if isinstance(data, dict) else ""
        return {
            "project_id": project_id,
            "report": report_name,
            "content": content,
        }

    async def tool_hi(self, project_override: Optional[str] = None) -> Dict[str, Any]:
        """Project overview and context discovery tool.

        Aggregates project state from multiple endpoints and returns a
        friendly markdown summary with health notes and suggested prompts.
        """
        project_id = await self._resolve_project_id(override=project_override)

        # -- Parallel data fetch ------------------------------------------------
        status_coro = self._api_get(f"/projects/{project_id}/status")
        included_coro = self._api_get(f"/projects/{project_id}/included_paths")
        weights_coro = self._api_get(f"/projects/{project_id}/path_weights")
        coverage_coro = self._api_get(f"/projects/{project_id}/trace/coverage")
        projects_coro = self._api_get("/projects")
        project_coro = self._api_get(f"/projects/{project_id}")
        hub_coro = self._api_get(f"/projects/{project_id}/trace/hub_files?k=5")

        results = await asyncio.gather(
            status_coro, included_coro, weights_coro,
            coverage_coro, projects_coro, project_coro,
            hub_coro,
            return_exceptions=True,
        )

        status = results[0] if not isinstance(results[0], Exception) else {}
        included = results[1] if not isinstance(results[1], Exception) else {}
        weights = results[2] if not isinstance(results[2], Exception) else {}
        coverage = results[3] if not isinstance(results[3], Exception) else {}
        all_projects = results[4] if not isinstance(results[4], Exception) else {}
        project_data = results[5] if not isinstance(results[5], Exception) else {}
        hub_data = results[6] if not isinstance(results[6], Exception) else {}

        # Safely unwrap dicts
        if not isinstance(status, dict):
            status = {}
        if not isinstance(included, dict):
            included = {}
        if not isinstance(weights, dict):
            weights = {}
        if not isinstance(coverage, dict):
            coverage = {}
        if not isinstance(all_projects, dict):
            all_projects = {}
        if not isinstance(project_data, dict):
            project_data = {}
        if not isinstance(hub_data, dict):
            hub_data = {}

        # -- Extract data -------------------------------------------------------
        index = status.get("index", {}) or {}
        trace = status.get("trace", {}) or {}
        watch = status.get("watch", {}) or {}
        building = bool(status.get("building", False))
        stale = bool(status.get("stale", False))
        stale_count = int(status.get("stale_count", 0))

        index_exists = bool(index.get("exists", False))
        total_chunks = int(index.get("total_chunks") or 0)
        model = index.get("embedding_model", "unknown")
        built_at = index.get("last_build_at")

        trace_enabled = bool(trace.get("enabled", False))
        total_nodes = int(trace.get("total_nodes") or coverage.get("total_nodes") or 0)
        total_edges = int(trace.get("total_edges") or coverage.get("total_edges") or 0)
        traced_count = int(coverage.get("traced_count", 0))
        untraced_count = int(coverage.get("untraced_count", 0))
        trace_total = traced_count + untraced_count
        trace_pct = round(100 * traced_count / trace_total) if trace_total > 0 else 0

        included_paths = included.get("included_paths", []) or []
        path_weights = weights.get("path_weights", {}) or {}

        watch_enabled = bool(watch.get("enabled", False))

        # O-2: Hub files (from trace graph)
        hub_files_raw = hub_data.get("hub_files", []) or []
        hub_files: List[Dict[str, Any]] = [
            h for h in hub_files_raw
            if isinstance(h, dict) and h.get("path") and h.get("in_degree", 0) > 0
        ][:5]

        # O-7: Change detection — extract stale file paths from coverage
        stale_file_list = coverage.get("stale", []) or []
        stale_file_paths: List[str] = []
        if isinstance(stale_file_list, list):
            for sf in stale_file_list[:10]:
                if isinstance(sf, dict):
                    sp = sf.get("path", "")
                    if sp:
                        stale_file_paths.append(sp)
                elif isinstance(sf, str):
                    stale_file_paths.append(sf)

        # Project name
        proj = project_data.get("project", project_data) if isinstance(project_data, dict) else {}
        if not isinstance(proj, dict):
            proj = {}
        project_name = proj.get("name") or project_id

        # Other projects
        proj_list = all_projects.get("projects", []) if isinstance(all_projects, dict) else []
        other_projects = [
            p.get("name") or p.get("id", "")
            for p in (proj_list if isinstance(proj_list, list) else [])
            if isinstance(p, dict) and str(p.get("id", "")) != project_id
        ]

        # -- O-3: Filename-based topic detection --------------------------------
        def _detect_topics(paths: List[str]) -> List[Dict[str, Any]]:
            """Cluster filenames into recognizable topics via keyword matching."""
            _TOPIC_CLUSTERS: Dict[str, set] = {
                "authentication": {"auth", "login", "logout", "session", "token", "tokens", "jwt", "oauth", "sso", "password", "credential", "signup", "signin"},
                "e-commerce": {"cart", "checkout", "payment", "order", "orders", "invoice", "billing", "subscription", "pricing", "product", "products", "catalog", "shop", "store"},
                "UI components": {"button", "modal", "dialog", "sidebar", "navbar", "nav", "header", "footer", "card", "cards", "form", "input", "dropdown", "tooltip", "menu", "tabs", "panel", "layout", "widget"},
                "API layer": {"api", "endpoint", "endpoints", "route", "routes", "router", "controller", "controllers", "handler", "handlers", "middleware", "rest", "graphql", "grpc"},
                "data models": {"model", "models", "schema", "schemas", "entity", "entities", "migration", "migrations", "database", "db", "orm", "repository", "repo"},
                "testing": {"test", "tests", "spec", "specs", "fixture", "fixtures", "mock", "mocks", "e2e", "integration", "unit"},
                "infrastructure": {"deploy", "deployment", "docker", "dockerfile", "compose", "terraform", "k8s", "kubernetes", "ci", "cd", "pipeline", "github", "workflow", "nginx", "helm"},
                "configuration": {"config", "settings", "env", "environment", "constants", "defaults", "options", "preferences"},
                "state management": {"store", "redux", "context", "provider", "reducer", "action", "actions", "state", "slice", "zustand", "atom"},
                "animation & visuals": {"animation", "parallax", "scroll", "canvas", "transition", "effect", "shader", "particle", "three", "webgl", "gsap"},
                "messaging & events": {"event", "events", "listener", "emitter", "queue", "message", "messages", "pubsub", "webhook", "webhooks", "notification", "notifications"},
                "file & storage": {"upload", "download", "file", "files", "storage", "s3", "blob", "media", "image", "images", "asset", "assets"},
            }

            # Extract stems from all filenames (split on separators, lowercase)
            import re
            all_stems: List[str] = []
            for p in paths:
                name = Path(p).stem  # filename without extension
                # Split camelCase, PascalCase, snake_case, kebab-case
                parts = re.findall(r'[a-z]+|[A-Z][a-z]*|\d+', name)
                all_stems.extend(w.lower() for w in parts if len(w) > 1)

            stem_set = set(all_stems)

            detected: List[Dict[str, Any]] = []
            for topic, keywords in _TOPIC_CLUSTERS.items():
                matches = stem_set & keywords
                if len(matches) >= 2:
                    # Find which files contributed to this topic
                    matched_files: List[str] = []
                    for p in paths:
                        name = Path(p).stem
                        file_parts = {w.lower() for w in re.findall(r'[a-z]+|[A-Z][a-z]*|\d+', name) if len(w) > 1}
                        if file_parts & keywords:
                            matched_files.append(str(Path(p).name))
                    detected.append({
                        "topic": topic,
                        "match_count": len(matches),
                        "keywords": sorted(matches),
                        "files": matched_files[:8],
                    })

            # Sort by match count descending
            detected.sort(key=lambda x: -x["match_count"])
            return detected[:5]  # top 5 topics

        detected_topics = _detect_topics(included_paths)

        # -- Categorize selected files ------------------------------------------
        file_count = len(included_paths)
        _DOC_EXTS = {".md", ".txt", ".rst", ".adoc", ".mdx"}
        _CODE_EXTS = {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".java",
            ".cpp", ".c", ".h", ".cs", ".rb", ".swift", ".kt", ".vue",
            ".svelte", ".php", ".scala", ".zig", ".lua", ".ex", ".exs",
        }
        _TEST_HINTS = {"test", "spec", "__tests__", "tests"}
        _CONFIG_EXTS = {
            ".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".cfg",
            ".lock", ".config",
        }
        _DOC_DIR_HINTS = {"docs", "documentation", "doc", "design", "designplan"}

        docs: List[str] = []
        code: List[str] = []
        tests: List[str] = []
        config: List[str] = []
        other_files: List[str] = []

        dir_counts: Dict[str, int] = {}
        all_dir_segments: set = set()  # all directory names at any level
        for p in included_paths:
            ps = str(p)
            parts = ps.split("/")
            top_dir = parts[0] if len(parts) > 1 else "(root)"
            dir_counts[top_dir] = dir_counts.get(top_dir, 0) + 1
            # Collect all directory segments (not just top-level)
            for seg in parts[:-1]:  # exclude filename
                all_dir_segments.add(seg.lower())

            # Categorize
            ext = ("." + ps.rsplit(".", 1)[-1]).lower() if "." in ps else ""
            low_parts = {seg.lower() for seg in parts}
            if low_parts & _TEST_HINTS:
                tests.append(ps)
            elif ext in _DOC_EXTS:
                docs.append(ps)
            elif ext in _CODE_EXTS:
                code.append(ps)
            elif ext in _CONFIG_EXTS:
                config.append(ps)
            elif low_parts & _DOC_DIR_HINTS:
                # Files without a recognized extension in docs-like directories
                docs.append(ps)
            else:
                other_files.append(ps)

        top_dirs = sorted(dir_counts.items(), key=lambda x: -x[1])[:5]

        # -- Build file inventory (structured data for AI) ---------------------
        _MAX_LIST = 10  # max filenames per category in the inventory

        file_inventory: Dict[str, Any] = {}
        if docs:
            file_inventory["docs"] = {
                "count": len(docs),
                "files": [str(Path(d).name) for d in docs[:_MAX_LIST]],
                "paths": docs[:_MAX_LIST],
            }
        if code:
            file_inventory["code"] = {
                "count": len(code),
                "files": [str(Path(c).name) for c in code[:_MAX_LIST]],
                "paths": code[:_MAX_LIST],
            }
        if tests:
            file_inventory["tests"] = {
                "count": len(tests),
                "files": [str(Path(t).name) for t in tests[:_MAX_LIST]],
                "paths": tests[:_MAX_LIST],
            }
        if config:
            file_inventory["config"] = {
                "count": len(config),
                "files": [str(Path(c).name) for c in config[:_MAX_LIST]],
                "paths": config[:_MAX_LIST],
            }

        # -- Build conversational summary ---------------------------------------
        lines: List[str] = []

        # Lead with selected files — this is the primary context
        if file_count > 0:
            dir_summary = ", ".join(f"**{d}/** ({n})" for d, n in top_dirs)
            lines.append(f"I'm looking at **{project_name}** — {file_count} files selected across {dir_summary}.")
            lines.append("")

            # File inventory by category (what the AI can actually discuss)
            if docs:
                doc_names = ", ".join(f"`{Path(d).name}`" for d in docs[:8])
                lines.append(f"**Docs & design files ({len(docs)}):** {doc_names}" + (f" +{len(docs)-8} more" if len(docs) > 8 else ""))
            if code:
                code_names = ", ".join(f"`{Path(c).name}`" for c in code[:8])
                lines.append(f"**Code ({len(code)}):** {code_names}" + (f" +{len(code)-8} more" if len(code) > 8 else ""))
            if tests:
                test_names = ", ".join(f"`{Path(t).name}`" for t in tests[:6])
                lines.append(f"**Tests ({len(tests)}):** {test_names}" + (f" +{len(tests)-6} more" if len(tests) > 6 else ""))
            if config:
                cfg_names = ", ".join(f"`{Path(c).name}`" for c in config[:4])
                lines.append(f"**Config ({len(config)}):** {cfg_names}" + (f" +{len(config)-4} more" if len(config) > 4 else ""))

            # O-3: Topic detection — surface detected topics naturally
            if detected_topics:
                topic_parts = [f"**{t['topic']}** ({', '.join(f'`{f}`' for f in t['files'][:3])})" for t in detected_topics[:3]]
                lines.append(f"\nIt looks like you're working on: {', '.join(topic_parts)}.")

            if total_chunks > 0:
                lines.append(f"\nIndex: {total_chunks} searchable chunks.")
        elif index_exists:
            lines.append(f"I'm looking at **{project_name}** — {total_chunks} chunks indexed across the project (no specific files selected).")
        elif building:
            lines.append(f"I'm setting up **{project_name}** — the index is building right now.")
        else:
            lines.append(f"I see **{project_name}** but there's no index yet. I'll need one before I can help with code questions.")

        # Trace as background capability (not the lead)
        if trace_enabled and total_nodes > 0:
            lines.append(f"Code graph active ({total_nodes} nodes, {total_edges} edges, {trace_pct}% coverage) — I can trace imports, calls, and structural connections between these files.")

        # O-2: Hub files — show the most connected files
        if hub_files:
            hub_parts = [f"`{Path(h['path']).name}` ({h['in_degree']} connections)" for h in hub_files[:5]]
            lines.append(f"Most connected files: {', '.join(hub_parts)}.")

        # O-7: Stale file names — show which files changed
        if stale_file_paths:
            stale_names = [f"`{Path(sp).name}`" for sp in stale_file_paths[:5]]
            suffix = f" +{len(stale_file_paths)-5} more" if len(stale_file_paths) > 5 else ""
            lines.append(f"Changed since last build: {', '.join(stale_names)}{suffix}.")

        # Path weights
        if path_weights:
            pw_parts = [f"`{k}` = {v}×" for k, v in sorted(path_weights.items())]
            lines.append(f"Priority areas: {', '.join(pw_parts)}.")

        lines.append("")  # blank line before health/observations

        # Health observations
        observations: List[str] = []
        if not index_exists:
            observations.append("No index exists yet — run `codrag_build` to get started.")
        elif building:
            observations.append("Index is currently building — results will improve once it finishes.")
        elif stale:
            if watch_enabled:
                observations.append(f"{stale_count} file(s) changed since last build. Auto-rebuild is on, so it will catch up shortly.")
            else:
                observations.append(f"{stale_count} file(s) changed since last build. Run `codrag_build` to refresh, or I may be working with slightly outdated context.")

        if trace_enabled and trace_pct < 60 and trace_total > 0:
            observations.append(f"Trace coverage is only {trace_pct}% ({traced_count}/{trace_total} files). Some structural connections may be missing.")

        if not watch_enabled and index_exists and not stale:
            observations.append("Auto-rebuild is off — if you change files, I won't pick up the changes until you rebuild.")

        if observations:
            lines.append("**Heads up:**")
            for obs in observations:
                lines.append(f"- {obs}")
            lines.append("")
        else:
            lines.append("Everything looks good — index is fresh and ready.\n")

        # -- O-8: Cross-file relationships (for small selections) --------------
        file_edges: List[Dict[str, str]] = []
        if trace_enabled and 2 <= len(included_paths) <= 30:
            try:
                # Fetch edges between selected files
                path_param = "&paths=".join(str(p) for p in included_paths[:20])
                edges_data = await self._api_get(
                    f"/projects/{project_id}/trace/file_edges?paths={path_param}"
                )
                if isinstance(edges_data, dict):
                    file_edges = edges_data.get("edges", []) or []
            except Exception:
                pass

        if file_edges:
            rel_parts: List[str] = []
            for e in file_edges[:8]:
                src_name = Path(str(e.get("source", ""))).name
                tgt_name = Path(str(e.get("target", ""))).name
                kind = e.get("kind", "imports")
                rel_parts.append(f"`{src_name}` {kind} `{tgt_name}`")
            lines.append(f"File connections: {', '.join(rel_parts)}.")
            lines.append("")

        # -- O-1: Doc content previews -----------------------------------------
        doc_previews: List[Dict[str, str]] = []
        if docs:
            # Fetch first heading + paragraph for up to 5 .md files
            preview_paths = [d for d in docs[:5] if d.endswith((".md", ".mdx", ".txt", ".rst"))]
            preview_coros = [
                self._api_get(f"/projects/{project_id}/file?path={p}")
                for p in preview_paths
            ]
            if preview_coros:
                preview_results = await asyncio.gather(*preview_coros, return_exceptions=True)
                for p, pr in zip(preview_paths, preview_results):
                    if isinstance(pr, Exception) or not isinstance(pr, dict):
                        continue
                    content = pr.get("content", "") or ""
                    if not content:
                        continue
                    # Extract first heading and first paragraph
                    heading = ""
                    paragraph = ""
                    for line in content.split("\n"):
                        stripped = line.strip()
                        if not heading and stripped.startswith("#"):
                            heading = stripped.lstrip("# ").strip()
                        elif heading and not paragraph and stripped and not stripped.startswith("#"):
                            paragraph = stripped[:200]
                            break
                    if heading:
                        doc_previews.append({
                            "path": p,
                            "file": str(Path(p).name),
                            "heading": heading,
                            "preview": paragraph,
                        })

        # -- Content-aware prompts (based on what's actually selected) ----------
        prompts: List[str] = []

        if not index_exists:
            prompts.append("Build my index: `codrag_build`")
        else:
            # Doc-aware prompts (highest signal — docs tell us intent)
            if docs:
                # Try to extract a meaningful doc topic from filenames
                doc_basenames = [Path(d).stem.replace("_", " ").replace("-", " ") for d in docs[:5]]
                if any(kw in " ".join(doc_basenames).lower() for kw in ("design", "plan", "spec", "rfc", "proposal", "architecture")):
                    prompts.append("What do the design docs say? Summarize the plans and identify next steps.")
                elif any(kw in " ".join(doc_basenames).lower() for kw in ("todo", "task", "roadmap", "backlog")):
                    prompts.append("What's on the TODO/roadmap? What should I work on next?")
                elif any(kw in " ".join(doc_basenames).lower() for kw in ("api", "endpoint", "route")):
                    prompts.append("Summarize the API documentation and identify any gaps.")
                else:
                    prompts.append("Summarize these docs and identify any action items or open questions.")

            # Code-aware prompts (check each domain independently)
            # Use all_dir_segments so subdirs like src/components/ are detected
            _code_prompt_added = False
            if code:
                if all_dir_segments & {"api", "routes", "endpoints", "server"}:
                    prompts.append("What API endpoints are in these files? Any missing error handling?")
                    _code_prompt_added = True
                if all_dir_segments & {"components", "views", "pages", "ui"}:
                    prompts.append("What UI components are here and how do they connect?")
                    _code_prompt_added = True
                if not _code_prompt_added:
                    if len(code) <= 10:
                        prompts.append("Walk me through this code — what does each file do and how do they relate?")
                    else:
                        prompts.append(f"How is {project_name} structured? What are the main modules?")

            # Test-aware prompts
            if tests:
                prompts.append("Review my tests — what's well-covered and what's missing?")

            # Cross-cutting prompts (docs + code selected together)
            if docs and code:
                prompts.append("Compare the design docs to the implementation — is anything out of sync?")

            # Trace-powered prompt (background capability)
            if trace_enabled and total_nodes > 0 and len(prompts) < 5:
                prompts.append("What are the most connected files and why?")

            if stale:
                prompts.append("Rebuild my index: `codrag_build`")

            # O-7: Stale-aware prompt
            if stale_file_paths and not stale:
                stale_sample = ", ".join(f"`{Path(sp).name}`" for sp in stale_file_paths[:3])
                prompts.append(f"Review what changed in {stale_sample} since the last build.")

            # O-3: Topic-aware prompts — generate specific prompts for detected topics
            if detected_topics and len(prompts) < 5:
                top_topic = detected_topics[0]["topic"]
                topic_files = ", ".join(f"`{f}`" for f in detected_topics[0]["files"][:3])
                _topic_prompts: Dict[str, str] = {
                    "authentication": f"Review the auth flow across {topic_files} — any security concerns?",
                    "e-commerce": f"Trace the purchase flow through {topic_files} — what happens end to end?",
                    "UI components": f"How do the UI components ({topic_files}) compose together?",
                    "API layer": f"What API endpoints exist in {topic_files}? Any missing validation?",
                    "data models": f"Review the data models in {topic_files} — are the relationships clean?",
                    "infrastructure": f"Review the infra setup ({topic_files}) — anything missing or outdated?",
                    "state management": f"How is state managed across {topic_files}? Any unnecessary complexity?",
                    "animation & visuals": f"Walk me through the animation system ({topic_files}) — how do the effects compose?",
                    "messaging & events": f"Trace the event flow through {topic_files} — what triggers what?",
                    "file & storage": f"Review the file handling in {topic_files} — any edge cases with large files?",
                }
                topic_prompt = _topic_prompts.get(top_topic)
                if topic_prompt and topic_prompt not in prompts:
                    prompts.append(topic_prompt)

            # Generic fallbacks to reach minimum 3
            fallbacks = [
                f"What does {project_name} do? Give me a high-level overview.",
                "What are the key data models or types?",
                "What could be improved or refactored in this code?",
            ]
            for fb in fallbacks:
                if len(prompts) >= 4:
                    break
                if fb not in prompts:
                    prompts.append(fb)

            # O-4: Smart prompt ordering — reorder by category match
            # Score each prompt: higher if its category matches the dominant selection
            dominant_cat = "code"  # default
            cat_counts = {"docs": len(docs), "code": len(code), "tests": len(tests), "config": len(config)}
            if cat_counts:
                dominant_cat = max(cat_counts, key=lambda k: cat_counts[k])

            def _prompt_score(prompt_text: str) -> int:
                """Higher score = more relevant to dominant category."""
                pt = prompt_text.lower()
                if dominant_cat == "docs" and any(kw in pt for kw in ("doc", "design", "plan", "summarize", "todo", "roadmap")):
                    return 3
                if dominant_cat == "tests" and any(kw in pt for kw in ("test", "coverage", "edge case")):
                    return 3
                if dominant_cat == "code" and any(kw in pt for kw in ("code", "module", "endpoint", "component", "structured", "walk")):
                    return 3
                # Cross-cutting prompts get a slight boost when both docs+code selected
                if docs and code and any(kw in pt for kw in ("compare", "sync", "implementation")):
                    return 2
                return 1

            prompts.sort(key=_prompt_score, reverse=True)

        if prompts:
            lines.append("**Here are some things I can help with:**")
            for i, p in enumerate(prompts[:6], 1):
                lines.append(f"{i}. {p}")
            lines.append("")

        # Other projects
        if other_projects:
            lines.append(f"_(You also have {', '.join(other_projects[:5])} indexed.)_\n")

        summary_md = "\n".join(lines)

        # -- Structured diagnostics for programmatic use ------------------------
        diagnostics: Dict[str, Any] = {
            "project_id": project_id,
            "project_name": project_name,
            "index_loaded": index_exists,
            "total_chunks": total_chunks,
            "building": building,
            "stale": stale,
            "stale_count": stale_count,
            "trace_enabled": trace_enabled,
            "trace_nodes": total_nodes,
            "trace_edges": total_edges,
            "trace_coverage_pct": trace_pct,
            "watch_enabled": watch_enabled,
            "included_paths_count": file_count,
            "path_weights": path_weights,
            "other_projects": other_projects[:5],
        }
        if hub_files:
            diagnostics["hub_files"] = hub_files
        if stale_file_paths:
            diagnostics["stale_files"] = stale_file_paths
        if file_edges:
            diagnostics["file_edges"] = file_edges[:10]
        if detected_topics:
            diagnostics["detected_topics"] = detected_topics

        # -- AI presentation guidance ------------------------------------------
        ai_note = (
            "IMPORTANT: The selected files ARE the user's focus. Lead with them.\n\n"
            "STANDALONE (user only said 'hi_codrag'): Present the file inventory "
            "conversationally — tell the user exactly which files and areas you're "
            "looking at. Group them naturally: 'I can see your design docs (X, Y), "
            "the code in components/ (A, B, C), and some tests.' If docs are selected, "
            "mention what they appear to be about (from filenames and doc_previews). "
            "Mention hub files as 'the most important/connected files'. "
            "Mention trace/graph as a background capability, not the lead. "
            "Offer the suggested prompts as numbered options. Speak in first person.\n\n"
            "WITH A QUESTION (user said 'hi_codrag' AND asked something): Briefly "
            "acknowledge the selected files (1 sentence), then address their question. "
            "Use codrag_search to retrieve specific content from the selected files.\n\n"
            "DEEPER CONTEXT: For detailed file content, call `codrag` (the ambient "
            "context tool) — it returns LOD-stratified content from hub files and "
            "module summaries. Use it when the user picks a suggested prompt or asks "
            "a specific question about the selected files."
        )

        result: Dict[str, Any] = {
            "_ai_note": ai_note,
            "summary": summary_md,
            "file_inventory": file_inventory,
            "diagnostics": diagnostics,
        }
        if doc_previews:
            result["doc_previews"] = doc_previews
        if detected_topics:
            result["detected_topics"] = detected_topics
        return result

    # -------------------------------------------------------------------------
    # MCP Protocol Handlers
    # -------------------------------------------------------------------------

    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request.

        Extracts workspace roots from the client so we can match them
        against registered CoDRAG projects for automatic routing.
        """
        self._initialize_roots = []

        # MCP spec: roots array in params
        roots = params.get("roots", [])
        if isinstance(roots, list):
            for root in roots:
                if isinstance(root, dict):
                    uri = root.get("uri", "")
                    path = self._uri_to_path(uri)
                    if path:
                        self._initialize_roots.append(path)
                elif isinstance(root, str):
                    path = self._uri_to_path(root)
                    if path:
                        self._initialize_roots.append(path)

        # LSP compat: rootUri (string)
        root_uri = params.get("rootUri") or params.get("rootPath", "")
        if root_uri:
            path = self._uri_to_path(str(root_uri))
            if path and path not in self._initialize_roots:
                self._initialize_roots.append(path)

        # LSP compat: workspaceFolders (array of {uri, name})
        workspace_folders = params.get("workspaceFolders", [])
        if isinstance(workspace_folders, list):
            for folder in workspace_folders:
                if isinstance(folder, dict):
                    uri = folder.get("uri", "")
                    path = self._uri_to_path(str(uri))
                    if path and path not in self._initialize_roots:
                        self._initialize_roots.append(path)

        if self._initialize_roots:
            logger.debug(f"Workspace roots from client: {self._initialize_roots}")

        # Phase 50 (OPP-3): Extract client identity for host-aware behavior
        client_info = params.get("clientInfo", {})
        if isinstance(client_info, dict):
            self._client_name = str(client_info.get("name", "unknown"))
            self._client_version = str(client_info.get("version", ""))
            logger.debug("MCP client: %s %s", self._client_name, self._client_version)

        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "codrag",
                "version": "2.0.0",
            },
            # Phase 50: MCP server instructions (spec 2025-06-18).
            # Gemini CLI, Claude Code, Qwen Code append this to system prompt.
            # Cursor/Windsurf may ignore it -- rules files cover those.
            "instructions": (
                "CoDRAG provides structural codebase intelligence -- "
                "module architecture, dependency analysis, code graph navigation, "
                "hub file identification, and codebase-wide structural context. "
                "Search for CoDRAG tools when: understanding codebase structure, "
                "analyzing dependencies before changes, finding connected files, "
                "or needing an architectural overview. "
                "Call `codrag` at the start of every task for module structure and hub files. "
                "Use `codrag_search` for code queries with structural expansion. "
                "Use `codrag_impact` before changes to understand the blast radius."
            ),
        }

    @staticmethod
    def _uri_to_path(uri: str) -> Optional[str]:
        """Convert a file:// URI or bare path to a filesystem path."""
        if not uri:
            return None
        if uri.startswith("file:///"):
            return uri[7:]  # file:///Users/... -> /Users/...
        if uri.startswith("file://"):
            return uri[7:]
        if uri.startswith("/"):
            return uri
        return None

    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {"tools": TOOLS}

    # ── Phase 50 Sprint 4: MCP Resources ─────────────────────────────

    async def handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request.

        Returns lightweight resource descriptors. Each resource is <500 tokens
        and serves as on-demand cached context the AI can pull without a
        tool call (no approval needed).
        """
        try:
            project_id = await self._resolve_project_id()
        except Exception:
            project_id = "default"

        return {"resources": [
            {
                "uri": f"codrag://{project_id}/structure",
                "name": "Codebase Structure",
                "description": "Module summaries, hub files, and dependency map. ~500 tokens.",
                "mimeType": "text/markdown",
            },
            {
                "uri": f"codrag://{project_id}/atlas",
                "name": "Codebase Atlas",
                "description": "Architectural overview of the codebase. ~400 tokens.",
                "mimeType": "text/markdown",
            },
            {
                "uri": f"codrag://{project_id}/files",
                "name": "Selected Files",
                "description": "Knowledge base files selected by the user. ~300 tokens.",
                "mimeType": "text/markdown",
            },
            {
                "uri": f"codrag://{project_id}/health",
                "name": "Index Health",
                "description": "Index freshness, coverage, and build status. ~100 tokens.",
                "mimeType": "text/markdown",
            },
        ]}

    async def handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request.

        Reads a specific resource by URI. Each resource generator is
        lightweight (<50ms) -- reads pre-computed data from disk, no LLM.
        """
        uri = params.get("uri", "")
        if not uri:
            raise InvalidParamsError("uri is required")

        # Parse URI: codrag://{project_id}/{resource_type}
        if not uri.startswith("codrag://"):
            raise InvalidParamsError(f"Unknown resource URI scheme: {uri}")

        parts = uri[len("codrag://"):].split("/", 1)
        if len(parts) != 2:
            raise InvalidParamsError(f"Invalid resource URI: {uri}")

        project_id_from_uri, resource_type = parts

        # Resolve actual project (URI project_id is a hint, auto-detect if needed)
        try:
            project_id = await self._resolve_project_id(override=project_id_from_uri)
        except Exception:
            project_id = project_id_from_uri

        content = ""
        try:
            if resource_type == "structure":
                content = await self._resource_structure(project_id)
            elif resource_type == "atlas":
                content = await self._resource_atlas(project_id)
            elif resource_type == "files":
                content = await self._resource_files(project_id)
            elif resource_type == "health":
                content = await self._resource_health(project_id)
            else:
                raise InvalidParamsError(f"Unknown resource type: {resource_type}")
        except InvalidParamsError:
            raise
        except Exception as e:
            logger.debug("Resource read failed for %s: %s", uri, e)
            content = f"(Resource unavailable: {e})"

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": content,
                }
            ]
        }

    # ── Resource content generators ──────────────────────────────────

    async def _resource_structure(self, project_id: str) -> str:
        """Hub files + graph topology. ~300 tokens. Fast: 2 API calls, <30ms."""
        data = await self._api_get(f"/projects/{project_id}/status")
        if not isinstance(data, dict):
            return "(No project data available)"

        index = data.get("index", {}) or {}
        trace = data.get("trace", {}) or {}
        parts: List[str] = []

        parts.append("## Codebase Structure\n")

        # Graph topology
        nodes = trace.get("total_nodes", 0)
        edges = trace.get("total_edges", 0)
        chunks = index.get("total_chunks", 0)
        if nodes or chunks:
            parts.append(f"Graph: {nodes} nodes, {edges} edges | Index: {chunks} chunks\n")

        # Hub files (single fast API call)
        try:
            hub_data = await self._api_get(f"/projects/{project_id}/trace/hub_files?k=8")
            hub_files = (hub_data or {}).get("hub_files", []) if isinstance(hub_data, dict) else []
            if hub_files:
                parts.append("### Hub Files (most connected)")
                for h in hub_files[:8]:
                    if isinstance(h, dict) and h.get("path"):
                        parts.append(f"- `{h['path']}` ({h.get('in_degree', 0)} connections)")
                parts.append("")
        except Exception:
            pass

        if len(parts) <= 2:
            return "(Structure data not yet available -- build the index first)"

        parts.append("Call `codrag` for full module summaries and hub file content.")
        return "\n".join(parts)

    async def _resource_atlas(self, project_id: str) -> str:
        """Codebase atlas text. ~400 tokens. Single API call."""
        try:
            # Request atlas via include_atlas=True. With empty query, the
            # backend prepends the atlas to the context string.
            ctx_data = await self._api_post(f"/projects/{project_id}/context", {
                "query": "", "max_chars": 2500, "include_atlas": True,
            })
            if not isinstance(ctx_data, dict):
                return "(Atlas not available)"

            atlas_meta = ctx_data.get("atlas", {}) or {}
            context = ctx_data.get("context", "") or ""

            if atlas_meta.get("included") and context:
                # The atlas is prepended to context. Return up to 2500 chars
                # which covers the full atlas for all project sizes.
                return context[:2500]

            return "(Atlas not yet generated -- the pipeline will create it at Stage 9)"
        except IndexNotReadyError:
            return "(Index not built yet -- atlas will be available after the pipeline runs)"
        except Exception as e:
            return f"(Atlas unavailable: {e})"

    async def _resource_files(self, project_id: str) -> str:
        """Selected knowledge base files. ~300 tokens."""
        try:
            data = await self._api_get(f"/projects/{project_id}/included_paths")
            paths = (data or {}).get("included_paths", []) if isinstance(data, dict) else []

            if not paths:
                return "(No files selected in knowledge base)"

            parts = [f"## Selected Files ({len(paths)} paths)\n"]
            for p in paths[:20]:
                parts.append(f"- `{p}`")
            if len(paths) > 20:
                parts.append(f"- ... +{len(paths) - 20} more")
            parts.append("\nCall `codrag` for detailed content from these areas.")
            return "\n".join(parts)
        except Exception as e:
            return f"(File list unavailable: {e})"

    async def _resource_health(self, project_id: str) -> str:
        """Index health summary. ~100 tokens."""
        try:
            data = await self._api_get(f"/projects/{project_id}/status")
            if not isinstance(data, dict):
                return "(Health data unavailable)"

            index = data.get("index", {}) or {}
            trace = data.get("trace", {}) or {}
            watch = data.get("watch", {}) or {}
            building = data.get("building", False)
            stale = data.get("stale", False)
            stale_count = data.get("stale_count", 0)

            parts = ["## Index Health\n"]

            # Index status
            if index.get("exists"):
                built_at = index.get("last_build_at", "unknown")
                parts.append(f"Index: loaded ({index.get('total_chunks', 0)} chunks, built {built_at})")
            elif building:
                parts.append("Index: building...")
            else:
                parts.append("Index: not built")

            # Trace status
            nodes = trace.get("total_nodes", 0)
            if nodes:
                parts.append(f"Trace: {nodes} nodes, {trace.get('total_edges', 0)} edges")

            # Watch status
            if watch.get("enabled"):
                parts.append("Watch: active (auto-rebuild on file changes)")
            else:
                parts.append("Watch: inactive")

            # Staleness
            if stale:
                parts.append(f"Stale: {stale_count} file(s) changed since last build")

            return "\n".join(parts)
        except Exception as e:
            return f"(Health data unavailable: {e})"

    # ── Phase 50 Sprint 5: MCP Prompts ─────────────────────────────

    _PROMPTS = [
        {
            "name": "codrag-analyze",
            "description": "Analyze the codebase architecture using CoDRAG's structural intelligence",
            "arguments": [
                {
                    "name": "focus",
                    "description": "Optional area to focus the analysis on (e.g., 'authentication', 'API layer')",
                    "required": False,
                },
            ],
        },
        {
            "name": "codrag-review",
            "description": "Review the current file or selection for bugs, style issues, and structural problems",
            "arguments": [
                {
                    "name": "scope",
                    "description": "What to review: 'file' (current file), 'selection' (selected code), or a file path",
                    "required": False,
                },
            ],
        },
        {
            "name": "codrag-plan",
            "description": "Plan a change with impact analysis -- understand what files are affected before editing",
            "arguments": [
                {
                    "name": "change",
                    "description": "Description of the change you want to make",
                    "required": True,
                },
            ],
        },
    ]

    async def handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list request."""
        return {"prompts": self._PROMPTS}

    async def handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request.

        Returns the prompt messages that the host injects into the conversation
        when the user triggers the prompt (e.g., via a slash command).
        """
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        if name == "codrag-analyze":
            focus = arguments.get("focus", "")
            focus_text = f" Focus on: {focus}." if focus else ""
            return {
                "description": "Analyze codebase architecture",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Analyze this codebase's architecture using CoDRAG.{focus_text}\n\n"
                                "1. Call `codrag` first to get the structural overview (modules, hub files, connections).\n"
                                "2. Identify architectural patterns, potential issues, and areas for improvement.\n"
                                "3. Use `codrag_search` to examine specific areas in detail.\n"
                                "4. Summarize your findings with concrete file references."
                            ),
                        },
                    }
                ],
            }

        elif name == "codrag-review":
            scope = arguments.get("scope", "file")
            return {
                "description": "Review code with structural context",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Review this code (scope: {scope}) using CoDRAG's structural understanding.\n\n"
                                "1. Call `codrag` for structural context -- understand where this code fits in the architecture.\n"
                                "2. Call `codrag_impact` on the relevant file to understand its dependencies and dependents.\n"
                                "3. Check for bugs, style issues, missing error handling, and structural problems.\n"
                                "4. Consider how changes here would affect connected files."
                            ),
                        },
                    }
                ],
            }

        elif name == "codrag-plan":
            change = arguments.get("change", "the proposed change")
            return {
                "description": "Plan a change with impact analysis",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                f"Plan this change: {change}\n\n"
                                "1. Call `codrag` for structural overview of the codebase.\n"
                                "2. Call `codrag_impact` on files that will be modified to understand the blast radius.\n"
                                "3. Call `codrag_search` to find related code that may need updates.\n"
                                "4. Create a step-by-step implementation plan that accounts for all dependencies.\n"
                                "5. List all files that need changes, in the order they should be modified."
                            ),
                        },
                    }
                ],
            }

        else:
            raise MethodNotFoundError(f"Unknown prompt: {name}")

    # EA-B12: MCP rate limiting state
    _mcp_call_times: List[float] = []
    _MCP_RATE_LIMIT = 120       # max calls
    _MCP_RATE_WINDOW = 60.0     # per N seconds

    def _check_rate_limit(self) -> None:
        """EA-B12: Enforce rate limit on MCP tool calls (120 calls/60s)."""
        import time
        now = time.monotonic()
        # Prune old entries
        self._mcp_call_times = [t for t in self._mcp_call_times if now - t < self._MCP_RATE_WINDOW]
        if len(self._mcp_call_times) >= self._MCP_RATE_LIMIT:
            raise MCPError(-32000, f"Rate limit exceeded: {self._MCP_RATE_LIMIT} calls per {int(self._MCP_RATE_WINDOW)}s")
        self._mcp_call_times.append(now)

    def _audit_mcp_call(self, tool_name: str, args: Dict[str, Any]) -> None:
        """EA-B12: Record MCP tool call to audit log."""
        try:
            from codrag.core.audit_log import get_audit_log
            audit = get_audit_log()
            audit.record(
                event_type="mcp_tool_call",
                severity="info",
                message=f"MCP tool called: {tool_name}",
                metadata={"tool": tool_name, "args_keys": list(args.keys())},
            )
        except Exception:
            pass  # Audit logging is best-effort

    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request.

        Phase 50: Consolidated dispatch with alias routing.
        New tool names (codrag, codrag_search, codrag_impact, codrag_audit,
        codrag_observe) are handled directly. Legacy tool names are
        transparently routed via TOOL_ALIASES with parameter transforms.
        """
        from codrag.mcp_tools import TOOL_ALIASES

        original_name = params.get("name", "")
        args = params.get("arguments", {})

        # EA-B12: Rate limit + audit log
        self._check_rate_limit()
        self._audit_mcp_call(original_name, args)

        # Phase 50: Resolve legacy aliases to new tool names.
        # Apply parameter transforms for consolidated tools.
        name = original_name
        if name in TOOL_ALIASES:
            resolved = TOOL_ALIASES[name]
            logger.debug("Alias dispatch: %s -> %s", name, resolved)

            # Parameter transforms for legacy -> consolidated routing
            if name == "codrag_trace_search":
                args.setdefault("type", "symbol")
                name = resolved
            elif name == "codrag_trace_neighbors":
                # Map neighbors params to impact params
                args.setdefault("direction", "all")
                if "node_id" in args:
                    args.setdefault("symbol", args.pop("node_id"))
                if "max_nodes" in args:
                    args.setdefault("max_hops", 1)
                name = resolved
            elif name == "codrag_audit_refactor":
                args.setdefault("action", "refactor")
                name = resolved
            elif name == "codrag_audit_check":
                args.setdefault("action", "verify")
                name = resolved
            elif name == "codrag_audit_report":
                args.setdefault("action", "report")
                name = resolved
            elif name == "codrag_save_observation":
                args.setdefault("action", "save")
                name = resolved
            elif name == "codrag_get_observations":
                args.setdefault("action", "get")
                name = resolved
            else:
                name = resolved

        project_override = args.get("project_id")

        try:
            # ── Primary tools (new consolidated set) ────────────────
            if name in ("codrag", "codrag_context", "codrag_"):
                self._codrag_called = True
                result = await self.tool_context(
                    max_chars=args.get("max_chars", 12000),
                    project_override=project_override,
                )

            elif name == "codrag_search":
                search_type = args.get("type", "context")
                if search_type == "symbol":
                    result = await self.tool_trace_search(
                        query=args.get("query", ""),
                        kind=args.get("kind"),
                        limit=args.get("limit", args.get("k", 20)),
                        project_override=project_override,
                    )
                else:
                    result = await self.tool_search(
                        query=args.get("query", ""),
                        k=args.get("k", 5),
                        max_chars=args.get("max_chars", 12000),
                        trace_expand=bool(args.get("trace_expand", True)),
                        compression=args.get("compression", "none"),
                        compression_level=args.get("compression_level", "standard"),
                        compression_timeout_s=args.get("compression_timeout_s", 30.0),
                        exclude_paths=args.get("exclude_paths") or None,
                        project_override=project_override,
                    )
                # Phase 50 Sprint 3: Nudge if codrag hasn't been called yet
                if not self._codrag_called and isinstance(result, dict):
                    md = result.get("_to_markdown", "")
                    if md:
                        result["_to_markdown"] = (
                            md + "\n\n---\n[tip: Call `codrag` (no args) for structural "
                            "codebase overview -- modules, hub files, and architecture.]"
                        )

            elif name == "codrag_impact":
                direction = args.get("direction", "dependents")
                if direction == "all":
                    # Full neighborhood -- use trace_neighbors backend
                    node_id = args.get("symbol") or args.get("node_id", "")
                    if not node_id and args.get("file_path"):
                        node_id = f"file:{args['file_path']}"
                    result = await self.tool_trace_neighbors(
                        node_id=node_id,
                        direction="both",
                        edge_kinds=args.get("edge_kinds"),
                        max_nodes=args.get("max_nodes", 25),
                        project_override=project_override,
                    )
                elif direction == "dependencies":
                    # What does X depend on? (outgoing edges)
                    node_id = args.get("symbol") or ""
                    if not node_id and args.get("file_path"):
                        node_id = f"file:{args['file_path']}"
                    result = await self.tool_trace_neighbors(
                        node_id=node_id,
                        direction="out",
                        edge_kinds=args.get("edge_kinds"),
                        max_nodes=args.get("max_nodes", 25),
                        project_override=project_override,
                    )
                else:
                    # Default: dependents (what breaks if I change X?)
                    result = await self.tool_impact(
                        file_path=args.get("file_path"),
                        symbol=args.get("symbol"),
                        max_hops=args.get("max_hops", 2),
                        project_override=project_override,
                    )

            elif name == "codrag_audit":
                action = args.get("action", "scan")
                if action == "refactor":
                    result = await self.tool_audit_refactor(
                        finding_ids=args.get("finding_ids", []),
                        instructions=args.get("instructions"),
                        project_override=project_override,
                    )
                elif action == "verify":
                    result = await self.tool_audit_check(
                        analyzers=args.get("analyzers", []),
                        project_override=project_override,
                    )
                elif action == "report":
                    result = await self.tool_audit_report(
                        report_name=args.get("report_name", ""),
                        project_override=project_override,
                    )
                else:
                    # Default: scan
                    result = await self.tool_audit(
                        synthesize=bool(args.get("synthesize", False)),
                        category=args.get("category"),
                        project_override=project_override,
                    )

            elif name == "codrag_observe":
                action = args.get("action", "get")
                if action == "save":
                    result = await self.tool_save_observation(
                        content=args.get("content", ""),
                        file_path=args.get("file_path"),
                        symbol=args.get("symbol"),
                        category=args.get("category", "note"),
                        project_override=project_override,
                    )
                else:
                    # Default: get
                    result = await self.tool_get_observations(
                        query=args.get("query"),
                        file_path=args.get("file_path"),
                        limit=args.get("limit", 10),
                        include_stale=args.get("include_stale", True),
                        project_override=project_override,
                    )

            # ── Hidden admin tool (not listed, but dispatches) ──────
            elif name == "codrag_build":
                result = await self.tool_build(
                    full=args.get("full", False),
                    project_override=project_override,
                )

            else:
                raise MethodNotFoundError(f"Unknown tool: {original_name}")

            # Phase 50 Sprint 3: Prefer markdown text over JSON for AI consumption.
            # Tool methods that set result["_to_markdown"] get clean text output.
            # Others fall back to json.dumps for backward compatibility.
            if isinstance(result, dict) and "_to_markdown" in result:
                text = result.pop("_to_markdown")
            else:
                text = json.dumps(result, indent=2)

            return {
                "content": [
                    {"type": "text", "text": text}
                ],
                "isError": False,
            }

        except (DaemonUnavailableError, DaemonError, InvalidParamsError) as e:
            return {
                "content": [
                    {"type": "text", "text": str(e)}
                ],
                "isError": True,
            }

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle a JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        # Notifications (no id) don't get responses
        if req_id is None:
            if method == "notifications/initialized":
                pass  # Client confirmed initialization
            return None

        try:
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "tools/list":
                result = await self.handle_tools_list(params)
            elif method == "tools/call":
                result = await self.handle_tools_call(params)
            elif method == "resources/list":
                result = await self.handle_resources_list(params)
            elif method == "resources/read":
                result = await self.handle_resources_read(params)
            elif method == "prompts/list":
                result = await self.handle_prompts_list(params)
            elif method == "prompts/get":
                result = await self.handle_prompts_get(params)
            elif method == "ping":
                result = {}
            else:
                raise MethodNotFoundError(f"Unknown method: {method}")

            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "result": result,
            }

        except MCPError as e:
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "error": {"code": e.code, "message": str(e)},
            }
        except Exception as e:
            logger.exception("Internal error handling request")
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "error": {"code": INTERNAL_ERROR, "message": str(e)},
            }


# =============================================================================
# Errors
# =============================================================================

