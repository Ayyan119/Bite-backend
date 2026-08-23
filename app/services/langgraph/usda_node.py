"""Async USDA Resolver Node for LangGraph Ingestion Pipeline."""

import asyncio
from typing import Any, Dict, Optional

from app.schemas.ingestion import IngestionState, USDANutrientProfile
from app.tools.usda import USDAService


async def usda_resolver_node(
    state: IngestionState, usda_service: Optional[USDAService] = None
) -> Dict[str, Any]:
    """LangGraph node to resolve detected food items against USDA API concurrently."""
    detected_items = state.get("detected_items", [])
    errors: list[str] = list(state.get("errors", []))

    if not detected_items:
        return {"usda_matches": {}, "errors": errors}

    service = usda_service or USDAService()

    # Parallel lookups for all detected items
    tasks = [
        service.resolve_food_item(
            food_name=item["food_name"],
            cooking_method=item.get("cooking_method"),
        )
        for item in detected_items
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    usda_matches: Dict[str, Optional[USDANutrientProfile]] = {}

    for item, result in zip(detected_items, results):
        food_name = item["food_name"]
        if isinstance(result, Exception):
            usda_matches[food_name] = None
            errors.append(f"USDA lookup error for '{food_name}': {str(result)}")
        else:
            usda_matches[food_name] = result

    return {
        "usda_matches": usda_matches,
        "errors": errors,
    }
