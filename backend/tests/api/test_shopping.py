"""Integration tests for the /shopping endpoints."""



# A new user's shopping list is empty
async def test_list_empty_on_fresh_db(client):
    r = await client.get("/shopping/")
    assert r.status_code == 200
    assert r.json() == []


# An item added to the shopping list comes back with its name and an id
async def test_add_item(client):
    r = await client.post("/shopping/", json={"item_name": "Eggs"})
    assert r.status_code == 201
    data = r.json()
    assert data["item_name"] == "Eggs"
    assert "id" in data


# Adding an item already on the list keeps one row
async def test_add_duplicate_ignored(client):
    await client.post("/shopping/", json={"item_name": "Milk"})
    r = await client.post("/shopping/", json={"item_name": "Milk"})
    assert r.status_code == 201
    # Should still be only one item
    listed = (await client.get("/shopping/")).json()
    milks = [i for i in listed if i["item_name"] == "Milk"]
    assert len(milks) == 1


# A deleted item is gone from the shopping list
async def test_delete_item(client):
    created = (await client.post("/shopping/", json={"item_name": "cheese"})).json()
    r = await client.delete(f"/shopping/{created['id']}")
    assert r.status_code == 204
    listed = (await client.get("/shopping/")).json()
    assert all(i["id"] != created["id"] for i in listed)


# A bulk add puts every item on the list and says how many it added
async def test_bulk_add(client):
    payload = [{"item_name": "tomato"}, {"item_name": "onion"}]
    r = await client.post("/shopping/bulk", json=payload)
    assert r.status_code == 201
    assert r.json() == {"added": 2}
    names = [i["item_name"] for i in (await client.get("/shopping/")).json()]
    assert "tomato" in names and "onion" in names


# A bulk add skips an item that is already on the list
async def test_bulk_add_skips_duplicates(client):
    await client.post("/shopping/", json={"item_name": "butter"})
    payload = [{"item_name": "butter"}, {"item_name": "cream"}]
    r = await client.post("/shopping/bulk", json=payload)
    assert r.status_code == 201
    listed = (await client.get("/shopping/")).json()
    butters = [i for i in listed if i["item_name"] == "butter"]
    assert len(butters) == 1


# Buying nothing is accepted and reports zero items bought
async def test_bought_empty_ids(client):
    r = await client.post("/shopping/bought", json={"ids": []})
    assert r.status_code == 200
    assert r.json() == {"bought": 0}


# Bought items move from the shopping list into the fridge
async def test_bought_adds_to_ingredients_and_removes_from_list(client):
    # Add items to shopping list
    item1 = (await client.post("/shopping/", json={"item_name": "Yogurt"})).json()
    item2 = (await client.post("/shopping/", json={"item_name": "Bread"})).json()

    # Buy them
    r = await client.post("/shopping/bought", json={"ids": [item1["id"], item2["id"]]})
    assert r.status_code == 200
    assert r.json() == {"bought": 2}

    # Shopping list should be empty
    listed = (await client.get("/shopping/")).json()
    assert len(listed) == 0

    # Items should be in ingredients
    ingredients = (await client.get("/ingredients/")).json()
    names = [i["name"] for i in ingredients]
    assert "Yogurt" in names
    assert "Bread" in names


# A bought item's best before date reaches its fridge item
async def test_bought_with_expiry_dates(client):
    item = (await client.post("/shopping/", json={"item_name": "Milk"})).json()

    r = await client.post("/shopping/bought", json={
        "ids": [item["id"]],
        "expiry_dates": {"Milk": "2026-04-15"},
    })
    assert r.status_code == 200

    # Check ingredient has the expiry date
    ingredients = (await client.get("/ingredients/")).json()
    milk = [i for i in ingredients if i["name"] == "Milk"][0]
    assert milk["expiry_date"] == "2026-04-15"


# Buying an item already in the fridge updates its expiry instead of adding a second row
async def test_bought_upserts_existing_ingredient(client):
    # Add an ingredient first
    await client.post("/ingredients/", json={"name": "Eggs"})

    # Add same item to shopping list and buy it
    item = (await client.post("/shopping/", json={"item_name": "Eggs"})).json()
    r = await client.post("/shopping/bought", json={
        "ids": [item["id"]],
        "expiry_dates": {"Eggs": "2026-05-01"},
    })
    assert r.status_code == 200

    # Should still be one ingredient, with updated expiry
    ingredients = (await client.get("/ingredients/")).json()
    eggs_list = [i for i in ingredients if i["name"] == "Eggs"]
    assert len(eggs_list) == 1
    assert eggs_list[0]["expiry_date"] == "2026-05-01"


async def test_bought_restores_group_from_memory(client):
    """Buying an item restores its group from memory if previously assigned."""
    # Add ingredient with explicit group, then delete it
    created = (await client.post("/ingredients/", json={"name": "Kasar", "group_name": "🐄 Animal Products"})).json()
    await client.delete(f"/ingredients/{created['id']}")

    # Add to shopping list and buy
    item = (await client.post("/shopping/", json={"item_name": "Kasar"})).json()
    await client.post("/shopping/bought", json={"ids": [item["id"]]})

    # Check ingredient has restored group
    ingredients = (await client.get("/ingredients/")).json()
    kasar = [i for i in ingredients if i["name"] == "Kasar"][0]
    assert kasar["group_name"] == "🐄 Animal Products"


# A bought item the user never placed gets the food list's group and is recorded, and an id that's gone doesn't stop the rest
async def test_bought_uses_the_food_list(client, db):
    item = (await client.post("/shopping/", json={"item_name": "Strawberries"})).json()
    r = await client.post("/shopping/bought", json={"ids": [item["id"], 9999]})
    assert r.json() == {"bought": 1}
    ingredients = (await client.get("/ingredients/")).json()
    assert [(i["name"], i["group_name"]) for i in ingredients] == [("Strawberries", "🥬 Produce")]
    async with db.execute("SELECT ingredient_name, group_name, picked FROM ingredient_group_memory") as cur:
        assert [tuple(r) for r in await cur.fetchall()] == [("Strawberries", "🥬 Produce", 0)]


# Delete all empties this user's shopping list and leaves another user's alone
async def test_clear_shopping_list_is_per_user(client):
    await client.post("/shopping/bulk", json=[{"item_name": "Kiwi"}, {"item_name": "Salmon"}])
    other = await _second_user_auth()
    await client.post("/shopping/", json={"item_name": "Milk"}, headers=other)
    r = await client.delete("/shopping/")
    assert r.status_code == 204
    assert (await client.get("/shopping/")).json() == []
    assert [i["item_name"] for i in (await client.get("/shopping/", headers=other)).json()] == ["Milk"]


# ---------------------------------------------------------------------------
# Shopping suggestions list (/shopping/suggestions)
# ---------------------------------------------------------------------------

SALMON = {"name": "Salmon", "reason": "Omega-3", "checked": True}
KIWI = {"name": "Kiwi", "reason": "In season", "checked": False}


async def _second_user_auth():
    """Auth header for a second user in the same test database."""
    import aiosqlite

    import database
    from auth import create_token, hash_pin

    async with aiosqlite.connect(database.DATABASE_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO users (name, pin_hash, is_admin) VALUES (?, ?, ?)", ("user2", hash_pin("5678"), 0),
        )
        await conn.commit()
    return {"Authorization": f"Bearer {create_token(cur.lastrowid)}"}


# A new user's suggestions list is empty
async def test_suggestions_list_empty_on_fresh_db(client):
    r = await client.get("/shopping/suggestions")
    assert r.status_code == 200
    assert r.json() == {"items": []}


# The saved list comes back in order with each item's reason and check
async def test_suggestions_list_saved_and_loaded(client):
    r = await client.put("/shopping/suggestions", json={"items": [KIWI, SALMON]})
    assert r.status_code == 200
    assert r.json() == {"items": [KIWI, SALMON]}
    assert (await client.get("/shopping/suggestions")).json() == {"items": [KIWI, SALMON]}


# Saving replaces the whole list: items left out (sent to the shopping list) are gone
async def test_suggestions_list_save_replaces(client):
    await client.put("/shopping/suggestions", json={"items": [SALMON, KIWI]})
    await client.put("/shopping/suggestions", json={"items": [KIWI]})
    assert (await client.get("/shopping/suggestions")).json() == {"items": [KIWI]}


# A removed item leaves the list
async def test_suggestions_list_removed_item_leaves(client):
    await client.put("/shopping/suggestions", json={"items": [SALMON, KIWI]})
    r = await client.put("/shopping/suggestions", json={"items": [SALMON], "removed": ["Kiwi"]})
    assert r.json() == {"items": [SALMON]}


# Another user neither sees nor changes the list
async def test_suggestions_list_is_per_user(client):
    await client.put("/shopping/suggestions", json={"items": [SALMON]})
    other = await _second_user_auth()
    assert (await client.get("/shopping/suggestions", headers=other)).json() == {"items": []}
    await client.put("/shopping/suggestions", json={"items": [KIWI]}, headers=other)
    assert (await client.get("/shopping/suggestions")).json() == {"items": [SALMON]}


# Bring back removed suggestions: the count is what × leaves out of new suggestions right now
async def test_removed_count_includes_only_the_last_seven_days(client, db):
    await client.put("/shopping/suggestions", json={"items": [SALMON], "removed": ["Kiwi", "Strawberries"]})
    assert (await client.get("/shopping/suggestions/removed")).json() == {"count": 2}
    await db.execute("UPDATE shopping_suggestions SET removed_at = datetime('now', '-8 days') WHERE name = 'Strawberries'")
    await db.commit()
    assert (await client.get("/shopping/suggestions/removed")).json() == {"count": 1}


# Bringing them back deletes only this user's removed items, and keeps the list and the avoid list
async def test_bring_back_removed_keeps_the_list_and_other_users(client):
    await client.put("/preferences/avoid:Milk", json={"value": "Milk"})
    await client.put("/shopping/suggestions", json={"items": [SALMON, KIWI], "removed": ["Strawberries"]})
    other = await _second_user_auth()
    await client.put("/shopping/suggestions", json={"items": [], "removed": ["Strawberries"]}, headers=other)

    r = await client.delete("/shopping/suggestions/removed")
    assert r.status_code == 204
    assert (await client.get("/shopping/suggestions/removed")).json() == {"count": 0}
    assert (await client.get("/shopping/suggestions")).json() == {"items": [SALMON, KIWI]}
    assert (await client.get("/shopping/suggestions/removed", headers=other)).json() == {"count": 1}
    avoid = [p for p in (await client.get("/preferences/")).json() if p["key"] == "avoid:Milk"]
    assert [p["value"] for p in avoid] == ["Milk"]
