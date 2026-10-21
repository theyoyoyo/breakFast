"""
Tests for auth — login, token management, endpoint protection.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

import database
from auth import hash_pin


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


async def test_login_success(unauth_client):
    r = await unauth_client.post("/auth/login", json={"name": "Alice", "pin": "1234"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert data["user"]["name"] == "Alice"
    assert data["user"]["is_admin"] == 1


async def test_login_wrong_pin(unauth_client):
    r = await unauth_client.post("/auth/login", json={"name": "Alice", "pin": "9999"})
    assert r.status_code == 401


async def test_login_unknown_user(unauth_client):
    r = await unauth_client.post("/auth/login", json={"name": "Nobody", "pin": "1234"})
    assert r.status_code == 401


async def test_endpoints_require_auth(unauth_client):
    """All data endpoints should return 401/422 without auth token."""
    r = await unauth_client.get("/ingredients/")
    assert r.status_code == 422  # missing Authorization header

    r = await unauth_client.get("/meals/")
    assert r.status_code == 422

    r = await unauth_client.get("/preferences/")
    assert r.status_code == 422


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
            json={"name": "eggs", "quantity": "6", "unit": "pcs"},
            headers=h1,
        )

        # User1 sees it
        r = await client.get("/ingredients/", headers=h1)
        assert len(r.json()) == 1
        assert r.json()[0]["name"] == "eggs"

        # User2 does NOT see it
        r = await client.get("/ingredients/", headers=h2)
        assert len(r.json()) == 0


async def test_demo_user_not_created_by_default(unauth_client):
    r = await unauth_client.post("/auth/login", json={"name": "demo", "pin": ""})
    assert r.status_code == 401


async def test_demo_user_created_when_enabled(unauth_client, monkeypatch):
    monkeypatch.setattr(database, "DEMO_USER", True)
    await database.init_db()
    r = await unauth_client.post("/auth/login", json={"name": "demo", "pin": ""})
    assert r.status_code == 200

