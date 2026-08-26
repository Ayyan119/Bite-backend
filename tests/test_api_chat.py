"""Unit tests for Conversational Agent SSE Streaming Chat endpoint."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import clear_claims_cache
from app.main import app
from tests.test_api_auth import create_test_jwt


@pytest.fixture(autouse=True)
def cleanup_cache():
    clear_claims_cache()
    yield
    clear_claims_cache()


async def mock_stream_chatbot_generator(
    user_input: str, user_id: str, thread_id: str, *args, **kwargs
):
    """Mock generator yielding simulated SSE event chunks."""
    yield 'event: status\ndata: {"status": "searching_usda", "message": "Searching USDA..."}\n\n'
    yield 'event: message\ndata: {"content": "Logged 300g Cholay with Naan!"}\n\n'


@pytest.mark.asyncio
async def test_chat_endpoint_unauthorized():
    """Verify 401 response when chat endpoint is called without JWT auth header."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post("/api/v1/chat", json={"message": "I ate 2 eggs"})
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_endpoint_empty_message_validation():
    """Verify 400 response when message prompt is empty or whitespace."""
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/chat", json={"message": "   "}, headers=headers
        )
        assert response.status_code == 400
        assert "error" in response.json()
        assert "cannot be empty" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_chat_endpoint_sse_streaming_success():
    """Verify POST /api/v1/chat returns text/event-stream with instant status and done events."""
    test_user_id = str(uuid4())
    token = create_test_jwt(user_id=test_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "message": "I ate 300g cholay with naan",
        "conversation_id": "test-session-123",
        "client_timezone": "Asia/Karachi",
    }

    with patch(
        "app.api.v1.endpoints.chat.stream_chatbot_response",
        side_effect=mock_stream_chatbot_generator,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/api/v1/chat", json=payload, headers=headers)
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            content = response.text
            assert "event: status" in content
            assert "processing_prompt" in content
            assert "Searching USDA" in content
            assert "Logged 300g Cholay with Naan!" in content
            assert "event: done" in content
            assert "test-session-123" in content


@pytest.mark.asyncio
async def test_chat_sessions_crud():
    """Verify chat session creation, listing, message retrieval, and deletion."""
    test_user_id = str(uuid4())
    token = create_test_jwt(user_id=test_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # 1. Create a session explicitly
        create_resp = await client.post(
            "/api/v1/chat/sessions",
            json={"title": "High Protein Breakfast Plan"},
            headers=headers,
        )
        assert create_resp.status_code == 201
        session_data = create_resp.json()
        assert session_data["title"] == "High Protein Breakfast Plan"
        session_id = session_data["id"]

        # 2. List sessions
        list_resp = await client.get("/api/v1/chat/sessions", headers=headers)
        assert list_resp.status_code == 200
        sessions = list_resp.json()
        assert any(s["id"] == session_id for s in sessions)

        # 3. Get messages for this new session (should be empty initially)
        msg_resp = await client.get(
            f"/api/v1/chat/sessions/{session_id}/messages", headers=headers
        )
        assert msg_resp.status_code == 200
        assert isinstance(msg_resp.json(), list)

        # 4. Delete session
        del_resp = await client.delete(
            f"/api/v1/chat/sessions/{session_id}", headers=headers
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"


async def mock_stream_chatbot_generator_tokens(
    user_input: str, user_id: str, thread_id: str, *args, **kwargs
):
    """Mock generator yielding simulated SSE event chunks with ChatStreamChunk token JSON format."""
    yield 'data: {"event_type": "action_status", "content": "Searching...", "tool_name": "search_usda_food", "is_fallback": false}\n\n'
    yield 'data: {"event_type": "token", "content": "Logged ", "role": "assistant", "tool_name": null, "is_fallback": false}\n\n'
    yield 'data: {"event_type": "token", "content": "300g Cholay!", "role": "assistant", "tool_name": null, "is_fallback": false}\n\n'


@pytest.mark.asyncio
async def test_chat_ai_response_persisted_in_history():
    """Verify that streaming tokens are correctly accumulated and persisted as assistant role in history DB."""
    test_user_id = str(uuid4())
    token = create_test_jwt(user_id=test_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    conv_id = f"test-persisted-conv-{uuid4()}"
    payload = {
        "message": "I ate 300g cholay",
        "conversation_id": conv_id,
        "client_timezone": "UTC",
    }

    with patch(
        "app.api.v1.endpoints.chat.stream_chatbot_response",
        side_effect=mock_stream_chatbot_generator_tokens,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # 1. Stream chat response
            stream_resp = await client.post(
                "/api/v1/chat", json=payload, headers=headers
            )
            assert stream_resp.status_code == 200

            # Consume the full stream content
            _ = stream_resp.text

            # 2. Fetch session messages history
            # Normalize thread UUID to match endpoint behavior
            from uuid import UUID, uuid5
            import uuid

            try:
                session_uuid = str(UUID(conv_id.replace("thread_", "")))
            except ValueError:
                session_uuid = str(uuid5(uuid.NAMESPACE_DNS, conv_id))

            msg_resp = await client.get(
                f"/api/v1/chat/sessions/{session_uuid}/messages", headers=headers
            )
            assert msg_resp.status_code == 200
            messages = msg_resp.json()

            # Verify that both user prompt and assistant reply are saved with correct role and content fields
            assert len(messages) >= 2
            user_msg = next((m for m in messages if m["role"] == "user"), None)
            assistant_msg = next(
                (m for m in messages if m["role"] == "assistant"), None
            )

            assert user_msg is not None
            assert user_msg["content"] == "I ate 300g cholay"
            assert user_msg["role"] == "user"

            assert assistant_msg is not None
            assert assistant_msg["content"] == "Logged 300g Cholay!"
            assert assistant_msg["role"] == "assistant"
