"""Tests for the numbered database migrations (#209)."""

import sqlite3
from contextlib import closing

import pytest

import database

LATEST = database.MIGRATIONS[-1][0]

# A database as an early multi-user version of the app created it: no user_version, columns
# and tables that came later are missing, the Fridge still has quantity and unit, group names
# are Turkish and weekly_summaries allows one review per week
OLD_SCHEMA = """
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    pin_hash    TEXT    NOT NULL,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE ingredient_inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    name        TEXT    NOT NULL,
    quantity    TEXT,
    unit        TEXT,
    added_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);
CREATE TABLE ingredient_group_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    ingredient_name TEXT    NOT NULL,
    group_name      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, ingredient_name)
);
CREATE TABLE meal_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    meal_name       TEXT    NOT NULL,
    description     TEXT,
    ingredients     TEXT,
    steps           TEXT,
    prep_time_min   INTEGER,
    nutrition_note  TEXT,
    schedule        TEXT,
    rating          INTEGER,
    logged_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE user_preferences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    key         TEXT    NOT NULL,
    value       TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, key)
);
CREATE TABLE health_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    rule_text   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE chat_sessions (
    id          TEXT    PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL REFERENCES chat_sessions(id),
    user_id     INTEGER NOT NULL REFERENCES users(id),
    role        TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
    content     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE user_profiles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id),
    age             INTEGER,
    gender          TEXT,
    height_cm       INTEGER,
    weight_kg       REAL,
    activity_level  TEXT,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE favorite_meals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    meal_name       TEXT    NOT NULL,
    description     TEXT,
    ingredients     TEXT,
    steps           TEXT,
    prep_time_min   INTEGER,
    nutrition_note  TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE suggested_meals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    session_id      TEXT    NOT NULL REFERENCES chat_sessions(id),
    meal_name       TEXT    NOT NULL,
    description     TEXT,
    ingredients     TEXT,
    steps           TEXT,
    prep_time_min   INTEGER,
    nutrition_note  TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE weekly_summaries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    week_key   TEXT NOT NULL,
    narrative  TEXT NOT NULL,
    scores     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, week_key)
);

INSERT INTO users (id, name, pin_hash) VALUES (1, 'Alice', 'x');
INSERT INTO ingredient_inventory (user_id, name, quantity, unit) VALUES
    (1, 'Honey', '1', 'jar'), (1, 'Grandma''s spice mix', '50', 'g');
INSERT INTO ingredient_group_memory (user_id, ingredient_name, group_name) VALUES
    (1, 'Pepper', '🥬 Sebze Meyve');
INSERT INTO meal_history (user_id, meal_name) VALUES (1, 'Egg sandwich');
INSERT INTO health_rules (user_id, rule_text) VALUES (1, 'Less sugar');
INSERT INTO weekly_summaries (user_id, week_key, narrative, scores) VALUES (1, '2026-W01', 'A good week', '{}');
"""


def _make(path, script: str) -> None:
    with closing(sqlite3.connect(path)) as db:
        db.executescript(script)


def _query(path, sql: str) -> list:
    with closing(sqlite3.connect(path)) as db:
        return db.execute(sql).fetchall()


def _columns(path) -> dict:
    """Each table's column names."""
    tables = [name for (name,) in _query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")]
    return {t: {row[1] for row in _query(path, f"PRAGMA table_info({t})")} for t in tables}


def _indexes(path) -> set:
    return {name for (name,) in _query(path, "SELECT name FROM sqlite_master WHERE type = 'index'")}


def _snapshot(path) -> tuple:
    """Everything a migration could change: the schema's text, its change counter and the version."""
    return (
        _query(path, "SELECT type, name, sql FROM sqlite_master ORDER BY name"),
        _query(path, "PRAGMA schema_version"),
        _query(path, "PRAGMA user_version"),
    )


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """The path init_db opens; nothing is there yet."""
    path = str(tmp_path / "app.db")
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    return path


@pytest.fixture
async def fresh_columns(tmp_path, monkeypatch):
    """The tables, columns and indexes of a brand-new database."""
    path = str(tmp_path / "fresh.db")
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    await database.init_db()
    return _columns(path), _indexes(path)


def _no_steps(monkeypatch) -> None:
    """Make every step fail, so a test shows that none ran."""
    async def boom(db):
        raise AssertionError("a migration step ran")

    monkeypatch.setattr(database, "MIGRATIONS", [(n, name, boom) for n, name, _ in database.MIGRATIONS])


# A brand-new database gets the full schema and the latest version at once, without running a step
async def test_new_database_gets_latest_version(db_path, monkeypatch):
    _no_steps(monkeypatch)
    await database.init_db()
    assert _query(db_path, "PRAGMA user_version") == [(LATEST,)]
    assert "shopping_suggestions" in _columns(db_path)


# A database from an old version of the app reaches a new one's tables, columns and indexes and keeps its rows
async def test_old_database_reaches_current_schema(fresh_columns, db_path):
    _make(db_path, OLD_SCHEMA)
    await database.init_db()

    assert (_columns(db_path), _indexes(db_path)) == fresh_columns
    assert _query(db_path, "PRAGMA user_version") == [(LATEST,)]
    # Step 1 ran too: the old pick is marked, and Honey moved from Other to the food list's group
    assert _query(db_path, "SELECT name, group_name FROM ingredient_inventory ORDER BY name") == [
        ("Grandma's spice mix", "🍽️ Other"), ("Honey", "🍯 Sweets"),
    ]
    assert _query(db_path, "SELECT ingredient_name, group_name, picked FROM ingredient_group_memory") == [
        ("Pepper", "🥬 Produce", 1),
    ]
    assert _query(db_path, "SELECT meal_name, menu_items FROM meal_history") == [("Egg sandwich", None)]
    assert _query(db_path, "SELECT rule_text, priority FROM health_rules") == [("Less sugar", "high")]


# The weekly reviews of an old database are kept when their table loses its one-per-week rule
async def test_old_weekly_reviews_are_kept(db_path):
    _make(db_path, OLD_SCHEMA)
    await database.init_db()

    with closing(sqlite3.connect(db_path)) as db:
        db.execute(
            "INSERT INTO weekly_summaries (user_id, week_key, narrative, scores) VALUES (1, '2026-W01', 'Again', '{}')"
        )
        db.commit()
    assert _query(db_path, "SELECT week_key, narrative FROM weekly_summaries ORDER BY id") == [
        ("2026-W01", "A good week"), ("2026-W01", "Again"),
    ]


# A second start changes nothing on a migrated database
async def test_running_twice_changes_nothing(db_path):
    _make(db_path, OLD_SCHEMA)
    await database.init_db()
    before = _snapshot(db_path)
    rows = _query(db_path, "SELECT * FROM ingredient_inventory ORDER BY id")

    await database.init_db()
    assert _snapshot(db_path) == before
    assert _query(db_path, "SELECT * FROM ingredient_inventory ORDER BY id") == rows


# A database at the latest version is left alone: no step runs and its schema isn't written
async def test_current_database_is_untouched(db_path, monkeypatch):
    await database.init_db()
    before = _snapshot(db_path)

    _no_steps(monkeypatch)
    await database.init_db()
    assert _snapshot(db_path) == before


# A database at version 1 runs only step 2: a missing column arrives and the one-time regroup isn't repeated
async def test_version_1_runs_later_steps_only(db_path):
    await database.init_db()
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("INSERT INTO users (id, name, pin_hash) VALUES (1, 'Alice', 'x')")
        db.execute("INSERT INTO ingredient_inventory (user_id, name) VALUES (1, 'Honey')")
        db.execute("ALTER TABLE user_profiles DROP COLUMN country")
        db.execute("PRAGMA user_version = 1")
        db.commit()

    await database.init_db()
    assert "country" in _columns(db_path)["user_profiles"]
    assert _query(db_path, "SELECT group_name FROM ingredient_inventory") == [("🍽️ Other",)]
    assert _query(db_path, "PRAGMA user_version") == [(LATEST,)]


# A database at version 0 that already has every column gets the version number and no schema change
async def test_version_0_with_every_column(db_path):
    await database.init_db()
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("PRAGMA user_version = 0")
    schema, _, _ = _snapshot(db_path)

    await database.init_db()
    assert _snapshot(db_path)[0] == schema
    assert _query(db_path, "PRAGMA user_version") == [(LATEST,)]


# A step that fails stops the start with its message, and its changes and version number are rolled back
async def test_failing_step_raises(db_path, monkeypatch):
    await database.init_db()

    async def broken(db):
        await db.execute("CREATE TABLE half_done (id INTEGER)")
        await db.execute("INSERT INTO users (name, pin_hash) VALUES ('Ghost', 'x')")
        raise ValueError("no such luck")

    monkeypatch.setattr(database, "MIGRATIONS", [*database.MIGRATIONS, (LATEST + 1, "a broken step", broken)])
    with pytest.raises(RuntimeError, match=rf"step {LATEST + 1} \(a broken step\): no such luck"):
        await database.init_db()

    assert _query(db_path, "PRAGMA user_version") == [(LATEST,)]
    assert "half_done" not in _columns(db_path)
    assert _query(db_path, "SELECT name FROM users") == []


# An ALTER that fails on an old database is no longer swallowed: the start stops and the database stays as it was
async def test_broken_old_database_stops_start(db_path):
    # health_rules is a view here, so its missing column can't be added
    _make(db_path, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT); CREATE VIEW health_rules AS SELECT 1 AS id;")
    before = _snapshot(db_path)

    with pytest.raises(RuntimeError, match="Database migration failed at step 1"):
        await database.init_db()
    assert _snapshot(db_path) == before


# A later step may add a column that step 2 already created with its table
async def test_add_column_skips_existing(db_path):
    import aiosqlite

    await database.init_db()
    async with aiosqlite.connect(db_path) as db:
        await database._add_column(db, "users", "last_expiry_check", "TEXT")
        await database._add_column(db, "users", "nickname", "TEXT")
        assert {"last_expiry_check", "nickname"} <= await database._columns(db, "users")


def _migration_backups(db_path) -> list:
    """The backups taken before pending steps, oldest first."""
    from pathlib import Path

    return sorted(Path(db_path).parent.glob("app_before_migration_*.db"))


# A pending step on a database with data leaves a backup of it as it was: old version, old schema, its rows
async def test_pending_migration_leaves_a_backup(db_path, capsys):
    _make(db_path, OLD_SCHEMA)
    await database.init_db()

    (backup,) = _migration_backups(db_path)
    assert f"Database backed up to {backup} before migrating from schema version 0" in capsys.readouterr().out
    assert backup.name.endswith("_v0.db")
    assert _query(backup, "PRAGMA user_version") == [(0,)]
    assert _query(backup, "PRAGMA integrity_check") == [("ok",)]
    assert "quantity" in _columns(backup)["ingredient_inventory"]
    assert _query(backup, "SELECT meal_name FROM meal_history") == [("Egg sandwich",)]


# A brand-new database and one already at the latest version get no backup
async def test_no_backup_without_pending_steps(db_path):
    await database.init_db()
    await database.init_db()
    assert _migration_backups(db_path) == []


# A step that fails still leaves the backup taken before it
async def test_failing_step_keeps_its_backup(db_path, monkeypatch):
    await database.init_db()

    async def broken(db):
        raise ValueError("no such luck")

    monkeypatch.setattr(database, "MIGRATIONS", [*database.MIGRATIONS, (LATEST + 1, "a broken step", broken)])
    with pytest.raises(RuntimeError):
        await database.init_db()
    (backup,) = _migration_backups(db_path)
    assert _query(backup, "PRAGMA user_version") == [(LATEST,)]


# Only the newest few backups are kept
async def test_old_migration_backups_are_removed(db_path):
    from pathlib import Path

    _make(db_path, OLD_SCHEMA)
    old = [Path(db_path).with_name(f"app_before_migration_2020010{n}_000000_v0.db") for n in range(1, 5)]
    for path in old:
        path.write_bytes(b"")
    await database.init_db()

    kept = _migration_backups(db_path)
    assert len(kept) == database.MIGRATION_BACKUPS_KEPT
    assert kept[:-1] == old[-(database.MIGRATION_BACKUPS_KEPT - 1):]
    assert kept[-1] not in old


# A backup that fails its integrity check stops the start before any step runs, and isn't kept
async def test_bad_backup_stops_migration(db_path, monkeypatch):
    _make(db_path, OLD_SCHEMA)
    before = _snapshot(db_path)

    monkeypatch.setattr(database, "_BACKUP_CHECK", "SELECT 'row 3 missing from index'")
    with pytest.raises(RuntimeError, match="integrity check"):
        await database.init_db()
    assert _snapshot(db_path) == before
    assert _migration_backups(db_path) == []


# A relative DATABASE_PATH counts from the backend folder whatever folder the program starts in; a full path stays
def test_relative_database_path_is_in_backend_folder(tmp_path, monkeypatch):
    from pathlib import Path

    import config

    backend = Path(config.__file__).resolve().parent
    monkeypatch.chdir(tmp_path)
    assert Path(config.resolve_database_path("./breakFAST.db")) == backend / "breakFAST.db"
    assert Path(config.resolve_database_path("data/app.db")) == backend / "data" / "app.db"
    assert Path(config.resolve_database_path(str(tmp_path / "x.db"))) == tmp_path / "x.db"


# The configured database path is the same full path when the program is started from two different folders
def test_database_path_is_the_same_from_any_folder(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    backend = Path(database.__file__).resolve().parent
    env = {**os.environ, "PYTHONPATH": str(backend), "DATABASE_PATH": "./breakFAST.db"}
    paths = [
        subprocess.run(
            [sys.executable, "-c", "import config; print(config.DATABASE_PATH)"],
            cwd=folder, env=env, capture_output=True, text=True, check=True,
        ).stdout.strip()
        for folder in (tmp_path, backend)
    ]
    assert paths[0] == paths[1]
    assert Path(paths[0]) == backend / "breakFAST.db"


# The server's start prints the database's full path and schema version
async def test_start_prints_database_path_and_version(db_path, capsys):
    from main import app, lifespan

    async with lifespan(app):
        pass
    assert f"Database: {db_path} (schema version {LATEST})" in capsys.readouterr().out


# A database at version 2 loses its rows without a parent (chained ones too) and rows under another user's parent, and keeps the rest
async def test_orphan_rows_are_cleaned(db_path):
    await database.init_db()
    with closing(sqlite3.connect(db_path)) as db:
        db.executescript("""
            INSERT INTO users (id, name, pin_hash) VALUES (1, 'Alice', 'x'), (2, 'Bob', 'x');
            INSERT INTO chat_sessions (id, user_id) VALUES ('alice-chat', 1), ('gone-user-chat', 99);
            INSERT INTO chat_messages (session_id, user_id, role, content) VALUES
                ('alice-chat', 1, 'user', 'Kept'),
                ('alice-chat', 2, 'user', 'Bob in Alice''s chat'),
                ('gone-chat', 1, 'user', 'No chat'),
                ('gone-user-chat', 99, 'user', 'No user');
            INSERT INTO suggested_meals (user_id, session_id, meal_name) VALUES (1, 'alice-chat', 'Kept'), (1, 'gone-chat', 'No chat');
            INSERT INTO user_supplements (id, user_id, name, frequency) VALUES (1, 1, 'Iron', 'sometimes');
            INSERT INTO supplement_daily_log (user_id, supplement_id, date, taken) VALUES
                (1, 1, '2026-11-01', 1), (1, 7, '2026-11-01', 1), (2, 1, '2026-11-01', 1);
            INSERT INTO shopping_list (user_id, item_name) VALUES (1, 'Milk'), (99, 'Ghost milk');
            PRAGMA user_version = 2;
        """)

    await database.init_db()
    assert _query(db_path, "PRAGMA foreign_key_check") == []
    assert _query(db_path, "SELECT id FROM chat_sessions") == [("alice-chat",)]
    assert _query(db_path, "SELECT content FROM chat_messages") == [("Kept",)]
    assert _query(db_path, "SELECT meal_name FROM suggested_meals") == [("Kept",)]
    assert _query(db_path, "SELECT user_id, supplement_id FROM supplement_daily_log") == [(1, 1)]
    assert _query(db_path, "SELECT item_name FROM shopping_list") == [("Milk",)]
    assert _query(db_path, "PRAGMA user_version") == [(LATEST,)]


# The app's connections enforce foreign keys, so a row can't point to a chat that doesn't exist
async def test_app_connections_enforce_foreign_keys(db_path):
    await database.init_db()
    async with database.get_db() as db:
        await db.execute("INSERT INTO users (id, name, pin_hash) VALUES (1, 'Alice', 'x')")
        with pytest.raises(sqlite3.IntegrityError):
            await db.execute(
                "INSERT INTO chat_messages (session_id, user_id, role, content) VALUES ('made-up', 1, 'user', 'Hi')"
            )


# Step 4 (#244) gives a database at version 3 the favorites' icon column, and its favorites keep their rows
async def test_version_3_gets_favorite_emoji(db_path):
    await database.init_db()
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("INSERT INTO users (id, name, pin_hash) VALUES (1, 'Alice', 'x')")
        db.execute("ALTER TABLE favorite_meals DROP COLUMN emoji")
        db.execute("INSERT INTO favorite_meals (user_id, meal_name) VALUES (1, 'Plate')")
        db.execute("PRAGMA user_version = 3")
        db.commit()

    await database.init_db()
    assert "emoji" in _columns(db_path)["favorite_meals"]
    assert _query(db_path, "SELECT meal_name, emoji FROM favorite_meals") == [("Plate", None)]
    assert _query(db_path, "PRAGMA user_version") == [(LATEST,)]


# A demo account created at the start with DEMO_USER on is a normal user, not an admin
async def test_new_demo_user_is_not_admin(db_path, monkeypatch):
    monkeypatch.setattr(database, "DEMO_USER", True)
    await database.init_db()
    assert _query(db_path, "SELECT is_admin FROM users WHERE name = 'demo'") == [(0,)]


# A demo account left as an admin by an earlier version loses the flag at the next start
async def test_existing_demo_user_loses_admin(db_path, monkeypatch):
    await database.init_db()
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("INSERT INTO users (name, pin_hash, is_admin) VALUES ('demo', 'x', 1), ('Alice', 'x', 1)")
        db.commit()

    monkeypatch.setattr(database, "DEMO_USER", True)
    await database.init_db()
    assert _query(db_path, "SELECT name, is_admin FROM users ORDER BY name") == [("Alice", 1), ("demo", 0)]
