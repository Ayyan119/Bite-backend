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


def test_get_current_time_tool():
    """Verify get_current_time returns valid real-time fields and timezone."""
    from app.services.langgraph_of_chatbot.db_tools import get_current_time

    res = get_current_time.invoke({})
    assert res["status"] == "success"
    assert "current_time_12h" in res
    assert "current_time_24h" in res
    assert "current_date" in res
    assert "day_of_week" in res
    assert "timezone" in res
    assert "iso_timestamp" in res
    assert "current_meal_period" in res


@pytest.mark.asyncio
async def test_update_user_profile_tool():
    """Verify update_user_profile tool updates body stats, BMR, TDEE, and targets."""
    from app.services.langgraph_of_chatbot.db_tools import update_user_profile

    user_id = str(uuid4())
    mock_conn = MagicMock()
    mock_cur = AsyncMock()
    mock_cur.fetchone.return_value = {
        "display_name": "Test User",
        "height_cm": None,
        "weight_kg": None,
        "age": None,
        "gender": None,
        "activity_level": None,
        "primary_goal": None,
        "target_calories": None,
    }
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur

    with patch(
        "app.services.langgraph_of_chatbot.db_tools.get_db_connection"
    ) as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_conn

        res = await update_user_profile.ainvoke(
            {
                "user_id": user_id,
                "weight_kg": 75.0,
                "height_cm": 178.0,
                "age": 28,
                "gender": "male",
                "primary_goal": "muscle_gain",
            }
        )

        assert res["status"] == "success"
        assert res["weight_kg"] == 75.0
        assert res["height_cm"] == 178.0
        assert res["bmr"] is not None
        assert res["tdee"] is not None
        assert res["target_calories"] is not None
        assert res["target_calories"] > 2000.0
