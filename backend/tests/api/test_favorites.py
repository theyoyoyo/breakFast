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
    """Deleting a non-existent favorite returns 404 and deletes nothing."""
    await client.post("/favorites/", json=SAMPLE_MEAL)
    before = (await client.get("/favorites/")).json()
    r = await client.delete("/favorites/9999")
    assert r.status_code == 404
    assert (await client.get("/favorites/")).json() == before


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
    """Updating a non-existent favorite returns 404, saves nothing and changes no other favorite."""
    await client.post("/favorites/", json=SAMPLE_MEAL)
    before = (await client.get("/favorites/")).json()
    r = await client.put("/favorites/9999", json={**SAMPLE_MEAL, "meal_name": "Another name"})
    assert r.status_code == 404
    assert (await client.get("/favorites/")).json() == before


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


# A second favorite with a name already taken (any case, extra spaces) is refused, whatever its food
@pytest.mark.asyncio
async def test_same_name_refused(client):
    meal2 = {**SAMPLE_MEAL, "meal_name": "  SERPME kahvaltı ", "ingredients": [{"name": "Yumurta", "quantity": 2, "unit": "adet"}]}
    assert (await client.post("/favorites/", json=SAMPLE_MEAL)).status_code == 201
    r = await client.post("/favorites/", json=meal2)
    assert r.status_code == 409
    favs = (await client.get("/favorites/")).json()
    assert [f["meal_name"] for f in favs] == ["Serpme Kahvaltı"]


# Names are unique per user: another user may save a favorite with the same name
@pytest.mark.asyncio
async def test_other_user_can_use_name(client):
    await client.post("/favorites/", json=SAMPLE_MEAL)
    r = await client.post("/favorites/", json=SAMPLE_MEAL, headers=await _second_user_auth())
    assert r.status_code == 201


# A rename to another favorite's name is refused and leaves the favorite as it was
@pytest.mark.asyncio
async def test_rename_to_taken_name_refused(client):
    await client.post("/favorites/", json=SAMPLE_MEAL)
    other_id = (await client.post("/favorites/", json={**SAMPLE_MEAL, "meal_name": "Omlet"})).json()["id"]
    r = await client.put(f"/favorites/{other_id}", json={**SAMPLE_MEAL, "meal_name": "serpme kahvaltı"})
    assert r.status_code == 409
    favs = {f["id"]: f["meal_name"] for f in (await client.get("/favorites/")).json()}
    assert favs[other_id] == "Omlet"


# Favorites that shared a name before the rule can still be edited when they keep their name
@pytest.mark.asyncio
async def test_old_duplicates_keep_their_name(client, db):
    for _ in range(2):
        await db.execute(
            "INSERT INTO favorite_meals (user_id, meal_name, ingredients, steps) VALUES (1, 'Serpme Kahvaltı', '[]', '[]')"
        )
    await db.commit()
    fav_id = (await client.get("/favorites/")).json()[0]["id"]
    r = await client.put(f"/favorites/{fav_id}", json={**SAMPLE_MEAL, "prep_time_min": 12})
    assert r.status_code == 200


# A favorite saved with an icon keeps it, and one saved without gets none (the app shows one from its id)
@pytest.mark.asyncio
async def test_favorite_keeps_its_emoji(client):
    await client.post("/favorites/", json={**SAMPLE_MEAL, "emoji": "🥐"})
    await client.post("/favorites/", json={**SAMPLE_MEAL, "meal_name": "Omlet", "emoji": "  "})
    favs = {f["meal_name"]: f["emoji"] for f in (await client.get("/favorites/")).json()}
    assert favs == {"Serpme Kahvaltı": "🥐", "Omlet": None}


# An edit changes the icon when it sends one, and a rename sent without one keeps the saved icon
@pytest.mark.asyncio
async def test_update_changes_or_keeps_emoji(client):
    fav_id = (await client.post("/favorites/", json={**SAMPLE_MEAL, "emoji": "🥐"})).json()["id"]

    assert (await client.put(f"/favorites/{fav_id}", json={**SAMPLE_MEAL, "emoji": "🧇"})).status_code == 200
    assert (await client.get("/favorites/")).json()[0]["emoji"] == "🧇"

    assert (await client.put(f"/favorites/{fav_id}", json={**SAMPLE_MEAL, "meal_name": "Brunch"})).status_code == 200
    fav = (await client.get("/favorites/")).json()[0]
    assert (fav["meal_name"], fav["emoji"]) == ("Brunch", "🧇")


# An icon longer than one emoji is refused with 422
@pytest.mark.asyncio
async def test_long_emoji_refused(client):
    r = await client.post("/favorites/", json={**SAMPLE_MEAL, "emoji": "🥐" * 20})
    assert r.status_code == 422
