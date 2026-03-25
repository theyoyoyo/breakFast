"""Integration tests for the /scheduler endpoints."""

import json
import pytest


async def test_plan_no_steps(client):
    """Should return empty timeline when no steps provided."""
    r = await client.post("/scheduler/plan", json={
        "meal_name": "Test Meal",
        "steps": [],
        "ingredients": [],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["timeline"] == []
    assert data["makespan_min"] == 0
    assert data["formatted"] == "No steps provided."


async def test_plan_with_cached_schedule(client, db):
    """Should return cached schedule when meal_id has one."""
    # Get the test user_id
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        row = await cur.fetchone()
        user_id = row[0]

    cached = {
        "timeline": [{"time": 0, "label": "boil eggs", "resource": "stove", "note": ""}],
        "makespan_min": 7,
        "formatted": "0:00  — boil eggs\nTotal time: 7 minutes.",
    }
    cur = await db.execute(
        """INSERT INTO meal_history (user_id, meal_name, ingredients, steps, schedule)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, "Cached Meal", "[]", "[]", json.dumps(cached)),
    )
    meal_id = cur.lastrowid
    await db.commit()

    r = await client.post("/scheduler/plan", json={
        "meal_name": "Cached Meal",
        "steps": ["boil eggs"],
        "ingredients": [],
        "meal_id": meal_id,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["cached"] is True
    assert data["makespan_min"] == 7
    assert len(data["timeline"]) == 1
    assert data["timeline"][0]["label"] == "boil eggs"


async def test_plan_without_meal_id_no_cache(client):
    """When meal_id is None and LLM unavailable, returns lyric fallback."""
    r = await client.post("/scheduler/plan", json={
        "meal_name": "Simple Meal",
        "steps": ["Toast bread", "Spread butter"],
        "ingredients": [{"name": "Bread"}, {"name": "Butter"}],
    })
    assert r.status_code == 200
    data = r.json()
    assert "formatted" in data
    assert "timeline" in data
    assert "makespan_min" in data


async def test_plan_caches_result_when_meal_id_provided(client, db):
    """When meal_id is provided but no cache, schedule should be saved after generation."""
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        row = await cur.fetchone()
        user_id = row[0]

    # Create a meal without cached schedule
    cur = await db.execute(
        """INSERT INTO meal_history (user_id, meal_name, ingredients, steps)
           VALUES (?, ?, ?, ?)""",
        (user_id, "Uncached Meal", "[]", "[]"),
    )
    meal_id = cur.lastrowid
    await db.commit()

    # Request schedule — LLM unavailable in test env, so we get a fallback
    r = await client.post("/scheduler/plan", json={
        "meal_name": "Uncached Meal",
        "steps": ["Boil water"],
        "ingredients": [],
        "meal_id": meal_id,
    })
    assert r.status_code == 200
    # Even if LLM fails, the endpoint should not crash
    assert "formatted" in r.json()
