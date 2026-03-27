"""
CoDRAG Direct MCP Server.

Implements the MCP protocol by directly calling CoDRAG core components (CodeIndex, TraceIndex)
in the same process, avoiding the need for a separate daemon.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from codrag.core import CodeIndex, Embedder, FakeEmbedder, OllamaEmbedder, TraceIndex
from codrag.mcp_tools import TOOLS

# Configure logging to stderr (stdout reserved for MCP JSON-RPC)
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Constants
MCP_PROTOCOL_VERSION = "2024-11-05"
JSONRPC_VERSION = "2.0"

# Error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class MCPError(Exception):
    code = INTERNAL_ERROR


class MethodNotFoundError(MCPError):
    code = METHOD_NOT_FOUND


class InvalidParamsError(MCPError):
    code = INVALID_PARAMS


class DirectMCPServer:
    """
    Direct Mode MCP Server.

    Holds the CodeIndex in memory and runs operations in thread pool
    to avoid blocking the asyncio event loop (stdio transport).
    """

    def __init__(
        self,
        repo_root: Path | str,
        index_dir: Optional[Path | str] = None,
        ollama_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        embedder: Optional[Embedder] = None,
    ):
        self.repo_root = Path(repo_root).resolve()

        # Default index location: .codrag/index inside repo, or ./codrag_data
        if index_dir:
            self.index_dir = Path(index_dir).resolve()
        else:
            self.index_dir = self.repo_root / ".codrag" / "index"

        self.ollama_url = ollama_url
        self.model = model
        self._injected_embedder = embedder  # For testing without Ollama

        self._index: Optional[CodeIndex] = None
        self._trace_index: Optional[TraceIndex] = None
        self._build_lock = asyncio.Lock()
        self._building = False

        # Ensure we don't block the event loop with heavy init
        self._init_done = False

    async def _ensure_init(self):
        if self._init_done:
            return

        # Lazy load index in thread
        await asyncio.to_thread(self._load_index)
        self._init_done = True

    def _load_index(self):
        """Synchronous load of index components."""
        try:
            embedder = self._injected_embedder or OllamaEmbedder(
                model=self.model, base_url=self.ollama_url
            )
            self._index = CodeIndex(index_dir=self.index_dir, embedder=embedder)

            # Trace index shares the same dir usually
            self._trace_index = TraceIndex(index_dir=self.index_dir)
            if self._trace_index.exists():
                self._trace_index.load()

            logger.info(f"Loaded index from {self.index_dir}")
        except Exception as e:
            logger.error(f"Failed to load index: {e}")

    # -------------------------------------------------------------------------
    # Tool Implementations
    # -------------------------------------------------------------------------

    async def tool_status(self) -> Dict[str, Any]:
        await self._ensure_init()

        stats = {
            "loaded": False,
            "total_documents": 0,
            "model": self.model,
            "built_at": None,
        }

        if self._index:
            try:
                # CodeIndex.stats() is fast/in-memory usually, but let's be safe
                s = await asyncio.to_thread(self._index.stats)
                stats.update(s)
            except Exception as e:
                logger.error(f"Error getting stats: {e}")

        return {
            "daemon": "direct_mode",
            "repo_root": str(self.repo_root),
            "index_dir": str(self.index_dir),
            "index_loaded": stats.get("loaded", False),
            "total_documents": stats.get("total_documents", 0),
            "model": stats.get("model", "unknown"),
            "built_at": stats.get("built_at"),
            "building": self._building,
        }

    async def tool_build(self, full: bool = False) -> Dict[str, Any]:
        if self._building:
            return {"status": "already_building", "message": "Build already in progress"}

        # Fire and forget build task
        asyncio.create_task(self._run_build(full))
        return {
            "status": "started",
            "message": "Build started in background. Check status for progress.",
        }

    async def _run_build(self, full: bool):
        async with self._build_lock:
            self._building = True
            try:
                await self._ensure_init()
                if not self._index:
                    return

                logger.info(f"Starting build (full={full})...")

                # Progress callback for build visibility
                def on_progress(file_path: str, current: int, total: int) -> None:
                    if current == 1 or current == total or current % 50 == 0:
                        logger.info(f"Build progress: {current}/{total} files ({file_path})")

                # Run the blocking build in a thread
                await asyncio.to_thread(
                    self._index.build,
                    repo_root=self.repo_root,
                    include_globs=None,
                    exclude_globs=None,
                    progress_callback=on_progress,
                )

                logger.info("Build completed")
            except Exception as e:
                logger.error(f"Build failed: {e}")
            finally:
                self._building = False

    async def tool_search(
        self,
        query: str,
        k: int = 8,
        min_score: float = 0.15,
    ) -> Dict[str, Any]:
        if not query.strip():
            raise InvalidParamsError("query is required")

        await self._ensure_init()
        if not self._index or not self._index.is_loaded():
            return {
                "query": query,
                "count": 0,
                "results": [],
                "error": "Index not loaded. Run codrag_build first.",
            }

        # Run blocking search in thread
        results = await asyncio.to_thread(self._index.search, query=query, k=k, min_score=min_score)

        formatted = []
        for r in results:
            doc = r.doc
            formatted.append(
                {
                    "path": doc.get("source_path", ""),
                    "section": doc.get("section", ""),
                    "score": round(r.score, 3),
                    "content": doc.get("content", "")[:500],
                }
            )

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
    ) -> Dict[str, Any]:
        if not query.strip():
            raise InvalidParamsError("query is required")

        await self._ensure_init()
        if not self._index or not self._index.is_loaded():
            return {"context": "", "error": "Index not loaded. Run codrag_build first."}

        # Run blocking context assembly in thread
        data = await asyncio.to_thread(
            self._index.get_context_structured,
            query=query,
            k=k,
            max_chars=max_chars,
            min_score=0.15,
        )

        return {
            "context": data.get("context", ""),
            "chunks_used": len(data.get("chunks", [])),
            "total_chars": data.get("total_chars", 0),
            "estimated_tokens": data.get("estimated_tokens", 0),
        }

    async def tool_hi(self) -> Dict[str, Any]:
        """Project overview and context discovery (direct mode)."""
        await self._ensure_init()

        project_name = self.repo_root.name

        # Index stats
        index_exists = False
        total_chunks = 0
        built_at = None
        if self._index:
            try:
                s = await asyncio.to_thread(self._index.stats)
                index_exists = s.get("loaded", False)
                total_chunks = s.get("total_documents", 0)
                built_at = s.get("built_at")
            except Exception:
                pass

        # Trace stats
        trace_enabled = False
        total_nodes = 0
        total_edges = 0
        if self._trace_index and self._trace_index.exists():
            trace_enabled = True
            try:
                total_nodes = (
                    len(self._trace_index.nodes()) if hasattr(self._trace_index, "nodes") else 0
                )
                total_edges = (
                    len(self._trace_index.edges()) if hasattr(self._trace_index, "edges") else 0
                )
            except Exception:
                pass

        # Build conversational summary
        lines: List[str] = []

        # What I'm looking at (lead with context, not status)
        if self._building:
            lines.append(f"I'm setting up **{project_name}** — the index is building right now.")
        elif index_exists:
            lines.append(
                f"I'm looking at **{project_name}** — {total_chunks} chunks indexed across the project."
            )
        else:
            lines.append(
                f"I see **{project_name}** but there's no index yet. I'll need one before I can help with code questions."
            )

        if trace_enabled and total_nodes > 0:
            lines.append(
                f"I can also follow the code graph ({total_nodes} nodes, {total_edges} edges) to trace imports, calls, and structural relationships."
            )

        lines.append("")

        # Health observations
        observations: List[str] = []
        if not index_exists:
            observations.append("No index exists yet — run `codrag_build` to get started.")

        if observations:
            lines.append("**Heads up:**")
            for obs in observations:
                lines.append(f"- {obs}")
            lines.append("")
        else:
            lines.append("Everything looks good — index is loaded and ready.\n")

        # Suggested prompts
        prompts: List[str] = []
        if not index_exists:
            prompts.append("Build my index: `codrag_build`")
        else:
            prompts.append(f"How is {project_name} structured? What are the main modules?")
            prompts.append(f"Find the main entry point of {project_name}.")
            prompts.append("What are the key data models or types?")
            if trace_enabled:
                prompts.append("What are the most connected modules in the code graph?")

        if prompts:
            lines.append("**Here are some things I can help with:**")
            for i, p in enumerate(prompts[:6], 1):
                lines.append(f"{i}. {p}")
            lines.append("")

        summary_md = "\n".join(lines)

        diagnostics = {
            "project_name": project_name,
            "mode": "direct",
            "repo_root": str(self.repo_root),
            "index_loaded": index_exists,
            "total_chunks": total_chunks,
            "building": self._building,
            "trace_enabled": trace_enabled,
            "trace_nodes": total_nodes,
            "trace_edges": total_edges,
        }

        ai_note = (
            "STANDALONE (user only said 'hi_codrag'): Present the summary above "
            "conversationally — tell the user what you're looking at, mention any "
            "health issues naturally, and offer the suggested prompts as numbered "
            "options they can pick from. Speak in first person: 'I can see...', "
            "'I'm looking at...'. Keep it warm and helpful.\n\n"
            "WITH A QUESTION (user said 'hi_codrag' AND asked something): Briefly "
            "acknowledge what you see (1-2 sentences), then address their question. "
            "If you need specific code context to answer, call codrag_search with "
            "their question."
        )

        return {
            "_ai_note": ai_note,
            "summary": summary_md,
            "diagnostics": diagnostics,
        }

    # -------------------------------------------------------------------------
    # Protocol Handlers
    # -------------------------------------------------------------------------

    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": "codrag-direct",
                "version": "0.1.0",
            },
        }

    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"tools": TOOLS}

    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
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
                )
            elif name == "hi_codrag":
                result = await self.tool_hi()
            else:
                raise MethodNotFoundError(f"Unknown tool: {name}")

            return {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                "isError": False,
            }

        except Exception as e:
            return {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            }

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        if req_id is None:
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
            logger.exception("Internal error")
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "error": {"code": INTERNAL_ERROR, "message": str(e)},
            }

    async def close(self):
        """Cleanup resources."""
        pass


async def run_stdio(server: DirectMCPServer) -> None:
    """Run the MCP server over stdio transport."""
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
