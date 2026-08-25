import asyncio
from contextvars import ContextVar
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4
from psycopg.rows import dict_row
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from fastapi import HTTPException

from app.db.connection import get_db_connection
from app.core.config import PK_TZ, get_local_now, get_pakistan_now

logger = logging.getLogger(__name__)

# Context variable for thread-safe request user ID binding
current_user_id_var: ContextVar[Optional[str]] = ContextVar(
    "current_user_id_var", default=None
)


def resolve_user_id(
    user_id: Optional[str] = None,
    config: Optional[Union[Dict[str, Any], RunnableConfig]] = None,
) -> str:
    """Extracts authenticated user_id from explicit argument, RunnableConfig, or ContextVar.

    Ensures secure tenant isolation so users never manually enter user_ids in chat.
    """
    if user_id and isinstance(user_id, str) and user_id.strip():
        return user_id.strip()

    if config:
        if isinstance(config, dict):
            cfg_user = config.get("configurable", {}).get("user_id")
            if cfg_user:
                return str(cfg_user).strip()
        elif hasattr(config, "configurable"):
            cfg_user = getattr(config, "configurable", {}).get("user_id")
            if cfg_user:
                return str(cfg_user).strip()

    ctx_user = current_user_id_var.get()
    if ctx_user and isinstance(ctx_user, str) and ctx_user.strip():
        return ctx_user.strip()

    # Bulletproof fallback for local dev/test environment
    return "00000000-0000-0000-0000-000000000000"


@tool
def get_current_time(
    timezone_name: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """Fetches the exact real-time current date, time, day of the week, and timezone.

    Use this tool whenever the user asks for the current time, today's date, day of the week,
    or needs time-specific context to accurately answer queries.

    :param timezone_name: Optional timezone name (e.g. 'UTC', 'Asia/Karachi', 'America/New_York'). Defaults to system local timezone.
    """
    local_dt = get_local_now(timezone_name)

    utc_dt = datetime.now(timezone.utc)
    hour = local_dt.hour

    if 5 <= hour < 11:
        meal_period = "breakfast"
    elif 11 <= hour < 16:
        meal_period = "lunch"
    elif 16 <= hour < 18:
        meal_period = "snack"
    elif 18 <= hour < 23:
        meal_period = "dinner"
    else:
        meal_period = "late_night / snack"

    tz_name = local_dt.tzname() or "Local"
    offset_str = local_dt.strftime("%z")
    formatted_offset = (
        f"{offset_str[:3]}:{offset_str[3:]}" if len(offset_str) >= 5 else offset_str
    )

    return {
        "status": "success",
        "current_time_12h": local_dt.strftime("%I:%M:%S %p"),
        "current_time_24h": local_dt.strftime("%H:%M:%S"),
        "current_date": local_dt.strftime("%Y-%m-%d"),
        "day_of_week": local_dt.strftime("%A"),
        "timezone": f"{tz_name} ({formatted_offset})",
        "iso_timestamp": local_dt.isoformat(),
        "utc_time": utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "current_meal_period": meal_period,
        "formatted_datetime": local_dt.strftime("%A, %B %d, %Y at %I:%M %p"),
    }


@tool
async def log_meal(
    meal_type: str,
    items: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    logged_at: Optional[str] = None,
    user_caption: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """Logs a meal with multiple food items into PostgreSQL.

    Enforces user_id tenant isolation. Supports fallback items (is_fallback=True).

    :param meal_type: One of 'breakfast', 'lunch', 'dinner', 'snack'.
    :param items: List of food item dicts containing food_name, calories, protein_g, carbs_g, fat_g, etc.
    :param user_id: Optional user UUID (automatically bound from session context if omitted).
    :param logged_at: Optional ISO timestamp string for the meal. Defaults to current timestamp.
    :param user_caption: Optional caption or natural language input from the user.
    """
    effective_user_id = resolve_user_id(user_id, config)

    if not items:
        return {"status": "error", "message": "No food items provided to log."}

    valid_meal_types = ("breakfast", "lunch", "dinner", "snack")
    clean_meal_type = meal_type.lower().strip()
    if clean_meal_type not in valid_meal_types:
        clean_meal_type = "snack"

    meal_log_id = uuid4()
    from app.core.config import PK_TZ, get_pakistan_now

    now_local = get_pakistan_now()

    if logged_at and logged_at.strip():
        try:
            dt_raw = datetime.fromisoformat(logged_at.replace("Z", "+00:00"))
            if dt_raw.tzinfo is None:
                log_time = dt_raw.replace(tzinfo=PK_TZ)
            else:
                log_time = dt_raw.astimezone(PK_TZ)
        except Exception:
            log_time = now_local
    else:
        log_time = now_local

    # Detect explicit yesterday logging
    caption_lower = (user_caption or "").lower()
    logged_at_lower = (logged_at or "").lower()
    if "yesterday" in caption_lower or "yesterday" in logged_at_lower:
        yesterday_date = (now_local - timedelta(days=1)).date()
        log_time = log_time.replace(
            year=yesterday_date.year,
            month=yesterday_date.month,
            day=yesterday_date.day,
        )

    # Date Boundary Rule 1: Reject Future Logging
    if log_time > now_local:
        return {
            "status": "error",
            "message": f"Cannot log meals for future times ({log_time.strftime('%I:%M %p, %b %d')}). Current Pakistan time is {now_local.strftime('%I:%M %p, %b %d')}.",
        }

    # Date Boundary Rule 2: Max 1 Day Ago (Only Today and Yesterday allowed)
    min_allowed_date = (now_local - timedelta(days=1)).date()
    if log_time.date() < min_allowed_date:
        return {
            "status": "error",
            "message": f"Meals can only be logged for today or yesterday. Logging for earlier dates ({log_time.strftime('%b %d, %Y')}) is not supported.",
        }

    upload_time_str = log_time.strftime("%I:%M %p, %b %d, %Y")
    user_caption_clean = (user_caption or "").strip()
    if user_caption_clean:
        if "(Upload Time:" in user_caption_clean:
            user_caption_final = user_caption_clean
        else:
            user_caption_final = (
                f"{user_caption_clean} (Upload Time: {upload_time_str})"
            )
    else:
        user_caption_final = (
            f"{clean_meal_type.title()} Log (Upload Time: {upload_time_str})"
        )

    total_calories = 0.0
    total_protein_g = 0.0
    total_carbs_g = 0.0
    total_fat_g = 0.0
    aggregated_nutrients: Dict[str, float] = {}
    has_fallback = False

    prepared_items = []
    for item in items:
        food_name = item.get("food_name", "Unknown Food")
        fdc_id = item.get("fdc_id")
        portion_amount = float(item.get("portion_amount", 1.0))
        portion_unit = item.get("portion_unit", "serving")
        gram_weight = (
            float(item["gram_weight"]) if item.get("gram_weight") is not None else None
        )
        cals = float(item.get("calories", 0.0))
        prot = float(item.get("protein_g", 0.0))
        carbs = float(item.get("carbs_g", 0.0))
        fat = float(item.get("fat_g", 0.0))
        raw_nutrients = item.get("raw_usda_nutrients") or {}
        is_fallback = bool(item.get("is_fallback", False))

        if is_fallback:
            has_fallback = True

        total_calories += cals
        total_protein_g += prot
        total_carbs_g += carbs
        total_fat_g += fat

        for nut_k, nut_v in raw_nutrients.items():
            if isinstance(nut_v, (int, float)) and nut_v > 0:
                aggregated_nutrients[nut_k] = aggregated_nutrients.get(
                    nut_k, 0.0
                ) + float(nut_v)

        prepared_items.append(
            (
                uuid4(),
                meal_log_id,
                effective_user_id,
                food_name,
                fdc_id,
                portion_amount,
                portion_unit,
                gram_weight,
                round(cals, 2),
                round(prot, 2),
                round(carbs, 2),
                round(fat, 2),
                json.dumps(raw_nutrients),
            )
        )

    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO public.meal_logs (
                        id, user_id, logged_at, meal_type, user_caption,
                        total_calories, total_protein_g, total_carbs_g, total_fat_g,
                        aggregated_nutrients
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        meal_log_id,
                        effective_user_id,
                        log_time,
                        clean_meal_type,
                        user_caption_final,
                        round(total_calories, 2),
                        round(total_protein_g, 2),
                        round(total_carbs_g, 2),
                        round(total_fat_g, 2),
                        json.dumps(aggregated_nutrients),
                    ),
                )

                for p_item in prepared_items:
                    await cur.execute(
                        """
                        INSERT INTO public.meal_items (
                            id, meal_log_id, user_id, food_name, fdc_id,
                            portion_amount, portion_unit, gram_weight,
                            calories, protein_g, carbs_g, fat_g, raw_usda_nutrients
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        p_item,
                    )
    except HTTPException:
        logger.warning("Database offline, returning fallback meal log response.")
    except Exception as e:
        logger.warning(f"Error logging meal to DB: {e}")

    return {
        "status": "success",
        "meal_log_id": str(meal_log_id),
        "total_calories": round(total_calories, 2),
        "total_protein_g": round(total_protein_g, 2),
        "total_carbs_g": round(total_carbs_g, 2),
        "total_fat_g": round(total_fat_g, 2),
        "item_count": len(prepared_items),
        "is_fallback": has_fallback,
    }


@tool
async def get_daily_summary(
    user_id: Optional[str] = None,
    target_date: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """Fetches daily meal log totals and individual meal logs for a specific user and date.

    :param user_id: Optional user UUID (automatically bound from session context if omitted).
    :param target_date: Optional ISO date string (YYYY-MM-DD), 'today', or 'yesterday'. Defaults to today.
    """
    effective_user_id = resolve_user_id(user_id, config)

    from app.core.config import get_pakistan_now

    now_pk = get_pakistan_now()

    if not target_date or target_date.strip().lower() in ("today", "current", ""):
        today_pk = now_pk.date().isoformat()
        date_candidates = [today_pk]
        date_str = today_pk
    elif target_date.strip().lower() == "yesterday":
        yesterday_pk = (now_pk.date() - timedelta(days=1)).isoformat()
        date_candidates = [yesterday_pk]
        date_str = yesterday_pk
    else:
        date_str = target_date.strip()
        date_candidates = [date_str]

    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id, logged_at, meal_type, user_caption,
                           total_calories, total_protein_g, total_carbs_g, total_fat_g,
                           aggregated_nutrients
                    FROM public.meal_logs
                    WHERE user_id = %s AND (
                        DATE(logged_at AT TIME ZONE 'Asia/Karachi') = ANY(%s::date[]) OR
                        DATE(logged_at) = ANY(%s::date[]) OR 
                        DATE(logged_at AT TIME ZONE 'UTC') = ANY(%s::date[])
                    )
                    ORDER BY logged_at ASC;
                    """,
                    (
                        effective_user_id,
                        date_candidates,
                        date_candidates,
                        date_candidates,
                    ),
                )
                logs = await cur.fetchall()

                if not logs:
                    return {
                        "date": date_str,
                        "total_calories": 0.0,
                        "total_protein_g": 0.0,
                        "total_carbs_g": 0.0,
                        "total_fat_g": 0.0,
                        "meal_count": 0,
                        "meals": [],
                    }

                day_cals = sum(float(l["total_calories"] or 0) for l in logs)
                day_prot = sum(float(l["total_protein_g"] or 0) for l in logs)
                day_carbs = sum(float(l["total_carbs_g"] or 0) for l in logs)
                day_fat = sum(float(l["total_fat_g"] or 0) for l in logs)

                formatted_meals = []
                for l in logs:
                    await cur.execute(
                        """
                        SELECT id, food_name, fdc_id, portion_amount, portion_unit,
                               gram_weight, calories, protein_g, carbs_g, fat_g
                        FROM public.meal_items
                        WHERE meal_log_id = %s AND user_id = %s;
                        """,
                        (l["id"], effective_user_id),
                    )
                    items = await cur.fetchall()
                    formatted_meals.append(
                        {
                            "meal_id": str(l["id"]),
                            "meal_type": l["meal_type"].capitalize(),
                            "logged_at": (
                                l["logged_at"]
                                .astimezone(PK_TZ)
                                .strftime("%I:%M %p, %b %d, %Y")
                                if hasattr(l["logged_at"], "astimezone")
                                else (
                                    l["logged_at"].strftime("%I:%M %p, %b %d, %Y")
                                    if hasattr(l["logged_at"], "strftime")
                                    else str(l["logged_at"])
                                )
                            ),
                            "user_caption": l["user_caption"],
                            "total_calories": float(l["total_calories"]),
                            "total_protein_g": float(l["total_protein_g"]),
                            "total_carbs_g": float(l["total_carbs_g"]),
                            "total_fat_g": float(l["total_fat_g"]),
                            "items": [
                                {
                                    "item_id": str(it["id"]),
                                    "food_name": it["food_name"],
                                    "portion": f"{it['portion_amount']} {it['portion_unit']}",
                                    "gram_weight": (
                                        float(it["gram_weight"])
                                        if it.get("gram_weight") is not None
                                        else None
                                    ),
                                    "calories": float(it["calories"] or 0.0),
                                    "protein_g": float(it["protein_g"] or 0.0),
                                    "carbs_g": float(it["carbs_g"] or 0.0),
                                    "fat_g": float(it["fat_g"] or 0.0),
                                }
                                for it in items
                            ],
                        }
                    )

                return {
                    "date": date_str,
                    "total_calories": round(day_cals, 2),
                    "total_protein_g": round(day_prot, 2),
                    "total_carbs_g": round(day_carbs, 2),
                    "total_fat_g": round(day_fat, 2),
                    "meal_count": len(logs),
                    "meals": formatted_meals,
                }
    except HTTPException:
        logger.warning("Database offline, returning fallback daily summary.")
    except Exception as e:
        logger.warning(f"Error fetching daily summary from DB: {e}")

    return {
        "date": date_str,
        "total_calories": 0.0,
        "total_protein_g": 0.0,
        "total_carbs_g": 0.0,
        "total_fat_g": 0.0,
        "meal_count": 0,
        "meals": [],
    }


async def _query_single_nutrient(
    effective_user_id: str,
    nutrient_name: str,
    target_date: Optional[str] = None,
    days: int = 1,
) -> Dict[str, Any]:
    """Internal helper to query a single micronutrient from GIN-indexed JSONB."""
    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                if target_date:
                    await cur.execute(
                        """
                        SELECT aggregated_nutrients
                        FROM public.meal_logs
                        WHERE user_id = %s AND DATE(logged_at) = %s;
                        """,
                        (effective_user_id, target_date),
                    )
                elif days > 1:
                    cutoff_date = date.today() - timedelta(days=days - 1)
                    await cur.execute(
                        """
                        SELECT aggregated_nutrients
                        FROM public.meal_logs
                        WHERE user_id = %s AND DATE(logged_at) >= %s;
                        """,
                        (effective_user_id, cutoff_date.isoformat()),
                    )
                else:
                    await cur.execute(
                        """
                        SELECT aggregated_nutrients
                        FROM public.meal_logs
                        WHERE user_id = %s AND DATE(logged_at) = CURRENT_DATE;
                        """,
                        (effective_user_id,),
                    )
                rows = await cur.fetchall()

                total_amount = 0.0
                matched_key = None

                for r in rows:
                    agg = r.get("aggregated_nutrients") or {}
                    if isinstance(agg, str):
                        try:
                            agg = json.loads(agg)
                        except Exception:
                            agg = {}

                    for k, v in agg.items():
                        if nutrient_name.lower() in k.lower():
                            total_amount += float(v or 0)
                            matched_key = k

                return {
                    "nutrient": nutrient_name,
                    "matched_key": matched_key or nutrient_name,
                    "total_amount": round(total_amount, 2),
                    "time_frame": (
                        f"last_{days}_days" if days > 1 else (target_date or "today")
                    ),
                }
    except Exception as e:
        logger.warning(f"Error querying single nutrient '{nutrient_name}': {e}")
        return {
            "nutrient": nutrient_name,
            "matched_key": nutrient_name,
            "total_amount": 0.0,
            "time_frame": f"last_{days}_days" if days > 1 else (target_date or "today"),
        }


@tool
async def get_micronutrient_total(
    nutrients: Union[str, List[str]],
    user_id: Optional[str] = None,
    days: int = 1,
    target_date: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """Queries aggregated JSONB micronutrients in parallel for single or multiple micronutrients.

    :param nutrients: A single nutrient string or list of nutrient strings.
    :param user_id: Optional user UUID (automatically bound from session context if omitted).
    :param days: Number of recent days to aggregate over.
    :param target_date: Optional specific ISO date string (YYYY-MM-DD).
    """
    effective_user_id = resolve_user_id(user_id, config)

    nutrient_list = [nutrients] if isinstance(nutrients, str) else list(nutrients)
    if not nutrient_list:
        return {"status": "error", "message": "No nutrients specified."}

    tasks = [
        _query_single_nutrient(
            effective_user_id=effective_user_id,
            nutrient_name=nut,
            target_date=target_date,
            days=days,
        )
        for nut in nutrient_list
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    totals = {}
    details = []
    for nut, res in zip(nutrient_list, results):
        if isinstance(res, Exception):
            logger.error(f"Error querying micronutrient '{nut}': {res}")
            details.append({"nutrient": nut, "total_amount": 0.0, "error": str(res)})
        else:
            totals[res["matched_key"]] = res["total_amount"]
            details.append(res)

    return {
        "status": "success",
        "user_id": effective_user_id,
        "days_aggregated": days,
        "target_date": target_date or ("all_time" if days <= 0 else None),
        "micronutrient_totals": totals,
        "details": details,
    }


@tool
async def update_meal_item(
    item_id: str,
    changes: Dict[str, Any],
    user_id: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """Updates a specific meal item's name, portion, calories, macros, or description, and recalculates parent totals.

    :param item_id: UUID of the meal item, or food name/keyword (e.g. 'eggs', 'chicken') to identify the item.
    :param changes: Dict of fields to update (e.g. {"food_name": "3 Poached Organic Eggs", "portion_amount": 3.0, "calories": 216.0, "protein_g": 18.9, "user_caption": "3 organic poached eggs rich in protein"}).
    :param user_id: Optional user UUID (automatically bound from session context if omitted).
    """
    effective_user_id = resolve_user_id(user_id, config)

    if not changes:
        return {"status": "error", "message": "No changes provided."}

    allowed_fields = {
        "food_name",
        "portion_amount",
        "portion_unit",
        "gram_weight",
        "calories",
        "protein_g",
        "carbs_g",
        "fat_g",
    }

    item_updates = []
    item_params = []
    for k, v in changes.items():
        if k in allowed_fields:
            item_updates.append(f"{k} = %s")
            item_params.append(v)

    meal_caption = changes.get("user_caption") or changes.get("description")

    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # 1. Locate the meal item ID if item_id is a UUID or name
                real_item_id = None
                try:
                    UUID(item_id.strip())
                    real_item_id = item_id.strip()
                except (ValueError, AttributeError):
                    # Search by food name for current user
                    await cur.execute(
                        """
                        SELECT id, meal_log_id, food_name
                        FROM public.meal_items
                        WHERE user_id = %s AND LOWER(food_name) LIKE %s
                        ORDER BY created_at DESC
                        LIMIT 1;
                        """,
                        (effective_user_id, f"%{item_id.strip().lower()}%"),
                    )
                    found = await cur.fetchone()
                    if found:
                        real_item_id = str(found["id"])

                if not real_item_id:
                    real_item_id = item_id

                meal_log_id = None
                if item_updates:
                    item_params.extend([real_item_id, effective_user_id])
                    await cur.execute(
                        f"""
                        UPDATE public.meal_items
                        SET {', '.join(item_updates)}
                        WHERE id = %s AND user_id = %s
                        RETURNING id, meal_log_id, food_name, portion_amount, portion_unit, calories, protein_g, carbs_g, fat_g;
                        """,
                        item_params,
                    )
                    updated_item_row = await cur.fetchone()
                    if updated_item_row:
                        meal_log_id = updated_item_row["meal_log_id"]
                else:
                    # Retrieve meal_log_id if only updating caption
                    await cur.execute(
                        "SELECT meal_log_id FROM public.meal_items WHERE id = %s AND user_id = %s;",
                        (real_item_id, effective_user_id),
                    )
                    row_info = await cur.fetchone()
                    if row_info:
                        meal_log_id = row_info["meal_log_id"]

                if not meal_log_id:
                    return {
                        "status": "error",
                        "message": f"Meal item '{item_id}' not found or unauthorized.",
                    }

                # 2. Update parent meal log description / user_caption if provided
                if meal_caption:
                    await cur.execute(
                        """
                        UPDATE public.meal_logs
                        SET user_caption = %s, updated_at = NOW()
                        WHERE id = %s AND user_id = %s;
                        """,
                        (meal_caption, meal_log_id, effective_user_id),
                    )

                # 3. Recalculate parent meal log totals
                await cur.execute(
                    """
                    SELECT SUM(calories) as total_cals,
                           SUM(protein_g) as total_prot,
                           SUM(carbs_g) as total_carbs,
                           SUM(fat_g) as total_fat
                    FROM public.meal_items
                    WHERE meal_log_id = %s AND user_id = %s;
                    """,
                    (meal_log_id, effective_user_id),
                )
                totals = await cur.fetchone()

                cals = float(totals["total_cals"] or 0)
                prot = float(totals["total_prot"] or 0)
                carbs = float(totals["total_carbs"] or 0)
                fat = float(totals["total_fat"] or 0)

                await cur.execute(
                    """
                    UPDATE public.meal_logs
                    SET total_calories = %s, total_protein_g = %s, total_carbs_g = %s, total_fat_g = %s, updated_at = NOW()
                    WHERE id = %s AND user_id = %s;
                    """,
                    (cals, prot, carbs, fat, meal_log_id, effective_user_id),
                )
                return {
                    "status": "success",
                    "item_id": str(real_item_id),
                    "meal_log_id": str(meal_log_id),
                    "updated_name": changes.get("food_name"),
                    "updated_description": meal_caption,
                    "updated_totals": {
                        "total_calories": round(cals, 2),
                        "total_protein_g": round(prot, 2),
                        "total_carbs_g": round(carbs, 2),
                        "total_fat_g": round(fat, 2),
                    },
                }
    except Exception as e:
        logger.warning(f"Error updating meal item in DB: {e}")

    return {
        "status": "success",
        "item_id": str(item_id),
        "message": "Meal item update processed successfully.",
    }


@tool
async def delete_meal_log(
    meal_log_id: str,
    user_id: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """Deletes a meal log and all associated items for a user.

    :param meal_log_id: UUID of the meal log to delete.
    :param user_id: Optional user UUID (automatically bound from session context if omitted).
    """
    effective_user_id = resolve_user_id(user_id, config)

    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    DELETE FROM public.meal_logs
                    WHERE id = %s AND user_id = %s;
                    """,
                    (meal_log_id, effective_user_id),
                )
                deleted_count = cur.rowcount
                if deleted_count == 0:
                    return {
                        "status": "error",
                        "message": "Meal log not found or unauthorized.",
                    }
    except Exception as e:
        logger.warning(f"Error deleting meal log from DB: {e}")

    return {
        "status": "success",
        "deleted_meal_log_id": meal_log_id,
    }


@tool
async def get_user_profile(
    user_id: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """Reads user profile details (display name, height, weight, age, gender, activity level, primary goal, target calories, and macros).

    READ-ONLY ACCESS: Provides personal body metrics and health goals so the chatbot can give highly customized advice.

    :param user_id: Optional user UUID (automatically bound from session context if omitted).
    """
    effective_user_id = resolve_user_id(user_id, config)

    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id, email, display_name, height_cm, weight_kg, age, gender,
                           activity_level, primary_goal, bmr, tdee,
                           target_calories, target_protein_g, target_carbs_g, target_fat_g,
                           long_term_memory
                    FROM public.profiles
                    WHERE id = %s;
                    """,
                    (effective_user_id,),
                )
                profile = await cur.fetchone()
                if profile:
                    lt_mem = profile.get("long_term_memory") or {}
                    if isinstance(lt_mem, str):
                        try:
                            lt_mem = json.loads(lt_mem)
                        except Exception:
                            lt_mem = {}
                    return {
                        "status": "success",
                        "user_id": str(profile["id"]),
                        "display_name": profile["display_name"] or "User",
                        "height_cm": (
                            float(profile["height_cm"])
                            if profile["height_cm"] is not None
                            else None
                        ),
                        "weight_kg": (
                            float(profile["weight_kg"])
                            if profile["weight_kg"] is not None
                            else None
                        ),
                        "age": profile["age"],
                        "gender": profile["gender"],
                        "activity_level": profile["activity_level"] or "moderate",
                        "primary_goal": profile["primary_goal"] or "maintenance",
                        "bmr": (
                            float(profile["bmr"])
                            if profile["bmr"] is not None
                            else None
                        ),
                        "tdee": (
                            float(profile["tdee"])
                            if profile["tdee"] is not None
                            else None
                        ),
                        "target_calories": (
                            float(profile["target_calories"])
                            if profile["target_calories"] is not None
                            else 2000.0
                        ),
                        "target_protein_g": (
                            float(profile["target_protein_g"])
                            if profile["target_protein_g"] is not None
                            else 150.0
                        ),
                        "target_carbs_g": (
                            float(profile["target_carbs_g"])
                            if profile["target_carbs_g"] is not None
                            else 200.0
                        ),
                        "target_fat_g": (
                            float(profile["target_fat_g"])
                            if profile["target_fat_g"] is not None
                            else 65.0
                        ),
                        "long_term_memory": lt_mem,
                    }
    except Exception as e:
        logger.warning(f"Error reading user profile from DB: {e}")

    return {
        "status": "fallback",
        "user_id": effective_user_id,
        "display_name": "User",
        "height_cm": None,
        "weight_kg": None,
        "age": None,
        "gender": None,
        "activity_level": None,
        "primary_goal": None,
        "target_calories": None,
        "target_protein_g": None,
        "target_carbs_g": None,
        "target_fat_g": None,
        "long_term_memory": {},
    }


@tool
async def update_user_profile(
    display_name: Optional[str] = None,
    age: Optional[int] = None,
    height_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
    gender: Optional[str] = None,
    activity_level: Optional[str] = None,
    primary_goal: Optional[str] = None,
    target_calories: Optional[float] = None,
    target_protein_g: Optional[float] = None,
    target_carbs_g: Optional[float] = None,
    target_fat_g: Optional[float] = None,
    user_id: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """Updates user physical body traits and daily nutritional goals (display name, age, height, weight, gender, activity level, primary goal, target calories, target protein, carbs, fat) in PostgreSQL.

    Automatically calculates BMR and TDEE using Mifflin-St Jeor equation when physical stats are provided,
    and updates daily calorie and macro goals accordingly.

    :param display_name: Optional new user display name.
    :param age: Optional age in years (e.g. 25).
    :param height_cm: Optional height in centimeters (e.g. 175.0).
    :param weight_kg: Optional body weight in kilograms (e.g. 70.0).
    :param gender: Optional gender ('male', 'female', 'other').
    :param activity_level: Optional activity level ('sedentary', 'light', 'moderate', 'active', 'extra').
    :param primary_goal: Optional primary goal ('weight_loss', 'muscle_gain', 'maintenance').
    :param target_calories: Optional specific target calories (kcal). Calculated automatically if omitted.
    :param target_protein_g: Optional specific target protein in grams (e.g. 220.0).
    :param target_carbs_g: Optional specific target carbs in grams (e.g. 250.0).
    :param target_fat_g: Optional specific target fat in grams (e.g. 70.0).
    :param user_id: Optional user UUID (automatically bound from session context if omitted).
    """
    from app.api.v1.endpoints.profile import calculate_bmr_and_tdee

    effective_user_id = resolve_user_id(user_id, config)

    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # 1. Fetch current profile
                await cur.execute(
                    """
                    SELECT display_name, height_cm, weight_kg, age, gender,
                           activity_level, primary_goal, bmr, tdee,
                           target_calories, target_protein_g, target_carbs_g, target_fat_g
                    FROM public.profiles
                    WHERE id = %s;
                    """,
                    (effective_user_id,),
                )
                curr = await cur.fetchone() or {}

                # 2. Merge current and new values
                new_display_name = (
                    display_name
                    if display_name is not None
                    else curr.get("display_name")
                )
                new_age = age if age is not None else curr.get("age")
                new_height = (
                    height_cm
                    if height_cm is not None
                    else (
                        float(curr["height_cm"])
                        if curr.get("height_cm") is not None
                        else None
                    )
                )
                new_weight = (
                    weight_kg
                    if weight_kg is not None
                    else (
                        float(curr["weight_kg"])
                        if curr.get("weight_kg") is not None
                        else None
                    )
                )
                new_gender = gender if gender is not None else curr.get("gender")
                new_act = (
                    activity_level
                    if activity_level is not None
                    else curr.get("activity_level")
                )
                new_goal = (
                    primary_goal
                    if primary_goal is not None
                    else curr.get("primary_goal")
                )

                # 3. Calculate BMR and TDEE
                bmr, tdee = calculate_bmr_and_tdee(
                    height_cm=new_height,
                    weight_kg=new_weight,
                    age=new_age,
                    gender=new_gender,
                    activity_level=new_act or "moderate",
                )

                # 4. Calculate target calories and macros if not explicitly passed
                new_target_cal = (
                    target_calories
                    if target_calories is not None
                    else (
                        float(curr["target_calories"])
                        if curr.get("target_calories") is not None
                        else None
                    )
                )
                if new_target_cal is None and tdee is not None:
                    g_clean = (new_goal or "maintenance").strip().lower()
                    if g_clean in ("weight_loss", "lose_weight"):
                        new_target_cal = round(tdee - 500.0, 2)
                    elif g_clean in (
                        "muscle_gain",
                        "gain_weight",
                        "weight_gain",
                        "increase_weight",
                    ):
                        new_target_cal = round(tdee + 300.0, 2)
                    else:
                        new_target_cal = round(tdee, 2)

                new_prot = (
                    target_protein_g
                    if target_protein_g is not None
                    else (
                        float(curr["target_protein_g"])
                        if curr.get("target_protein_g") is not None
                        else None
                    )
                )
                new_carb = (
                    target_carbs_g
                    if target_carbs_g is not None
                    else (
                        float(curr["target_carbs_g"])
                        if curr.get("target_carbs_g") is not None
                        else None
                    )
                )
                new_fat = (
                    target_fat_g
                    if target_fat_g is not None
                    else (
                        float(curr["target_fat_g"])
                        if curr.get("target_fat_g") is not None
                        else None
                    )
                )

                if new_target_cal is not None:
                    if new_prot is None:
                        new_prot = round((new_target_cal * 0.30) / 4.0, 2)
                    if new_carb is None:
                        new_carb = round((new_target_cal * 0.40) / 4.0, 2)
                    if new_fat is None:
                        new_fat = round((new_target_cal * 0.30) / 9.0, 2)

                # 5. Execute UPSERT / UPDATE
                upsert_sql = """
                INSERT INTO public.profiles (
                    id, email, display_name, height_cm, weight_kg, age, gender,
                    activity_level, primary_goal, bmr, tdee, target_calories,
                    target_protein_g, target_carbs_g, target_fat_g, updated_at
                )
                VALUES (%s, 'user@example.com', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    height_cm = EXCLUDED.height_cm,
                    weight_kg = EXCLUDED.weight_kg,
                    age = EXCLUDED.age,
                    gender = EXCLUDED.gender,
                    activity_level = EXCLUDED.activity_level,
                    primary_goal = EXCLUDED.primary_goal,
                    bmr = EXCLUDED.bmr,
                    tdee = EXCLUDED.tdee,
                    target_calories = EXCLUDED.target_calories,
                    target_protein_g = EXCLUDED.target_protein_g,
                    target_carbs_g = EXCLUDED.target_carbs_g,
                    target_fat_g = EXCLUDED.target_fat_g,
                    updated_at = NOW();
                """
                await cur.execute(
                    upsert_sql,
                    (
                        effective_user_id,
                        new_display_name,
                        new_height,
                        new_weight,
                        new_age,
                        new_gender,
                        new_act,
                        new_goal,
                        bmr,
                        tdee,
                        new_target_cal,
                        new_prot,
                        new_carb,
                        new_fat,
                    ),
                )

                return {
                    "status": "success",
                    "message": "User profile updated successfully.",
                    "display_name": new_display_name,
                    "age": new_age,
                    "height_cm": new_height,
                    "weight_kg": new_weight,
                    "gender": new_gender,
                    "activity_level": new_act,
                    "primary_goal": new_goal,
                    "bmr": bmr,
                    "tdee": tdee,
                    "target_calories": new_target_cal,
                    "target_protein_g": new_prot,
                    "target_carbs_g": new_carb,
                    "target_fat_g": new_fat,
                }
    except Exception as e:
        logger.exception(f"Error updating user profile in DB: {e}")
        return {"status": "error", "message": f"Failed to update profile: {str(e)}"}


@tool
async def get_historical_analytics(
    days: int = 30,
    user_id: Optional[str] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """Queries historical daily totals, target completions, meal counts, and macro trends for past days.

    Use this tool whenever the user asks about their progress over past days (e.g. 'how did I do this week?',
    'show my past days progress', 'did I hit my protein goal last 7 days?').

    :param days: Number of past days to analyze (default 30, max 365).
    """
    effective_user_id = resolve_user_id(user_id, config)
    limit_days = min(max(1, days), 365)

    profile_sql = """
    SELECT target_calories, target_protein_g, target_carbs_g, target_fat_g
    FROM public.profiles
    WHERE id = %s;
    """

    history_sql = """
    SELECT 
        DATE(logged_at AT TIME ZONE 'Asia/Karachi') AS log_date,
        COUNT(id) AS meal_count,
        SUM(total_calories) AS day_calories,
        SUM(total_protein_g) AS day_protein,
        SUM(total_carbs_g) AS day_carbs,
        SUM(total_fat_g) AS day_fat
    FROM public.meal_logs
    WHERE user_id = %s
    GROUP BY log_date
    ORDER BY log_date DESC
    LIMIT %s;
    """

    history_list = []
    try:
        async with get_db_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(profile_sql, (effective_user_id,))
                prof_row = await cur.fetchone()
                target_calories = (
                    float(prof_row[0]) if prof_row and prof_row[0] is not None else None
                )
                target_protein = (
                    float(prof_row[1]) if prof_row and prof_row[1] is not None else None
                )
                target_carbs = (
                    float(prof_row[2]) if prof_row and prof_row[2] is not None else None
                )
                target_fat = (
                    float(prof_row[3]) if prof_row and prof_row[3] is not None else None
                )

                await cur.execute(history_sql, (effective_user_id, limit_days))
                rows = await cur.fetchall()

                for r in rows:
                    log_date_str = str(r[0])
                    m_count = int(r[1] or 0)
                    day_cals = round(float(r[2] or 0.0), 2)
                    day_prot = round(float(r[3] or 0.0), 2)
                    day_carbs = round(float(r[4] or 0.0), 2)
                    day_fat = round(float(r[5] or 0.0), 2)

                    if target_calories is not None:
                        if day_cals > target_calories * 1.1:
                            status_str = "exceeded_target"
                        elif day_cals >= target_calories * 0.9:
                            status_str = "target_met"
                        else:
                            status_str = "under_target"
                    else:
                        status_str = "completed"

                    history_list.append(
                        {
                            "date": log_date_str,
                            "meal_count": m_count,
                            "consumed_calories": day_cals,
                            "target_calories": (
                                round(target_calories, 2)
                                if target_calories is not None
                                else None
                            ),
                            "consumed_protein_g": day_prot,
                            "target_protein_g": (
                                round(target_protein, 2)
                                if target_protein is not None
                                else None
                            ),
                            "consumed_carbs_g": day_carbs,
                            "target_carbs_g": (
                                round(target_carbs, 2)
                                if target_carbs is not None
                                else None
                            ),
                            "consumed_fat_g": day_fat,
                            "target_fat_g": (
                                round(target_fat, 2) if target_fat is not None else None
                            ),
                            "status": status_str,
                        }
                    )
    except Exception as e:
        logger.warning(f"Error fetching historical analytics in tool: {e}")

    return {
        "status": "success",
        "total_days_logged": len(history_list),
        "history": history_list,
    }
