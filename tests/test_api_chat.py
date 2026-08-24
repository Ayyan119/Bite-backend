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


async def mock_stream_chatbot_generator(user_input: str, user_id: str, thread_id: str):
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
