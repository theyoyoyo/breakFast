"""
Shopping suggestions: the reply schema and the code dedupe.

Ollama constrains the shopping persona's reply to SUGGESTIONS_SCHEMA, and plain
code then keeps only new products: anything in the fridge, on the shopping list,
already shown or on the avoid list is dropped, and so are names that aren't one
product and the user's own dishes (a safety net: the prompt asks for a dish's
ingredients instead of the dish). Product names are specific, so names are
compared exactly (see fridge.same_name), not loosely.

Items the user removed from the suggestions list with × are left out for
REMOVED_DAYS (recently_removed); after that they may come back. The avoid list is
the permanent ban.

Each press shows the model a random share of the fridge and of the user's taste
hints (pick_input), so suggestions start from a different place each time. Code
still drops anything in the whole fridge.
"""

import json
import random
import re

from services.fridge import same_name
from services.knowledge import format_favorite_meal

# A suggestion removed with × stays out of new suggestions this long
REMOVED_DAYS = 7

SUGGESTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["name", "reason"],
            },
        },
    },
    "required": ["items"],
}


def parse_suggestions(reply: str) -> list[dict] | None:
    """The items of a schema-shaped reply, or None when the reply isn't one."""
    try:
        data = json.loads(reply)
    except (json.JSONDecodeError, TypeError):
        return None
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            result.append({"name": name, "reason": str(item.get("reason") or "").strip()})
    return result


# The share of the fridge items and of the taste hints one press shows
INPUT_SHARE = 0.7
# Ratings at or above this are taste hints; at or below LOW_RATING they're limits (as in format_ratings)
HIGH_RATING, LOW_RATING = 7, 4


def random_share(items: list, rng: random.Random, share: float = INPUT_SHARE) -> list:
    """A random ~70% of the items in random order, at least one when there are any."""
    return rng.sample(items, max(1, round(len(items) * share))) if items else []


def taste_hints(ctx: dict) -> list[str]:
    """Every hint about what the user enjoys, one line each: liked items, staples, saved favorite
    meals with their items, habits, behavior patterns and high-rated items."""
    prefs = ctx.get("preferences") or {}
    hints = [f"Likes {v}" for k, v in prefs.items() if k.startswith("fav:")]
    hints += [f"Keeps around: {s}" for s in ctx.get("favorites") or []]
    hints += [f"Saved favorite meal: {format_favorite_meal(m)}" for m in ctx.get("favorite_meals") or []]
    hints += [f"Habit: {h}" for h in ctx.get("stated_habits") or []]
    hints += [f"Pattern: {h}" for h in ctx.get("inferred_habits") or []]
    hints += [
        f"Rated {r['rating']}/10: {r['product_name']}" for r in ctx.get("ratings") or []
        if r.get("rating", 0) >= HIGH_RATING
    ]
    return hints


def pick_input(ctx: dict, rng: random.Random) -> tuple[list[str], list[str]]:
    """One press's fridge items and taste hints, a random share of each. Limits (health rules,
    avoid list, dislikes, low ratings) aren't drawn: the prompt always has them."""
    fridge = random_share([i["name"] for i in ctx["ingredients"]], rng)
    return fridge, random_share(taste_hints(ctx), rng)


def shopping_request(language: str, shown: list[str] = (), fridge: list[str] = ()) -> str:
    """The user message for the shopping call. A 7B model writing JSON follows the last message
    better than the system prompt, so it lists this press's share of the fridge and names the
    reply language and, for Suggest More, the items the user has already seen."""
    name = "English" if language == "en" else "Turkish"
    have = f"Some of what I have now: {', '.join(fridge)}.\n" if fridge else ""
    if not shown:
        return f"{have}Generate shopping suggestions for me, in {name}."
    return (
        f"{have}Generate more shopping suggestions for me, in {name}, all different from these, "
        f"which I've already seen: {', '.join(shown)}."
    )


# A name that is not one product: alternatives or examples ("Leafy greens (e.g. spinach)", "Milk or yogurt")
_NOT_ONE_PRODUCT = re.compile(r"[(/]|\be\.?g\b|\bor\b", re.IGNORECASE)


def _names(items) -> list[str]:
    return [str(i.get("name") or "") if isinstance(i, dict) else str(i) for i in items or []]


def dish_names(meals: list[dict]) -> list[str]:
    """The user's own dishes, from their logged and favorite meals: each meal's name and every
    menu item made with ingredients (Menemen). A simple item is one product served as it is, so
    it stays a product, and so does a name that is one of its own ingredients (a meal called Simit)."""
    dishes = []
    for meal in meals:
        menu = [i for i in meal.get("menu_items") or [] if isinstance(i, dict)]
        parts = _names(meal.get("ingredients")) + _names(menu) + [n for i in menu for n in _names(i.get("ingredients"))]
        candidates = [(meal.get("meal_name"), parts)]
        candidates += [(i.get("name"), _names(i["ingredients"])) for i in menu if i.get("ingredients")]
        for name, own in candidates:
            name = str(name or "").strip()
            if name and name not in dishes and not any(same_name(name, p) for p in own):
                dishes.append(name)
    return dishes


def new_suggestions(items: list[dict], known: list[str], dishes: list[str] = ()) -> list[dict]:
    """Items whose names aren't already known, each name once. Names that aren't one product
    and the user's own dishes (see dish_names) are left out too."""
    seen = list(known)
    result = []
    for item in items:
        name = item["name"]
        if _NOT_ONE_PRODUCT.search(name) or any(same_name(name, d) for d in dishes):
            continue
        if any(same_name(name, k) for k in seen):
            continue
        seen.append(item["name"])
        result.append(item)
    return result


async def recently_removed(db, user_id: int) -> list[str]:
    """Names the user removed from the suggestions list in the last REMOVED_DAYS days."""
    async with db.execute(
        """SELECT name FROM shopping_suggestions
           WHERE user_id = ? AND removed_at >= datetime('now', ?)""",
        (user_id, f"-{REMOVED_DAYS} days"),
    ) as cur:
        return [r["name"] for r in await cur.fetchall()]
