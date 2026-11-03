"""
/auth — login endpoint.
"""

import asyncio
from fastapi import APIRouter, HTTPException
from database import get_db
from auth import hash_pin, verify_pin, needs_rehash, unknown_user_hash, create_token
from models.user import UserLogin, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(body: UserLogin):
    """Authenticate with name + pin, get a session token."""
    async with get_db() as db:
        async with db.execute(
            "SELECT id, name, is_admin, created_at, pin_hash FROM users WHERE name = ?",
            (body.name,),
        ) as cur:
            user = await cur.fetchone()

    # scrypt is slow on purpose, so it runs off the event loop (chat streams keep going)
    stored = user["pin_hash"] if user else unknown_user_hash()
    if not await asyncio.to_thread(verify_pin, body.pin, stored) or not user:
        raise HTTPException(status_code=401, detail="Invalid name or pin")

    # A hash from before scrypt (or at an older cost) is replaced while the PIN is at hand
    if needs_rehash(stored):
        new_hash = await asyncio.to_thread(hash_pin, body.pin)
        async with get_db() as db:
            await db.execute("UPDATE users SET pin_hash = ? WHERE id = ?", (new_hash, user["id"]))
            await db.commit()

    token = create_token(user["id"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "is_admin": user["is_admin"],
            "created_at": user["created_at"],
        },
    }
