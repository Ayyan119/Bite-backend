"""Unit tests for Food Vision Analyze endpoint and image compression guard."""

from unittest.mock import AsyncMock, patch
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
