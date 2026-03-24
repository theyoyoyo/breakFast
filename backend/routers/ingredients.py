"""
/ingredients — CRUD endpoints for the ingredient inventory.
All queries are scoped to the authenticated user.
"""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from database import get_db
from auth import require_user
from models.ingredient import Ingredient, IngredientCreate

router = APIRouter(prefix="/ingredients", tags=["ingredients"])

# Shared upsert SQL used by both single-add and bulk-add
_UPSERT_SQL = """
    INSERT INTO ingredient_inventory (user_id, name, expiry_date)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id, name) DO UPDATE SET
        expiry_date = excluded.expiry_date,
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
        await db.execute(_UPSERT_SQL, (user_id, body.name, body.expiry_date))
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
            [(user_id, item.name, item.expiry_date) for item in ingredients],
        )
        await db.commit()
    return {"added": len(ingredients)}


# ---------------------------------------------------------------------------
# Expiry checking
# ---------------------------------------------------------------------------


@router.get("/expired", response_model=list[Ingredient])
async def get_expired_ingredients(user_id: int = Depends(require_user)):
    """Return ingredients that expired between the last check date and today.

    If already checked today, returns an empty list.
    Updates last_expiry_check to today after returning results.
    """
    today = date.today().isoformat()

    async with get_db() as db:
        # Get last check date
        async with db.execute(
            "SELECT last_expiry_check FROM users WHERE id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            last_check = row["last_expiry_check"] if row else None

        # If already checked today, return empty
        if last_check == today:
            return []

        # Find expired items: expiry_date is set AND expiry_date <= today
        # If last_check exists, only items that expired after that date
        if last_check:
            async with db.execute(
                """SELECT * FROM ingredient_inventory
                   WHERE user_id = ? AND expiry_date IS NOT NULL
                   AND expiry_date > ? AND expiry_date <= ?
                   ORDER BY expiry_date""",
                (user_id, last_check, today),
            ) as cur:
                expired = [dict(r) for r in await cur.fetchall()]
        else:
            # First check ever — report everything expired up to today
            async with db.execute(
                """SELECT * FROM ingredient_inventory
                   WHERE user_id = ? AND expiry_date IS NOT NULL
                   AND expiry_date <= ?
                   ORDER BY expiry_date""",
                (user_id, today),
            ) as cur:
                expired = [dict(r) for r in await cur.fetchall()]

        # Update last check date
        await db.execute(
            "UPDATE users SET last_expiry_check = ? WHERE id = ?",
            (today, user_id),
        )
        await db.commit()

        return expired


class ThrownRequest(BaseModel):
    ids: list[int]


@router.post("/expired/thrown", status_code=200)
async def confirm_thrown(body: ThrownRequest, user_id: int = Depends(require_user)):
    """Remove expired ingredients that the user has confirmed as thrown away."""
    async with get_db() as db:
        for ingredient_id in body.ids:
            await db.execute(
                "DELETE FROM ingredient_inventory WHERE id = ? AND user_id = ?",
                (ingredient_id, user_id),
            )
        await db.commit()
    return {"removed": len(body.ids)}
