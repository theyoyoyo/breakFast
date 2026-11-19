"""
Tests for the insights service — aggregate meal history into inferred habits.
"""

import json
import aiosqlite
import database
from auth import hash_pin
from services.insights import refresh_insights_for_user, PATTERN_DAYS


async def _create_test_user(db_path: str, name: str = "testuser") -> int:
    """Create a test user and return the user_id."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash) VALUES (?, ?)",
            (name, hash_pin("1234")),
        )
        await db.commit()
        async with db.execute("SELECT id FROM users WHERE name = ?", (name,)) as cur:
            return (await cur.fetchone())[0]


async def _seed_meal(db, user_id: int, meal_name, ingredients, rating=None, days_ago=0, menu_items=None):
    """Insert a meal at a given age (days_ago=0 means now), with an optional menu."""
    logged_at = f"datetime('now', '-{days_ago} days')" if days_ago else "datetime('now')"
    await db.execute(
        f"""
        INSERT INTO meal_history (user_id, meal_name, ingredients, rating, menu_items, logged_at)
        VALUES (?, ?, ?, ?, ?, {logged_at})
        """,
        (user_id, meal_name, json.dumps(ingredients), rating,
         json.dumps(menu_items) if menu_items is not None else None),
    )


async def _inferred(user_id: int) -> list[str]:
    """The user's inferred habits."""
    async with database.get_db() as db:
        async with db.execute(
            "SELECT description FROM user_habits WHERE user_id = ? AND source = 'inferred'",
            (user_id,),
        ) as cur:
            return [r["description"] for r in await cur.fetchall()]


async def test_no_insights_with_too_few_meals(tmp_path, monkeypatch):
    """Fewer than 3 meals → no inferred habits produced."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    async with database.get_db() as db:
        await _seed_meal(db, user_id, "Toast", ["bread", "butter"])
        await db.commit()

    count = await refresh_insights_for_user(user_id)
    assert count == 0

    async with database.get_db() as db:
        async with db.execute(
            "SELECT * FROM user_habits WHERE user_id = ? AND source = 'inferred'",
            (user_id,),
        ) as cur:
            assert len(await cur.fetchall()) == 0


async def test_insights_from_sufficient_history(tmp_path, monkeypatch):
    """With enough meals, inferred habits are created."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    async with database.get_db() as db:
        await _seed_meal(db, user_id, "Eggs & Toast", ["eggs", "bread", "butter"])
        await _seed_meal(db, user_id, "Omelette", ["eggs", "cheese", "tomato"], rating=5)
        await _seed_meal(db, user_id, "Yogurt Bowl", ["yogurt", "berries", "honey"])
        await _seed_meal(db, user_id, "Scrambled Eggs", ["eggs", "olive oil"], rating=5)
        await db.commit()

    count = await refresh_insights_for_user(user_id)
    assert count >= 2  # at least "already eating enough" + "rarely eaten"

    async with database.get_db() as db:
        async with db.execute(
            "SELECT description FROM user_habits WHERE user_id = ? AND source = 'inferred'",
            (user_id,),
        ) as cur:
            descriptions = [r["description"] for r in await cur.fetchall()]

    frequent = next(d for d in descriptions if "Already eating enough" in d)
    assert "eggs" in frequent.lower()

    gaps = next(d for d in descriptions if "Rarely eaten" in d)
    assert len(gaps) > 0


async def test_refresh_replaces_old_inferred_habits(tmp_path, monkeypatch):
    """Running refresh twice replaces old inferred habits, not duplicates them."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    async with database.get_db() as db:
        for i in range(5):
            await _seed_meal(db, user_id, f"Meal {i}", ["eggs", "bread"])
        await db.commit()

    first_count = await refresh_insights_for_user(user_id)
    second_count = await refresh_insights_for_user(user_id)

    async with database.get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) as c FROM user_habits WHERE user_id = ? AND source = 'inferred'",
            (user_id,),
        ) as cur:
            total = (await cur.fetchone())["c"]

    assert total == second_count


async def test_stated_habits_not_deleted(tmp_path, monkeypatch):
    """refresh_insights only deletes inferred habits, never stated ones."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    async with database.get_db() as db:
        await db.execute(
            "INSERT INTO user_habits (user_id, description, source) VALUES (?, ?, 'stated')",
            (user_id, "I prefer quick breakfasts"),
        )
        for i in range(5):
            await _seed_meal(db, user_id, f"Meal {i}", ["eggs"])
        await db.commit()

    await refresh_insights_for_user(user_id)

    async with database.get_db() as db:
        async with db.execute(
            "SELECT * FROM user_habits WHERE user_id = ? AND source = 'stated'",
            (user_id,),
        ) as cur:
            stated = await cur.fetchall()

    assert len(stated) == 1
    assert stated[0]["description"] == "I prefer quick breakfasts"


async def test_old_meals_kept_and_not_counted(tmp_path, monkeypatch):
    """A meal from 45 days ago stays in the history after a refresh and isn't counted in the patterns."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    async with database.get_db() as db:
        await _seed_meal(db, user_id, "Recent 1", ["eggs"])
        await _seed_meal(db, user_id, "Recent 2", ["eggs", "bread"])
        await _seed_meal(db, user_id, "Recent 3", ["eggs", "yogurt"])
        await _seed_meal(db, user_id, "Old 1", ["rice"], days_ago=45)
        await db.commit()

    await refresh_insights_for_user(user_id)

    async with database.get_db() as db:
        async with db.execute(
            "SELECT meal_name FROM meal_history WHERE user_id = ?",
            (user_id,),
        ) as cur:
            names = [r["meal_name"] for r in await cur.fetchall()]
        async with db.execute(
            "SELECT description FROM user_habits WHERE user_id = ? AND source = 'inferred'",
            (user_id,),
        ) as cur:
            descriptions = [r["description"] for r in await cur.fetchall()]

    assert 45 > PATTERN_DAYS
    assert {"Recent 1", "Recent 2", "Recent 3", "Old 1"} <= set(names)
    frequent = next(d for d in descriptions if "Already eating enough" in d)
    assert "eggs (3x)" in frequent
    assert "rice" not in frequent


async def test_structured_ingredients_handled(tmp_path, monkeypatch):
    """Structured dict ingredients (name/quantity/unit) are parsed correctly."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    structured = [
        {"name": "Eggs", "quantity": 2, "unit": "adet"},
        {"name": "Bread", "quantity": 1, "unit": "dilim"},
    ]
    async with database.get_db() as db:
        await _seed_meal(db, user_id, "Meal 1", structured)
        await _seed_meal(db, user_id, "Meal 2", structured)
        await _seed_meal(db, user_id, "Meal 3", structured)
        await db.commit()

    count = await refresh_insights_for_user(user_id)
    assert count >= 1

    async with database.get_db() as db:
        async with db.execute(
            "SELECT description FROM user_habits WHERE user_id = ? AND source = 'inferred'",
            (user_id,),
        ) as cur:
            descriptions = [r["description"] for r in await cur.fetchall()]

    frequent = next(d for d in descriptions if "Already eating enough" in d)
    assert "eggs" in frequent.lower()
    assert "bread" in frequent.lower()


async def test_high_rated_patterns_extracted(tmp_path, monkeypatch):
    """Ingredients from 5-star meals appear in high-rated insight."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    async with database.get_db() as db:
        await _seed_meal(db, user_id, "Fav 1", ["avocado", "eggs"], rating=5)
        await _seed_meal(db, user_id, "Fav 2", ["avocado", "tomato"], rating=5)
        await _seed_meal(db, user_id, "Meh", ["bread", "butter"], rating=1)
        await _seed_meal(db, user_id, "OK", ["oats", "milk"])
        await db.commit()

    await refresh_insights_for_user(user_id)

    async with database.get_db() as db:
        async with db.execute(
            "SELECT description FROM user_habits WHERE user_id = ? AND source = 'inferred'",
            (user_id,),
        ) as cur:
            descriptions = [r["description"] for r in await cur.fetchall()]

    rated = next((d for d in descriptions if "High-rated" in d), None)
    assert rated is not None
    assert "avocado" in rated.lower()


# A menu card's flat list is the menu as first suggested; the menu as eaten is what counts
async def test_menu_items_counted_over_flat_list(tmp_path, monkeypatch):
    """A meal whose menu differs from its flat ingredients counts the menu's dish ingredients and simple items."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    menu = [
        {"name": "Omelette", "ingredients": [{"name": "Eggs", "amount": 2, "unit": "pcs"}, {"name": "Spinach"}]},
        {"name": "Feta", "amount": 50, "unit": "g", "ingredients": []},
    ]
    async with database.get_db() as db:
        for i in range(3):
            await _seed_meal(db, user_id, f"Edited {i}", [{"name": "Salmon"}, {"name": "Bread"}], rating=5, menu_items=menu)
        await db.commit()

    await refresh_insights_for_user(user_id)
    descriptions = await _inferred(user_id)

    frequent = next(d for d in descriptions if "Already eating enough" in d)
    assert "eggs (3x)" in frequent
    assert "spinach (3x)" in frequent
    assert "feta (3x)" in frequent
    assert "salmon" not in frequent and "bread" not in frequent
    rated = next(d for d in descriptions if "High-rated" in d)
    assert "eggs" in rated and "salmon" not in rated


# A dish is counted by what's in it, never by its own name
async def test_dish_name_not_counted(tmp_path, monkeypatch):
    """A dish's own name isn't counted as an ingredient."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    menu = [{"name": "Menemen", "ingredients": [{"name": "Eggs"}, {"name": "Tomatoes"}]}]
    async with database.get_db() as db:
        for i in range(3):
            await _seed_meal(db, user_id, f"Meal {i}", [], menu_items=menu)
        await db.commit()

    await refresh_insights_for_user(user_id)
    frequent = next(d for d in await _inferred(user_id) if "Already eating enough" in d)
    assert "eggs (3x)" in frequent and "tomatoes (3x)" in frequent
    assert "menemen" not in frequent


# Meals from before the menu format have only the flat list, and still count
async def test_old_flat_meal_still_counted(tmp_path, monkeypatch):
    """A meal with no menu counts its flat ingredients, beside meals that have a menu."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    user_id = await _create_test_user(db_path)

    async with database.get_db() as db:
        await _seed_meal(db, user_id, "Old flat", [{"name": "Oats"}, "honey"])
        await _seed_meal(db, user_id, "Empty menu", [{"name": "Oats"}], menu_items=[])
        await _seed_meal(db, user_id, "Menu", [{"name": "Rice"}], menu_items=[{"name": "Oats", "amount": 40, "unit": "g", "ingredients": []}])
        await db.commit()

    await refresh_insights_for_user(user_id)
    frequent = next(d for d in await _inferred(user_id) if "Already eating enough" in d)
    assert "oats (3x)" in frequent
    assert "honey (1x)" in frequent
    assert "rice" not in frequent
