"""
MCP transport layers — stdio and Streamable HTTP.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import StreamingResponse
    from fastapi.middleware.base import BaseHTTPMiddleware
    import uvicorn
except ImportError:
    FastAPI = None
    uvicorn = None
    BaseHTTPMiddleware = object  # type: ignore

from typing import TYPE_CHECKING

from .errors import MCPError

if TYPE_CHECKING:
    from .server import MCPServer

logger = logging.getLogger(__name__)


async def run_stdio(server: "MCPServer") -> None:
    """
    Run the MCP server over stdio transport.
    
    Reads JSON-RPC messages from stdin, writes responses to stdout.
    Messages are newline-delimited.
    """
    loop = asyncio.get_event_loop()

    def read_line():
        return sys.stdin.readline()

    try:
        while True:
            # Read line in a separate thread to avoid blocking the event loop
            line_str = await loop.run_in_executor(None, read_line)
            if not line_str:
                break

            line_str = line_str.strip()
            if not line_str:
                continue

            try:
                request = json.loads(line_str)
            except json.JSONDecodeError as e:
                from .server import JSONRPC_VERSION
                from .errors import PARSE_ERROR
                error_response = {
                    "jsonrpc": JSONRPC_VERSION,
                    "id": None,
                    "error": {"code": PARSE_ERROR, "message": f"Parse error: {e}"},
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
                continue

            response = await server.handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

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
    from .server import MCPServer  # runtime import to avoid circular
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

