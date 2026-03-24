"""Tests for the /favorites endpoints."""

import pytest


SAMPLE_MEAL = {
    "meal_name": "Serpme Kahvaltı",
    "description": "Klasik Türk kahvaltısı",
    "ingredients": [
        {"name": "Beyaz peynir", "quantity": 50, "unit": "g"},
        {"name": "Zeytin", "quantity": 6, "unit": "adet"},
    ],
    "steps": ["Peyniri tabağa koy", "Zeytini ekle"],
    "prep_time_min": 5,
    "nutrition_note": "Protein açısından zengin",
}


@pytest.mark.asyncio
async def test_list_empty(client):
    """Empty favorites list returns 200 with empty array."""
    r = await client.get("/favorites/")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_add_and_list(client):
    """Adding a favorite returns its id and it appears in the list."""
    r = await client.post("/favorites/", json=SAMPLE_MEAL)
    assert r.status_code == 201
    fav_id = r.json()["id"]
    assert fav_id > 0

    r = await client.get("/favorites/")
    favs = r.json()
    assert len(favs) == 1
    assert favs[0]["meal_name"] == "Serpme Kahvaltı"
    assert favs[0]["id"] == fav_id
    assert isinstance(favs[0]["ingredients"], list)
    assert len(favs[0]["ingredients"]) == 2


@pytest.mark.asyncio
async def test_delete(client):
    """Deleting a favorite removes it from the list."""
    r = await client.post("/favorites/", json=SAMPLE_MEAL)
    fav_id = r.json()["id"]

    r = await client.delete(f"/favorites/{fav_id}")
    assert r.status_code == 200

    r = await client.get("/favorites/")
    assert r.json() == []


@pytest.mark.asyncio
async def test_delete_not_found(client):
    """Deleting a non-existent favorite returns 404."""
    r = await client.delete("/favorites/9999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update(client):
    """Updating a favorite changes its data."""
    r = await client.post("/favorites/", json=SAMPLE_MEAL)
    fav_id = r.json()["id"]

    updated = {**SAMPLE_MEAL, "meal_name": "Updated Kahvaltı", "prep_time_min": 20}
    r = await client.put(f"/favorites/{fav_id}", json=updated)
    assert r.status_code == 200

    r = await client.get("/favorites/")
    fav = r.json()[0]
    assert fav["meal_name"] == "Updated Kahvaltı"
    assert fav["prep_time_min"] == 20


@pytest.mark.asyncio
async def test_update_not_found(client):
    """Updating a non-existent favorite returns 404."""
    r = await client.put("/favorites/9999", json=SAMPLE_MEAL)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_multiple_same_name(client):
    """Same meal name can be favorited multiple times with different ingredients."""
    meal2 = {**SAMPLE_MEAL, "ingredients": [{"name": "Yumurta", "quantity": 2, "unit": "adet"}]}
    await client.post("/favorites/", json=SAMPLE_MEAL)
    await client.post("/favorites/", json=meal2)

    r = await client.get("/favorites/")
    favs = r.json()
    assert len(favs) == 2
    # Both have the same name but different ingredients
    names = [f["meal_name"] for f in favs]
    assert names == ["Serpme Kahvaltı", "Serpme Kahvaltı"]
