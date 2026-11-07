"""
The chat a Suggest press reads (#161).

The server builds it from the session's saved messages, so every device and reload sends the
same thing: one block in chat order, oldest first and the latest last. It holds the user's typed
messages (never the Suggest buttons' own text) and the meal cards in the chat as they are now,
edits included. Nothing else the app wrote (chat replies, analyses, prep plans) goes in. The
draft and the reviser both get the block, placed last in their message.

The chat persona reads the same session as its history, with each meal card as its one line, and
its reply loses any meal block before it is saved: meal cards come only from a Suggest press (#168).
"""

from services.fridge import meal_ingredient_names
from utils import extract_json_block

# What the Suggest button sends per mode, mirrored in the frontend (ChatInterface.jsx,
# handleSuggest). A press saves this text as a user message, and it is no wish of the user's.
SUGGEST_MESSAGES = {
    None: "Suggest Breakfast",
    "favorites": "Suggest breakfast from my favorite meals",
    "explore": "Suggest a different breakfast from world cuisines",
}
_BUTTON_TEXTS = set(SUGGEST_MESSAGES.values())

# Only a chat longer than this (about 1,500-2,000 tokens) loses its oldest entries, so the draft
# and the reviser still fit in the 8,192-token context (OLLAMA_NUM_CTX) with their replies.
CHAT_BLOCK_CHARS = 6000

CHAT_HEADER = """\
THE CHAT SO FAR, numbered in chat order (oldest first, the latest last). These are the user's \
own words about this breakfast, so they come before their habits, favorites and patterns; health \
rules and the avoid list still hold.
- A later message wins over an earlier one it disagrees with, and a message right after a menu \
is about that menu. Every other message still counts.
- Whatever the chat asks for (a time, a food, a mood) holds for every menu from here on, as \
closely as the fridge allows, until a later message changes it.
- A new menu differs from the menus shown here, unless the user asks for one again."""


def _card_line(meal: dict) -> str:
    """A meal card as one line: its name, its dishes and the items it uses, each once."""
    name = str(meal.get("menu_name") or meal.get("meal_name") or "Unnamed menu").strip()
    dishes = [
        str(item.get("name", "")).strip()
        for item in meal.get("menu") or []
        if isinstance(item, dict) and item.get("ingredients") and str(item.get("name", "")).strip()
    ]
    items = list(dict.fromkeys(meal_ingredient_names(meal)))
    parts = [f"Menu shown: {name}."]
    if dishes:
        parts.append(f"Dishes: {', '.join(dishes)}.")
    parts.append(f"Items: {', '.join(items) or 'none listed'}")
    return " ".join(parts)


def _meal_card(content: str) -> dict | None:
    meal = extract_json_block(content)
    if not isinstance(meal, dict):
        return None
    if isinstance(meal.get("menu"), list) and meal["menu"] or isinstance(meal.get("ingredients"), list):
        return meal
    return None


def chat_entries(rows: list[dict]) -> list[str]:
    """The session's messages (oldest first) as the block's lines: typed messages and meal cards.
    The user's latest typed message is marked, since it wins over earlier ones."""
    entries, latest = [], None
    for row in rows:
        content = str(row.get("content") or "").strip()
        if row.get("role") == "user":
            if content and content not in _BUTTON_TEXTS:
                latest = len(entries)
                entries.append(f"User: {content}")
        else:
            meal = _meal_card(content)
            if meal:
                entries.append(_card_line(meal))
    if latest is not None:
        entries[latest] = "User (latest message): " + entries[latest].removeprefix("User: ")
    return entries


def format_chat_block(rows: list[dict]) -> str | None:
    """The chat block a Suggest press sends to the draft and the reviser, or None for a chat with
    no typed message and no meal card. A chat too long for the context loses its oldest entries.
    The entries are numbered in chat order, so the reviser can say which entries each ask comes
    from, and a later message that changes an earlier one is read together with it."""
    entries = chat_entries(rows)
    if not entries:
        return None
    kept, size = [], 0
    for entry in reversed(entries):
        size += len(entry) + 8  # "- #12 " and the newline
        if kept and size > CHAT_BLOCK_CHARS:
            break
        kept.append(entry[:CHAT_BLOCK_CHARS])
    lines = "\n".join(f"- #{n} {e}" for n, e in enumerate(reversed(kept), start=1))
    return f"{CHAT_HEADER}\n\n{lines}"


async def load_chat_block(db, session_id: str, user_id: int) -> str | None:
    """The chat block of the user's session, from its saved messages in chat order."""
    async with db.execute(
        "SELECT role, content FROM chat_messages WHERE session_id = ? AND user_id = ? ORDER BY id",
        (session_id, user_id),
    ) as cur:
        rows = await cur.fetchall()
    return format_chat_block([{"role": r["role"], "content": r["content"]} for r in rows])


# What a chat reply says when it was nothing but a meal block: the menu comes from a Suggest press
CHAT_SUGGEST_TEXTS = {
    "en": "Tap Suggest when you're ready, and the menu will follow what you told me.",
    "tr": "Hazır olduğunuzda Suggest düğmesine basın, menü yazdıklarınıza göre hazırlanır.",
}
_FENCE = "```json"


def chat_history(rows: list[dict]) -> list[dict]:
    """The session's messages as the chat persona's history: each meal card becomes its one line
    after the reply's own text, so the chat knows which menus were shown but has no meal JSON to
    copy into its reply (the 7B model copied it into every reply after a Suggest press)."""
    history = []
    for row in rows:
        content = str(row.get("content") or "")
        meal = _meal_card(content) if row.get("role") == "assistant" else None
        if meal:
            text = content.split(_FENCE, 1)[0].strip()
            content = "\n\n".join(part for part in (text, _card_line(meal)) if part)
        history.append({"role": row.get("role"), "content": content})
    return history


def drop_meal_block(reply: str) -> str:
    """A chat reply without its meal block, cut where the app stops showing it while it streams
    (ChatInterface.jsx, stripStreamingJsonBlock), so a chat reply never becomes a meal card."""
    return reply.split(_FENCE, 1)[0].rstrip()
