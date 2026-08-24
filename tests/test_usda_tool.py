import pytest
from unittest.mock import AsyncMock, patch
from app.services.langgraph_of_chatbot.usda_tool import search_usda_food, usda_cache


@pytest.mark.asyncio
async def test_search_usda_food_concurrent_and_cache():
    """Verify concurrent USDA search and TTLCache caching mechanism."""
    usda_cache.clear()

    mock_profile = {
        "fdc_id": 171077,
        "food_description": "Egg, whole, raw",
        "calories_100g": 143.0,
        "protein_100g": 12.6,
        "carbs_100g": 0.7,
        "fat_100g": 9.5,
        "micronutrients_100g": {},
    }

    async def mock_resolve(food_name, cooking_method=None):
        if "egg" in food_name.lower():
            return mock_profile
        return None

    with patch(
        "app.services.langgraph_of_chatbot.usda_tool.USDAService.resolve_food_item",
        side_effect=mock_resolve,
    ):
        results = await search_usda_food.ainvoke({"queries": ["egg", "cholay"]})
        assert len(results) == 2

        egg_res = next(r for r in results if r["query"] == "egg")
        assert egg_res["found"] is True
        assert egg_res["profile"]["calories_100g"] == 143.0

        cholay_res = next(r for r in results if r["query"] == "cholay")
        assert cholay_res["found"] is False
        assert cholay_res["profile"] is None

        # Verify caching
        assert "egg:" in usda_cache or "egg:None" in usda_cache
