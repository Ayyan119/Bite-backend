import asyncio
import logging
from typing import Any, Dict, List, Optional
from cachetools import TTLCache
from langchain_core.tools import tool
from app.tools.usda import USDAService, USDANutrientProfile

logger = logging.getLogger(__name__)

# In-memory LRU Cache for USDA items with 1-hour TTL
usda_cache: TTLCache[str, Optional[USDANutrientProfile]] = TTLCache(
    maxsize=1000, ttl=3600
)
_usda_service_instance: Optional[USDAService] = None


def get_usda_service() -> USDAService:
    """Singleton getter for USDAService."""
    global _usda_service_instance
    if _usda_service_instance is None:
        _usda_service_instance = USDAService()
    return _usda_service_instance


async def fetch_single_usda_food(
    food_name: str, cooking_method: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetches USDA profile for a single food item with TTLCache lookup.
    """
    clean_name = food_name.lower().strip()
    cache_key = f"{clean_name}:{cooking_method or ''}"

    if cache_key in usda_cache:
        cached_profile = usda_cache[cache_key]
        if cached_profile:
            return {"found": True, "query": food_name, "profile": cached_profile}
        return {"found": False, "query": food_name, "profile": None}

    service = get_usda_service()
    profile = await service.resolve_food_item(food_name, cooking_method)

    usda_cache[cache_key] = profile

    if profile:
        return {"found": True, "query": food_name, "profile": profile}
    return {"found": False, "query": food_name, "profile": None}


@tool
async def search_usda_food(queries: List[str]) -> List[Dict[str, Any]]:
    """
    Searches the USDA FoodData Central database concurrently for a list of food queries.
    Returns nutritional profiles for matched items, or marks unmatched items (e.g. regional dishes)
    as not found so the LLM agent can apply internal culinary estimation.
    """
    if not queries:
        return []

    tasks = [fetch_single_usda_food(q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    formatted_results = []
    for q, res in zip(queries, results):
        if isinstance(res, Exception):
            logger.error(f"Error fetching USDA food for '{q}': {res}")
            formatted_results.append(
                {"found": False, "query": q, "profile": None, "error": str(res)}
            )
        else:
            formatted_results.append(res)

    return formatted_results
