import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.services.langgraph_of_chatbot.checkpointer import (
    get_checkpointer,
    prefetch_memory_parallel,
)


@pytest.mark.asyncio
async def test_get_checkpointer():
    """Verify that get_checkpointer returns an AsyncPostgresSaver instance."""
    mock_pool = MagicMock()
    with patch(
        "app.services.langgraph_of_chatbot.checkpointer.init_db_pool",
        return_value=mock_pool,
    ), patch(
        "app.services.langgraph_of_chatbot.checkpointer._checkpointer_instance", None
    ):
        checkpointer = await get_checkpointer()
        assert isinstance(checkpointer, AsyncPostgresSaver)


@pytest.mark.asyncio
async def test_prefetch_memory_parallel_success():
    """Verify that prefetch_memory_parallel executes both coroutines in parallel."""
    mock_checkpointer = AsyncMock(spec=AsyncPostgresSaver)
    mock_checkpoint_tuple = MagicMock()
    mock_checkpointer.aget_tuple.return_value = mock_checkpoint_tuple

    async def mock_fetch_long_term():
        await asyncio.sleep(0.01)
        return {"diet": "keto", "allergies": ["peanuts"]}

    config = {"configurable": {"thread_id": "test-user-123"}}
    short_term, long_term = await prefetch_memory_parallel(
        mock_checkpointer, config, mock_fetch_long_term()
    )

    assert short_term == mock_checkpoint_tuple
    assert long_term == {"diet": "keto", "allergies": ["peanuts"]}
    mock_checkpointer.aget_tuple.assert_called_once_with(config)


@pytest.mark.asyncio
async def test_prefetch_memory_parallel_error_handling():
    """Verify error isolation in prefetch_memory_parallel when a coroutine fails."""
    mock_checkpointer = AsyncMock(spec=AsyncPostgresSaver)
    mock_checkpointer.aget_tuple.side_effect = RuntimeError("DB connection error")

    async def mock_fetch_long_term():
        return {"preferences": "high protein"}

    config = {"configurable": {"thread_id": "test-user-456"}}
    short_term, long_term = await prefetch_memory_parallel(
        mock_checkpointer, config, mock_fetch_long_term()
    )

    assert short_term is None
    assert long_term == {"preferences": "high protein"}
