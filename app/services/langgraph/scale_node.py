"""Nutrient Reconciliation & Math Scaling Node for LangGraph Ingestion Pipeline."""

from typing import Any, Dict, List
from app.schemas.ingestion import IngestionState, ReconciledItem, USDANutrientProfile


def reconciliation_node(state: IngestionState) -> Dict[str, Any]:
    """LangGraph node to scale per-100g nutrient profiles to exact gram weights and compute meal totals."""
    detected_items = state.get("detected_items", [])
    usda_matches: Dict[str, USDANutrientProfile] = state.get("usda_matches", {})

    reconciled_items: List[ReconciledItem] = []
    total_calories = 0.0
    total_protein_g = 0.0
    total_carbs_g = 0.0
    total_fat_g = 0.0
    aggregated_nutrients: Dict[str, float] = {}

    for item in detected_items:
        food_name = item["food_name"]
        profile = usda_matches.get(food_name)

        if not profile:
            continue

        gram_weight = float(item.get("gram_weight", 100.0))
        scale_factor = gram_weight / 100.0

        item_calories = round(profile.get("calories_100g", 0.0) * scale_factor, 2)
        item_protein = round(profile.get("protein_100g", 0.0) * scale_factor, 2)
        item_carbs = round(profile.get("carbs_100g", 0.0) * scale_factor, 2)
        item_fat = round(profile.get("fat_100g", 0.0) * scale_factor, 2)
        is_fallback = profile.get("fdc_id") is None
        raw_nutrients = profile.get("micronutrients_100g", {})

        # Aggregate micronutrients scaled by portion size
        for nut_key, amount_100g in raw_nutrients.items():
            scaled_amount = round(float(amount_100g) * scale_factor, 2)
            existing = aggregated_nutrients.get(nut_key, 0.0)
            aggregated_nutrients[nut_key] = round(existing + scaled_amount, 2)

        reconciled_item: ReconciledItem = {
            "food_name": food_name,
            "fdc_id": profile.get("fdc_id"),
            "portion_amount": round(scale_factor, 2),
            "portion_unit": item.get("portion_estimate", "serving"),
            "gram_weight": gram_weight,
            "calories": item_calories,
            "protein_g": item_protein,
            "carbs_g": item_carbs,
            "fat_g": item_fat,
            "is_fallback": is_fallback,
            "raw_usda_nutrients": raw_nutrients,
        }

        reconciled_items.append(reconciled_item)

        total_calories += item_calories
        total_protein_g += item_protein
        total_carbs_g += item_carbs
        total_fat_g += item_fat

    return {
        "reconciled_items": reconciled_items,
        "total_calories": round(total_calories, 2),
        "total_protein_g": round(total_protein_g, 2),
        "total_carbs_g": round(total_carbs_g, 2),
        "total_fat_g": round(total_fat_g, 2),
        "aggregated_nutrients": aggregated_nutrients,
    }
