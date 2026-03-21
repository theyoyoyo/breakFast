"""
/auth — login endpoint.
"""

from fastapi import APIRouter, HTTPException
from database import get_db
from auth import hash_pin, create_token
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

    if not user or user["pin_hash"] != hash_pin(body.pin):
        raise HTTPException(status_code=401, detail="Invalid name or pin")

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
