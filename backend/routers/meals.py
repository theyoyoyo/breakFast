"""
/meals — meal history endpoints.
"""

import json
from fastapi import APIRouter, HTTPException
from database import get_db
from models.meal import Meal, MealLog, MealRating

router = APIRouter(prefix="/meals", tags=["meals"])


def _parse_json_field(value, default):
    """Safely decode a JSON-encoded DB field, returning `default` on failure."""
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _row_to_meal(row) -> dict:
    """Convert a raw DB row to a dict with JSON list fields decoded."""
    d = dict(row)
    d["ingredients"] = _parse_json_field(d.get("ingredients"), [])
    d["steps"] = _parse_json_field(d.get("steps"), [])
    d["schedule"] = _parse_json_field(d.get("schedule"), None)
    return d


@router.get("/", response_model=list[Meal])
async def list_meals(limit: int = 50):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM meal_history ORDER BY logged_at DESC LIMIT ?", (limit,)
        ) as cur:
            return [_row_to_meal(r) for r in await cur.fetchall()]


@router.get("/{meal_id}", response_model=Meal)
async def get_meal(meal_id: int):
    async with get_db() as db:
        async with db.execute("SELECT * FROM meal_history WHERE id = ?", (meal_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Meal not found")
    return _row_to_meal(row)


@router.post("/", response_model=Meal, status_code=201)
async def log_meal(body: MealLog):
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO meal_history
                (meal_name, description, ingredients, steps, prep_time_min, nutrition_note, schedule)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.meal_name,
                body.description,
                json.dumps(body.ingredients or [], ensure_ascii=False),
                json.dumps(body.steps or [], ensure_ascii=False),
                body.prep_time_min,
                body.nutrition_note,
                json.dumps(body.schedule, ensure_ascii=False) if body.schedule else None,
            ),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM meal_history WHERE id = last_insert_rowid()"
        ) as cur:
            return _row_to_meal(await cur.fetchone())


@router.patch("/{meal_id}/rating", response_model=Meal)
async def rate_meal(meal_id: int, body: MealRating):
    """Rate a meal thumbs-up (5) or thumbs-down (1)."""
    if body.rating not in (1, 5):
        raise HTTPException(status_code=400, detail="Rating must be 1 (down) or 5 (up)")
    async with get_db() as db:
        # UPDATE directly — check rowcount instead of a wasted SELECT
        cursor = await db.execute(
            "UPDATE meal_history SET rating = ? WHERE id = ?", (body.rating, meal_id)
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Meal not found")
        async with db.execute("SELECT * FROM meal_history WHERE id = ?", (meal_id,)) as cur:
            return _row_to_meal(await cur.fetchone())
