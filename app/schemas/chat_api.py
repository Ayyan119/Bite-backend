from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ChatSessionResponse(BaseModel):
    """Response model for a chat conversation session."""

    id: UUID
    user_id: UUID
    title: str = Field(description="Display title of the chat conversation session.")
    created_at: str
    updated_at: str
    message_count: int = Field(default=0, description="Total messages in this session.")


class ChatMessageResponse(BaseModel):
    """Response model for an individual message within a chat session."""

    id: UUID
    session_id: UUID
    role: str = Field(
        description="Role of message sender: 'user', 'assistant', or 'system'."
    )
    content: str = Field(description="Text content of the message.")
    created_at: str


class CreateSessionRequest(BaseModel):
    """Request payload for explicitly creating a new chat session."""

    title: Optional[str] = Field(
        default="New Conversation",
        description="Optional custom title for the chat session.",
    )


class ChatRequest(BaseModel):
    """JSON request payload for /api/v1/chat SSE stream endpoint."""

    message: str = Field(
        description="Natural language user chat prompt, e.g. 'I ate 300g cholay with naan'"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Chat session ID / thread_id for persistent conversation state. Auto-created if omitted.",
    )
    client_timezone: Optional[str] = Field(
        default="UTC",
        description="Client local timezone identifier, e.g. 'Asia/Karachi'",
    )
