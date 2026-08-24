import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.langgraph_of_chatbot.db_tools import (
    log_meal,
    get_micronutrient_total,
    resolve_user_id,
)


@pytest.mark.asyncio
async def test_db_tools_parallel_micronutrients_and_user_resolution():
    """Verify parallel multi-nutrient lookups and session user_id binding."""
    user_id = str(uuid4())

    # Test user_id resolution from config
    resolved = resolve_user_id(None, {"configurable": {"user_id": user_id}})
    assert resolved == user_id

    # Test parallel multi-nutrient query
    nutrients = ["Magnesium", "Iron", "Calcium", "Vitamin C"]

    mock_conn = MagicMock()
    mock_cur = AsyncMock()
    mock_cur.fetchall.return_value = [
        {
            "aggregated_nutrients": {
                "Magnesium (mg)": 50.0,
                "Iron (mg)": 4.5,
                "Calcium (mg)": 120.0,
                "Vitamin C (mg)": 30.0,
            }
        }
    ]
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur

    with patch(
        "app.services.langgraph_of_chatbot.db_tools.get_db_connection"
    ) as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_conn

        res = await get_micronutrient_total.ainvoke(
            {"nutrients": nutrients, "user_id": user_id, "days": 3}
        )

        assert res["status"] == "success"
        assert res["days_aggregated"] == 3
        assert len(res["details"]) == 4
        assert res["micronutrient_totals"]["Magnesium (mg)"] == 50.0
        assert res["micronutrient_totals"]["Iron (mg)"] == 4.5
