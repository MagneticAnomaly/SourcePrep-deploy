from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

import anyio
import httpx
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server


def _api_base() -> str:
    return (os.environ.get("RAG_API_BASE") or "http://localhost:5000/api/self-rag").rstrip("/")


def _timeout_s() -> float:
    try:
        return float(os.environ.get("RAG_TIMEOUT_S") or "30")
    except Exception:
        return 30.0


async def _http_json(path: str, method: str = "GET", body: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{_api_base()}{path}"
    timeout = httpx.Timeout(_timeout_s())

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(
            method,
            url,
            headers={"Content-Type": "application/json"} if body is not None else None,
            json=body,
        )

    if resp.status_code >= 400:
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        msg = "HTTP %s" % resp.status_code
        if isinstance(data, dict) and data.get("error"):
            msg = str(data.get("error"))
        raise ValueError(f"{method} {url} failed: {msg}")

    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


app = Server("mcp-local-rag")


@app.list_tools()
async def list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="local_rag_status",
            title="Local RAG Status",
            description="Check status of the local RAG index server.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="local_rag_build",
            title="Local RAG Build",
            description=(
                "Trigger an async build of the local RAG index. "
                "Arguments are passed through to the underlying HTTP /build endpoint."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_root": {"type": "string"},
                    "roots": {"type": "array", "items": {"type": "string"}},
                    "repo_root": {"type": "string"},
                    "include_globs": {"type": "array", "items": {"type": "string"}},
                    "exclude_globs": {"type": "array", "items": {"type": "string"}},
                    "max_file_bytes": {"type": "integer"},
                },
            },
        ),
        types.Tool(
            name="local_rag_search",
            title="Local RAG Search",
            description="Search the local RAG index and return scored chunks with metadata.",
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer"},
                    "min_score": {"type": "number"},
                },
            },
        ),
        types.Tool(
            name="local_rag_context",
            title="Local RAG Context",
            description=(
                "Return an assembled context string (best chunks) for LLM injection. "
                "Use this when you want ready-to-use context for a prompt. "
                "Headers include source paths by default for attribution."
            ),
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "k": {"type": "integer", "description": "Number of chunks to include (default: 5)"},
                    "max_chars": {"type": "integer", "description": "Maximum total characters (default: 6000)"},
                    "include_sources": {"type": "boolean", "description": "Include source file paths in headers (default: true)"},
                    "include_scores": {"type": "boolean", "description": "Include relevance scores in headers (default: false)"},
                    "min_score": {"type": "number", "description": "Minimum relevance score threshold (default: 0.15)"},
                    "structured": {"type": "boolean", "description": "Return structured response with metadata (default: false)"},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.ContentBlock]:
    if name == "local_rag_status":
        data = await _http_json("/status", method="GET")
        return [types.TextContent(type="text", text=json.dumps(data, indent=2))]

    if name == "local_rag_build":
        payload = dict(arguments or {})
        data = await _http_json("/build", method="POST", body=payload)
        return [types.TextContent(type="text", text=json.dumps(data, indent=2))]

    if name == "local_rag_search":
        query = (arguments.get("query") or "").strip()
        if not query:
            raise ValueError("Missing required argument 'query'")

        payload: Dict[str, Any] = {"query": query}
        if arguments.get("k") is not None:
            payload["k"] = arguments.get("k")
        if arguments.get("min_score") is not None:
            payload["min_score"] = arguments.get("min_score")

        data = await _http_json("/search", method="POST", body=payload)
        return [types.TextContent(type="text", text=json.dumps(data, indent=2))]

    if name == "local_rag_context":
        query = (arguments.get("query") or "").strip()
        if not query:
            raise ValueError("Missing required argument 'query'")

        payload: Dict[str, Any] = {"query": query}
        if arguments.get("k") is not None:
            payload["k"] = arguments.get("k")
        if arguments.get("max_chars") is not None:
            payload["max_chars"] = arguments.get("max_chars")
        if arguments.get("include_sources") is not None:
            payload["include_sources"] = arguments.get("include_sources")
        if arguments.get("include_scores") is not None:
            payload["include_scores"] = arguments.get("include_scores")
        if arguments.get("min_score") is not None:
            payload["min_score"] = arguments.get("min_score")
        if arguments.get("structured") is not None:
            payload["structured"] = arguments.get("structured")

        data = await _http_json("/context", method="POST", body=payload)

        # If structured mode, return full JSON; otherwise just context string
        if arguments.get("structured"):
            return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
        else:
            ctx = ""
            if isinstance(data, dict) and data.get("context") is not None:
                ctx = str(data.get("context") or "")
            return [types.TextContent(type="text", text=ctx)]

    raise ValueError(f"Unknown tool: {name}")


async def _run_stdio() -> None:
    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())


def main() -> None:
    try:
        print("mcp-local-rag: starting", file=sys.stderr, flush=True)
        anyio.run(_run_stdio)
    except Exception as e:
        print(f"mcp-local-rag: fatal error: {e}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
