from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Subtask 2.2: LangGraph TypedDict State Definitions
# ---------------------------------------------------------------------------


class VisionItem(TypedDict):
    food_name: str
    portion_estimate: str
    gram_weight: float
    cooking_method: Optional[str]


class USDANutrientProfile(TypedDict):
    fdc_id: Optional[int]
    food_description: str
    calories_100g: float
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    micronutrients_100g: Dict[str, float]


class ReconciledItem(TypedDict):
    food_name: str
    fdc_id: Optional[int]
    portion_amount: float
    portion_unit: str
    gram_weight: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    is_fallback: bool
    raw_usda_nutrients: Dict[str, Any]


class IngestionState(TypedDict):
    # Node 1 Inputs
    image_bytes: Optional[bytes]
    image_url: Optional[str]
    user_caption: Optional[str]

    # Node 2 Outputs
    detected_items: List[VisionItem]
    vision_confidence: float
    detected_meal_type: Optional[str]

    # Node 3 Outputs
    usda_matches: Dict[str, Optional[USDANutrientProfile]]

    # Node 4 / Node 5 Outputs
    reconciled_items: List[ReconciledItem]
    total_calories: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    aggregated_nutrients: Dict[str, float]

    # Diagnostics & Warnings
    errors: List[str]


# ---------------------------------------------------------------------------
# Subtask 2.3: Pydantic Structured Output Models
# ---------------------------------------------------------------------------


class ExtractedFoodItem(BaseModel):
    food_name: str = Field(description="Specific name of the food item detected.")
    portion_estimate: str = Field(
        description="Human readable portion size, e.g., '1 cup', '150g', '2 slices'."
    )
    gram_weight: float = Field(
        description="Estimated total weight of portion in grams.", gt=0
    )
    cooking_method: Optional[str] = Field(
        default="raw",
        description="Preparation method, e.g., 'fried', 'boiled', 'grilled', 'raw'.",
    )


class VisionAnalysisResult(BaseModel):
    is_food: bool = Field(
        default=True,
        description="Set to True if the image contains edible human food or drinks. Set to False if non-food, grass, plants, animals, objects, or empty plate.",
    )
    detected_items: List[ExtractedFoodItem] = Field(
        default_factory=list,
        description="Array of all food items detected in the image. MUST be empty [] if is_food is False.",
    )
    confidence_score: float = Field(
        description="Overall vision extraction confidence from 0.0 to 1.0 (0.0 if is_food is False)."
    )
    caption_match_score: float = Field(
        default=1.0,
        description="Semantic agreement score between visual content and user caption (0.0 to 1.0). Default 1.0 if no caption.",
    )
    caption_mismatch_reason: Optional[str] = Field(
        default=None,
        description="Explanation if caption_match_score is less than 0.6.",
    )
    detected_meal_type: Optional[str] = Field(
        default=None,
        description="Guessed or caption-inferred meal category: 'breakfast', 'lunch', 'dinner', or 'snack'.",
    )


class FallbackMacroEstimate(BaseModel):
    food_name: str = Field(description="Name of the unlisted food item.")
    calories_100g: float = Field(description="Estimated calories per 100 grams.", ge=0)
    protein_100g: float = Field(
        description="Estimated protein in grams per 100g.", ge=0
    )
    carbs_100g: float = Field(
        description="Estimated carbohydrates in grams per 100g.", ge=0
    )
    fat_100g: float = Field(description="Estimated total fat in grams per 100g.", ge=0)
    estimated_micronutrients_100g: Dict[str, float] = Field(
        default_factory=dict, description="Key vitamins and minerals per 100g."
    )
