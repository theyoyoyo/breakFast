"""Tests for the per-user context loaders that feed the prompts."""

from services.context import _food_preferences


# App settings and avoid entries never reach prompts as food preferences
def test_food_preferences_drop_settings_and_avoid_entries():
    prefs = {
        "fav:1": "olives",
        "avoid:1": "peanuts",
        "response_language": "tr",
        "theme": "purple",
        "weekly_summary_in_suggestions": "true",
    }
    assert _food_preferences(prefs) == {"fav:1": "olives"}


# The chat context's history carries each meal's menu, so the pipeline's reviewer sees what recent meals had
async def test_chat_history_has_menu_items(client, db):
    from services.context import load_chat_context
    from services.knowledge import format_history_detailed

    menu = [{"name": "Menemen", "ingredients": [{"name": "Eggs", "amount": 2, "unit": "pcs"}]}]
    await client.post("/meals/", json={"meal_name": "Weekend", "ingredients": [], "menu_items": menu})
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        user_id = (await cur.fetchone())[0]

    chat = await load_chat_context(db, user_id)
    assert format_history_detailed(chat["history"]) == "- Weekend: Menemen (Eggs)"


# The profile's country reaches the chat and shopping contexts, but not the profile text the analysts read
async def test_country_in_contexts(client, db):
    from services.context import load_chat_context, load_shopping_context
    from services.knowledge import format_user_profile

    await client.put("/profile/", json={"age": 30, "country": "Türkiye"})
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        user_id = (await cur.fetchone())[0]

    chat = await load_chat_context(db, user_id)
    shopping = await load_shopping_context(db, user_id)
    assert chat["country"] == "Türkiye"
    assert shopping["country"] == "Türkiye"
    assert "Türkiye" not in format_user_profile(chat["user_profile"])


# The favorite meals loader returns this user's newest ten saved meals with their menus, newest first
async def test_favorite_meals_newest_ten_for_this_user(client, db):
    import json
    from services.context import fetch_favorite_meals
    from services.knowledge import format_meal_items

    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        user_id = (await cur.fetchone())[0]
    cur = await db.execute("INSERT INTO users (name, pin_hash) VALUES ('other', 'x')")
    other_id = cur.lastrowid
    menu = json.dumps([{"name": "Menemen", "ingredients": [{"name": "Eggs", "amount": 2, "unit": "pcs"}]}])
    for i in range(12):
        await db.execute(
            "INSERT INTO favorite_meals (user_id, meal_name, menu_items, created_at) VALUES (?, ?, ?, ?)",
            (user_id, f"Meal {i}", menu, f"2026-11-01 08:{i:02d}:00"),
        )
    await db.execute(
        "INSERT INTO favorite_meals (user_id, meal_name, created_at) VALUES (?, 'Not mine', '2026-11-02 08:00:00')",
        (other_id,),
    )
    await db.commit()

    meals = await fetch_favorite_meals(db, user_id)
    assert [m["meal_name"] for m in meals] == [f"Meal {i}" for i in range(11, 1, -1)]
    assert format_meal_items(meals[0]) == "Menemen (Eggs)"


# The chat context carries the saved favorite meals, the staples and the ratings, which favorites mode lists
async def test_chat_context_has_taste_hints(client, db):
    from services.context import load_chat_context

    menu = [{"name": "Cheddar toast", "ingredients": [{"name": "Bread", "amount": 2, "unit": "slice"}]}]
    await client.post("/favorites/", json={"menu_name": "Cheddar toast", "menu": menu})
    await client.post("/favorite-ingredients/", json={"ingredient_name": "Cheddar"})
    await client.post("/ratings/", json={"product_name": "Cheddar", "rating": 9})
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        user_id = (await cur.fetchone())[0]

    chat = await load_chat_context(db, user_id)
    assert [m["meal_name"] for m in chat["favorite_meals"]] == ["Cheddar toast"]
    assert chat["favorites"] == ["Cheddar"]
    assert chat["ratings"] == [{"product_name": "Cheddar", "rating": 9}]
