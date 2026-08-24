"""Unit tests for Daily Dashboard Analytics endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import clear_claims_cache
from app.main import app
from tests.test_api_auth import create_test_jwt


@pytest.fixture(autouse=True)
def cleanup_cache():
    clear_claims_cache()
    yield
    clear_claims_cache()


@pytest.mark.asyncio
async def test_dashboard_endpoint_unauthorized():
    """Verify 401 response when dashboard endpoint is called without JWT auth header."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/dashboard/daily")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_endpoint_invalid_date_format():
    """Verify 400 response when target_date is not YYYY-MM-DD format."""
    token = create_test_jwt()
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/api/v1/dashboard/daily?target_date=2026/08/24", headers=headers
        )
        assert response.status_code == 400
        assert "error" in response.json()
        assert "Invalid target_date format" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_dashboard_endpoint_success():
    """Verify GET /api/v1/dashboard/daily returns macro budget, meal cards, and micronutrients."""
    test_user_id = str(uuid4())
    token = create_test_jwt(user_id=test_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    mock_profile_row = (2200.0, 160.0, 220.0, 70.0)
    mock_meal_rows = [
        (
            uuid4(),
            "breakfast",
            "Oatmeal & Berries",
            "https://example.com/oats.jpg",
            350.0,
            12.0,
            60.0,
            6.0,
            '{"Iron (mg)": 3.2, "Calcium (mg)": 80.0}',
            "2026-08-24 08:30:00+00",
        ),
        (
            uuid4(),
            "lunch",
            "Chicken & Rice",
            "https://example.com/chicken.jpg",
            650.0,
            50.0,
            75.0,
            14.0,
            '{"Iron (mg)": 1.8, "Calcium (mg)": 40.0, "Vitamin C (mg)": 15.0}',
            "2026-08-24 13:00:00+00",
        ),
    ]

    mock_cursor = AsyncMock()
    mock_cursor.fetchone.return_value = mock_profile_row
    mock_cursor.fetchall.return_value = mock_meal_rows

    mock_cursor_cm = AsyncMock()
    mock_cursor_cm.__aenter__.return_value = mock_cursor
    mock_cursor_cm.__aexit__.return_value = None

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor_cm

    mock_conn_cm = AsyncMock()
    mock_conn_cm.__aenter__.return_value = mock_conn
    mock_conn_cm.__aexit__.return_value = None

    with patch(
        "app.api.v1.endpoints.dashboard.get_db_connection", return_value=mock_conn_cm
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/api/v1/dashboard/daily?target_date=2026-08-24", headers=headers
            )
            assert response.status_code == 200
            data = response.json()

            assert data["date"] == "2026-08-24"
            assert data["target_calories"] == 2200.0
            assert data["consumed_calories"] == 1000.0
            assert data["remaining_calories"] == 1200.0

            assert data["protein"]["target"] == 160.0
            assert data["protein"]["consumed"] == 62.0
            assert data["protein"]["remaining"] == 98.0

            assert len(data["meals"]) == 2
            assert data["meals"][0]["meal_type"] == "breakfast"
            assert data["meals"][1]["meal_type"] == "lunch"

            assert data["top_micronutrients"]["Iron (mg)"] == 5.0
            assert data["top_micronutrients"]["Calcium (mg)"] == 120.0
            assert data["top_micronutrients"]["Vitamin C (mg)"] == 15.0
