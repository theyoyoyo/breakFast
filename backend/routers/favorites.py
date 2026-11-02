"""
CRUD endpoints for favorite meals.
"""

import json as _json

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from database import get_db
from db_helpers import row_to_favorite

router = APIRouter(prefix="/favorites", tags=["favorites"])

NAME_TAKEN = "A favorite with this name already exists"


def _name_key(name) -> str:
    """Favorite names are compared exactly, in any case (like the app's star)."""
    return (name or "").strip().lower()


async def _name_taken(db, user_id: int, name: str, exclude_id: int | None = None) -> bool:
    """Whether another of the user's favorites has this name: names are unique per user, so a
    favorite saved again with other food gets a new name or an edit of the one saved before."""
    async with db.execute(
        "SELECT id, meal_name FROM favorite_meals WHERE user_id = ?", (user_id,)
    ) as cur:
        rows = await cur.fetchall()
    key = _name_key(name)
    return any(r["id"] != exclude_id and _name_key(r["meal_name"]) == key for r in rows)


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
    name = meal.get("menu_name") or meal.get("meal_name", "Meal")
    async with get_db() as db:
        if await _name_taken(db, user_id, name):
            raise HTTPException(status_code=409, detail=NAME_TAKEN)
        cur = await db.execute(
            """
            INSERT INTO favorite_meals
                (user_id, meal_name, description, ingredients, steps, prep_time_min, nutrition_note, menu_items)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                name,
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
    name = meal.get("menu_name") or meal.get("meal_name", "Meal")
    async with get_db() as db:
        async with db.execute(
            "SELECT meal_name FROM favorite_meals WHERE id = ? AND user_id = ?", (fav_id, user_id)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Favorite not found")
        # A rename may not take another favorite's name; keeping its own name is always fine,
        # so favorites that shared a name before this rule can still be edited
        if _name_key(name) != _name_key(row["meal_name"]) and await _name_taken(db, user_id, name, fav_id):
            raise HTTPException(status_code=409, detail=NAME_TAKEN)
        cur = await db.execute(
            """
            UPDATE favorite_meals
            SET meal_name = ?, description = ?, ingredients = ?, steps = ?,
                prep_time_min = ?, nutrition_note = ?, menu_items = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                name,
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
