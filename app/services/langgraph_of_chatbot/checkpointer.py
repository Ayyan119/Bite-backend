import asyncio
import logging
from typing import Any, Coroutine, Tuple
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.db.connection import init_db_pool

logger = logging.getLogger(__name__)

_checkpointer_instance: Any = None
_memory_saver_instance = MemorySaver()


async def get_checkpointer() -> Any:
    """Get or initialize the global checkpointer instance.

    Uses AsyncPostgresSaver when PostgreSQL is available; falls back to MemorySaver
    if database is offline or unreachable (<1s probe) to guarantee zero latency.
    """
    global _checkpointer_instance
    if _checkpointer_instance is None:
        try:
            db_pool = await init_db_pool()
            # Fast 1.0s probe to check DB connectivity
            async with db_pool.connection(timeout=1.0) as conn:
                pass
            _checkpointer_instance = AsyncPostgresSaver(db_pool)
            logger.info("Using PostgreSQL AsyncPostgresSaver checkpointer.")
        except Exception as e:
            logger.warning(
                f"PostgreSQL checkpointer probe failed ({e}). "
                f"Falling back to zero-latency MemorySaver checkpointer."
            )
            _checkpointer_instance = _memory_saver_instance
    return _checkpointer_instance


async def setup_checkpointer() -> Any:
    """Initialize checkpointer and run setup migrations for LangGraph postgres tables if available."""
    checkpointer = await get_checkpointer()
    if isinstance(checkpointer, AsyncPostgresSaver):
        logger.info("Setting up LangGraph AsyncPostgresSaver database tables...")
        try:
            await checkpointer.setup()
        except Exception as e:
            logger.warning(f"Failed to setup Postgres checkpointer tables: {e}")
    return checkpointer


async def prefetch_memory_parallel(
    checkpointer: Any,
    config: dict[str, Any],
    fetch_long_term_coro: Coroutine[Any, Any, Any],
) -> Tuple[Any, Any]:
    """Pre-fetches short-term checkpoint state and long-term user facts concurrently."""
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
