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
    assert data["formatted"] == "Adım bulunamadı."


async def test_plan_with_cached_schedule(client, db):
    """Should return cached schedule when meal_id has one."""
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        row = await cur.fetchone()
        user_id = row[0]

    cached = {
        "timeline": [
            {"start_min": 0, "task": "Yumurtaları haşla", "duration_min": 7,
             "resource": "ocak", "end_action": "Süz ve soğuk suya al"},
        ],
        "makespan_min": 7,
        "formatted": "🔪 Hazırlık\n  • Domates dilimle\n\n⏱ Zamanlama (7 dk)\n  0:00  — Yumurtaları haşla (7 dk)  [ocak]\n  7:00  — Hazır! ✓",
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
        "steps": ["Yumurtaları haşla"],
        "ingredients": [],
        "meal_id": meal_id,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["cached"] is True
    assert data["makespan_min"] == 7
    assert len(data["timeline"]) == 1
    assert data["timeline"][0]["task"] == "Yumurtaları haşla"
    assert "Hazır!" in data["formatted"]


async def test_plan_without_meal_id_llm_down(client):
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


async def test_plan_caches_result(client, db):
    """When meal_id is provided but no cache, endpoint doesn't crash."""
    async with db.execute("SELECT id FROM users WHERE name = 'testuser'") as cur:
        row = await cur.fetchone()
        user_id = row[0]

    cur = await db.execute(
        """INSERT INTO meal_history (user_id, meal_name, ingredients, steps)
           VALUES (?, ?, ?, ?)""",
        (user_id, "Uncached Meal", "[]", "[]"),
    )
    meal_id = cur.lastrowid
    await db.commit()

    r = await client.post("/scheduler/plan", json={
        "meal_name": "Uncached Meal",
        "steps": ["Boil water"],
        "ingredients": [],
        "meal_id": meal_id,
    })
    assert r.status_code == 200
    assert "formatted" in r.json()
