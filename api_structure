# Project Bite API Specification & Structure Reference

This document provides a comprehensive specification of all REST endpoints, SSE streaming protocols, request/response DTO schemas, and authentication mechanics in the **Bite Backend API**.

---

## 1. Global API Metadata

* **Base URL**: `http://<HOST>:8000/api/v1`
* **Content-Type**: `application/json` (Default) / `multipart/form-data` (File upload) / `text/event-stream` (SSE Chat)
* **Authentication**: HTTP Bearer JWT Token (`Authorization: Bearer <access_token>`)
* **Interactive OpenAPI Specs**: `http://<HOST>:8000/docs`
* **OpenAPI Schema**: `http://<HOST>:8000/openapi.json`

---

## 2. Authentication & Dev Security (`/api/v1/auth`)

### 2.1 User Login
* **HTTP Method**: `POST`
* **Path**: `/api/v1/auth/login`
* **Auth Required**: No
* **Description**: Authenticates user with email and password, returning a signed 24-hour Supabase Bearer JWT token and profile metadata.
* **Request Body** (`LoginRequest`):
  ```json
  {
    "email": "user@example.com",
    "password": "user_password"
  }
  ```
* **Response** (`AuthResponse` - `200 OK`):
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "user@example.com",
    "display_name": "User Name",
    "age": 28,
    "height_cm": 178.0,
    "weight_kg": 75.0,
    "gender": "male",
    "bmr": 1720.0,
    "tdee": 2666.0,
    "target_calories": 2400.0
  }
  ```

---

### 2.2 User Registration
* **HTTP Method**: `POST`
* **Path**: `/api/v1/auth/register`
* **Auth Required**: No
* **Description**: Registers a new user, calculates BMR/TDEE automatically using Mifflin-St Jeor equation, and sets macro targets.
* **Request Body** (`RegisterRequest`):
  ```json
  {
    "email": "newuser@example.com",
    "password": "secret_password",
    "display_name": "New User",
    "age": 25,
    "height_cm": 175.0,
    "weight_kg": 70.0,
    "gender": "male",
    "activity_level": "moderate",
    "primary_goal": "muscle_gain"
  }
  ```
* **Response** (`AuthResponse` - `201 Created`): Same as `AuthResponse`.

---

### 2.3 Development JWT Token Generator
* **HTTP Method**: `POST`
* **Path**: `/api/v1/auth/dev-token`
* **Auth Required**: No
* **Description**: Generates a valid test JWT token for Swagger UI or API client integration without password verification.
* **Request Body** (`DevTokenRequest`):
  ```json
  {
    "email": "alex.morgan@bite.app",
    "user_id": null
  }
  ```
* **Response** (`DevTokenResponse` - `200 OK`):
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "alex.morgan@bite.app",
    "display_name": "Alex Morgan"
  }
  ```

---

## 3. Meal Ingestion & Analysis (`/api/v1/meals`)

### 3.1 Multimodal Food Vision Analysis
* **HTTP Method**: `POST`
* **Path**: `/api/v1/meals/analyze`
* **Auth Required**: Yes (`Bearer Token`)
* **Content-Type**: `application/json` OR `multipart/form-data`
* **Description**: Analyzes food images via AI Vision (`gpt-4o-mini`), resolves food names against USDA FoodData Central, calculates macros, and auto-infers meal category.
* **JSON Request Body** (`MealAnalyzeRequest`):
  ```json
  {
    "image_url": "https://example.com/food.jpg",
    "user_caption": "2 bananas with 1 cup milk",
    "meal_type": "breakfast"
  }
  ```
* **Multipart Form Data**:
  * `file`: Binary image file upload (JPEG/PNG, max 10MB)
  * `user_caption`: (Optional string)
  * `meal_type`: (Optional: `breakfast`, `lunch`, `dinner`, `snack`)
* **Response** (`MealAnalysisResponse` - `200 OK`):
  ```json
  {
    "detected_items": [
      {
        "food_name": "Banana",
        "fdc_id": 2012128,
        "portion_amount": 2.0,
        "portion_unit": "medium banana",
        "gram_weight": 236.0,
        "calories": 210.04,
        "protein_g": 2.57,
        "carbs_g": 53.81,
        "fat_g": 0.78,
        "is_fallback": false,
        "raw_usda_nutrients": {
          "Fiber, total dietary (g)": 6.14,
          "Total Sugars (g)": 28.86
        }
      }
    ],
    "meal_type": "breakfast",
    "meal_type_source": "caption_explicit",
    "total_calories": 210.04,
    "total_protein_g": 2.57,
    "total_carbs_g": 53.81,
    "total_fat_g": 0.78,
    "aggregated_nutrients": {
      "Fiber, total dietary (g)": 6.14,
      "Total Sugars (g)": 28.86
    },
    "confidence_score": 1.0,
    "warnings": []
  }
  ```

---

### 3.2 Confirm & Persist Meal Log
* **HTTP Method**: `POST`
* **Path**: `/api/v1/meals/confirm`
* **Auth Required**: Yes (`Bearer Token`)
* **Description**: Atomically commits a user-reviewed meal log and item breakdown into database via single-query CTE.
* **Request Body** (`MealConfirmRequest`):
  ```json
  {
    "meal_type": "breakfast",
    "user_caption": "2 bananas breakfast",
    "image_url": "https://example.com/food.jpg",
    "items": [
      {
        "food_name": "Banana",
        "fdc_id": 2012128,
        "portion_amount": 2.0,
        "portion_unit": "medium banana",
        "gram_weight": 236.0,
        "calories": 210.04,
        "protein_g": 2.57,
        "carbs_g": 53.81,
        "fat_g": 0.78,
        "is_fallback": false,
        "raw_usda_nutrients": {}
      }
    ]
  }
  ```
* **Response** (`MealConfirmResponse` - `201 Created`):
  ```json
  {
    "meal_id": "c1f7b8e0-1234-4567-89ab-cdef01234567",
    "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "logged_at": "2026-08-25 10:30:00+00",
    "meal_type": "breakfast",
    "total_calories": 210.04,
    "total_protein_g": 2.57,
    "total_carbs_g": 53.81,
    "total_fat_g": 0.78,
    "item_count": 1
  }
  ```

---

## 4. Conversational AI Chatbot & History (`/api/v1/chat`)

### 4.1 Real-Time SSE Stream Chatbot
* **HTTP Method**: `POST`
* **Path**: `/api/v1/chat`
* **Auth Required**: Yes (`Bearer Token`)
* **Response Media Type**: `text/event-stream`
* **Description**: Connects client to LangGraph Workflow 2 Agent via Server-Sent Events (SSE). Performs instant header flush (<10ms TTFT) and streams status and assistant tokens.
* **Request Body** (`ChatRequest`):
  ```json
  {
    "message": "I ate 300g chicken biryani for lunch",
    "conversation_id": "optional-session-uuid",
    "client_timezone": "Asia/Karachi"
  }
  ```
* **SSE Event Output Format**:
  ```http
  event: status
  data: {"status": "processing_prompt", "message": "Analyzing prompt and loading session memory..."}

  event: message
  data: {"content": "I have logged your "}

  event: message
  data: {"content": "Chicken Biryani (300g)."}

  event: done
  data: {"conversation_id": "optional-session-uuid", "status": "completed"}
  ```

---

### 4.2 List User Chat Sessions
* **HTTP Method**: `GET`
* **Path**: `/api/v1/chat/sessions`
* **Auth Required**: Yes (`Bearer Token`)
* **Description**: Retrieves all conversation sessions for the authenticated user.
* **Response** (`List[ChatSessionResponse]` - `200 OK`):
  ```json
  [
    {
      "id": "c1f7b8e0-1234-4567-89ab-cdef01234567",
      "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "title": "Lunch Logging: Chicken Biryani",
      "created_at": "2026-08-25 10:00:00+00",
      "updated_at": "2026-08-25 10:05:00+00",
      "message_count": 4
    }
  ]
  ```

---

### 4.3 Create Chat Session
* **HTTP Method**: `POST`
* **Path**: `/api/v1/chat/sessions`
* **Auth Required**: Yes (`Bearer Token`)
* **Request Body** (`CreateSessionRequest`):
  ```json
  {
    "title": "Custom Session Title"
  }
  ```
* **Response** (`ChatSessionResponse` - `201 Created`).

---

### 4.4 Get Messages for a Session
* **HTTP Method**: `GET`
* **Path**: `/api/v1/chat/sessions/{session_id}/messages`
* **Auth Required**: Yes (`Bearer Token`)
* **Response** (`List[ChatMessageResponse]` - `200 OK`):
  ```json
  [
    {
      "id": "m1f7b8e0-1234-4567-89ab-cdef01234567",
      "session_id": "c1f7b8e0-1234-4567-89ab-cdef01234567",
      "role": "user",
      "content": "I ate 300g chicken biryani for lunch",
      "created_at": "2026-08-25 10:00:00+00"
    },
    {
      "id": "m2f7b8e0-1234-4567-89ab-cdef01234567",
      "session_id": "c1f7b8e0-1234-4567-89ab-cdef01234567",
      "role": "assistant",
      "content": "Logged 300g Chicken Biryani (480 kcal, 28g protein).",
      "created_at": "2026-08-25 10:00:05+00"
    }
  ]
  ```

---

### 4.5 Delete Chat Session
* **HTTP Method**: `DELETE`
* **Path**: `/api/v1/chat/sessions/{session_id}`
* **Auth Required**: Yes (`Bearer Token`)
* **Response** (`200 OK`): `{"status": "deleted", "session_id": "uuid"}`

---

## 5. Dashboard & Analytics (`/api/v1/dashboard`)

### 5.1 Daily Dashboard Summary
* **HTTP Method**: `GET`
* **Path**: `/api/v1/dashboard/daily`
* **Query Parameters**:
  * `target_date`: (Optional `YYYY-MM-DD`, defaults to today)
* **Auth Required**: Yes (`Bearer Token`)
* **Response** (`DailyDashboardResponse` - `200 OK`):
  ```json
  {
    "date": "2026-08-25",
    "target_calories": 2400.0,
    "consumed_calories": 1872.0,
    "remaining_calories": 528.0,
    "protein": {
      "target": 180.0,
      "consumed": 75.0,
      "remaining": 105.0
    },
    "carbs": {
      "target": 250.0,
      "consumed": 243.6,
      "remaining": 6.4
    },
    "fat": {
      "target": 70.0,
      "consumed": 37.5,
      "remaining": 32.5
    },
    "meals": [
      {
        "meal_id": "c1f7b8e0-1234-4567-89ab-cdef01234567",
        "meal_type": "snack",
        "user_caption": "Banana Snack",
        "image_url": "https://example.com/banana.jpg",
        "calories": 1872.0,
        "protein_g": 75.0,
        "carbs_g": 243.6,
        "fat_g": 37.5,
        "logged_at": "2026-08-25 15:30:00+00"
      }
    ],
    "top_micronutrients": {
      "Fiber, total dietary (g)": 37.2,
      "Calcium, Ca (mg)": 750.0
    }
  }
  ```

---

### 5.2 Historical Analytics Breakdown
* **HTTP Method**: `GET`
* **Path**: `/api/v1/dashboard/history`
* **Query Parameters**:
  * `days`: (Integer `1-365`, default: `30`)
* **Auth Required**: Yes (`Bearer Token`)
* **Response** (`HistoricalAnalyticsResponse` - `200 OK`):
  ```json
  {
    "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "total_days_logged": 1,
    "history": [
      {
        "date": "2026-08-25",
        "meal_count": 1,
        "total_calories": 1872.0,
        "target_calories": 2400.0,
        "total_protein_g": 75.0,
        "target_protein_g": 180.0,
        "total_carbs_g": 243.6,
        "target_carbs_g": 250.0,
        "total_fat_g": 37.5,
        "target_fat_g": 70.0,
        "goal_status": "under"
      }
    ]
  }
  ```

---

## 6. User Profile Management (`/api/v1/profile`)

### 6.1 Get Profile & Macro Targets
* **HTTP Method**: `GET`
* **Path**: `/api/v1/profile`
* **Auth Required**: Yes (`Bearer Token`)
* **Response** (`UserProfileResponse` - `200 OK`):
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "display_name": "Alex Morgan",
    "height_cm": 178.0,
    "weight_kg": 75.0,
    "age": 28,
    "gender": "male",
    "activity_level": "moderate",
    "primary_goal": "muscle_gain",
    "bmr": 1720.0,
    "tdee": 2666.0,
    "target_calories": 2400.0,
    "target_protein_g": 180.0,
    "target_carbs_g": 250.0,
    "target_fat_g": 70.0,
    "target_micronutrients": {}
  }
  ```

---

### 6.2 Update Profile & Re-calculate BMR/TDEE
* **HTTP Method**: `PUT`
* **Path**: `/api/v1/profile`
* **Auth Required**: Yes (`Bearer Token`)
* **Request Body** (`UserProfileUpdate`):
  ```json
  {
    "display_name": "Alex Morgan",
    "height_cm": 180.0,
    "weight_kg": 77.0,
    "age": 29,
    "gender": "male",
    "activity_level": "active",
    "primary_goal": "muscle_gain"
  }
  ```
* **Response** (`UserProfileResponse` - `200 OK`).
