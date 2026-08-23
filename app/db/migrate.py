import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import psycopg

# Load environment variables from .env
load_dotenv()

MIGRATION_FILE = (
    Path(__file__).parent.parent.parent / "migrations" / "001_initial_schema.sql"
)


async def run_migrations(db_url: str | None = None) -> bool:
    """Executes the DDL migrations against PostgreSQL."""
    if not db_url:
        db_url = os.getenv("SUPABASE_POSTGRES_DIRECT_URL")

    if not db_url:
        print("[ERROR] SUPABASE_POSTGRES_DIRECT_URL environment variable is not set.")
        return False

    if not MIGRATION_FILE.exists():
        print(f"[ERROR] Migration file not found at: {MIGRATION_FILE}")
        return False

    print(f"[INFO] Reading DDL migration file: {MIGRATION_FILE.name}")
    sql_script = MIGRATION_FILE.read_text(encoding="utf-8")

    print(f"[INFO] Connecting to database...")
    try:
        async with await psycopg.AsyncConnection.connect(
            db_url, autocommit=True
        ) as aconn:
            async with aconn.cursor() as acur:
                print("[INFO] Executing DDL migration script...")
                await acur.execute(sql_script)
                print("[SUCCESS] DDL Migration executed successfully!")
                return True
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    success = asyncio.run(run_migrations(url))
    sys.exit(0 if success else 1)
