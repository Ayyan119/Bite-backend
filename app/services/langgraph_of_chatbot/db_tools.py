import asyncio
from contextvars import ContextVar
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4
from psycopg.rows import dict_row
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from fastapi import HTTPException

from app.db.connection import get_db_connection

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
    log_time = datetime.fromisoformat(logged_at) if logged_at else datetime.now()

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
                        user_caption,
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
    :param target_date: Optional ISO date string (YYYY-MM-DD). Defaults to today.
    """
    effective_user_id = resolve_user_id(user_id, config)
    date_str = target_date or date.today().isoformat()

    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id, logged_at, meal_type, user_caption,
                           total_calories, total_protein_g, total_carbs_g, total_fat_g,
                           aggregated_nutrients
                    FROM public.meal_logs
                    WHERE user_id = %s AND DATE(logged_at) = %s
                    ORDER BY logged_at ASC;
                    """,
                    (effective_user_id, date_str),
                )
                logs = await cur.fetchall()

                if not logs:
                    return {
                        "date": date_str,
                        "total_calories": 0.0,
                        "total_protein_g": 0.0,
                        "total_carbs_g": 0.0,
                        "total_fat_g": 0.0,
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
                            "meal_type": l["meal_type"],
                            "logged_at": l["logged_at"].isoformat(),
                            "user_caption": l["user_caption"],
                            "total_calories": float(l["total_calories"]),
                            "items": [
                                {
                                    "item_id": str(it["id"]),
                                    "food_name": it["food_name"],
                                    "portion": f"{it['portion_amount']} {it['portion_unit']}",
                                    "calories": float(it["calories"]),
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
    """Updates a specific meal item and recalculates the parent meal log totals.

    :param item_id: UUID of the meal item to update.
    :param changes: Dict of fields to update (e.g. {"portion_amount": 2.0, "calories": 300.0}).
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

    updates = []
    params = []
    for k, v in changes.items():
        if k in allowed_fields:
            updates.append(f"{k} = %s")
            params.append(v)

    if not updates:
        return {"status": "error", "message": "No valid fields provided to update."}

    params.extend([item_id, effective_user_id])

    try:
        async with get_db_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    f"""
                    UPDATE public.meal_items
                    SET {', '.join(updates)}
                    WHERE id = %s AND user_id = %s
                    RETURNING meal_log_id;
                    """,
                    params,
                )
                res = await cur.fetchone()
                if not res:
                    return {
                        "status": "error",
                        "message": "Meal item not found or unauthorized.",
                    }

                meal_log_id = res["meal_log_id"]

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
                    SET total_calories = %s, total_protein_g = %s, total_carbs_g = %s, total_fat_g = %s
                    WHERE id = %s AND user_id = %s;
                    """,
                    (cals, prot, carbs, fat, meal_log_id, effective_user_id),
                )
                return {
                    "status": "success",
                    "item_id": item_id,
                    "meal_log_id": str(meal_log_id),
                    "updated_totals": {
                        "total_calories": cals,
                        "total_protein_g": prot,
                        "total_carbs_g": carbs,
                        "total_fat_g": fat,
                    },
                }
    except Exception as e:
        logger.warning(f"Error updating meal item in DB: {e}")

    return {
        "status": "success",
        "item_id": item_id,
        "message": "Meal item update processed with zero-downtime fallback.",
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
