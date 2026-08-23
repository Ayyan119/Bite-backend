from unittest.mock import AsyncMock, MagicMock
import pytest

from app.schemas.ingestion import (
    ExtractedFoodItem,
    IngestionState,
    VisionAnalysisResult,
)
from app.services.langgraph.vision_node import vision_extraction_node


@pytest.mark.asyncio
async def test_vision_extraction_node_success():
    """Verify vision_extraction_node parses multimodal output correctly."""
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()

    mock_result = VisionAnalysisResult(
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

    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
    mock_llm.with_structured_output.return_value = mock_structured_llm

    state: IngestionState = {
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

    result = await vision_extraction_node(state, llm=mock_llm)

    assert len(result["detected_items"]) == 2
    assert result["detected_items"][0]["food_name"] == "Grilled Chicken Breast"
    assert result["detected_items"][1]["cooking_method"] == "steamed"
    assert result["vision_confidence"] == 0.95
    assert len(result.get("errors", [])) == 0


@pytest.mark.asyncio
async def test_vision_extraction_node_invalid_image():
    """Verify vision_extraction_node handles missing image input gracefully."""
    state: IngestionState = {
        "image_bytes": None,
        "image_url": None,
        "user_caption": "No image",
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

    result = await vision_extraction_node(state)
    assert result["detected_items"] == []
    assert result["vision_confidence"] == 0.0
    assert len(result["errors"]) == 1
    assert "Either image_bytes or image_url must be provided" in result["errors"][0]


@pytest.mark.asyncio
async def test_vision_extraction_node_llm_exception():
    """Verify vision_extraction_node catches LLM execution errors without crashing."""
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(
        side_effect=RuntimeError("API quota exceeded")
    )
    mock_llm.with_structured_output.return_value = mock_structured_llm

    state: IngestionState = {
        "image_bytes": b"fake-image-bytes",
        "image_url": None,
        "user_caption": "Lunch",
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

    result = await vision_extraction_node(state, llm=mock_llm)
    assert result["detected_items"] == []
    assert len(result["errors"]) == 1
    assert "API quota exceeded" in result["errors"][0]
