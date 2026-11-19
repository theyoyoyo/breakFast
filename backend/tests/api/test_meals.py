"""Integration tests for the /meals endpoints."""


SAMPLE_MEAL = {
    "meal_name": "Scrambled Eggs",
    "description": "Quick and easy",
    "ingredients": ["2 eggs", "butter", "salt"],
    "steps": ["Beat eggs", "Melt butter", "Cook"],
    "prep_time_min": 5,
}

STRUCTURED_MEAL = {
    "meal_name": "Menemen",
    "description": "Classic Turkish breakfast",
    "ingredients": [
        {"name": "yumurta", "quantity": 2, "unit": "adet"},
        {"name": "domates", "quantity": 1, "unit": "adet"},
        {"name": "biber", "quantity": 0.5, "unit": "adet"},
    ],
    "steps": ["Chop vegetables", "Fry", "Add eggs"],
    "prep_time_min": 10,
}


async def test_list_meals_empty(client):
    r = await client.get("/meals/")
    assert r.status_code == 200
    assert r.json() == []


async def test_log_meal(client):
    r = await client.post("/meals/", json=SAMPLE_MEAL)
    assert r.status_code == 201
    data = r.json()
    assert data["meal_name"] == "Scrambled Eggs"
    assert data["ingredients"] == ["2 eggs", "butter", "salt"]
    assert data["steps"] == ["Beat eggs", "Melt butter", "Cook"]
    assert data["rating"] is None
    assert "id" in data


# Logs a meal with structured ingredients (name/quantity/unit objects)
async def test_log_meal_structured_ingredients(client):
    r = await client.post("/meals/", json=STRUCTURED_MEAL)
    assert r.status_code == 201
    data = r.json()
    assert data["meal_name"] == "Menemen"
    assert len(data["ingredients"]) == 3
    assert data["ingredients"][0]["name"] == "yumurta"
    assert data["ingredients"][0]["quantity"] == 2
    assert data["ingredients"][0]["unit"] == "adet"
    assert data["ingredients"][2]["quantity"] == 0.5


# Newly created meals have no cached nutrition
async def test_new_meal_has_null_cached_nutrition(client):
    r = await client.post("/meals/", json=STRUCTURED_MEAL)
    assert r.status_code == 201
    assert r.json()["cached_nutrition"] is None


# Updates meal name and ingredients via PUT
async def test_update_meal(client):
    meal = (await client.post("/meals/", json=SAMPLE_MEAL)).json()
    updated = {**SAMPLE_MEAL, "meal_name": "Menemen", "ingredients": ["eggs", "tomato", "pepper"]}
    r = await client.put(f"/meals/{meal['id']}", json=updated)
    assert r.status_code == 200
    data = r.json()
    assert data["meal_name"] == "Menemen"
    assert data["ingredients"] == ["eggs", "tomato", "pepper"]


# Updating a meal clears cached_nutrition
async def test_update_meal_clears_cache(client, db):
    meal = (await client.post("/meals/", json=STRUCTURED_MEAL)).json()
    # Manually set cached_nutrition and schedule to simulate prior results
    await db.execute(
        "UPDATE meal_history SET cached_nutrition = ?, schedule = ? WHERE id = ?",
        ('{"analysis_text": "test", "analysis_data": {}}',
         '{"timeline": [], "makespan_min": 5, "formatted": "test"}',
         meal["id"]),
    )
    await db.commit()
    # Verify they're set
    async with db.execute("SELECT cached_nutrition, schedule FROM meal_history WHERE id = ?", (meal["id"],)) as cur:
        row = await cur.fetchone()
        assert row[0] is not None
        assert row[1] is not None
    # Update the meal — should clear both caches
    updated = {**STRUCTURED_MEAL, "meal_name": "Updated Menemen"}
    r = await client.put(f"/meals/{meal['id']}", json=updated)
    assert r.status_code == 200
    assert r.json()["cached_nutrition"] is None
    # Verify schedule is also cleared
    async with db.execute("SELECT schedule FROM meal_history WHERE id = ?", (meal["id"],)) as cur:
        row = await cur.fetchone()
        assert row[0] is None


# Returns 404 when updating a non-existent meal
async def test_update_unknown_meal_returns_404(client):
    r = await client.put("/meals/9999", json=SAMPLE_MEAL)
    assert r.status_code == 404


# Deletes a single meal by ID
async def test_delete_meal(client):
    meal = (await client.post("/meals/", json=SAMPLE_MEAL)).json()
    r = await client.delete(f"/meals/{meal['id']}")
    assert r.status_code == 204
    meals = (await client.get("/meals/")).json()
    assert len(meals) == 0


# Returns 404 when deleting a non-existent meal
async def test_delete_unknown_meal_returns_404(client):
    r = await client.delete("/meals/9999")
    assert r.status_code == 404


# Returns zero when no meals are older than one month
async def test_delete_old_meals_none(client):
    await client.post("/meals/", json=SAMPLE_MEAL)
    r = await client.delete("/meals/old")
    assert r.status_code == 200
    assert r.json()["deleted"] == 0
    # Meal still exists
    meals = (await client.get("/meals/")).json()
    assert len(meals) == 1


# Deletes the user's meals older than one month, keeps newer ones and never another user's
async def test_delete_old_meals_removes_old(client, db):
    old = (await client.post("/meals/", json=SAMPLE_MEAL)).json()
    recent = (await client.post("/meals/", json=STRUCTURED_MEAL)).json()
    await db.execute("UPDATE meal_history SET logged_at = datetime('now', '-45 days') WHERE id = ?", (old["id"],))
    await db.execute("UPDATE meal_history SET logged_at = datetime('now', '-20 days') WHERE id = ?", (recent["id"],))
    cur = await db.execute("INSERT INTO users (name, pin_hash) VALUES ('user2', 'x')")
    other_id = cur.lastrowid
    await db.execute(
        "INSERT INTO meal_history (user_id, meal_name, logged_at) VALUES (?, 'Other', datetime('now', '-45 days'))",
        (other_id,),
    )
    await db.commit()
    r = await client.delete("/meals/old")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1
    meals = (await client.get("/meals/")).json()
    assert [m["id"] for m in meals] == [recent["id"]]
    async with db.execute("SELECT COUNT(*) AS c FROM meal_history WHERE user_id = ?", (other_id,)) as c:
        assert (await c.fetchone())["c"] == 1
