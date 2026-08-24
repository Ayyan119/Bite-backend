"""API request and response DTO schemas for Daily Dashboard Analytics."""

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class MacroProgress(BaseModel):
    """Macro budget breakdown containing target, consumed, and remaining values."""

    target: float = Field(description="Daily target goal in grams or kcal.")
    consumed: float = Field(description="Total consumed value today.")
    remaining: float = Field(description="Remaining budget value today.")


class DailyDashboardResponse(BaseModel):
    """Response DTO payload for GET /api/v1/dashboard/daily endpoint."""

    date: str = Field(description="Target date in YYYY-MM-DD format.")
    target_calories: float
    consumed_calories: float
    remaining_calories: float
    protein: MacroProgress
    carbs: MacroProgress
    fat: MacroProgress
    meals: List[Dict[str, Any]] = Field(
        default_factory=list, description="Chronological list of meal log cards."
    )
    top_micronutrients: Dict[str, float] = Field(
        default_factory=dict, description="Aggregated micronutrients for target date."
    )
