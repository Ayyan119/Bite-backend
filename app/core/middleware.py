"""Custom ASGI Middlewares for Security Headers, Performance Metrics, and In-Memory Rate Limiting."""

import logging
import time
from typing import Dict, List

from fastapi import Request, Response, status
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces OWASP production security headers on all outgoing HTTP responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Allow Swagger UI and ReDoc to load CDN bundles and inline styles/scripts for interactive documentation
        if request.url.path in ("/docs", "/redoc", "/openapi.json"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:;"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'"

        if settings.APP_ENV != "development":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        return response


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    """Measures request execution time in milliseconds and injects X-Process-Time header."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time"] = f"{process_time_ms:.2f}ms"
        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window rate limiter per client IP address.

    Limits request rate (default 120 requests/minute) with zero network overhead.
    """

    def __init__(self, app, max_requests: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._ip_timestamps: Dict[str, List[float]] = {}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Exclude health probe endpoints and docs from rate limiting
        if request.url.path in (
            "/health",
            "/health/ready",
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()

        # Clean timestamps older than window_seconds
        timestamps = self._ip_timestamps.get(client_ip, [])
        timestamps = [ts for ts in timestamps if now - ts < self.window_seconds]

        if len(timestamps) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return ORJSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": 429,
                        "message": "Too many requests. Please slow down.",
                    }
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        timestamps.append(now)
        self._ip_timestamps[client_ip] = timestamps
        return await call_next(request)
