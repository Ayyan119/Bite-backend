"""Authentication and Development Token Generator Router."""

import logging
import time
import uuid
from uuid import UUID

import jwt
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import ORJSONResponse
from psycopg.rows import dict_row

from app.api.deps import get_jwt_secret
from app.core.security import hash_password, verify_password
from app.db.connection import get_db_connection
from app.schemas.auth import (
    AuthResponse,
    DevTokenRequest,
    DevTokenResponse,
    LoginRequest,
    RegisterRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_deterministic_user_id(email: str) -> UUID:
    """Generates a consistent, deterministic UUIDv5 based on user email address."""
    clean_email = email.strip().lower()
    return uuid.uuid5(uuid.NAMESPACE_DNS, clean_email)


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    response_class=ORJSONResponse,
)
async def login_user(payload: LoginRequest) -> AuthResponse:
    """Authenticates an existing user with email & password and returns a signed Supabase Bearer JWT token."""
    clean_email = payload.email.strip().lower()
    target_user_id = get_deterministic_user_id(clean_email)

    now = int(time.time())
    expires_in = 86400  # 24 hours validity

    display_name = clean_email.split("@")[0].replace(".", " ").title()
    age = None
    height_cm = None
    weight_kg = None
    gender = None
    bmr = None
    tdee = None
    target_calories = None

    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # Check if profile exists
                await cur.execute(
                    """
                    SELECT id, email, display_name, age, height_cm, weight_kg, gender,
                           bmr, tdee, target_calories, password_hash
                    FROM public.profiles
                    WHERE id = %s OR email = %s;
                    """,
                    (str(target_user_id), clean_email),
                )
                existing = await cur.fetchone()

                if not existing:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User account not found. Please sign up first.",
                    )

                stored_pwd = existing.get("password_hash")
                if stored_pwd and payload.password:
                    if not verify_password(payload.password, stored_pwd):
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect password. Please check your credentials.",
                        )

                display_name = existing.get("display_name") or display_name
                age = existing.get("age")
                height_cm = (
                    float(existing["height_cm"])
                    if existing.get("height_cm") is not None
                    else None
                )
                weight_kg = (
                    float(existing["weight_kg"])
                    if existing.get("weight_kg") is not None
                    else None
                )
                gender = existing.get("gender")
                bmr = (
                    float(existing["bmr"]) if existing.get("bmr") is not None else None
                )
                tdee = (
                    float(existing["tdee"])
                    if existing.get("tdee") is not None
                    else None
                )
                target_calories = (
                    float(existing["target_calories"])
                    if existing.get("target_calories") is not None
                    else None
                )
    except HTTPException:
        raise
    except Exception as err:
        logger.warning(f"Database error during login profile lookup: {err}")

    secret = get_jwt_secret()
    jwt_payload = {
        "sub": str(target_user_id),
        "email": clean_email,
        "role": "authenticated",
        "iat": now,
        "exp": now + expires_in,
    }
    signed_jwt = jwt.encode(jwt_payload, secret, algorithm="HS256")

    return AuthResponse(
        access_token=signed_jwt,
        token_type="bearer",
        expires_in=expires_in,
        user_id=target_user_id,
        email=clean_email,
        display_name=display_name,
        age=age,
        height_cm=height_cm,
        weight_kg=weight_kg,
        gender=gender,
        bmr=bmr,
        tdee=tdee,
        target_calories=target_calories,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    response_class=ORJSONResponse,
)
async def register_user(payload: RegisterRequest) -> AuthResponse:
    """Registers a new user and persists their health profile and goals."""
    from app.api.v1.endpoints.profile import calculate_bmr_and_tdee

    clean_email = payload.email.strip().lower()
    target_user_id = get_deterministic_user_id(clean_email)

    now = int(time.time())
    expires_in = 86400

    # Reject registration if user already exists
    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id FROM public.profiles
                    WHERE id = %s OR email = %s;
                    """,
                    (str(target_user_id), clean_email),
                )
                existing = await cur.fetchone()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="An account with this email address already exists. Please log in instead.",
                    )
    except HTTPException:
        raise
    except Exception as err:
        logger.warning(f"Database error checking existing registration: {err}")

    disp_name = (
        payload.display_name or clean_email.split("@")[0].replace(".", " ").title()
    )

    # Optional BMR and TDEE calculation if user provides physical details
    bmr, tdee = calculate_bmr_and_tdee(
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        age=payload.age,
        gender=payload.gender,
        activity_level=payload.activity_level or "moderate",
    )

    target_calories = None
    target_protein = None
    target_carbs = None
    target_fat = None

    if tdee is not None:
        goal_clean = (payload.primary_goal or "maintenance").strip().lower()
        if goal_clean == "weight_loss":
            target_calories = round(tdee - 500.0, 2)
        elif goal_clean == "muscle_gain":
            target_calories = round(tdee + 300.0, 2)
        else:
            target_calories = round(tdee, 2)

        # Standard macro splits based on calculated target
        target_protein = round((target_calories * 0.30) / 4.0, 2)
        target_carbs = round((target_calories * 0.40) / 4.0, 2)
        target_fat = round((target_calories * 0.30) / 9.0, 2)

    hashed_pwd = hash_password(payload.password) if payload.password else None

    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO public.profiles (
                        id, email, display_name, height_cm, weight_kg, age, gender,
                        activity_level, primary_goal, bmr, tdee, target_calories,
                        target_protein_g, target_carbs_g, target_fat_g, password_hash, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
                    """,
                    (
                        str(target_user_id),
                        clean_email,
                        disp_name,
                        payload.height_cm,
                        payload.weight_kg,
                        payload.age,
                        payload.gender,
                        payload.activity_level,
                        payload.primary_goal,
                        bmr,
                        tdee,
                        target_calories,
                        target_protein,
                        target_carbs,
                        target_fat,
                        hashed_pwd,
                    ),
                )
    except Exception as err:
        logger.exception(f"Database error during registration: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register user: {str(err)}",
        )

    secret = get_jwt_secret()
    jwt_payload = {
        "sub": str(target_user_id),
        "email": clean_email,
        "role": "authenticated",
        "iat": now,
        "exp": now + expires_in,
    }
    signed_jwt = jwt.encode(jwt_payload, secret, algorithm="HS256")

    return AuthResponse(
        access_token=signed_jwt,
        token_type="bearer",
        expires_in=expires_in,
        user_id=target_user_id,
        email=clean_email,
        display_name=disp_name,
        age=payload.age,
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        gender=payload.gender,
        bmr=bmr,
        tdee=tdee,
        target_calories=target_calories,
    )


@router.post(
    "/dev-token",
    response_model=DevTokenResponse,
    status_code=status.HTTP_200_OK,
    response_class=ORJSONResponse,
)
async def generate_dev_token(
    payload: DevTokenRequest = DevTokenRequest(),
) -> DevTokenResponse:
    """Generate a valid, signed Supabase Bearer JWT token for local API testing in Swagger UI.

    No password required for development testing.
    """
    if payload.user_id:
        try:
            target_user_id = UUID(payload.user_id.strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provided user_id is not a valid UUID string.",
            )
    else:
        email_clean = (payload.email or "alex.morgan@bite.app").strip().lower()
        target_user_id = get_deterministic_user_id(email_clean)

    now = int(time.time())
    expires_in = 86400  # 24 hours validity

    email_str = (payload.email or "alex.morgan@bite.app").strip().lower()
    jwt_payload = {
        "sub": str(target_user_id),
        "email": email_str,
        "role": "authenticated",
        "iat": now,
        "exp": now + expires_in,
    }

    secret = get_jwt_secret()
    signed_jwt = jwt.encode(jwt_payload, secret, algorithm="HS256")

    disp_name = (
        "Alex Morgan" if "alex" in email_str else email_str.split("@")[0].title()
    )

    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO public.profiles (
                        id, email, display_name, height_cm, weight_kg, age, gender,
                        activity_level, primary_goal, target_calories, target_protein_g, target_carbs_g, target_fat_g
                    )
                    VALUES (%s, %s, %s, 178.0, 75.0, 28, 'male', 'moderate', 'muscle_gain', 2400.0, 180.0, 250.0, 70.0)
                    ON CONFLICT (id) DO UPDATE SET
                        email = EXCLUDED.email,
                        display_name = COALESCE(public.profiles.display_name, EXCLUDED.display_name),
                        height_cm = COALESCE(public.profiles.height_cm, EXCLUDED.height_cm),
                        weight_kg = COALESCE(public.profiles.weight_kg, EXCLUDED.weight_kg),
                        age = COALESCE(public.profiles.age, EXCLUDED.age),
                        gender = COALESCE(public.profiles.gender, EXCLUDED.gender);
                    """,
                    (str(target_user_id), email_str, disp_name),
                )
    except Exception as err:
        logger.warning(f"Failed to auto-create profile row for dev token: {err}")

    return DevTokenResponse(
        access_token=signed_jwt,
        token_type="bearer",
        expires_in=expires_in,
        user_id=target_user_id,
        email=email_str,
        display_name=disp_name,
    )
