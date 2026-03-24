"""
/shopping — CRUD endpoints for the persistent shopping list.
All queries are scoped to the authenticated user.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_db
from auth import require_user

router = APIRouter(prefix="/shopping", tags=["shopping"])


class ShoppingItem(BaseModel):
    id: int
    item_name: str
    created_at: str


class ShoppingItemCreate(BaseModel):
    item_name: str


class BoughtRequest(BaseModel):
    ids: list[int]
    expiry_dates: Optional[dict[str, str]] = None  # {item_name: expiry_date}


@router.get("/", response_model=list[ShoppingItem])
async def list_shopping(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM shopping_list WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/", response_model=ShoppingItem, status_code=201)
async def add_shopping_item(body: ShoppingItemCreate, user_id: int = Depends(require_user)):
    """Add an item to the shopping list. Ignores duplicates."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO shopping_list (user_id, item_name) VALUES (?, ?)
               ON CONFLICT(user_id, item_name) DO NOTHING""",
            (user_id, body.item_name),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM shopping_list WHERE user_id = ? AND item_name = ?",
            (user_id, body.item_name),
        ) as cur:
            return dict(await cur.fetchone())


@router.post("/bulk", status_code=201)
async def bulk_add_shopping(items: list[ShoppingItemCreate], user_id: int = Depends(require_user)):
    """Add multiple items to the shopping list. Skips duplicates."""
    async with get_db() as db:
        await db.executemany(
            """INSERT INTO shopping_list (user_id, item_name) VALUES (?, ?)
               ON CONFLICT(user_id, item_name) DO NOTHING""",
            [(user_id, item.item_name) for item in items],
        )
        await db.commit()
    return {"added": len(items)}


@router.delete("/{item_id}", status_code=204)
async def delete_shopping_item(item_id: int, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM shopping_list WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        )
        await db.commit()


@router.post("/bought", status_code=200)
async def bought_items(body: BoughtRequest, user_id: int = Depends(require_user)):
    """Mark items as bought: add them as ingredients and remove from shopping list.

    Optionally accepts expiry_dates mapping item_name -> expiry_date.
    """
    async with get_db() as db:
        # Get item names for the given IDs
        if not body.ids:
            return {"bought": 0}
        placeholders = ",".join("?" for _ in body.ids)
        async with db.execute(
            f"SELECT id, item_name FROM shopping_list WHERE id IN ({placeholders}) AND user_id = ?",
            [*body.ids, user_id],
        ) as cur:
            items = [dict(r) for r in await cur.fetchall()]

        # Add each as an ingredient
        for item in items:
            expiry = (body.expiry_dates or {}).get(item["item_name"])
            await db.execute(
                """INSERT INTO ingredient_inventory (user_id, name, expiry_date)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, name) DO UPDATE SET
                       expiry_date = excluded.expiry_date,
                       updated_at = datetime('now')""",
                (user_id, item["item_name"], expiry),
            )

        # Remove bought items from shopping list
        await db.execute(
            f"DELETE FROM shopping_list WHERE id IN ({placeholders}) AND user_id = ?",
            [*body.ids, user_id],
        )
        await db.commit()

    return {"bought": len(items)}
