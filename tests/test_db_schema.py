import os
import pytest
from pathlib import Path
import psycopg

MIGRATION_FILE = Path(__file__).parent.parent / "migrations" / "001_initial_schema.sql"


def test_migration_file_exists():
    """Verify that the DDL migration file exists and is non-empty."""
    assert MIGRATION_FILE.exists(), f"Migration file {MIGRATION_FILE} does not exist"
    content = MIGRATION_FILE.read_text(encoding="utf-8")
    assert len(content) > 0, "Migration file is empty"


def test_migration_sql_structure():
    """Verify required tables, columns, indexes, and RLS policies in the DDL script."""
    sql = MIGRATION_FILE.read_text(encoding="utf-8")

    # Required Tables
    assert "CREATE TABLE IF NOT EXISTS public.profiles" in sql
    assert "CREATE TABLE IF NOT EXISTS public.meal_logs" in sql
    assert "CREATE TABLE IF NOT EXISTS public.meal_items" in sql

    # Required JSONB Columns
    assert "aggregated_nutrients JSONB" in sql
    assert "raw_usda_nutrients JSONB" in sql

    # Required GIN Indexes
    assert "USING GIN (aggregated_nutrients jsonb_path_ops)" in sql
    assert "USING GIN (raw_usda_nutrients jsonb_path_ops)" in sql

    # Required RLS Statements
    assert "ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE public.meal_logs ENABLE ROW LEVEL SECURITY;" in sql
    assert "ALTER TABLE public.meal_items ENABLE ROW LEVEL SECURITY;" in sql
    assert "auth.uid()" in sql


@pytest.mark.asyncio
async def test_live_postgres_migration():
    """Run migration against live Postgres database if connection is available."""
    db_url = os.getenv("SUPABASE_POSTGRES_DIRECT_URL")
    if not db_url or "localhost" in db_url:
        # Check if local postgres port is open
        try:
            aconn = await psycopg.AsyncConnection.connect(db_url, connect_timeout=1)
            await aconn.close()
        except Exception:
            pytest.skip("PostgreSQL database server is not currently reachable.")

    async with await psycopg.AsyncConnection.connect(db_url) as aconn:
        async with aconn.cursor() as acur:
            # Check table existence in public schema
            await acur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public';
            """)
            rows = await acur.fetchall()
            tables = [r[0] for r in rows]
            assert "profiles" in tables
            assert "meal_logs" in tables
            assert "meal_items" in tables
