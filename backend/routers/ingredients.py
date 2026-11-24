"""
/ingredients — CRUD endpoints for the ingredient inventory.
All queries are scoped to the authenticated user.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_user
from database import get_db
from db_helpers import fridge_names
from models.ingredient import INGREDIENT_GROUPS, Ingredient, IngredientCreate, IngredientUpdate
from models.limits import BULK_ITEMS_MAX, Id, SizedDict
from services.fridge import find_missing_ingredients
from services.ingredient_groups import remember, resolve_groups

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


def _validate_group(group_name: str | None) -> str | None:
    """Reject unknown group names."""
    if group_name is not None and group_name not in INGREDIENT_GROUPS:
        raise HTTPException(status_code=422, detail="Invalid group")
    return group_name


_UPSERT_SQL = """
    INSERT INTO ingredient_inventory (user_id, name, expiry_date, group_name)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(user_id, name) DO UPDATE SET
        expiry_date = excluded.expiry_date,
        group_name = excluded.group_name,
        updated_at = datetime('now')
"""


@router.get("/", response_model=list[Ingredient])
async def list_ingredients(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            """SELECT * FROM ingredient_inventory WHERE user_id = ?
               ORDER BY
                 CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END,
                 expiry_date ASC,
                 name ASC""",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/", response_model=Ingredient, status_code=201)
async def add_ingredient(body: IngredientCreate, user_id: int = Depends(require_user)):
    """Add an item: the group picked, else the user's pick for the name, the food list or Other.

    Memory records the name either way; only a picked group counts as the user's choice.
    """
    _validate_group(body.group_name)
    async with get_db() as db:
        # Capital first letters, or the user's item of that name in any case
        name = (await fridge_names(db, user_id, [body.name]))[body.name]
        group = body.group_name or (await resolve_groups(db, user_id, [name]))[name]
        await db.execute(_UPSERT_SQL, (user_id, name, body.expiry_date, group))
        await remember(db, user_id, name, group, picked=bool(body.group_name))
        await db.commit()
        async with db.execute(
            "SELECT * FROM ingredient_inventory WHERE user_id = ? AND name = ?",
            (user_id, name),
        ) as cur:
            return dict(await cur.fetchone())


@router.patch("/{ingredient_id}", response_model=Ingredient)
async def update_ingredient(ingredient_id: Id, body: IngredientUpdate, user_id: int = Depends(require_user)):
    """Update an ingredient's name, expiry date, and/or group."""
    _validate_group(body.group_name)

    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.expiry_date is not None:
        # Allow clearing expiry with empty string
        updates["expiry_date"] = body.expiry_date if body.expiry_date != "" else None
    if body.group_name is not None:
        updates["group_name"] = body.group_name

    async with get_db() as db:
        if updates.get("name") is not None:
            # Names are unique per user, so a taken name is refused before anything is written
            async with db.execute(
                "SELECT 1 FROM ingredient_inventory WHERE user_id = ? AND name = ? AND id != ?",
                (user_id, updates["name"], ingredient_id),
            ) as cur:
                if await cur.fetchone():
                    raise HTTPException(status_code=409, detail="An item with this name is already in your fridge")
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            cursor = await db.execute(
                f"UPDATE ingredient_inventory SET {set_clause}, updated_at = datetime('now') WHERE id = ? AND user_id = ?",
                [*updates.values(), ingredient_id, user_id],
            )
            await db.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Ingredient not found")

        async with db.execute(
            "SELECT * FROM ingredient_inventory WHERE id = ? AND user_id = ?",
            (ingredient_id, user_id),
        ) as cur:
            row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # The Fridge edit always sends the group, so it's a pick only when code wouldn't
    # give the name that group: a move, or a renamed item keeping its group
    if body.group_name is not None:
        async with get_db() as db:
            auto = (await resolve_groups(db, user_id, [row["name"]]))[row["name"]]
            await remember(db, user_id, row["name"], body.group_name, picked=body.group_name != auto)
            await db.commit()

    return dict(row)


@router.delete("/{ingredient_id}", status_code=204)
async def delete_ingredient(ingredient_id: Id, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM ingredient_inventory WHERE id = ? AND user_id = ?",
            (ingredient_id, user_id),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Missing-ingredient check (meal details highlight them, Confirm is blocked)
# ---------------------------------------------------------------------------


class MissingCheck(BaseModel):
    meal: SizedDict


@router.post("/check")
async def check_missing(body: MissingCheck, user_id: int = Depends(require_user)):
    """Ingredients of a meal that aren't in the user's fridge, matched like the suggestion pipeline."""
    async with get_db() as db:
        async with db.execute(
            "SELECT name FROM ingredient_inventory WHERE user_id = ?", (user_id,)
        ) as cur:
            inventory = [{"name": r["name"]} for r in await cur.fetchall()]
    return {"missing": find_missing_ingredients(body.meal, inventory)}


# ---------------------------------------------------------------------------
# Expiry checking
# ---------------------------------------------------------------------------


@router.get("/expired-count")
async def get_expired_count(user_id: int = Depends(require_user)):
    """Return the count of currently expired, unacknowledged items. No side effects."""
    today = date.today().isoformat()
    async with get_db() as db:
        async with db.execute(
            """SELECT COUNT(*) as count FROM ingredient_inventory
               WHERE user_id = ? AND expiry_date IS NOT NULL
               AND expiry_date <= ? AND expiry_acknowledged = 0""",
            (user_id, today),
        ) as cur:
            row = await cur.fetchone()
            return {"count": row["count"]}


@router.get("/expired", response_model=list[Ingredient])
async def get_expired_ingredients(user_id: int = Depends(require_user)):
    """Return all currently expired, unacknowledged ingredients."""
    today = date.today().isoformat()
    async with get_db() as db:
        async with db.execute(
            """SELECT * FROM ingredient_inventory
               WHERE user_id = ? AND expiry_date IS NOT NULL
               AND expiry_date <= ? AND expiry_acknowledged = 0
               ORDER BY expiry_date""",
            (user_id, today),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


class ExpiredActionRequest(BaseModel):
    delete_ids: list[Id] = Field(default=[], max_length=BULK_ITEMS_MAX)
    keep_ids: list[Id] = Field(default=[], max_length=BULK_ITEMS_MAX)
    shopping_ids: list[Id] = Field(default=[], max_length=BULK_ITEMS_MAX)


@router.post("/expired/action", status_code=200)
async def handle_expired_action(body: ExpiredActionRequest, user_id: int = Depends(require_user)):
    """Handle expired items: delete, keep (acknowledge), or move to shopping list."""
    async with get_db() as db:
        # Delete items
        for ingredient_id in body.delete_ids:
            await db.execute(
                "DELETE FROM ingredient_inventory WHERE id = ? AND user_id = ?",
                (ingredient_id, user_id),
            )

        # Keep items (acknowledge expiry — they stay in inventory but won't show as expired)
        for ingredient_id in body.keep_ids:
            await db.execute(
                "UPDATE ingredient_inventory SET expiry_acknowledged = 1, updated_at = datetime('now') WHERE id = ? AND user_id = ?",
                (ingredient_id, user_id),
            )

        # Shopping items: look up name, add to shopping list, then delete from inventory
        for ingredient_id in body.shopping_ids:
            async with db.execute(
                "SELECT name FROM ingredient_inventory WHERE id = ? AND user_id = ?",
                (ingredient_id, user_id),
            ) as cur:
                row = await cur.fetchone()
            if row:
                await db.execute(
                    """INSERT INTO shopping_list (user_id, item_name) VALUES (?, ?)
                       ON CONFLICT(user_id, item_name) DO NOTHING""",
                    (user_id, row["name"]),
                )
                await db.execute(
                    "DELETE FROM ingredient_inventory WHERE id = ? AND user_id = ?",
                    (ingredient_id, user_id),
                )

        await db.commit()

    return {
        "deleted": len(body.delete_ids),
        "kept": len(body.keep_ids),
        "to_shopping": len(body.shopping_ids),
    }
