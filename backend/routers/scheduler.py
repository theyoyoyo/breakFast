"""
/scheduler endpoint — kitchen prep plan for a specific meal.

The LLM lists each dish's steps (hands-on or waiting, with minutes and an appliance), and
services/prep_plan.py does the scheduling math.
Supports caching via meal_history.schedule column.
"""

import asyncio
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth import require_user
from database import get_db
from models.limits import INGREDIENTS_MAX, MENU_ITEMS_MAX, STEPS_MAX, MealName, Note, SizedItem
from services.context import fetch_kitchen_appliances, fetch_preferences
from services.knowledge import format_ingredient_item
from services.llm import LLMUnavailableError, lyric_cycler, stream_response
from services.personas import build_scheduler_prompt, build_scheduler_user_message
from services.personas.scheduler import DEFAULT_APPLIANCES
from services.prep_plan import _build_plan, _labels, served_items
from utils import extract_json_block

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class ScheduleRequest(BaseModel):
    meal_name: MealName
    steps: list[Note] = Field(default=[], max_length=STEPS_MAX)
    menu: list[SizedItem] = Field(default=[], max_length=MENU_ITEMS_MAX)
    ingredients: list[SizedItem] = Field(default=[], max_length=INGREDIENTS_MAX)
    meal_id: int | None = None


class ScheduleResponse(BaseModel):
    timeline: list[dict]
    makespan_min: float
    formatted: str
    cached: bool = False


@router.post("/plan", response_model=ScheduleResponse)
async def get_schedule(body: ScheduleRequest, user_id: int = Depends(require_user)):
    """Generate a parallel prep schedule for a meal."""

    # Check cache if meal_id is provided
    if body.meal_id is not None:
        async with get_db() as db:
            async with db.execute(
                "SELECT schedule FROM meal_history WHERE id = ? AND user_id = ?",
                (body.meal_id, user_id),
            ) as cur:
                row = await cur.fetchone()
            if row and row["schedule"]:
                cached = json.loads(row["schedule"])
                return ScheduleResponse(
                    timeline=cached.get("timeline", []),
                    makespan_min=cached.get("makespan_min", 0),
                    formatted=cached.get("formatted", ""),
                    cached=True,
                )

    # Menu-format meals have no steps; the LLM plans from the menu instead
    if not (body.steps or body.menu or body.ingredients):
        return ScheduleResponse(timeline=[], makespan_min=0, formatted="No steps found.")

    # Format ingredients for the prompt
    if body.ingredients:
        ingredients_str = ", ".join(format_ingredient_item(i) for i in body.ingredients)
    else:
        ingredients_str = "ingredient list unavailable"

    # Fetch user's kitchen appliances and language preference for the prompt
    async with get_db() as db:
        kitchen_appliances = await fetch_kitchen_appliances(db, user_id)
        prefs = await fetch_preferences(db, user_id)
    language = prefs.get("response_language", "en")

    # The plan keeps only the appliances the prompt offered
    appliances = kitchen_appliances or DEFAULT_APPLIANCES
    system_prompt = build_scheduler_prompt(body.meal_name, body.steps, ingredients_str, kitchen_appliances=appliances, language=language)
    user_message = build_scheduler_user_message(body.meal_name, body.steps, ingredients_str, menu=body.menu, language=language)

    # Collect full LLM response
    full_response = []
    try:
        async for chunk in stream_response(system_prompt, [], user_message, temperature=0.3, task="plan", language=language):
            full_response.append(chunk)
    except LLMUnavailableError:
        return ScheduleResponse(
            timeline=[],
            makespan_min=0,
            formatted=lyric_cycler.next(),
        )

    response_text = "".join(full_response)

    # Parse the JSON plan from LLM output
    raw_plan = extract_json_block(response_text)
    if not isinstance(raw_plan, dict) or not isinstance(raw_plan.get("dishes"), list):
        return ScheduleResponse(
            timeline=[],
            makespan_min=0,
            formatted=_labels(language)["unreadable"],
        )

    # Build the schedule ourselves, off the event loop since the search takes a moment; the model
    # sometimes gives a served item a "serve" step
    result = await asyncio.to_thread(_build_plan, raw_plan, language, appliances, served_items(body.menu))

    # Cache if meal_id was provided
    if body.meal_id is not None:
        cache_payload = json.dumps(result, ensure_ascii=False)
        async with get_db() as db:
            await db.execute(
                "UPDATE meal_history SET schedule = ? WHERE id = ? AND user_id = ?",
                (cache_payload, body.meal_id, user_id),
            )
            await db.commit()

    return ScheduleResponse(
        timeline=result["timeline"],
        makespan_min=result["makespan_min"],
        formatted=result["formatted"],
    )
