from unittest.mock import AsyncMock, MagicMock
import pytest

from app.schemas.ingestion import IngestionState, VisionItem
from app.services.langgraph.usda_node import usda_resolver_node
from app.tools.usda import USDAService, compute_match_score, extract_100g_profile


def test_compute_match_score():
    """Verify match score token overlap calculation."""
    score_high = compute_match_score(
        "Chicken Breast", "Chicken breast, skinless, grilled"
    )
    assert score_high >= 0.6

    score_low = compute_match_score("Dragonfruit", "Chicken breast, skinless, grilled")
    assert score_low < 0.6


def test_extract_100g_profile():
    """Verify per-100g nutrient extraction from USDA raw dict."""
    usda_dict = {
        "fdcId": 171077,
        "description": "Chicken, broilers or fryers, breast, meat only, cooked, grilled",
        "foodNutrients": [
            {
                "nutrientId": 1008,
                "nutrientName": "Energy",
                "value": 165.0,
                "unitName": "KCAL",
            },
            {
                "nutrientId": 1003,
                "nutrientName": "Protein",
                "value": 31.02,
                "unitName": "G",
            },
            {
                "nutrientId": 1005,
                "nutrientName": "Carbohydrate, by difference",
                "value": 0.0,
                "unitName": "G",
            },
            {
                "nutrientId": 1004,
                "nutrientName": "Total lipid (fat)",
                "value": 3.57,
                "unitName": "G",
            },
            {
                "nutrientId": 1087,
                "nutrientName": "Calcium, Ca",
                "value": 15.0,
                "unitName": "MG",
            },
        ],
    }

    profile = extract_100g_profile(usda_dict)
    assert profile["fdc_id"] == 171077
    assert profile["calories_100g"] == 165.0
    assert profile["protein_100g"] == 31.02
    assert profile["carbs_100g"] == 0.0
    assert profile["fat_100g"] == 3.57
    assert "Calcium, Ca (mg)" in profile["micronutrients_100g"]
    assert profile["micronutrients_100g"]["Calcium, Ca (mg)"] == 15.0


@pytest.mark.asyncio
async def test_usda_resolver_node_success():
    """Verify usda_resolver_node maps parallel lookup results into usda_matches."""
    mock_service = MagicMock(spec=USDAService)

    chicken_profile = {
        "fdc_id": 171077,
        "food_description": "Chicken breast, grilled",
        "calories_100g": 165.0,
        "protein_100g": 31.0,
        "carbs_100g": 0.0,
        "fat_100g": 3.6,
        "micronutrients_100g": {},
    }

    async def mock_resolve(food_name, cooking_method=None):
        if "Chicken" in food_name:
            return chicken_profile
        return None

    mock_service.resolve_food_item = AsyncMock(side_effect=mock_resolve)

    state: IngestionState = {
        "image_bytes": b"fake",
        "image_url": None,
        "user_caption": "Chicken and alien fruit",
        "detected_items": [
            {
                "food_name": "Grilled Chicken",
                "portion_estimate": "150g",
                "gram_weight": 150.0,
                "cooking_method": "grilled",
            },
            {
                "food_name": "Alien Fruit",
                "portion_estimate": "100g",
                "gram_weight": 100.0,
                "cooking_method": "raw",
            },
        ],
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

    result = await usda_resolver_node(state, usda_service=mock_service)

    assert "usda_matches" in result
    assert result["usda_matches"]["Grilled Chicken"] == chicken_profile
    assert result["usda_matches"]["Alien Fruit"] is None
