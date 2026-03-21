"""
/preferences — user preferences and habits CRUD endpoints.
All queries are scoped to the authenticated user.
"""

from database import get_db
from fastapi import APIRouter, Depends
from auth import require_user
from models.preferences import Habit, HabitCreate, Preference, PreferenceSet

router = APIRouter(prefix="/preferences", tags=["preferences"])


# ---------------------------------------------------------------------------
# Key/value preferences
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[Preference])
async def list_preferences(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM user_preferences WHERE user_id = ? ORDER BY key",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.put("/{key}", response_model=Preference)
async def set_preference(key: str, body: PreferenceSet, user_id: int = Depends(require_user)):
    """Upsert a preference. The key comes from the URL; body only carries the value."""
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO user_preferences (user_id, key, value)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
            """,
            (user_id, key, body.value),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM user_preferences WHERE user_id = ? AND key = ?",
            (user_id, key),
        ) as cur:
            return dict(await cur.fetchone())


@router.delete("/{key}", status_code=204)
async def delete_preference(key: str, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM user_preferences WHERE user_id = ? AND key = ?",
            (user_id, key),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Habits
# ---------------------------------------------------------------------------

@router.get("/habits", response_model=list[Habit])
async def list_habits(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM user_habits WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/habits", response_model=Habit, status_code=201)
async def add_habit(body: HabitCreate, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO user_habits (user_id, description, source) VALUES (?, ?, ?)",
            (user_id, body.description, body.source or "stated"),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM user_habits WHERE id = last_insert_rowid()"
        ) as cur:
            return dict(await cur.fetchone())


@router.delete("/habits/{habit_id}", status_code=204)
async def delete_habit(habit_id: int, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM user_habits WHERE id = ? AND user_id = ?",
            (habit_id, user_id),
        )
        await db.commit()
