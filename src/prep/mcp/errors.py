"""
MCP error classes.
"""


class MCPError(Exception):
    """Base exception for MCP protocol errors."""
    def __init__(self, message: str, code: int = -32603):
        self.message = message
        self.code = code
        super().__init__(message)


class MethodNotFoundError(MCPError):
    def __init__(self, method: str):
        super().__init__(f"Method not found: {method}", code=-32601)


class InvalidParamsError(MCPError):
    def __init__(self, message: str):
        super().__init__(message, code=-32602)


class DaemonUnavailableError(MCPError):
    def __init__(self, message: str = "CoDRAG daemon is not running"):
        super().__init__(message, code=-32000)


class DaemonError(MCPError):
    def __init__(self, message: str, code: int = -32001):
        super().__init__(message, code=code)


class IndexNotReadyError(DaemonError):
    def __init__(self, message: str = "Index not built yet"):
        super().__init__(message, code=-32002)


class BuildInProgressError(DaemonError):
    def __init__(self, message: str = "Build already in progress"):
        super().__init__(message, code=-32003)


class ProjectNotFoundError(DaemonError):
    def __init__(self, message: str = "Project not found"):
        super().__init__(message, code=-32004)


class ProjectSelectionAmbiguousError(DaemonError):
    def __init__(self, message: str = "Multiple projects available — specify project_id"):
        super().__init__(message, code=-32005)
