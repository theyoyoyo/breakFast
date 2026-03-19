"""
/ingredients — CRUD endpoints for the ingredient inventory.
"""

from fastapi import APIRouter, HTTPException
from database import get_db
from models.ingredient import Ingredient, IngredientCreate, IngredientUpdate

router = APIRouter(prefix="/ingredients", tags=["ingredients"])

# Shared upsert SQL used by both single-add and bulk-add
_UPSERT_SQL = """
    INSERT INTO ingredient_inventory (name, quantity, unit)
    VALUES (?, ?, ?)
    ON CONFLICT(name) DO UPDATE SET
        quantity = excluded.quantity,
        unit = excluded.unit,
        updated_at = datetime('now')
"""


@router.get("/", response_model=list[Ingredient])
async def list_ingredients():
    async with get_db() as db:
        async with db.execute("SELECT * FROM ingredient_inventory ORDER BY name") as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/", response_model=Ingredient, status_code=201)
async def add_ingredient(body: IngredientCreate):
    async with get_db() as db:
        await db.execute(_UPSERT_SQL, (body.name, body.quantity, body.unit))
        await db.commit()
        async with db.execute(
            "SELECT * FROM ingredient_inventory WHERE name = ?", (body.name,)
        ) as cur:
            return dict(await cur.fetchone())


@router.patch("/{ingredient_id}", response_model=Ingredient)
async def update_ingredient(ingredient_id: int, body: IngredientUpdate):
    """Partial update of quantity and/or unit. Returns 404 if the id doesn't exist."""
    updates = {k: v for k, v in {"quantity": body.quantity, "unit": body.unit}.items() if v is not None}

    async with get_db() as db:
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            cursor = await db.execute(
                f"UPDATE ingredient_inventory SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                [*updates.values(), ingredient_id],
            )
            await db.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Ingredient not found")

        async with db.execute(
            "SELECT * FROM ingredient_inventory WHERE id = ?", (ingredient_id,)
        ) as cur:
            row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return dict(row)


@router.delete("/{ingredient_id}", status_code=204)
async def delete_ingredient(ingredient_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM ingredient_inventory WHERE id = ?", (ingredient_id,))
        await db.commit()


@router.post("/bulk", status_code=201)
async def bulk_add_ingredients(ingredients: list[IngredientCreate]):
    """Add or update multiple ingredients at once (used after NL parsing)."""
    async with get_db() as db:
        await db.executemany(
            _UPSERT_SQL,
            [(item.name, item.quantity, item.unit) for item in ingredients],
        )
        await db.commit()
    return {"added": len(ingredients)}
