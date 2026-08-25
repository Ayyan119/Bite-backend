"""API request and response DTO schemas for Meal Ingestion & Confirmation."""

from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class MealAnalyzeRequest(BaseModel):
    """JSON Request body for meal image analysis endpoint."""

    image_url: Optional[str] = Field(
        default=None, description="HTTP URL or base64 data URI of meal image."
    )
    user_caption: Optional[str] = Field(
        default=None, description="User optional text description/caption."
    )
    meal_type: Optional[str] = Field(
        default=None,
        description="Optional meal type override: breakfast, lunch, dinner, snack",
    )


class AnalyzedItemResponse(BaseModel):
    """Analyzed food item response with portion-scaled macros and USDA profile."""

    food_name: str
    fdc_id: Optional[int] = None
    portion_amount: float = 1.0
    portion_unit: str = "serving"
    gram_weight: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    is_fallback: bool = False
    raw_usda_nutrients: Dict[str, Any] = Field(default_factory=dict)


class MealAnalysisResponse(BaseModel):
    """Complete response payload for food vision analysis endpoint."""

    detected_items: List[AnalyzedItemResponse]
    meal_type: str = Field(
        default="snack",
        description="Detected or time-inferred meal category: breakfast, lunch, dinner, snack.",
    )
    meal_type_source: str = Field(
        default="time_inferred",
        description="Source of meal category: 'caption_explicit' or 'time_inferred'.",
    )
    total_calories: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    aggregated_nutrients: Dict[str, float] = Field(default_factory=dict)
    confidence_score: float = 1.0
    warnings: List[str] = Field(default_factory=list)


class ConfirmedItemCreate(BaseModel):
    """Item schema for persistent meal confirmation."""

    food_name: str
    fdc_id: Optional[int] = None
    portion_amount: float = 1.0
    portion_unit: str = "serving"
    gram_weight: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    is_fallback: bool = False
    raw_usda_nutrients: Dict[str, Any] = Field(default_factory=dict)


class MealConfirmRequest(BaseModel):
    """Request payload for committing analyzed/edited meal to database."""

    meal_type: Optional[str] = Field(
        default=None,
        description="Meal type: breakfast, lunch, dinner, snack (auto-inferred if omitted)",
    )
    user_caption: Optional[str] = None
    image_url: Optional[str] = None
    items: List[ConfirmedItemCreate]


class MealConfirmResponse(BaseModel):
    """Response payload returned upon successful meal confirmation."""

    meal_id: UUID
    user_id: UUID
    logged_at: str
    meal_type: str
    total_calories: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    item_count: int
