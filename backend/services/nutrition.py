"""
Nutrition data service.
Primary: Open Food Facts API (global, free, no API key required, good Turkish coverage).
Fallback: LLM estimation (marked as approximate).
"""

import httpx
from typing import Optional

from config import NUTRITION_USER_AGENT, OPEN_FOOD_FACTS_BASE_URL


async def get_nutrition(ingredient_name: str) -> dict:
    """
    Look up nutrition data for an ingredient.
    Returns a dict with keys: name, calories, protein_g, fat_g, carbs_g, source.
    source is 'open_food_facts' or 'estimated'.
    """
    result = await _fetch_from_off(ingredient_name)
    if result:
        return result

    # Fallback — return a placeholder that signals LLM estimation is needed
    return {
        "name": ingredient_name,
        "calories": None,
        "protein_g": None,
        "fat_g": None,
        "carbs_g": None,
        "source": "estimated",
        "note": f"Nutrition for '{ingredient_name}' not found; values are LLM estimates.",
    }


async def _fetch_from_off(ingredient_name: str) -> Optional[dict]:
    """Query Open Food Facts search API."""
    headers = {"User-Agent": NUTRITION_USER_AGENT}
    params = {
        "search_terms": ingredient_name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 1,
        "fields": "product_name,nutriments",
    }
    url = f"{OPEN_FOOD_FACTS_BASE_URL}/cgi/search.pl"

    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None

    products = data.get("products", [])
    if not products:
        return None

    p = products[0]
    n = p.get("nutriments", {})
    return {
        "name": p.get("product_name", ingredient_name),
        "calories": n.get("energy-kcal_100g"),
        "protein_g": n.get("proteins_100g"),
        "fat_g": n.get("fat_100g"),
        "carbs_g": n.get("carbohydrates_100g"),
        "source": "open_food_facts",
    }
