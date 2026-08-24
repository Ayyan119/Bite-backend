-- =============================================================================
-- Migration: 001_initial_schema.sql
-- Description: Phase 1 Database Setup for Project Bite
-- Tables: profiles, meal_logs, meal_items
-- Indexes: Relational B-Tree & JSONB GIN Path Indexes
-- RLS: Enabled with user isolation policies matching auth.uid()
-- =============================================================================

-- Enable required extension for UUID generation if available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- Helper Function: Auto-update updated_at timestamp
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1. Table: public.profiles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL,
    display_name TEXT,
    height_cm NUMERIC(5,2),
    weight_kg NUMERIC(5,2),
    age INTEGER,
    gender TEXT,
    activity_level TEXT DEFAULT 'moderate',
    primary_goal TEXT DEFAULT 'maintenance',
    bmr NUMERIC(7,2) CHECK (bmr > 0),
    tdee NUMERIC(7,2) CHECK (tdee > 0),
    target_calories NUMERIC(7,2) CHECK (target_calories > 0),
    target_protein_g NUMERIC(6,2) CHECK (target_protein_g >= 0),
    target_carbs_g NUMERIC(6,2) CHECK (target_carbs_g >= 0),
    target_fat_g NUMERIC(6,2) CHECK (target_fat_g >= 0),
    target_micronutrients JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DROP TRIGGER IF EXISTS update_profiles_updated_at ON public.profiles;
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 2. Table: public.meal_logs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.meal_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meal_type TEXT NOT NULL CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    image_url TEXT,
    user_caption TEXT,
    total_calories NUMERIC(7,2) DEFAULT 0 CHECK (total_calories >= 0),
    total_protein_g NUMERIC(6,2) DEFAULT 0 CHECK (total_protein_g >= 0),
    total_carbs_g NUMERIC(6,2) DEFAULT 0 CHECK (total_carbs_g >= 0),
    total_fat_g NUMERIC(6,2) DEFAULT 0 CHECK (total_fat_g >= 0),
    aggregated_nutrients JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DROP TRIGGER IF EXISTS update_meal_logs_updated_at ON public.meal_logs;
CREATE TRIGGER update_meal_logs_updated_at
    BEFORE UPDATE ON public.meal_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 3. Table: public.meal_items
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.meal_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meal_log_id UUID NOT NULL REFERENCES public.meal_logs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    food_name TEXT NOT NULL,
    fdc_id INTEGER,
    portion_amount NUMERIC(6,2) DEFAULT 1.0 CHECK (portion_amount > 0),
    portion_unit TEXT DEFAULT 'serving',
    gram_weight NUMERIC(7,2) CHECK (gram_weight > 0),
    calories NUMERIC(7,2) DEFAULT 0 CHECK (calories >= 0),
    protein_g NUMERIC(6,2) DEFAULT 0 CHECK (protein_g >= 0),
    carbs_g NUMERIC(6,2) DEFAULT 0 CHECK (carbs_g >= 0),
    fat_g NUMERIC(6,2) DEFAULT 0 CHECK (fat_g >= 0),
    is_fallback BOOLEAN DEFAULT FALSE,
    raw_usda_nutrients JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 4. B-Tree & GIN Indexes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_meal_logs_user_id ON public.meal_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_meal_logs_logged_at ON public.meal_logs(logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_meal_items_meal_log_id ON public.meal_items(meal_log_id);
CREATE INDEX IF NOT EXISTS idx_meal_items_user_id ON public.meal_items(user_id);
CREATE INDEX IF NOT EXISTS idx_meal_items_fdc_id ON public.meal_items(fdc_id);

-- GIN indexes on JSONB for sub-millisecond micronutrient queries
CREATE INDEX IF NOT EXISTS idx_meal_logs_aggregated_nutrients_gin 
    ON public.meal_logs USING GIN (aggregated_nutrients jsonb_path_ops);

CREATE INDEX IF NOT EXISTS idx_meal_items_raw_usda_nutrients_gin 
    ON public.meal_items USING GIN (raw_usda_nutrients jsonb_path_ops);

-- -----------------------------------------------------------------------------
-- 5. Row Level Security (RLS) Policies
-- -----------------------------------------------------------------------------
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_items ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if re-running
DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
DROP POLICY IF EXISTS "Users can insert own profile" ON public.profiles;

DROP POLICY IF EXISTS "Users can view own meal logs" ON public.meal_logs;
DROP POLICY IF EXISTS "Users can insert own meal logs" ON public.meal_logs;
DROP POLICY IF EXISTS "Users can update own meal logs" ON public.meal_logs;
DROP POLICY IF EXISTS "Users can delete own meal logs" ON public.meal_logs;

DROP POLICY IF EXISTS "Users can view own meal items" ON public.meal_items;
DROP POLICY IF EXISTS "Users can insert own meal items" ON public.meal_items;
DROP POLICY IF EXISTS "Users can update own meal items" ON public.meal_items;
DROP POLICY IF EXISTS "Users can delete own meal items" ON public.meal_items;

-- Create RLS Policies
CREATE POLICY "Users can view own profile" 
    ON public.profiles FOR SELECT 
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" 
    ON public.profiles FOR UPDATE 
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" 
    ON public.profiles FOR INSERT 
    WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can view own meal logs" 
    ON public.meal_logs FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own meal logs" 
    ON public.meal_logs FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own meal logs" 
    ON public.meal_logs FOR UPDATE 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own meal logs" 
    ON public.meal_logs FOR DELETE 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can view own meal items" 
    ON public.meal_items FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own meal items" 
    ON public.meal_items FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own meal items" 
    ON public.meal_items FOR UPDATE 
    USING (auth.uid() = user_id);

-- -----------------------------------------------------------------------------
-- 6. LangGraph Checkpoint Tables for State Machine Memory
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_path TEXT NOT NULL DEFAULT '',
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id ON checkpoints (thread_id, checkpoint_ns);
CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread_id ON checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id);

