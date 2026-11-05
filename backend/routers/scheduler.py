"""
/scheduler endpoint — kitchen prep plan for a specific meal.

The LLM lists each dish's steps (hands-on or waiting, with minutes and an appliance). We do
the scheduling math: steps are placed backwards from the finish so the dishes are ready
together, and the plan reads as one list in time order, dishes interleaved.
Supports caching via meal_history.schedule column.
"""

import json
import math
from collections import Counter

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Union

from auth import require_user
from database import get_db
from services.suggestion import stream_response
from services.personas import build_scheduler_prompt, build_scheduler_user_message
from services.personas.scheduler import DEFAULT_APPLIANCES
from services.llm import LLMUnavailableError, lyric_cycler
from services.fridge import same_name
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


# Fixed labels in the formatted plan, per response language. The app colors plans whose
# heading is "⏱ Plan (" by dish (#145), so older plans keep their look.
_PLAN_LABELS = {
    "en": {"plan": "⏱ Plan", "min": "min", "ready": "Ready! ✓", "dish": "Dish",
           "unreadable": "Couldn't read the plan. Please try again."},
    "tr": {"plan": "⏱ Plan", "min": "dk", "ready": "Hazır! ✓", "dish": "Yemek",
           "unreadable": "Plan ayrıştırılamadı. Lütfen tekrar dene."},
}

# Steps an appliance holds at once: the stove has two pans, every other appliance one step
_CAPACITY = {"stove": 2}
# Minutes for a step whose estimate code can't use, by hands-on (True) or waiting (False)
_DEFAULT_MINUTES = {True: 2, False: 5}
# The longest step code plans, so a wild estimate can't stretch the plan for hours
_MAX_MINUTES = 120


def _labels(language: str) -> dict:
    return _PLAN_LABELS.get(language, _PLAN_LABELS["en"])


def _clean(text) -> str:
    """One line of text, whitespace collapsed, so a step can't break the plan's layout."""
    return " ".join(str(text or "").split())


def _minutes(value, hands_on: bool) -> int:
    """Whole minutes for a step, rounded up and at least one; the default when the estimate is
    missing, negative or not a number."""
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        minutes = -1
    if isinstance(value, bool) or not 0 <= minutes < math.inf:  # NaN fails the comparison too
        return _DEFAULT_MINUTES[hands_on]
    return min(max(math.ceil(minutes), 1), _MAX_MINUTES)


def _read_dishes(raw: dict, language: str, appliances: list[str] | None, served: list[str]) -> list[dict]:
    """The LLM's dishes with their steps in order. Dish names lose their colons, so the app can read
    the dish as the text before the first colon of a time line. A dish named like an item the menu
    serves as it is gets no steps. An appliance outside the user's list is dropped (None keeps any),
    and a step without hands_on is waiting when it has an appliance."""
    known = None if appliances is None else {a.lower(): a for a in appliances}
    entries = raw.get("dishes") if isinstance(raw.get("dishes"), list) else []
    dishes = []
    for entry in (e for e in entries if isinstance(e, dict)):
        if any(same_name(str(entry.get("dish") or ""), item) for item in served):
            continue
        steps = []
        for step in entry.get("steps") or []:
            if not isinstance(step, dict) or not _clean(step.get("action")):
                continue
            appliance = _clean(step.get("appliance"))
            if known is not None:
                appliance = known.get(appliance.lower(), "")
            hands_on = step.get("hands_on")
            if not isinstance(hands_on, bool):
                hands_on = not appliance
            steps.append({
                "task": _clean(step["action"]),
                "duration_min": _minutes(step.get("minutes"), hands_on),
                "hands_on": hands_on,
                "resource": appliance,
            })
        if steps:
            name = _clean(str(entry.get("dish") or "").replace(":", " "))
            dishes.append({"name": name or f"{_labels(language)['dish']} {len(dishes) + 1}", "steps": steps})
    return dishes


def _schedule(dishes: list[dict]) -> int:
    """Give every step a start minute and return the total minutes.

    Works backwards from the finish so the dishes are ready together: each dish's steps stay
    in order, one cook does the hands-on steps one at a time, and an appliance holds one step
    (the stove two). Waiting steps need no cook, so other dishes' hands-on steps fill them.
    Times inside count minutes before the finish."""
    cook, used = set(), Counter()  # minutes the cook is busy; steps on each (appliance, minute)
    left = [len(d["steps"]) for d in dishes]  # steps still to place, per dish
    ready = [0] * len(dishes)  # where each dish's earliest placed step starts

    def fits(step: dict, at: int) -> bool:
        minutes = range(at, at + step["duration_min"])
        capacity = _CAPACITY.get(step["resource"].lower(), 1)
        return (not step["hands_on"] or cook.isdisjoint(minutes)) and (
            not step["resource"] or all(used[step["resource"], m] < capacity for m in minutes))

    def latest(i: int) -> int:
        """The closest to the finish dish i's next step can end without a clash."""
        step, at = dishes[i]["steps"][left[i] - 1], ready[i]
        while not fits(step, at):
            at += 1
        return at

    while any(left):
        # The step that can end closest to the finish goes next; on a tie, the dish with the most work left
        at, _, i = min(
            (latest(i), -sum(s["duration_min"] for s in dishes[i]["steps"][:left[i]]), i)
            for i in range(len(dishes)) if left[i]
        )
        step = dishes[i]["steps"][left[i] - 1]
        for m in range(at, at + step["duration_min"]):
            if step["hands_on"]:
                cook.add(m)
            if step["resource"]:
                used[step["resource"], m] += 1
        step["end_before"] = at
        ready[i] = at + step["duration_min"]
        left[i] -= 1

    total = max(ready, default=0)
    for dish in dishes:
        for step in dish["steps"]:
            step["start_min"] = total - step.pop("end_before") - step["duration_min"]
    return total


def _in_time_order(dishes: list[dict]) -> list[dict]:
    """Every step in time order. On a tie the dish just shown goes on, then waiting steps
    (start them, then work while they cook), then menu order."""
    pending = [{**s, "dish": d["name"], "order": i} for i, d in enumerate(dishes) for s in d["steps"]]
    ordered = []
    while pending:
        first = min(s["start_min"] for s in pending)
        last = ordered[-1]["order"] if ordered else None
        step = min(
            (s for s in pending if s["start_min"] == first),
            key=lambda s: (s["order"] != last, s["hands_on"], s["order"]),
        )
        pending.remove(step)
        ordered.append(step)
    return ordered


def served_items(menu: list) -> list[str]:
    """The names of the menu's items served as they are; the planner's steps for them are dropped."""
    return [i.get("name") or "" if isinstance(i, dict) else i for i in menu
            if not (isinstance(i, dict) and i.get("ingredients"))]


def _clock(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


def _build_plan(raw: dict, language: str = "en", appliances: list[str] | None = None, served: list[str] = ()) -> dict:
    """
    Take the LLM's {dishes: [{dish, steps}]} output and produce a formatted plan.

    One list in time order under one heading: a time line names its dish before the step, the
    dish's steps that follow right after it sit under it as ↳ lines, waiting steps show their
    minutes and appliance, and the Ready line ends it. `served` names the menu's items served
    as they are, which go straight to the table.
    """
    labels = _labels(language)
    dishes = _read_dishes(raw, language, appliances, served)
    total = _schedule(dishes)
    timeline = _in_time_order(dishes)

    lines = [f"{labels['plan']} ({total} {labels['min']})"]
    previous = None
    for step in timeline:
        text = step["task"]
        if not step["hands_on"]:
            text += f" ({step['duration_min']} {labels['min']})" + (f" [{step['resource']}]" if step["resource"] else "")
        goes_on = previous is not None and previous["order"] == step["order"] and (
            previous["start_min"] + previous["duration_min"] == step["start_min"])
        if goes_on:
            lines.append(f"         ↳ {text}")
        else:
            lines.append(f"  {_clock(step['start_min'])}  — {step['dish']}: {text}")
        previous = step
    lines.append(f"  {_clock(total)}  — {labels['ready']}")

    return {
        "timeline": [{k: v for k, v in s.items() if k != "order"} for s in timeline],
        "makespan_min": total,
        "formatted": "\n".join(lines),
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

    # The plan keeps only the appliances the prompt offered
    appliances = kitchen_appliances or DEFAULT_APPLIANCES
    system_prompt = build_scheduler_prompt(body.meal_name, body.steps, ingredients_str, kitchen_appliances=appliances, language=language)
    user_message = build_scheduler_user_message(body.meal_name, body.steps, ingredients_str, menu=body.menu, language=language)

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
    if not isinstance(raw_plan, dict) or not isinstance(raw_plan.get("dishes"), list):
        return ScheduleResponse(
            timeline=[],
            makespan_min=0,
            formatted=_labels(language)["unreadable"],
        )

    # Build the schedule ourselves; the model sometimes gives a served item a "serve" step
    result = _build_plan(raw_plan, language, appliances, served_items(body.menu))

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
