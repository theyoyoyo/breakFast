"""
Simple token-based authentication.
Tokens are random hex strings stored in memory (no JWT complexity needed).
On server restart, users simply re-login.
"""

import hashlib
import secrets
from fastapi import Header, HTTPException


# In-memory token store: {token_string: user_id}
_active_tokens: dict[str, int] = {}


def hash_pin(pin: str) -> str:
    """Hash a pin with SHA-256. Simple and sufficient for home use."""
    return hashlib.sha256(pin.encode()).hexdigest()


def create_token(user_id: int) -> str:
    """Generate a new session token for a user."""
    token = secrets.token_hex(32)
    _active_tokens[token] = user_id
    return token


def revoke_token(token: str) -> None:
    """Remove a token (logout)."""
    _active_tokens.pop(token, None)


def get_user_id_from_token(token: str) -> int | None:
    """Look up user_id from token. Returns None if invalid."""
    return _active_tokens.get(token)


async def require_user(authorization: str = Header(..., alias="Authorization")) -> int:
    """
    FastAPI dependency that extracts user_id from the Authorization header.
    Header format: "Bearer <token>"
    Returns user_id or raises 401.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    user_id = get_user_id_from_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_id
