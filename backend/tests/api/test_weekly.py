"""Tests for the /meals/weekly endpoint — consecutive-day meal summary."""

import pytest


SAMPLE_MEAL = {
    "meal_name": "Toast",
    "ingredients": [{"name": "ekmek", "quantity": 2, "unit": "dilim"}],
}


# Returns empty list when no meals exist
@pytest.mark.asyncio
async def test_weekly_empty(client):
    r = await client.get("/meals/weekly")
    assert r.status_code == 200
    assert r.json() == []


# Returns a single meal when only one exists
@pytest.mark.asyncio
async def test_weekly_single_meal(client):
    await client.post("/meals/", json=SAMPLE_MEAL)
    r = await client.get("/meals/weekly")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["meal_name"] == "Toast"


# Returns meals from consecutive days, stops at gap
@pytest.mark.asyncio
async def test_weekly_stops_at_gap(client, db):
    # Create 3 meals on consecutive days, then a gap, then another meal
    m1 = (await client.post("/meals/", json={**SAMPLE_MEAL, "meal_name": "Day1"})).json()
    m2 = (await client.post("/meals/", json={**SAMPLE_MEAL, "meal_name": "Day2"})).json()
    m3 = (await client.post("/meals/", json={**SAMPLE_MEAL, "meal_name": "Day3"})).json()
    m4 = (await client.post("/meals/", json={**SAMPLE_MEAL, "meal_name": "Day5"})).json()

    # Set dates: m4=today, m3=yesterday, m2=2 days ago (gap), m1=4 days ago
    await db.execute(
        "UPDATE meal_history SET logged_at = datetime('now') WHERE id = ?", (m4["id"],)
    )
    await db.execute(
        "UPDATE meal_history SET logged_at = datetime('now', '-1 day') WHERE id = ?", (m3["id"],)
    )
    await db.execute(
        "UPDATE meal_history SET logged_at = datetime('now', '-3 days') WHERE id = ?", (m2["id"],)
    )
    await db.execute(
        "UPDATE meal_history SET logged_at = datetime('now', '-4 days') WHERE id = ?", (m1["id"],)
    )
    await db.commit()

    r = await client.get("/meals/weekly")
    data = r.json()
    # Should only return m4 and m3 (consecutive), then stop at the gap before m2
    assert len(data) == 2
    assert data[0]["meal_name"] == "Day5"
    assert data[1]["meal_name"] == "Day3"


# Multiple meals on the same day are all included
@pytest.mark.asyncio
async def test_weekly_multiple_same_day(client, db):
    m1 = (await client.post("/meals/", json={**SAMPLE_MEAL, "meal_name": "Morning"})).json()
    m2 = (await client.post("/meals/", json={**SAMPLE_MEAL, "meal_name": "Brunch"})).json()

    # Both on today
    await db.execute(
        "UPDATE meal_history SET logged_at = datetime('now') WHERE id = ?", (m1["id"],)
    )
    await db.execute(
        "UPDATE meal_history SET logged_at = datetime('now', '+1 hour') WHERE id = ?", (m2["id"],)
    )
    await db.commit()

    r = await client.get("/meals/weekly")
    data = r.json()
    assert len(data) == 2


# Max 7 meals returned even with more consecutive days
@pytest.mark.asyncio
async def test_weekly_max_seven(client, db):
    ids = []
    for i in range(10):
        m = (await client.post("/meals/", json={**SAMPLE_MEAL, "meal_name": f"Day{i}"})).json()
        ids.append(m["id"])

    # Set consecutive dates
    for i, mid in enumerate(ids):
        await db.execute(
            "UPDATE meal_history SET logged_at = datetime('now', ? || ' days') WHERE id = ?",
            (str(-i), mid),
        )
    await db.commit()

    r = await client.get("/meals/weekly")
    data = r.json()
    assert len(data) == 7


# Includes cached_nutrition field when present
@pytest.mark.asyncio
async def test_weekly_includes_cached_nutrition(client, db):
    m = (await client.post("/meals/", json=SAMPLE_MEAL)).json()
    await db.execute(
        "UPDATE meal_history SET cached_nutrition = ? WHERE id = ?",
        ('{"analysis_text": "test", "analysis_data": {}}', m["id"]),
    )
    await db.commit()

    r = await client.get("/meals/weekly")
    data = r.json()
    assert len(data) == 1
    assert data[0]["cached_nutrition"] is not None
    assert data[0]["cached_nutrition"]["analysis_text"] == "test"
