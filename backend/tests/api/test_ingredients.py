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


async def test_expired_second_call_same_day_returns_empty(client):
    """Calling expired twice on the same day returns empty on second call."""
    await client.post("/ingredients/", json={"name": "old_milk", "expiry_date": "2020-01-01"})
    r1 = await client.get("/ingredients/expired")
    assert len(r1.json()) > 0
    # Second call same day → empty
    r2 = await client.get("/ingredients/expired")
    assert r2.json() == []


async def test_expired_new_day_returns_newly_expired(client):
    """On a new day, only items expired after last check are returned."""
    await client.post("/ingredients/", json={"name": "item_a", "expiry_date": "2026-03-23"})

    # First check with mocked date 2026-03-23
    with patch("routers.ingredients.date") as mock_date:
        mock_date.today.return_value.isoformat.return_value = "2026-03-23"
        r1 = await client.get("/ingredients/expired")
        assert len(r1.json()) > 0

    # Add another item expiring 2026-03-24
    await client.post("/ingredients/", json={"name": "item_b", "expiry_date": "2026-03-24"})

    # Second check with mocked date 2026-03-24
    with patch("routers.ingredients.date") as mock_date:
        mock_date.today.return_value.isoformat.return_value = "2026-03-24"
        r2 = await client.get("/ingredients/expired")
        names = [i["name"] for i in r2.json()]
        assert "item_b" in names
        # item_a was already reported, should not reappear
        assert "item_a" not in names


# ---------------------------------------------------------------------------
# Thrown confirmation tests
# ---------------------------------------------------------------------------


async def test_thrown_removes_ingredients(client):
    """Confirming thrown removes expired items from inventory."""
    created = (await client.post("/ingredients/", json={"name": "expired_cheese", "expiry_date": "2020-01-01"})).json()
    r = await client.post("/ingredients/expired/thrown", json={"ids": [created["id"]]})
    assert r.status_code == 200
    assert r.json() == {"removed": 1}
    # Verify it's gone
    listed = (await client.get("/ingredients/")).json()
    assert all(i["name"] != "expired_cheese" for i in listed)


async def test_thrown_empty_list(client):
    """Thrown with empty list is a no-op."""
    r = await client.post("/ingredients/expired/thrown", json={"ids": []})
    assert r.status_code == 200
    assert r.json() == {"removed": 0}
