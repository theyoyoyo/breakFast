"""
Shared context loading for LLM prompts.

Provides reusable async loaders for user data (profile, supplements,
health rules, ingredients, preferences, habits, history) used by both
the chat WebSocket and analyst REST endpoints.
"""

import asyncio
from datetime import date as date_type


async def fetch_ingredients(db, user_id: int) -> list[dict]:
    async with db.execute(
        "SELECT name, group_name FROM ingredient_inventory WHERE user_id = ? ORDER BY name",
        (user_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def fetch_history(db, user_id: int, limit: int = 10, include_ingredients: bool = False) -> list[dict]:
    cols = "meal_name, ingredients" if include_ingredients else "meal_name"
    async with db.execute(
        f"SELECT {cols} FROM meal_history WHERE user_id = ? ORDER BY logged_at DESC LIMIT ?",
        (user_id, limit),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def fetch_preferences(db, user_id: int) -> dict:
    async with db.execute(
        "SELECT key, value FROM user_preferences WHERE user_id = ?",
        (user_id,),
    ) as cur:
        return {r["key"]: r["value"] for r in await cur.fetchall()}


async def fetch_habits(db, user_id: int) -> tuple[list[str], list[str]]:
    async with db.execute(
        "SELECT description, source FROM user_habits WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ) as cur:
        rows = await cur.fetchall()
        stated = [r["description"] for r in rows if r["source"] == "stated"]
        inferred = [r["description"] for r in rows if r["source"] == "inferred"]
        return stated, inferred


async def fetch_health_rules(db, user_id: int) -> list[dict]:
    async with db.execute(
        "SELECT rule_text, priority FROM health_rules WHERE user_id = ? ORDER BY created_at",
        (user_id,),
    ) as cur:
        return [{"rule_text": r["rule_text"], "priority": r["priority"]} for r in await cur.fetchall()]


async def fetch_profile(db, user_id: int) -> dict | None:
    async with db.execute(
        "SELECT age, gender, height_cm, weight_kg, activity_level FROM user_profiles WHERE user_id = ?",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def fetch_supplements(db, user_id: int) -> list[dict]:
    today = date_type.today().isoformat()
    async with db.execute(
        """
        SELECT s.name, s.contents, s.frequency, COALESCE(l.taken, 0) AS taken_today
        FROM user_supplements s
        LEFT JOIN supplement_daily_log l
            ON l.supplement_id = s.id AND l.user_id = s.user_id AND l.date = ?
        WHERE s.user_id = ?
        ORDER BY s.name
        """,
        (today, user_id),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def load_chat_context(db, user_id: int) -> dict:
    """Load full context for the chat persona."""
    (
        ingredients, history, prefs,
        (stated_habits, inferred_habits),
        health_rules, user_profile, supplements,
    ) = await asyncio.gather(
        fetch_ingredients(db, user_id),
        fetch_history(db, user_id, limit=10),
        fetch_preferences(db, user_id),
        fetch_habits(db, user_id),
        fetch_health_rules(db, user_id),
        fetch_profile(db, user_id),
        fetch_supplements(db, user_id),
    )
    avoid_list = [v for k, v in prefs.items() if k.startswith("avoid:")]
    filtered_prefs = {k: v for k, v in prefs.items() if not k.startswith("avoid:")}

    return {
        "ingredients": ingredients,
        "history": history,
        "preferences": filtered_prefs,
        "stated_habits": stated_habits,
        "inferred_habits": inferred_habits,
        "health_rules": health_rules,
        "user_profile": user_profile,
        "supplements": supplements,
        "avoid_list": avoid_list,
    }


async def load_shopping_context(db, user_id: int) -> dict:
    """Load full context for the shopping persona."""
    (
        ingredients, history, prefs,
        (stated_habits, inferred_habits),
        health_rules, user_profile, supplements,
    ) = await asyncio.gather(
        fetch_ingredients(db, user_id),
        fetch_history(db, user_id, limit=10, include_ingredients=True),
        fetch_preferences(db, user_id),
        fetch_habits(db, user_id),
        fetch_health_rules(db, user_id),
        fetch_profile(db, user_id),
        fetch_supplements(db, user_id),
    )
    avoid_list = [v for k, v in prefs.items() if k.startswith("avoid:")]
    filtered_prefs = {k: v for k, v in prefs.items() if not k.startswith("avoid:")}

    return {
        "ingredients": ingredients,
        "history": history,
        "preferences": filtered_prefs,
        "stated_habits": stated_habits,
        "inferred_habits": inferred_habits,
        "health_rules": health_rules,
        "user_profile": user_profile,
        "supplements": supplements,
        "avoid_list": avoid_list,
    }


async def load_analyst_context(db, user_id: int) -> dict:
    """Load lighter context for the analyst persona."""
    history, profile, supplements, health_rules = await asyncio.gather(
        fetch_history(db, user_id, limit=15, include_ingredients=True),
        fetch_profile(db, user_id),
        fetch_supplements(db, user_id),
        fetch_health_rules(db, user_id),
    )
    return {
        "history": history,
        "user_profile": profile,
        "supplements": supplements,
        "health_rules": health_rules,
    }
