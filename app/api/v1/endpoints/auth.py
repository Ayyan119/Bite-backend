"""Authentication and Development Token Generator Router."""

import logging
import time
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import ORJSONResponse

from app.api.deps import get_jwt_secret
from app.schemas.auth import DevTokenRequest, DevTokenResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/dev-token",
    response_model=DevTokenResponse,
    status_code=status.HTTP_200_OK,
    response_class=ORJSONResponse,
)
async def generate_dev_token(
    payload: DevTokenRequest = DevTokenRequest(),
) -> DevTokenResponse:
    """Generate a valid, signed Supabase Bearer JWT token for local API testing in Swagger UI.

    No password required for development testing. Copy the returned 'access_token' and click
    the green 'Authorize' button in Swagger UI to authenticate.
    """
    if payload.user_id:
        try:
            target_user_id = UUID(payload.user_id.strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provided user_id is not a valid UUID string.",
            )
    else:
        target_user_id = uuid4()

    now = int(time.time())
    expires_in = 86400  # 24 hours validity for testing convenience

    jwt_payload = {
        "sub": str(target_user_id),
        "email": payload.email or "developer@example.com",
        "role": "authenticated",
        "iat": now,
        "exp": now + expires_in,
    }

    secret = get_jwt_secret()
    signed_jwt = jwt.encode(jwt_payload, secret, algorithm="HS256")

    return DevTokenResponse(
        access_token=signed_jwt,
        token_type="bearer",
        expires_in=expires_in,
        user_id=target_user_id,
        email=payload.email,
    )
