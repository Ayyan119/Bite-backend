"""Centralized prompt templates for LangGraph LLM nodes.

Enforces zero prompt scatter and clean maintainability across Vision and Fallback nodes.
"""

from typing import Optional

VISION_SYSTEM_PROMPT = """You are an expert computer vision clinical nutritionist.
Your task is to analyze the provided image of a meal alongside any user caption.

User caption context: "{user_caption}"

Rules:
1. FOOD IDENTIFICATION STRICTNESS:
   - Determine if the image contains edible human food or beverages.
   - If the image depicts non-food items, grass, plants, animals, objects, cars, furniture, or an empty plate, set is_food = False, set detected_items = [], and set confidence_score = 0.0. Do NOT detect food in non-food images.

2. CAPTION VS IMAGE MATCHING:
   - If user_caption is provided (and not "None provided"), evaluate the semantic agreement between the visual content in the image and the user caption.
   - Assign caption_match_score from 0.0 (complete mismatch) to 1.0 (exact match).
   - If the caption describes a completely different item than what is visually shown (e.g. image shows grass or banana, but caption says "Chicken Biryani"), set caption_match_score < 0.6 and explain the discrepancy in caption_mismatch_reason.
   - Always prioritize the actual visual content in the image for food item extraction.

3. PORTION & PREPARATION ESTIMATION:
   - For valid food items detected, estimate portion weight in grams, human-readable portion description, and cooking method (e.g., "fried", "steamed", "grilled", "raw")."""


FALLBACK_SYSTEM_PROMPT = """You are a USDA food database specialist and nutritional science expert.
A specific food item was not found in the USDA FoodData Central database.
Provide your best scientifically accurate estimation of its nutritional profile PER 100 GRAMS.

Food Item: {food_name}
Cooking Method: {cooking_method}

Provide per-100g values for Calories, Protein (g), Carbohydrates (g), Total Fat (g), and major micronutrients (Sodium mg, Potassium mg, Calcium mg, Iron mg, Vitamin C mg, Vitamin A mcg)."""


def format_vision_prompt(user_caption: Optional[str] = None) -> str:
    """Format vision system prompt with optional user caption context."""
    caption_text = user_caption.strip() if user_caption else "None provided"
    return VISION_SYSTEM_PROMPT.format(user_caption=caption_text)


def format_fallback_prompt(food_name: str, cooking_method: Optional[str] = None) -> str:
    """Format fallback system prompt for unlisted food items."""
    method_text = cooking_method.strip() if cooking_method else "raw/unknown"
    return FALLBACK_SYSTEM_PROMPT.format(
        food_name=food_name.strip(), cooking_method=method_text
    )
