"""Tests for the chat block a Suggest press reads from the session (#161), and the chat persona's
view of the same session (#168)."""

import json

from services.chat_block import (
    CHAT_BLOCK_CHARS, CHAT_HEADER, SUGGEST_MESSAGES, chat_entries, chat_history, drop_meal_block, format_chat_block,
    load_chat_block,
)


def _card(meal: dict, text: str = "A breakfast for you.") -> str:
    return f"{text}\n\n```json\n{json.dumps(meal)}\n```"


PLATE = {
    "menu_name": "Breakfast plate",
    "menu": [
        {"name": "Scrambled eggs", "ingredients": [
            {"name": "Eggs", "amount": 2, "unit": "pcs"}, {"name": "Butter", "amount": 1, "unit": "tsp"},
        ]},
        {"name": "Cucumber", "amount": 1, "unit": "pcs", "ingredients": []},
    ],
}


def _user(text: str) -> dict:
    return {"role": "user", "content": text}


def _app(text: str) -> dict:
    return {"role": "assistant", "content": text}


# The block keeps typed messages and meal cards in chat order, numbered, and leaves out button text and every other app reply
def test_block_has_typed_messages_and_cards_only():
    rows = [
        _user(SUGGEST_MESSAGES[None]),
        _app(_card(PLATE)),
        _user("Too heavy, and no butter."),
        _app("Sure, something lighter then!"),
        _app("📊 Breakfast plate — Nutrition Analysis\n\nAbout 450 kcal."),
        _app("📋 Breakfast plate — Prep Plan\n\n⏱ Plan (10 min)"),
        _user(SUGGEST_MESSAGES["favorites"]),
        _app("No meal this time, add a few items in the Fridge tab."),
        _user("I only have 10 minutes."),
        _user(SUGGEST_MESSAGES["explore"]),
    ]
    assert chat_entries(rows) == [
        "Menu shown: Breakfast plate. Dishes: Scrambled eggs. Items: Eggs, Butter, Cucumber",
        "User: Too heavy, and no butter.",
        "User (latest message): I only have 10 minutes.",
    ]
    assert format_chat_block(rows) == (
        f"{CHAT_HEADER}\n\n"
        "- #1 Menu shown: Breakfast plate. Dishes: Scrambled eggs. Items: Eggs, Butter, Cucumber\n"
        "- #2 User: Too heavy, and no butter.\n"
        "- #3 User (latest message): I only have 10 minutes."
    )


# Only the latest typed message is marked, even when a menu comes after it; a card alone still makes a block
def test_latest_typed_message_is_marked():
    rows = [_user("No eggs."), _user("Something sweet."), _app(_card(PLATE))]
    assert chat_entries(rows)[:2] == ["User: No eggs.", "User (latest message): Something sweet."]
    assert chat_entries([_app(_card(PLATE))]) == [
        "Menu shown: Breakfast plate. Dishes: Scrambled eggs. Items: Eggs, Butter, Cucumber",
    ]


# The header says the user's words come first, the later message wins, asks last until changed, and menus don't repeat
def test_header_states_the_rules():
    assert "come before their habits, favorites and patterns" in CHAT_HEADER
    assert "health rules and the avoid list still hold" in CHAT_HEADER
    assert "A later message wins over an earlier one" in CHAT_HEADER
    assert "a message right after a menu is about that menu" in CHAT_HEADER
    assert "holds for every menu from here on" in CHAT_HEADER
    assert "differs from the menus shown here" in CHAT_HEADER
    assert "numbered in chat order" in CHAT_HEADER


# A chat with nothing typed and no card sends no block, and an old flat meal or an unreadable block is handled
def test_empty_chat_and_old_cards():
    assert format_chat_block([]) is None
    assert format_chat_block([_user(SUGGEST_MESSAGES[None]), _app("Hello!")]) is None
    assert format_chat_block([_app("```json\n{broken\n```"), _app('```json\n{"score": 3}\n```')]) is None
    flat = {"meal_name": "Toast", "ingredients": [{"name": "Bread"}, {"name": "Cheese"}]}
    assert chat_entries([_app(_card(flat))]) == ["Menu shown: Toast. Items: Bread, Cheese"]


# Only a chat too long for the context loses entries, the oldest first, the kept ones numbered from 1, and the latest always stays
def test_long_chat_loses_its_oldest_entries():
    rows = [_user(f"Message {i}: " + "x" * 200) for i in range(60)]
    block = format_chat_block(rows)
    assert len(block) <= len(CHAT_HEADER) + CHAT_BLOCK_CHARS + 2
    assert "Message 59" in block and "Message 0:" not in block
    kept = block.split("\n\n", 1)[1].splitlines()
    assert [int(line.split("Message ")[1].split(":")[0]) for line in kept] == list(range(60 - len(kept), 60))
    assert kept[0].startswith("- #1 User: ") and kept[-1].startswith(f"- #{len(kept)} User (latest message): ")
    assert format_chat_block([_user("y" * (CHAT_BLOCK_CHARS * 2))]).endswith("y" * 100)


# The server reads the user's own session in chat order, with a meal card as it is after an edit
async def test_load_reads_the_session_with_card_edits(client, db):
    session_id = (await client.post("/sessions/")).json()["session_id"]
    await client.post(f"/sessions/{session_id}/messages", json={"role": "user", "content": "No butter please."})
    card_id = (await client.post(f"/sessions/{session_id}/messages", json={"content": _card(PLATE)})).json()["id"]
    edited = {**PLATE, "menu_name": "Light plate", "menu": PLATE["menu"][1:]}
    await client.put(f"/sessions/{session_id}/messages/{card_id}", json={"content": _card(edited)})
    await client.post(f"/sessions/{session_id}/messages", json={"role": "user", "content": SUGGEST_MESSAGES[None]})
    await db.execute("INSERT INTO users (name, pin_hash) VALUES ('other', 'x')")
    await db.execute(
        "INSERT INTO chat_messages (session_id, user_id, role, content) "
        "SELECT ?, id, 'user', 'Not my message.' FROM users WHERE name = 'other'",
        (session_id,),
    )
    await db.commit()
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        user_id = (await cur.fetchone())[0]

    block = await load_chat_block(db, session_id, user_id)
    assert block.split("\n\n", 1)[1].splitlines() == [
        "- #1 User (latest message): No butter please.",
        "- #2 Menu shown: Light plate. Items: Cucumber",
    ]
    assert await load_chat_block(db, "no-such-session", user_id) is None


# The chat persona's history keeps every message in order, with a meal card's JSON turned into its one line after the reply's text
def test_chat_history_turns_cards_into_lines():
    rows = [_user(SUGGEST_MESSAGES[None]), _app(_card(PLATE)), _user("Too heavy."), _app("Lighter it is!")]
    history = chat_history(rows)
    assert [h["role"] for h in history] == ["user", "assistant", "user", "assistant"]
    assert history[1]["content"] == (
        "A breakfast for you.\n\nMenu shown: Breakfast plate. Dishes: Scrambled eggs. Items: Eggs, Butter, Cucumber"
    )
    assert history[0] == rows[0] and history[2:] == rows[2:]
    assert not any("```" in h["content"] for h in history)
    # A card with no text of its own is just its line
    assert chat_history([_app(_card(PLATE, text=""))])[0]["content"].startswith("Menu shown: Breakfast plate.")


# A chat reply loses its meal block from the fence on, as the app stops showing it while it streams, and plain text stays
def test_drop_meal_block():
    assert drop_meal_block('Quick one!\n\n```json\n{"menu": []}\n```') == "Quick one!"
    assert drop_meal_block("```json\n{}\n```") == ""
    assert drop_meal_block("Tap Suggest when you're ready.") == "Tap Suggest when you're ready."
