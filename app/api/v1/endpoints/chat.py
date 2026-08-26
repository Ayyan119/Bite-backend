"""Conversational Agent Real-Time SSE Stream & Chat History Sessions Router."""

import json
import logging
from typing import List, Optional
import uuid
from uuid import UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import ORJSONResponse, StreamingResponse
from psycopg.rows import dict_row

from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.auth import CurrentUser
from app.schemas.chat_api import (
    ChatMessageResponse,
    ChatRequest,
    ChatSessionResponse,
    CreateSessionRequest,
)
from app.services.langgraph_of_chatbot.agent_graph import stream_chatbot_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


def generate_title_from_prompt(prompt: str, max_words: int = 6) -> str:
    """Generates a concise, clean conversation title from the initial user prompt."""
    clean_p = " ".join(prompt.strip().split())
    words = clean_p.split()
    if len(words) <= max_words:
        title = clean_p
    else:
        title = " ".join(words[:max_words]) + "..."
    return title.title()[:60]


async def ensure_session_exists(
    session_id: str, user_id: str, prompt_text: str
) -> None:
    """Ensures parent profile and chat session exist in PostgreSQL, creating on-demand."""
    title = generate_title_from_prompt(prompt_text)
    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                # Ensure profile exists for foreign key constraint
                await cur.execute(
                    """
                    INSERT INTO public.profiles (id, email, display_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    (user_id, "user@example.com", "User"),
                )
                # Ensure session exists
                await cur.execute(
                    """
                    INSERT INTO public.chat_sessions (id, user_id, title)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET updated_at = NOW();
                    """,
                    (session_id, user_id, title),
                )
    except Exception as e:
        logger.warning(f"Could not ensure chat session {session_id} in DB: {e}")


async def save_message_to_db(
    session_id: str, user_id: str, role: str, content: str
) -> None:
    """Persists an individual user or assistant message to public.chat_messages."""
    if not content or not content.strip():
        return
    norm_role = str(role).strip().lower()
    if norm_role in ("model", "bot", "ai", "assistant"):
        norm_role = "assistant"
    elif norm_role in ("user", "human"):
        norm_role = "user"
    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO public.chat_messages (id, session_id, user_id, role, content)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s);
                    """,
                    (session_id, user_id, norm_role, content.strip()),
                )
                await cur.execute(
                    """
                    UPDATE public.chat_sessions
                    SET updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (session_id,),
                )
    except Exception as e:
        logger.warning(f"Could not persist chat message for session {session_id}: {e}")


@router.get(
    "/sessions",
    response_model=List[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    response_class=ORJSONResponse,
)
async def list_chat_sessions(
    current_user: CurrentUser = Depends(get_current_user),
) -> List[ChatSessionResponse]:
    """List all previous chat sessions for the authenticated user ordered by most recently active."""
    user_id_str = str(current_user.user_id)
    query_sql = """
    SELECT s.id, s.user_id, s.title, s.created_at, s.updated_at,
           COUNT(m.id)::int AS message_count
    FROM public.chat_sessions s
    LEFT JOIN public.chat_messages m ON s.id = m.session_id
    WHERE s.user_id = %s
    GROUP BY s.id
    ORDER BY s.updated_at DESC;
    """
    sessions: List[ChatSessionResponse] = []
    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query_sql, (user_id_str,))
                rows = await cur.fetchall()
                for row in rows:
                    sessions.append(
                        ChatSessionResponse(
                            id=row["id"],
                            user_id=row["user_id"],
                            title=row["title"],
                            created_at=str(row["created_at"]),
                            updated_at=str(row["updated_at"]),
                            message_count=row["message_count"] or 0,
                        )
                    )
    except Exception as e:
        logger.warning(f"Error fetching chat sessions for user {user_id_str}: {e}")
    return sessions


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    response_class=ORJSONResponse,
)
async def create_chat_session(
    payload: CreateSessionRequest = CreateSessionRequest(),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatSessionResponse:
    """Explicitly create a new chat conversation session."""
    user_id_str = str(current_user.user_id)
    session_id = uuid4()
    session_title = payload.title or "New Conversation"

    insert_sql = """
    INSERT INTO public.chat_sessions (id, user_id, title)
    VALUES (%s, %s, %s)
    RETURNING id, user_id, title, created_at, updated_at;
    """
    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO public.profiles (id, email, display_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    (user_id_str, current_user.email or "user@example.com", "User"),
                )
                await cur.execute(
                    insert_sql, (str(session_id), user_id_str, session_title)
                )
                row = await cur.fetchone()
                if row:
                    return ChatSessionResponse(
                        id=row["id"],
                        user_id=row["user_id"],
                        title=row["title"],
                        created_at=str(row["created_at"]),
                        updated_at=str(row["updated_at"]),
                        message_count=0,
                    )
    except Exception as e:
        logger.exception(f"Error creating chat session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat session: {str(e)}",
        )

    return ChatSessionResponse(
        id=session_id,
        user_id=current_user.user_id,
        title=session_title,
        created_at="",
        updated_at="",
        message_count=0,
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[ChatMessageResponse],
    status_code=status.HTTP_200_OK,
    response_class=ORJSONResponse,
)
async def get_session_messages(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> List[ChatMessageResponse]:
    """Retrieve full chronological message history for a past conversation session."""
    user_id_str = str(current_user.user_id)
    query_sql = """
    SELECT id, session_id, role, content, created_at
    FROM public.chat_messages
    WHERE session_id = %s AND user_id = %s
    ORDER BY created_at ASC;
    """
    messages: List[ChatMessageResponse] = []
    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query_sql, (session_id, user_id_str))
                rows = await cur.fetchall()
                for row in rows:
                    role_val = str(row.get("role") or "user").strip().lower()
                    if role_val in ("model", "bot", "ai", "assistant"):
                        role_val = "assistant"
                    elif role_val in ("user", "human"):
                        role_val = "user"

                    messages.append(
                        ChatMessageResponse(
                            id=row["id"],
                            session_id=row["session_id"],
                            role=role_val,
                            content=row["content"] or "",
                            created_at=str(row["created_at"]),
                        )
                    )
    except Exception as e:
        logger.warning(f"Error fetching messages for session {session_id}: {e}")
    return messages


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    response_class=ORJSONResponse,
)
async def delete_chat_session(
    session_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Delete a conversation session and all its stored historical messages."""
    user_id_str = str(current_user.user_id)
    delete_sql = """
    DELETE FROM public.chat_sessions
    WHERE id = %s AND user_id = %s;
    """
    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(delete_sql, (session_id, user_id_str))
    except Exception as e:
        logger.exception(f"Error deleting chat session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete chat session: {str(e)}",
        )
    return {"status": "deleted", "session_id": session_id}


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
    Persists user prompts and assistant replies into public.chat_messages for complete chat history.
    """
    if not payload.message or not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat message prompt cannot be empty.",
        )

    # Normalize session_uuid for DB while preserving client_conv_id for client response
    raw_conv_id = payload.conversation_id
    if raw_conv_id and raw_conv_id.strip():
        client_conv_id = raw_conv_id.strip()
        try:
            session_uuid = str(UUID(client_conv_id.replace("thread_", "")))
        except ValueError:
            session_uuid = str(uuid5(uuid.NAMESPACE_DNS, client_conv_id))
    else:
        client_conv_id = str(uuid4())
        session_uuid = client_conv_id

    user_id_str = str(current_user.user_id)
    user_prompt = payload.message.strip()

    # Pre-save session and user message to persistent database
    await ensure_session_exists(session_uuid, user_id_str, user_prompt)
    await save_message_to_db(session_uuid, user_id_str, "user", user_prompt)

    async def event_generator():
        accumulated_assistant_tokens: List[str] = []
        try:
            # Instant-flush initial SSE status event (<10ms TTFT)
            initial_status = {
                "status": "processing_prompt",
                "message": "Thinking...",
            }
            yield f"event: status\ndata: {json.dumps(initial_status)}\n\n"

            # Stream real-time LangGraph agent events
            async for sse_chunk in stream_chatbot_response(
                user_input=user_prompt,
                user_id=user_id_str,
                thread_id=session_uuid,
                client_timezone=payload.client_timezone,
            ):
                # Intercept message token data to accumulate for chat history persistence
                for line in sse_chunk.splitlines():
                    line_str = line.strip()
                    if line_str.startswith("data:"):
                        json_str = line_str[5:].strip()
                        try:
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict):
                                event_type = parsed.get("event_type")
                                # Accumulate token chunks (ignore status events, errors, done events)
                                if event_type == "token" or (
                                    event_type is None
                                    and ("content" in parsed or "token" in parsed)
                                    and not parsed.get("tool_name")
                                    and "status" not in parsed
                                ):
                                    tok = (
                                        parsed.get("token")
                                        or parsed.get("content")
                                        or ""
                                    )
                                    if tok:
                                        accumulated_assistant_tokens.append(str(tok))
                        except Exception:
                            pass

                yield sse_chunk

            # Persist accumulated assistant response to database chat history
            full_reply = "".join(accumulated_assistant_tokens).strip()
            if full_reply:
                await save_message_to_db(
                    session_uuid, user_id_str, "assistant", full_reply
                )

            # Emit completion event
            done_payload = {
                "conversation_id": client_conv_id,
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
