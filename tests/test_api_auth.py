"""Unit tests for Supabase JWT authentication dependency & claims LRU cache."""

import time
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.responses import ORJSONResponse
from httpx import ASGITransport, AsyncClient

from app.api.deps import clear_claims_cache, get_current_user, get_jwt_secret
from app.core.config import settings
from app.main import app
from app.schemas.auth import CurrentUser

# Create test router exposing protected test route
test_app = FastAPI(default_response_class=ORJSONResponse)


@test_app.get("/protected")
async def protected_route(user: CurrentUser = Depends(get_current_user)):
    return {"user_id": str(user.user_id), "email": user.email, "role": user.role}


@pytest.fixture(autouse=True)
def cleanup_cache():
    clear_claims_cache()
    yield
    clear_claims_cache()


def create_test_jwt(
    user_id: str | None = None,
    email: str = "user@example.com",
    role: str = "authenticated",
    expires_in: int = 3600,
    secret: str | None = None,
) -> str:
    """Generate a signed JWT token for testing."""
    if user_id is None:
        user_id = str(uuid4())

    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + expires_in,
    }
    jwt_secret = secret or get_jwt_secret()
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


@pytest.mark.asyncio
async def test_protected_route_missing_token():
    """Verify 401 response when no Authorization header is provided."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        response = await client.get("/protected")
        assert response.status_code == 401
        assert "Missing or invalid Bearer" in response.json()["detail"]


@pytest.mark.asyncio
async def test_protected_route_valid_jwt():
    """Verify successful authentication with a valid signed JWT token."""
    test_user_id = str(uuid4())
    token = create_test_jwt(user_id=test_user_id, email="test@example.com")

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/protected", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == test_user_id
        assert data["email"] == "test@example.com"
        assert data["role"] == "authenticated"


@pytest.mark.asyncio
async def test_protected_route_ttl_cache_hit():
    """Verify claims cache serves subsequent requests instantaneously."""
    test_user_id = str(uuid4())
    token = create_test_jwt(user_id=test_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        # First call populates cache
        resp1 = await client.get("/protected", headers=headers)
        assert resp1.status_code == 200

        # Second call hits RAM cache
        resp2 = await client.get("/protected", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["user_id"] == test_user_id


@pytest.mark.asyncio
async def test_protected_route_expired_jwt():
    """Verify 401 response when JWT token is expired."""
    token = create_test_jwt(expires_in=-10)  # Expired 10 seconds ago
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        response = await client.get("/protected", headers=headers)
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_protected_route_invalid_signature():
    """Verify 401 response when JWT signature is invalid."""
    token = create_test_jwt(secret="wrong-secret-key-1234567890")
    headers = {"Authorization": f"Bearer {token}"}

    # Temporarily set SUPABASE_JWT_SECRET to enforce strict signature check
    original_secret = settings.SUPABASE_JWT_SECRET
    try:
        settings.SUPABASE_JWT_SECRET = "real-production-secret-123"
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://testserver"
        ) as client:
            response = await client.get("/protected", headers=headers)
            assert response.status_code == 401
            assert "invalid" in response.json()["detail"].lower()
    finally:
        settings.SUPABASE_JWT_SECRET = original_secret


@pytest.mark.asyncio
async def test_protected_route_invalid_uuid_claim():
    """Verify 401 response when subject claim is not a valid UUID."""
    now = int(time.time())
    payload = {"sub": "not-a-valid-uuid", "email": "a@b.com", "exp": now + 3600}
    token = jwt.encode(payload, get_jwt_secret(), algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://testserver"
    ) as client:
        response = await client.get("/protected", headers=headers)
        assert response.status_code == 401
        assert "invalid UUID" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_dev_token_endpoint():
    """Verify POST /api/v1/auth/dev-token generates a valid signed Bearer JWT token."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/auth/dev-token", json={"email": "tester@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["email"] == "tester@example.com"
