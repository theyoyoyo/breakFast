"""
/ingredients — CRUD endpoints for the ingredient inventory.
All queries are scoped to the authenticated user.
"""

from fastapi import APIRouter, Depends
from database import get_db
from auth import require_user
from models.ingredient import Ingredient, IngredientCreate

router = APIRouter(prefix="/ingredients", tags=["ingredients"])

# Shared upsert SQL used by both single-add and bulk-add
_UPSERT_SQL = """
    INSERT INTO ingredient_inventory (user_id, name)
    VALUES (?, ?)
    ON CONFLICT(user_id, name) DO UPDATE SET
        updated_at = datetime('now')
"""


@router.get("/", response_model=list[Ingredient])
async def list_ingredients(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM ingredient_inventory WHERE user_id = ? ORDER BY name",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/", response_model=Ingredient, status_code=201)
async def add_ingredient(body: IngredientCreate, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(_UPSERT_SQL, (user_id, body.name))
        await db.commit()
        async with db.execute(
            "SELECT * FROM ingredient_inventory WHERE user_id = ? AND name = ?",
            (user_id, body.name),
        ) as cur:
            return dict(await cur.fetchone())


@router.delete("/{ingredient_id}", status_code=204)
async def delete_ingredient(ingredient_id: int, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM ingredient_inventory WHERE id = ? AND user_id = ?",
            (ingredient_id, user_id),
        )
        await db.commit()


@router.post("/bulk", status_code=201)
async def bulk_add_ingredients(ingredients: list[IngredientCreate], user_id: int = Depends(require_user)):
    """Add or update multiple ingredients at once (used after NL parsing)."""
    async with get_db() as db:
        await db.executemany(
            _UPSERT_SQL,
            [(user_id, item.name) for item in ingredients],
        )
        await db.commit()
    return {"added": len(ingredients)}
