"""
/chat WebSocket endpoint.
Handles streaming conversation with context loading from DB.
Parses JSON meal blocks from LLM responses and auto-logs meals.
Messages are persisted to chat_messages table for session continuity.
"""

import asyncio
import json
import uuid
from datetime import date as date_type
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from database import get_db
from auth import get_user_id_from_token
from services.llm import LLMUnavailableError, LLM_UNAVAILABLE_MESSAGE
from services.suggestion import build_chat_prompt, build_suggestion_prompt, stream_response
from utils import extract_json_block

router = APIRouter()


async def _load_context(db, user_id: int) -> dict:
    """
    Load all context needed to build the system prompt.
    The four queries are independent and run concurrently via asyncio.gather.
    """
    async def fetch_ingredients():
        async with db.execute(
            "SELECT name, quantity, unit FROM ingredient_inventory WHERE user_id = ? ORDER BY name",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def fetch_history():
        async with db.execute(
            "SELECT meal_name FROM meal_history WHERE user_id = ? ORDER BY logged_at DESC LIMIT 10",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def fetch_prefs():
        async with db.execute(
            "SELECT key, value FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ) as cur:
            return {r["key"]: r["value"] for r in await cur.fetchall()}

    async def fetch_habits():
        async with db.execute(
            "SELECT description, source FROM user_habits WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
            stated = [r["description"] for r in rows if r["source"] == "stated"]
            inferred = [r["description"] for r in rows if r["source"] == "inferred"]
            return stated, inferred

    async def fetch_health_rules():
        async with db.execute(
            "SELECT rule_text FROM health_rules WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ) as cur:
            return [r["rule_text"] for r in await cur.fetchall()]

    async def fetch_profile():
        async with db.execute(
            "SELECT age, gender, height_cm, weight_kg, activity_level FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def fetch_supplements():
        today = date_type.today().isoformat()
        async with db.execute(
            """
            SELECT s.name, s.contents, s.frequency, COALESCE(l.taken, 0) AS taken_today
            FROM user_supplements s
            LEFT JOIN supplement_daily_log l
                ON l.supplement_id = s.id AND l.user_id = s.user_id AND l.date = ?
            WHERE s.user_id = ?
            ORDER BY s.name
            """,
            (today, user_id),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    (
        ingredients, history, prefs,
        (stated_habits, inferred_habits),
        health_rules, user_profile, supplements,
    ) = await asyncio.gather(
        fetch_ingredients(), fetch_history(), fetch_prefs(),
        fetch_habits(), fetch_health_rules(),
        fetch_profile(), fetch_supplements(),
    )
    # Separate avoid items from regular preferences
    avoid_list = [v for k, v in prefs.items() if k.startswith("avoid:")]
    filtered_prefs = {k: v for k, v in prefs.items() if not k.startswith("avoid:")}

    return {
        "ingredients": ingredients,
        "history": history,
        "preferences": filtered_prefs,
        "stated_habits": stated_habits,
        "inferred_habits": inferred_habits,
        "health_rules": health_rules,
        "user_profile": user_profile,
        "supplements": supplements,
        "avoid_list": avoid_list,
    }


async def _log_meal(db, user_id: int, meal_data: dict) -> None:
    """Insert a suggested meal into history. Called after a successful LLM suggestion."""
    await db.execute(
        """
        INSERT INTO meal_history
            (user_id, meal_name, description, ingredients, steps, prep_time_min, nutrition_note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            meal_data.get("meal_name", "Unknown"),
            meal_data.get("description"),
            json.dumps(meal_data.get("ingredients", []), ensure_ascii=False),
            json.dumps(meal_data.get("steps", []), ensure_ascii=False),
            meal_data.get("prep_time_min"),
            meal_data.get("nutrition_note"),
        ),
    )
    await db.commit()


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
                    cached_context = await _load_context(db, user_id)

            # Temperature per suggestion mode
            SUGGEST_TEMPERATURES = {
                "favorites": 0.6,
                "explore": 0.9,
            }
            temperature = SUGGEST_TEMPERATURES.get(suggest_mode) if prompt_type == "suggest" else None

            if prompt_type == "suggest":
                # Force fresh context for suggestion requests
                async with get_db() as db:
                    cached_context = await _load_context(db, user_id)
                system_prompt = build_suggestion_prompt(
                    ingredient_inventory=cached_context["ingredients"],
                    recent_meal_history=cached_context["history"],
                    user_preferences=cached_context["preferences"],
                    stated_habits=cached_context["stated_habits"],
                    inferred_habits=cached_context["inferred_habits"],
                    health_rules=cached_context["health_rules"],
                    user_profile=cached_context["user_profile"],
                    supplements=cached_context["supplements"],
                    avoid_list=cached_context["avoid_list"],
                    mode=suggest_mode,
                )
            else:
                system_prompt = build_chat_prompt(
                    ingredient_inventory=cached_context["ingredients"],
                    recent_meal_history=cached_context["history"],
                    user_preferences=cached_context["preferences"],
                    stated_habits=cached_context["stated_habits"],
                    inferred_habits=cached_context["inferred_habits"],
                    health_rules=cached_context["health_rules"],
                    avoid_list=cached_context["avoid_list"],
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
                response_text = LLM_UNAVAILABLE_MESSAGE
            except Exception:
                response_text = LLM_UNAVAILABLE_MESSAGE

            # Persist both messages to DB before signaling done
            async with get_db() as db:
                await _save_message(db, session_id, user_id, "user", user_message)
                await _save_message(db, session_id, user_id, "assistant", response_text)

            await websocket.send_json({"type": "done", "content": response_text})

            # Auto-log meal if the response contains a ```json meal block
            meal_data = extract_json_block(response_text)
            if meal_data:
                async with get_db() as db:
                    await _log_meal(db, user_id, meal_data)
                await websocket.send_json({"type": "meal_logged", "meal": meal_data})
                cached_context = None

    except WebSocketDisconnect:
        pass
