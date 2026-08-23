"""USDA FoodData Central API Service & Resolver Tool."""

import os
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.schemas.ingestion import USDANutrientProfile


def compute_match_score(query: str, description: str) -> float:
    """Calculate token overlap match score between query string and USDA description (0.0 to 1.0)."""
    if not query or not description:
        return 0.0

    query_tokens = set(query.lower().replace(",", " ").replace("-", " ").split())
    desc_tokens = set(description.lower().replace(",", " ").replace("-", " ").split())

    if not query_tokens:
        return 0.0

    overlap = query_tokens.intersection(desc_tokens)
    return len(overlap) / len(query_tokens)


def extract_100g_profile(usda_food: Dict[str, Any]) -> USDANutrientProfile:
    """Extract per-100g calories, macros, and micronutrients from USDA FoodData Central item."""
    fdc_id = usda_food.get("fdcId")
    description = usda_food.get("description", "Unknown Food")

    calories_100g = 0.0
    protein_100g = 0.0
    carbs_100g = 0.0
    fat_100g = 0.0
    micronutrients_100g: Dict[str, float] = {}

    nutrients = usda_food.get("foodNutrients", [])
    for nut in nutrients:
        nut_id = nut.get("nutrientId") or nut.get("nutrient", {}).get("id")
        nut_name = nut.get("nutrientName") or nut.get("nutrient", {}).get("name") or ""
        amount = float(nut.get("value") or nut.get("amount") or 0.0)
        unit = (
            nut.get("unitName") or nut.get("nutrient", {}).get("unitName") or "g"
        ).lower()

        # Map standard macros
        if nut_id in (1008, 208) or "energy" in nut_name.lower():
            if unit == "kcal":
                calories_100g = amount
            elif unit == "kj" and calories_100g == 0.0:
                calories_100g = round(amount / 4.184, 2)
            elif calories_100g == 0.0:
                calories_100g = amount
        elif nut_id in (1003, 203) or nut_name.lower() == "protein":
            protein_100g = amount
        elif nut_id in (1005, 205) or "carbohydrate" in nut_name.lower():
            carbs_100g = amount
        elif nut_id in (1004, 204) or "total lipid" in nut_name.lower():
            fat_100g = amount
        else:
            if nut_name and amount > 0:
                key = f"{nut_name} ({unit})"
                micronutrients_100g[key] = amount

    return {
        "fdc_id": fdc_id,
        "food_description": description,
        "calories_100g": round(calories_100g, 2),
        "protein_100g": round(protein_100g, 2),
        "carbs_100g": round(carbs_100g, 2),
        "fat_100g": round(fat_100g, 2),
        "micronutrients_100g": micronutrients_100g,
    }


_shared_httpx_client: Optional[httpx.AsyncClient] = None
_usda_search_cache: Dict[str, List[Dict[str, Any]]] = {}


def get_shared_httpx_client() -> httpx.AsyncClient:
    """Return a shared singleton AsyncClient with connection pooling."""
    global _shared_httpx_client
    if _shared_httpx_client is None or _shared_httpx_client.is_closed:
        _shared_httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
    return _shared_httpx_client


class USDAService:
    """Async Client service for USDA FoodData Central search API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self._api_key = api_key
        self.base_url = (base_url or settings.USDA_API_BASE_URL).rstrip("/")
        self._client = client

    @property
    def api_key(self) -> str:
        if self._api_key and self._api_key != "DEMO_KEY":
            return self._api_key
        env_key = os.getenv("USDA_API_KEY")
        if env_key and env_key != "DEMO_KEY":
            return env_key
        return settings.USDA_API_KEY or "DEMO_KEY"

    async def search_food(self, query: str, page_size: int = 3) -> List[Dict[str, Any]]:
        """Query USDA FoodData Central search API with query caching and connection pooling."""
        clean_query = query.lower().strip()
        cache_key = f"{clean_query}:{page_size}"
        if cache_key in _usda_search_cache:
            return _usda_search_cache[cache_key]

        url = f"{self.base_url}/foods/search"
        params = {
            "api_key": self.api_key,
            "query": clean_query,
            "pageSize": page_size,
        }

        client = self._client or get_shared_httpx_client()
        response = await client.get(url, params=params)

        if response.status_code in (403, 404) and params.get("api_key") != "DEMO_KEY":
            params["api_key"] = "DEMO_KEY"
            response = await client.get(url, params=params)

        response.raise_for_status()
        data = response.json()
        foods = data.get("foods", [])
        _usda_search_cache[cache_key] = foods
        return foods

    async def resolve_food_item(
        self, food_name: str, cooking_method: Optional[str] = None
    ) -> Optional[USDANutrientProfile]:
        """Search USDA and return matched 100g nutrient profile if match score >= 0.6."""
        queries_to_try = [food_name]
        if cooking_method:
            queries_to_try.append(f"{cooking_method} {food_name}")

        try:
            for query in queries_to_try:
                foods = await self.search_food(query)
                if not foods:
                    continue

                best_match = None
                best_score = 0.0

                for food in foods:
                    desc = food.get("description", "")
                    score = compute_match_score(food_name, desc)
                    if score > best_score:
                        best_score = score
                        best_match = food

                if best_match and best_score >= 0.6:
                    return extract_100g_profile(best_match)

            return None
        except Exception:
            return None
