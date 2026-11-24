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


def capitalize_words(name: str, language: str = "en") -> str:
    """A new fridge item's name with a capital first letter on every word ("greek yogurt" → "Greek
    Yogurt", #285). Only a lowercase first letter changes, so the rest of a word stays as written
    ("BBQ" stays); Turkish capitalizes "i" as "İ"."""
    def cap(word: str) -> str:
        if not word or not word[0].islower():
            return word
        first = "İ" if language == "tr" and word[0] == "i" else word[0].upper()
        return first + word[1:]
    return " ".join(cap(word) for word in name.split(" "))


async def fridge_names(db, user_id: int, names: list[str]) -> dict[str, str]:
    """The name each new fridge item is stored under: the user's item of that name when there is one
    (any case, so a re-added "yumurta" updates "Yumurta" instead of adding a second row), else the
    name with capital first letters in the user's reply language."""
    async with db.execute("SELECT name FROM ingredient_inventory WHERE user_id = ?", (user_id,)) as cur:
        have = {row["name"].casefold(): row["name"] for row in await cur.fetchall()}
    async with db.execute(
        "SELECT value FROM user_preferences WHERE user_id = ? AND key = 'response_language'", (user_id,),
    ) as cur:
        row = await cur.fetchone()
    language = row["value"] if row else "en"
    stored = {}
    for name in names:
        written = capitalize_words(name, language)
        stored[name] = have.get(written.casefold()) or have.get(name.casefold()) or written
    return stored
