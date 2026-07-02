"""Enrich dishes with real recipes from TheMealDB (free, permits attribution use).

TheMealDB gives ingredients + measures + full instructions for the dishes it
covers (~300). We look a dish up by name; if found, we attach the recipe.
"""
from __future__ import annotations

from .common import RateLimiter, get_json

# Test key "1" is fine for open/non-commercial use per TheMealDB.
SEARCH_URL = "https://www.themealdb.com/api/json/v1/1/search.php"

_limiter = RateLimiter(0.5)


def fetch_recipe(session, name: str) -> dict | None:
    """Return a normalized recipe dict for `name`, or None if not found."""
    data = get_json(session, SEARCH_URL, params={"s": name}, limiter=_limiter)
    if not data or not data.get("meals"):
        return None
    meal = data["meals"][0]

    ingredients = []
    for i in range(1, 21):
        ing = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}") or "").strip()
        if ing:
            ingredients.append({"ingredient": ing, "measure": measure})

    return {
        "source": "TheMealDB",
        "source_id": meal.get("idMeal"),
        "category": meal.get("strCategory"),
        "area": meal.get("strArea"),           # extra nationality signal
        "instructions": (meal.get("strInstructions") or "").strip(),
        "ingredients": ingredients,
        "youtube": meal.get("strYoutube") or "",
        "thumb": meal.get("strMealThumb") or "",  # candidate image
    }
