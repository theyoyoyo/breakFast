"""
Shared test fixtures for the break FAST backend.

Each test function gets a fresh SQLite database via the `client` fixture,
which patches database.DATABASE_PATH before creating the FastAPI test client.
A test user is created and all requests include the auth token.
"""

import sys
from pathlib import Path

# Make backend/ importable without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


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
