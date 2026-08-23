"""LLM Fallback Estimation Node for LangGraph Ingestion Pipeline."""

from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.schemas.ingestion import (
    FallbackMacroEstimate,
    IngestionState,
    USDANutrientProfile,
)
from app.services.langgraph.prompts import format_fallback_prompt


def get_fallback_llm() -> ChatOpenAI:
    """Instantiate OpenAI LLM for fallback macro estimations."""
    api_key = settings.OPENAI_API_KEY or "dummy_key"
    return ChatOpenAI(
        model=settings.FAST_LLM_MODEL,
        api_key=api_key,
        temperature=0.1,
    )


async def fallback_node(
    state: IngestionState, llm: Optional[Any] = None
) -> Dict[str, Any]:
    """LangGraph node to estimate per-100g nutrient profiles for items not resolved via USDA."""
    detected_items = state.get("detected_items", [])
    usda_matches: Dict[str, Optional[USDANutrientProfile]] = dict(
        state.get("usda_matches", {})
    )
    errors: List[str] = list(state.get("errors", []))

    # Identify items requiring LLM fallback
    unmatched_items = [
        item for item in detected_items if usda_matches.get(item["food_name"]) is None
    ]

    if not unmatched_items:
        return {"usda_matches": usda_matches, "errors": errors}

    model = llm or get_fallback_llm()
    structured_llm = model.with_structured_output(
        FallbackMacroEstimate, method="function_calling"
    )

    for item in unmatched_items:
        food_name = item["food_name"]
        prompt = format_fallback_prompt(
            food_name=food_name,
            cooking_method=item.get("cooking_method"),
        )

        try:
            estimate: FallbackMacroEstimate = await structured_llm.ainvoke(
                [HumanMessage(content=prompt)]
            )

            fallback_profile: USDANutrientProfile = {
                "fdc_id": None,
                "food_description": f"{food_name} (LLM Estimated)",
                "calories_100g": estimate.calories_100g,
                "protein_100g": estimate.protein_100g,
                "carbs_100g": estimate.carbs_100g,
                "fat_100g": estimate.fat_100g,
                "micronutrients_100g": estimate.estimated_micronutrients_100g or {},
            }

            usda_matches[food_name] = fallback_profile
            errors.append(
                f"USDA lookup failed for '{food_name}'; used LLM fallback estimation."
            )
        except Exception as exc:
            errors.append(
                f"LLM fallback estimation failed for '{food_name}': {str(exc)}"
            )
            usda_matches[food_name] = {
                "fdc_id": None,
                "food_description": f"{food_name} (Fallback Failed)",
                "calories_100g": 0.0,
                "protein_100g": 0.0,
                "carbs_100g": 0.0,
                "fat_100g": 0.0,
                "micronutrients_100g": {},
            }

    return {
        "usda_matches": usda_matches,
        "errors": errors,
    }
