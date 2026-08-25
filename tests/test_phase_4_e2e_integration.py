"""End-to-End (E2E) Integration Test Suite for Phase 4 FastAPI Application Layer.

Simulates a complete user journey across authentication, profile configuration, food vision analysis,
single-query CTE meal persistence, daily dashboard analytics, and conversational agent SSE streaming.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
import io

from app.api.deps import clear_claims_cache
from app.main import app
from tests.test_api_auth import create_test_jwt


@pytest.fixture(autouse=True)
def cleanup_cache():
    clear_claims_cache()
    yield
    clear_claims_cache()


def create_sample_image_bytes(width: int = 1200, height: int = 900) -> bytes:
    """Generate sample JPEG image buffer."""
    img = Image.new("RGB", (width, height), color="green")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_full_phase_4_e2e_user_journey():
    """Verify complete end-to-end user lifecycle across all Phase 4 endpoints."""
    test_user_id = str(uuid4())
    generated_meal_id = uuid4()
    token = create_test_jwt(user_id=test_user_id, email="e2e_user@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Step 1: Liveness & Readiness Probes
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"
        assert "X-Process-Time" in health_resp.headers

        # Step 2: Configure User Profile & Calculate BMR/TDEE (PUT /api/v1/profile)
        profile_update_payload = {
            "display_name": "E2E Test User",
            "height_cm": 175.0,
            "weight_kg": 75.0,
            "age": 28,
            "gender": "male",
            "activity_level": "moderate",
            "primary_goal": "weight_loss",
            "target_micronutrients": {"Protein (g)": 160.0},
        }

        mock_profile_row = (
            test_user_id,
            "E2E Test User",
            175.0,
            75.0,
            28,
            "male",
            "moderate",
            "weight_loss",
            1718.75,
            2664.06,
            2164.06,
            160.0,
            200.0,
            65.0,
            '{"Protein (g)": 160.0}',
        )

        mock_cur = AsyncMock()
        mock_cur.fetchone.return_value = mock_profile_row
        mock_cur_cm = AsyncMock()
        mock_cur_cm.__aenter__.return_value = mock_cur
        mock_cur_cm.__aexit__.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur_cm
        mock_conn_cm = AsyncMock()
        mock_conn_cm.__aenter__.return_value = mock_conn
        mock_conn_cm.__aexit__.return_value = None

        with patch(
            "app.api.v1.endpoints.profile.get_db_connection", return_value=mock_conn_cm
        ):
            prof_resp = await client.put(
                "/api/v1/profile", json=profile_update_payload, headers=headers
            )
            assert prof_resp.status_code == 200
            prof_data = prof_resp.json()
            assert prof_data["id"] == test_user_id
            assert prof_data["bmr"] == 1718.75
            assert prof_data["target_calories"] == 2164.06

        # Step 3: Analyze Meal Image (POST /api/v1/meals/analyze)
        sample_img_bytes = create_sample_image_bytes()
        mock_graph_output = {
            "reconciled_items": [
                {
                    "food_name": "Avocado Toast",
                    "fdc_id": 171706,
                    "portion_amount": 1.0,
                    "portion_unit": "slice",
                    "gram_weight": 120.0,
                    "calories": 250.0,
                    "protein_g": 6.0,
                    "carbs_g": 24.0,
                    "fat_g": 15.0,
                    "is_fallback": False,
                    "raw_usda_nutrients": {"Potassium (mg)": 350.0},
                }
            ],
            "total_calories": 250.0,
            "total_protein_g": 6.0,
            "total_carbs_g": 24.0,
            "total_fat_g": 15.0,
            "aggregated_nutrients": {"Potassium (mg)": 350.0},
            "vision_confidence": 0.96,
            "errors": [],
        }

        with patch(
            "app.api.v1.endpoints.meals.ingestion_graph.ainvoke",
            new_callable=AsyncMock,
            return_value=mock_graph_output,
        ):
            files = {"file": ("avocado_toast.jpg", sample_img_bytes, "image/jpeg")}
            analyze_resp = await client.post(
                "/api/v1/meals/analyze", files=files, headers=headers
            )
            assert analyze_resp.status_code == 200
            analyze_data = analyze_resp.json()
            assert analyze_data["total_calories"] == 250.0
            assert len(analyze_data["detected_items"]) == 1

        # Step 4: Atomically Confirm Meal (POST /api/v1/meals/confirm)
        confirm_payload = {
            "meal_type": "breakfast",
            "user_caption": "Avocado toast breakfast",
            "image_url": "https://example.com/toast.jpg",
            "items": [
                {
                    "food_name": "Avocado Toast",
                    "fdc_id": 171706,
                    "portion_amount": 1.0,
                    "portion_unit": "slice",
                    "gram_weight": 120.0,
                    "calories": 250.0,
                    "protein_g": 6.0,
                    "carbs_g": 24.0,
                    "fat_g": 15.0,
                    "is_fallback": False,
                    "raw_usda_nutrients": {"Potassium (mg)": 350.0},
                }
            ],
        }

        mock_cur_confirm = AsyncMock()
        mock_cur_confirm.fetchone.return_value = (
            generated_meal_id,
            "2026-08-24 19:24:00+00",
        )
        mock_cur_cm_confirm = AsyncMock()
        mock_cur_cm_confirm.__aenter__.return_value = mock_cur_confirm
        mock_cur_cm_confirm.__aexit__.return_value = None
        mock_conn_confirm = MagicMock()
        mock_conn_confirm.cursor.return_value = mock_cur_cm_confirm
        mock_conn_cm_confirm = AsyncMock()
        mock_conn_cm_confirm.__aenter__.return_value = mock_conn_confirm
        mock_conn_cm_confirm.__aexit__.return_value = None

        with patch(
            "app.api.v1.endpoints.meals.get_db_connection",
            return_value=mock_conn_cm_confirm,
        ):
            confirm_resp = await client.post(
                "/api/v1/meals/confirm", json=confirm_payload, headers=headers
            )
            assert confirm_resp.status_code == 201
            confirm_data = confirm_resp.json()
            assert confirm_data["meal_id"] == str(generated_meal_id)
            assert confirm_data["item_count"] == 1

        # Step 5: Fetch Daily Dashboard Analytics (GET /api/v1/dashboard/daily)
        mock_cur_dash = AsyncMock()
        mock_cur_dash.fetchone.return_value = (2164.06, 160.0, 200.0, 65.0)
        mock_cur_dash.fetchall.return_value = [
            (
                generated_meal_id,
                "breakfast",
                "Avocado toast breakfast",
                "https://example.com/toast.jpg",
                250.0,
                6.0,
                24.0,
                15.0,
                '{"Potassium (mg)": 350.0}',
                "2026-08-24 19:24:00+00",
            )
        ]
        mock_cur_cm_dash = AsyncMock()
        mock_cur_cm_dash.__aenter__.return_value = mock_cur_dash
        mock_cur_cm_dash.__aexit__.return_value = None
        mock_conn_dash = MagicMock()
        mock_conn_dash.cursor.return_value = mock_cur_cm_dash
        mock_conn_cm_dash = AsyncMock()
        mock_conn_cm_dash.__aenter__.return_value = mock_conn_dash
        mock_conn_cm_dash.__aexit__.return_value = None

        with patch(
            "app.api.v1.endpoints.dashboard.get_db_connection",
            return_value=mock_conn_cm_dash,
        ):
            dash_resp = await client.get(
                "/api/v1/dashboard/daily?target_date=2026-08-24", headers=headers
            )
            assert dash_resp.status_code == 200
            dash_data = dash_resp.json()
            assert dash_data["consumed_calories"] == 250.0
            assert dash_data["remaining_calories"] == 1914.06
            assert len(dash_data["meals"]) == 1

        # Step 6: Chatbot Real-Time SSE Stream (POST /api/v1/chat)
        async def mock_stream_gen(
            user_input: str, user_id: str, thread_id: str, *args, **kwargs
        ):
            yield 'event: status\ndata: {"status": "processing", "message": "Analyzing..."}\n\n'
            yield 'event: message\ndata: {"content": "Logged 1 Avocado Toast (250 kcal)!"}\n\n'

        with patch(
            "app.api.v1.endpoints.chat.stream_chatbot_response",
            side_effect=mock_stream_gen,
        ):
            chat_resp = await client.post(
                "/api/v1/chat",
                json={"message": "What did I eat today?"},
                headers=headers,
            )
            assert chat_resp.status_code == 200
            assert "text/event-stream" in chat_resp.headers.get("content-type", "")
            assert "Logged 1 Avocado Toast" in chat_resp.text
            assert "event: done" in chat_resp.text
