import json
import pytest
from unittest.mock import MagicMock
from app.services.langgraph_of_chatbot.action_status_streamer import (
    get_tool_status_message,
    format_sse_chunk,
    parse_and_stream_astream_events,
)


@pytest.mark.asyncio
async def test_action_status_sse_streaming():
    """Verify tool status mapping, SSE formatting, and event stream parsing."""
    # Test tool status text lookup
    msg = get_tool_status_message("search_usda_food")
    assert "USDA database" in msg

    # Test SSE chunk formatting
    sse_line = format_sse_chunk("action_status", msg, tool_name="search_usda_food")
    assert sse_line.startswith("data: {")
    assert sse_line.endswith("}\n\n")

    # Test astream_events parsing
    async def mock_events():
        yield {"event": "on_tool_start", "name": "log_meal"}
        mock_chunk = MagicMock()
        mock_chunk.content = "Logged 2 eggs!"
        yield {
            "event": "on_chat_model_stream",
            "name": "ChatOpenAI",
            "data": {"chunk": mock_chunk},
        }

    chunks = []
    async for chunk in parse_and_stream_astream_events(mock_events()):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert "action_status" in chunks[0]
    assert "Saving meal items to your log..." in chunks[0]
    assert "Logged 2 eggs!" in chunks[1]
