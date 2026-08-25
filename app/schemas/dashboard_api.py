"""API request and response DTO schemas for Daily Dashboard Analytics."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MacroProgress(BaseModel):
    """Macro budget breakdown containing target, consumed, and remaining values."""

    target: Optional[float] = Field(
        default=None, description="Optional daily target goal in grams or kcal."
    )
    consumed: float = Field(default=0.0, description="Total consumed value today.")
    remaining: Optional[float] = Field(
        default=None, description="Optional remaining budget value today."
    )


class DailyDashboardResponse(BaseModel):
    """Response DTO payload for GET /api/v1/dashboard/daily endpoint."""

    date: str = Field(description="Target date in YYYY-MM-DD format.")
    target_calories: Optional[float] = None
    consumed_calories: float = 0.0
    remaining_calories: Optional[float] = None
    protein: MacroProgress
    carbs: MacroProgress
    fat: MacroProgress
    meals: List[Dict[str, Any]] = Field(
        default_factory=list, description="Chronological list of meal log cards."
    )
    top_micronutrients: Dict[str, float] = Field(
        default_factory=dict, description="Aggregated micronutrients for target date."
    )


class DailyHistoryItem(BaseModel):
    """Analytics item for a single historical day."""

    date: str = Field(description="Date in YYYY-MM-DD format.")
    meal_count: int = Field(
        default=0, description="Total number of meals logged on this date."
    )
    total_calories: float = Field(
        default=0.0, description="Total calories consumed on this date."
    )
    target_calories: Optional[float] = Field(
        default=None, description="Calorie target on this date."
    )
    total_protein_g: float = Field(default=0.0)
    target_protein_g: Optional[float] = None
    total_carbs_g: float = Field(default=0.0)
    target_carbs_g: Optional[float] = None
    total_fat_g: float = Field(default=0.0)
    target_fat_g: Optional[float] = None
    goal_status: str = Field(
        default="completed", description="'met', 'exceeded', or 'under'"
    )


class HistoricalAnalyticsResponse(BaseModel):
    """Response DTO payload for GET /api/v1/dashboard/history endpoint."""

    user_id: str
    total_days_logged: int
    history: List[DailyHistoryItem]
