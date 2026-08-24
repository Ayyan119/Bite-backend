import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.services.langgraph_of_chatbot.memory_short_term import (
    get_trimmed_messages,
    count_user_messages,
    maybe_trigger_background_summarization,
)


@pytest.mark.asyncio
async def test_short_term_memory_trimming_and_trigger():
    """Verify message trimming and non-blocking background summarization task trigger."""
    system_msg = SystemMessage(content="System prompt")
    messages = [system_msg] + [HumanMessage(content=f"Meal {i}") for i in range(12)]

    # Test count & trimming
    assert count_user_messages(messages) == 12
    trimmed = get_trimmed_messages(messages, max_messages=4)
    assert len(trimmed) == 5  # SystemMessage + 4 latest HumanMessages
    assert trimmed[0] == system_msg
    assert trimmed[-1].content == "Meal 11"

    # Test background trigger
    callback_mock = AsyncMock()
    with patch(
        "app.services.langgraph_of_chatbot.memory_short_term.summarize_history_async",
        new=AsyncMock(return_value="Summary of older meals"),
    ):
        triggered = maybe_trigger_background_summarization(
            messages,
            existing_summary="",
            on_summary_complete=callback_mock,
            threshold=10,
            window_size=4,
        )
        assert triggered is True
        # Allow event loop to process background task
        await asyncio.sleep(0.05)
        callback_mock.assert_called_once_with("Summary of older meals")
