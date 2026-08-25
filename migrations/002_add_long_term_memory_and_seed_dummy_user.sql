-- =============================================================================
-- Migration: 002_add_long_term_memory_and_seed_dummy_user.sql
-- Description: Adds long_term_memory and password_hash columns to public.profiles
--              and seeds deterministic dummy user (Alex Morgan) and meals.
-- =============================================================================

-- 1. Add columns to public.profiles if not existing
ALTER TABLE public.profiles 
    ADD COLUMN IF NOT EXISTS long_term_memory JSONB DEFAULT '{}'::jsonb;

ALTER TABLE public.profiles 
    ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- 2. Seed / Upsert Dummy User (Alex Morgan)
-- UUID generated via uuid5(NAMESPACE_DNS, 'alex.morgan@bite.app') -> 579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e
INSERT INTO public.profiles (
    id, email, display_name, height_cm, weight_kg, age, gender,
    activity_level, primary_goal, bmr, tdee,
    target_calories, target_protein_g, target_carbs_g, target_fat_g,
    target_micronutrients, long_term_memory, password_hash, updated_at
)
VALUES (
    '579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e',
    'alex.morgan@bite.app',
    'Alex Morgan',
    178.00,
    75.00,
    28,
    'male',
    'moderate',
    'muscle_gain',
    1740.00,
    2697.00,
    2400.00,
    180.00,
    250.00,
    70.00,
    '{"calcium_mg": 1000, "iron_mg": 18, "potassium_mg": 3500, "vitamin_c_mg": 90}'::jsonb,
    '{
        "allergies": ["Peanuts"],
        "dietary_preferences": ["High Protein", "Mediterranean"],
        "disliked_foods": ["Mushrooms"],
        "notes": ["Prefers oats & eggs for breakfast", "Aims for 180g protein daily", "Trains 4 times a week"]
    }'::jsonb,
    'bite12345',
    NOW()
)
ON CONFLICT (id) DO UPDATE SET
    email = EXCLUDED.email,
    display_name = EXCLUDED.display_name,
    height_cm = EXCLUDED.height_cm,
    weight_kg = EXCLUDED.weight_kg,
    age = EXCLUDED.age,
    gender = EXCLUDED.gender,
    activity_level = EXCLUDED.activity_level,
    primary_goal = EXCLUDED.primary_goal,
    bmr = EXCLUDED.bmr,
    tdee = EXCLUDED.tdee,
    target_calories = EXCLUDED.target_calories,
    target_protein_g = EXCLUDED.target_protein_g,
    target_carbs_g = EXCLUDED.target_carbs_g,
    target_fat_g = EXCLUDED.target_fat_g,
    target_micronutrients = EXCLUDED.target_micronutrients,
    long_term_memory = EXCLUDED.long_term_memory,
    password_hash = EXCLUDED.password_hash,
    updated_at = NOW();

-- 3. Also seed developer@example.com with full profile stats
INSERT INTO public.profiles (
    id, email, display_name, height_cm, weight_kg, age, gender,
    activity_level, primary_goal, bmr, tdee,
    target_calories, target_protein_g, target_carbs_g, target_fat_g,
    target_micronutrients, long_term_memory, password_hash, updated_at
)
VALUES (
    '4c388bec-d158-553c-9857-0887231c6481',
    'developer@example.com',
    'Developer Ayyan',
    175.00,
    70.00,
    25,
    'male',
    'moderate',
    'maintenance',
    1680.00,
    2604.00,
    2200.00,
    160.00,
    220.00,
    65.00,
    '{"calcium_mg": 1000, "iron_mg": 18, "potassium_mg": 3500, "vitamin_c_mg": 90}'::jsonb,
    '{
        "allergies": [],
        "dietary_preferences": ["Balanced", "High Protein"],
        "disliked_foods": [],
        "notes": ["Developer test account with full body stats"]
    }'::jsonb,
    'bite12345',
    NOW()
)
ON CONFLICT (id) DO UPDATE SET
    display_name = COALESCE(public.profiles.display_name, EXCLUDED.display_name),
    height_cm = COALESCE(public.profiles.height_cm, EXCLUDED.height_cm),
    weight_kg = COALESCE(public.profiles.weight_kg, EXCLUDED.weight_kg),
    age = COALESCE(public.profiles.age, EXCLUDED.age),
    gender = COALESCE(public.profiles.gender, EXCLUDED.gender),
    long_term_memory = COALESCE(public.profiles.long_term_memory, EXCLUDED.long_term_memory),
    password_hash = COALESCE(public.profiles.password_hash, EXCLUDED.password_hash),
    updated_at = NOW();

-- 4. Clean up any previous seed dummy meals to avoid duplicate key violations
DELETE FROM public.meal_logs 
WHERE id IN ('a1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002');

-- 5. Seed Breakfast for Alex Morgan (Today)
WITH new_meal AS (
    INSERT INTO public.meal_logs (
        id, user_id, logged_at, meal_type, user_caption,
        total_calories, total_protein_g, total_carbs_g, total_fat_g,
        aggregated_nutrients
    )
    VALUES (
        'a1000000-0000-0000-0000-000000000001',
        '579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e',
        CURRENT_DATE + TIME '08:30:00',
        'breakfast',
        'Scrambled eggs, whole wheat toast, and an apple',
        471.00,
        25.40,
        54.20,
        16.70,
        '{"calcium_mg": 120.5, "iron_mg": 3.8, "potassium_mg": 450.0, "vitamin_c_mg": 8.4}'::jsonb
    )
    RETURNING id, user_id
)
INSERT INTO public.meal_items (
    id, meal_log_id, user_id, food_name, fdc_id,
    portion_amount, portion_unit, gram_weight,
    calories, protein_g, carbs_g, fat_g, raw_usda_nutrients
)
VALUES
    (
        gen_random_uuid(),
        'a1000000-0000-0000-0000-000000000001',
        '579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e',
        'Scrambled Eggs (3 large)',
        748967,
        3.0,
        'large egg',
        150.0,
        216.0,
        18.9,
        1.2,
        14.4,
        '{"calcium_mg": 75.0, "iron_mg": 2.5, "potassium_mg": 200.0}'::jsonb
    ),
    (
        gen_random_uuid(),
        'a1000000-0000-0000-0000-000000000001',
        '579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e',
        'Whole Wheat Toast',
        1100598,
        2.0,
        'slice',
        60.0,
        160.0,
        6.0,
        28.0,
        2.0,
        '{"calcium_mg": 35.5, "iron_mg": 1.1, "potassium_mg": 110.0}'::jsonb
    ),
    (
        gen_random_uuid(),
        'a1000000-0000-0000-0000-000000000001',
        '579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e',
        'Fresh Red Apple',
        1102644,
        1.0,
        'medium apple',
        182.0,
        95.0,
        0.5,
        25.0,
        0.3,
        '{"potassium_mg": 140.0, "vitamin_c_mg": 8.4}'::jsonb
    );

-- 6. Seed Lunch for Alex Morgan (Today)
WITH new_lunch AS (
    INSERT INTO public.meal_logs (
        id, user_id, logged_at, meal_type, user_caption,
        total_calories, total_protein_g, total_carbs_g, total_fat_g,
        aggregated_nutrients
    )
    VALUES (
        'a1000000-0000-0000-0000-000000000002',
        '579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e',
        CURRENT_DATE + TIME '13:15:00',
        'lunch',
        'Grilled chicken breast with brown rice and steamed broccoli',
        600.00,
        70.70,
        56.30,
        9.40,
        '{"calcium_mg": 95.0, "iron_mg": 4.2, "potassium_mg": 780.0, "vitamin_c_mg": 89.2}'::jsonb
    )
    RETURNING id, user_id
)
INSERT INTO public.meal_items (
    id, meal_log_id, user_id, food_name, fdc_id,
    portion_amount, portion_unit, gram_weight,
    calories, protein_g, carbs_g, fat_g, raw_usda_nutrients
)
VALUES
    (
        gen_random_uuid(),
        'a1000000-0000-0000-0000-000000000002',
        '579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e',
        'Grilled Chicken Breast',
        171077,
        1.0,
        'fillet',
        200.0,
        330.0,
        62.0,
        0.0,
        7.2,
        '{"iron_mg": 1.8, "potassium_mg": 420.0}'::jsonb
    ),
    (
        gen_random_uuid(),
        'a1000000-0000-0000-0000-000000000002',
        '579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e',
        'Cooked Brown Rice',
        169704,
        1.0,
        'cup',
        195.0,
        218.0,
        4.5,
        45.8,
        1.6,
        '{"iron_mg": 1.0, "potassium_mg": 150.0}'::jsonb
    ),
    (
        gen_random_uuid(),
        'a1000000-0000-0000-0000-000000000002',
        '579b6a22-cbaf-55eb-836c-f7f8cfbfaf7e',
        'Steamed Broccoli',
        1103170,
        1.0,
        'cup chopped',
        150.0,
        52.0,
        4.2,
        10.5,
        0.6,
        '{"calcium_mg": 60.0, "iron_mg": 1.4, "potassium_mg": 210.0, "vitamin_c_mg": 89.2}'::jsonb
    );
