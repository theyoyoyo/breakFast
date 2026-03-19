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
