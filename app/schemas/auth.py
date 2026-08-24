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
