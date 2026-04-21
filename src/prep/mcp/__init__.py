"""
MCP subpackage — Model Context Protocol integration.

Re-exports MCPServer and key classes for backward compatibility with
``from prep.mcp_server import MCPServer``.
"""
from .server import MCPServer, configure_logging
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
from .transport import run_stdio, TrustedOriginMiddleware, run_http

__all__ = [
    "MCPServer",
    "configure_logging",
    "MCPError",
    "MethodNotFoundError",
    "InvalidParamsError",
    "DaemonUnavailableError",
    "DaemonError",
    "IndexNotReadyError",
    "BuildInProgressError",
    "ProjectNotFoundError",
    "ProjectSelectionAmbiguousError",
    "run_stdio",
    "TrustedOriginMiddleware",
    "run_http",
]
