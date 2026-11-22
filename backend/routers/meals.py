"""
/meals — meal history endpoints.
All queries are scoped to the authenticated user.
"""

import asyncio
import json
from datetime import date as dt_date
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import require_user
from database import get_db
from db_helpers import row_to_meal, serialize_json_field
from models.limits import MEALS_LIMIT_DEFAULT, MEALS_LIMIT_MAX
from models.meal import Meal, MealLog
from services.context import fetch_health_rules, fetch_preferences, fetch_profile, fetch_supplements
from services.insights import PATTERN_DAYS
from services.knowledge import format_history_for_weekly_review
from services.llm import LLMUnavailableError, lyric_cycler, stream_response
from services.personas.weekly_analyst import build_weekly_analyst_prompt_with_meals
from utils import extract_json_block

router = APIRouter(prefix="/meals", tags=["meals"])


@router.get("/", response_model=list[Meal])
async def list_meals(
    limit: int = Query(MEALS_LIMIT_DEFAULT, ge=1, le=MEALS_LIMIT_MAX),
    user_id: int = Depends(require_user),
):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM meal_history WHERE user_id = ? ORDER BY logged_at DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            return [row_to_meal(r) for r in await cur.fetchall()]


class WeeklyReviewResponse(BaseModel):
    narrative: str
    scores: list[dict]
    week_key: str
    cached: bool = False


@router.get("/weekly-review", response_model=WeeklyReviewResponse)
async def get_weekly_review(user_id: int = Depends(require_user)):
    """Return the most recent cached weekly review for the current ISO week.

    Returns 404 if no analysis has been run yet this week.
    """
    week_key = dt_date.today().strftime("%G-W%V")
    async with get_db() as db:
        async with db.execute(
            """
            SELECT narrative, scores, created_at FROM weekly_summaries
            WHERE user_id = ? AND week_key = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id, week_key),
        ) as cur:
            row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No weekly review found for this week")

    return WeeklyReviewResponse(
        narrative=row["narrative"],
        scores=json.loads(row["scores"]),
        week_key=week_key,
        cached=True,
    )


@router.post("/weekly-review", response_model=WeeklyReviewResponse)
async def generate_weekly_review(user_id: int = Depends(require_user)):
    """Run the weekly analyst and save a new review entry for the current ISO week.

    Always generates a fresh analysis — existing entries are kept (not overwritten).
    """
    week_key = dt_date.today().strftime("%G-W%V")

    # Fetch meals from the last 7 calendar days
    today = dt_date.today()
    week_start = today - timedelta(days=6)
    async with get_db() as db:
        async with db.execute(
            """
            SELECT meal_name, ingredients, menu_items, nutrition_note, logged_at
            FROM meal_history
            WHERE user_id = ? AND date(logged_at) >= ? AND date(logged_at) <= ?
            ORDER BY logged_at ASC
            """,
            (user_id, week_start.isoformat(), today.isoformat()),
        ) as cur:
            meal_rows = [dict(r) for r in await cur.fetchall()]

    if not meal_rows:
        raise HTTPException(status_code=404, detail="No meals found in the last 7 days")

    # Load user context
    async with get_db() as db:
        profile, supplements, health_rules, prefs = await asyncio.gather(
            fetch_profile(db, user_id),
            fetch_supplements(db, user_id),
            fetch_health_rules(db, user_id),
            fetch_preferences(db, user_id),
        )
    language = prefs.get("response_language", "en")

    weekly_meals_text = format_history_for_weekly_review(meal_rows)
    system_prompt = build_weekly_analyst_prompt_with_meals(
        weekly_meals_text=weekly_meals_text,
        user_profile=profile,
        supplements=supplements,
        health_rules=health_rules,
        language=language,
    )

    user_message = "Please review this week's breakfasts and provide your assessment."

    full_response = []
    try:
        async for chunk in stream_response(system_prompt, [], user_message, temperature=0.3):
            full_response.append(chunk)
    except LLMUnavailableError:
        return WeeklyReviewResponse(
            narrative=lyric_cycler.next(),
            scores=[],
            week_key=week_key,
            cached=False,
        )

    response_text = "".join(full_response)
    data = extract_json_block(response_text)
    if not data or "scores" not in data:
        raise HTTPException(status_code=500, detail="Weekly analyst returned invalid JSON")

    narrative = data.get("narrative", "")
    scores = data.get("scores", [])

    # Always insert a new row — history is preserved, latest retrieved by ORDER BY created_at DESC
    async with get_db() as db:
        await db.execute(
            "INSERT INTO weekly_summaries (user_id, week_key, narrative, scores) VALUES (?, ?, ?, ?)",
            (user_id, week_key, narrative, json.dumps(scores, ensure_ascii=False)),
        )
        await db.commit()

    return WeeklyReviewResponse(
        narrative=narrative,
        scores=scores,
        week_key=week_key,
        cached=False,
    )


@router.get("/{meal_id}", response_model=Meal)
async def get_meal(meal_id: int, user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM meal_history WHERE id = ? AND user_id = ?",
            (meal_id, user_id),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Meal not found")
    return row_to_meal(row)


@router.post("/", response_model=Meal, status_code=201)
async def log_meal(body: MealLog, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO meal_history
                (user_id, meal_name, description, ingredients, steps, prep_time_min, nutrition_note, schedule, menu_items)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                body.meal_name,
                body.description,
                serialize_json_field(body.ingredients),
                json.dumps(body.steps or [], ensure_ascii=False),
                body.prep_time_min,
                body.nutrition_note,
                json.dumps(body.schedule, ensure_ascii=False) if body.schedule else None,
                json.dumps(body.menu_items, ensure_ascii=False) if body.menu_items else None,
            ),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM meal_history WHERE id = last_insert_rowid()"
        ) as cur:
            return row_to_meal(await cur.fetchone())


@router.delete("/old", status_code=200)
async def delete_old_meals(user_id: int = Depends(require_user)):
    """Delete the current user's meals older than one month (the window the patterns look at)."""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM meal_history WHERE user_id = ? AND logged_at < datetime('now', ?)",
            (user_id, f"-{PATTERN_DAYS} days"),
        )
        await db.commit()
        return {"deleted": cursor.rowcount}


@router.put("/{meal_id}", response_model=Meal)
async def update_meal(meal_id: int, body: MealLog, user_id: int = Depends(require_user)):
    """Update a meal's details. Clears cached analysis and schedule since content may have changed."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            UPDATE meal_history SET
                meal_name = ?, description = ?, ingredients = ?,
                steps = ?, prep_time_min = ?, nutrition_note = ?,
                cached_nutrition = NULL, schedule = NULL, menu_items = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                body.meal_name,
                body.description,
                serialize_json_field(body.ingredients),
                json.dumps(body.steps or [], ensure_ascii=False),
                body.prep_time_min,
                body.nutrition_note,
                json.dumps(body.menu_items, ensure_ascii=False) if body.menu_items else None,
                meal_id,
                user_id,
            ),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Meal not found")
        async with db.execute(
            "SELECT * FROM meal_history WHERE id = ? AND user_id = ?",
            (meal_id, user_id),
        ) as cur:
            return row_to_meal(await cur.fetchone())


@router.delete("/{meal_id}", status_code=204)
async def delete_meal(meal_id: int, user_id: int = Depends(require_user)):
    """Delete a single meal from history."""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM meal_history WHERE id = ? AND user_id = ?",
            (meal_id, user_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Meal not found")

