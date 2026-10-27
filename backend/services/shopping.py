"""
Shopping suggestions: the reply schema and the code dedupe.

Ollama constrains the shopping persona's reply to SUGGESTIONS_SCHEMA, and plain
code then keeps only new items: anything in the fridge, on the shopping list,
already shown or on the avoid list is dropped. Product names are specific, so
names are compared exactly (see fridge.same_name), not loosely.
"""

import json

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


def new_suggestions(items: list[dict], known: list[str]) -> list[dict]:
    """Items whose names aren't already known, each name once."""
    seen = list(known)
    result = []
    for item in items:
        if any(same_name(item["name"], k) for k in seen):
            continue
        seen.append(item["name"])
        result.append(item)
    return result
