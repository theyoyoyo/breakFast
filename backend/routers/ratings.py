"""
/ratings — product rating CRUD endpoints.
All queries are scoped to the authenticated user.
"""

import aiosqlite
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from auth import require_user
from pydantic import BaseModel, Field
from models.limits import Name


router = APIRouter(prefix="/ratings", tags=["ratings"])


class RatingIn(BaseModel):
    product_name: Name
    rating: int = Field(default=10, ge=1, le=10)


class RatingUpdate(BaseModel):
    rating: int = Field(ge=1, le=10)


class RatingOut(BaseModel):
    id: int
    product_name: str
    rating: int
    created_at: str
    updated_at: str


@router.get("/", response_model=list[RatingOut])
async def list_ratings(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM product_ratings WHERE user_id = ? ORDER BY product_name",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/", response_model=RatingOut, status_code=201)
async def create_rating(body: RatingIn, user_id: int = Depends(require_user)):
    async with get_db() as db:
        try:
            await db.execute(
                """
                INSERT INTO product_ratings (user_id, product_name, rating)
                VALUES (?, ?, ?)
                """,
                (user_id, body.product_name, body.rating),
            )
            await db.commit()
        except aiosqlite.IntegrityError:
            raise HTTPException(status_code=409, detail="Product already rated")
        async with db.execute(
            "SELECT * FROM product_ratings WHERE id = last_insert_rowid()"
        ) as cur:
            return dict(await cur.fetchone())


@router.put("/{rating_id}", response_model=RatingOut)
async def update_rating(rating_id: int, body: RatingUpdate, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            """
            UPDATE product_ratings SET rating = ?, updated_at = datetime('now')
            WHERE id = ? AND user_id = ?
            """,
            (body.rating, rating_id, user_id),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM product_ratings WHERE id = ? AND user_id = ?",
            (rating_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Rating not found")
            return dict(row)


@router.delete("/{rating_id}", status_code=204)
async def delete_rating(rating_id: int, user_id: int = Depends(require_user)):
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM product_ratings WHERE id = ? AND user_id = ?",
            (rating_id, user_id),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rating not found")
