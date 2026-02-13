"""
CoDRAG MCP Server - Model Context Protocol integration.

Provides MCP tools for IDE integration (Cursor, VS Code, Windsurf, JetBrains, etc.)

Transport: stdio (primary), Streamable HTTP (planned)
Spec version: 2025-11-25

Tools:
- codrag_status: Get index status and daemon health
- codrag_build: Trigger index build (async)
- codrag_search: Search the index
- codrag: Get assembled context for LLM injection (primary tool)
- codrag_trace_search: Search the code graph for symbols
- codrag_trace_neighbors: Get neighbors for a trace node
- codrag_trace_coverage: Get trace coverage statistics
"""

from __future__ import annotations

import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
try:
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import StreamingResponse
    from fastapi.middleware.base import BaseHTTPMiddleware
    import uvicorn
except ImportError:
    FastAPI = None
    uvicorn = None
    BaseHTTPMiddleware = object  # type: ignore

# Configure logging to stderr (stdout reserved for MCP JSON-RPC)
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
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
        try:
            resp = await client.get(url)
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
        try:
            resp = await client.post(url, json=payload)
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

    async def _resolve_project_id(self) -> str:
        if self.project_id:
            return self.project_id

        cwd = str(Path.cwd().resolve())
        if self.auto_detect and self._resolved_project_id and self._resolved_project_cwd == cwd:
            return self._resolved_project_id

        data = await self._api_get("/projects")
        projects: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            raw = data.get("projects")
            if isinstance(raw, list):
                projects = [p for p in raw if isinstance(p, dict)]

        if not projects:
            raise ProjectNotFoundError("No projects configured in daemon")

        def _project_lines() -> List[str]:
            lines: List[str] = []
            for p in projects:
                pid = str(p.get("id") or "").strip()
                if not pid:
                    continue
                name = str(p.get("name") or "").strip() or "(unnamed)"
                path = str(p.get("path") or "").strip()
                lines.append(f"- {pid}: {name} ({path})")
            return lines

        if self.auto_detect:
            matches: List[Dict[str, Any]] = []
            for p in projects:
                pid = p.get("id")
                p_path = str(p.get("path") or "").rstrip("/")
                if not pid or not p_path:
                    continue
                if cwd == p_path or cwd.startswith(p_path + "/"):
                    matches.append(p)

            if matches:
                max_len = max(len(str(p.get("path") or "").rstrip("/")) for p in matches)
                best = [
                    p
                    for p in matches
                    if len(str(p.get("path") or "").rstrip("/")) == max_len
                ]
                if len(best) == 1 and best[0].get("id"):
                    best_id = str(best[0].get("id"))
                    self._resolved_project_id = best_id
                    self._resolved_project_cwd = cwd
                    logger.debug(
                        f"Auto-detected project_id={best_id} cwd={cwd} path={best[0].get('path')}"
                    )
                    return best_id

                msg = (
                    "PROJECT_SELECTION_AMBIGUOUS: Multiple projects match current working directory.\n"
                    f"cwd: {cwd}\n\n"
                    "Projects:\n"
                    + "\n".join(_project_lines())
                    + "\n\nHint: Run MCP with --project <id> to pin a project."
                )
                raise ProjectSelectionAmbiguousError(msg)

        if len(projects) == 1 and projects[0].get("id"):
            pid = str(projects[0].get("id"))
            if self.auto_detect:
                self._resolved_project_id = pid
                self._resolved_project_cwd = cwd
            return pid

        lines = _project_lines()
        if self.auto_detect:
            msg = (
                "PROJECT_NOT_FOUND: No project matched current working directory.\n"
                f"cwd: {cwd}\n\n"
                "Projects:\n"
                + "\n".join(lines)
                + "\n\nHint: Run MCP with --project <id>, or run MCP with --auto from inside a project directory."
            )
            raise ProjectNotFoundError(msg)

        msg = (
            "PROJECT_SELECTION_AMBIGUOUS: Multiple projects are configured; selection is ambiguous.\n\n"
            "Projects:\n"
            + "\n".join(lines)
            + "\n\nHint: Run MCP with --project <id> to pin a project, or use --auto to select based on cwd."
        )
        raise ProjectSelectionAmbiguousError(msg)

    # -------------------------------------------------------------------------
    # Tool Implementations
    # -------------------------------------------------------------------------

    async def tool_status(self) -> Dict[str, Any]:
        """Get index status."""
        project_id = await self._resolve_project_id()
        data = await self._api_get(f"/projects/{project_id}/status")

        # Lean output for token efficiency
        index = (data or {}).get("index", {}) if isinstance(data, dict) else {}
        return {
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

    async def tool_build(self, full: bool = False) -> Dict[str, Any]:
        """Trigger index build."""
        project_id = await self._resolve_project_id()
        path = f"/projects/{project_id}/build"
        if full:
            path = f"{path}?full=true"

        try:
            data = await self._api_post(path, {})
        except BuildInProgressError:
            return {"status": "already_building", "message": "A build is already in progress."}

        if isinstance(data, dict) and data.get("started"):
            return {"status": "started", "message": "Index build started. Use codrag_status to check progress."}
        return {"status": "unknown", "data": data}

    async def tool_search(
        self,
        query: str,
        k: int = 8,
        min_score: float = 0.15,
    ) -> Dict[str, Any]:
        """Search the index."""
        if not query.strip():
            raise InvalidParamsError("query is required")

        try:
            k = int(k)
        except Exception:
            raise InvalidParamsError("k must be an integer")
        if k < 1:
            raise InvalidParamsError("k must be >= 1")
        if k > MAX_SEARCH_K:
            raise InvalidParamsError(f"k too large (max {MAX_SEARCH_K})")

        try:
            min_score = float(min_score)
        except Exception:
            raise InvalidParamsError("min_score must be a number")
        if min_score < 0.0 or min_score > 1.0:
            raise InvalidParamsError("min_score must be between 0 and 1")

        project_id = await self._resolve_project_id()
        data = await self._api_post(f"/projects/{project_id}/search", {
            "query": query,
            "k": k,
            "min_score": min_score,
        })

        # Format results for token efficiency
        results = (data or {}).get("results", []) if isinstance(data, dict) else []
        formatted = []
        for r in results:
            formatted.append({
                "path": r.get("source_path", ""),
                "section": "",
                "score": round(r.get("score", 0), 3),
                "content": str(r.get("preview", ""))[:500],  # Truncate for listing
            })

        return {
            "query": query,
            "count": len(formatted),
            "results": formatted,
        }

    async def tool_context(
        self,
        query: str,
        k: int = 5,
        max_chars: int = 6000,
        trace_expand: bool = False,
        compression: str = "none",
        compression_level: str = "standard",
        compression_timeout_s: float = 30.0,
    ) -> Dict[str, Any]:
        """Get assembled context."""
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

        if compression not in ("none", "clara"):
            raise InvalidParamsError("compression must be 'none' or 'clara'")
        if compression_level not in ("light", "standard", "aggressive"):
            raise InvalidParamsError("compression_level must be 'light', 'standard', or 'aggressive'")

        project_id = await self._resolve_project_id()
        payload: Dict[str, Any] = {
            "query": query,
            "k": k,
            "max_chars": max_chars,
            "include_sources": True,
            "include_scores": False,
            "structured": True,
        }
        if trace_expand:
            payload["trace_expand"] = True
        if compression != "none":
            payload["compression"] = compression
            payload["compression_level"] = compression_level
            payload["compression_timeout_s"] = float(compression_timeout_s)

        data = await self._api_post(f"/projects/{project_id}/context", payload)

        chunks = data.get("chunks") if isinstance(data, dict) else None
        chunks_used = len(chunks) if isinstance(chunks, list) else 0
        result: Dict[str, Any] = {
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

        project_id = await self._resolve_project_id()
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

        return {
            "query": query,
            "count": len(formatted),
            "nodes": formatted,
        }

    async def tool_trace_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_kinds: Optional[List[str]] = None,
        max_nodes: int = 25,
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

        project_id = await self._resolve_project_id()
        
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
            "center": center,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes[:max_nodes],
            "edges": edges[:50],  # Cap edges for token efficiency
        }

    async def tool_trace_coverage(self) -> Dict[str, Any]:
        """Get trace coverage statistics."""
        project_id = await self._resolve_project_id()
        data = await self._api_get(f"/projects/{project_id}/trace/coverage")

        # Return lean summary for token efficiency
        return {
            "traced_count": (data or {}).get("traced_count", 0) if isinstance(data, dict) else 0,
            "untraced_count": (data or {}).get("untraced_count", 0) if isinstance(data, dict) else 0,
            "stale_count": (data or {}).get("stale_count", 0) if isinstance(data, dict) else 0,
            "excluded_count": (data or {}).get("excluded_count", 0) if isinstance(data, dict) else 0,
            "total_nodes": (data or {}).get("total_nodes", 0) if isinstance(data, dict) else 0,
            "total_edges": (data or {}).get("total_edges", 0) if isinstance(data, dict) else 0,
            "building": bool((data or {}).get("building", False)) if isinstance(data, dict) else False,
        }

    # -------------------------------------------------------------------------
    # MCP Protocol Handlers
    # -------------------------------------------------------------------------

    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": "codrag",
                "version": "0.1.0",
            },
        }

    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {"tools": TOOLS}

    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        name = params.get("name", "")
        args = params.get("arguments", {})

        try:
            if name == "codrag_status":
                result = await self.tool_status()
            elif name == "codrag_build":
                result = await self.tool_build(full=args.get("full", False))
            elif name == "codrag_search":
                result = await self.tool_search(
                    query=args.get("query", ""),
                    k=args.get("k", 8),
                    min_score=args.get("min_score", 0.15),
                )
            elif name == "codrag":
                result = await self.tool_context(
                    query=args.get("query", ""),
                    k=args.get("k", 5),
                    max_chars=args.get("max_chars", 6000),
                    trace_expand=bool(args.get("trace_expand", False)),
                    compression=args.get("compression", "none"),
                    compression_level=args.get("compression_level", "standard"),
                    compression_timeout_s=args.get("compression_timeout_s", 30.0),
                )
            elif name == "codrag_trace_search":
                result = await self.tool_trace_search(
                    query=args.get("query", ""),
                    kind=args.get("kind"),
                    limit=args.get("limit", 20),
                )
            elif name == "codrag_trace_neighbors":
                result = await self.tool_trace_neighbors(
                    node_id=args.get("node_id", ""),
                    direction=args.get("direction", "both"),
                    edge_kinds=args.get("edge_kinds"),
                    max_nodes=args.get("max_nodes", 25),
                )
            elif name == "codrag_trace_coverage":
                result = await self.tool_trace_coverage()
            else:
                raise MethodNotFoundError(f"Unknown tool: {name}")

            return {
                "content": [
                    {"type": "text", "text": json.dumps(result, indent=2)}
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

class MCPError(Exception):
    """Base MCP error."""
    code = INTERNAL_ERROR


class MethodNotFoundError(MCPError):
    code = METHOD_NOT_FOUND


class InvalidParamsError(MCPError):
    code = INVALID_PARAMS


class DaemonUnavailableError(MCPError):
    code = DAEMON_UNAVAILABLE


class DaemonError(MCPError):
    code = INTERNAL_ERROR


class IndexNotReadyError(DaemonError):
    code = INDEX_NOT_READY


class BuildInProgressError(DaemonError):
    code = BUILD_IN_PROGRESS


class ProjectNotFoundError(DaemonError):
    code = PROJECT_NOT_FOUND


class ProjectSelectionAmbiguousError(DaemonError):
    code = PROJECT_SELECTION_AMBIGUOUS


# =============================================================================
# stdio Transport
# =============================================================================

async def run_stdio(server: MCPServer) -> None:
    """
    Run the MCP server over stdio transport.
    
    Reads JSON-RPC messages from stdin, writes responses to stdout.
    Messages are newline-delimited.
    """
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())

    try:
        while True:
            line = await reader.readline()
            if not line:
                break

            line = line.decode("utf-8").strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": None,
                    "error": {"code": PARSE_ERROR, "message": f"Parse error: {e}"},
                }
                writer.write((json.dumps(error_response) + "\n").encode("utf-8"))
                await writer.drain()
                continue

            response = await server.handle_request(request)
            if response is not None:
                writer.write((json.dumps(response) + "\n").encode("utf-8"))
                await writer.drain()

    except Exception as e:
        logger.exception("Error in stdio loop")
    finally:
        await server.close()


class TrustedOriginMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_origins: List[str]):
        super().__init__(app)
        self.allowed_origins = allowed_origins

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        # If origin is present, it must be in allowed list
        # If no origin (e.g. curl/native apps), we allow it (assuming local binding protection)
        # Note: Browsers ALWAYS send Origin for CORS requests (like SSE)
        if origin:
            # Simple exact match check
            # For robust production use, this might need wildcard support
            if origin not in self.allowed_origins:
                # Check for localhost/loopback variations if configured
                is_local = origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")
                if not is_local:
                    return Response(status_code=403, content="Forbidden: Origin not allowed")
        
        return await call_next(request)


async def run_http(
    daemon_url: str,
    project_id: Optional[str],
    auto_detect: bool,
    host: str,
    port: int
) -> None:
    """Run the MCP server over HTTP SSE transport."""
    if not FastAPI or not uvicorn:
        logger.error("FastAPI/Uvicorn not installed. Cannot run HTTP transport.")
        sys.exit(1)

    app = FastAPI()
    
    # P05-R6: Implement Origin validation
    # By default, allow localhost origins since this is a local tool
    # In a future remote deployment, this should be configurable
    app.add_middleware(
        TrustedOriginMiddleware, 
        allowed_origins=[
            f"http://{host}:{port}",
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
            "null"  # Some local tools send null origin
        ]
    )
    
    # Session state: sessionId -> {"queue": asyncio.Queue, "server": MCPServer}
    sessions: Dict[str, Dict[str, Any]] = {}

    @app.get("/sse")
    async def sse(request: Request):
        session_id = uuid.uuid4().hex
        queue = asyncio.Queue()
        
        server = MCPServer(
            daemon_url=daemon_url,
            project_id=project_id,
            auto_detect=auto_detect
        )
        sessions[session_id] = {"queue": queue, "server": server}
        
        async def event_generator():
            endpoint = f"/message?sessionId={session_id}"
            yield f"event: endpoint\ndata: {endpoint}\n\n"
            
            try:
                while True:
                    # Keep connection alive with periodic comments if needed,
                    # but typically just wait for messages.
                    # uvicorn/starlette handles disconnects via cancelled error.
                    message = await queue.get()
                    yield f"event: message\ndata: {json.dumps(message)}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                await server.close()
                if session_id in sessions:
                    del sessions[session_id]

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.post("/message")
    async def handle_message(request: Request, sessionId: str):
        if sessionId not in sessions:
            return Response(status_code=404, content="Session not found")
            
        session = sessions[sessionId]
        queue = session["queue"]
        server = session["server"]
        
        try:
            body = await request.json()
            
            async def process():
                try:
                    response = await server.handle_request(body)
                    if response:
                        await queue.put(response)
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
            
            asyncio.create_task(process())
            return Response(status_code=202)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return Response(status_code=500, content=str(e))

    print(f"[codrag] Starting MCP HTTP server at http://{host}:{port}/sse", file=sys.stderr)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


# =============================================================================
# Entry Point
# =============================================================================

def main(
    daemon_url: str = "http://127.0.0.1:8400",
    project_id: Optional[str] = None,
    auto_detect: bool = False,
    debug: bool = False,
    log_file: Optional[str] = None,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8401,
) -> None:
    """Run the MCP server."""
    configure_logging(debug=bool(debug), log_file=log_file)
    
    if transport == "http":
        asyncio.run(run_http(
            daemon_url=daemon_url,
            project_id=project_id,
            auto_detect=auto_detect,
            host=host,
            port=port
        ))
    else:
        server = MCPServer(
            daemon_url=daemon_url,
            project_id=project_id,
            auto_detect=auto_detect,
        )
        asyncio.run(run_stdio(server))


if __name__ == "__main__":
    main()
