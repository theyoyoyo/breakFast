"""
Database connection and schema initialization.

Usage in routers:
    async with get_db() as db:
        await db.execute(...)
        await db.commit()
"""

import logging
import sqlite3

import aiosqlite
from contextlib import asynccontextmanager

from config import DATABASE_PATH, DEMO_USER
from models.ingredient import DEMO_FRIDGE
from services.ingredient_groups import regroup_once

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema — what a brand-new database gets (older ones reach it through MIGRATIONS)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    pin_hash    TEXT    NOT NULL,
    -- Reserved for admin-only features: no endpoint checks it today.
    is_admin    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    last_expiry_check TEXT
);

CREATE TABLE IF NOT EXISTS ingredient_inventory (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    name                TEXT    NOT NULL,
    expiry_date         TEXT,
    expiry_acknowledged INTEGER NOT NULL DEFAULT 0,
    group_name          TEXT    NOT NULL DEFAULT '🍽️ Other',
    added_at            TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS ingredient_group_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    ingredient_name TEXT    NOT NULL,
    group_name      TEXT    NOT NULL,
    picked          INTEGER NOT NULL DEFAULT 0,  -- 1: the user chose this group; 0: code did
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
    selected_message_id INTEGER,    -- the meal card selected for today, the same on every device
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL REFERENCES chat_sessions(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    role        TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
    content     TEXT    NOT NULL,
    ate_draft   TEXT,           -- JSON meal: the card's "Today I ate" version, saved with Save
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
    country         TEXT,
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

-- Fridge tab's shopping suggestions, the same on every device. A row with removed_at
-- was removed with ×: it is left out of new suggestions for 7 days.
CREATE TABLE IF NOT EXISTS shopping_suggestions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    name        TEXT    NOT NULL,
    reason      TEXT    NOT NULL DEFAULT '',
    checked     INTEGER NOT NULL DEFAULT 1,
    position    INTEGER NOT NULL DEFAULT 0,
    removed_at  TEXT,
    UNIQUE(user_id, name)
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
CREATE INDEX IF NOT EXISTS idx_shopping_suggestions_user ON shopping_suggestions(user_id);
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


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------
# Numbered steps, run in order, each in one transaction together with its
# PRAGMA user_version, so a step is applied whole or not at all. A step that fails
# stops the start with its message. A brand-new database gets _SCHEMA and the latest
# number at once and runs no step.
#
# To change the schema: update _SCHEMA and add a step at the end of MIGRATIONS.
# Never edit or renumber a step that has shipped. Add columns with _add_column:
# step 2 creates missing tables from today's _SCHEMA, so on an old database a later
# step can find its column already there.

# Group names from before the English ones
_GROUP_RENAMES = {
    # Historical renames (pre-English migration)
    "🧀 Şarküteri": "🐄 Animal Products",
    "🥬 Sebze/Meyve": "🥬 Produce",
    "🌿 Baharatlar": "🧂 Spices",
    "📦 Diğer": "🍽️ Other",
    # Turkish → English
    "🐄 Hayvansal": "🐄 Animal Products",
    "🥬 Sebze Meyve": "🥬 Produce",
    "🍞 Ekmekler": "🍞 Breads",
    "🍯 Tatlılar": "🍯 Sweets",
    "🫒 Kahvaltılık": "🫒 Breakfast Staples",
    "🥜 Kuruyemişler": "🥜 Nuts & Seeds",
    "🌱 Bitkisel": "🌱 Plant-Based",
    "☕ İçecekler": "☕ Beverages",
    "🧂 Baharatlar": "🧂 Spices",
    "🍽️ Diğer": "🍽️ Other",
}

# Columns added after their table, in the order they arrived: (table, column, definition)
_LEGACY_COLUMNS = [
    ("health_rules", "priority",
     "TEXT NOT NULL DEFAULT 'high' CHECK (priority IN ('low', 'high', 'critical'))"),
    ("meal_history", "cached_nutrition", "TEXT"),
    ("ingredient_inventory", "expiry_date", "TEXT"),
    ("ingredient_inventory", "expiry_acknowledged", "INTEGER NOT NULL DEFAULT 0"),
    ("ingredient_inventory", "group_name", "TEXT NOT NULL DEFAULT '🍽️ Other'"),
    ("ingredient_group_memory", "picked", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "last_expiry_check", "TEXT"),
    ("meal_history", "menu_items", "TEXT"),
    ("suggested_meals", "menu_items", "TEXT"),
    ("favorite_meals", "menu_items", "TEXT"),
    ("user_profiles", "country", "TEXT"),
    ("chat_sessions", "selected_message_id", "INTEGER"),
    ("chat_messages", "ate_draft", "TEXT"),
]


async def _columns(db, table: str) -> set[str]:
    """The names of a table's columns (empty when the table doesn't exist)."""
    async with db.execute(f"PRAGMA table_info({table})") as cur:
        return {row[1] for row in await cur.fetchall()}


async def _add_column(db, table: str, column: str, definition: str) -> None:
    """Add a column unless the table already has it."""
    if column not in await _columns(db, table):
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def _run_script(db, script: str) -> None:
    """Run a script one statement at a time, inside the open transaction.

    executescript would commit first, which would split a migration step in two.
    """
    statement = ""
    for line in script.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            await db.execute(statement)
            statement = ""


async def _legacy_schema(db) -> None:
    """Bring a database from before the numbered steps up to the schema of step 2.

    These changes used to run on every start, each ALTER in a try that ignored any
    error. Every change here looks first, so it runs cleanly on a database that has
    some, all or none of them.
    """
    # Tables that arrived later came through CREATE TABLE IF NOT EXISTS
    await _run_script(db, _SCHEMA)

    # ingredient_inventory once had quantity and unit columns
    if "quantity" in await _columns(db, "ingredient_inventory"):
        await db.execute("""
            CREATE TABLE _ingredient_inventory_new (
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
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_ingredient_inventory_user ON ingredient_inventory(user_id)"
        )

    for table, column, definition in _LEGACY_COLUMNS:
        await _add_column(db, table, column, definition)

    for old, new in _GROUP_RENAMES.items():
        for table in ("ingredient_inventory", "ingredient_group_memory"):
            await db.execute(f"UPDATE {table} SET group_name = ? WHERE group_name = ?", (new, old))

    # weekly_summaries once allowed one review per week: rebuilt without the UNIQUE, rows kept
    async with db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='weekly_summaries'"
    ) as cur:
        (table_sql,) = await cur.fetchone()
    if "UNIQUE" in (table_sql or ""):
        await db.execute("ALTER TABLE weekly_summaries RENAME TO _weekly_summaries_old")
        await db.execute("""
            CREATE TABLE weekly_summaries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                week_key   TEXT NOT NULL,
                narrative  TEXT NOT NULL,
                scores     TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            INSERT INTO weekly_summaries (id, user_id, week_key, narrative, scores, created_at)
            SELECT id, user_id, week_key, narrative, scores, created_at FROM _weekly_summaries_old
        """)
        await db.execute("DROP TABLE _weekly_summaries_old")
        await db.execute(
            "CREATE INDEX idx_weekly_summaries_user_week ON weekly_summaries(user_id, week_key)"
        )


async def _regroup(db) -> None:
    """Step 1 (#162): old group memory rows become picks unless they say Other, and Fridge
    items in Other get the built-in food list's group. Once only: a later Other pick stays.

    This step is older than the numbered list and the columns it reads were added outside
    it, so a database that never ran it is first brought up to date.
    """
    await _legacy_schema(db)
    await regroup_once(db)


# (number, what it does, step). The number is the PRAGMA user_version once the step has run.
MIGRATIONS = [
    (1, "group picks and the built-in food list", _regroup),
    (2, "tables and columns added before the numbered steps", _legacy_schema),
]


async def _user_version(db) -> int:
    async with db.execute("PRAGMA user_version") as cur:
        (version,) = await cur.fetchone()
    return version


async def _is_empty(db) -> bool:
    """True for a brand-new database: it has no tables yet."""
    async with db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ) as cur:
        (tables,) = await cur.fetchone()
    return tables == 0


async def migrate(db) -> None:
    """Bring the database to the latest schema. One that is already there is not written to."""
    latest = MIGRATIONS[-1][0]
    while True:
        version = await _user_version(db)
        if version > latest:
            logger.warning(
                "The database is at schema version %s and this code knows up to %s: "
                "a newer version of the app has opened it.", version, latest,
            )
        if version >= latest:
            return

        # The write lock comes first and the version is read again under it, so two
        # processes that start together (the server and manage.py) never run a step twice.
        await db.execute("BEGIN IMMEDIATE")
        target, name = latest, "new database"
        try:
            version = await _user_version(db)
            if await _is_empty(db):
                await _run_script(db, _SCHEMA)
            else:
                pending = [m for m in MIGRATIONS if m[0] > version]
                if not pending:
                    await db.rollback()
                    return
                target, name, step = pending[0]
                await step(db)
            await db.execute(f"PRAGMA user_version = {int(target)}")
            await db.commit()
        except Exception as exc:
            await db.rollback()
            raise RuntimeError(
                f"Database migration failed at step {target} ({name}): {exc}. "
                f"The step was rolled back and the database is still at version {version}."
            ) from exc


async def init_db() -> None:
    """Create or migrate the schema, then do the start-up housekeeping. Called once at startup."""
    from auth import hash_pin

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await migrate(db)

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

        # Opt-in "demo" user with an empty PIN (DEMO_USER=true) for local try-outs.
        # Runs after the migrations; a newly created demo account gets a starter fridge.
        if DEMO_USER:
            cur = await db.execute(
                """
                INSERT OR IGNORE INTO users (name, pin_hash, is_admin)
                VALUES (?, ?, 1)
                """,
                ("demo", hash_pin("")),
            )
            if cur.rowcount:
                await db.executemany(
                    "INSERT INTO ingredient_inventory (user_id, name, group_name) VALUES (?, ?, ?)",
                    [(cur.lastrowid, name, group) for name, group in DEMO_FRIDGE],
                )

        await db.commit()
