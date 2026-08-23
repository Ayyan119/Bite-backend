# Implementation Plan: Phase 1 — Database Setup (Supabase / PostgreSQL)

## Goal Description
Establish a production-grade relational database architecture on PostgreSQL / Supabase for **Project Bite** based on [`specs/1_DATABASE_SETUP.md`](file:///home/jiggra/bite-backend/specs/1_DATABASE_SETUP.md). 

This feature provisions:
1. Three core relational tables: `public.profiles`, `public.meal_logs`, and `public.meal_items`.
2. Flexible JSONB document columns (`aggregated_nutrients` and `raw_usda_nutrients`) for full micronutrient tracking.
3. Generalized Inverted Indexes (GIN with `jsonb_path_ops`) for high-speed sub-millisecond micronutrient queries.
4. Row Level Security (RLS) policies linking table access directly to Supabase `auth.uid()` for zero-trust tenant isolation.
5. Python async migration runners and comprehensive pytest test coverage using `psycopg3` / `asyncpg`.

---

## User Review Required

> [!IMPORTANT]
> **Database Credentials & Environment Configuration**
> * The `.env` file currently contains `SUPABASE_POSTGRES_DIRECT_URL=postgresql://postgres:password@localhost:5432/bite_db`.
> * For live production deployment, ensure the Supabase direct database connection string (e.g. `postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres`) is placed in your local `.env`.
> * Offline / automated unit tests will validate SQL DDL syntax, GIN index constructs, RLS definitions, and fallback gracefully if PostgreSQL host is offline.

---

## Open Questions

> [!NOTE]
> 1. Should we include automated seed data generation scripts (e.g. `app/db/seed.py`) for development profiles and sample meal logs?
> 2. Do you intend to use Supabase CLI for local database migrations (`supabase migration new`), or maintain standalone SQL migration scripts (`migrations/001_initial_schema.sql`) executed via Python async migration script? (The plan currently uses standalone SQL migrations for maximum portability across custom PostgreSQL and Supabase environments).

---

## Proposed Changes

### Database & Migration Layer (`migrations/`, `app/db/`)

#### `[NEW]` [`migrations/001_initial_schema.sql`](file:///home/jiggra/bite-backend/migrations/001_initial_schema.sql)
SQL DDL script executing schema definition:
* Extensions & Triggers: `uuid-ossp` extension and `update_updated_at_column()` PL/pgSQL trigger.
* Tables: `public.profiles`, `public.meal_logs`, `public.meal_items`.
* Relational B-Tree Indexes on `user_id`, `logged_at DESC`, `meal_log_id`, and `fdc_id`.
* GIN Indexes on `aggregated_nutrients` and `raw_usda_nutrients` (`jsonb_path_ops`).
* Row Level Security (RLS) Policies on all 3 tables checking `auth.uid() = id` / `user_id`.

```sql
-- Core Table Creation Snippet
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    bmr NUMERIC(7,2) CHECK (bmr > 0),
    tdee NUMERIC(7,2) CHECK (tdee > 0),
    target_calories NUMERIC(7,2) CHECK (target_calories > 0),
    target_protein_g NUMERIC(6,2) CHECK (target_protein_g >= 0),
    target_carbs_g NUMERIC(6,2) CHECK (target_carbs_g >= 0),
    target_fat_g NUMERIC(6,2) CHECK (target_fat_g >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### `[NEW]` [`app/db/migrate.py`](file:///home/jiggra/bite-backend/app/db/migrate.py)
Async database migration module using `psycopg.AsyncConnection` to parse and execute `migrations/001_initial_schema.sql` atomically against PostgreSQL.

#### `[NEW]` [`app/db/connection.py`](file:///home/jiggra/bite-backend/app/db/connection.py)
Connection pool management utility utilizing `psycopg_pool.AsyncConnectionPool` for non-blocking async query execution across FastAPI endpoints and LangGraph nodes.

---

### Data Models & Schemas (`app/schemas/`)

#### `[NEW]` [`app/schemas/profile.py`](file:///home/jiggra/bite-backend/app/schemas/profile.py)
Pydantic v2 schemas (`ProfileBase`, `ProfileCreate`, `ProfileResponse`) with strict field validations and type annotations.

#### `[NEW]` [`app/schemas/meal.py`](file:///home/jiggra/bite-backend/app/schemas/meal.py)
Pydantic v2 schemas (`MealLogBase`, `MealLogCreate`, `MealItemBase`, `MealItemCreate`, `NutrientAggregation`) with JSONB validation.

---

### Testing Suite (`tests/`)

#### `[NEW]` [`tests/test_db_schema.py`](file:///home/jiggra/bite-backend/tests/test_db_schema.py)
Automated pytest test suite verifying:
1. Migration file existence and SQL syntax validity.
2. Mandatory column, constraint, GIN index (`jsonb_path_ops`), and RLS policy definitions.
3. Async live migration execution and connection fallback tests.

---

## Verification Plan

### Automated Tests
Execute the pytest suite using the project virtual environment:
```bash
.venv/bin/pytest -v tests/test_db_schema.py
```

### Manual Verification
1. Run database migration script:
   ```bash
   .venv/bin/python app/db/migrate.py
   ```
2. Verify table structures, GIN indexes, and RLS policies in Supabase Dashboard SQL Editor or via `psql`:
   ```sql
   SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
   SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public';
   ```
