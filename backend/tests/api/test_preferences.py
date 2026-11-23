"""Integration tests for the /preferences endpoints (key-value prefs and habits)."""


# A new user has no preferences
async def test_list_preferences_empty(client):
    r = await client.get("/preferences/")
    assert r.status_code == 200
    assert r.json() == []


# A preference is saved under its key with its value
async def test_set_and_get_preference(client):
    r = await client.put("/preferences/fav:eggs", json={"value": "eggs"})
    assert r.status_code == 200
    data = r.json()
    assert data["key"] == "fav:eggs"
    assert data["value"] == "eggs"


# Setting a key again replaces its value instead of adding a second row
async def test_set_preference_is_idempotent(client):
    await client.put("/preferences/fav:toast", json={"value": "toast"})
    await client.put("/preferences/fav:toast", json={"value": "TOAST"})
    prefs = (await client.get("/preferences/")).json()
    matches = [p for p in prefs if p["key"] == "fav:toast"]
    assert len(matches) == 1
    assert matches[0]["value"] == "TOAST"


# A deleted preference is gone from the list
async def test_delete_preference(client):
    await client.put("/preferences/dislike:mushrooms", json={"value": "mushrooms"})
    r = await client.delete("/preferences/dislike:mushrooms")
    assert r.status_code == 204
    keys = [p["key"] for p in (await client.get("/preferences/")).json()]
    assert "dislike:mushrooms" not in keys


# An avoid-list item is saved like any other preference, under its avoid: key
async def test_set_avoid_preference(client):
    r = await client.put("/preferences/avoid:shellfish", json={"value": "shellfish"})
    assert r.status_code == 200
    data = r.json()
    assert data["key"] == "avoid:shellfish"
    assert data["value"] == "shellfish"


# An avoid-list item can be deleted by its key
async def test_delete_avoid_preference(client):
    await client.put("/preferences/avoid:peanuts", json={"value": "peanuts"})
    r = await client.delete("/preferences/avoid:peanuts")
    assert r.status_code == 204
    keys = [p["key"] for p in (await client.get("/preferences/")).json()]
    assert "avoid:peanuts" not in keys


# Likes, dislikes and the avoid list are kept side by side
async def test_avoid_coexists_with_fav_and_dislike(client):
    await client.put("/preferences/fav:eggs", json={"value": "eggs"})
    await client.put("/preferences/dislike:olives", json={"value": "olives"})
    await client.put("/preferences/avoid:gluten", json={"value": "gluten"})
    prefs = (await client.get("/preferences/")).json()
    keys = [p["key"] for p in prefs]
    assert "fav:eggs" in keys
    assert "dislike:olives" in keys
    assert "avoid:gluten" in keys


# A new user has no habits
async def test_list_habits_empty(client):
    r = await client.get("/preferences/habits")
    assert r.status_code == 200
    assert r.json() == []


# A habit the user adds is saved as stated, with an id
async def test_add_and_list_habit(client):
    r = await client.post("/preferences/habits", json={"description": "eat breakfast before 9am"})
    assert r.status_code == 201
    habit = r.json()
    assert habit["description"] == "eat breakfast before 9am"
    assert habit["source"] == "stated"
    assert "id" in habit


# A deleted habit is gone from the list
async def test_delete_habit(client):
    habit = (await client.post("/preferences/habits", json={"description": "avoid sugar"})).json()
    r = await client.delete(f"/preferences/habits/{habit['id']}")
    assert r.status_code == 204
    habits = (await client.get("/preferences/habits")).json()
    assert all(h["id"] != habit["id"] for h in habits)
