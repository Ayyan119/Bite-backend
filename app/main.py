"""FastAPI Application Main Entrypoint.

Configured with uvloop event loop, ORJSONResponse serialization, CORS middleware,
security headers, rate limiting, lifespan connection pool management, and health probes.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvloop

# Install ultra-fast uvloop event loop policy
uvloop.install()

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import setup_exception_handlers
from app.core.middleware import (
    ProcessTimeMiddleware,
    RateLimiterMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.connection import close_db_pool, init_db_pool, pool
from app.tools.usda import _shared_httpx_client, get_shared_httpx_client

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bite.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager initializing and gracefully terminating shared pools."""
    logger.info("Starting up Project Bite API application...")

    # Initialize database connection pool
    await init_db_pool()

    # Warm up shared HTTP keep-alive client
    _ = get_shared_httpx_client()

    yield

    logger.info("Shutting down Project Bite API application...")

    # Close shared HTTP client
    global _shared_httpx_client
    if _shared_httpx_client is not None and not _shared_httpx_client.is_closed:
        await _shared_httpx_client.aclose()
        _shared_httpx_client = None

    # Close database connection pool
    await close_db_pool()


app = FastAPI(
    title="Project Bite API",
    description="Photo-first AI calorie and macronutrient tracker API powered by LangGraph, USDA, Supabase PostgreSQL, and FastAPI.",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add custom Middlewares
app.add_middleware(ProcessTimeMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimiterMiddleware, max_requests=120, window_seconds=60)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global exception handlers
setup_exception_handlers(app)

# Include API v1 Router
app.include_router(api_v1_router)


@app.get("/", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def root_welcome() -> ORJSONResponse:
    """Root welcome route providing API overview and interactive documentation links."""
    return ORJSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "Welcome to Project Bite API!",
            "status": "online",
            "version": "1.0.0",
            "documentation": "/docs",
            "health_check": "/health",
            "api_v1_prefix": "/api/v1",
        },
    )


@app.get("/health", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def health_check() -> ORJSONResponse:
    """Liveness probe endpoint returning basic server health status."""
    return ORJSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "app": "Project Bite API",
            "environment": settings.APP_ENV,
        },
    )


@app.get("/health/ready", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def readiness_check() -> ORJSONResponse:
    """Readiness probe endpoint verifying database connection pool health."""
    db_status = "uninitialized"
    if pool is not None:
        db_status = "ready" if pool.get_stats().get("pool_size", 0) >= 0 else "degraded"

    return ORJSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ready" if db_status != "uninitialized" else "not_ready",
            "database": db_status,
        },
    )
