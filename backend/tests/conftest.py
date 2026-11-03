"""
Shared test fixtures for the break FAST backend.

Each test function gets a fresh SQLite database via the `client` fixture,
which patches database.DATABASE_PATH before creating the FastAPI test client.
A test user is created and all requests include the auth token.
PINs are hashed at a tiny scrypt cost unless a test is marked real_scrypt.
"""

import sys
from pathlib import Path

# Make backend/ importable without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest.fixture(autouse=True)
def fast_pin_hashing(request, monkeypatch):
    """Hash PINs at a tiny scrypt cost, since the real one takes a quarter second per hash."""
    if request.node.get_closest_marker("real_scrypt"):
        return
    import auth

    monkeypatch.setattr(auth, "SCRYPT_N", 2**4)
    monkeypatch.setattr(auth, "SCRYPT_P", 1)


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    """AsyncClient pointed at the FastAPI app with an isolated per-test database."""
    db_path = str(tmp_path / "test.db")

    import database

    monkeypatch.setattr(database, "DATABASE_PATH", db_path)

    # Initialize schema on the temp file (idempotent; uses IF NOT EXISTS)
    await database.init_db()

    # Create a test user
    from auth import hash_pin, create_token

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash, is_admin) VALUES (?, ?, ?)",
            ("testuser", hash_pin("1234"), 1),
        )
        await db.commit()
        async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
            row = await cur.fetchone()
            user_id = row[0]

    token = create_token(user_id)

    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db(client, tmp_path):
    """Direct database connection for tests that need to manipulate data beyond the API."""
    import database

    async with aiosqlite.connect(database.DATABASE_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn
