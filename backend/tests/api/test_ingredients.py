"""Integration tests for the /ingredients endpoints."""



# A new user's fridge is empty
async def test_list_empty_on_fresh_db(client):
    r = await client.get("/ingredients/")
    assert r.status_code == 200
    assert r.json() == []


# An item added without a date is stored with its name, an id and no expiry
async def test_add_ingredient(client):
    r = await client.post("/ingredients/", json={"name": "eggs"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "eggs"
    assert data["expiry_date"] is None
    assert "id" in data


# An item added with an expiry date keeps that date
async def test_add_ingredient_with_expiry(client):
    r = await client.post("/ingredients/", json={"name": "yogurt", "expiry_date": "2026-04-01"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "yogurt"
    assert data["expiry_date"] == "2026-04-01"


# Adding a name already in the fridge updates its expiry instead of adding a second row
async def test_add_same_name_upserts(client):
    await client.post("/ingredients/", json={"name": "milk"})
    r = await client.post("/ingredients/", json={"name": "milk", "expiry_date": "2026-04-05"})
    assert r.status_code == 201
    # Should still be one record, with updated expiry
    listed = await client.get("/ingredients/")
    milks = [i for i in listed.json() if i["name"] == "milk"]
    assert len(milks) == 1
    assert milks[0]["expiry_date"] == "2026-04-05"


# A deleted item is gone from the fridge list
async def test_delete_ingredient(client):
    created = (await client.post("/ingredients/", json={"name": "cheese"})).json()
    r = await client.delete(f"/ingredients/{created['id']}")
    assert r.status_code == 204
    listed = (await client.get("/ingredients/")).json()
    assert all(i["id"] != created["id"] for i in listed)


# ---------------------------------------------------------------------------
# Expiry check tests
# ---------------------------------------------------------------------------


async def test_expired_returns_empty_when_no_expiry(client):
    """No ingredients with expiry → empty result."""
    await client.post("/ingredients/", json={"name": "salt"})
    r = await client.get("/ingredients/expired")
    assert r.status_code == 200
    assert r.json() == []


async def test_expired_returns_expired_items(client):
    """Items with expiry_date in the past should be returned."""
    await client.post("/ingredients/", json={"name": "old_yogurt", "expiry_date": "2020-01-01"})
    await client.post("/ingredients/", json={"name": "fresh_eggs"})
    r = await client.get("/ingredients/expired")
    assert r.status_code == 200
    expired = r.json()
    names = [i["name"] for i in expired]
    assert "old_yogurt" in names
    assert "fresh_eggs" not in names


async def test_expired_always_returns_unacknowledged(client):
    """Calling expired multiple times still returns the same unacknowledged items."""
    await client.post("/ingredients/", json={"name": "old_milk", "expiry_date": "2020-01-01"})
    r1 = await client.get("/ingredients/expired")
    assert len(r1.json()) > 0
    # Second call returns the same items (no longer gated per day)
    r2 = await client.get("/ingredients/expired")
    assert len(r2.json()) > 0
    assert r2.json()[0]["name"] == "old_milk"


async def test_expired_count_endpoint(client):
    """expired-count returns current count of expired unacknowledged items."""
    r = await client.get("/ingredients/expired-count")
    assert r.json() == {"count": 0}

    await client.post("/ingredients/", json={"name": "old_item", "expiry_date": "2020-01-01"})
    r = await client.get("/ingredients/expired-count")
    assert r.json() == {"count": 1}

    # Non-expired item doesn't affect count
    await client.post("/ingredients/", json={"name": "fresh_item", "expiry_date": "2030-01-01"})
    r = await client.get("/ingredients/expired-count")
    assert r.json() == {"count": 1}


# ---------------------------------------------------------------------------
# Expired action tests (3-way: delete, keep, shopping)
# ---------------------------------------------------------------------------


async def test_expired_action_delete(client):
    """Delete action removes ingredients from inventory."""
    created = (await client.post("/ingredients/", json={"name": "expired_cheese", "expiry_date": "2020-01-01"})).json()
    r = await client.post("/ingredients/expired/action", json={"delete_ids": [created["id"]]})
    assert r.status_code == 200
    assert r.json()["deleted"] == 1
    listed = (await client.get("/ingredients/")).json()
    assert all(i["name"] != "expired_cheese" for i in listed)


async def test_expired_action_keep(client):
    """Keep action acknowledges expiry — item stays in inventory but disappears from expired list."""
    created = (await client.post("/ingredients/", json={"name": "old_honey", "expiry_date": "2020-01-01"})).json()

    # Should appear in expired list
    expired = (await client.get("/ingredients/expired")).json()
    assert any(i["name"] == "old_honey" for i in expired)

    # Keep it
    r = await client.post("/ingredients/expired/action", json={"keep_ids": [created["id"]]})
    assert r.json()["kept"] == 1

    # Should NOT appear in expired list anymore
    expired = (await client.get("/ingredients/expired")).json()
    assert all(i["name"] != "old_honey" for i in expired)

    # But should still be in inventory
    listed = (await client.get("/ingredients/")).json()
    assert any(i["name"] == "old_honey" for i in listed)

    # Count should also be 0
    r = await client.get("/ingredients/expired-count")
    assert r.json() == {"count": 0}


async def test_expired_action_shopping(client):
    """Shopping action removes from inventory and adds to shopping list."""
    created = (await client.post("/ingredients/", json={"name": "expired_milk", "expiry_date": "2020-01-01"})).json()
    r = await client.post("/ingredients/expired/action", json={"shopping_ids": [created["id"]]})
    assert r.json()["to_shopping"] == 1

    # Should be gone from inventory
    listed = (await client.get("/ingredients/")).json()
    assert all(i["name"] != "expired_milk" for i in listed)

    # Should be in shopping list
    shopping = (await client.get("/shopping/")).json()
    assert any(i["item_name"] == "expired_milk" for i in shopping)


async def test_expired_action_mixed(client):
    """All three actions work together."""
    a = (await client.post("/ingredients/", json={"name": "item_del", "expiry_date": "2020-01-01"})).json()
    b = (await client.post("/ingredients/", json={"name": "item_keep", "expiry_date": "2020-01-01"})).json()
    c = (await client.post("/ingredients/", json={"name": "item_shop", "expiry_date": "2020-01-01"})).json()

    r = await client.post("/ingredients/expired/action", json={
        "delete_ids": [a["id"]],
        "keep_ids": [b["id"]],
        "shopping_ids": [c["id"]],
    })
    assert r.json() == {"deleted": 1, "kept": 1, "to_shopping": 1}


# ---------------------------------------------------------------------------
# Ingredient groups tests
# ---------------------------------------------------------------------------


async def test_add_ingredient_default_group(client):
    """Adding a name the food list doesn't know, without group_name, defaults to Other."""
    r = await client.post("/ingredients/", json={"name": "Grandma's spice mix"})
    assert r.status_code == 201
    assert r.json()["group_name"] == "🍽️ Other"


# Without a group, the food list gives one by exact name: case, Turkish letters and plurals only
async def test_add_ingredient_gets_the_food_list_group(client):
    groups = {}
    for name in ["Tomatoes", "domates", "Yumurtalar", "Free-range eggs"]:
        groups[name] = (await client.post("/ingredients/", json={"name": name})).json()["group_name"]
    assert groups == {
        "Tomatoes": "🥬 Produce",
        "domates": "🥬 Produce",
        "Yumurtalar": "🐄 Animal Products",
        "Free-range eggs": "🍽️ Other",
    }


# A group picked in the add panel beats the food list
async def test_picked_group_beats_the_food_list(client):
    r = await client.post("/ingredients/", json={"name": "Honey", "group_name": "🍽️ Other"})
    assert r.json()["group_name"] == "🍽️ Other"


# Honey moved to Other, deleted and added again stays in Other: the user's pick beats the list
async def test_moved_group_beats_the_food_list(client):
    created = (await client.post("/ingredients/", json={"name": "Honey"})).json()
    assert created["group_name"] == "🍯 Sweets"
    await client.patch(f"/ingredients/{created['id']}", json={"group_name": "🍽️ Other"})
    await client.delete(f"/ingredients/{created['id']}")
    r = await client.post("/ingredients/", json={"name": "Honey"})
    assert r.json()["group_name"] == "🍽️ Other"


async def _picks(db) -> dict[str, str]:
    async with db.execute("SELECT ingredient_name, group_name FROM ingredient_group_memory WHERE picked = 1") as cur:
        return {r["ingredient_name"]: r["group_name"] for r in await cur.fetchall()}


async def _names(db) -> dict[str, str]:
    async with db.execute("SELECT ingredient_name, group_name FROM ingredient_group_memory") as cur:
        return {r["ingredient_name"]: r["group_name"] for r in await cur.fetchall()}


# Every added name is recorded, but only a move is a pick: an Auto add and an expiry-only edit aren't
async def test_memory_records_names_and_marks_picks(client, db):
    created = (await client.post("/ingredients/", json={"name": "Grandma's spice mix"})).json()
    await client.post("/ingredients/", json={"name": "Tomatoes"})
    await client.patch(f"/ingredients/{created['id']}", json={
        "name": "Grandma's spice mix", "expiry_date": "2026-12-01", "group_name": "🍽️ Other",
    })
    assert await _names(db) == {"Grandma's spice mix": "🍽️ Other", "Tomatoes": "🥬 Produce"}
    assert await _picks(db) == {}
    await client.patch(f"/ingredients/{created['id']}", json={"group_name": "🧂 Spices"})
    assert await _picks(db) == {"Grandma's spice mix": "🧂 Spices"}


# An Auto add of a name the user picked a group for keeps the pick
async def test_auto_add_keeps_the_pick(client, db):
    created = (await client.post("/ingredients/", json={"name": "Honey", "group_name": "🫒 Breakfast Staples"})).json()
    await client.delete(f"/ingredients/{created['id']}")
    await client.post("/ingredients/", json={"name": "Honey"})
    assert await _picks(db) == {"Honey": "🫒 Breakfast Staples"}


# A renamed item keeps its group under the new name, which the list doesn't know
async def test_rename_keeps_the_group_as_a_pick(client):
    created = (await client.post("/ingredients/", json={"name": "Eggs"})).json()
    await client.patch(f"/ingredients/{created['id']}", json={
        "name": "Village eggs", "group_name": created["group_name"],
    })
    await client.delete(f"/ingredients/{created['id']}")
    r = await client.post("/ingredients/", json={"name": "Village eggs"})
    assert r.json()["group_name"] == "🐄 Animal Products"


# Memory matches by exact name too, and a new pick replaces the earlier one for the same name (kept as a name)
async def test_memory_matches_the_same_name(client, db):
    created = (await client.post("/ingredients/", json={"name": "Peanut butter", "group_name": "🍯 Sweets"})).json()
    await client.delete(f"/ingredients/{created['id']}")
    r = await client.post("/ingredients/", json={"name": "peanut butter"})
    assert r.json()["group_name"] == "🍯 Sweets"
    await client.patch(f"/ingredients/{r.json()['id']}", json={"group_name": "🌱 Plant-Based"})
    assert await _picks(db) == {"peanut butter": "🌱 Plant-Based"}
    assert set(await _names(db)) == {"Peanut butter", "peanut butter"}


# A rename to a name another item has is refused with 409, and both items stay as they were
async def test_rename_to_a_taken_name_is_refused(client):
    eggs = (await client.post("/ingredients/", json={"name": "Eggs", "expiry_date": "2026-12-01"})).json()
    milk = (await client.post("/ingredients/", json={"name": "Milk"})).json()
    r = await client.patch(f"/ingredients/{milk['id']}", json={"name": "Eggs", "expiry_date": "2026-12-05"})
    assert r.status_code == 409
    assert r.json()["detail"] == "An item with this name is already in your fridge"
    listed = {i["id"]: i for i in (await client.get("/ingredients/")).json()}
    assert listed[eggs["id"]]["name"] == "Eggs"
    assert listed[eggs["id"]]["expiry_date"] == "2026-12-01"
    assert listed[milk["id"]]["name"] == "Milk"
    assert listed[milk["id"]]["expiry_date"] is None


# A refused rename writes nothing to the group memory, not even the group it sent along
async def test_refused_rename_leaves_the_group_memory_alone(client, db):
    await client.post("/ingredients/", json={"name": "Eggs"})
    milk = (await client.post("/ingredients/", json={"name": "Milk"})).json()
    names, picks = await _names(db), await _picks(db)
    r = await client.patch(f"/ingredients/{milk['id']}", json={"name": "Eggs", "group_name": "🧂 Spices"})
    assert r.status_code == 409
    assert await _names(db) == names
    assert await _picks(db) == picks


# Saving an item under its own current name is fine
async def test_rename_to_its_own_name_works(client):
    eggs = (await client.post("/ingredients/", json={"name": "Eggs"})).json()
    r = await client.patch(f"/ingredients/{eggs['id']}", json={"name": "Eggs", "expiry_date": "2026-12-01"})
    assert r.status_code == 200
    assert r.json()["name"] == "Eggs"
    assert r.json()["expiry_date"] == "2026-12-01"


# A blank or spaces-only name is refused with 422 on add and on rename, and the item keeps its name
async def test_blank_name_is_refused(client):
    for blank in ["", "   "]:
        assert (await client.post("/ingredients/", json={"name": blank})).status_code == 422
    eggs = (await client.post("/ingredients/", json={"name": "Eggs"})).json()
    for blank in ["", "   "]:
        r = await client.patch(f"/ingredients/{eggs['id']}", json={"name": blank})
        assert r.status_code == 422
    assert [i["name"] for i in (await client.get("/ingredients/")).json()] == ["Eggs"]


# The spaces around a name are cut on add and on rename
async def test_names_are_trimmed(client):
    added = (await client.post("/ingredients/", json={"name": "  Honey "})).json()
    assert added["name"] == "Honey"
    r = await client.patch(f"/ingredients/{added['id']}", json={"name": " Jam  "})
    assert r.json()["name"] == "Jam"
    assert [i["name"] for i in (await client.get("/ingredients/")).json()] == ["Jam"]


async def test_add_ingredient_with_group(client):
    """Adding with explicit group assigns it correctly."""
    r = await client.post("/ingredients/", json={"name": "sucuk", "group_name": "🐄 Animal Products"})
    assert r.status_code == 201
    assert r.json()["group_name"] == "🐄 Animal Products"


async def test_update_ingredient_group(client):
    """PATCH can change an ingredient's group."""
    created = (await client.post("/ingredients/", json={"name": "Grandma's spice mix"})).json()
    assert created["group_name"] == "🍽️ Other"
    r = await client.patch(f"/ingredients/{created['id']}", json={"group_name": "🧂 Spices"})
    assert r.status_code == 200
    assert r.json()["group_name"] == "🧂 Spices"


async def test_invalid_group_rejected(client):
    """Unknown group names return 422."""
    r = await client.post("/ingredients/", json={"name": "water", "group_name": "InvalidGroup"})
    assert r.status_code == 422


async def test_group_memory_on_readd(client):
    """Deleting and re-adding an ingredient restores its remembered group."""
    created = (await client.post("/ingredients/", json={"name": "tomato", "group_name": "🥬 Produce"})).json()
    await client.delete(f"/ingredients/{created['id']}")
    # Re-add without specifying group — should restore from memory
    r = await client.post("/ingredients/", json={"name": "tomato"})
    assert r.status_code == 201
    assert r.json()["group_name"] == "🥬 Produce"


# The check lists only the meal's ingredients missing from the user's fridge (water never counts)
async def test_check_lists_missing_ingredients(client):
    await client.post("/ingredients/", json={"name": "Yumurta"})
    await client.post("/ingredients/", json={"name": "Tuz", "group_name": "🫙 Pantry"})
    meal = {"menu": [
        {"name": "Menemen", "ingredients": [
            {"name": "Yumurta"}, {"name": "Tuz"}, {"name": "Avocado"}, {"name": "Water"},
        ]},
        {"name": "Olives", "amount": 10, "unit": "adet", "ingredients": []},
    ]}
    r = await client.post("/ingredients/check", json={"meal": meal})
    assert r.status_code == 200
    assert r.json() == {"missing": ["Avocado", "Olives"]}


# Another user's fridge never makes an item count as available
async def test_check_ignores_other_users_fridge(client, db):
    cur = await db.execute("INSERT INTO users (name, pin_hash) VALUES ('Other', 'x')")
    await db.execute(
        "INSERT INTO ingredient_inventory (user_id, name) VALUES (?, 'Avocado')", (cur.lastrowid,)
    )
    await db.commit()
    meal = {"menu": [{"name": "Avocado", "amount": 1, "unit": "adet", "ingredients": []}]}
    r = await client.post("/ingredients/check", json={"meal": meal})
    assert r.json() == {"missing": ["Avocado"]}
