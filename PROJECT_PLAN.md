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
- [x] **Task 1.1:** Connect via MCP Postgres server to verify database connectivity.
- [x] **Task 1.2:** Execute DDL migration for:
  - `public.profiles` (User BMR, TDEE, macro targets).
  - `public.meal_logs` (Timestamps, meal types, macro summaries, image URLs, `aggregated_nutrients jsonb`).
  - `public.meal_items` (Food names, `fdc_id`, servings, macros, `raw_usda_nutrients jsonb`).
- [x] **Task 1.3:** Create GIN indexes on `jsonb` columns for fast micronutrient querying.
- [x] **Task 1.4:** Setup Row Level Security (RLS) policies linking `user_id` to Supabase `auth.users`.

---

## Phase 2: LangGraph Workflow 1 — Food Vision & USDA Resolver
- [x] **Task 2.1:** Implement input schema & validation (Image base64 / URL + user caption, payload size bounds).
- [x] **Task 2.2:** Build **Vision Extraction Node** (Multimodal LLM) to detect food items, portions in grams, and cooking methods with Pydantic structured output.
- [x] **Task 2.3:** Build **USDA Tool Node** that searches USDA FoodData Central by item keywords concurrently (`asyncio.gather`).
- [x] **Task 2.4:** Build **Nutrient Reconciliation & Scaling Node**:
  - Scales 100g USDA values to estimated portion weights.
  - Extracts macro totals (Calories, Protein, Carbs, Fat).
  - Encapsulates complete micronutrient lists into JSONB format.
- [x] **Task 2.5:** Add fallback handling for items not found in USDA (LLM nutritional estimation with `is_fallback: true`).
- [x] **Task 2.6:** Write unit tests for the ingestion graph (`test_ingestion_graph_success` & `test_ingestion_graph_fallback`).

---

## Phase 3: LangGraph Workflow 2 — Conversational CRUD, Text Logging & Dual-Memory Agent
- [x] **Task 3.1:** Setup `AsyncPostgresSaver` checkpointer with `AsyncConnectionPool` and parallel memory pre-fetch (`asyncio.gather`).
- [x] **Task 3.2:** Build Short-Term Memory Manager & non-blocking background auto-summarizer (`asyncio.create_task` when message count > 10).
- [x] **Task 3.3:** Build Long-Term Memory Extractor (`asyncio.create_task`) and direct profile context injector (<0.1ms).
- [x] **Task 3.4:** Build Concurrent USDA Tool with In-Memory LRU Cache (`cachetools.TTLCache`) and fallback handlers.
- [x] **Task 3.5:** Implement 5 tenant-isolated database CRUD & analytics tools (`log_meal`, `get_daily_summary`, `get_micronutrient_total`, `update_meal_item`, `delete_meal_log`) supporting `is_fallback: true` regional dishes.
- [x] **Task 3.6:** Build Action Status SSE Streamer & Pydantic v2 schemas (`action_status` live events via `astream_events`).
- [x] **Task 3.7:** Author Agent System Prompt with temporal context, regional dish fallback rules (*"cholay with naan"*), and grounding guardrails.
- [x] **Task 3.8:** Assemble and compile conversational state graph (`agent_graph` and `run_agent_stream`).
- [x] **Task 3.9:** Write Integration Test 1 (Meal addition, regional fallback dishes, concurrent USDA & action status streaming).
- [x] **Task 3.10:** Write Integration Test 2 (JSONB micronutrient analytics, background long-term memory & history summarization).

---

## Phase 4: FastAPI Application Layer
- [ ] **Task 4.1: FastAPI Scaffold, uvloop Engine & Lifespan Pool Management**
  - Initialize `uvloop` event loop policy (`uvloop.install()`) and `ORJSONResponse` fast C-serialization.
  - Implement async `lifespan` manager initializing and gracefully closing `AsyncConnectionPool` and global `httpx.AsyncClient` HTTP/2 keep-alive pool.
  - Configure CORS middleware for Flutter Mobile and Web clients.
  - Setup global exception handlers (`RequestValidationError`, `HTTPException`, internal 500 handler).
  - Add health and readiness probes (`/health`, `/health/ready`).

- [ ] **Task 4.2: Zero-Network Supabase JWT Auth & Claims LRU Cache**
  - Build `app/api/deps.py` with `get_current_user` FastAPI dependency.
  - Cryptographically verify Supabase Bearer JWTs locally in-memory using `SUPABASE_JWT_SECRET` (0 network calls to auth servers).
  - Cache validated claims in an async in-memory LRU cache (`TTLCache(maxsize=1000, ttl=60)`), decoding subsequent requests in <0.01ms.
  - Enforce zero-trust security: inject verified `user_id` into all downstream database queries, LangGraph threads, and API routes.

- [ ] **Task 4.3: Food Vision Analysis Endpoint with Compression Guard (`POST /api/v1/meals/analyze`)**
  - Accept `multipart/form-data` (image file uploads up to 10MB) or `application/json` (base64 URI or image URL) + optional `user_caption` and `meal_type`.
  - Validate image payload format (magic bytes check) and compress/downscale images to max 1024x1024 (JPEG 80%), reducing payload size by 70% and vision latency by 50%.
  - Trigger LangGraph Workflow 1 (`ingestion_graph.ainvoke`) using global `httpx` HTTP/2 keep-alive pool.
  - Return structured `MealAnalysisResponse` containing detected items, portion estimates, USDA match status (`fdc_id`), fallback flags (`is_fallback`), scaled macros, and aggregated micronutrient JSONB dictionary.

- [ ] **Task 4.4: Single-Query CTE Atomic Persistence Endpoint (`POST /api/v1/meals/confirm`)**
  - Accept confirmed/edited meal payload (`MealConfirmRequest`) with adjusted portion weights, food names, and meal type.
  - Execute atomic single-query CTE SQL statement over `AsyncConnectionPool` inserting records into `public.meal_logs` and `public.meal_items` in 1 DB network round-trip.
  - Persist `aggregated_nutrients` and `raw_usda_nutrients` JSONB with `is_fallback` audit tracking.
  - Return `MealLogResponse` with newly created `meal_id` and updated daily nutrient totals.

- [ ] **Task 4.5: Instant-Flush SSE Conversational Agent Endpoint (`POST /api/v1/chat`)**
  - Connect Flutter chat interface to LangGraph Workflow 2 using `StreamingResponse(media_type="text/event-stream")`.
  - Flush initial SSE response headers immediately within <10ms (`event: status`).
  - Pass authenticated `user_id` and `thread_id` into LangGraph checkpointer (`AsyncPostgresSaver`).
  - Stream real-time dual-channel SSE events (`action_status` progress + assistant Markdown tokens).
  - Execute background long-term memory extraction via `asyncio.create_task` detached execution (0ms user wait time).

- [ ] **Task 4.6: Sub-Millisecond GIN-Indexed Daily Dashboard Endpoint (`GET /api/v1/dashboard/daily`)**
  - Accept query parameter `target_date: Optional[date]` (defaults to user's current date).
  - Execute ultra-low latency, GIN-indexed SQL queries over `public.meal_logs` and `public.profiles` using indexed `@>` path operators.
  - Return total consumed calories, protein, carbs, and fat alongside user target goals (BMR, TDEE, macro goals) and remaining calorie budget.
  - Return chronological meal cards grouped by `meal_type` (breakfast, lunch, dinner, snack) and top micronutrient breakdown.

- [ ] **Task 4.7: Direct Meal & Item REST CRUD Endpoints**
  - `GET /api/v1/meals`: Paginated meal history with date range filtering.
  - `GET /api/v1/meals/{meal_id}`: Detailed single meal log with associated item breakdown and micronutrients.
  - `PATCH /api/v1/meals/items/{item_id}`: Edit individual food item portion weight and recalculate macros.
  - `DELETE /api/v1/meals/{meal_id}`: Tenant-isolated deletion of meal log and cascading meal items.

- [ ] **Task 4.8: User Profile & Goals Management Endpoints**
  - `GET /api/v1/profile`: Retrieve user profile, BMR, TDEE, macro targets, and long-term memory facts.
  - `PUT /api/v1/profile`: Update user biometric profile, calorie targets, macro ratios, and dietary preferences.

- [ ] **Task 4.9: Automated Zero-Latency FastAPI Test Suite**
  - Author integration test suite using `httpx.AsyncClient` with `ASGITransport` / `pytest-asyncio`.
  - `tests/test_api_auth.py`: In-memory JWT authentication, token validation, and 401 unauthorized handling.
  - `tests/test_api_meals.py`: Test `/analyze` and single-query CTE `/confirm` endpoints.
  - `tests/test_api_chat.py`: Test `/chat` instant-flush SSE streaming, action status protocol, and thread persistence.
  - `tests/test_api_dashboard.py`: Test `/dashboard/daily` macro calculations, timeline grouping, and empty state handling.
  - `tests/test_api_profile.py`: Test profile retrieval and update endpoints.

---

## Phase 5: Verification & Deployment Preparation
- [ ] **Task 5.1:** Perform end-to-end integration tests (Upload -> Analyze -> Persist -> Query via Chatbot).
- [ ] **Task 5.2:** Dockerize FastAPI app (`Dockerfile` and `docker-compose.yml`).
- [ ] **Task 5.3:** Setup production environment variables and deploy backend.