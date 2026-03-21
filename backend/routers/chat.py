"""
/chat WebSocket endpoint.
Handles streaming conversation with context loading from DB.
Parses JSON meal blocks from LLM responses and auto-logs meals.
"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from database import get_db
from auth import get_user_id_from_token
from services.llm import LLMUnavailableError, LLM_UNAVAILABLE_MESSAGE
from services.suggestion import build_system_prompt, stream_response
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

    ingredients, history, prefs, (stated_habits, inferred_habits) = await asyncio.gather(
        fetch_ingredients(), fetch_history(), fetch_prefs(), fetch_habits()
    )
    return {
        "ingredients": ingredients,
        "history": history,
        "preferences": prefs,
        "stated_habits": stated_habits,
        "inferred_habits": inferred_habits,
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


@router.websocket("/chat")
async def chat_endpoint(websocket: WebSocket, token: str = Query(...)):
    # Authenticate via query param: ws://host/chat?token=xxx
    user_id = get_user_id_from_token(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept()
    conversation_history: list[dict] = []
    cached_context: dict | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"message": raw}

            user_message = payload.get("message", "").strip()
            if not user_message:
                continue

            if cached_context is None:
                async with get_db() as db:
                    cached_context = await _load_context(db, user_id)

            system_prompt = build_system_prompt(
                ingredient_inventory=cached_context["ingredients"],
                recent_meal_history=cached_context["history"],
                user_preferences=cached_context["preferences"],
                stated_habits=cached_context["stated_habits"],
                inferred_habits=cached_context["inferred_habits"],
            )

            # Stream response token by token
            full_response = []
            try:
                async for chunk in stream_response(system_prompt, conversation_history, user_message):
                    full_response.append(chunk)
                    await websocket.send_json({"type": "token", "content": chunk})

                response_text = "".join(full_response)
            except LLMUnavailableError:
                response_text = LLM_UNAVAILABLE_MESSAGE
            except Exception:
                response_text = LLM_UNAVAILABLE_MESSAGE

            await websocket.send_json({"type": "done", "content": response_text})

            # Maintain a bounded conversation history (20 turns = 10 exchanges)
            conversation_history.append({"role": "user", "content": user_message})
            conversation_history.append({"role": "assistant", "content": response_text})
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]

            # Auto-log meal if the response contains a ```json meal block
            meal_data = extract_json_block(response_text)
            if meal_data:
                async with get_db() as db:
                    await _log_meal(db, user_id, meal_data)
                await websocket.send_json({"type": "meal_logged", "meal": meal_data})
                cached_context = None

    except WebSocketDisconnect:
        pass
