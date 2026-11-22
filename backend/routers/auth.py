"""
/auth — login and logout endpoints.
"""

import asyncio

from fastapi import APIRouter, Header, HTTPException, Request, Response

import config
from auth import (
    bearer_token,
    clear_login_failures,
    create_token,
    hash_pin,
    login_wait,
    needs_rehash,
    record_login_failure,
    revoke_token,
    unknown_user_hash,
    verify_pin,
)
from database import get_db
from models.user import TokenOut, UserLogin

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
    Too many failures for the name on the client's IP get 429 with Retry-After."""
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


@router.post("/logout", status_code=204)
async def logout(authorization: str | None = Header(None)):
    """End the session this request is made with, so its token no longer works.
    The user's other devices keep their own sessions. An unknown or already ended session
    gets 204 too, so logging out twice is harmless."""
    token = bearer_token(authorization)
    if token is not None:
        revoke_token(token)
    return Response(status_code=204)
