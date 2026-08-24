"""FastAPI Dependency Injection Module.

Provides get_current_user security dependency performing in-memory cryptographic verification
of Supabase Bearer JWT tokens with an async TTLCache claims cache.
"""

import logging
from typing import Optional
from uuid import UUID

import cachetools
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.schemas.auth import CurrentUser

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Async claims in-memory LRU cache (max 1000 users, 60s TTL)
_claims_cache: cachetools.TTLCache = cachetools.TTLCache(maxsize=1000, ttl=60)


def get_jwt_secret() -> str:
    """Retrieve Supabase JWT secret or dev fallback."""
    if settings.SUPABASE_JWT_SECRET:
        return settings.SUPABASE_JWT_SECRET
    # Development fallback secret for testing environments
    return "super-secret-jwt-key-for-dev-testing"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> CurrentUser:
    """FastAPI security dependency validating Supabase JWT tokens.

    Decodes JWT token in-memory using cryptographic signature verification and
    caches resolved user contexts in RAM to eliminate database/network overhead (<0.01ms resolution).
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()

    # Check RAM cache first
    if token in _claims_cache:
        return _claims_cache[token]

    secret = get_jwt_secret()

    try:
        # Decode and cryptographically verify signature
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        # In development mode, if signature fails due to dummy key, allow unverified decode for mock tokens if dev environment
        if settings.APP_ENV == "development" and not settings.SUPABASE_JWT_SECRET:
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid authentication token: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication token signature or claims: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing subject (sub) claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(str(sub))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token contains invalid UUID subject (sub) claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email")
    role = payload.get("role", "authenticated")

    current_user = CurrentUser(user_id=user_id, email=email, role=role)

    # Store in RAM cache
    _claims_cache[token] = current_user
    return current_user


def clear_claims_cache() -> None:
    """Utility function to clear token claims cache (used in unit tests)."""
    _claims_cache.clear()
