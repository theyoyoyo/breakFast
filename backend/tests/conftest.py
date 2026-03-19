"""
Shared test fixtures for the break FAST backend.

Each test function gets a fresh SQLite database via the `client` fixture,
which patches database.DATABASE_PATH before creating the FastAPI test client.
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

    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
