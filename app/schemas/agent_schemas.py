from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class BaseAgentSchema(BaseModel):
    """Base Pydantic model enforcing strict extra='forbid' validation."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ActionStatusEvent(BaseAgentSchema):
    """Schema for SSE Action Status live progress events sent to Flutter UI."""

    event_type: Literal["action_status"] = Field(
        default="action_status", description="SSE event type identifier"
    )
    tool_name: str = Field(description="Name of the tool being executed")
    status_message: str = Field(description="Human readable progress badge text")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of the event"
    )


class ChatStreamChunk(BaseAgentSchema):
    """Schema for SSE chat token/message chunk streaming to Flutter UI."""

    event_type: Literal["token", "action_status", "error", "done"] = Field(
        description="Type of SSE payload chunk"
    )
    content: str = Field(description="Payload content or status message")
    role: Optional[str] = Field(
        default="assistant", description="Role of message sender, defaults to assistant"
    )
    tool_name: Optional[str] = Field(
        default=None, description="Associated tool name if action status"
    )
    is_fallback: Optional[bool] = Field(
        default=False, description="Flag indicating if LLM fallback estimation was used"
    )


class MealItemInput(BaseAgentSchema):
    """Strict schema for meal item logging tool input."""

    food_name: str = Field(description="Name of the food item")
    fdc_id: Optional[int] = Field(
        default=None, description="USDA FoodData Central ID if available"
    )
    portion_amount: float = Field(default=1.0, gt=0, description="Portion quantity")
    portion_unit: str = Field(default="serving", description="Portion unit name")
    gram_weight: Optional[float] = Field(
        default=None, gt=0, description="Estimated gram weight"
    )
    calories: float = Field(default=0.0, ge=0, description="Estimated or USDA calories")
    protein_g: float = Field(default=0.0, ge=0, description="Protein in grams")
    carbs_g: float = Field(default=0.0, ge=0, description="Carbohydrates in grams")
    fat_g: float = Field(default=0.0, ge=0, description="Fat in grams")
    raw_usda_nutrients: Dict[str, float] = Field(
        default_factory=dict, description="Micronutrient mapping"
    )
    is_fallback: bool = Field(
        default=False, description="True if estimated via LLM fallback"
    )
