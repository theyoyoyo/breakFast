"""
Tests for auth — login, logout, token management, endpoint protection.
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import aiosqlite
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import auth
import config
import database
from auth import hash_pin, needs_rehash, verify_pin
from models.ingredient import DEMO_FRIDGE
from tests.chat_socket import open_chat


@pytest_asyncio.fixture
async def unauth_client(tmp_path, monkeypatch):
    """AsyncClient WITHOUT auth token for testing login and 401 responses."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    # Create a user for login tests
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash, is_admin) VALUES (?, ?, ?)",
            ("Alice", hash_pin("1234"), 1),
        )
        await db.commit()

    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# The right name and PIN log in and return a token with the user's name
async def test_login_success(unauth_client):
    r = await unauth_client.post("/auth/login", json={"name": "Alice", "pin": "1234"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data["user"]["name"] == "Alice"
    assert data["user"]["is_admin"] == 1


# A wrong PIN for a known name is refused with 401
async def test_login_wrong_pin(unauth_client):
    r = await unauth_client.post("/auth/login", json={"name": "Alice", "pin": "9999"})
    assert r.status_code == 401


# A name with no account is refused with 401, like a wrong PIN
async def test_login_unknown_user(unauth_client):
    r = await unauth_client.post("/auth/login", json={"name": "Nobody", "pin": "1234"})
    assert r.status_code == 401


async def _pin_hash(name: str) -> str:
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        async with db.execute("SELECT pin_hash FROM users WHERE name = ?", (name,)) as cur:
            return (await cur.fetchone())[0]


async def _add_sha256_user(name: str, pin: str) -> None:
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash) VALUES (?, ?)",
            (name, hashlib.sha256(pin.encode()).hexdigest()),
        )
        await db.commit()


# The same PIN hashed twice gives two different salted scrypt hashes, and both verify
def test_hash_pin_is_salted():
    first, second = hash_pin("482916"), hash_pin("482916")
    assert first != second
    assert first.startswith("scrypt$") and second.startswith("scrypt$")
    assert verify_pin("482916", first) and verify_pin("482916", second)


# A wrong PIN fails against a scrypt hash, an old SHA-256 hash and a broken hash
def test_verify_pin_rejects_wrong_pin():
    assert not verify_pin("482917", hash_pin("482916"))
    assert not verify_pin("482917", hashlib.sha256(b"482916").hexdigest())
    assert not verify_pin("482916", "scrypt$broken")


# The production scrypt cost fits the memory limit hashlib gets, so real logins don't fail
@pytest.mark.real_scrypt
def test_real_scrypt_cost_hashes_and_verifies():
    stored = hash_pin("482916")
    assert stored.startswith("scrypt$32768$8$3$")
    assert verify_pin("482916", stored)
    assert not needs_rehash(stored)


# An old SHA-256 hash (and its short PIN) still logs in, and that login replaces it with scrypt
async def test_login_upgrades_sha256_hash(unauth_client):
    await _add_sha256_user("Bob", "1357")
    r = await unauth_client.post("/auth/login", json={"name": "Bob", "pin": "1357"})
    assert r.status_code == 200
    stored = await _pin_hash("Bob")
    assert stored.startswith("scrypt$") and verify_pin("1357", stored)

    r = await unauth_client.post("/auth/login", json={"name": "Bob", "pin": "1357"})
    assert r.status_code == 200


# A wrong PIN leaves an old SHA-256 hash as it was
async def test_wrong_pin_keeps_sha256_hash(unauth_client):
    await _add_sha256_user("Bob", "1357")
    r = await unauth_client.post("/auth/login", json={"name": "Bob", "pin": "7531"})
    assert r.status_code == 401
    assert await _pin_hash("Bob") == hashlib.sha256(b"1357").hexdigest()


# A login with a hash at the current cost doesn't rewrite it
async def test_login_keeps_current_hash(unauth_client):
    before = await _pin_hash("Alice")
    r = await unauth_client.post("/auth/login", json={"name": "Alice", "pin": "1234"})
    assert r.status_code == 200
    assert await _pin_hash("Alice") == before


@pytest.fixture
def clock(monkeypatch):
    """The rate limit's clock, moved forward by adding seconds to clock[0]."""
    now = [1000.0]
    monkeypatch.setattr(auth, "_clock", lambda: now[0])
    return now


async def _login(client, name: str, pin: str) -> int:
    return (await client.post("/auth/login", json={"name": name, "pin": pin})).status_code


# The 5th failure in a row gets 429 with Retry-After, and even the right PIN waits it out
async def test_login_rate_limit_kicks_in(unauth_client, clock):
    for _ in range(4):
        assert await _login(unauth_client, "Alice", "999999") == 401
    r = await unauth_client.post("/auth/login", json={"name": "Alice", "pin": "999999"})
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "30"
    assert "30 seconds" in r.json()["detail"]

    assert await _login(unauth_client, "Alice", "1234") == 429
    clock[0] += 31
    assert await _login(unauth_client, "Alice", "1234") == 200


# A page on another origin (the dev server's port) may read Retry-After from a 429
async def test_login_rate_limit_exposes_retry_after(unauth_client, clock):
    for _ in range(4):
        assert await _login(unauth_client, "Alice", "999999") == 401
    r = await unauth_client.post(
        "/auth/login",
        json={"name": "Alice", "pin": "999999"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert r.status_code == 429
    assert "retry-after" in r.headers["access-control-expose-headers"].lower()


# Each failure after the limit doubles the wait, up to 15 minutes
async def test_login_rate_limit_wait_grows(unauth_client, clock):
    waits = []
    for _ in range(10):
        r = await unauth_client.post("/auth/login", json={"name": "Alice", "pin": "999999"})
        if r.status_code == 429:
            waits.append(int(r.headers["Retry-After"]))
            clock[0] += waits[-1]
    assert waits == [30, 60, 120, 240, 480, 900]


# A successful login clears the count, so the next failures start from zero
async def test_login_success_resets_rate_limit(unauth_client, clock):
    for _ in range(4):
        assert await _login(unauth_client, "Alice", "999999") == 401
    assert await _login(unauth_client, "Alice", "1234") == 200
    for _ in range(4):
        assert await _login(unauth_client, "Alice", "999999") == 401


# Failures more than an hour apart don't add up
async def test_login_failures_forgotten_after_window(unauth_client, clock):
    for _ in range(4):
        assert await _login(unauth_client, "Alice", "999999") == 401
    clock[0] += 3601
    for _ in range(4):
        assert await _login(unauth_client, "Alice", "999999") == 401


# A lock holds one name on one IP: the same name from another IP and another name from the same IP still log in
async def test_login_rate_limit_per_name_and_ip(unauth_client, clock):
    from main import app

    async with database.get_db() as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash, is_admin) VALUES (?, ?, 0)", ("Bob", hash_pin("246813")),
        )
        await db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app, client=("127.0.0.2", 50000)), base_url="http://test"
    ) as other_ip:
        for _ in range(4):
            assert await _login(unauth_client, "Alice", "999999") == 401
        assert await _login(unauth_client, "Alice", "999999") == 429
        assert await _login(unauth_client, "Alice", "1234") == 429

        assert await _login(other_ip, "Alice", "1234") == 200
        assert await _login(unauth_client, "Bob", "246813") == 200


# A PIN longer than 10 digits, set before the 6-10 rule, still logs in
async def test_login_takes_long_old_pin(unauth_client):
    await _add_sha256_user("Bob", "135792468024")
    assert await _login(unauth_client, "Bob", "135792468024") == 200


# A name over 100 characters or a PIN over 64 is refused before it is hashed or counted as a failure
async def test_login_refuses_overlong_input(unauth_client):
    assert await _login(unauth_client, "A" * 101, "999999") == 422
    assert await _login(unauth_client, "Alice", "9" * 65) == 422
    assert auth._login_failures == {}


async def test_endpoints_work_with_auth(unauth_client):
    """After login, token grants access to endpoints."""
    # Login first
    r = await unauth_client.post("/auth/login", json={"name": "Alice", "pin": "1234"})
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Now access endpoints
    r = await unauth_client.get("/ingredients/", headers=headers)
    assert r.status_code == 200
    assert r.json() == []

    r = await unauth_client.get("/meals/", headers=headers)
    assert r.status_code == 200

    r = await unauth_client.get("/preferences/", headers=headers)
    assert r.status_code == 200


async def _session(client) -> dict:
    """Log Alice in and return the Authorization header of the new session."""
    r = await client.post("/auth/login", json={"name": "Alice", "pin": "1234"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _socket_close_code(headers: dict) -> int | None:
    """Open the chat socket with a session's token: None when it opens, else the close code."""
    from main import app

    token = headers["Authorization"].removeprefix("Bearer ")
    try:
        with open_chat(TestClient(app), token):
            return None
    except WebSocketDisconnect as exc:
        return exc.code


# After a logout the session's token gets 401 on REST and the chat socket refuses it
async def test_logout_ends_the_session(unauth_client):
    headers = await _session(unauth_client)
    assert (await unauth_client.get("/health/auth", headers=headers)).status_code == 200
    assert _socket_close_code(headers) is None

    r = await unauth_client.post("/auth/logout", headers=headers)
    assert r.status_code == 204
    assert r.content == b""
    assert (await unauth_client.get("/health/auth", headers=headers)).status_code == 401
    assert (await unauth_client.get("/ingredients/", headers=headers)).status_code == 401
    assert _socket_close_code(headers) == 4001


# Logging out twice, with a token the server never gave or with no token at all gets 204
async def test_logout_is_harmless_when_repeated(unauth_client):
    headers = await _session(unauth_client)
    assert (await unauth_client.post("/auth/logout", headers=headers)).status_code == 204
    assert (await unauth_client.post("/auth/logout", headers=headers)).status_code == 204

    unknown = {"Authorization": "Bearer never-given"}
    assert (await unauth_client.post("/auth/logout", headers=unknown)).status_code == 204
    assert (await unauth_client.post("/auth/logout")).status_code == 204


# Logging out on one device leaves the same user's session on another device working
async def test_logout_keeps_other_sessions(unauth_client):
    phone, desktop = await _session(unauth_client), await _session(unauth_client)
    assert (await unauth_client.post("/auth/logout", headers=phone)).status_code == 204

    assert (await unauth_client.get("/health/auth", headers=phone)).status_code == 401
    assert (await unauth_client.get("/health/auth", headers=desktop)).status_code == 200
    assert _socket_close_code(desktop) is None


async def test_user_data_isolation(tmp_path, monkeypatch):
    """Two users cannot see each other's data."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash) VALUES (?, ?)",
            ("User1", hash_pin("1111")),
        )
        await db.execute(
            "INSERT INTO users (name, pin_hash) VALUES (?, ?)",
            ("User2", hash_pin("2222")),
        )
        await db.commit()

    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Login as User1
        r1 = await client.post("/auth/login", json={"name": "User1", "pin": "1111"})
        h1 = {"Authorization": f"Bearer {r1.json()['token']}"}

        # Login as User2
        r2 = await client.post("/auth/login", json={"name": "User2", "pin": "2222"})
        h2 = {"Authorization": f"Bearer {r2.json()['token']}"}

        # User1 adds an ingredient
        await client.post(
            "/ingredients/",
            json={"name": "Eggs", "quantity": "6", "unit": "pcs"},
            headers=h1,
        )

        # User1 sees it
        r = await client.get("/ingredients/", headers=h1)
        assert len(r.json()) == 1
        assert r.json()[0]["name"] == "Eggs"

        # User2 does NOT see it
        r = await client.get("/ingredients/", headers=h2)
        assert len(r.json()) == 0


# Without DEMO_USER there is no demo account, so its empty PIN doesn't log in
async def test_demo_user_not_created_by_default(unauth_client):
    r = await unauth_client.post("/auth/login", json={"name": "demo", "pin": ""})
    assert r.status_code == 401


# With DEMO_USER on, the start creates one demo account, whose empty PIN logs in and opens protected routes
async def test_demo_user_created_when_enabled(unauth_client, monkeypatch):
    monkeypatch.setattr(database, "DEMO_USER", True)
    monkeypatch.setattr(config, "DEMO_USER", True)
    await database.init_db()
    r = await unauth_client.post("/auth/login", json={"name": "demo", "pin": ""})
    assert r.status_code == 200
    assert (await unauth_client.get("/health/auth", headers={"Authorization": f"Bearer {r.json()['token']}"})).status_code == 200
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE name = 'demo'") as cur:
            assert await cur.fetchone() == (1,)


# A demo account left over from a try-out can't log in with its empty PIN once DEMO_USER is off
async def test_demo_user_locked_when_disabled(unauth_client, monkeypatch):
    monkeypatch.setattr(database, "DEMO_USER", True)
    await database.init_db()
    r = await unauth_client.post("/auth/login", json={"name": "demo", "pin": ""})
    assert r.status_code == 401


# A new demo account starts with the starter fridge, basics included, added only once
async def test_demo_user_gets_starter_fridge_once(unauth_client, monkeypatch):
    monkeypatch.setattr(database, "DEMO_USER", True)
    monkeypatch.setattr(config, "DEMO_USER", True)
    await database.init_db()
    await database.init_db()  # a restart must not add the items again
    token = (await unauth_client.post("/auth/login", json={"name": "demo", "pin": ""})).json()["token"]
    r = await unauth_client.get("/ingredients/", headers={"Authorization": f"Bearer {token}"})
    items = {i["name"]: i["group_name"] for i in r.json()}
    assert len(items) == len(r.json()) == len(DEMO_FRIDGE)
    assert items["Salt"] == "🫙 Pantry"
    assert items["Olive oil"] == "🫙 Pantry"
    assert items["Butter"] == "🐄 Animal Products"



# The signed-in check answers without the account's internal id, like every other reply
async def test_health_auth_reply_has_no_id(client):
    r = await client.get("/health/auth")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
