"""
/chat WebSocket endpoint.
Handles streaming conversation with context loading from DB.
A Suggest press runs the suggestion pipeline and saves its meal to suggested_meals.
Messages are persisted to chat_messages table for session continuity.
Each open socket is registered in services/chat_sync, so a saved reply reaches the user's other devices.
"""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from auth import SOCKET_AUTH_PROTOCOL, get_user_id_from_token, socket_token
from database import get_db
from db_helpers import owns_session
from models.limits import CHAT_MESSAGE_MAX, SESSION_ID_MAX
from models.units import count_unit
from services import chat_sync
from services.chat_block import CHAT_SUGGEST_TEXTS, chat_history, drop_meal_block, load_chat_block
from services.context import load_chat_context
from services.llm import LLMUnavailableError, lyric_cycler, stream_response
from services.personas import build_chat_prompt
from services.personas.chat import build_chat_message
from services.pipeline import RETRY_TEXTS, in_language, run_suggestion_pipeline
from utils import extract_json_block

router = APIRouter()

# Temperature per suggestion mode (also used by the prompt test, tools/prompt_check.py)
SUGGEST_TEMPERATURES = {
    "favorites": 0.6,
    "explore": 0.9,
}

# The reply to a typed message over the length limit; nothing is saved or sent to the model
TOO_LONG_TEXTS = {
    "en": "That message is too long for me to read. Could you send a shorter one?",
    "tr": "Bu mesaj okuyamayacağım kadar uzun. Daha kısa bir mesaj gönderebilir misin?",
}


def _session_id(value) -> str | None:
    """A session id a client sent, or None when it isn't a string of a sane length."""
    return value if isinstance(value, str) and len(value) <= SESSION_ID_MAX else None


# Shown when the session is deleted (on another device) while its reply is made: nothing is
# saved, since the session is gone. App text, so English like the rest of the UI.
SESSION_GONE_TEXT = "This chat is no longer available. Please start a new chat."


async def _save_suggestion(db, user_id: int, session_id: str, meal_data: dict, language: str = "en") -> int:
    """Insert a suggested meal into suggested_meals. Returns the new suggestion's id.
    `session_id` is the socket's checked session, one of the user's own (see chat_endpoint)."""
    # Support both old flat format and new menu format
    menu_items = meal_data.get("menu")
    meal_name = meal_data.get("menu_name") or meal_data.get("meal_name", "Unknown")
    # Flatten ingredients from menu for backward-compat fields
    if menu_items:
        flat_ingredients = []
        for item in menu_items:
            sub = item.get("ingredients") or []
            if sub:
                flat_ingredients.extend(sub)
            else:
                flat_ingredients.append({"name": item.get("name", ""), "amount": item.get("amount", 1), "unit": item.get("unit", count_unit(language))})
    else:
        flat_ingredients = meal_data.get("ingredients", [])

    await db.execute(
        """
        INSERT INTO suggested_meals
            (user_id, session_id, meal_name, description, ingredients, steps, prep_time_min, nutrition_note, menu_items)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            session_id,
            meal_name,
            meal_data.get("description"),
            json.dumps(flat_ingredients, ensure_ascii=False),
            json.dumps(meal_data.get("steps", []), ensure_ascii=False),
            meal_data.get("prep_time_min"),
            meal_data.get("nutrition_note"),
            json.dumps(menu_items, ensure_ascii=False) if menu_items else None,
        ),
    )
    await db.commit()
    async with db.execute("SELECT last_insert_rowid()") as cur:
        row = await cur.fetchone()
        return row[0]


async def _save_message(db, session_id: str, user_id: int, role: str, content: str) -> int:
    """Persist a chat message and touch session updated_at. Returns the new message's id."""
    cur = await db.execute(
        "INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)",
        (session_id, user_id, role, content),
    )
    # The session id comes from the client, so only the user's own session is touched
    await db.execute(
        "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ? AND user_id = ?",
        (session_id, user_id),
    )
    await db.commit()
    return cur.lastrowid


async def _load_session_history(db, session_id: str, user_id: int) -> list[dict]:
    """Load persisted messages for a session (last 20 for LLM context), oldest first.
    Sorted by id, the order they were saved in, not by created_at: it counts whole seconds, and
    a message and its reply are saved in the same second, so by time a reply came before its message."""
    async with db.execute(
        """
        SELECT role, content FROM chat_messages
        WHERE session_id = ? AND user_id = ?
        ORDER BY id DESC LIMIT 20
        """,
        (session_id, user_id),
    ) as cur:
        rows = await cur.fetchall()
    # Reverse to chat order
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


@router.websocket("/chat")
async def chat_endpoint(websocket: WebSocket):
    # The token comes in the Sec-WebSocket-Protocol header, never the URL, so it stays out of logs
    token = socket_token(websocket.scope.get("subprotocols", []))
    user_id = get_user_id_from_token(token) if token else None
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept(subprotocol=SOCKET_AUTH_PROTOCOL)
    chat_sync.register(user_id, websocket)
    cached_context: dict | None = None
    session_id: str | None = None
    # False once this device drops mid-reply (a phone locked while waiting): the reply
    # still finishes and is saved, and the user's devices load it from the session
    client_live = True

    async def send_live(event: dict) -> None:
        """Send a reply event to this device, unless it has already dropped."""
        nonlocal client_live
        if not client_live:
            return
        try:
            await websocket.send_json(event)
        except WebSocketDisconnect:
            client_live = False

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"message": raw}
            # Valid JSON that isn't an object (123, "hi", [1]) is plain text too
            if not isinstance(payload, dict):
                payload = {"message": raw}

            # Handle session management messages
            # (a session id, mode or type that isn't a string is ignored: it would crash a lookup;
            # so is a session that isn't the user's own, and the current one stays)
            if "session_id" in payload and "message" not in payload:
                named = _session_id(payload["session_id"])
                if named:
                    async with get_db() as db:
                        if await owns_session(db, named, user_id):
                            session_id = named
                continue

            message_text = payload.get("message", "")
            user_message = message_text.strip() if isinstance(message_text, str) else ""
            if not user_message:
                continue

            # Determine prompt type: "suggest" uses suggestion persona, default uses chat
            prompt_type = payload.get("type", "chat")
            suggest_mode = payload.get("mode")  # "favorites" or "explore"
            if not isinstance(prompt_type, str):
                prompt_type = "chat"
            if not isinstance(suggest_mode, str):
                suggest_mode = None

            # Use session_id from payload if provided, otherwise keep current. The message is saved only
            # in one of the user's own sessions: one that isn't (another user's, one deleted on another
            # device, or an id over the length limit) falls back to the current session, then to the latest,
            # so the message still gets its reply. Everything below, the suggestion included, uses this checked id.
            named = _session_id(payload.get("session_id"))
            async with get_db() as db:
                if named and await owns_session(db, named, user_id):
                    session_id = named
                elif session_id is not None and not await owns_session(db, session_id, user_id):
                    session_id = None

            # Ensure we have a session
            if session_id is None:
                async with get_db() as db:
                    async with db.execute(
                        "SELECT id FROM chat_sessions WHERE user_id = ? ORDER BY rowid DESC LIMIT 1",
                        (user_id,),
                    ) as cur:
                        row = await cur.fetchone()
                    if row:
                        session_id = row["id"]
                    else:
                        session_id = str(uuid.uuid4())
                        await db.execute(
                            "INSERT INTO chat_sessions (id, user_id) VALUES (?, ?)",
                            (session_id, user_id),
                        )
                        await db.commit()

            if cached_context is None:
                async with get_db() as db:
                    cached_context = await load_chat_context(db, user_id)

            if len(user_message) > CHAT_MESSAGE_MAX:
                await send_live({"type": "done", "content": in_language(TOO_LONG_TEXTS, cached_context.get("language", "en"))})
                if not client_live:
                    break
                continue

            temperature = SUGGEST_TEMPERATURES.get(suggest_mode) if prompt_type == "suggest" else None

            if prompt_type == "suggest":
                # Force fresh context for suggestion requests, and read the chat so far from the
                # session (this press isn't saved yet), so every device sends the same chat
                async with get_db() as db:
                    cached_context = await load_chat_context(db, user_id)
                    chat_block = await load_chat_block(db, session_id, user_id)

                # Run the 3-step pipeline: draft → revise → present
                response_text = ""
                try:
                    async for event in run_suggestion_pipeline(
                        context=cached_context,
                        user_message=user_message,
                        mode=suggest_mode,
                        temperature=temperature,
                        chat_block=chat_block,
                    ):
                        if event["type"] == "progress":
                            await send_live(event)
                        elif event["type"] == "token":
                            await send_live(event)
                        elif event["type"] == "done":
                            response_text = event["content"]
                except LLMUnavailableError:
                    response_text = lyric_cycler.next()
                except Exception:
                    logging.exception("Suggestion pipeline failed; asking to press Suggest again")
                # Ollama answered but the press failed (a timeout, an error) or said nothing:
                # tell the user it failed instead of posting nothing or a lyric
                response_text = response_text or in_language(RETRY_TEXTS, cached_context.get("language", "en"))
            else:
                system_prompt = build_chat_prompt(
                    ingredient_inventory=cached_context["ingredients"],
                    recent_meal_history=cached_context["history"],
                    user_preferences=cached_context["preferences"],
                    stated_habits=cached_context["stated_habits"],
                    inferred_habits=cached_context["inferred_habits"],
                    health_rules=cached_context["health_rules"],
                    avoid_list=cached_context["avoid_list"],
                    kitchen_appliances=cached_context.get("kitchen_appliances"),
                    language=cached_context.get("language", "en"),
                )

                # Load persisted conversation history for LLM context, meal cards as one line each
                async with get_db() as db:
                    conversation_history = chat_history(await _load_session_history(db, session_id, user_id))

                # Stream response token by token
                full_response = []
                try:
                    # The user's words with the app's note on how to reply; the words alone are saved
                    message = build_chat_message(user_message, cached_context.get("language", "en"))
                    async for chunk in stream_response(
                        system_prompt, conversation_history, message, temperature=temperature,
                        task="chat", language=cached_context.get("language", "en"),
                    ):
                        full_response.append(chunk)
                        await send_live({"type": "token", "content": chunk})

                    response_text = "".join(full_response)
                except LLMUnavailableError:
                    response_text = lyric_cycler.next()
                except Exception:
                    logging.exception("Chat reply failed; replying with a lyric")
                    response_text = lyric_cycler.next()
                # Meal cards come only from a Suggest press (#168): a chat reply keeps the text before
                # any meal block, or points to Suggest when the block was all it wrote
                response_text = (
                    drop_meal_block(response_text)
                    or in_language(CHAT_SUGGEST_TEXTS, cached_context.get("language", "en"))
                )

            # A Suggest reply's ```json meal block is saved as a suggestion and becomes a new meal card
            meal_data = extract_json_block(response_text) if prompt_type == "suggest" else None
            saved_text = response_text
            async with get_db() as db:
                still_owned = await owns_session(db, session_id, user_id)
            if not still_owned:
                # The session was deleted while the reply was made: nothing left to save it to
                await send_live({"type": "error", "code": "session_not_found", "message": SESSION_GONE_TEXT})
                session_id = None
                if not client_live:
                    break
                continue
            if meal_data:
                async with get_db() as db:
                    suggestion_id = await _save_suggestion(db, user_id, session_id, meal_data, cached_context.get("language", "en"))
                meal_data["id"] = suggestion_id
                # Normalize: ensure meal_name is always set (may come as menu_name)
                if "menu_name" in meal_data and "meal_name" not in meal_data:
                    meal_data["meal_name"] = meal_data["menu_name"]
                # Re-serialize JSON block with id so it persists in the message
                enriched_json = json.dumps(meal_data, ensure_ascii=False)
                saved_text = response_text[:response_text.rfind("```json")] + "```json\n" + enriched_json + "\n```"

            # Persist both messages to DB; a new suggestion becomes the selected meal card,
            # on every device (this one selects it when meal_logged arrives)
            async with get_db() as db:
                await _save_message(db, session_id, user_id, "user", user_message)
                message_id = await _save_message(db, session_id, user_id, "assistant", saved_text)
                if meal_data:
                    await db.execute(
                        "UPDATE chat_sessions SET selected_message_id = ? WHERE id = ? AND user_id = ?",
                        (message_id, session_id, user_id),
                    )
                    await db.commit()

            # The user's other devices reload this chat (they never get the tokens)
            await chat_sync.notify_session_updated(user_id, session_id, exclude=websocket)

            # message_id lets this device save later meal card edits into the message
            await send_live({"type": "done", "content": response_text, "message_id": message_id})

            if meal_data:
                await send_live({"type": "meal_logged", "meal": meal_data})
                cached_context = None

            if not client_live:
                break

    except WebSocketDisconnect:
        pass
    finally:
        chat_sync.unregister(user_id, websocket)
