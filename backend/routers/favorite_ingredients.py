"""
CRUD endpoints for favorite ingredients — a persistent "staples" list
independent of current inventory.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_user
from database import get_db
from models.limits import Name

router = APIRouter(prefix="/favorite-ingredients", tags=["favorite-ingredients"])


def _public(row) -> dict:
    """A staple as the app gets it: without the account's id."""
    d = dict(row)
    d.pop("user_id", None)
    return d


class FavoriteIngredientCreate(BaseModel):
    ingredient_name: Name


@router.get("/")
async def list_favorite_ingredients(user_id: int = Depends(require_user)):
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM favorite_ingredients WHERE user_id = ? ORDER BY ingredient_name",
            (user_id,),
        )
        return [_public(r) for r in rows]


@router.post("/", status_code=201)
async def add_favorite_ingredient(
    body: FavoriteIngredientCreate,
    user_id: int = Depends(require_user),
):
    name = body.ingredient_name.strip()
    if not name:
        raise HTTPException(422, "ingredient_name is required")
    async with get_db() as db:
        try:
            cur = await db.execute(
                "INSERT INTO favorite_ingredients (user_id, ingredient_name) VALUES (?, ?)",
                (user_id, name),
            )
            await db.commit()
        except Exception:
            raise HTTPException(409, "Already in favorites")
        row = await db.execute_fetchall(
            "SELECT * FROM favorite_ingredients WHERE id = ?", (cur.lastrowid,)
        )
        return _public(row[0])


@router.delete("/{ingredient_name}")
async def remove_favorite_ingredient(
    ingredient_name: str,
    user_id: int = Depends(require_user),
):
    async with get_db() as db:
        cur = await db.execute(
            "DELETE FROM favorite_ingredients WHERE user_id = ? AND ingredient_name = ?",
            (user_id, ingredient_name),
        )
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "Not found in favorites")
        return {"ok": True}
