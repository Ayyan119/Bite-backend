"""Centralized prompt templates for LangGraph LLM nodes.

Enforces zero prompt scatter and clean maintainability across Vision and Fallback nodes.
"""

from typing import Optional

VISION_SYSTEM_PROMPT = """You are an expert computer vision clinical nutritionist.
Your task is to analyze the provided image of a meal alongside any user caption.
Identify every distinct food component present, estimate its portion weight in grams, human-readable portion description, and preparation/cooking method.

User caption context: "{user_caption}"

Rules:
1. If user caption specifies a specific food variant (e.g. "whole wheat bread"), prioritize that over visual ambiguity.
2. Provide gram weights based on standard visual portion estimation guidelines.
3. Be precise with cooking methods (e.g., "deep-fried", "pan-seared", "steamed", "raw")."""


FALLBACK_SYSTEM_PROMPT = """You are a USDA food database specialist and nutritional science expert.
A specific food item was not found in the USDA FoodData Central database.
Provide your best scientifically accurate estimation of its nutritional profile PER 100 GRAMS.

Food Item: {food_name}
Cooking Method: {cooking_method}

Provide per-100g values for Calories, Protein (g), Carbohydrates (g), Total Fat (g), and major micronutrients (Sodium mg, Potassium mg, Calcium mg, Iron mg, Vitamin C mg, Vitamin A mcg)."""


def format_vision_prompt(
    user_caption: Optional[str] = None, current_time: Optional[str] = None
) -> str:
    """Format vision system prompt with optional user caption context."""
    caption_text = user_caption.strip() if user_caption else "None provided"
    return VISION_SYSTEM_PROMPT.format(user_caption=caption_text)


def format_fallback_prompt(food_name: str, cooking_method: Optional[str] = None) -> str:
    """Format fallback system prompt for unlisted food items."""
    method_text = cooking_method.strip() if cooking_method else "raw/unknown"
    return FALLBACK_SYSTEM_PROMPT.format(
        food_name=food_name.strip(), cooking_method=method_text
    )
