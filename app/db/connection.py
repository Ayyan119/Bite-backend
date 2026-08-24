import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import psycopg
from psycopg_pool import AsyncConnectionPool, PoolTimeout
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global async connection pool instance
pool: AsyncConnectionPool | None = None


async def init_db_pool() -> AsyncConnectionPool:
    """Initialize global async connection pool with 5.0s timeout for cloud DB connections."""
    global pool
    if pool is None:
        logger.info("Initializing PostgreSQL async connection pool...")
        pool = AsyncConnectionPool(
            conninfo=settings.SUPABASE_POSTGRES_DIRECT_URL,
            min_size=1,
            max_size=10,
            timeout=5.0,
            max_waiting=50,
            open=False,
            kwargs={"prepare_threshold": None},
        )
        try:
            await pool.open()
        except Exception as e:
            logger.warning(f"PostgreSQL pool initialization warning: {e}")
    return pool


async def close_db_pool() -> None:
    """Close global async connection pool."""
    global pool
    if pool is not None:
        logger.info("Closing PostgreSQL async connection pool...")
        try:
            await pool.close()
        except Exception as e:
            logger.warning(f"Error closing DB pool: {e}")
        pool = None


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Provide a non-blocking async database connection from the pool with 5.0s timeout."""
    global pool
    if pool is None:
        await init_db_pool()

    try:
        async with pool.connection(timeout=5.0) as conn:
            yield conn
    except (PoolTimeout, psycopg.OperationalError) as e:
        logger.warning(f"Database connection pool checkout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently offline or unreachable.",
        )
