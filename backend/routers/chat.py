"""
/chat WebSocket endpoint.
Handles streaming conversation with context loading from DB.
Parses JSON meal blocks from LLM responses and auto-logs meals.
"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from database import get_db
from services.suggestion import build_system_prompt, stream_response
from utils import extract_json_block

router = APIRouter()


async def _load_context(db) -> dict:
    """
    Load all context needed to build the system prompt.
    The four queries are independent and run concurrently via asyncio.gather.
    """
    async def fetch_ingredients():
        async with db.execute(
            "SELECT name, quantity, unit FROM ingredient_inventory ORDER BY name"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def fetch_history():
        async with db.execute(
            "SELECT meal_name FROM meal_history ORDER BY logged_at DESC LIMIT 10"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def fetch_prefs():
        async with db.execute("SELECT key, value FROM user_preferences") as cur:
            return {r["key"]: r["value"] for r in await cur.fetchall()}

    async def fetch_habits():
        async with db.execute(
            "SELECT description, source FROM user_habits ORDER BY created_at DESC"
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


async def _log_meal(db, meal_data: dict) -> None:
    """Insert a suggested meal into history. Called after a successful LLM suggestion."""
    await db.execute(
        """
        INSERT INTO meal_history
            (meal_name, description, ingredients, steps, prep_time_min, nutrition_note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
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
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    conversation_history: list[dict] = []
    # Context is cached per session and only refreshed after a meal is logged
    # (the only DB write that occurs within this handler).
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

            # Load context; reuse cached value unless a meal was logged last turn
            if cached_context is None:
                async with get_db() as db:
                    cached_context = await _load_context(db)

            system_prompt = build_system_prompt(
                ingredient_inventory=cached_context["ingredients"],
                recent_meal_history=cached_context["history"],
                user_preferences=cached_context["preferences"],
                stated_habits=cached_context["stated_habits"],
                inferred_habits=cached_context["inferred_habits"],
            )

            # Stream response token by token
            full_response = []
            async for chunk in stream_response(system_prompt, conversation_history, user_message):
                full_response.append(chunk)
                await websocket.send_json({"type": "token", "content": chunk})

            response_text = "".join(full_response)
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
                    await _log_meal(db, meal_data)
                await websocket.send_json({"type": "meal_logged", "meal": meal_data})
                # Invalidate context cache so next turn reflects the new history entry
                cached_context = None

    except WebSocketDisconnect:
        pass
