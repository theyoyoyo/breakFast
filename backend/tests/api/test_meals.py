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


# Updates meal name and ingredients via PUT
async def test_update_meal(client):
    meal = (await client.post("/meals/", json=SAMPLE_MEAL)).json()
    updated = {**SAMPLE_MEAL, "meal_name": "Menemen", "ingredients": ["eggs", "tomato", "pepper"]}
    r = await client.put(f"/meals/{meal['id']}", json=updated)
    assert r.status_code == 200
    data = r.json()
    assert data["meal_name"] == "Menemen"
    assert data["ingredients"] == ["eggs", "tomato", "pepper"]


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
