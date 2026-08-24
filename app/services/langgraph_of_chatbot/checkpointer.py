import asyncio
import logging
from typing import Any, Coroutine, Tuple
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.db.connection import init_db_pool

logger = logging.getLogger(__name__)

_checkpointer_instance: AsyncPostgresSaver | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """
    Get or initialize the global AsyncPostgresSaver checkpointer instance.
    Uses the global PostgreSQL AsyncConnectionPool.
    """
    global _checkpointer_instance
    if _checkpointer_instance is None:
        db_pool = await init_db_pool()
        _checkpointer_instance = AsyncPostgresSaver(db_pool)
    return _checkpointer_instance


async def setup_checkpointer() -> AsyncPostgresSaver:
    """
    Initialize checkpointer and run setup migrations for LangGraph postgres tables.
    """
    checkpointer = await get_checkpointer()
    logger.info("Setting up LangGraph AsyncPostgresSaver database tables...")
    await checkpointer.setup()
    return checkpointer


async def prefetch_memory_parallel(
    checkpointer: AsyncPostgresSaver,
    config: dict[str, Any],
    fetch_long_term_coro: Coroutine[Any, Any, Any],
) -> Tuple[Any, Any]:
    """
    Pre-fetches short-term checkpoint state and long-term user facts concurrently
    using asyncio.gather() to minimize DB wait latency on request start.

    :param checkpointer: The AsyncPostgresSaver checkpointer instance.
    :param config: The LangGraph state configuration dict containing thread_id.
    :param fetch_long_term_coro: Coroutine function to fetch long-term user profile/memory.
    :return: A tuple of (checkpoint_tuple, long_term_memory_data).
    """
    short_term_task = checkpointer.aget_tuple(config)

    short_term_res, long_term_res = await asyncio.gather(
        short_term_task,
        fetch_long_term_coro,
        return_exceptions=True,
    )

    if isinstance(short_term_res, Exception):
        logger.error(f"Error fetching short-term memory: {short_term_res}")
        short_term_res = None

    if isinstance(long_term_res, Exception):
        logger.error(f"Error fetching long-term memory: {long_term_res}")
        long_term_res = None

    return short_term_res, long_term_res
