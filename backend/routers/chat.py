"""
/chat WebSocket endpoint.
Handles streaming conversation with context loading from DB.
Parses JSON meal blocks from LLM responses and auto-logs meals.
Messages are persisted to chat_messages table for session continuity.
"""

import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from database import get_db
from auth import get_user_id_from_token
from services.llm import LLMUnavailableError, lyric_cycler
from services.suggestion import build_chat_prompt, stream_response
from services.pipeline import run_suggestion_pipeline
from services.context import load_chat_context
from utils import extract_json_block

router = APIRouter()


async def _save_suggestion(db, user_id: int, session_id: str, meal_data: dict) -> int:
    """Insert a suggested meal into suggested_meals. Returns the new suggestion's id."""
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
                flat_ingredients.append({"name": item.get("name", ""), "amount": item.get("amount", 1), "unit": item.get("unit", "adet")})
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


async def _save_message(db, session_id: str, user_id: int, role: str, content: str):
    """Persist a chat message and touch session updated_at."""
    await db.execute(
        "INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)",
        (session_id, user_id, role, content),
    )
    await db.execute(
        "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    await db.commit()


async def _load_session_history(db, session_id: str, user_id: int) -> list[dict]:
    """Load persisted messages for a session (last 20 for LLM context)."""
    async with db.execute(
        """
        SELECT role, content FROM chat_messages
        WHERE session_id = ? AND user_id = ?
        ORDER BY created_at DESC LIMIT 20
        """,
        (session_id, user_id),
    ) as cur:
        rows = await cur.fetchall()
    # Reverse to chronological order
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


@router.websocket("/chat")
async def chat_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Authenticate via query param: ws://host/chat?token=xxx
    user_id = get_user_id_from_token(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept()
    cached_context: dict | None = None
    session_id: str | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"message": raw}

            # Handle session management messages
            if "session_id" in payload and "message" not in payload:
                session_id = payload["session_id"]
                continue

            user_message = payload.get("message", "").strip()
            if not user_message:
                continue

            # Determine prompt type: "suggest" uses suggestion persona, default uses chat
            prompt_type = payload.get("type", "chat")
            suggest_mode = payload.get("mode")  # "favorites" or "explore"

            # Use session_id from payload if provided, otherwise keep current
            if "session_id" in payload:
                session_id = payload["session_id"]

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

            # Temperature per suggestion mode
            SUGGEST_TEMPERATURES = {
                "favorites": 0.6,
                "explore": 0.9,
            }
            temperature = SUGGEST_TEMPERATURES.get(suggest_mode) if prompt_type == "suggest" else None

            if prompt_type == "suggest":
                # Force fresh context for suggestion requests
                async with get_db() as db:
                    cached_context = await load_chat_context(db, user_id)

                # Run 3-step pipeline: draft → analyst review → refine
                response_text = ""
                try:
                    async for event in run_suggestion_pipeline(
                        context=cached_context,
                        user_message=user_message,
                        mode=suggest_mode,
                        temperature=temperature,
                    ):
                        if event["type"] == "progress":
                            await websocket.send_json(event)
                        elif event["type"] == "token":
                            await websocket.send_json(event)
                        elif event["type"] == "done":
                            response_text = event["content"]
                except LLMUnavailableError:
                    response_text = lyric_cycler.next()
                except Exception:
                    response_text = lyric_cycler.next()
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
                )

                # Load persisted conversation history for LLM context
                async with get_db() as db:
                    conversation_history = await _load_session_history(db, session_id, user_id)

                # Stream response token by token
                full_response = []
                try:
                    async for chunk in stream_response(system_prompt, conversation_history, user_message, temperature=temperature):
                        full_response.append(chunk)
                        await websocket.send_json({"type": "token", "content": chunk})

                    response_text = "".join(full_response)
                except LLMUnavailableError:
                    response_text = lyric_cycler.next()
                except Exception:
                    response_text = lyric_cycler.next()

            # Save suggestion if the response contains a ```json meal block.
            # Suggest responses: save to DB and notify frontend as a new meal.
            # Chat responses: notify frontend as an update to the existing meal —
            # do not save a new suggestion row (user didn't request a new meal).
            meal_data = extract_json_block(response_text)
            saved_text = response_text
            if meal_data and prompt_type == "suggest":
                async with get_db() as db:
                    suggestion_id = await _save_suggestion(db, user_id, session_id, meal_data)
                meal_data["id"] = suggestion_id
                # Normalize: ensure meal_name is always set (may come as menu_name)
                if "menu_name" in meal_data and "meal_name" not in meal_data:
                    meal_data["meal_name"] = meal_data["menu_name"]
                # Re-serialize JSON block with id so it persists in the message
                enriched_json = json.dumps(meal_data, ensure_ascii=False)
                saved_text = response_text[:response_text.rfind("```json")] + "```json\n" + enriched_json + "\n```"

            # Persist both messages to DB
            async with get_db() as db:
                await _save_message(db, session_id, user_id, "user", user_message)
                await _save_message(db, session_id, user_id, "assistant", saved_text)

            await websocket.send_json({"type": "done", "content": response_text})

            if meal_data:
                if prompt_type == "suggest":
                    await websocket.send_json({"type": "meal_logged", "meal": meal_data})
                else:
                    await websocket.send_json({"type": "meal_updated", "meal": meal_data})
                cached_context = None

    except WebSocketDisconnect:
        pass
