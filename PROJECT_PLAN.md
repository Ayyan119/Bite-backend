# Project Bite — Engineering Blueprint & Implementation Plan

**Goal:** Photo-first AI calorie and macronutrient tracker powered by LangGraph, USDA FoodData Central, Supabase PostgreSQL, and Flutter.

---

## Phase 0: Workspace & Repository Setup
- [x] **Task 0.1:** Initialize local Python virtual environment (`python -m venv .venv` and activate).
- [x] **Task 0.2:** Create `.gitignore` (Python, Flutter, `.env`, credentials).
- [x] **Task 0.3:** Initialize local git repository (`git init`) and commit baseline files.
- [x] **Task 0.4:** Create remote GitHub repository named `bite-backend` (or `bite-app`) and push initial commit.
- [x] **Task 0.5:** Setup `.env` file with placeholders for:
  - `SUPABASE_POSTGRES_DIRECT_URL`
  - `OPENAI_API_KEY` or `GEMINI_API_KEY`
  - `USDA_API_KEY`
  - `SUPABASE_JWT_SECRET`

---

## Phase 1: Database Setup (Supabase / PostgreSQL)
- [ ] **Task 1.1:** Connect via MCP Postgres server to verify database connectivity.
- [ ] **Task 1.2:** Execute DDL migration for:
  - `public.profiles` (User BMR, TDEE, macro targets).
  - `public.meal_logs` (Timestamps, meal types, macro summaries, image URLs, `aggregated_nutrients jsonb`).
  - `public.meal_items` (Food names, `fdc_id`, servings, macros, `raw_usda_nutrients jsonb`).
- [ ] **Task 1.3:** Create GIN indexes on `jsonb` columns for fast micronutrient querying.
- [ ] **Task 1.4:** Setup Row Level Security (RLS) policies linking `user_id` to Supabase `auth.users`.

---

## Phase 2: LangGraph Workflow 1 — Food Vision & USDA Resolver
- [ ] **Task 2.1:** Implement input schema (Image base64 / URL + user caption).
- [ ] **Task 2.2:** Build **Vision Extraction Node** (Multimodal LLM) to detect food items, portions, and cooking methods.
- [ ] **Task 2.3:** Build **USDA Tool Node** that searches USDA FoodData Central by item keywords.
- [ ] **Task 2.4:** Build **Nutrient Reconciliation & Scaling Node**:
  - Scales 100g USDA values to estimated portion weights.
  - Extracts macro totals (Calories, Protein, Carbs, Fat).
  - Encapsulates complete micronutrient lists into JSONB format.
- [ ] **Task 2.5:** Add fallback handling for items not found in USDA.
- [ ] **Task 2.6:** Write unit  tests for the ingestion graph.(only 2 test)

---

## Phase 3: LangGraph Workflow 2 — Conversational CRUD & Micronutrient Agent
- [ ] **Task 3.1:** Setup `AsyncPostgresSaver` checkpointer for session/conversation memory.
- [ ] **Task 3.2:** Build database toolset (scoped to `user_id`):
  - `log_meal(meal_data)`
  - `get_daily_summary(date)`
  - `get_micronutrient_total(nutrient_name, date)` (queries JSONB)
  - `update_meal_item(item_id, changes)`
  - `delete_meal_log(meal_id)`
- [ ] **Task 3.3:** Define Agent System Prompt (warm, joyful, concise, safety-conscious).
- [ ] **Task 3.4:** Build conversational state graph with tool calling.
- [ ] **Task 3.5:** Write integration tests verifying database edits and JSONB queries.(only 2 test)

---

## Phase 4: FastAPI Application Layer
- [ ] **Task 4.1:** Scaffold FastAPI project structure (`app/`, `routers/`, `services/`, `models/`).
- [ ] **Task 4.2:** Implement Supabase JWT verification middleware for securing endpoints.
- [ ] **Task 4.3:** Build `/api/v1/meals/analyze` endpoint (Accepts multipart image + caption, triggers Workflow 1).
- [ ] **Task 4.4:** Build `/api/v1/meals/confirm` endpoint (Persists confirmed meal and items to database).
- [ ] **Task 4.5:** Build `/api/v1/chat` endpoint (Connects Flutter chat interface to Workflow 2 with streaming response support).
- [ ] **Task 4.6:** Build `/api/v1/dashboard/daily` endpoint (Fast macro totals for Flutter home screen).

---

## Phase 5: Verification & Deployment Preparation
- [ ] **Task 5.1:** Perform end-to-end integration tests (Upload -> Analyze -> Persist -> Query via Chatbot).
- [ ] **Task 5.2:** Dockerize FastAPI app (`Dockerfile` and `docker-compose.yml`).
- [ ] **Task 5.3:** Setup production environment variables and deploy backend.