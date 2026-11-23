"""Tests for the favorite ingredients API endpoints."""



async def test_list_empty(client):
    """Empty favorites returns empty list."""
    r = await client.get("/favorite-ingredients/")
    assert r.status_code == 200
    assert r.json() == []


async def test_add_and_list(client):
    """Add a favorite then list it."""
    r = await client.post("/favorite-ingredients/", json={"ingredient_name": "Ceviz"})
    assert r.status_code == 201
    data = r.json()
    assert data["ingredient_name"] == "Ceviz"

    r2 = await client.get("/favorite-ingredients/")
    assert len(r2.json()) == 1
    assert r2.json()[0]["ingredient_name"] == "Ceviz"


async def test_duplicate_returns_409(client):
    """Adding the same ingredient twice returns 409."""
    await client.post("/favorite-ingredients/", json={"ingredient_name": "Bal"})
    r = await client.post("/favorite-ingredients/", json={"ingredient_name": "Bal"})
    assert r.status_code == 409


async def test_remove(client):
    """Remove a favorited ingredient."""
    await client.post("/favorite-ingredients/", json={"ingredient_name": "Tahin"})
    r = await client.delete("/favorite-ingredients/Tahin")
    assert r.status_code == 200

    r2 = await client.get("/favorite-ingredients/")
    assert len(r2.json()) == 0


async def test_remove_not_found(client):
    """Removing a non-existent favorite returns 404."""
    r = await client.delete("/favorite-ingredients/NonExistent")
    assert r.status_code == 404
