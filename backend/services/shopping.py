"""
Shopping suggestions: the reply schema and the code dedupe.

Ollama constrains the shopping persona's reply to SUGGESTIONS_SCHEMA, and plain
code then keeps only new products: anything in the fridge, on the shopping list,
already shown or on the avoid list is dropped, and so are names that aren't one
product and the user's own dishes. Product names are specific, so names are
compared exactly (see fridge.same_name), not loosely.
"""

import json
import re

from services.fridge import same_name

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


def new_suggestions(items: list[dict], known: list[str], dishes: list[str] = ()) -> list[dict]:
    """Items whose names aren't already known, each name once. Names that aren't one product
    and the user's own dishes (meal names from their history, like Menemen) are left out too."""
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
