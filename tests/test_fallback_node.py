from unittest.mock import AsyncMock, MagicMock
import pytest

from app.schemas.ingestion import FallbackMacroEstimate, IngestionState
from app.services.langgraph.fallback_node import fallback_node


@pytest.mark.asyncio
async def test_fallback_node_unmatched_item():
    """Verify fallback_node estimates macros for unmatched items and logs warnings."""
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()

    mock_estimate = FallbackMacroEstimate(
        food_name="Dragonfruit Bowl",
        calories_100g=60.0,
        protein_100g=1.0,
        carbs_100g=14.0,
        fat_100g=0.5,
        estimated_micronutrients_100g={"Vitamin C (mg)": 20.0},
    )

    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_estimate)
    mock_llm.with_structured_output.return_value = mock_structured_llm

    state: IngestionState = {
        "image_bytes": b"fake",
        "image_url": None,
        "user_caption": "Dragonfruit bowl",
        "detected_items": [
            {
                "food_name": "Dragonfruit Bowl",
                "portion_estimate": "200g",
                "gram_weight": 200.0,
                "cooking_method": "raw",
            }
        ],
        "vision_confidence": 0.9,
        "usda_matches": {"Dragonfruit Bowl": None},
        "reconciled_items": [],
        "total_calories": 0.0,
        "total_protein_g": 0.0,
        "total_carbs_g": 0.0,
        "total_fat_g": 0.0,
        "aggregated_nutrients": {},
        "errors": [],
    }

    result = await fallback_node(state, llm=mock_llm)

    match_profile = result["usda_matches"]["Dragonfruit Bowl"]
    assert match_profile is not None
    assert match_profile["fdc_id"] is None
    assert match_profile["calories_100g"] == 60.0
    assert match_profile["protein_100g"] == 1.0
    assert len(result["errors"]) == 1
    assert "USDA lookup failed" in result["errors"][0]


@pytest.mark.asyncio
async def test_fallback_node_skips_matched_items():
    """Verify fallback_node does not invoke LLM when USDA match exists."""
    mock_llm = MagicMock()

    existing_profile = {
        "fdc_id": 123456,
        "food_description": "Grilled Chicken",
        "calories_100g": 165.0,
        "protein_100g": 31.0,
        "carbs_100g": 0.0,
        "fat_100g": 3.6,
        "micronutrients_100g": {},
    }

    state: IngestionState = {
        "image_bytes": b"fake",
        "image_url": None,
        "user_caption": "Grilled Chicken",
        "detected_items": [
            {
                "food_name": "Grilled Chicken",
                "portion_estimate": "150g",
                "gram_weight": 150.0,
                "cooking_method": "grilled",
            }
        ],
        "vision_confidence": 0.95,
        "usda_matches": {"Grilled Chicken": existing_profile},
        "reconciled_items": [],
        "total_calories": 0.0,
        "total_protein_g": 0.0,
        "total_carbs_g": 0.0,
        "total_fat_g": 0.0,
        "aggregated_nutrients": {},
        "errors": [],
    }

    result = await fallback_node(state, llm=mock_llm)

    assert result["usda_matches"]["Grilled Chicken"] == existing_profile
    assert len(result["errors"]) == 0
    mock_llm.with_structured_output.assert_not_called()
