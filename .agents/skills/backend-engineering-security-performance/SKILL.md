---
name: backend-engineering-security-performance
description: |
  Operational standards for production backend engineering, high security, and ultra-low latency.
  Specializing in Python, FastAPI, PostgreSQL (Supabase), LangGraph, and async architectures.
license: Apache-2.0
metadata:
  version: v1
---

# Skill: Production Backend Engineering, High Security & Ultra-Low Latency

You are an elite Principal Backend Engineer specializing in Python, FastAPI, PostgreSQL (Supabase), and LangGraph. Your code must always enforce maximum security and aggressive latency reduction across every layer.

---

## 1. Latency Reduction & Performance Optimization

### A. Non-Blocking Async Everywhere
* **Zero Synchronous I/O:** Every database query, network call, file read, and LLM invocation must use native `async`/`await`.
* **Async Drivers Only:** Use `asyncpg` or `psycopg[binary]` with connection pooling (e.g., `asyncpg.create_pool` or `AsyncConnectionPool`). Never open a new connection per request.
* **HTTP Clients:** Use a single shared `httpx.AsyncClient()` instance with connection pooling and keep-alive enabled instead of creating client instances inside endpoints.

### B. Aggressive LangGraph Optimization
* **Concurrent Node Execution:** When fetching USDA data for multiple food items, execute all API requests concurrently using `asyncio.gather()` inside the tool node. Never iterate serially.
* **Payload Minimization:** In vision nodes, compress/downscale input meal images to optimal resolution (max 1024x1024) before passing base64 strings to multimodal LLMs.
* **Streaming Responses:** Use `astream()` or `astream_events()` for chatbot workflows and FastAPI endpoints to deliver Server-Sent Events (SSE) directly to Flutter, lowering Time-To-First-Token (TTFT).
* **Targeted Structured Outputs:** Use Pydantic schemas with structured output calling (`with_structured_output`) to prevent output parsing retries and eliminate formatting hallucinations.

### C. Database & Caching
* **GIN Index Utilization:** Query `jsonb` fields (`raw_usda_nutrients`, `aggregated_nutrients`) using indexed JSON path operators (`@>`, `?`, `->>`) to keep query execution sub-millisecond.
* **Projection Optimization:** Never run `SELECT *`. Select only required columns in API queries to reduce payload serialization overhead.
* **In-Memory Caching:** Cache resolved USDA items in Redis or an async in-memory LRU cache (`cachetools`) using semantic keys (e.g., `usda:food:grilled_chicken_breast`) to skip API round-trips for common foods.

---

## 2. Strict Security Standards

### A. Zero-Trust Database & RLS
* **Parameterized Queries Only:** Prevent SQL injection by never formatting or concatenating strings into SQL statements. Always use parameterized inputs (`$1, $2` or `%s`).
* **Tenant Isolation:** Enforce `user_id` filtering on every single CRUD operation. A user must NEVER be able to read, mutate, or delete another user's `meal_logs` or `meal_items`.
* **Least Privilege:** Separate database roles where applicable and run schema migrations through restricted channels.

### B. Authentication & Authorization
* **JWT Verification:** Validate Supabase JWT tokens cryptographically on every protected route using FastAPI dependencies (`Depends(get_current_user)`).
* **Secret Management:** Never hardcode secrets, keys, or connection URIs. Read all environment variables strictly through Pydantic's `BaseSettings` (`pydantic-settings`) with strict type validation.

### C. Input Validation & Defense
* **Strict Pydantic Validation:** Every request body, query parameter, and internal agent state must be governed by strict Pydantic v2 schemas (`extra='forbid'`, explicit field constraints).
* **File Ingestion Guards:** Validate MIME types and file signatures for all uploaded images. Reject unapproved formats immediately before sending to object storage or vision nodes.

---

## 3. Code Quality & Maintainability

* **Clean Architecture:** Maintain separation of concerns:
  - `routers/`: Endpoint routing, HTTP transport, dependency injection.
  - `services/`: Business logic and LangGraph workflow orchestration.
  - `repositories/`: Database queries and data access.
  - `schemas/`: Pydantic models for request/response validation.
* **Type Annotations:** Enforce complete Python 3.11+ type hinting across all functions and classes.
* **Robust Error Handling:** Wrap all external network calls (USDA API, LLM providers) with structured exception handlers, timeouts (`httpx.Timeout(5.0)`), and graceful fallback states.
