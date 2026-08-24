"""User Profile and Nutritional Target Management Router."""

import json
import logging
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import ORJSONResponse

from app.api.deps import get_current_user
from app.db.connection import get_db_connection
from app.schemas.auth import CurrentUser
from app.schemas.profile_api import UserProfileResponse, UserProfileUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Profile"])

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "extra": 1.9,
}


def calculate_bmr_and_tdee(
    height_cm: Optional[float],
    weight_kg: Optional[float],
    age: Optional[int],
    gender: Optional[str],
    activity_level: Optional[str] = "moderate",
) -> Tuple[Optional[float], Optional[float]]:
    """Calculate Basal Metabolic Rate (BMR) and Total Daily Energy Expenditure (TDEE) using Mifflin-St Jeor equation."""
    if not (height_cm and weight_kg and age and gender):
        return None, None

    g_clean = gender.strip().lower()
    if g_clean == "male":
        gender_offset = 5.0
    elif g_clean == "female":
        gender_offset = -161.0
    else:
        gender_offset = -78.0

    bmr = round(
        (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) + gender_offset, 2
    )
    multiplier = ACTIVITY_MULTIPLIERS.get(
        (activity_level or "moderate").strip().lower(), 1.55
    )
    tdee = round(bmr * multiplier, 2)
    return bmr, tdee


@router.get(
    "",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    response_class=ORJSONResponse,
)
async def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
) -> UserProfileResponse:
    """Fetch current user profile and target macro goals from database with zero-downtime fallback."""
    user_id_str = str(current_user.user_id)

    select_sql = """
    SELECT id, display_name, height_cm, weight_kg, age, gender,
           activity_level, primary_goal, bmr, tdee,
           target_calories, target_protein_g, target_carbs_g, target_fat_g,
           target_micronutrients
    FROM public.profiles
    WHERE id = %s;
    """

    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(select_sql, (user_id_str,))
                row = await cur.fetchone()
                if not row:
                    return UserProfileResponse(
                        id=current_user.user_id,
                        display_name=(
                            current_user.email.split("@")[0]
                            if current_user.email
                            else "User"
                        ),
                        target_calories=2000.0,
                        target_protein_g=150.0,
                        target_carbs_g=200.0,
                        target_fat_g=65.0,
                        target_micronutrients={},
                    )

                (
                    u_id,
                    d_name,
                    h_cm,
                    w_kg,
                    u_age,
                    gdr,
                    act,
                    goal,
                    bmr,
                    tdee,
                    cal,
                    prot,
                    carb,
                    fat,
                    micro_raw,
                ) = row
                micro_dict = (
                    json.loads(micro_raw)
                    if isinstance(micro_raw, str)
                    else (micro_raw or {})
                )

                return UserProfileResponse(
                    id=u_id,
                    display_name=d_name,
                    height_cm=float(h_cm) if h_cm is not None else None,
                    weight_kg=float(w_kg) if w_kg is not None else None,
                    age=int(u_age) if u_age is not None else None,
                    gender=gdr,
                    activity_level=act or "moderate",
                    primary_goal=goal or "maintenance",
                    bmr=float(bmr) if bmr is not None else None,
                    tdee=float(tdee) if tdee is not None else None,
                    target_calories=float(cal or 2000.0),
                    target_protein_g=float(prot or 150.0),
                    target_carbs_g=float(carb or 200.0),
                    target_fat_g=float(fat or 65.0),
                    target_micronutrients=micro_dict,
                )
    except HTTPException as http_err:
        if http_err.status_code == 503:
            logger.warning(
                "Database offline; returning default UserProfileResponse fallback."
            )
            return UserProfileResponse(
                id=current_user.user_id,
                display_name=(
                    current_user.email.split("@")[0] if current_user.email else "User"
                ),
                target_calories=2000.0,
                target_protein_g=150.0,
                target_carbs_g=200.0,
                target_fat_g=65.0,
                target_micronutrients={},
            )
        raise
    except Exception as e:
        logger.exception("Error fetching user profile")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user profile: {str(e)}",
        )


@router.put(
    "",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    response_class=ORJSONResponse,
)
async def update_profile(
    payload: UserProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
) -> UserProfileResponse:
    """Update user health profile, calculate BMR/TDEE, and UPSERT macro targets with zero-downtime fallback."""
    user_id_str = str(current_user.user_id)

    bmr, tdee = calculate_bmr_and_tdee(
        height_cm=payload.height_cm,
        weight_kg=payload.weight_kg,
        age=payload.age,
        gender=payload.gender,
        activity_level=payload.activity_level,
    )

    # Determine calorie target based on TDEE and primary goal if not explicitly provided
    target_calories = payload.target_calories
    if target_calories is None:
        if tdee:
            goal_clean = (payload.primary_goal or "maintenance").strip().lower()
            if goal_clean == "weight_loss":
                target_calories = round(tdee - 500.0, 2)
            elif goal_clean == "muscle_gain":
                target_calories = round(tdee + 300.0, 2)
            else:
                target_calories = round(tdee, 2)
        else:
            target_calories = 2000.0

    target_protein_g = payload.target_protein_g or 150.0
    target_carbs_g = payload.target_carbs_g or 200.0
    target_fat_g = payload.target_fat_g or 65.0
    target_micro = payload.target_micronutrients or {}

    upsert_sql = """
    INSERT INTO public.profiles (
        id, display_name, height_cm, weight_kg, age, gender,
        activity_level, primary_goal, bmr, tdee,
        target_calories, target_protein_g, target_carbs_g, target_fat_g,
        target_micronutrients, updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
    ON CONFLICT (id) DO UPDATE SET
        display_name = COALESCE(EXCLUDED.display_name, public.profiles.display_name),
        height_cm = COALESCE(EXCLUDED.height_cm, public.profiles.height_cm),
        weight_kg = COALESCE(EXCLUDED.weight_kg, public.profiles.weight_kg),
        age = COALESCE(EXCLUDED.age, public.profiles.age),
        gender = COALESCE(EXCLUDED.gender, public.profiles.gender),
        activity_level = COALESCE(EXCLUDED.activity_level, public.profiles.activity_level),
        primary_goal = COALESCE(EXCLUDED.primary_goal, public.profiles.primary_goal),
        bmr = COALESCE(EXCLUDED.bmr, public.profiles.bmr),
        tdee = COALESCE(EXCLUDED.tdee, public.profiles.tdee),
        target_calories = EXCLUDED.target_calories,
        target_protein_g = EXCLUDED.target_protein_g,
        target_carbs_g = EXCLUDED.target_carbs_g,
        target_fat_g = EXCLUDED.target_fat_g,
        target_micronutrients = EXCLUDED.target_micronutrients,
        updated_at = NOW()
    RETURNING id, display_name, height_cm, weight_kg, age, gender, activity_level, primary_goal, bmr, tdee, target_calories, target_protein_g, target_carbs_g, target_fat_g, target_micronutrients;
    """

    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    upsert_sql,
                    (
                        user_id_str,
                        payload.display_name,
                        payload.height_cm,
                        payload.weight_kg,
                        payload.age,
                        payload.gender,
                        payload.activity_level or "moderate",
                        payload.primary_goal or "maintenance",
                        bmr,
                        tdee,
                        float(target_calories),
                        float(target_protein_g),
                        float(target_carbs_g),
                        float(target_fat_g),
                        json.dumps(target_micro),
                    ),
                )
                row = await cur.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update user profile record.",
                    )

                (
                    u_id,
                    d_name,
                    h_cm,
                    w_kg,
                    u_age,
                    gdr,
                    act,
                    goal,
                    bmr_val,
                    tdee_val,
                    cal,
                    prot,
                    carb,
                    fat,
                    micro_raw,
                ) = row
                micro_dict = (
                    json.loads(micro_raw)
                    if isinstance(micro_raw, str)
                    else (micro_raw or {})
                )

                return UserProfileResponse(
                    id=u_id,
                    display_name=d_name,
                    height_cm=float(h_cm) if h_cm is not None else None,
                    weight_kg=float(w_kg) if w_kg is not None else None,
                    age=int(u_age) if u_age is not None else None,
                    gender=gdr,
                    activity_level=act or "moderate",
                    primary_goal=goal or "maintenance",
                    bmr=float(bmr_val) if bmr_val is not None else None,
                    tdee=float(tdee_val) if tdee_val is not None else None,
                    target_calories=float(cal or 2000.0),
                    target_protein_g=float(prot or 150.0),
                    target_carbs_g=float(carb or 200.0),
                    target_fat_g=float(fat or 65.0),
                    target_micronutrients=micro_dict,
                )
    except HTTPException as http_err:
        if http_err.status_code == 503:
            logger.warning(
                "Database offline; returning updated UserProfileResponse in-memory fallback."
            )
            return UserProfileResponse(
                id=current_user.user_id,
                display_name=payload.display_name
                or (current_user.email.split("@")[0] if current_user.email else "User"),
                height_cm=payload.height_cm,
                weight_kg=payload.weight_kg,
                age=payload.age,
                gender=payload.gender,
                activity_level=payload.activity_level or "moderate",
                primary_goal=payload.primary_goal or "maintenance",
                bmr=bmr,
                tdee=tdee,
                target_calories=float(target_calories),
                target_protein_g=float(target_protein_g),
                target_carbs_g=float(target_carbs_g),
                target_fat_g=float(target_fat_g),
                target_micronutrients=target_micro,
            )
        raise
    except Exception as e:
        logger.exception("Error updating user profile record")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user profile: {str(e)}",
        )
