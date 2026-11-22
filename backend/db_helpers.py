"""
Shared database helper functions.

Provides reusable JSON field parsing and serialization used across
multiple routers (meals, favorites, suggestions), and the chat session ownership check.
"""

import json

_SENTINEL = object()


def parse_json_field(value, default=_SENTINEL):
    """Safely decode a JSON-encoded DB field, returning `default` on failure.

    If no default is provided, returns [].
    Pass default=None explicitly to get None for empty/missing fields.
    """
    if not value:
        return [] if default is _SENTINEL else default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return [] if default is _SENTINEL else default


def serialize_json_field(value) -> str:
    """Serialize a list/dict to JSON for DB storage — handles Pydantic models."""
    if not value:
        return "[]"
    serialized = []
    for item in value:
        if hasattr(item, "model_dump"):
            serialized.append(item.model_dump())
        else:
            serialized.append(item)
    return json.dumps(serialized, ensure_ascii=False)


async def owns_session(db, session_id: str, user_id: int) -> bool:
    """True when the chat session exists and belongs to the user (session ids come from the client)."""
    async with db.execute(
        "SELECT 1 FROM chat_sessions WHERE id = ? AND user_id = ?", (session_id, user_id)
    ) as cur:
        return await cur.fetchone() is not None


def row_to_meal(row) -> dict:
    """Convert a raw DB row to a dict with JSON list fields decoded."""
    d = dict(row)
    d["ingredients"] = parse_json_field(d.get("ingredients"), [])
    d["steps"] = parse_json_field(d.get("steps"), [])
    d["schedule"] = parse_json_field(d.get("schedule"), None)
    d["cached_nutrition"] = parse_json_field(d.get("cached_nutrition"), None)
    d["menu_items"] = parse_json_field(d.get("menu_items"), None)
    return d


def row_to_favorite(row) -> dict:
    """Convert a favorite_meals DB row to a dict with JSON fields decoded."""
    d = dict(row)
    d.pop("user_id", None)  # the account's id stays on the server
    for field in ("ingredients", "steps"):
        d[field] = parse_json_field(d.get(field), [])
    d["menu_items"] = parse_json_field(d.get("menu_items"), None)
    return d
