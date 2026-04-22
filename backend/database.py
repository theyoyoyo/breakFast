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
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    name                TEXT    NOT NULL,
    expiry_date         TEXT,
    expiry_acknowledged INTEGER NOT NULL DEFAULT 0,
    group_name          TEXT    NOT NULL DEFAULT '🍽️ Diğer',
    added_at            TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS ingredient_group_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    ingredient_name TEXT    NOT NULL,
    group_name      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, ingredient_name)
);

CREATE TABLE IF NOT EXISTS favorite_ingredients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    ingredient_name TEXT    NOT NULL,
    added_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, ingredient_name)
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
    menu_items      TEXT,           -- JSON menu array (new multi-item format)
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

CREATE TABLE IF NOT EXISTS favorite_meals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    meal_name       TEXT    NOT NULL,
    description     TEXT,
    ingredients     TEXT,           -- JSON list
    steps           TEXT,           -- JSON list
    prep_time_min   INTEGER,
    nutrition_note  TEXT,
    menu_items      TEXT,           -- JSON menu array (new multi-item format)
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS suggested_meals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    session_id      TEXT    NOT NULL REFERENCES chat_sessions(id),
    meal_name       TEXT    NOT NULL,
    description     TEXT,
    ingredients     TEXT,           -- JSON list
    steps           TEXT,           -- JSON list
    prep_time_min   INTEGER,
    nutrition_note  TEXT,
    menu_items      TEXT,           -- JSON menu array (new multi-item format)
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS shopping_list (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    item_name   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, item_name)
);

CREATE TABLE IF NOT EXISTS user_kitchen_appliances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    appliance_key   TEXT    NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, appliance_key)
);

CREATE TABLE IF NOT EXISTS weekly_summaries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    week_key   TEXT NOT NULL,
    narrative  TEXT NOT NULL,
    scores     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indices on frequently-filtered foreign key columns
CREATE INDEX IF NOT EXISTS idx_shopping_list_user ON shopping_list(user_id);
CREATE INDEX IF NOT EXISTS idx_user_kitchen_appliances_user ON user_kitchen_appliances(user_id);
CREATE INDEX IF NOT EXISTS idx_ingredient_inventory_user ON ingredient_inventory(user_id);
CREATE INDEX IF NOT EXISTS idx_ingredient_group_memory_user ON ingredient_group_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_meal_history_user ON meal_history(user_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_habits_user ON user_habits(user_id);
CREATE INDEX IF NOT EXISTS idx_health_rules_user ON health_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_product_ratings_user ON product_ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_supplements_user ON user_supplements(user_id);
CREATE INDEX IF NOT EXISTS idx_favorite_meals_user ON favorite_meals(user_id);
CREATE INDEX IF NOT EXISTS idx_suggested_meals_session ON suggested_meals(session_id);
CREATE INDEX IF NOT EXISTS idx_suggested_meals_user ON suggested_meals(user_id);
CREATE INDEX IF NOT EXISTS idx_weekly_summaries_user_week ON weekly_summaries(user_id, week_key);
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

        # Migrate: drop quantity/unit columns from ingredient_inventory
        async with db.execute("PRAGMA table_info(ingredient_inventory)") as cur:
            cols = {r[1] for r in await cur.fetchall()}
        if "quantity" in cols:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS _ingredient_inventory_new (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL REFERENCES users(id),
                    name        TEXT    NOT NULL,
                    added_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(user_id, name)
                )
            """)
            await db.execute("""
                INSERT OR IGNORE INTO _ingredient_inventory_new (id, user_id, name, added_at, updated_at)
                SELECT id, user_id, name, added_at, updated_at FROM ingredient_inventory
            """)
            await db.execute("DROP TABLE ingredient_inventory")
            await db.execute("ALTER TABLE _ingredient_inventory_new RENAME TO ingredient_inventory")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_ingredient_inventory_user ON ingredient_inventory(user_id)")

        # Migrate: add expiry_date column to ingredient_inventory if missing
        try:
            await db.execute(
                "ALTER TABLE ingredient_inventory ADD COLUMN expiry_date TEXT"
            )
        except Exception:
            pass  # Column already exists

        # Migrate: add expiry_acknowledged column to ingredient_inventory if missing
        try:
            await db.execute(
                "ALTER TABLE ingredient_inventory ADD COLUMN expiry_acknowledged INTEGER NOT NULL DEFAULT 0"
            )
        except Exception:
            pass  # Column already exists

        # Migrate: add group_name column to ingredient_inventory if missing
        try:
            await db.execute(
                "ALTER TABLE ingredient_inventory ADD COLUMN group_name TEXT NOT NULL DEFAULT '🍽️ Diğer'"
            )
        except Exception:
            pass  # Column already exists

        # Migrate: rename old group names to new ones
        _GROUP_RENAMES = {
            "🧀 Şarküteri": "🐄 Hayvansal",
            "🥬 Sebze/Meyve": "🥬 Sebze Meyve",
            "🌿 Baharatlar": "🧂 Baharatlar",
            "📦 Diğer": "🍽️ Diğer",
        }
        for old, new in _GROUP_RENAMES.items():
            await db.execute(
                "UPDATE ingredient_inventory SET group_name = ? WHERE group_name = ?",
                (new, old),
            )
            await db.execute(
                "UPDATE ingredient_group_memory SET group_name = ? WHERE group_name = ?",
                (new, old),
            )

        # Migrate: add last_expiry_check column to users if missing
        try:
            await db.execute(
                "ALTER TABLE users ADD COLUMN last_expiry_check TEXT"
            )
        except Exception:
            pass  # Column already exists

        # Migrate: add menu_items column to meal_history if missing
        try:
            await db.execute(
                "ALTER TABLE meal_history ADD COLUMN menu_items TEXT"
            )
        except Exception:
            pass  # Column already exists

        # Migrate: add menu_items column to suggested_meals if missing
        try:
            await db.execute(
                "ALTER TABLE suggested_meals ADD COLUMN menu_items TEXT"
            )
        except Exception:
            pass  # Column already exists

        # Migrate: add menu_items column to favorite_meals if missing
        try:
            await db.execute(
                "ALTER TABLE favorite_meals ADD COLUMN menu_items TEXT"
            )
        except Exception:
            pass  # Column already exists

        # Migrate: recreate weekly_summaries without UNIQUE constraint (allow multiple per week)
        async with db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='weekly_summaries'"
        ) as cur:
            ws_row = await cur.fetchone()
        if ws_row and "UNIQUE" in (ws_row[0] or ""):
            await db.execute("DROP TABLE IF EXISTS weekly_summaries")
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS weekly_summaries (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL REFERENCES users(id),
                    week_key   TEXT NOT NULL,
                    narrative  TEXT NOT NULL,
                    scores     TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_weekly_summaries_user_week
                    ON weekly_summaries(user_id, week_key);
            """)

        # Clean up chat sessions older than 8 days
        await db.execute(
            """
            DELETE FROM suggested_meals WHERE session_id IN (
                SELECT id FROM chat_sessions
                WHERE updated_at < datetime('now', '-8 days')
            )
            """
        )
        await db.execute(
            """
            DELETE FROM chat_messages WHERE session_id IN (
                SELECT id FROM chat_sessions
                WHERE updated_at < datetime('now', '-8 days')
            )
            """
        )
        await db.execute(
            "DELETE FROM chat_sessions WHERE updated_at < datetime('now', '-8 days')"
        )

        await db.commit()
