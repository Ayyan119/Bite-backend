"""Authentication Pydantic schemas for Supabase user security context and login."""

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


class LoginRequest(BaseModel):
    """User login request with email and password."""

    email: EmailStr = Field(
        default="alex.morgan@bite.app",
        description="User email address.",
    )
    password: str = Field(
        default="bite12345",
        min_length=4,
        description="User account password.",
    )


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(description="User email address.")
    password: str = Field(min_length=4, description="User account password.")
    display_name: Optional[str] = Field(default=None, description="User display name.")
    age: Optional[int] = Field(
        default=None, ge=10, le=120, description="Optional user age in years."
    )
    height_cm: Optional[float] = Field(
        default=None, ge=50.0, le=250.0, description="Optional height in cm."
    )
    weight_kg: Optional[float] = Field(
        default=None, ge=20.0, le=300.0, description="Optional weight in kg."
    )
    gender: Optional[str] = Field(
        default=None, description="Optional gender: male, female, other."
    )
    activity_level: Optional[str] = Field(
        default=None,
        description="Optional activity level: sedentary, light, moderate, active, extra.",
    )
    primary_goal: Optional[str] = Field(
        default=None,
        description="Optional primary goal: weight_loss, muscle_gain, maintenance.",
    )


class AuthResponse(BaseModel):
    """Response payload containing signed Bearer JWT token and user profile summary."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user_id: UUID
    email: EmailStr
    display_name: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    gender: Optional[str] = None
    bmr: Optional[float] = None
    tdee: Optional[float] = None
    target_calories: Optional[float] = None


class DevTokenRequest(BaseModel):
    """Request payload for generating a development JWT token in Swagger UI."""

    user_id: Optional[str] = Field(
        default=None, description="Optional UUID string for test user ID."
    )
    email: Optional[EmailStr] = Field(
        default="alex.morgan@bite.app", description="User email address."
    )


class DevTokenResponse(BaseModel):
    """Response payload containing signed Bearer JWT token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user_id: UUID
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
