"""Unit tests for User Profile CRUD and BMR/TDEE calculation endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import clear_claims_cache
from app.api.v1.endpoints.profile import calculate_bmr_and_tdee
from app.main import app
from tests.test_api_auth import create_test_jwt


@pytest.fixture(autouse=True)
def cleanup_cache():
    clear_claims_cache()
    yield
    clear_claims_cache()


def test_calculate_bmr_and_tdee_formula():
    """Verify BMR and TDEE calculation via Mifflin-St Jeor equation."""
    # Male: 180cm, 80kg, 25 years old, moderate activity (1.55)
    # BMR = 10*80 + 6.25*180 - 5*25 + 5 = 800 + 1125 - 125 + 5 = 1805.0
    # TDEE = 1805.0 * 1.55 = 2797.75
    bmr, tdee = calculate_bmr_and_tdee(
        height_cm=180.0,
        weight_kg=80.0,
        age=25,
        gender="male",
        activity_level="moderate",
    )
    assert bmr == 1805.0
    assert tdee == 2797.75

    # Female: 165cm, 60kg, 30 years old, light activity (1.375)
    # BMR = 10*60 + 6.25*165 - 5*30 - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
    # TDEE = 1320.25 * 1.375 = 1815.34
    bmr_f, tdee_f = calculate_bmr_and_tdee(
        height_cm=165.0, weight_kg=60.0, age=30, gender="female", activity_level="light"
    )
    assert bmr_f == 1320.25
    assert tdee_f == 1815.34


@pytest.mark.asyncio
async def test_get_profile_unauthorized():
    """Verify 401 response when GET /api/v1/profile is called without auth."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/profile")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_profile_success():
    """Verify GET /api/v1/profile returns user profile targets."""
    test_user_id = str(uuid4())
    token = create_test_jwt(user_id=test_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    mock_row = (
        test_user_id,
        "John Doe",
        180.0,
        80.0,
        25,
        "male",
        "moderate",
        "weight_loss",
        1805.0,
        2797.75,
        2297.75,
        180.0,
        220.0,
        70.0,
        '{"Vitamin D (IU)": 600.0}',
    )

    mock_cursor = AsyncMock()
    mock_cursor.fetchone.return_value = mock_row

    mock_cursor_cm = AsyncMock()
    mock_cursor_cm.__aenter__.return_value = mock_cursor
    mock_cursor_cm.__aexit__.return_value = None

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor_cm

    mock_conn_cm = AsyncMock()
    mock_conn_cm.__aenter__.return_value = mock_conn
    mock_conn_cm.__aexit__.return_value = None

    with patch(
        "app.api.v1.endpoints.profile.get_db_connection", return_value=mock_conn_cm
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/api/v1/profile", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == test_user_id
            assert data["display_name"] == "John Doe"
            assert data["bmr"] == 1805.0
            assert data["tdee"] == 2797.75
            assert data["target_calories"] == 2297.75


@pytest.mark.asyncio
async def test_update_profile_success():
    """Verify PUT /api/v1/profile UPSERTs profile targets and auto-calculates BMR/TDEE."""
    test_user_id = str(uuid4())
    token = create_test_jwt(user_id=test_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "display_name": "Jane Smith",
        "height_cm": 165.0,
        "weight_kg": 60.0,
        "age": 30,
        "gender": "female",
        "activity_level": "light",
        "primary_goal": "weight_loss",
        "target_micronutrients": {"Iron (mg)": 18.0},
    }

    # Auto TDEE = 1815.34 -> Goal weight_loss = 1815.34 - 500 = 1315.34
    mock_returned_row = (
        test_user_id,
        "Jane Smith",
        165.0,
        60.0,
        30,
        "female",
        "light",
        "weight_loss",
        1320.25,
        1815.34,
        1315.34,
        150.0,
        200.0,
        65.0,
        '{"Iron (mg)": 18.0}',
    )

    mock_cursor = AsyncMock()
    mock_cursor.fetchone.return_value = mock_returned_row

    mock_cursor_cm = AsyncMock()
    mock_cursor_cm.__aenter__.return_value = mock_cursor
    mock_cursor_cm.__aexit__.return_value = None

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor_cm

    mock_conn_cm = AsyncMock()
    mock_conn_cm.__aenter__.return_value = mock_conn
    mock_conn_cm.__aexit__.return_value = None

    with patch(
        "app.api.v1.endpoints.profile.get_db_connection", return_value=mock_conn_cm
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.put(
                "/api/v1/profile", json=update_payload, headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == test_user_id
            assert data["display_name"] == "Jane Smith"
            assert data["bmr"] == 1320.25
            assert data["tdee"] == 1815.34
            assert data["target_calories"] == 1315.34
            assert data["target_micronutrients"]["Iron (mg)"] == 18.0
