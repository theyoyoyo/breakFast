"""
Simple token-based authentication.
Tokens are random hex strings stored in memory (no JWT complexity needed).
On server restart, users simply re-login.

PINs are stored as salted scrypt hashes (`scrypt$n$r$p$salt$hash`, hex). Plain SHA-256 hashes
from before scrypt still verify, and a successful login re-hashes them with scrypt.
Failed logins are counted in memory too, per user name on each client IP.
"""

import hashlib
import hmac
import math
import secrets
import time
from dataclasses import dataclass
from fastapi import Header, HTTPException


# In-memory token store: {token_string: user_id}
_active_tokens: dict[str, int] = {}

# scrypt cost: OWASP's N=2^15, r=8, p=3 (32 MiB of memory per hash).
# Each stored hash names its own cost, so raising these re-hashes a PIN on its next login.
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 3
_SALT_BYTES = 16
_HASH_BYTES = 32

# New or changed PINs take this many digits; shorter PINs set before the rule still log in
MIN_PIN_LENGTH = 6
MAX_PIN_LENGTH = 10

# Login rate limit, per user name on each client IP: the 5th failure in a row locks that name on
# that IP for 30 s, and each further one doubles the wait up to 15 min. Failures are forgotten
# after an hour without one, and a successful login clears them. One counter per pair, so typos
# on one device don't lock other users there, and nobody can lock a user out of their own device.
# Guessing from many IPs would take many devices on the server's own network (Tailscale or LAN).
MAX_LOGIN_FAILURES = 5
LOGIN_BASE_WAIT = 30
LOGIN_MAX_WAIT = 15 * 60
LOGIN_FAILURE_WINDOW = 60 * 60

# Seconds on a steady clock; tests replace it to move time forward
_clock = time.monotonic


@dataclass
class _Failures:
    count: int = 0
    last: float = 0.0
    locked_until: float = 0.0


# {(name, client IP): its failed logins}
_login_failures: dict[tuple[str, str | None], _Failures] = {}


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
    """Why a new or changed PIN is refused, or None when it has 6-10 digits.
    Digits only, because the login screen opens the number pad on phones."""
    if not (pin.isascii() and pin.isdigit()) or not MIN_PIN_LENGTH <= len(pin) <= MAX_PIN_LENGTH:
        return f"A PIN needs {MIN_PIN_LENGTH}-{MAX_PIN_LENGTH} digits (0-9 only)."
    return None


def login_wait(name: str, ip: str | None) -> int:
    """Seconds until this name may try to log in again from this IP (0 = now)."""
    f = _login_failures.get((name, ip))
    wait = f.locked_until - _clock() if f else 0
    return math.ceil(wait) if wait > 0 else 0


def record_login_failure(name: str, ip: str | None) -> None:
    """Count a failed login for the name on this IP, locking the pair once there are too many."""
    now = _clock()
    # Drop counters quiet for a whole window (longer than any lock), so the store stays small
    for key in [k for k, f in _login_failures.items() if now - f.last > LOGIN_FAILURE_WINDOW]:
        del _login_failures[key]
    f = _login_failures.setdefault((name, ip), _Failures())
    f.count += 1
    f.last = now
    if f.count >= MAX_LOGIN_FAILURES:
        doublings = min(f.count - MAX_LOGIN_FAILURES, 10)
        f.locked_until = now + min(LOGIN_BASE_WAIT * 2**doublings, LOGIN_MAX_WAIT)


def clear_login_failures(name: str, ip: str | None) -> None:
    """Forget the failed logins of a name on this IP (after a successful login)."""
    _login_failures.pop((name, ip), None)


def create_token(user_id: int) -> str:
    """Generate a new session token for a user."""
    token = secrets.token_hex(32)
    _active_tokens[token] = user_id
    return token


def revoke_token(token: str) -> None:
    """End a session (logout); an unknown or already ended token is ignored."""
    _active_tokens.pop(token, None)


def get_user_id_from_token(token: str) -> int | None:
    """Look up user_id from token. Returns None if invalid."""
    return _active_tokens.get(token)


def bearer_token(authorization: str | None) -> str | None:
    """The token in an "Authorization: Bearer <token>" header, or None for any other header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization[7:]


# A browser can't set headers on a WebSocket except its subprotocols, so the app sends its
# token there as "bearer" then the token, and the server accepts with "bearer"
SOCKET_AUTH_PROTOCOL = "bearer"


def socket_token(protocols: list[str]) -> str | None:
    """The token in a socket's Sec-WebSocket-Protocol header ("bearer", then the token), or None."""
    if len(protocols) != 2 or protocols[0] != SOCKET_AUTH_PROTOCOL:
        return None
    return protocols[1]


async def require_user(authorization: str = Header(..., alias="Authorization")) -> int:
    """
    FastAPI dependency that extracts user_id from the Authorization header.
    Header format: "Bearer <token>"
    Returns user_id or raises 401.
    """
    token = bearer_token(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    user_id = get_user_id_from_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_id
