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
"""

import json
import re

from services.fridge import same_name

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


def shopping_request(language: str, shown: list[str] = ()) -> str:
    """The user message for the shopping call. A 7B model writing JSON follows the last message
    better than the system prompt, so it names the reply language and, for Suggest More, the
    items the user has already seen."""
    name = "English" if language == "en" else "Turkish"
    if not shown:
        return f"Generate shopping suggestions for me, in {name}."
    return (
        f"Generate more shopping suggestions for me, in {name}, all different from these, "
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
