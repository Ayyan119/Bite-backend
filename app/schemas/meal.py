from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

MealType = Literal["breakfast", "lunch", "dinner", "snack"]


# -----------------------------------------------------------------------------
# Meal Item Schemas
# -----------------------------------------------------------------------------
class MealItemBase(BaseModel):
    """Base schema for individual meal item."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    food_name: str = Field(min_length=1, max_length=255, description="Food item name")
    fdc_id: int | None = Field(default=None, description="USDA FoodData Central ID")
    portion_amount: float = Field(
        default=1.0, gt=0, description="Serving portion amount"
    )
    portion_unit: str = Field(default="serving", description="Portion unit label")
    gram_weight: float | None = Field(
        default=None, gt=0, description="Gram weight equivalent"
    )
    calories: float = Field(default=0.0, ge=0, description="Calories in kcal")
    protein_g: float = Field(default=0.0, ge=0, description="Protein in grams")
    carbs_g: float = Field(default=0.0, ge=0, description="Carbohydrates in grams")
    fat_g: float = Field(default=0.0, ge=0, description="Fat in grams")
    raw_usda_nutrients: dict[str, Any] = Field(
        default_factory=dict, description="Raw USDA micronutrient JSONB map"
    )


class MealItemCreate(MealItemBase):
    """Schema for creating a meal item."""

    meal_log_id: UUID
    user_id: UUID


class MealItemResponse(MealItemBase):
    """Schema for meal item API response."""

    id: UUID
    meal_log_id: UUID
    user_id: UUID
    created_at: datetime


# -----------------------------------------------------------------------------
# Meal Log Schemas
# -----------------------------------------------------------------------------
class MealLogBase(BaseModel):
    """Base schema for meal log entry."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    meal_type: MealType = Field(
        description="Meal type (breakfast, lunch, dinner, snack)"
    )
    image_url: str | None = Field(default=None, description="Uploaded meal image URL")
    user_caption: str | None = Field(
        default=None, description="User provided meal caption"
    )
    total_calories: float = Field(default=0.0, ge=0, description="Aggregated calories")
    total_protein_g: float = Field(
        default=0.0, ge=0, description="Aggregated protein in grams"
    )
    total_carbs_g: float = Field(
        default=0.0, ge=0, description="Aggregated carbs in grams"
    )
    total_fat_g: float = Field(default=0.0, ge=0, description="Aggregated fat in grams")
    aggregated_nutrients: dict[str, Any] = Field(
        default_factory=dict, description="Aggregated micronutrients JSONB map"
    )


class MealLogCreate(MealLogBase):
    """Schema for creating a meal log entry."""

    user_id: UUID
    logged_at: datetime | None = None
    items: list[MealItemBase] = Field(
        default_factory=list, description="Associated meal items"
    )


class MealLogResponse(MealLogBase):
    """Schema for meal log API response."""

    id: UUID
    user_id: UUID
    logged_at: datetime
    created_at: datetime
    updated_at: datetime
    items: list[MealItemResponse] = Field(default_factory=list)
