import asyncio
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.langgraph_of_chatbot.db_tools import get_micronutrient_total
from app.services.langgraph_of_chatbot.memory_short_term import (
    maybe_trigger_background_summarization,
)
from app.services.langgraph_of_chatbot.memory_long_term import (
    format_long_term_context,
    maybe_trigger_long_term_extraction,
)


@pytest.mark.asyncio
async def test_analytics_and_memory_workflow():
    """
    Integration test verifying:
    1. Micronutrient JSONB aggregation queries over multiple nutrients.
    2. Background short-term history summarization (>10 messages).
    3. Long-term fact formatting and background extraction.
    """
    user_id = str(uuid4())

    # 1. Micronutrient JSONB query verification
    mock_conn = MagicMock()
    mock_cur = AsyncMock()
    mock_cur.fetchall.return_value = [
        {
            "aggregated_nutrients": {
                "Calcium, Ca (mg)": 150.0,
                "Vitamin C (mg)": 65.0,
                "Magnesium, Mg (mg)": 80.0,
            }
        }
    ]
    mock_conn.cursor.return_value.__aenter__.return_value = mock_cur

    with patch(
        "app.services.langgraph_of_chatbot.db_tools.get_db_connection"
    ) as mock_get_conn:
        mock_get_conn.return_value.__aenter__.return_value = mock_conn

        micro_res = await get_micronutrient_total.ainvoke(
            {
                "nutrients": ["Calcium", "Vitamin C", "Magnesium"],
                "user_id": user_id,
                "days": 3,
            }
        )

        assert micro_res["status"] == "success"
        assert micro_res["days_aggregated"] == 3
        assert len(micro_res["details"]) == 3

    # 2. Short-term history summarization trigger (>10 messages)
    long_history = [HumanMessage(content=f"Log item {i}") for i in range(12)]
    callback_mock = AsyncMock()

    with patch(
        "app.services.langgraph_of_chatbot.memory_short_term.summarize_history_async",
        new=AsyncMock(return_value="Summary of items"),
    ):
        triggered = maybe_trigger_background_summarization(
            long_history,
            existing_summary="",
            on_summary_complete=callback_mock,
            threshold=10,
        )
        assert triggered is True
        await asyncio.sleep(0.05)
        callback_mock.assert_called_once_with("Summary of items")

    # 3. Long-term memory formatting & extraction trigger
    profile = {
        "target_calories": 2000,
        "long_term_memory": {
            "allergies": ["shellfish"],
            "dietary_preferences": ["halal"],
        },
    }
    formatted = format_long_term_context(profile)
    assert "2000 kcal" in formatted
    assert "Allergies: shellfish" in formatted

    fact_callback = AsyncMock()
    with patch(
        "app.services.langgraph_of_chatbot.memory_long_term.extract_long_term_facts_async",
        new=AsyncMock(return_value={"allergies": ["shellfish"]}),
    ):
        lt_triggered = maybe_trigger_long_term_extraction(
            long_history, user_id=user_id, save_facts_callback=fact_callback
        )
        assert lt_triggered is True
        await asyncio.sleep(0.05)
        fact_callback.assert_called_once_with(user_id, {"allergies": ["shellfish"]})
