"""
Simple token-based authentication.
Tokens are random hex strings stored in memory (no JWT complexity needed).
On server restart, users simply re-login.

PINs are stored as salted scrypt hashes (`scrypt$n$r$p$salt$hash`, hex). Plain SHA-256 hashes
from before scrypt still verify, and a successful login re-hashes them with scrypt.
"""

import hashlib
import hmac
import secrets
from fastapi import Header, HTTPException


# In-memory token store: {token_string: user_id}
_active_tokens: dict[str, int] = {}

# scrypt cost: 32 MiB of memory and about a quarter second per hash (OWASP's N=2^15, r=8, p=3).
# Each stored hash names its own cost, so raising these re-hashes a PIN on its next login.
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 3
_SALT_BYTES = 16
_HASH_BYTES = 32

# New or changed PINs need this many digits; shorter PINs set before the rule still log in
MIN_PIN_LENGTH = 6


def _scrypt(pin: str, salt: bytes, n: int, r: int, p: int, dklen: int = _HASH_BYTES) -> bytes:
    # maxmem is twice what OpenSSL needs (128·r·(n+p+2) bytes); its 32 MiB default is too tight
    return hashlib.scrypt(
        pin.encode(), salt=salt, n=n, r=r, p=p, maxmem=256 * r * (n + p + 2), dklen=dklen,
    )


def hash_pin(pin: str) -> str:
    """Hash a PIN with scrypt and a random salt, so the same PIN never gives the same hash."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = _scrypt(pin, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    """Check a PIN against a stored hash: scrypt, or plain SHA-256 hex from before scrypt."""
    if not stored.startswith("scrypt$"):
        legacy = hashlib.sha256(pin.encode()).hexdigest()
        return hmac.compare_digest(legacy.encode(), stored.encode())
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = bytes.fromhex(digest)
        actual = _scrypt(pin, bytes.fromhex(salt), int(n), int(r), int(p), dklen=len(expected))
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


def needs_rehash(stored: str) -> bool:
    """True when a stored hash isn't scrypt at the current cost (SHA-256 included)."""
    return not stored.startswith(f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}$")


def unknown_user_hash() -> str:
    """A scrypt hash at the current cost that no PIN matches: checking a PIN against it for an
    unknown name takes as long as for a real user, so the reply time doesn't tell names apart."""
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${'00' * _SALT_BYTES}${'00' * _HASH_BYTES}"


def pin_problem(pin: str) -> str | None:
    """Why a new or changed PIN is refused, or None when it has 6+ digits.
    Digits only, because the login screen opens the number pad on phones."""
    if not (pin.isascii() and pin.isdigit()) or len(pin) < MIN_PIN_LENGTH:
        return f"A PIN needs at least {MIN_PIN_LENGTH} digits (0-9 only)."
    return None


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
