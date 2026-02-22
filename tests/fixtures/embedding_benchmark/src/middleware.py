"""HTTP middleware for request/response processing."""

import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API endpoints."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict = {}

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        bucket = self._buckets.get(client_id, {"count": 0, "reset_at": now + self.window_seconds})
        if now > bucket["reset_at"]:
            bucket = {"count": 0, "reset_at": now + self.window_seconds}
        bucket["count"] += 1
        self._buckets[client_id] = bucket
        return bucket["count"] <= self.max_requests


class RequestLogger:
    """Middleware that logs incoming requests and response times."""

    def log_request(self, method: str, path: str, status_code: int, duration_ms: float):
        logger.info("%s %s → %d (%.1fms)", method, path, status_code, duration_ms)


class CORSMiddleware:
    """Cross-Origin Resource Sharing middleware."""

    ALLOWED_ORIGINS = ["http://localhost:3000", "https://app.example.com"]

    def add_cors_headers(self, origin: str, response_headers: dict) -> dict:
        if origin in self.ALLOWED_ORIGINS or "*" in self.ALLOWED_ORIGINS:
            response_headers["Access-Control-Allow-Origin"] = origin
            response_headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE"
            response_headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response_headers
