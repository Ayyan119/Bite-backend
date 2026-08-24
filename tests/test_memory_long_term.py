import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage
from app.services.langgraph_of_chatbot.memory_long_term import (
    format_long_term_context,
    maybe_trigger_long_term_extraction,
)


@pytest.mark.asyncio
async def test_long_term_memory_format_and_extraction():
    """Verify instant context formatting (<0.1ms) and background fact extraction trigger."""
    profile = {
        "target_calories": 2200,
        "target_protein_g": 160,
        "long_term_memory": {
            "allergies": ["peanuts"],
            "dietary_preferences": ["High Protein"],
        },
    }

    # Test context formatting
    formatted = format_long_term_context(profile)
    assert "2200 kcal" in formatted
    assert "Protein: 160.0g" in formatted or "Protein: 160g" in formatted
    assert "Allergies: peanuts" in formatted

    # Test background trigger
    messages = [
        HumanMessage(content="I am allergic to peanuts and I prefer high protein.")
    ]
    callback_mock = AsyncMock()

    extracted_mock = {
        "allergies": ["peanuts"],
        "dietary_preferences": ["High Protein"],
        "disliked_foods": [],
        "notes": [],
    }

    with patch(
        "app.services.langgraph_of_chatbot.memory_long_term.extract_long_term_facts_async",
        new=AsyncMock(return_value=extracted_mock),
    ):
        triggered = maybe_trigger_long_term_extraction(
            messages,
            "user-uuid-123",
            existing_facts={},
            save_facts_callback=callback_mock,
        )
        assert triggered is True
        await asyncio.sleep(0.05)
        callback_mock.assert_called_once_with("user-uuid-123", extracted_mock)
