"""Integration tests for the /preferences endpoints (key-value prefs and habits)."""


async def test_list_preferences_empty(client):
    r = await client.get("/preferences/")
    assert r.status_code == 200
    assert r.json() == []


async def test_set_and_get_preference(client):
    r = await client.put("/preferences/fav:eggs", json={"value": "eggs"})
    assert r.status_code == 200
    data = r.json()
    assert data["key"] == "fav:eggs"
    assert data["value"] == "eggs"


async def test_set_preference_is_idempotent(client):
    await client.put("/preferences/fav:toast", json={"value": "toast"})
    await client.put("/preferences/fav:toast", json={"value": "TOAST"})
    prefs = (await client.get("/preferences/")).json()
    matches = [p for p in prefs if p["key"] == "fav:toast"]
    assert len(matches) == 1
    assert matches[0]["value"] == "TOAST"


async def test_delete_preference(client):
    await client.put("/preferences/dislike:mushrooms", json={"value": "mushrooms"})
    r = await client.delete("/preferences/dislike:mushrooms")
    assert r.status_code == 204
    keys = [p["key"] for p in (await client.get("/preferences/")).json()]
    assert "dislike:mushrooms" not in keys


async def test_list_habits_empty(client):
    r = await client.get("/preferences/habits")
    assert r.status_code == 200
    assert r.json() == []


async def test_add_and_list_habit(client):
    r = await client.post("/preferences/habits", json={"description": "eat breakfast before 9am"})
    assert r.status_code == 201
    habit = r.json()
    assert habit["description"] == "eat breakfast before 9am"
    assert habit["source"] == "stated"
    assert "id" in habit


async def test_delete_habit(client):
    habit = (await client.post("/preferences/habits", json={"description": "avoid sugar"})).json()
    r = await client.delete(f"/preferences/habits/{habit['id']}")
    assert r.status_code == 204
    habits = (await client.get("/preferences/habits")).json()
    assert all(h["id"] != habit["id"] for h in habits)
