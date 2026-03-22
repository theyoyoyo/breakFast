"""Integration tests for the /meals endpoints."""


SAMPLE_MEAL = {
    "meal_name": "Scrambled Eggs",
    "description": "Quick and easy",
    "ingredients": ["2 eggs", "butter", "salt"],
    "steps": ["Beat eggs", "Melt butter", "Cook"],
    "prep_time_min": 5,
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


async def test_rate_meal(client):
    meal = (await client.post("/meals/", json=SAMPLE_MEAL)).json()
    r = await client.patch(f"/meals/{meal['id']}/rating", json={"rating": 5})
    assert r.status_code == 200
    assert r.json()["rating"] == 5


async def test_rate_unknown_meal_returns_404(client):
    r = await client.patch("/meals/9999/rating", json={"rating": 5})
    assert r.status_code == 404


# Returns zero when no meals are older than 1 year
async def test_delete_old_meals_none(client):
    await client.post("/meals/", json=SAMPLE_MEAL)
    r = await client.delete("/meals/old")
    assert r.status_code == 200
    assert r.json()["deleted"] == 0
    # Meal still exists
    meals = (await client.get("/meals/")).json()
    assert len(meals) == 1


# Deletes meals with logged_at artificially set to 2 years ago
async def test_delete_old_meals_removes_old(client, db):
    meal = (await client.post("/meals/", json=SAMPLE_MEAL)).json()
    await db.execute(
        "UPDATE meal_history SET logged_at = datetime('now', '-2 years') WHERE id = ?",
        (meal["id"],),
    )
    await db.commit()
    r = await client.delete("/meals/old")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1
    meals = (await client.get("/meals/")).json()
    assert len(meals) == 0
