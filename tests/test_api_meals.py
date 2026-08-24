"""Unit tests for Food Vision Analyze & Single-Query CTE Confirm endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
import io

from app.api.deps import clear_claims_cache
from app.api.v1.endpoints.meals import compress_and_downscale_image
from app.main import app
from tests.test_api_auth import create_test_jwt


@pytest.fixture(autouse=True)
def cleanup_cache():
    clear_claims_cache()
    yield
    clear_claims_cache()


def create_sample_image_bytes(width: int = 2000, height: int = 1500) -> bytes:
    """Generate a sample JPEG image buffer for testing compression."""
    img = Image.new("RGB", (width, height), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_compress_and_downscale_image():
    """Verify compress_and_downscale_image resizes oversized image to max 1024x1024."""
    original_bytes = create_sample_image_bytes(2000, 1500)
    compressed_bytes = compress_and_downscale_image(
        original_bytes, max_dim=1024, quality=80
    )

    assert len(compressed_bytes) > 0
    assert len(compressed_bytes) <= len(original_bytes)

    with Image.open(io.BytesIO(compressed_bytes)) as img:
        width, height = img.size
        assert max(width, height) <= 1024


@pytest.mark.asyncio
async def test_analyze_meal_unauthorized():
    """Verify 401 response when analyze endpoint is called without JWT auth header."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post("/api/v1/meals/analyze", json={})
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_analyze_meal_json_payload_success():
    """Verify POST /api/v1/meals/analyze with valid JSON payload."""
    test_user_id = str(uuid4())
    token = create_test_jwt(user_id=test_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    mock_graph_output = {
        "reconciled_items": [
            {
                "food_name": "Grilled Chicken Breast",
                "fdc_id": 171077,
                "portion_amount": 1.5,
                "portion_unit": "serving",
                "gram_weight": 150.0,
                "calories": 247.5,
                "protein_g": 46.5,
                "carbs_g": 0.0,
                "fat_g": 5.4,
                "is_fallback": False,
                "raw_usda_nutrients": {},
            }
        ],
        "total_calories": 247.5,
        "total_protein_g": 46.5,
        "total_carbs_g": 0.0,
        "total_fat_g": 5.4,
        "aggregated_nutrients": {"Calcium (mg)": 20.0},
        "vision_confidence": 0.95,
        "errors": [],
    }

    with patch(
        "app.api.v1.endpoints.meals.ingestion_graph.ainvoke", new_callable=AsyncMock
    ) as mock_graph:
        mock_graph.return_value = mock_graph_output

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            payload = {
                "image_url": "https://example.com/meal.jpg",
                "user_caption": "Grilled chicken breast lunch",
                "meal_type": "lunch",
            }
            response = await client.post(
                "/api/v1/meals/analyze", json=payload, headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total_calories"] == 247.5
            assert data["total_protein_g"] == 46.5
            assert len(data["detected_items"]) == 1
            assert data["detected_items"][0]["food_name"] == "Grilled Chicken Breast"


@pytest.mark.asyncio
async def test_analyze_meal_file_upload_success():
    """Verify POST /api/v1/meals/analyze with multipart image file upload."""
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    sample_bytes = create_sample_image_bytes(1200, 900)

    mock_graph_output = {
        "reconciled_items": [
            {
                "food_name": "Steamed Broccoli",
                "fdc_id": 170379,
                "portion_amount": 1.0,
                "portion_unit": "cup",
                "gram_weight": 100.0,
                "calories": 34.0,
                "protein_g": 2.8,
                "carbs_g": 7.0,
                "fat_g": 0.4,
                "is_fallback": False,
                "raw_usda_nutrients": {},
            }
        ],
        "total_calories": 34.0,
        "total_protein_g": 2.8,
        "total_carbs_g": 7.0,
        "total_fat_g": 0.4,
        "aggregated_nutrients": {"Vitamin C (mg)": 89.2},
        "vision_confidence": 0.98,
        "errors": [],
    }

    with patch(
        "app.api.v1.endpoints.meals.ingestion_graph.ainvoke", new_callable=AsyncMock
    ) as mock_graph:
        mock_graph.return_value = mock_graph_output

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            files = {"file": ("meal.jpg", sample_bytes, "image/jpeg")}
            response = await client.post(
                "/api/v1/meals/analyze", files=files, headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total_calories"] == 34.0
            assert data["detected_items"][0]["food_name"] == "Steamed Broccoli"


@pytest.mark.asyncio
async def test_confirm_meal_unauthorized():
    """Verify 401 response when confirm endpoint is called without JWT auth header."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post("/api/v1/meals/confirm", json={"items": []})
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_confirm_meal_empty_items_validation():
    """Verify 400 response when items list is empty."""
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/meals/confirm",
            json={"meal_type": "lunch", "items": []},
            headers=headers,
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "must contain at least one item" in data["error"]["message"]


@pytest.mark.asyncio
async def test_confirm_meal_single_cte_success():
    """Verify POST /api/v1/meals/confirm executes single CTE query and returns 201 Created."""
    test_user_id = str(uuid4())
    generated_meal_id = uuid4()
    token = create_test_jwt(user_id=test_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    confirm_payload = {
        "meal_type": "dinner",
        "user_caption": "Healthy dinner bowl",
        "image_url": "https://example.com/dinner.jpg",
        "items": [
            {
                "food_name": "Grilled Salmon",
                "fdc_id": 175168,
                "portion_amount": 1.0,
                "portion_unit": "fillet",
                "gram_weight": 180.0,
                "calories": 360.0,
                "protein_g": 36.0,
                "carbs_g": 0.0,
                "fat_g": 22.0,
                "is_fallback": False,
                "raw_usda_nutrients": {"Calcium (mg)": 15.0},
            },
            {
                "food_name": "Quinoa",
                "fdc_id": 168874,
                "portion_amount": 1.0,
                "portion_unit": "cup",
                "gram_weight": 185.0,
                "calories": 222.0,
                "protein_g": 8.0,
                "carbs_g": 39.0,
                "fat_g": 3.5,
                "is_fallback": False,
                "raw_usda_nutrients": {"Iron (mg)": 2.8},
            },
        ],
    }

    mock_cursor = AsyncMock()
    mock_cursor.fetchone.return_value = (generated_meal_id, "2026-08-24 18:40:00+00")

    mock_cursor_cm = AsyncMock()
    mock_cursor_cm.__aenter__.return_value = mock_cursor
    mock_cursor_cm.__aexit__.return_value = None

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor_cm

    mock_conn_cm = AsyncMock()
    mock_conn_cm.__aenter__.return_value = mock_conn
    mock_conn_cm.__aexit__.return_value = None

    with patch(
        "app.api.v1.endpoints.meals.get_db_connection", return_value=mock_conn_cm
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/api/v1/meals/confirm", json=confirm_payload, headers=headers
            )
            assert response.status_code == 201
            data = response.json()
            assert data["meal_id"] == str(generated_meal_id)
            assert data["user_id"] == test_user_id
            assert data["meal_type"] == "dinner"
            assert data["total_calories"] == 582.0
            assert data["total_protein_g"] == 44.0
            assert data["total_carbs_g"] == 39.0
            assert data["total_fat_g"] == 25.5
            assert data["item_count"] == 2

            # Assert CTE SQL query was executed on database cursor
            assert mock_cursor.execute.called
            executed_sql = mock_cursor.execute.call_args[0][0]
            assert "WITH new_log AS" in executed_sql
            assert "jsonb_to_recordset" in executed_sql
