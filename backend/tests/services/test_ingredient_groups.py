"""Tests for the built-in food list and the one-time regroup (#162)."""

import database
from models.ingredient import DEFAULT_GROUP, DEMO_FRIDGE, INGREDIENT_GROUPS
from services.fridge import name_tokens, same_tokens
from services.ingredient_groups import CATALOG, catalog_group


def _names():
    """Every name on the list as (name, food number, language)."""
    foods = [food for group in CATALOG.values() for food in group]
    return [(name, i, lang) for i, food in enumerate(foods) for lang in ("en", "tr") for name in food[lang]]


# Every group on the list is one of the fixed groups, and Other isn't listed (it's the fallback)
def test_groups_are_fixed_groups():
    assert set(CATALOG) <= set(INGREDIENT_GROUPS)
    assert DEFAULT_GROUP not in CATALOG


# Every food has an English and a Turkish name
def test_every_food_has_both_languages():
    for group, foods in CATALOG.items():
        for food in foods:
            assert set(food) == {"en", "tr"}, food
            assert food["en"] and food["tr"], food
            assert all(isinstance(n, str) and n.strip() == n and n for n in food["en"] + food["tr"]), food


# No name belongs to two foods, so a name never maps to two groups, and no food repeats a name in one language
def test_no_name_twice():
    names = [(name, name_tokens(name), food, lang) for name, food, lang in _names()]
    clashes = [
        (a, b) for i, (a, ta, food_a, lang_a) in enumerate(names) for b, tb, food_b, lang_b in names[i + 1:]
        if (food_a != food_b or lang_a == lang_b) and same_tokens(ta, tb)
    ]
    assert clashes == []


# The demo account's starter fridge is on the list with the same groups
def test_demo_fridge_matches_the_list():
    assert [(name, catalog_group(name)) for name, _ in DEMO_FRIDGE] == DEMO_FRIDGE


# The list matches by exact name: case, Turkish letters and plurals, never an extra word or a name it leaves out
def test_catalog_group_matches_exact_names():
    assert catalog_group("tomato") == "🥬 Produce"
    assert catalog_group("SALATALIK") == "🥬 Produce"
    assert catalog_group("Kasar peyniri") == "🐄 Animal Products"
    assert catalog_group("Zeytinler") == "🫒 Breakfast Staples"
    assert catalog_group("Free-range eggs") is None
    assert catalog_group("Pepper") is None


async def _state(db):
    async with db.execute("SELECT ingredient_name, group_name, picked FROM ingredient_group_memory") as cur:
        memory = {r[0]: (r[1], r[2]) for r in await cur.fetchall()}
    async with db.execute("SELECT name, group_name FROM ingredient_inventory") as cur:
        fridge = {r[0]: r[1] for r in await cur.fetchall()}
    return memory, fridge


# The one-time pass keeps every old name, marks the ones not in Other as picks, moves Other items the list knows, and runs only once
async def test_regroup_runs_once(client, db):
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        (user_id,) = await cur.fetchone()
    await db.executemany(
        "INSERT INTO ingredient_group_memory (user_id, ingredient_name, group_name) VALUES (?, ?, ?)",
        [(user_id, "Honey", DEFAULT_GROUP), (user_id, "Pepper", "🥬 Produce")],
    )
    await db.executemany(
        "INSERT INTO ingredient_inventory (user_id, name, group_name) VALUES (?, ?, ?)",
        [(user_id, "Honey", DEFAULT_GROUP), (user_id, "Grandma's spice mix", DEFAULT_GROUP),
         (user_id, "Olives", "🧂 Spices")],
    )
    await db.execute("PRAGMA user_version = 0")
    await db.commit()

    await database.init_db()
    memory, fridge = await _state(db)
    assert memory == {"Honey": (DEFAULT_GROUP, 0), "Pepper": ("🥬 Produce", 1)}
    assert fridge == {"Honey": "🍯 Sweets", "Grandma's spice mix": DEFAULT_GROUP, "Olives": "🧂 Spices"}

    # A later Other pick stays on the next start
    await db.execute("UPDATE ingredient_group_memory SET picked = 1 WHERE ingredient_name = 'Honey'")
    await db.execute("UPDATE ingredient_inventory SET group_name = ? WHERE name = 'Honey'", (DEFAULT_GROUP,))
    await db.commit()
    await database.init_db()
    memory, fridge = await _state(db)
    assert memory == {"Honey": (DEFAULT_GROUP, 1), "Pepper": ("🥬 Produce", 1)}
    assert fridge["Honey"] == DEFAULT_GROUP


# A database from before the list gets the picked column, so its old rows can be marked
async def test_old_memory_table_gets_picked(tmp_path, monkeypatch):
    import aiosqlite

    path = str(tmp_path / "old.db")
    async with aiosqlite.connect(path) as conn:
        await conn.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE ingredient_group_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, ingredient_name TEXT NOT NULL,
                group_name TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, ingredient_name));
            INSERT INTO users (id, name) VALUES (1, 'old');
            INSERT INTO ingredient_group_memory (user_id, ingredient_name, group_name) VALUES (1, 'Pepper', '🥬 Produce');
        """)
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    await database.init_db()
    async with aiosqlite.connect(path) as conn:
        async with conn.execute("SELECT ingredient_name, picked FROM ingredient_group_memory") as cur:
            assert await cur.fetchall() == [("Pepper", 1)]
