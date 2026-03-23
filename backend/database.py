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
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    pin_hash    TEXT    NOT NULL,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingredient_inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    name        TEXT    NOT NULL,
    quantity    TEXT,
    unit        TEXT,
    added_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS meal_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    meal_name       TEXT    NOT NULL,
    description     TEXT,
    ingredients     TEXT,           -- JSON list of strings
    steps           TEXT,           -- JSON list of strings
    prep_time_min   INTEGER,
    nutrition_note  TEXT,
    schedule        TEXT,           -- JSON (kitchen scheduler output)
    rating          INTEGER,        -- 1 = thumbs down, 5 = thumbs up, NULL = no feedback
    cached_nutrition TEXT,           -- JSON (analyst output cache, NULL = not yet analyzed)
    logged_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    key         TEXT    NOT NULL,
    value       TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, key)
);

CREATE TABLE IF NOT EXISTS user_habits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    description TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'stated',  -- 'stated' or 'inferred'
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS health_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    rule_text   TEXT    NOT NULL,
    priority    TEXT    NOT NULL DEFAULT 'high' CHECK (priority IN ('low', 'high', 'critical')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id          TEXT    PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL REFERENCES chat_sessions(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    role        TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
    content     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS product_ratings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    product_name TEXT   NOT NULL,
    rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 10) DEFAULT 10,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, product_name)
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id),
    age             INTEGER,
    gender          TEXT,
    height_cm       INTEGER,
    weight_kg       REAL,
    activity_level  TEXT,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_supplements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    name        TEXT    NOT NULL,
    contents    TEXT    NOT NULL DEFAULT '',
    frequency   TEXT    NOT NULL DEFAULT 'daily' CHECK(frequency IN ('daily', 'sometimes')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS supplement_daily_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    supplement_id   INTEGER NOT NULL REFERENCES user_supplements(id),
    date            TEXT    NOT NULL,
    taken           INTEGER NOT NULL DEFAULT 1,
    UNIQUE(user_id, supplement_id, date)
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
    from auth import hash_pin

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript(_SCHEMA)

        # Ensure a "demo" user always exists (for quick dev/demo access)
        await db.execute(
            """
            INSERT OR IGNORE INTO users (name, pin_hash, is_admin)
            VALUES (?, ?, 1)
            """,
            ("demo", hash_pin("")),
        )

        # Migrate: add priority column to health_rules if missing
        try:
            await db.execute(
                "ALTER TABLE health_rules ADD COLUMN priority TEXT NOT NULL DEFAULT 'high' "
                "CHECK (priority IN ('low', 'high', 'critical'))"
            )
        except Exception:
            pass  # Column already exists

        # Migrate: add cached_nutrition column to meal_history if missing
        try:
            await db.execute(
                "ALTER TABLE meal_history ADD COLUMN cached_nutrition TEXT"
            )
        except Exception:
            pass  # Column already exists

        # Clean up chat sessions older than 48 hours
        await db.execute(
            """
            DELETE FROM chat_messages WHERE session_id IN (
                SELECT id FROM chat_sessions
                WHERE updated_at < datetime('now', '-48 hours')
            )
            """
        )
        await db.execute(
            "DELETE FROM chat_sessions WHERE updated_at < datetime('now', '-48 hours')"
        )

        await db.commit()
