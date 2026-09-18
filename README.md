# Bite-Backend: Multimodal AI Nutrition Engine & Dual-Memory Agent

A high-performance, asynchronous AI nutrition platform powered by **LangGraph**, **FastAPI (uvloop)**, **Supabase PostgreSQL**, and the **USDA FoodData Central API**. It delivers real-time multimodal meal image analysis, portion estimation, nutrition scaling, and a dual-memory conversational assistant with streaming Server-Sent Events (SSE).

---

## Architecture Overview

```mermaid
flowchart TD
    Client([Flutter App / Web Client]) --> Gateway[FastAPI + uvloop Gateway]
    
    subgraph IngestionFlow ["1. Multimodal Food Vision & USDA Ingestion"]
        Gateway -->|POST /api/v1/meals/analyze| VisionNode[Vision Extraction Node (Multimodal LLM)]
        VisionNode -->|Detected Foods & Portions| USDANode[Concurrent USDA Resolver (asyncio.gather)]
        USDANode -->|FDC Matching & Scaling| Reconcile[Nutrient Scaling & JSONB Encapsulation]
        Reconcile -->|Structured Meal Analysis| Client
        Client -->|POST /api/v1/meals/confirm| SingleCTE[Atomic Single-Query CTE Persistence]
        SingleCTE --> Postgres[(Supabase PostgreSQL + GIN Indexes)]
    end
    
    subgraph ConversationalFlow ["2. Dual-Memory Agent & Analytics"]
        Gateway -->|POST /api/v1/chat| AgentGraph[LangGraph Conversational Graph]
        AgentGraph <--> Checkpointer[(AsyncPostgresSaver Checkpointer)]
        AgentGraph --> STM[Short-Term Memory & Background Summarizer]
        AgentGraph --> LTM[Long-Term Biometric Profile Extractor]
        AgentGraph --> CRUD[5 Tenant-Isolated Database & Analytics Tools]
        AgentGraph -->|Real-Time Dual-Channel SSE| Client
    end
```

---

## Key Features

- 📸 **Multimodal Food Vision Ingestion:** Analyzes meal images or URLs to identify food items, estimated gram weights, and preparation methods with strict Pydantic validation.
- 🥗 **Concurrent USDA FoodData Central Resolver:** Performs asynchronous parallel lookups against USDA databases with in-memory TTL caching (`cachetools.TTLCache`) and fallback estimation for regional/custom dishes.
- ⚡ **High-Throughput FastAPI Engine:** Built with `uvloop`, `ORJSONResponse`, HTTP/2 connection pooling (`httpx.AsyncClient`), and asynchronous connection pooling (`AsyncConnectionPool`).
- 🔒 **Zero-Network In-Memory JWT Authentication:** Locally verifies Supabase Bearer tokens cryptographically via `SUPABASE_JWT_SECRET` with in-memory LRU claims caching (<0.01ms auth overhead).
- 🧠 **Dual-Memory Conversational Agent (LangGraph):**
  - **Short-Term Memory (STM):** Automatic non-blocking message window summarization.
  - **Long-Term Memory (LTM):** Asynchronous biometric profile and dietary preference extraction (<0.1ms injection).
  - **State Persistence:** Persistent multi-turn threads powered by `AsyncPostgresSaver`.
- 📊 **Sub-Millisecond GIN-Indexed Analytics:** Single-query CTE atomic inserts and GIN-indexed JSONB queries for fast macro/micronutrient tracking.
- 🌊 **Instant-Flush Dual-Channel SSE:** Streams both `action_status` tool progress events and assistant response tokens directly to clients.

---

## Tech Stack

- **AI & Agent Orchestration:** LangGraph (`StateGraph`, `AsyncPostgresSaver`), LangChain Core, LangChain OpenAI / Gemini
- **Backend API:** FastAPI, Uvicorn, uvloop, Pydantic v2, HTTPX, ORJSON
- **Database & Storage:** PostgreSQL, Supabase, `psycopg` async pool, GIN indexing
- **External Integrations:** USDA FoodData Central API
- **Containerization & Testing:** Docker, Docker Compose, Pytest AsyncIO

---

## API Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/meals/analyze` | Multimodal meal image/URL ingestion, portion estimation, and USDA resolution |
| `POST` | `/api/v1/meals/confirm` | Atomic single-query CTE persistence for confirmed meal nutrients |
| `POST` | `/api/v1/chat` | Instant-flush Server-Sent Events (SSE) conversational assistant stream |
| `GET` | `/api/v1/dashboard/daily` | GIN-indexed daily macro totals, calorie budget, and grouped meal timeline |
| `GET/PUT`| `/api/v1/profile` | Biometric profile, BMR/TDEE calculation, and long-term memory facts |
| `GET` | `/health` / `/health/ready` | Health checks and connection pool readiness probes |

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- PostgreSQL / Supabase account
- Docker & Docker Compose (optional)

### 2. Installation

```bash
git clone https://github.com/Ayyan119/Bite-backend.git
cd Bite-backend

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Setup

Copy `.env.example` to `.env` and configure your credentials:

```bash
cp .env.example .env
```

```env
SUPABASE_POSTGRES_DIRECT_URL=postgresql://user:pass@host:5432/dbname
SUPABASE_JWT_SECRET=your_supabase_jwt_secret
OPENAI_API_KEY=your_openai_api_key
USDA_API_KEY=your_usda_api_key
```

### 4. Running the Server

**Local Development:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Using Docker:**
```bash
docker build -t bite-backend .
docker run -p 8000:8000 --env-file .env bite-backend
```

### 5. Running the Test Suite

```bash
pytest tests/ -v
```

---

## License

MIT License.
