"""Integration tests for the /shopping endpoints."""

import pytest


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
    created = (await client.post("/ingredients/", json={"name": "kaşar", "group_name": "🐄 Hayvansal"})).json()
    await client.delete(f"/ingredients/{created['id']}")

    # Add to shopping list and buy
    item = (await client.post("/shopping/", json={"item_name": "kaşar"})).json()
    await client.post("/shopping/bought", json={"ids": [item["id"]]})

    # Check ingredient has restored group
    ingredients = (await client.get("/ingredients/")).json()
    kasar = [i for i in ingredients if i["name"] == "kaşar"][0]
    assert kasar["group_name"] == "🐄 Hayvansal"
