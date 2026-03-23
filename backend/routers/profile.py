"""
/profile — user physical profile and supplement management.
All queries are scoped to the authenticated user.
"""

from datetime import date as date_type
import aiosqlite
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from auth import require_user
from pydantic import BaseModel, Field


router = APIRouter(prefix="/profile", tags=["profile"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProfileIn(BaseModel):
    age: int | None = None
    gender: str | None = None
    height_cm: int | None = None
    weight_kg: float | None = None
    activity_level: str | None = None


class ProfileOut(ProfileIn):
    id: int
    user_id: int
    updated_at: str


class SupplementIn(BaseModel):
    name: str
    contents: str = ""
    frequency: str = Field(default="daily", pattern="^(daily|sometimes)$")


class SupplementOut(BaseModel):
    id: int
    user_id: int
    name: str
    contents: str
    frequency: str
    created_at: str


class SupplementToggle(BaseModel):
    taken: bool = True


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------

@router.get("/", response_model=ProfileOut | None)
async def get_profile(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


@router.put("/", response_model=ProfileOut)
async def upsert_profile(body: ProfileIn, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO user_profiles (user_id, age, gender, height_cm, weight_kg, activity_level)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                age = excluded.age,
                gender = excluded.gender,
                height_cm = excluded.height_cm,
                weight_kg = excluded.weight_kg,
                activity_level = excluded.activity_level,
                updated_at = datetime('now')
            """,
            (user_id, body.age, body.gender, body.height_cm, body.weight_kg, body.activity_level),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ) as cur:
            return dict(await cur.fetchone())


# ---------------------------------------------------------------------------
# Supplements CRUD
# ---------------------------------------------------------------------------

@router.get("/supplements", response_model=list[SupplementOut])
async def list_supplements(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM user_supplements WHERE user_id = ? ORDER BY name",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/supplements", response_model=SupplementOut, status_code=201)
async def create_supplement(body: SupplementIn, user_id: int = Depends(require_user)):
    async with get_db() as db:
        try:
            await db.execute(
                "INSERT INTO user_supplements (user_id, name, contents, frequency) VALUES (?, ?, ?, ?)",
                (user_id, body.name, body.contents, body.frequency),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(status_code=409, detail="Supplement already exists")
        async with db.execute(
            "SELECT * FROM user_supplements WHERE id = last_insert_rowid()"
        ) as cur:
            return dict(await cur.fetchone())


@router.put("/supplements/{supp_id}", response_model=SupplementOut)
async def update_supplement(supp_id: int, body: SupplementIn, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            """
            UPDATE user_supplements SET name = ?, contents = ?, frequency = ?
            WHERE id = ? AND user_id = ?
            """,
            (body.name, body.contents, body.frequency, supp_id, user_id),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM user_supplements WHERE id = ? AND user_id = ?",
            (supp_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Supplement not found")
            return dict(row)


@router.delete("/supplements/{supp_id}", status_code=204)
async def delete_supplement(supp_id: int, user_id: int = Depends(require_user)):
    async with get_db() as db:
        # Also delete daily log entries
        await db.execute(
            "DELETE FROM supplement_daily_log WHERE supplement_id = ? AND user_id = ?",
            (supp_id, user_id),
        )
        await db.execute(
            "DELETE FROM user_supplements WHERE id = ? AND user_id = ?",
            (supp_id, user_id),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Supplement daily toggle (for "sometimes" supplements)
# ---------------------------------------------------------------------------

@router.get("/supplements/today", response_model=list[dict])
async def get_today_supplements(user_id: int = Depends(require_user)):
    """List all supplements with their taken_today status."""
    today = date_type.today().isoformat()
    async with get_db() as db:
        async with db.execute(
            """
            SELECT s.*, COALESCE(l.taken, 0) AS taken_today
            FROM user_supplements s
            LEFT JOIN supplement_daily_log l
                ON l.supplement_id = s.id AND l.user_id = s.user_id AND l.date = ?
            WHERE s.user_id = ?
            ORDER BY s.name
            """,
            (today, user_id),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/supplements/{supp_id}/toggle")
async def toggle_supplement_today(
    supp_id: int,
    body: SupplementToggle,
    user_id: int = Depends(require_user),
):
    """Toggle a supplement's taken status for today."""
    today = date_type.today().isoformat()
    async with get_db() as db:
        if body.taken:
            await db.execute(
                """
                INSERT INTO supplement_daily_log (user_id, supplement_id, date, taken)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, supplement_id, date) DO UPDATE SET taken = 1
                """,
                (user_id, supp_id, today),
            )
        else:
            await db.execute(
                "DELETE FROM supplement_daily_log WHERE user_id = ? AND supplement_id = ? AND date = ?",
                (user_id, supp_id, today),
            )
        await db.commit()
    return {"status": "ok", "taken": body.taken}
