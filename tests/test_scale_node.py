from app.schemas.ingestion import IngestionState, USDANutrientProfile, VisionItem
from app.services.langgraph.scale_node import reconciliation_node


def test_reconciliation_node_scaling_math():
    """Verify portion scaling math, totals aggregation, and micronutrient calculations."""
    chicken_profile: USDANutrientProfile = {
        "fdc_id": 171077,
        "food_description": "Grilled Chicken Breast",
        "calories_100g": 165.0,
        "protein_100g": 31.0,
        "carbs_100g": 0.0,
        "fat_100g": 3.6,
        "micronutrients_100g": {"Calcium (mg)": 15.0, "Iron (mg)": 1.0},
    }

    broccoli_profile: USDANutrientProfile = {
        "fdc_id": 169967,
        "food_description": "Steamed Broccoli",
        "calories_100g": 34.0,
        "protein_100g": 2.8,
        "carbs_100g": 7.0,
        "fat_100g": 0.4,
        "micronutrients_100g": {"Calcium (mg)": 47.0, "Vitamin C (mg)": 89.0},
    }

    detected_items = [
        VisionItem(
            food_name="Grilled Chicken Breast",
            portion_estimate="150g",
            gram_weight=150.0,
            cooking_method="grilled",
        ),
        VisionItem(
            food_name="Steamed Broccoli",
            portion_estimate="100g",
            gram_weight=100.0,
            cooking_method="steamed",
        ),
    ]

    state: IngestionState = {
        "image_bytes": b"fake",
        "image_url": None,
        "user_caption": "Chicken and broccoli",
        "detected_items": detected_items,
        "vision_confidence": 0.95,
        "usda_matches": {
            "Grilled Chicken Breast": chicken_profile,
            "Steamed Broccoli": broccoli_profile,
        },
        "reconciled_items": [],
        "total_calories": 0.0,
        "total_protein_g": 0.0,
        "total_carbs_g": 0.0,
        "total_fat_g": 0.0,
        "aggregated_nutrients": {},
        "errors": [],
    }

    result = reconciliation_node(state)

    reconciled = result["reconciled_items"]
    assert len(reconciled) == 2

    # Chicken: 1.5 * 165 = 247.5 kcal
    assert reconciled[0]["calories"] == 247.5
    assert reconciled[0]["protein_g"] == 46.5
    assert reconciled[0]["is_fallback"] is False

    # Broccoli: 1.0 * 34 = 34 kcal
    assert reconciled[1]["calories"] == 34.0
    assert reconciled[1]["carbs_g"] == 7.0

    # Total calories: 247.5 + 34 = 281.5
    assert result["total_calories"] == 281.5

    # Aggregated Calcium: 15.0 * 1.5 + 47.0 * 1.0 = 22.5 + 47 = 69.5
    assert result["aggregated_nutrients"]["Calcium (mg)"] == 69.5
    assert result["aggregated_nutrients"]["Vitamin C (mg)"] == 89.0
