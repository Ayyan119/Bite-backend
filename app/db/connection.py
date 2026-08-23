import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import psycopg
from psycopg_pool import AsyncConnectionPool
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global async connection pool instance
pool: AsyncConnectionPool | None = None


async def init_db_pool() -> AsyncConnectionPool:
    """Initialize global async connection pool."""
    global pool
    if pool is None:
        logger.info("Initializing PostgreSQL async connection pool...")
        pool = AsyncConnectionPool(
            conninfo=settings.SUPABASE_POSTGRES_DIRECT_URL,
            min_size=1,
            max_size=10,
            open=False,
        )
        await pool.open()
    return pool


async def close_db_pool() -> None:
    """Close global async connection pool."""
    global pool
    if pool is not None:
        logger.info("Closing PostgreSQL async connection pool...")
        await pool.close()
        pool = None


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Provide a non-blocking async database connection from the pool."""
    global pool
    if pool is None:
        # Fallback to direct async connection if pool is not explicitly opened
        async with await psycopg.AsyncConnection.connect(
            settings.SUPABASE_POSTGRES_DIRECT_URL
        ) as conn:
            yield conn
    else:
        async with pool.connection() as conn:
            yield conn
