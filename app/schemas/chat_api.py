"""API request and response DTO schemas for Chatbot SSE streaming."""

from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """JSON request payload for /api/v1/chat SSE stream endpoint."""

    message: str = Field(
        description="Natural language user chat prompt, e.g. 'I ate 300g cholay with naan'"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="LangGraph thread_id for conversation state memory. Auto-generated if omitted.",
    )
    client_timezone: Optional[str] = Field(
        default="UTC",
        description="Client local timezone identifier, e.g. 'Asia/Karachi'",
    )
