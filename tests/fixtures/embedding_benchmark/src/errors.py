"""Custom exception hierarchy and error handling utilities."""

from typing import Any, Dict, Optional


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, code: str = "UNKNOWN", status: int = 500):
        self.message = message
        self.code = code
        self.status = status
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        return {"error": self.code, "message": self.message, "status": self.status}


class NotFoundError(AppError):
    """Resource not found."""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            code="NOT_FOUND",
            status=404,
        )


class ConflictError(AppError):
    """Resource already exists or state conflict."""
    def __init__(self, message: str):
        super().__init__(message=message, code="CONFLICT", status=409)


class AuthenticationError(AppError):
    """Invalid credentials or expired token."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, code="AUTH_FAILED", status=401)


class AuthorizationError(AppError):
    """Insufficient permissions."""
    def __init__(self, action: str, resource: str):
        super().__init__(
            message=f"Not authorized to {action} on {resource}",
            code="FORBIDDEN",
            status=403,
        )


class RateLimitError(AppError):
    """Too many requests."""
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(
            message=f"Rate limit exceeded. Retry after {retry_after}s",
            code="RATE_LIMITED",
            status=429,
        )


def error_handler(error: Exception) -> Dict[str, Any]:
    """Convert exceptions to API-friendly error responses."""
    if isinstance(error, AppError):
        return error.to_dict()
    return {"error": "INTERNAL", "message": "An unexpected error occurred", "status": 500}
