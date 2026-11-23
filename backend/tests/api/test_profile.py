"""Integration tests for the /profile endpoints (profile + supplements + daily toggle)."""

import pytest

# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------

# A new user has no profile yet, so the endpoint returns null
async def test_get_profile_returns_none_initially(client):
    r = await client.get("/profile/")
    assert r.status_code == 200
    assert r.json() is None


# The first save creates the profile with every field given
async def test_upsert_profile_creates(client):
    body = {"age": 30, "gender": "male", "height_cm": 180, "weight_kg": 80.5, "activity_level": "moderate"}
    r = await client.put("/profile/", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["age"] == 30
    assert data["gender"] == "male"
    assert data["height_cm"] == 180
    assert data["weight_kg"] == 80.5
    assert data["activity_level"] == "moderate"


# A second save updates the existing profile
async def test_upsert_profile_updates(client):
    await client.put("/profile/", json={"age": 25, "gender": "female"})
    r = await client.put("/profile/", json={"age": 26, "gender": "female", "height_cm": 165})
    assert r.status_code == 200
    data = r.json()
    assert data["age"] == 26
    assert data["height_cm"] == 165


# The saved profile is what a later read returns
async def test_get_profile_returns_saved(client):
    await client.put("/profile/", json={"age": 40, "weight_kg": 75})
    r = await client.get("/profile/")
    assert r.status_code == 200
    data = r.json()
    assert data["age"] == 40
    assert data["weight_kg"] == 75


# A save with only some fields leaves the others empty
async def test_upsert_profile_partial_fields(client):
    r = await client.put("/profile/", json={"age": 28})
    assert r.status_code == 200
    data = r.json()
    assert data["age"] == 28
    assert data["gender"] is None
    assert data["height_cm"] is None


# An age, height or weight of zero or below is refused with 422, and the saved profile stays as it was
@pytest.mark.parametrize("body", [
    {"age": -5},
    {"age": 0},
    {"height_cm": -170},
    {"weight_kg": -80},
    {"weight_kg": 0},
])
async def test_impossible_profile_values_rejected(client, body):
    saved = (await client.put("/profile/", json={"age": 30, "height_cm": 180, "weight_kg": 75})).json()
    r = await client.put("/profile/", json=body)
    assert r.status_code == 422
    assert (await client.get("/profile/")).json() == saved


async def test_clear_individual_field(client):
    """Setting a field to null should clear it while keeping others."""
    await client.put("/profile/", json={"age": 30, "height_cm": 180, "weight_kg": 75})
    r = await client.put("/profile/", json={"age": 30, "height_cm": None, "weight_kg": 75})
    assert r.status_code == 200
    data = r.json()
    assert data["age"] == 30
    assert data["height_cm"] is None
    assert data["weight_kg"] == 75


async def test_country_saved_and_cleared(client):
    """The optional country is saved with the profile; a blank value clears it."""
    r = await client.put("/profile/", json={"age": 30, "country": " Türkiye "})
    assert r.json()["country"] == "Türkiye"
    r = await client.put("/profile/", json={"age": 30, "country": ""})
    assert r.json()["country"] is None


async def test_country_too_long_rejected(client):
    """A country name over 60 characters is rejected."""
    r = await client.put("/profile/", json={"country": "x" * 61})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Supplements CRUD
# ---------------------------------------------------------------------------

# A new user has no supplements
async def test_list_supplements_empty(client):
    r = await client.get("/profile/supplements")
    assert r.status_code == 200
    assert r.json() == []


# A new supplement is saved with its name, contents, frequency and an id
async def test_create_supplement(client):
    r = await client.post("/profile/supplements", json={"name": "Vitamin D", "contents": "1000 IU", "frequency": "daily"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Vitamin D"
    assert data["contents"] == "1000 IU"
    assert data["frequency"] == "daily"
    assert "id" in data


# A supplement given only a name gets empty contents and a daily frequency
async def test_create_supplement_defaults(client):
    r = await client.post("/profile/supplements", json={"name": "Omega-3"})
    assert r.status_code == 201
    data = r.json()
    assert data["contents"] == ""
    assert data["frequency"] == "daily"


# A second supplement with the same name is refused with 409
async def test_duplicate_supplement_returns_409(client):
    await client.post("/profile/supplements", json={"name": "Zinc"})
    r = await client.post("/profile/supplements", json={"name": "Zinc"})
    assert r.status_code == 409


# A frequency outside the allowed values is refused with 422
async def test_invalid_frequency_returns_422(client):
    r = await client.post("/profile/supplements", json={"name": "X", "frequency": "weekly"})
    assert r.status_code == 422


# An edit changes a supplement's name and frequency
async def test_update_supplement(client):
    r = await client.post("/profile/supplements", json={"name": "Magnesium", "frequency": "daily"})
    sid = r.json()["id"]
    r2 = await client.put(f"/profile/supplements/{sid}", json={"name": "Magnesium Citrate", "contents": "400mg", "frequency": "sometimes"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "Magnesium Citrate"
    assert r2.json()["frequency"] == "sometimes"


# Renaming a supplement to another one's name is refused like adding a duplicate
async def test_rename_to_existing_supplement_returns_409(client):
    await client.post("/profile/supplements", json={"name": "Zinc"})
    sid = (await client.post("/profile/supplements", json={"name": "Iron"})).json()["id"]
    r = await client.put(f"/profile/supplements/{sid}", json={"name": "Zinc", "contents": "", "frequency": "daily"})
    assert r.status_code == 409


# Editing a supplement that doesn't exist gets 404
async def test_update_nonexistent_returns_404(client):
    r = await client.put("/profile/supplements/9999", json={"name": "X", "contents": "", "frequency": "daily"})
    assert r.status_code == 404


# A deleted supplement is gone from the list
async def test_delete_supplement(client):
    r = await client.post("/profile/supplements", json={"name": "Iron"})
    sid = r.json()["id"]
    r2 = await client.delete(f"/profile/supplements/{sid}")
    assert r2.status_code == 204

    listed = await client.get("/profile/supplements")
    assert all(s["name"] != "Iron" for s in listed.json())


# Supplements are listed in name order
async def test_list_supplements_ordered_by_name(client):
    await client.post("/profile/supplements", json={"name": "Zinc"})
    await client.post("/profile/supplements", json={"name": "Biotin"})
    await client.post("/profile/supplements", json={"name": "Omega-3"})
    r = await client.get("/profile/supplements")
    names = [s["name"] for s in r.json()]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# Daily toggle
# ---------------------------------------------------------------------------

# Today's list shows a supplement as not taken until it is marked taken
async def test_today_supplements_with_taken_status(client):
    r = await client.post("/profile/supplements", json={"name": "Vitamin C", "frequency": "sometimes"})
    sid = r.json()["id"]

    # Initially not taken
    r2 = await client.get("/profile/supplements/today")
    supps = r2.json()
    vitc = next(s for s in supps if s["name"] == "Vitamin C")
    assert vitc["taken_today"] == 0

    # Toggle on
    await client.post(f"/profile/supplements/{sid}/toggle", json={"taken": True})
    r3 = await client.get("/profile/supplements/today")
    vitc = next(s for s in r3.json() if s["name"] == "Vitamin C")
    assert vitc["taken_today"] == 1

    # Toggle off
    await client.post(f"/profile/supplements/{sid}/toggle", json={"taken": False})
    r4 = await client.get("/profile/supplements/today")
    vitc = next(s for s in r4.json() if s["name"] == "Vitamin C")
    assert vitc["taken_today"] == 0


# Marking a pill taken twice is not an error and leaves it taken
async def test_toggle_idempotent(client):
    r = await client.post("/profile/supplements", json={"name": "B12", "frequency": "sometimes"})
    sid = r.json()["id"]

    # Toggle on twice — should not error
    await client.post(f"/profile/supplements/{sid}/toggle", json={"taken": True})
    r2 = await client.post(f"/profile/supplements/{sid}/toggle", json={"taken": True})
    assert r2.status_code == 200
    assert r2.json()["taken"] is True


# A supplement marked taken today and then deleted is gone from today's list
async def test_delete_supplement_also_deletes_log(client):
    r = await client.post("/profile/supplements", json={"name": "Probiotic", "frequency": "sometimes"})
    sid = r.json()["id"]

    # Toggle on so a log entry exists
    await client.post(f"/profile/supplements/{sid}/toggle", json={"taken": True})

    # Delete supplement
    await client.delete(f"/profile/supplements/{sid}")

    # Today list should not include deleted supplement
    r2 = await client.get("/profile/supplements/today")
    assert all(s["name"] != "Probiotic" for s in r2.json())


# A toggle for another user's supplement or one that doesn't exist gets 404 and logs nothing
@pytest.mark.parametrize("whose", ["bob", "made-up"])
async def test_toggle_supplement_not_own_gets_404(client, db, whose):
    await db.execute("INSERT INTO users (name, pin_hash) VALUES ('Bob', 'unused')")
    cur = await db.execute(
        "INSERT INTO user_supplements (user_id, name) SELECT id, 'Iron' FROM users WHERE name = 'Bob'"
    )
    await db.commit()
    supp_id = cur.lastrowid if whose == "bob" else 9999

    for taken in (True, False):
        r = await client.post(f"/profile/supplements/{supp_id}/toggle", json={"taken": taken})
        assert r.status_code == 404

    async with db.execute("SELECT COUNT(*) FROM supplement_daily_log") as cur:
        assert (await cur.fetchone())[0] == 0


# A daily supplement starts as taken, can be skipped for today, and a mark back removes the stored row
async def test_daily_supplement_can_be_skipped_today(client, db):
    r = await client.post("/profile/supplements", json={"name": "Vitamin D", "frequency": "daily"})
    sid = r.json()["id"]

    async def state():
        r = await client.get("/profile/supplements/today")
        return next(s for s in r.json() if s["id"] == sid)["taken_today"]

    assert await state() == 1
    await client.post(f"/profile/supplements/{sid}/toggle", json={"taken": False})
    assert await state() == 0
    await client.post(f"/profile/supplements/{sid}/toggle", json={"taken": True})
    assert await state() == 1
    async with db.execute("SELECT COUNT(*) FROM supplement_daily_log") as cur:
        assert (await cur.fetchone())[0] == 0
