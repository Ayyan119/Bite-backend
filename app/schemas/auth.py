"""Authentication Pydantic schemas for Supabase user security context."""

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class CurrentUser(BaseModel):
    """Pydantic model representing authenticated user context extracted from JWT."""

    user_id: UUID = Field(
        description="Unique Supabase auth user identifier (sub claim)."
    )
    email: Optional[EmailStr] = Field(default=None, description="User email address.")
    role: str = Field(default="authenticated", description="Supabase user role.")


class DevTokenRequest(BaseModel):
    """Request payload for generating a development JWT token in Swagger UI."""

    user_id: Optional[str] = Field(
        default=None, description="Optional UUID string for test user ID."
    )
    email: Optional[EmailStr] = Field(
        default="developer@example.com", description="User email address."
    )


class DevTokenResponse(BaseModel):
    """Response payload containing signed Bearer JWT token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user_id: UUID
    email: Optional[EmailStr] = None
