from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileBase(BaseModel):
    """Base Pydantic model for user profile."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    email: EmailStr = Field(description="User email address")
    display_name: str | None = Field(
        default=None, max_length=100, description="Display name"
    )
    bmr: float | None = Field(
        default=None, gt=0, description="Basal Metabolic Rate in kcal"
    )
    tdee: float | None = Field(
        default=None, gt=0, description="Total Daily Energy Expenditure in kcal"
    )
    target_calories: float | None = Field(
        default=None, gt=0, description="Target daily calories"
    )
    target_protein_g: float | None = Field(
        default=None, ge=0, description="Target daily protein in grams"
    )
    target_carbs_g: float | None = Field(
        default=None, ge=0, description="Target daily carbs in grams"
    )
    target_fat_g: float | None = Field(
        default=None, ge=0, description="Target daily fat in grams"
    )


class ProfileCreate(ProfileBase):
    """Schema for creating a profile (requires explicit UUID matching auth.users.id)."""

    id: UUID = Field(description="UUID matching Supabase auth.users.id")


class ProfileUpdate(BaseModel):
    """Schema for updating a profile."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=100)
    bmr: float | None = Field(default=None, gt=0)
    tdee: float | None = Field(default=None, gt=0)
    target_calories: float | None = Field(default=None, gt=0)
    target_protein_g: float | None = Field(default=None, ge=0)
    target_carbs_g: float | None = Field(default=None, ge=0)
    target_fat_g: float | None = Field(default=None, ge=0)


class ProfileResponse(ProfileBase):
    """Schema for profile response payload."""

    id: UUID
    created_at: datetime
    updated_at: datetime
