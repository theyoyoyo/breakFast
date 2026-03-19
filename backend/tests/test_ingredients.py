"""Integration tests for the /ingredients endpoints."""

import pytest


async def test_list_empty_on_fresh_db(client):
    r = await client.get("/ingredients/")
    assert r.status_code == 200
    assert r.json() == []


async def test_add_ingredient(client):
    r = await client.post("/ingredients/", json={"name": "eggs", "quantity": "6", "unit": "pcs"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "eggs"
    assert data["quantity"] == "6"
    assert data["unit"] == "pcs"
    assert "id" in data


async def test_add_same_name_upserts(client):
    await client.post("/ingredients/", json={"name": "milk", "quantity": "1", "unit": "L"})
    r = await client.post("/ingredients/", json={"name": "milk", "quantity": "2", "unit": "L"})
    assert r.status_code == 201
    # Should still be one record, with updated quantity
    listed = await client.get("/ingredients/")
    milks = [i for i in listed.json() if i["name"] == "milk"]
    assert len(milks) == 1
    assert milks[0]["quantity"] == "2"


async def test_update_ingredient_quantity(client):
    created = (await client.post("/ingredients/", json={"name": "butter", "quantity": "100", "unit": "g"})).json()
    r = await client.patch(f"/ingredients/{created['id']}", json={"quantity": "200"})
    assert r.status_code == 200
    assert r.json()["quantity"] == "200"


async def test_update_unknown_id_returns_404(client):
    r = await client.patch("/ingredients/9999", json={"quantity": "1"})
    assert r.status_code == 404


async def test_delete_ingredient(client):
    created = (await client.post("/ingredients/", json={"name": "cheese"})).json()
    r = await client.delete(f"/ingredients/{created['id']}")
    assert r.status_code == 204
    listed = (await client.get("/ingredients/")).json()
    assert all(i["id"] != created["id"] for i in listed)


async def test_bulk_add(client):
    payload = [
        {"name": "tomato", "quantity": "3", "unit": "pcs"},
        {"name": "onion", "quantity": "1", "unit": "pcs"},
    ]
    r = await client.post("/ingredients/bulk", json=payload)
    assert r.status_code == 201
    assert r.json() == {"added": 2}
    names = [i["name"] for i in (await client.get("/ingredients/")).json()]
    assert "tomato" in names and "onion" in names
