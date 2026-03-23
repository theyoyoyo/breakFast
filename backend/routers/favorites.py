"""
CRUD endpoints for favorite meals.
"""

import json as _json

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from database import get_db

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _row_to_dict(row) -> dict:
    d = dict(row)
    for field in ("ingredients", "steps"):
        if d.get(field):
            try:
                d[field] = _json.loads(d[field])
            except (ValueError, TypeError):
                pass
    return d


@router.get("/")
async def list_favorites(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM favorite_meals WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cur:
            return [_row_to_dict(r) for r in await cur.fetchall()]


@router.post("/", status_code=201)
async def add_favorite(meal: dict, user_id: int = Depends(require_user)):
    ingredients = _json.dumps(meal.get("ingredients", []), ensure_ascii=False)
    steps = _json.dumps(meal.get("steps", []), ensure_ascii=False)
    async with get_db() as db:
        cur = await db.execute(
            """
            INSERT INTO favorite_meals
                (user_id, meal_name, description, ingredients, steps, prep_time_min, nutrition_note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                meal.get("meal_name", "Meal"),
                meal.get("description"),
                ingredients,
                steps,
                meal.get("prep_time_min"),
                meal.get("nutrition_note"),
            ),
        )
        await db.commit()
        return {"id": cur.lastrowid}


@router.delete("/{fav_id}")
async def delete_favorite(fav_id: int, user_id: int = Depends(require_user)):
    async with get_db() as db:
        cur = await db.execute(
            "DELETE FROM favorite_meals WHERE id = ? AND user_id = ?",
            (fav_id, user_id),
        )
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Favorite not found")
        return {"ok": True}
