"""Tests for HTTP middleware components."""


def test_rate_limiter_allows_within_limit():
    from src.middleware import RateLimiter
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        assert limiter.is_allowed("client1") is True


def test_rate_limiter_blocks_over_limit():
    from src.middleware import RateLimiter
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    limiter.is_allowed("client1")
    limiter.is_allowed("client1")
    assert limiter.is_allowed("client1") is False


def test_cors_adds_headers_for_allowed_origin():
    from src.middleware import CORSMiddleware
    cors = CORSMiddleware()
    headers = cors.add_cors_headers("http://localhost:3000", {})
    assert "Access-Control-Allow-Origin" in headers


def test_request_logger_does_not_crash():
    from src.middleware import RequestLogger
    logger = RequestLogger()
    logger.log_request("GET", "/api/users", 200, 12.5)
