"""
/ingredients — CRUD endpoints for the ingredient inventory.
All queries are scoped to the authenticated user.
"""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from database import get_db
from auth import require_user
from fastapi import HTTPException
from models.ingredient import Ingredient, IngredientCreate, IngredientUpdate

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
    async with get_db() as db:
        await db.execute(_UPSERT_SQL, (user_id, body.name, body.expiry_date))
        await db.commit()
        async with db.execute(
            "SELECT * FROM ingredient_inventory WHERE user_id = ? AND name = ?",
            (user_id, body.name),
        ) as cur:
            return dict(await cur.fetchone())


@router.patch("/{ingredient_id}", response_model=Ingredient)
async def update_ingredient(ingredient_id: int, body: IngredientUpdate, user_id: int = Depends(require_user)):
    """Update an ingredient's name and/or expiry date."""
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.expiry_date is not None:
        # Allow clearing expiry with empty string
        updates["expiry_date"] = body.expiry_date if body.expiry_date != "" else None

    async with get_db() as db:
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
    return dict(row)


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
    delete_ids: list[int] = []
    keep_ids: list[int] = []
    shopping_ids: list[int] = []


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


# Keep old endpoint for backward compat with existing tests
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


# ---------------------------------------------------------------------------
# Shopping suggestions (LLM-powered)
# ---------------------------------------------------------------------------


class ShoppingSuggestionsRequest(BaseModel):
    exclude: list[str] = []


@router.post("/shopping-suggestions")
async def get_shopping_suggestions(
    body: ShoppingSuggestionsRequest | None = None,
    user_id: int = Depends(require_user),
):
    """Generate AI-powered shopping suggestions based on full user context."""
    import json as _json
    from services.context import load_shopping_context
    from services.suggestion import build_shopping_prompt
    from services.llm import chat_complete, LLMUnavailableError

    exclude = body.exclude if body else []

    async with get_db() as db:
        ctx = await load_shopping_context(db, user_id)

    prompt = build_shopping_prompt(
        ingredient_inventory=ctx["ingredients"],
        recent_meal_history=ctx["history"],
        user_preferences=ctx["preferences"],
        stated_habits=ctx["stated_habits"],
        inferred_habits=ctx["inferred_habits"],
        health_rules=ctx["health_rules"],
        user_profile=ctx["user_profile"],
        supplements=ctx["supplements"],
        avoid_list=ctx["avoid_list"],
        exclude_names=exclude,
    )

    try:
        response = await chat_complete(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "Benim için alışveriş önerileri hazırla."}],
        )
    except LLMUnavailableError:
        from services.llm import lyric_cycler
        return {"suggestions": [], "lyric": lyric_cycler.next()}

    # Parse the JSON array from the response
    from utils import extract_json_block
    json_str = extract_json_block(response)
    if json_str:
        try:
            suggestions = _json.loads(json_str)
            if isinstance(suggestions, list):
                return {"suggestions": suggestions, "lyric": None}
        except _json.JSONDecodeError:
            pass

    # Fallback: try parsing the entire response as JSON
    try:
        suggestions = _json.loads(response)
        if isinstance(suggestions, list):
            return {"suggestions": suggestions, "lyric": None}
    except _json.JSONDecodeError:
        pass

    # If all parsing fails, return raw text wrapped
    return {"suggestions": [{"name": "error", "reason": "Could not parse suggestions. Raw: " + response[:500]}], "lyric": None}
