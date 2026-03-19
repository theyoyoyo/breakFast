"""
Database connection and schema initialization.

Usage in routers:
    async with get_db() as db:
        await db.execute(...)
        await db.commit()
"""

import aiosqlite
from contextlib import asynccontextmanager

from config import DATABASE_PATH


# ---------------------------------------------------------------------------
# Schema — all tables in one executescript call
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingredient_inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    quantity    TEXT,
    unit        TEXT,
    added_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meal_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_name       TEXT    NOT NULL,
    description     TEXT,
    ingredients     TEXT,           -- JSON list of strings
    steps           TEXT,           -- JSON list of strings
    prep_time_min   INTEGER,
    nutrition_note  TEXT,
    schedule        TEXT,           -- JSON (kitchen scheduler output)
    rating          INTEGER,        -- 1 = thumbs down, 5 = thumbs up, NULL = no feedback
    logged_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT    NOT NULL UNIQUE,
    value       TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_habits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'stated',  -- 'stated' or 'inferred'
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_db():
    """Async context manager that yields an open, row-factory-enabled connection."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    """Create all tables if they don't exist. Called once at startup."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()
