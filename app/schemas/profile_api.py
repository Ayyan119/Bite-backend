"""API request and response DTO schemas for User Profile & Health Goals."""

from typing import Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class UserProfileUpdate(BaseModel):
    """JSON Request body for updating user health goals and physical traits."""

    display_name: Optional[str] = Field(
        default=None, description="User full display name"
    )
    height_cm: Optional[float] = Field(
        default=None, ge=50, le=250, description="Height in centimeters"
    )
    weight_kg: Optional[float] = Field(
        default=None, ge=20, le=300, description="Weight in kilograms"
    )
    age: Optional[int] = Field(default=None, ge=10, le=120, description="Age in years")
    gender: Optional[str] = Field(
        default=None, description="Gender: male, female, or other"
    )
    activity_level: Optional[str] = Field(
        default="moderate",
        description="Activity level: sedentary, light, moderate, active, extra",
    )
    primary_goal: Optional[str] = Field(
        default="maintenance",
        description="Goal: weight_loss, muscle_gain, maintenance",
    )

    target_calories: Optional[float] = Field(
        default=None, ge=500, le=10000, description="Daily target calories"
    )
    target_protein_g: Optional[float] = Field(
        default=None, ge=0, le=1000, description="Daily protein target in grams"
    )
    target_carbs_g: Optional[float] = Field(
        default=None, ge=0, le=1500, description="Daily carbs target in grams"
    )
    target_fat_g: Optional[float] = Field(
        default=None, ge=0, le=500, description="Daily fat target in grams"
    )
    target_micronutrients: Optional[Dict[str, float]] = Field(
        default_factory=dict, description="Target micronutrients dictionary"
    )


class UserProfileResponse(BaseModel):
    """Response payload for user profile endpoints."""

    id: UUID
    display_name: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    activity_level: str = "moderate"
    primary_goal: str = "maintenance"
    bmr: Optional[float] = None
    tdee: Optional[float] = None
    target_calories: float = 2000.0
    target_protein_g: float = 150.0
    target_carbs_g: float = 200.0
    target_fat_g: float = 65.0
    target_micronutrients: Dict[str, float] = Field(default_factory=dict)
