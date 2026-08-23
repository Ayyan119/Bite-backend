import pytest
from pydantic import ValidationError

from app.schemas.ingestion import (
    ExtractedFoodItem,
    FallbackMacroEstimate,
    IngestionState,
    ReconciledItem,
    USDANutrientProfile,
    VisionAnalysisResult,
    VisionItem,
)


def test_vision_item_typeddict():
    """Verify VisionItem TypedDict structure."""
    item: VisionItem = {
        "food_name": "Grilled Chicken",
        "portion_estimate": "150g",
        "gram_weight": 150.0,
        "cooking_method": "grilled",
    }
    assert item["food_name"] == "Grilled Chicken"
    assert item["gram_weight"] == 150.0


def test_usda_nutrient_profile_typeddict():
    """Verify USDANutrientProfile TypedDict structure."""
    profile: USDANutrientProfile = {
        "fdc_id": 123456,
        "food_description": "Chicken breast, grilled",
        "calories_100g": 165.0,
        "protein_100g": 31.0,
        "carbs_100g": 0.0,
        "fat_100g": 3.6,
        "micronutrients_100g": {"Calcium (mg)": 15.0},
    }
    assert profile["fdc_id"] == 123456
    assert profile["protein_100g"] == 31.0


def test_extracted_food_item_pydantic_validation():
    """Verify ExtractedFoodItem Pydantic schema validation."""
    food = ExtractedFoodItem(
        food_name="Steamed Broccoli",
        portion_estimate="1 cup",
        gram_weight=100.0,
        cooking_method="steamed",
    )
    assert food.gram_weight == 100.0

    # Gram weight must be > 0
    with pytest.raises(ValidationError):
        ExtractedFoodItem(
            food_name="Invalid",
            portion_estimate="0g",
            gram_weight=0.0,
        )


def test_vision_analysis_result_pydantic():
    """Verify VisionAnalysisResult Pydantic schema."""
    result = VisionAnalysisResult(
        detected_items=[
            ExtractedFoodItem(
                food_name="Rice",
                portion_estimate="1 cup",
                gram_weight=200.0,
            )
        ],
        confidence_score=0.95,
    )
    assert len(result.detected_items) == 1
    assert result.confidence_score == 0.95


def test_fallback_macro_estimate_pydantic():
    """Verify FallbackMacroEstimate Pydantic schema."""
    estimate = FallbackMacroEstimate(
        food_name="Exotic Fruit",
        calories_100g=50.0,
        protein_100g=1.0,
        carbs_100g=12.0,
        fat_100g=0.2,
        estimated_micronutrients_100g={"Vitamin C": 30.0},
    )
    assert estimate.calories_100g == 50.0
    assert estimate.estimated_micronutrients_100g["Vitamin C"] == 30.0


def test_ingestion_state_structure():
    """Verify complete IngestionState dictionary structure."""
    state: IngestionState = {
        "image_bytes": b"fake",
        "image_url": None,
        "user_caption": "My lunch",
        "detected_items": [],
        "vision_confidence": 0.9,
        "usda_matches": {},
        "reconciled_items": [],
        "total_calories": 0.0,
        "total_protein_g": 0.0,
        "total_carbs_g": 0.0,
        "total_fat_g": 0.0,
        "aggregated_nutrients": {},
        "errors": [],
    }
    assert state["user_caption"] == "My lunch"
