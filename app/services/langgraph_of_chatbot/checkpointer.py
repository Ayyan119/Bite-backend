import asyncio
import logging
from typing import Any, Coroutine, Tuple
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

# Singleton memory saver instance for zero-latency, collision-free thread state
_memory_saver_instance = MemorySaver()
_checkpointer_instance: Any = None


async def get_checkpointer() -> Any:
    """Get or initialize the global checkpointer instance.

    Uses MemorySaver to guarantee zero latency and prevent prepared statement
    collisions on Supabase transaction poolers.
    """
    global _checkpointer_instance
    if _checkpointer_instance is None:
        _checkpointer_instance = _memory_saver_instance
        logger.info("Using zero-latency MemorySaver checkpointer for chatbot workflow.")
    return _checkpointer_instance


async def setup_checkpointer() -> Any:
    """Initialize checkpointer."""
    return await get_checkpointer()


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
