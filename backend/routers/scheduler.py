"""
/scheduler endpoint — kitchen prep timeline for a specific meal.

Decomposes meal steps into parallel tasks using an LLM, then runs the
job-shop scheduler. Supports caching via meal_history.schedule column.
"""

import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Union

from auth import require_user
from database import get_db
from services.suggestion import stream_response
from services.personas import build_scheduler_prompt, build_scheduler_user_message
from services.llm import LLMUnavailableError, lyric_cycler
from services.scheduler import Task, schedule
from services.knowledge import format_ingredient_item
from utils import extract_json_block

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class ScheduleRequest(BaseModel):
    meal_name: str
    steps: list[str]
    ingredients: list[Union[dict, str]] = []
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

    if not body.steps:
        return ScheduleResponse(timeline=[], makespan_min=0, formatted="No steps provided.")

    # Format ingredients for the prompt
    if body.ingredients:
        ingredients_str = ", ".join(format_ingredient_item(i) for i in body.ingredients)
    else:
        ingredients_str = "malzeme listesi yok"

    system_prompt = build_scheduler_prompt(body.meal_name, body.steps, ingredients_str)
    user_message = build_scheduler_user_message(body.meal_name, body.steps, ingredients_str)

    # Collect full LLM response
    full_response = []
    try:
        async for chunk in stream_response(system_prompt, [], user_message, temperature=0.3):
            full_response.append(chunk)
    except LLMUnavailableError:
        return ScheduleResponse(
            timeline=[],
            makespan_min=0,
            formatted=lyric_cycler.next(),
        )

    response_text = "".join(full_response)

    # Parse the JSON task array from LLM output
    raw_tasks = extract_json_block(response_text)
    if not raw_tasks or not isinstance(raw_tasks, list):
        return ScheduleResponse(
            timeline=[],
            makespan_min=0,
            formatted="Could not parse schedule from LLM response.",
        )

    # Convert to Task objects
    tasks = []
    for t in raw_tasks:
        if not isinstance(t, dict):
            continue
        tasks.append(Task(
            name=t.get("name", "?"),
            resource=t.get("resource", "hands"),
            duration_min=float(t.get("duration_min", 1)),
            predecessors=t.get("predecessors", []),
            item=t.get("item", ""),
        ))

    if not tasks:
        return ScheduleResponse(
            timeline=[],
            makespan_min=0,
            formatted="No tasks extracted from steps.",
        )

    # Run the scheduler
    result = schedule(tasks)

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
