"""
Meal history insights — aggregate patterns from old meals into inferred habits,
then prune old records. Runs once at startup via lifespan.

The goal is DIVERSIFICATION, not reinforcement:
- Frequently eaten items → "already getting enough"
- Rarely eaten healthy items → "actively suggest these"
- Rating patterns → guide the style of new suggestions
"""

import json
from database import get_db

# Meals older than this are pruned after insights are extracted
_RETENTION_DAYS = 30

# Health-aligned items from the system prompt — used to detect gaps
_HEALTHY_POOL = {
    "eggs", "pumpkin seeds", "legumes", "chickpeas", "walnuts", "flaxseed",
    "yogurt", "kefir", "whole grains", "leafy greens", "berries", "tomatoes",
    "olive oil", "fatty fish", "oats", "spinach", "avocado",
}


async def _count_meals(db, user_id: int) -> int:
    """Total meals in the retention window."""
    async with db.execute(
        "SELECT COUNT(*) as c FROM meal_history WHERE user_id = ? AND logged_at >= datetime('now', ?)",
        (user_id, f"-{_RETENTION_DAYS} days"),
    ) as cur:
        return (await cur.fetchone())["c"]


async def _top_ingredients(db, user_id: int, limit: int = 10) -> list[dict]:
    """
    Most frequently used ingredients in the retention window.
    Returns [{"name": "eggs", "count": 18}, ...].
    """
    async with db.execute(
        """
        SELECT ingredients FROM meal_history
        WHERE user_id = ? AND logged_at >= datetime('now', ?)
        """,
        (user_id, f"-{_RETENTION_DAYS} days"),
    ) as cur:
        rows = await cur.fetchall()

    # Flatten JSON ingredient lists and count occurrences
    counts: dict[str, int] = {}
    for row in rows:
        try:
            items = json.loads(row["ingredients"]) if row["ingredients"] else []
        except (json.JSONDecodeError, TypeError):
            continue
        for item in items:
            name = _extract_name(item)
            if name:
                counts[name] = counts.get(name, 0) + 1

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"name": n, "count": c} for n, c in sorted_items[:limit]]


def _extract_name(item) -> str:
    """Extract ingredient name from either a structured dict or a plain string."""
    if isinstance(item, dict):
        return (item.get("name") or "").strip().lower()
    if isinstance(item, str):
        return item.strip().lower().split()[-1] if item.strip() else ""
    return ""


async def _avg_prep_time(db, user_id: int) -> float | None:
    """Average prep time across meals with a recorded value."""
    async with db.execute(
        """
        SELECT AVG(prep_time_min) as avg_time FROM meal_history
        WHERE user_id = ? AND prep_time_min IS NOT NULL
          AND logged_at >= datetime('now', ?)
        """,
        (user_id, f"-{_RETENTION_DAYS} days"),
    ) as cur:
        row = await cur.fetchone()
        return round(row["avg_time"], 1) if row["avg_time"] else None


async def _high_rated_patterns(db, user_id: int) -> list[str]:
    """Ingredient names that appear most in highly-rated meals (rating=5)."""
    async with db.execute(
        """
        SELECT ingredients FROM meal_history
        WHERE user_id = ? AND rating = 5 AND logged_at >= datetime('now', ?)
        """,
        (user_id, f"-{_RETENTION_DAYS} days"),
    ) as cur:
        rows = await cur.fetchall()

    counts: dict[str, int] = {}
    for row in rows:
        try:
            items = json.loads(row["ingredients"]) if row["ingredients"] else []
        except (json.JSONDecodeError, TypeError):
            continue
        for item in items:
            name = _extract_name(item)
            if name:
                counts[name] = counts.get(name, 0) + 1

    # Return top 5 ingredients from liked meals
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [n for n, _ in sorted_items[:5]]


async def _build_insights(db, user_id: int) -> list[str]:
    """
    Analyze meal history and produce human-readable insight strings.
    These become inferred habits in the system prompt.
    """
    total = await _count_meals(db, user_id)
    if total < 3:
        return []  # not enough data to infer anything

    insights: list[str] = []

    # 1. Frequently eaten — "already getting enough"
    top = await _top_ingredients(db, user_id)
    if top:
        frequent = [f"{i['name']} ({i['count']}x)" for i in top[:5]]
        insights.append(f"Already eating enough: {', '.join(frequent)}")

    # 2. Gaps — healthy items rarely or never eaten
    eaten_names = {i["name"] for i in top}
    missing = _HEALTHY_POOL - eaten_names
    if missing:
        insights.append(f"Rarely eaten, suggest more: {', '.join(sorted(missing))}")

    # 3. Average prep time
    avg = await _avg_prep_time(db, user_id)
    if avg is not None:
        insights.append(f"Average prep time: {avg} min")

    # 4. High-rated patterns
    liked = await _high_rated_patterns(db, user_id)
    if liked:
        insights.append(
            f"High-rated meals tend to include: {', '.join(liked)}"
        )

    return insights


async def refresh_insights_for_user(user_id: int) -> int:
    """
    Refresh insights for a specific user.
    1. Aggregate insights from meal history
    2. Replace old inferred habits with fresh ones
    3. Prune meals older than the retention window
    Returns the number of insights written.
    """
    async with get_db() as db:
        insights = await _build_insights(db, user_id)

        # Clear previous inferred habits for this user (stated habits are untouched)
        await db.execute(
            "DELETE FROM user_habits WHERE user_id = ? AND source = 'inferred'",
            (user_id,),
        )

        # Write fresh insights
        if insights:
            await db.executemany(
                "INSERT INTO user_habits (user_id, description, source) VALUES (?, ?, 'inferred')",
                [(user_id, desc) for desc in insights],
            )

        # Prune old meals for this user
        await db.execute(
            "DELETE FROM meal_history WHERE user_id = ? AND logged_at < datetime('now', ?)",
            (user_id, f"-{_RETENTION_DAYS} days"),
        )

        await db.commit()

    return len(insights)


async def refresh_insights() -> int:
    """
    Main entry point — called at startup.
    Refreshes insights for ALL users.
    """
    async with get_db() as db:
        async with db.execute("SELECT id FROM users") as cur:
            user_ids = [row["id"] for row in await cur.fetchall()]

    total = 0
    for uid in user_ids:
        total += await refresh_insights_for_user(uid)
    return total
