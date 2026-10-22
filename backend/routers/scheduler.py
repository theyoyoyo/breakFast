"""
/scheduler endpoint — kitchen prep timeline for a specific meal.

LLM extracts a structured plan (prep + timed tasks). We handle the scheduling
math: timed tasks are scheduled backwards so everything finishes together.
Supports caching via meal_history.schedule column.
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
from services.knowledge import format_ingredient_item
from utils import extract_json_block

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class ScheduleRequest(BaseModel):
    meal_name: str
    steps: list[str] = []
    menu: list[Union[dict, str]] = []
    ingredients: list[Union[dict, str]] = []
    meal_id: int | None = None


class ScheduleResponse(BaseModel):
    timeline: list[dict]
    makespan_min: float
    formatted: str
    cached: bool = False


def _build_plan(raw: dict) -> dict:
    """
    Take the LLM's {prep, timed} output and produce a formatted plan.

    Timed tasks are scheduled backwards so they all finish at the same time.
    """
    prep = raw.get("prep", [])
    timed = raw.get("timed", [])

    if not timed:
        makespan = 0
    else:
        makespan = max(t.get("duration_min", 0) for t in timed)

    # Build timeline: timed tasks start at (makespan - duration) so they all end together
    timeline = []
    for t in timed:
        dur = t.get("duration_min", 0)
        start = makespan - dur
        timeline.append({
            "start_min": round(start, 1),
            "task": t.get("task", "?"),
            "duration_min": dur,
            "resource": t.get("resource", ""),
            "end_action": t.get("end_action", ""),
        })

    # Sort by start time (earliest first), then by duration desc for ties
    timeline.sort(key=lambda t: (t["start_min"], -t["duration_min"]))

    # Format
    lines = []

    if prep:
        lines.append("🔪 Hazırlık")
        for p in prep:
            task = p.get("task", "?") if isinstance(p, dict) else str(p)
            detail = p.get("detail", "") if isinstance(p, dict) else ""
            line = f"  • {task}"
            if detail:
                line += f" — {detail}"
            lines.append(line)
        lines.append("")

    if timeline:
        lines.append(f"⏱ Zamanlama ({int(makespan)} dk)")
        for entry in timeline:
            m = int(entry["start_min"])
            s = int((entry["start_min"] - m) * 60)
            res = f"  [{entry['resource']}]" if entry["resource"] else ""
            lines.append(
                f"  {m}:{s:02d}  — {entry['task']} ({entry['duration_min']:.0f} dk){res}"
            )
            if entry["end_action"]:
                lines.append(f"         ↳ {entry['end_action']}")

        # Final "done" line
        done_m = int(makespan)
        done_s = int((makespan - done_m) * 60)
        lines.append(f"  {done_m}:{done_s:02d}  — Hazır! ✓")

    formatted = "\n".join(lines)

    return {
        "timeline": timeline,
        "makespan_min": makespan,
        "formatted": formatted,
    }


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
    from services.context import fetch_kitchen_appliances, fetch_preferences
    async with get_db() as db:
        kitchen_appliances = await fetch_kitchen_appliances(db, user_id)
        prefs = await fetch_preferences(db, user_id)
    language = prefs.get("response_language", "en")

    system_prompt = build_scheduler_prompt(body.meal_name, body.steps, ingredients_str, kitchen_appliances=kitchen_appliances, language=language)
    user_message = build_scheduler_user_message(body.meal_name, body.steps, ingredients_str, menu=body.menu)

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

    # Parse the JSON plan from LLM output
    raw_plan = extract_json_block(response_text)
    if not raw_plan or not isinstance(raw_plan, dict):
        return ScheduleResponse(
            timeline=[],
            makespan_min=0,
            formatted="Plan ayrıştırılamadı.",
        )

    # Build the schedule ourselves
    result = _build_plan(raw_plan)

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
