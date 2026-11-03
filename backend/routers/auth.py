"""
/auth — login endpoint.
"""

import asyncio
from fastapi import APIRouter, HTTPException, Request
import config
from database import get_db
from auth import (
    hash_pin, verify_pin, needs_rehash, unknown_user_hash, create_token,
    login_wait, record_login_failure, clear_login_failures,
)
from models.user import UserLogin, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _too_many_failures(wait: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=f"Too many failed logins. Try again in {wait} seconds.",
        headers={"Retry-After": str(wait)},
    )


@router.post("/login", response_model=TokenOut)
async def login(body: UserLogin, request: Request):
    """Authenticate with name + pin, get a session token.
    Too many failures for the name or the client IP get 429 with Retry-After."""
    ip = request.client.host if request.client else None
    wait = login_wait(body.name, ip)
    if wait:
        raise _too_many_failures(wait)
    # Counted as a failure before the PIN check, so parallel requests can't all slip in under
    # the limit; a success clears it again
    record_login_failure(body.name, ip)

    async with get_db() as db:
        async with db.execute(
            "SELECT id, name, is_admin, created_at, pin_hash FROM users WHERE name = ?",
            (body.name,),
        ) as cur:
            user = await cur.fetchone()

    # scrypt is slow on purpose, so it runs off the event loop (chat streams keep going).
    # An empty PIN (the demo account's) logs in only while DEMO_USER is on, so a demo account
    # left over from a try-out is locked once the setting is off.
    stored = user["pin_hash"] if user else unknown_user_hash()
    pin_allowed = bool(body.pin) or config.DEMO_USER
    if not (pin_allowed and await asyncio.to_thread(verify_pin, body.pin, stored)) or not user:
        wait = login_wait(body.name, ip)
        if wait:
            raise _too_many_failures(wait)
        raise HTTPException(status_code=401, detail="Invalid name or pin")
    clear_login_failures(body.name, ip)

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
