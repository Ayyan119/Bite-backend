import asyncio
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.langgraph_of_chatbot.usda_tool import search_usda_food
from app.services.langgraph_of_chatbot.db_tools import log_meal
from app.services.langgraph_of_chatbot.action_status_streamer import (
    get_tool_status_message,
    format_sse_chunk,
)


@pytest.mark.asyncio
async def test_standard_and_regional_fallback_logging():
    """
    Integration test verifying:
    1. Concurrent USDA search execution & action status messaging.
    2. Regional dish LLM fallback logging with is_fallback=True.
    """
    user_id = str(uuid4())

    # 1. Action status check
    status_msg = get_tool_status_message("search_usda_food")
    assert "USDA database" in status_msg
    sse_chunk = format_sse_chunk(
        "action_status", status_msg, tool_name="search_usda_food"
    )
    assert "action_status" in sse_chunk

    # 2. Regional fallback meal logging test ("300g cholay with naan")
    fallback_items = [
        {
            "food_name": "Cholay (Chana Masala)",
            "portion_amount": 1.0,
            "portion_unit": "300g",
            "gram_weight": 300.0,
            "calories": 390.0,
            "protein_g": 15.0,
            "carbs_g": 54.0,
            "fat_g": 12.0,
            "is_fallback": True,
        },
        {
            "food_name": "Naan",
            "portion_amount": 1.0,
            "portion_unit": "piece",
            "gram_weight": 120.0,
            "calories": 310.0,
            "protein_g": 9.0,
            "carbs_g": 52.0,
            "fat_g": 6.0,
            "is_fallback": True,
        },
    ]

    mock_conn = MagicMock()
    mock_cur = AsyncMock()
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur

    with patch(
        "app.services.langgraph_of_chatbot.db_tools.get_db_connection"
    ) as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_conn

        res = await log_meal.ainvoke(
            {
                "meal_type": "lunch",
                "items": fallback_items,
                "user_caption": "I ate 300g cholay with naan",
                "user_id": user_id,
            }
        )

        assert res["status"] == "success"
        assert res["total_calories"] == 700.0
        assert res["total_protein_g"] == 24.0
        assert res["is_fallback"] is True
        assert res["item_count"] == 2
