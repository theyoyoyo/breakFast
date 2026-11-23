"""
/shopping — CRUD endpoints for the persistent shopping list, and the Fridge tab's
shopping suggestions list (/shopping/suggestions), kept per user so every device shows
the same one. Items removed from it with × can be brought back from Settings
(/shopping/suggestions/removed). Suggest Shopping asks the Shopping persona for new items
(/shopping/suggestions/generate). A suggestions change tells the user's open chats (services/chat_sync).
All queries are scoped to the authenticated user.
"""

import logging
import random
from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from auth import require_user
from database import get_db
from models.limits import BULK_ITEMS_MAX, Name, Note, ShortText
from services import chat_sync
from services.context import load_shopping_context
from services.ingredient_groups import remember, resolve_groups
from services.llm import LLMUnavailableError, chat_json, lyric_cycler
from services.personas import build_shopping_prompt
from services.shopping import (
    REMOVED_DAYS,
    SUGGESTIONS_SCHEMA,
    new_suggestions,
    parse_suggestions,
    pick_input,
    recently_removed,
    shopping_request,
)

router = APIRouter(prefix="/shopping", tags=["shopping"])


class ShoppingItem(BaseModel):
    id: int
    item_name: str
    created_at: str


class ShoppingItemCreate(BaseModel):
    item_name: Name


class BoughtRequest(BaseModel):
    ids: list[int] = Field(max_length=BULK_ITEMS_MAX)
    expiry_dates: Optional[dict[Name, ShortText]] = Field(default=None, max_length=BULK_ITEMS_MAX)  # {item_name: expiry_date}


class SuggestionItem(BaseModel):
    name: Name = Field(min_length=1)
    reason: Note = ""
    checked: bool = True


class SuggestionsState(BaseModel):
    items: list[SuggestionItem] = Field(default=[], max_length=BULK_ITEMS_MAX)   # the whole list, in order
    removed: list[Name] = Field(default=[], max_length=BULK_ITEMS_MAX)            # names just removed with ×


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
async def bulk_add_shopping(
    items: list[ShoppingItemCreate] = Body(max_length=BULK_ITEMS_MAX),
    user_id: int = Depends(require_user),
):
    """Add multiple items to the shopping list. Skips duplicates."""
    async with get_db() as db:
        await db.executemany(
            """INSERT INTO shopping_list (user_id, item_name) VALUES (?, ?)
               ON CONFLICT(user_id, item_name) DO NOTHING""",
            [(user_id, item.item_name) for item in items],
        )
        await db.commit()
    return {"added": len(items)}


@router.delete("/", status_code=204)
async def clear_shopping(user_id: int = Depends(require_user)):
    """Empty this user's shopping list (the list's Delete all)."""
    async with get_db() as db:
        await db.execute("DELETE FROM shopping_list WHERE user_id = ?", (user_id,))
        await db.commit()


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

        # Add each as an ingredient, in the user's group for it, else the food list's
        groups = await resolve_groups(db, user_id, [item["item_name"] for item in items])

        for item in items:
            expiry = (body.expiry_dates or {}).get(item["item_name"])
            group = groups[item["item_name"]]
            await db.execute(
                """INSERT INTO ingredient_inventory (user_id, name, expiry_date, group_name)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id, name) DO UPDATE SET
                       expiry_date = excluded.expiry_date,
                       group_name = excluded.group_name,
                       updated_at = datetime('now')""",
                (user_id, item["item_name"], expiry, group),
            )
            await remember(db, user_id, item["item_name"], group, picked=False)

        # Remove bought items from shopping list
        await db.execute(
            f"DELETE FROM shopping_list WHERE id IN ({placeholders}) AND user_id = ?",
            [*body.ids, user_id],
        )
        await db.commit()

    return {"bought": len(items)}


# ---------------------------------------------------------------------------
# Shopping suggestions list (Fridge tab)
# ---------------------------------------------------------------------------


async def _suggestion_items(db, user_id: int) -> list[dict]:
    async with db.execute(
        """SELECT name, reason, checked FROM shopping_suggestions
           WHERE user_id = ? AND removed_at IS NULL
           ORDER BY position, id""",
        (user_id,),
    ) as cur:
        return [{"name": r["name"], "reason": r["reason"], "checked": bool(r["checked"])} for r in await cur.fetchall()]


@router.get("/suggestions")
async def get_suggestions(user_id: int = Depends(require_user)):
    """The suggestions list with each item's check, in order."""
    async with get_db() as db:
        return {"items": await _suggestion_items(db, user_id)}


@router.put("/suggestions")
async def put_suggestions(body: SuggestionsState, user_id: int = Depends(require_user)):
    """Replace the suggestions list. Names in `removed` were removed with ×: they are kept
    with the time, so new suggestions leave them out for REMOVED_DAYS days.
    Items that are simply gone (sent to the shopping list) are deleted."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM shopping_suggestions WHERE user_id = ? AND removed_at IS NULL", (user_id,)
        )
        await db.execute(
            "DELETE FROM shopping_suggestions WHERE user_id = ? AND removed_at < datetime('now', ?)",
            (user_id, f"-{REMOVED_DAYS} days"),
        )
        await db.executemany(
            """INSERT INTO shopping_suggestions (user_id, name, removed_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(user_id, name) DO UPDATE SET removed_at = excluded.removed_at""",
            [(user_id, name) for name in body.removed],
        )
        await db.executemany(
            """INSERT INTO shopping_suggestions (user_id, name, reason, checked, position) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, name) DO UPDATE SET
                   reason = excluded.reason, checked = excluded.checked,
                   position = excluded.position, removed_at = NULL""",
            [(user_id, item.name, item.reason, int(item.checked), i) for i, item in enumerate(body.items)],
        )
        await db.commit()
        items = await _suggestion_items(db, user_id)
    await chat_sync.notify_user(user_id, {"type": "shopping_suggestions_updated"})
    return {"items": items}


@router.get("/suggestions/removed")
async def get_removed_count(user_id: int = Depends(require_user)):
    """How many items removed with × new suggestions leave out right now (removed in the last
    REMOVED_DAYS days), for Settings' Bring back button."""
    async with get_db() as db:
        return {"count": len(await recently_removed(db, user_id))}


@router.delete("/suggestions/removed", status_code=204)
async def bring_back_removed(user_id: int = Depends(require_user)):
    """Forget the items removed with ×, so the next Suggest Shopping may bring them back.
    The list itself and the avoid list stay as they are."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM shopping_suggestions WHERE user_id = ? AND removed_at IS NOT NULL", (user_id,)
        )
        await db.commit()
    await chat_sync.notify_user(user_id, {"type": "shopping_suggestions_updated"})


# ---------------------------------------------------------------------------
# Shopping suggestions (LLM-powered): new items for the list above
# ---------------------------------------------------------------------------


class ShoppingSuggestionsRequest(BaseModel):
    exclude: list[Name] = Field(default=[], max_length=BULK_ITEMS_MAX)


# What the app shows when suggestions fail; the cause goes to the server log only
SUGGESTIONS_FAILED = "Could not get suggestions. Please try again."


@router.post("/suggestions/generate")
async def get_shopping_suggestions(
    body: ShoppingSuggestionsRequest | None = None,
    user_id: int = Depends(require_user),
):
    """Generate AI-powered shopping suggestions based on full user context.

    Code keeps only new items: anything in the fridge, on the shopping list,
    already shown (`exclude`), on the avoid list or removed from the suggestions
    list in the last 7 days is dropped by exact name.
    When a whole reply is repeats, the model is asked once more.
    """
    shown = list(body.exclude) if body else []

    try:
        async with get_db() as db:
            ctx = await load_shopping_context(db, user_id)
            removed = await recently_removed(db, user_id)
    except Exception:
        logging.exception("Shopping context load failed")
        return {"suggestions": [], "lyric": lyric_cycler.next(), "error": SUGGESTIONS_FAILED}

    # The avoid list is a hard ban, so code enforces it beside the prompt rule.
    # Items removed with × are left out by code only, so the prompt stays the same.
    known = [i["name"] for i in ctx["ingredients"]] + ctx["shopping_list"] + ctx["avoid_list"] + removed
    # This press shows a random share of the fridge and of the taste hints, so it starts somewhere new
    fridge, hints = pick_input(ctx, random.Random())

    for _ in range(2):
        try:
            prompt = build_shopping_prompt(
                taste_hints=hints,
                user_preferences=ctx["preferences"],
                health_rules=ctx["health_rules"],
                user_profile=ctx["user_profile"],
                supplements=ctx["supplements"],
                avoid_list=ctx["avoid_list"],
                shopping_list=ctx["shopping_list"],
                ratings=ctx["ratings"],
                language=ctx["language"],
                country=ctx["country"],
            )
            reply = await chat_json(
                system_prompt=prompt,
                messages=[{"role": "user", "content": shopping_request(ctx["language"], shown, fridge)}],
                schema=SUGGESTIONS_SCHEMA,
                temperature=0.6,
                task="shopping",
                language=ctx["language"],
            )
        except LLMUnavailableError:
            return {"suggestions": [], "lyric": lyric_cycler.next()}
        except Exception:
            logging.exception("Shopping LLM call failed")
            return {"suggestions": [], "lyric": lyric_cycler.next(), "error": SUGGESTIONS_FAILED}

        items = parse_suggestions(reply)
        if items is None:
            logging.warning("Shopping suggestions: could not parse the reply: %r", reply)
            return {"suggestions": [], "lyric": None, "error": "Could not read the AI reply. Please try again."}

        fresh = new_suggestions(items, known + shown, ctx["dishes"])
        if fresh:
            return {"suggestions": fresh, "lyric": None}
        shown += [i["name"] for i in items]

    return {"suggestions": [], "lyric": None}
