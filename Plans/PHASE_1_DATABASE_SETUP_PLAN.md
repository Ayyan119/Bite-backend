# Implementation Plan: Phase 1 — Database Setup (Supabase / PostgreSQL)

## Goal Description
Establish a production-grade, highly secure, and optimized database schema for **Project Bite** in PostgreSQL/Supabase. 

This phase creates core database tables (`profiles`, `meal_logs`, `meal_items`), configures **GIN indexes** on `jsonb` columns for ultra-fast micronutrient analytics, enforces strict **Row Level Security (RLS)** for multi-tenant isolation, and sets up an async database migration pipeline.

---

## User Review Required

> [!IMPORTANT]
> **Database Credentials & Connection:**
> The plan includes a migration script `scripts/apply_migrations.py` that connects to PostgreSQL via `SUPABASE_POSTGRES_DIRECT_URL` in `.env`. Ensure your target Supabase or local PostgreSQL instance is running and reachable before executing migrations.

> [!NOTE]
> **RLS Policy Scope:**
> All queries are scoped strictly to `auth.uid()` using Supabase authentication conventions. `meal_items` policies use join checks on `meal_logs` to ensure user isolation without duplicate `user_id` columns.

---

## Open Questions

1. **Supabase Auth vs. Standalone Postgres**: Will you be running this against a remote Supabase instance (with `auth.users` populated by Supabase Auth) or a local Postgres instance (where a mock `auth.users` schema may be needed for local development)?

---

## Proposed Changes

### Database DDL & Schema Migration
#### [NEW] `sql/migrations/001_initial_schema.sql`
- Defines `public.profiles`, `public.meal_logs`, and `public.meal_items` tables.
- Creates foreign key constraints pointing to `auth.users(id)` and cascading deletes.
- Configures GIN indexes on `jsonb` columns (`aggregated_nutrients`, `raw_usda_nutrients`).
- Configures composite B-tree indexes for fast date-range meal history queries.
- Enables RLS and attaches row security policies for tenant isolation.

```sql
-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Profiles Table (User BMR, TDEE, macro targets)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    age INT CHECK (age > 0 AND age < 120),
    gender TEXT CHECK (gender IN ('male', 'female', 'other')),
    height_cm NUMERIC(5,2) CHECK (height_cm > 0),
    weight_kg NUMERIC(5,2) CHECK (weight_kg > 0),
    bmr NUMERIC(7,2) DEFAULT 0.00,
    tdee NUMERIC(7,2) DEFAULT 0.00,
    calorie_target INT DEFAULT 2000 CHECK (calorie_target > 0),
    protein_target_g INT DEFAULT 150 CHECK (protein_target_g >= 0),
    carb_target_g INT DEFAULT 200 CHECK (carb_target_g >= 0),
    fat_target_g INT DEFAULT 65 CHECK (fat_target_g >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Meal Logs Table (Timestamps, meal types, macro summaries, image URLs, aggregated_nutrients jsonb)
CREATE TABLE IF NOT EXISTS public.meal_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    meal_type TEXT NOT NULL CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    image_url TEXT,
    user_caption TEXT,
    total_calories NUMERIC(7,2) NOT NULL DEFAULT 0.00,
    total_protein_g NUMERIC(7,2) NOT NULL DEFAULT 0.00,
    total_carbs_g NUMERIC(7,2) NOT NULL DEFAULT 0.00,
    total_fat_g NUMERIC(7,2) NOT NULL DEFAULT 0.00,
    aggregated_nutrients JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Meal Items Table (Food names, fdc_id, servings, macros, raw_usda_nutrients jsonb)
CREATE TABLE IF NOT EXISTS public.meal_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meal_log_id UUID NOT NULL REFERENCES public.meal_logs(id) ON DELETE CASCADE,
    food_name TEXT NOT NULL,
    fdc_id INT,
    serving_size_g NUMERIC(7,2) NOT NULL CHECK (serving_size_g > 0),
    calories NUMERIC(7,2) NOT NULL DEFAULT 0.00,
    protein_g NUMERIC(7,2) NOT NULL DEFAULT 0.00,
    carbs_g NUMERIC(7,2) NOT NULL DEFAULT 0.00,
    fat_g NUMERIC(7,2) NOT NULL DEFAULT 0.00,
    raw_usda_nutrients JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. GIN & Performance Indexes
CREATE INDEX IF NOT EXISTS idx_meal_logs_aggregated_nutrients 
    ON public.meal_logs USING gin (aggregated_nutrients jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_meal_items_raw_usda_nutrients 
    ON public.meal_items USING gin (raw_usda_nutrients jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_meal_logs_user_logged_at 
    ON public.meal_logs (user_id, logged_at DESC);

CREATE INDEX IF NOT EXISTS idx_meal_items_meal_log_id 
    ON public.meal_items (meal_log_id);

-- 5. Row Level Security (RLS) Policies
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_items ENABLE ROW LEVEL SECURITY;

-- Profiles Policies
CREATE POLICY "Users can view their own profile" 
    ON public.profiles FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile" 
    ON public.profiles FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert their own profile" 
    ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);

-- Meal Logs Policies
CREATE POLICY "Users can view their own meal logs" 
    ON public.meal_logs FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own meal logs" 
    ON public.meal_logs FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own meal logs" 
    ON public.meal_logs FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own meal logs" 
    ON public.meal_logs FOR DELETE USING (auth.uid() = user_id);

-- Meal Items Policies (Scoped via meal_logs relation)
CREATE POLICY "Users can view their own meal items" 
    ON public.meal_items FOR SELECT USING (
        EXISTS (SELECT 1 FROM public.meal_logs WHERE id = meal_items.meal_log_id AND user_id = auth.uid())
    );

CREATE POLICY "Users can insert items into their own meal logs" 
    ON public.meal_items FOR INSERT WITH CHECK (
        EXISTS (SELECT 1 FROM public.meal_logs WHERE id = meal_items.meal_log_id AND user_id = auth.uid())
    );

CREATE POLICY "Users can update items in their own meal logs" 
    ON public.meal_items FOR UPDATE USING (
        EXISTS (SELECT 1 FROM public.meal_logs WHERE id = meal_items.meal_log_id AND user_id = auth.uid())
    );

CREATE POLICY "Users can delete items from their own meal logs" 
    ON public.meal_items FOR DELETE USING (
        EXISTS (SELECT 1 FROM public.meal_logs WHERE id = meal_items.meal_log_id AND user_id = auth.uid())
    );
```

---

### Migration Runner Script
#### [NEW] `scripts/apply_migrations.py`
- Async python script using `asyncpg` to load `.env` credentials, execute `sql/migrations/001_initial_schema.sql`, and log migration progress.

```python
import asyncio
import os
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("SUPABASE_POSTGRES_DIRECT_URL")

async def run_migrations():
    if not DATABASE_URL:
        raise ValueError("SUPABASE_POSTGRES_DIRECT_URL is not set in .env")
    
    print("Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        sql_path = Path(__file__).parent.parent / "sql" / "migrations" / "001_initial_schema.sql"
        print(f"Reading migration file: {sql_path}")
        sql = sql_path.read_text()
        
        print("Executing DDL migration...")
        await conn.execute(sql)
        print("Migration executed successfully!")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migrations())
```

---

## Verification Plan

### Automated Tests
#### [NEW] `tests/test_database_schema.py`
- Automated test using `pytest` & `asyncpg` verifying table existence, index definitions, and foreign key relationships.

Commands to run:
```bash
pytest tests/test_database_schema.py -v
```

### Manual Verification
1. Run `python scripts/apply_migrations.py`.
2. Verify tables `profiles`, `meal_logs`, `meal_items` exist in PostgreSQL.
3. Verify GIN indexes `idx_meal_logs_aggregated_nutrients` and `idx_meal_items_raw_usda_nutrients` exist.
