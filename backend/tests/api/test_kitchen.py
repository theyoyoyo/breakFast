"""Integration tests for the /kitchen endpoints."""

import pytest
import aiosqlite


# First GET returns all appliances with stove enabled, rest disabled
async def test_kitchen_list_default(client):
    r = await client.get("/kitchen/")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 9
    enabled = [a for a in data if a["enabled"]]
    assert len(enabled) == 1
    assert enabled[0]["key"] == "stove"


# Toggle an appliance on and verify
async def test_kitchen_toggle_on(client):
    r = await client.put("/kitchen/air_fryer", json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["enabled"] is True

    listed = await client.get("/kitchen/")
    af = [a for a in listed.json() if a["key"] == "air_fryer"][0]
    assert af["enabled"] is True


# Toggle an appliance off and verify
async def test_kitchen_toggle_off(client):
    # First enable
    await client.put("/kitchen/oven", json={"enabled": True})
    # Then disable
    r = await client.put("/kitchen/oven", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    listed = await client.get("/kitchen/")
    oven = [a for a in listed.json() if a["key"] == "oven"][0]
    assert oven["enabled"] is False


# PUT with unknown key returns 404
async def test_kitchen_invalid_key(client):
    r = await client.put("/kitchen/flux_capacitor", json={"enabled": True})
    assert r.status_code == 404


# Two users have independent kitchen configs
async def test_kitchen_per_user_isolation(client, db):
    # Create a second user
    from auth import hash_pin, create_token

    import database
    async with aiosqlite.connect(database.DATABASE_PATH) as conn:
        await conn.execute(
            "INSERT INTO users (name, pin_hash, is_admin) VALUES (?, ?, ?)",
            ("user2", hash_pin("5678"), 0),
        )
        await conn.commit()
        async with conn.execute("SELECT id FROM users WHERE name = 'user2'") as cur:
            user2_id = (await cur.fetchone())[0]

    token2 = create_token(user2_id)

    # User 1 enables air_fryer
    await client.put("/kitchen/air_fryer", json={"enabled": True})

    # User 2 should still have defaults (only stove enabled)
    r = await client.get("/kitchen/", headers={"Authorization": f"Bearer {token2}"})
    assert r.status_code == 200
    data = r.json()
    af = [a for a in data if a["key"] == "air_fryer"][0]
    assert af["enabled"] is False
