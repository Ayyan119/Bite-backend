"""Unit tests for FastAPI application scaffold, uvloop event policy, lifespan, and health endpoints."""

import pytest
import uvloop
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_uvloop_installed():
    """Verify uvloop event policy is installed and active."""
    policy = uvloop.EventLoopPolicy()
    assert isinstance(policy, uvloop.EventLoopPolicy)


@pytest.mark.asyncio
async def test_root_welcome_endpoint():
    """Verify GET / returns status 200 and root welcome payload."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "documentation" in data


@pytest.mark.asyncio
async def test_health_liveness_endpoint():
    """Verify GET /health returns status 200 and correct JSON payload."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == "Project Bite API"


@pytest.mark.asyncio
async def test_health_readiness_endpoint():
    """Verify GET /health/ready returns status 200 and database pool state."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data


@pytest.mark.asyncio
async def test_global_exception_handler_404():
    """Verify 404 error response format from global exception handlers."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/nonexistent-route")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == 404
