import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import app.services.langgraph.fallback_node
import app.services.langgraph.vision_node
from app.schemas.ingestion import (
    ExtractedFoodItem,
    FallbackMacroEstimate,
    IngestionState,
    VisionAnalysisResult,
)
from app.services.langgraph.graph import ingestion_graph


@pytest.mark.asyncio
async def test_ingestion_graph_success():
    """Verify end-to-end graph execution when all items are matched via USDA."""
    v_mod = sys.modules["app.services.langgraph.vision_node"]

    mock_vision_result = VisionAnalysisResult(
        detected_items=[
            ExtractedFoodItem(
                food_name="Grilled Chicken Breast",
                portion_estimate="150g",
                gram_weight=150.0,
                cooking_method="grilled",
            ),
            ExtractedFoodItem(
                food_name="Steamed Broccoli",
                portion_estimate="100g",
                gram_weight=100.0,
                cooking_method="steamed",
            ),
        ],
        confidence_score=0.95,
    )

    chicken_profile = {
        "fdc_id": 171077,
        "food_description": "Grilled Chicken Breast",
        "calories_100g": 165.0,
        "protein_100g": 31.0,
        "carbs_100g": 0.0,
        "fat_100g": 3.6,
        "micronutrients_100g": {"Calcium (mg)": 15.0},
    }

    broccoli_profile = {
        "fdc_id": 169967,
        "food_description": "Steamed Broccoli",
        "calories_100g": 34.0,
        "protein_100g": 2.8,
        "carbs_100g": 7.0,
        "fat_100g": 0.4,
        "micronutrients_100g": {"Vitamin C (mg)": 89.0},
    }

    async def mock_resolve_food_item(food_name, cooking_method=None):
        if "Chicken" in food_name:
            return chicken_profile
        elif "Broccoli" in food_name:
            return broccoli_profile
        return None

    initial_state: IngestionState = {
        "image_bytes": b"fake-image-bytes",
        "image_url": None,
        "user_caption": "Grilled chicken breast with broccoli",
        "detected_items": [],
        "vision_confidence": 0.0,
        "usda_matches": {},
        "reconciled_items": [],
        "total_calories": 0.0,
        "total_protein_g": 0.0,
        "total_carbs_g": 0.0,
        "total_fat_g": 0.0,
        "aggregated_nutrients": {},
        "errors": [],
    }

    with patch.object(v_mod, "ChatOpenAI") as mock_v_cls, patch(
        "app.tools.usda.USDAService.resolve_food_item",
        side_effect=mock_resolve_food_item,
    ):
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_vision_result)
        mock_llm.with_structured_output.return_value = mock_structured
        mock_v_cls.return_value = mock_llm

        final_state = await ingestion_graph.ainvoke(initial_state)

    reconciled = final_state["reconciled_items"]
    assert len(reconciled) == 2

    # Chicken: 1.5 * 165 = 247.5 kcal
    assert reconciled[0]["calories"] == 247.5
    assert reconciled[0]["is_fallback"] is False

    # Total calories: 247.5 + 34 = 281.5 kcal
    assert final_state["total_calories"] == 281.5
    assert "Calcium (mg)" in final_state["aggregated_nutrients"]
    assert "Vitamin C (mg)" in final_state["aggregated_nutrients"]


@pytest.mark.asyncio
async def test_ingestion_graph_fallback():
    """Verify graph execution with fallback estimation when USDA lookup fails."""
    v_mod = sys.modules["app.services.langgraph.vision_node"]
    f_mod = sys.modules["app.services.langgraph.fallback_node"]

    mock_vision_result = VisionAnalysisResult(
        detected_items=[
            ExtractedFoodItem(
                food_name="Dragonfruit Smoothie Bowl",
                portion_estimate="200g",
                gram_weight=200.0,
                cooking_method="raw",
            )
        ],
        confidence_score=0.90,
    )

    mock_fallback_estimate = FallbackMacroEstimate(
        food_name="Dragonfruit Smoothie Bowl",
        calories_100g=60.0,
        protein_100g=1.0,
        carbs_100g=14.0,
        fat_100g=0.5,
        estimated_micronutrients_100g={"Vitamin C (mg)": 20.0},
    )

    initial_state: IngestionState = {
        "image_bytes": b"fake-image-bytes",
        "image_url": None,
        "user_caption": "Dragonfruit smoothie bowl",
        "detected_items": [],
        "vision_confidence": 0.0,
        "usda_matches": {},
        "reconciled_items": [],
        "total_calories": 0.0,
        "total_protein_g": 0.0,
        "total_carbs_g": 0.0,
        "total_fat_g": 0.0,
        "aggregated_nutrients": {},
        "errors": [],
    }

    with patch.object(v_mod, "ChatOpenAI") as mock_v_cls, patch.object(
        f_mod, "ChatOpenAI"
    ) as mock_f_cls, patch(
        "app.tools.usda.USDAService.resolve_food_item", return_value=None
    ):
        mock_v_llm = MagicMock()
        mock_v_struct = MagicMock()
        mock_v_struct.ainvoke = AsyncMock(return_value=mock_vision_result)
        mock_v_llm.with_structured_output.return_value = mock_v_struct
        mock_v_cls.return_value = mock_v_llm

        mock_f_llm = MagicMock()
        mock_f_struct = MagicMock()
        mock_f_struct.ainvoke = AsyncMock(return_value=mock_fallback_estimate)
        mock_f_llm.with_structured_output.return_value = mock_f_struct
        mock_f_cls.return_value = mock_f_llm

        final_state = await ingestion_graph.ainvoke(initial_state)

    reconciled = final_state["reconciled_items"]
    assert len(reconciled) == 1
    assert reconciled[0]["is_fallback"] is True

    # Total calories: 200g * 60 / 100 = 120.0 kcal
    assert final_state["total_calories"] == 120.0
    assert len(final_state["errors"]) > 0
    assert any("fallback" in err.lower() for err in final_state["errors"])
