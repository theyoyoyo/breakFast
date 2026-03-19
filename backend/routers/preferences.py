"""
/preferences — user preferences and habits CRUD endpoints.
"""

from database import get_db
from fastapi import APIRouter
from models.preferences import Habit, HabitCreate, Preference, PreferenceSet

router = APIRouter(prefix="/preferences", tags=["preferences"])


# ---------------------------------------------------------------------------
# Key/value preferences
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[Preference])
async def list_preferences():
    async with get_db() as db:
        async with db.execute("SELECT * FROM user_preferences ORDER BY key") as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.put("/{key}", response_model=Preference)
async def set_preference(key: str, body: PreferenceSet):
    """Upsert a preference. The key comes from the URL; body only carries the value."""
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO user_preferences (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
            """,
            (key, body.value),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM user_preferences WHERE key = ?", (key,)
        ) as cur:
            return dict(await cur.fetchone())


@router.delete("/{key}", status_code=204)
async def delete_preference(key: str):
    async with get_db() as db:
        await db.execute("DELETE FROM user_preferences WHERE key = ?", (key,))
        await db.commit()


# ---------------------------------------------------------------------------
# Habits
# ---------------------------------------------------------------------------

@router.get("/habits", response_model=list[Habit])
async def list_habits():
    async with get_db() as db:
        async with db.execute("SELECT * FROM user_habits ORDER BY created_at DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/habits", response_model=Habit, status_code=201)
async def add_habit(body: HabitCreate):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO user_habits (description, source) VALUES (?, ?)",
            (body.description, body.source or "stated"),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM user_habits WHERE id = last_insert_rowid()"
        ) as cur:
            return dict(await cur.fetchone())


@router.delete("/habits/{habit_id}", status_code=204)
async def delete_habit(habit_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM user_habits WHERE id = ?", (habit_id,))
        await db.commit()
