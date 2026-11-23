"""
/meals — meal history endpoints.
All queries are scoped to the authenticated user.
"""

import asyncio
import json
import logging
from datetime import date as dt_date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import require_user
from database import get_db
from db_helpers import row_to_meal, serialize_json_field
from models.limits import MEALS_LIMIT_DEFAULT, MEALS_LIMIT_MAX, Id
from models.meal import Meal, MealLog
from services.context import fetch_health_rules, fetch_preferences, fetch_profile, fetch_supplements
from services.insights import PATTERN_DAYS
from services.knowledge import format_history_for_weekly_review
from services.llm import LLMUnavailableError, chat_json, lyric_cycler
from services.personas.weekly_analyst import build_weekly_analyst_prompt_with_meals
from services.weekly import (
    MEALS_IN_WINDOW,
    WEEKLY_SCHEMA,
    analysis_window,
    fetch_recent_analysis,
    needs_analysis,
    parse_weekly_reply,
    save_analysis,
    week_of,
)

# Fixed replies: a refusal for a week without meals, and a failed analysis (its cause goes to the log)
NO_MEALS_THIS_WEEK = "No meals logged in the last 7 days"
WEEKLY_REVIEW_FAILED = "Could not analyze the week. Please try again."

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


class WeeklyReviewStatus(BaseModel):
    nudge: bool  # a meal of the last 7 days is newer than the latest analysis (or there is none)


@router.get("/weekly-review", response_model=WeeklyReviewResponse)
async def get_weekly_review(user_id: int = Depends(require_user)):
    """The latest weekly analysis when it ran in the last 7 days; 404 when there is none."""
    async with get_db() as db:
        analysis = await fetch_recent_analysis(db, user_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="No weekly review found for this week")
    return WeeklyReviewResponse(
        narrative=analysis["narrative"],
        scores=json.loads(analysis["scores"]),
        week_key=analysis["week_key"],
        cached=True,
    )


@router.get("/weekly-review/status", response_model=WeeklyReviewStatus)
async def get_weekly_review_status(user_id: int = Depends(require_user)):
    """Whether the Weekly analysis button nudges: a meal was logged or changed in the last 7 days
    after the latest analysis, or there is none."""
    async with get_db() as db:
        return WeeklyReviewStatus(nudge=await needs_analysis(db, user_id, dt_date.today()))


@router.post("/weekly-review", response_model=WeeklyReviewResponse)
async def generate_weekly_review(user_id: int = Depends(require_user)):
    """Run the weekly analyst on the 7 days up to today and keep the analysis.

    It replaces the analysis from the same calendar week, if any. Without a meal in those days
    there is nothing to analyze: 422. A lyric comes back, and nothing is kept, while Ollama is
    unreachable.
    """
    today = dt_date.today()
    week_key = week_of(today)
    start, end = analysis_window(today)
    async with get_db() as db:
        async with db.execute(
            f"""
            SELECT meal_name, ingredients, menu_items, nutrition_note, logged_at
            FROM meal_history WHERE {MEALS_IN_WINDOW}
            ORDER BY logged_at ASC
            """,
            (user_id, start.isoformat(), end.isoformat()),
        ) as cur:
            meal_rows = [dict(r) for r in await cur.fetchall()]

    if not meal_rows:
        raise HTTPException(status_code=422, detail=NO_MEALS_THIS_WEEK)

    # Load user context
    async with get_db() as db:
        profile, supplements, health_rules, prefs = await asyncio.gather(
            fetch_profile(db, user_id),
            fetch_supplements(db, user_id),
            fetch_health_rules(db, user_id),
            fetch_preferences(db, user_id),
        )
    language = prefs.get("response_language", "en")

    system_prompt = build_weekly_analyst_prompt_with_meals(
        weekly_meals_text=format_history_for_weekly_review(meal_rows),
        user_profile=profile,
        supplements=supplements,
        health_rules=health_rules,
        language=language,
    )
    user_message = "Please review this week's breakfasts and provide your assessment."

    try:
        reply = await chat_json(
            system_prompt, [{"role": "user", "content": user_message}], WEEKLY_SCHEMA,
            temperature=0.3, task="weekly", language=language,
        )
    except LLMUnavailableError:
        return WeeklyReviewResponse(narrative=lyric_cycler.next(), scores=[], week_key=week_key, cached=False)
    except Exception:
        logging.exception("Weekly analyst call failed")
        raise HTTPException(status_code=500, detail=WEEKLY_REVIEW_FAILED) from None

    analysis = parse_weekly_reply(reply)
    if analysis is None:
        logging.warning("Weekly analyst reply could not be read: %r", reply[:500])
        raise HTTPException(status_code=500, detail=WEEKLY_REVIEW_FAILED)

    async with get_db() as db:
        await save_analysis(db, user_id, analysis, start, end, week_key)
        await db.commit()

    # The nutrient lists stay on the server: the suggestions read them, the review's text speaks for them
    return WeeklyReviewResponse(
        narrative=analysis["narrative"],
        scores=analysis["scores"],
        week_key=week_key,
        cached=False,
    )


# Nothing in the app calls this yet; kept for later use.
@router.get("/{meal_id}", response_model=Meal)
async def get_meal(meal_id: Id, user_id: int = Depends(require_user)):
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
async def update_meal(meal_id: Id, body: MealLog, user_id: int = Depends(require_user)):
    """Update a meal's details. Clears cached analysis and schedule since content may have changed."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            UPDATE meal_history SET
                meal_name = ?, description = ?, ingredients = ?,
                steps = ?, prep_time_min = ?, nutrition_note = ?,
                cached_nutrition = NULL, schedule = NULL, menu_items = ?,
                updated_at = datetime('now')
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
async def delete_meal(meal_id: Id, user_id: int = Depends(require_user)):
    """Delete a single meal from history."""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM meal_history WHERE id = ? AND user_id = ?",
            (meal_id, user_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Meal not found")

