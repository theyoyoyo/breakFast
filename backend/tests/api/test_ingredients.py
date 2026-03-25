"""Integration tests for the /ingredients endpoints."""

import pytest
from unittest.mock import patch


async def test_list_empty_on_fresh_db(client):
    r = await client.get("/ingredients/")
    assert r.status_code == 200
    assert r.json() == []


async def test_add_ingredient(client):
    r = await client.post("/ingredients/", json={"name": "eggs"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "eggs"
    assert data["expiry_date"] is None
    assert "id" in data


async def test_add_ingredient_with_expiry(client):
    r = await client.post("/ingredients/", json={"name": "yogurt", "expiry_date": "2026-04-01"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "yogurt"
    assert data["expiry_date"] == "2026-04-01"


async def test_add_same_name_upserts(client):
    await client.post("/ingredients/", json={"name": "milk"})
    r = await client.post("/ingredients/", json={"name": "milk", "expiry_date": "2026-04-05"})
    assert r.status_code == 201
    # Should still be one record, with updated expiry
    listed = await client.get("/ingredients/")
    milks = [i for i in listed.json() if i["name"] == "milk"]
    assert len(milks) == 1
    assert milks[0]["expiry_date"] == "2026-04-05"


async def test_delete_ingredient(client):
    created = (await client.post("/ingredients/", json={"name": "cheese"})).json()
    r = await client.delete(f"/ingredients/{created['id']}")
    assert r.status_code == 204
    listed = (await client.get("/ingredients/")).json()
    assert all(i["id"] != created["id"] for i in listed)


async def test_bulk_add(client):
    payload = [
        {"name": "tomato"},
        {"name": "onion"},
    ]
    r = await client.post("/ingredients/bulk", json=payload)
    assert r.status_code == 201
    assert r.json() == {"added": 2}
    names = [i["name"] for i in (await client.get("/ingredients/")).json()]
    assert "tomato" in names and "onion" in names


async def test_bulk_add_with_expiry(client):
    payload = [
        {"name": "butter", "expiry_date": "2026-05-01"},
        {"name": "cream"},
    ]
    r = await client.post("/ingredients/bulk", json=payload)
    assert r.status_code == 201
    listed = (await client.get("/ingredients/")).json()
    butter = [i for i in listed if i["name"] == "butter"][0]
    cream = [i for i in listed if i["name"] == "cream"][0]
    assert butter["expiry_date"] == "2026-05-01"
    assert cream["expiry_date"] is None


# ---------------------------------------------------------------------------
# Expiry check tests
# ---------------------------------------------------------------------------


async def test_expired_returns_empty_when_no_expiry(client):
    """No ingredients with expiry → empty result."""
    await client.post("/ingredients/", json={"name": "salt"})
    r = await client.get("/ingredients/expired")
    assert r.status_code == 200
    assert r.json() == []


async def test_expired_returns_expired_items(client):
    """Items with expiry_date in the past should be returned."""
    await client.post("/ingredients/", json={"name": "old_yogurt", "expiry_date": "2020-01-01"})
    await client.post("/ingredients/", json={"name": "fresh_eggs"})
    r = await client.get("/ingredients/expired")
    assert r.status_code == 200
    expired = r.json()
    names = [i["name"] for i in expired]
    assert "old_yogurt" in names
    assert "fresh_eggs" not in names


async def test_expired_always_returns_unacknowledged(client):
    """Calling expired multiple times still returns the same unacknowledged items."""
    await client.post("/ingredients/", json={"name": "old_milk", "expiry_date": "2020-01-01"})
    r1 = await client.get("/ingredients/expired")
    assert len(r1.json()) > 0
    # Second call returns the same items (no longer gated per day)
    r2 = await client.get("/ingredients/expired")
    assert len(r2.json()) > 0
    assert r2.json()[0]["name"] == "old_milk"


async def test_expired_count_endpoint(client):
    """expired-count returns current count of expired unacknowledged items."""
    r = await client.get("/ingredients/expired-count")
    assert r.json() == {"count": 0}

    await client.post("/ingredients/", json={"name": "old_item", "expiry_date": "2020-01-01"})
    r = await client.get("/ingredients/expired-count")
    assert r.json() == {"count": 1}

    # Non-expired item doesn't affect count
    await client.post("/ingredients/", json={"name": "fresh_item", "expiry_date": "2030-01-01"})
    r = await client.get("/ingredients/expired-count")
    assert r.json() == {"count": 1}


# ---------------------------------------------------------------------------
# Expired action tests (3-way: delete, keep, shopping)
# ---------------------------------------------------------------------------


async def test_expired_action_delete(client):
    """Delete action removes ingredients from inventory."""
    created = (await client.post("/ingredients/", json={"name": "expired_cheese", "expiry_date": "2020-01-01"})).json()
    r = await client.post("/ingredients/expired/action", json={"delete_ids": [created["id"]]})
    assert r.status_code == 200
    assert r.json()["deleted"] == 1
    listed = (await client.get("/ingredients/")).json()
    assert all(i["name"] != "expired_cheese" for i in listed)


async def test_expired_action_keep(client):
    """Keep action acknowledges expiry — item stays in inventory but disappears from expired list."""
    created = (await client.post("/ingredients/", json={"name": "old_honey", "expiry_date": "2020-01-01"})).json()

    # Should appear in expired list
    expired = (await client.get("/ingredients/expired")).json()
    assert any(i["name"] == "old_honey" for i in expired)

    # Keep it
    r = await client.post("/ingredients/expired/action", json={"keep_ids": [created["id"]]})
    assert r.json()["kept"] == 1

    # Should NOT appear in expired list anymore
    expired = (await client.get("/ingredients/expired")).json()
    assert all(i["name"] != "old_honey" for i in expired)

    # But should still be in inventory
    listed = (await client.get("/ingredients/")).json()
    assert any(i["name"] == "old_honey" for i in listed)

    # Count should also be 0
    r = await client.get("/ingredients/expired-count")
    assert r.json() == {"count": 0}


async def test_expired_action_shopping(client):
    """Shopping action removes from inventory and adds to shopping list."""
    created = (await client.post("/ingredients/", json={"name": "expired_milk", "expiry_date": "2020-01-01"})).json()
    r = await client.post("/ingredients/expired/action", json={"shopping_ids": [created["id"]]})
    assert r.json()["to_shopping"] == 1

    # Should be gone from inventory
    listed = (await client.get("/ingredients/")).json()
    assert all(i["name"] != "expired_milk" for i in listed)

    # Should be in shopping list
    shopping = (await client.get("/shopping/")).json()
    assert any(i["item_name"] == "expired_milk" for i in shopping)


async def test_expired_action_mixed(client):
    """All three actions work together."""
    a = (await client.post("/ingredients/", json={"name": "item_del", "expiry_date": "2020-01-01"})).json()
    b = (await client.post("/ingredients/", json={"name": "item_keep", "expiry_date": "2020-01-01"})).json()
    c = (await client.post("/ingredients/", json={"name": "item_shop", "expiry_date": "2020-01-01"})).json()

    r = await client.post("/ingredients/expired/action", json={
        "delete_ids": [a["id"]],
        "keep_ids": [b["id"]],
        "shopping_ids": [c["id"]],
    })
    assert r.json() == {"deleted": 1, "kept": 1, "to_shopping": 1}


# ---------------------------------------------------------------------------
# Legacy thrown confirmation tests (backward compat)
# ---------------------------------------------------------------------------


async def test_thrown_removes_ingredients(client):
    """Confirming thrown removes expired items from inventory."""
    created = (await client.post("/ingredients/", json={"name": "expired_cheese", "expiry_date": "2020-01-01"})).json()
    r = await client.post("/ingredients/expired/thrown", json={"ids": [created["id"]]})
    assert r.status_code == 200
    assert r.json() == {"removed": 1}
    listed = (await client.get("/ingredients/")).json()
    assert all(i["name"] != "expired_cheese" for i in listed)


async def test_thrown_empty_list(client):
    """Thrown with empty list is a no-op."""
    r = await client.post("/ingredients/expired/thrown", json={"ids": []})
    assert r.status_code == 200
    assert r.json() == {"removed": 0}


# ---------------------------------------------------------------------------
# Ingredient groups tests
# ---------------------------------------------------------------------------


async def test_add_ingredient_default_group(client):
    """Adding without group_name defaults to Diğer."""
    r = await client.post("/ingredients/", json={"name": "salt"})
    assert r.status_code == 201
    assert r.json()["group_name"] == "🍽️ Diğer"


async def test_add_ingredient_with_group(client):
    """Adding with explicit group assigns it correctly."""
    r = await client.post("/ingredients/", json={"name": "sucuk", "group_name": "🐄 Hayvansal"})
    assert r.status_code == 201
    assert r.json()["group_name"] == "🐄 Hayvansal"


async def test_update_ingredient_group(client):
    """PATCH can change an ingredient's group."""
    created = (await client.post("/ingredients/", json={"name": "kekik"})).json()
    assert created["group_name"] == "🍽️ Diğer"
    r = await client.patch(f"/ingredients/{created['id']}", json={"group_name": "🧂 Baharatlar"})
    assert r.status_code == 200
    assert r.json()["group_name"] == "🧂 Baharatlar"


async def test_invalid_group_rejected(client):
    """Unknown group names return 400."""
    r = await client.post("/ingredients/", json={"name": "water", "group_name": "InvalidGroup"})
    assert r.status_code == 400


async def test_group_memory_on_readd(client):
    """Deleting and re-adding an ingredient restores its remembered group."""
    created = (await client.post("/ingredients/", json={"name": "domates", "group_name": "🥬 Sebze Meyve"})).json()
    await client.delete(f"/ingredients/{created['id']}")
    # Re-add without specifying group — should restore from memory
    r = await client.post("/ingredients/", json={"name": "domates"})
    assert r.status_code == 201
    assert r.json()["group_name"] == "🥬 Sebze Meyve"


async def test_bulk_add_with_group_memory(client):
    """Bulk add restores group from memory for previously assigned items."""
    # First, add with explicit group and delete
    created = (await client.post("/ingredients/", json={"name": "biber", "group_name": "🥬 Sebze Meyve"})).json()
    await client.delete(f"/ingredients/{created['id']}")
    # Bulk add without group — should restore from memory
    r = await client.post("/ingredients/bulk", json=[{"name": "biber"}, {"name": "tuz"}])
    assert r.status_code == 201
    listed = (await client.get("/ingredients/")).json()
    biber = [i for i in listed if i["name"] == "biber"][0]
    tuz = [i for i in listed if i["name"] == "tuz"][0]
    assert biber["group_name"] == "🥬 Sebze Meyve"
    assert tuz["group_name"] == "🍽️ Diğer"


async def test_groups_endpoint(client):
    """GET /ingredients/groups returns the fixed group list."""
    r = await client.get("/ingredients/groups")
    assert r.status_code == 200
    data = r.json()
    assert "🐄 Hayvansal" in data["groups"]
    assert "🍽️ Diğer" in data["groups"]
    assert data["default"] == "🍽️ Diğer"
    assert len(data["groups"]) == 10
