"""Integration tests for the /shopping endpoints."""



async def test_list_empty_on_fresh_db(client):
    r = await client.get("/shopping/")
    assert r.status_code == 200
    assert r.json() == []


async def test_add_item(client):
    r = await client.post("/shopping/", json={"item_name": "eggs"})
    assert r.status_code == 201
    data = r.json()
    assert data["item_name"] == "eggs"
    assert "id" in data


async def test_add_duplicate_ignored(client):
    await client.post("/shopping/", json={"item_name": "milk"})
    r = await client.post("/shopping/", json={"item_name": "milk"})
    assert r.status_code == 201
    # Should still be only one item
    listed = (await client.get("/shopping/")).json()
    milks = [i for i in listed if i["item_name"] == "milk"]
    assert len(milks) == 1


async def test_delete_item(client):
    created = (await client.post("/shopping/", json={"item_name": "cheese"})).json()
    r = await client.delete(f"/shopping/{created['id']}")
    assert r.status_code == 204
    listed = (await client.get("/shopping/")).json()
    assert all(i["id"] != created["id"] for i in listed)


async def test_bulk_add(client):
    payload = [{"item_name": "tomato"}, {"item_name": "onion"}]
    r = await client.post("/shopping/bulk", json=payload)
    assert r.status_code == 201
    assert r.json() == {"added": 2}
    names = [i["item_name"] for i in (await client.get("/shopping/")).json()]
    assert "tomato" in names and "onion" in names


async def test_bulk_add_skips_duplicates(client):
    await client.post("/shopping/", json={"item_name": "butter"})
    payload = [{"item_name": "butter"}, {"item_name": "cream"}]
    r = await client.post("/shopping/bulk", json=payload)
    assert r.status_code == 201
    listed = (await client.get("/shopping/")).json()
    butters = [i for i in listed if i["item_name"] == "butter"]
    assert len(butters) == 1


async def test_bought_empty_ids(client):
    r = await client.post("/shopping/bought", json={"ids": []})
    assert r.status_code == 200
    assert r.json() == {"bought": 0}


async def test_bought_adds_to_ingredients_and_removes_from_list(client):
    # Add items to shopping list
    item1 = (await client.post("/shopping/", json={"item_name": "yogurt"})).json()
    item2 = (await client.post("/shopping/", json={"item_name": "bread"})).json()

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
    assert "yogurt" in names
    assert "bread" in names


async def test_bought_with_expiry_dates(client):
    item = (await client.post("/shopping/", json={"item_name": "milk"})).json()

    r = await client.post("/shopping/bought", json={
        "ids": [item["id"]],
        "expiry_dates": {"milk": "2026-04-15"},
    })
    assert r.status_code == 200

    # Check ingredient has the expiry date
    ingredients = (await client.get("/ingredients/")).json()
    milk = [i for i in ingredients if i["name"] == "milk"][0]
    assert milk["expiry_date"] == "2026-04-15"


async def test_bought_upserts_existing_ingredient(client):
    # Add an ingredient first
    await client.post("/ingredients/", json={"name": "eggs"})

    # Add same item to shopping list and buy it
    item = (await client.post("/shopping/", json={"item_name": "eggs"})).json()
    r = await client.post("/shopping/bought", json={
        "ids": [item["id"]],
        "expiry_dates": {"eggs": "2026-05-01"},
    })
    assert r.status_code == 200

    # Should still be one ingredient, with updated expiry
    ingredients = (await client.get("/ingredients/")).json()
    eggs_list = [i for i in ingredients if i["name"] == "eggs"]
    assert len(eggs_list) == 1
    assert eggs_list[0]["expiry_date"] == "2026-05-01"


async def test_bought_restores_group_from_memory(client):
    """Buying an item restores its group from memory if previously assigned."""
    # Add ingredient with explicit group, then delete it
    created = (await client.post("/ingredients/", json={"name": "kasar", "group_name": "🐄 Animal Products"})).json()
    await client.delete(f"/ingredients/{created['id']}")

    # Add to shopping list and buy
    item = (await client.post("/shopping/", json={"item_name": "kasar"})).json()
    await client.post("/shopping/bought", json={"ids": [item["id"]]})

    # Check ingredient has restored group
    ingredients = (await client.get("/ingredients/")).json()
    kasar = [i for i in ingredients if i["name"] == "kasar"][0]
    assert kasar["group_name"] == "🐄 Animal Products"


# ---------------------------------------------------------------------------
# Shopping suggestions list (/shopping/suggestions)
# ---------------------------------------------------------------------------

SALMON = {"name": "Salmon", "reason": "Omega-3", "checked": True}
KIWI = {"name": "Kiwi", "reason": "In season", "checked": False}


async def _second_user_auth():
    """Auth header for a second user in the same test database."""
    import aiosqlite
    import database
    from auth import hash_pin, create_token

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
