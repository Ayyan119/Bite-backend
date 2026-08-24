"""Unit tests for FastAPI security headers, timing metrics, and rate limiter middleware stack."""

import pytest
from fastapi import FastAPI, status
from fastapi.responses import ORJSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.middleware import (
    ProcessTimeMiddleware,
    RateLimiterMiddleware,
    SecurityHeadersMiddleware,
)
from app.main import app


@pytest.mark.asyncio
async def test_security_headers_middleware():
    """Verify security headers are present on all outgoing HTTP responses."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert (
            response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        )
        assert response.headers.get("Content-Security-Policy") == "default-src 'self'"


@pytest.mark.asyncio
async def test_process_time_middleware():
    """Verify X-Process-Time header is injected on all responses."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        process_time = response.headers.get("X-Process-Time")
        assert process_time is not None
        assert process_time.endswith("ms")


@pytest.mark.asyncio
async def test_rate_limiter_middleware():
    """Verify RateLimiterMiddleware blocks excessive requests with 429 status code."""
    test_app = FastAPI(default_response_class=ORJSONResponse)
    test_app.add_middleware(RateLimiterMiddleware, max_requests=3, window_seconds=60)

    @test_app.get("/test-limit")
    async def limited_route():
        return {"status": "ok"}

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        # First 3 requests succeed
        for _ in range(3):
            res = await client.get("/test-limit")
            assert res.status_code == 200

        # 4th request gets blocked with 429 Too Many Requests
        blocked_res = await client.get("/test-limit")
        assert blocked_res.status_code == 429
        assert blocked_res.headers.get("Retry-After") == "60"
        assert "Too many requests" in blocked_res.json()["error"]["message"]
