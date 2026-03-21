"""Integration tests for the /ratings endpoints."""

import pytest


async def test_list_empty_on_fresh_db(client):
    r = await client.get("/ratings/")
    assert r.status_code == 200
    assert r.json() == []


async def test_create_rating(client):
    r = await client.post("/ratings/", json={"product_name": "eggs", "rating": 8})
    assert r.status_code == 201
    data = r.json()
    assert data["product_name"] == "eggs"
    assert data["rating"] == 8
    assert "id" in data


async def test_create_rating_default_10(client):
    r = await client.post("/ratings/", json={"product_name": "milk"})
    assert r.status_code == 201
    assert r.json()["rating"] == 10


async def test_duplicate_product_returns_409(client):
    await client.post("/ratings/", json={"product_name": "cheese"})
    r = await client.post("/ratings/", json={"product_name": "cheese"})
    assert r.status_code == 409


async def test_update_rating(client):
    r = await client.post("/ratings/", json={"product_name": "yogurt", "rating": 5})
    rid = r.json()["id"]
    r2 = await client.put(f"/ratings/{rid}", json={"rating": 9})
    assert r2.status_code == 200
    assert r2.json()["rating"] == 9


async def test_update_nonexistent_returns_404(client):
    r = await client.put("/ratings/9999", json={"rating": 5})
    assert r.status_code == 404


async def test_delete_rating(client):
    r = await client.post("/ratings/", json={"product_name": "bread"})
    rid = r.json()["id"]
    r2 = await client.delete(f"/ratings/{rid}")
    assert r2.status_code == 204

    listed = await client.get("/ratings/")
    assert all(item["product_name"] != "bread" for item in listed.json())


async def test_rating_validation_min_max(client):
    r = await client.post("/ratings/", json={"product_name": "x", "rating": 0})
    assert r.status_code == 422

    r = await client.post("/ratings/", json={"product_name": "y", "rating": 11})
    assert r.status_code == 422


async def test_list_returns_all_ratings(client):
    await client.post("/ratings/", json={"product_name": "a", "rating": 3})
    await client.post("/ratings/", json={"product_name": "b", "rating": 7})
    await client.post("/ratings/", json={"product_name": "c", "rating": 10})

    r = await client.get("/ratings/")
    assert r.status_code == 200
    names = [item["product_name"] for item in r.json()]
    assert "a" in names
    assert "b" in names
    assert "c" in names
