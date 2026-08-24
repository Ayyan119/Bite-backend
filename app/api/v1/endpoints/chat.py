"""Conversational Agent Real-Time SSE Stream Endpoint Router."""

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.chat_api import ChatRequest
from app.services.langgraph_of_chatbot.agent_graph import stream_chatbot_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    response_class=StreamingResponse,
)
async def chat_stream_endpoint(
    payload: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Connect Flutter chat UI to LangGraph Workflow 2 agent via Server-Sent Events (SSE) streaming.

    Delivers instant header flush (<10ms TTFT) with dual-channel SSE status and message events:
    - event: status -> live progress updates ('Searching USDA...', 'Estimating regional nutrition...')
    - event: message -> streaming Markdown assistant tokens
    - event: done -> execution completion metadata
    """
    if not payload.message or not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat message prompt cannot be empty.",
        )

    thread_id = payload.conversation_id or str(uuid4())
    user_id_str = str(current_user.user_id)

    async def event_generator():
        try:
            # Instant-flush initial SSE status event (<10ms TTFT)
            initial_status = {
                "status": "processing_prompt",
                "message": "Analyzing prompt and loading session memory...",
            }
            yield f"event: status\ndata: {json.dumps(initial_status)}\n\n"

            # Stream real-time LangGraph agent events
            async for sse_chunk in stream_chatbot_response(
                user_input=payload.message.strip(),
                user_id=user_id_str,
                thread_id=thread_id,
            ):
                yield sse_chunk

            # Emit completion event
            done_payload = {
                "conversation_id": thread_id,
                "status": "completed",
            }
            yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
        except Exception as e:
            logger.exception("Error streaming chatbot response SSE events")
            err_payload = {"error": str(e), "status": "failed"}
            yield f"event: error\ndata: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
