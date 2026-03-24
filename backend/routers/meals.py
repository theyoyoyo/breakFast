"""
/meals — meal history endpoints.
All queries are scoped to the authenticated user.
"""

import json
from fastapi import APIRouter, HTTPException, Depends
from database import get_db
from auth import require_user
from models.meal import Meal, MealLog, MealRating
from db_helpers import row_to_meal, serialize_json_field

router = APIRouter(prefix="/meals", tags=["meals"])


@router.get("/", response_model=list[Meal])
async def list_meals(limit: int = 50, user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM meal_history WHERE user_id = ? ORDER BY logged_at DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            return [row_to_meal(r) for r in await cur.fetchall()]


@router.get("/weekly", response_model=list[Meal])
async def weekly_meals(user_id: int = Depends(require_user)):
    """Return last 7 meals with no date gaps — stops at the first missing day.

    Walks backward from the most recent meal's date. If a calendar day has no
    meal, that's the boundary. Returns up to 7 meals within the consecutive
    streak, most recent first.
    """
    from datetime import date as dt_date, timedelta

    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM meal_history WHERE user_id = ? ORDER BY logged_at DESC LIMIT 50",
            (user_id,),
        ) as cur:
            rows = [row_to_meal(r) for r in await cur.fetchall()]
    if not rows:
        return []

    result = []
    prev_date = None
    for meal in rows:
        meal_date = meal["logged_at"][:10]  # "YYYY-MM-DD"
        try:
            d = dt_date.fromisoformat(meal_date)
        except ValueError:
            continue
        if prev_date is None:
            prev_date = d
        elif d < prev_date:
            if prev_date - d > timedelta(days=1):
                break  # gap detected
            prev_date = d
        result.append(meal)
        if len(result) >= 7:
            break
    return result


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
                (user_id, meal_name, description, ingredients, steps, prep_time_min, nutrition_note, schedule)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM meal_history WHERE id = last_insert_rowid()"
        ) as cur:
            return row_to_meal(await cur.fetchone())


@router.delete("/old", status_code=200)
async def delete_old_meals(user_id: int = Depends(require_user)):
    """Delete meal history entries older than 1 year for the current user."""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM meal_history WHERE user_id = ? AND logged_at < datetime('now', '-1 year')",
            (user_id,),
        )
        await db.commit()
        return {"deleted": cursor.rowcount}


@router.put("/{meal_id}", response_model=Meal)
async def update_meal(meal_id: int, body: MealLog, user_id: int = Depends(require_user)):
    """Update a meal's details. Clears cached_nutrition since ingredients may have changed."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            UPDATE meal_history SET
                meal_name = ?, description = ?, ingredients = ?,
                steps = ?, prep_time_min = ?, nutrition_note = ?,
                cached_nutrition = NULL
            WHERE id = ? AND user_id = ?
            """,
            (
                body.meal_name,
                body.description,
                serialize_json_field(body.ingredients),
                json.dumps(body.steps or [], ensure_ascii=False),
                body.prep_time_min,
                body.nutrition_note,
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


@router.patch("/{meal_id}/rating", response_model=Meal)
async def rate_meal(meal_id: int, body: MealRating, user_id: int = Depends(require_user)):
    """Rate a meal thumbs-up (5) or thumbs-down (1)."""
    if body.rating not in (1, 5):
        raise HTTPException(status_code=400, detail="Rating must be 1 (down) or 5 (up)")
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE meal_history SET rating = ? WHERE id = ? AND user_id = ?",
            (body.rating, meal_id, user_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Meal not found")
        async with db.execute(
            "SELECT * FROM meal_history WHERE id = ? AND user_id = ?",
            (meal_id, user_id),
        ) as cur:
            return row_to_meal(await cur.fetchone())
