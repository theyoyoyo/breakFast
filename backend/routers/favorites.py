"""
CRUD endpoints for favorite meals.
"""

import json as _json

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from database import get_db
from db_helpers import row_to_favorite

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("/")
async def list_favorites(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM favorite_meals WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cur:
            return [row_to_favorite(r) for r in await cur.fetchall()]


@router.post("/", status_code=201)
async def add_favorite(meal: dict, user_id: int = Depends(require_user)):
    ingredients = _json.dumps(meal.get("ingredients", []), ensure_ascii=False)
    steps = _json.dumps(meal.get("steps", []), ensure_ascii=False)
    menu_items = meal.get("menu_items") or meal.get("menu")
    async with get_db() as db:
        cur = await db.execute(
            """
            INSERT INTO favorite_meals
                (user_id, meal_name, description, ingredients, steps, prep_time_min, nutrition_note, menu_items)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                meal.get("menu_name") or meal.get("meal_name", "Meal"),
                meal.get("description"),
                ingredients,
                steps,
                meal.get("prep_time_min"),
                meal.get("nutrition_note"),
                _json.dumps(menu_items, ensure_ascii=False) if menu_items else None,
            ),
        )
        await db.commit()
        return {"id": cur.lastrowid}


@router.put("/{fav_id}")
async def update_favorite(fav_id: int, meal: dict, user_id: int = Depends(require_user)):
    ingredients = _json.dumps(meal.get("ingredients", []), ensure_ascii=False)
    steps = _json.dumps(meal.get("steps", []), ensure_ascii=False)
    menu_items = meal.get("menu_items") or meal.get("menu")
    async with get_db() as db:
        cur = await db.execute(
            """
            UPDATE favorite_meals
            SET meal_name = ?, description = ?, ingredients = ?, steps = ?,
                prep_time_min = ?, nutrition_note = ?, menu_items = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                meal.get("menu_name") or meal.get("meal_name", "Meal"),
                meal.get("description"),
                ingredients,
                steps,
                meal.get("prep_time_min"),
                meal.get("nutrition_note"),
                _json.dumps(menu_items, ensure_ascii=False) if menu_items else None,
                fav_id,
                user_id,
            ),
        )
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Favorite not found")
        return {"status": "ok"}


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
        return {"status": "ok"}
