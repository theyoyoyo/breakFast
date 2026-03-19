"""
Tests for the insights service — aggregate, infer habits, and prune old meals.
"""

import json
import aiosqlite
import database
from services.insights import refresh_insights, _build_insights, _RETENTION_DAYS


async def _seed_meal(db, meal_name, ingredients, rating=None, days_ago=0):
    """Insert a meal at a given age (days_ago=0 means now)."""
    logged_at = f"datetime('now', '-{days_ago} days')" if days_ago else "datetime('now')"
    await db.execute(
        f"""
        INSERT INTO meal_history (meal_name, ingredients, rating, logged_at)
        VALUES (?, ?, ?, {logged_at})
        """,
        (meal_name, json.dumps(ingredients), rating),
    )


async def test_no_insights_with_too_few_meals(tmp_path, monkeypatch):
    """Fewer than 3 meals → no inferred habits produced."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    async with database.get_db() as db:
        await _seed_meal(db, "Toast", ["bread", "butter"])
        await db.commit()

    count = await refresh_insights()
    assert count == 0

    # No inferred habits written
    async with database.get_db() as db:
        async with db.execute(
            "SELECT * FROM user_habits WHERE source = 'inferred'"
        ) as cur:
            assert len(await cur.fetchall()) == 0


async def test_insights_from_sufficient_history(tmp_path, monkeypatch):
    """With enough meals, inferred habits are created."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    async with database.get_db() as db:
        await _seed_meal(db, "Eggs & Toast", ["eggs", "bread", "butter"])
        await _seed_meal(db, "Omelette", ["eggs", "cheese", "tomato"], rating=5)
        await _seed_meal(db, "Yogurt Bowl", ["yogurt", "berries", "honey"])
        await _seed_meal(db, "Scrambled Eggs", ["eggs", "olive oil"], rating=5)
        await db.commit()

    count = await refresh_insights()
    assert count >= 2  # at least "already eating enough" + "rarely eaten"

    async with database.get_db() as db:
        async with db.execute(
            "SELECT description FROM user_habits WHERE source = 'inferred'"
        ) as cur:
            descriptions = [r["description"] for r in await cur.fetchall()]

    # "eggs" should show up as frequently eaten
    frequent = next(d for d in descriptions if "Already eating enough" in d)
    assert "eggs" in frequent.lower()

    # There should be a "rarely eaten" insight listing healthy gaps
    gaps = next(d for d in descriptions if "Rarely eaten" in d)
    assert len(gaps) > 0


async def test_refresh_replaces_old_inferred_habits(tmp_path, monkeypatch):
    """Running refresh twice replaces old inferred habits, not duplicates them."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    async with database.get_db() as db:
        for i in range(5):
            await _seed_meal(db, f"Meal {i}", ["eggs", "bread"])
        await db.commit()

    first_count = await refresh_insights()
    second_count = await refresh_insights()

    # Counts should be similar (same data), and no duplicates
    async with database.get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) as c FROM user_habits WHERE source = 'inferred'"
        ) as cur:
            total = (await cur.fetchone())["c"]

    assert total == second_count  # only latest batch exists


async def test_stated_habits_not_deleted(tmp_path, monkeypatch):
    """refresh_insights only deletes inferred habits, never stated ones."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    # Add a stated habit
    async with database.get_db() as db:
        await db.execute(
            "INSERT INTO user_habits (description, source) VALUES (?, 'stated')",
            ("I prefer quick breakfasts",),
        )
        for i in range(5):
            await _seed_meal(db, f"Meal {i}", ["eggs"])
        await db.commit()

    await refresh_insights()

    async with database.get_db() as db:
        async with db.execute(
            "SELECT * FROM user_habits WHERE source = 'stated'"
        ) as cur:
            stated = await cur.fetchall()

    assert len(stated) == 1
    assert stated[0]["description"] == "I prefer quick breakfasts"


async def test_old_meals_pruned(tmp_path, monkeypatch):
    """Meals older than retention window are deleted after insights run."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    async with database.get_db() as db:
        # 3 recent meals + 2 old meals
        await _seed_meal(db, "Recent 1", ["eggs"])
        await _seed_meal(db, "Recent 2", ["bread"])
        await _seed_meal(db, "Recent 3", ["yogurt"])
        await _seed_meal(db, "Old 1", ["rice"], days_ago=_RETENTION_DAYS + 5)
        await _seed_meal(db, "Old 2", ["pasta"], days_ago=_RETENTION_DAYS + 10)
        await db.commit()

    await refresh_insights()

    async with database.get_db() as db:
        async with db.execute("SELECT meal_name FROM meal_history") as cur:
            names = [r["meal_name"] for r in await cur.fetchall()]

    assert "Recent 1" in names
    assert "Recent 2" in names
    assert "Recent 3" in names
    assert "Old 1" not in names
    assert "Old 2" not in names


async def test_high_rated_patterns_extracted(tmp_path, monkeypatch):
    """Ingredients from 5-star meals appear in high-rated insight."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    async with database.get_db() as db:
        await _seed_meal(db, "Fav 1", ["avocado", "eggs"], rating=5)
        await _seed_meal(db, "Fav 2", ["avocado", "tomato"], rating=5)
        await _seed_meal(db, "Meh", ["bread", "butter"], rating=1)
        await _seed_meal(db, "OK", ["oats", "milk"])
        await db.commit()

    await refresh_insights()

    async with database.get_db() as db:
        async with db.execute(
            "SELECT description FROM user_habits WHERE source = 'inferred'"
        ) as cur:
            descriptions = [r["description"] for r in await cur.fetchall()]

    rated = next((d for d in descriptions if "High-rated" in d), None)
    assert rated is not None
    assert "avocado" in rated.lower()
