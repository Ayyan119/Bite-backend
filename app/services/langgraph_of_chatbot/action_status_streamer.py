import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional
from app.schemas.agent_schemas import ActionStatusEvent, ChatStreamChunk

logger = logging.getLogger(__name__)

# Human-readable status badges for client UI live progress
TOOL_STATUS_MESSAGES: Dict[str, str] = {
    "get_current_time": "Checking real-time date, time & timezone...",
    "search_usda_food": "Searching USDA database & calculating regional estimates...",
    "log_meal": "Saving meal items to your log...",
    "get_daily_summary": "Retrieving your daily nutrition summary...",
    "get_micronutrient_total": "Calculating micronutrient totals in parallel...",
    "update_meal_item": "Updating meal item & recalculating totals...",
    "delete_meal_log": "Deleting meal log entry...",
    "get_user_profile": "Reading your profile and health metrics...",
}


def get_tool_status_message(tool_name: str) -> str:
    """Returns human readable status message for a tool."""
    return TOOL_STATUS_MESSAGES.get(tool_name, f"Executing {tool_name}...")


def format_sse_chunk(
    event_type: str,
    content: str,
    tool_name: Optional[str] = None,
    is_fallback: bool = False,
) -> str:
    """Formats payload into a Server-Sent Events (SSE) data string."""
    chunk = ChatStreamChunk(
        event_type=event_type,  # type: ignore
        content=content,
        tool_name=tool_name,
        is_fallback=is_fallback,
    )
    return f"data: {chunk.model_dump_json()}\n\n"


async def parse_and_stream_astream_events(
    astream_events_gen: AsyncGenerator[Dict[str, Any], None],
) -> AsyncGenerator[str, None]:
    """
    Parses astream_events v2 events from compiled LangGraph state machine
    and yields SSE formatted string chunks ('data: {...}\n\n') for client streaming.
    """
    async for event in astream_events_gen:
        kind = event.get("event")
        name = event.get("name", "")

        # Emit action status live progress badge on tool execution start
        if kind == "on_tool_start":
            status_msg = get_tool_status_message(name)
            yield format_sse_chunk("action_status", status_msg, tool_name=name)

        # Stream text token chunk from LLM response
        elif kind == "on_chat_model_stream":
            chunk_data = event.get("data", {}).get("chunk")
            if chunk_data and hasattr(chunk_data, "content") and chunk_data.content:
                text_content = str(chunk_data.content)
                if text_content:
                    yield format_sse_chunk("token", text_content)
