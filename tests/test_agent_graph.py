import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from app.services.langgraph_of_chatbot.agent_graph import (
    build_chatbot_graph,
    get_compiled_chatbot_graph,
    CHATBOT_TOOLS,
)


@pytest.mark.asyncio
async def test_agent_graph_assembly_and_compilation():
    """Verify state machine graph assembly, 6 tools binding, and checkpointer compilation."""
    assert len(CHATBOT_TOOLS) == 6

    tool_names = [t.name for t in CHATBOT_TOOLS]
    assert "search_usda_food" in tool_names
    assert "log_meal" in tool_names
    assert "get_daily_summary" in tool_names
    assert "get_micronutrient_total" in tool_names
    assert "update_meal_item" in tool_names
    assert "delete_meal_log" in tool_names

    # Test graph build
    builder = build_chatbot_graph()
    assert isinstance(builder, StateGraph)

    # Test compiled graph
    cp = MemorySaver()
    compiled = await get_compiled_chatbot_graph(checkpointer=cp)
    assert compiled is not None
