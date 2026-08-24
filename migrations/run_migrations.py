"""Database Migration Runner Script for Project Bite PostgreSQL."""

import asyncio
import logging
import os
import psycopg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_runner")

ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
MIGRATION_FILE = os.path.join(os.path.dirname(__file__), "001_initial_schema.sql")


def load_env():
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip().strip("'").strip('"')
                    os.environ[key.strip()] = val


async def run_migration():
    load_env()
    db_url = os.getenv("SUPABASE_POSTGRES_DIRECT_URL")
    if not db_url or "localhost" in db_url and "password" in db_url:
        logger.warning(f"DB URL in .env: {db_url}")

    logger.info("Connecting to PostgreSQL database...")
    try:
        async with await psycopg.AsyncConnection.connect(
            db_url, autocommit=True
        ) as conn:
            async with conn.cursor() as cur:
                with open(MIGRATION_FILE) as f:
                    sql_script = f.read()

                logger.info(
                    "Executing initial schema migration (001_initial_schema.sql)..."
                )
                await cur.execute(sql_script)
                logger.info("✅ Migration executed successfully!")

                # Check tables
                await cur.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
                )
                tables = await cur.fetchall()
                logger.info(f"Existing public tables: {[t[0] for t in tables]}")
    except Exception as e:
        logger.error(f"❌ Failed to run migration: {e}")


if __name__ == "__main__":
    asyncio.run(run_migration())
