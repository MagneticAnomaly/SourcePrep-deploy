"""
Backward-compat wrapper — re-exports everything from the mcp subpackage.

Import sites that do ``from codrag.mcp_server import MCPServer`` etc.
continue to work without modification.
"""
# These module-level names are needed because tests patch them via
# ``patch("codrag.mcp_server.Path")`` etc.
from pathlib import Path  # noqa: F401
from codrag.mcp import (  # noqa: F401
    MCPServer,
    configure_logging,
    MCPError,
    MethodNotFoundError,
    InvalidParamsError,
    DaemonUnavailableError,
    DaemonError,
    IndexNotReadyError,
    BuildInProgressError,
    ProjectNotFoundError,
    ProjectSelectionAmbiguousError,
    run_stdio,
    TrustedOriginMiddleware,
    run_http,
)

# Constants that tests and other code import from this module
from codrag.mcp.server import (  # noqa: F401
    MCP_PROTOCOL_VERSION,
    JSONRPC_VERSION,
    MAX_CONTEXT_K,
    MAX_CONTEXT_CHARS,
)
from codrag.mcp_tools import TOOLS  # noqa: F401

# The main() entrypoint needs to stay here for cli.py compatibility
from codrag.mcp.server import MCPServer as _MCPServer  # noqa: F811


def main(
    daemon_url: str = "http://127.0.0.1:8400",
    project_id: str | None = None,
    auto_detect: bool = True,
    debug: bool = False,
    log_file: str | None = None,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8401,
) -> None:
    """Run the MCP server (stdio or HTTP transport)."""
    import asyncio
    import sys
    import logging

    configure_logging(debug=debug, log_file=log_file)

    logger = logging.getLogger(__name__)

    if transport == "http":
        logger.info("Starting MCP server (HTTP SSE) on %s:%d", host, port)
        asyncio.run(run_http(
            daemon_url=daemon_url,
            project_id=project_id,
            auto_detect=auto_detect,
            host=host,
            port=port,
        ))
    else:
        server = _MCPServer(
            daemon_url=daemon_url,
            project_id=project_id,
            auto_detect=auto_detect,
        )
        logger.info("Starting MCP server (stdio)")
        try:
            asyncio.run(run_stdio(server))
        except KeyboardInterrupt:
            logger.info("MCP server stopped")
        finally:
            import asyncio as _aio
            try:
                _aio.run(server.close())
            except Exception:
                pass
