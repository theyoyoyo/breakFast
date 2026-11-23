"""Integration tests for the /ratings endpoints."""



# A new user has no ratings
async def test_list_empty_on_fresh_db(client):
    r = await client.get("/ratings/")
    assert r.status_code == 200
    assert r.json() == []


# A rating is saved with its item, its score and an id
async def test_create_rating(client):
    r = await client.post("/ratings/", json={"product_name": "eggs", "rating": 8})
    assert r.status_code == 201
    data = r.json()
    assert data["product_name"] == "eggs"
    assert data["rating"] == 8
    assert "id" in data


# A rating given without a score gets 10
async def test_create_rating_default_10(client):
    r = await client.post("/ratings/", json={"product_name": "milk"})
    assert r.status_code == 201
    assert r.json()["rating"] == 10


# A second rating for the same product is refused with 409, and the first keeps its score
async def test_duplicate_product_returns_409(client):
    await client.post("/ratings/", json={"product_name": "cheese", "rating": 4})
    r = await client.post("/ratings/", json={"product_name": "cheese", "rating": 9})
    assert r.status_code == 409
    assert [(x["product_name"], x["rating"]) for x in (await client.get("/ratings/")).json()] == [("cheese", 4)]


# An edit changes a rating's score
async def test_update_rating(client):
    r = await client.post("/ratings/", json={"product_name": "yogurt", "rating": 5})
    rid = r.json()["id"]
    r2 = await client.put(f"/ratings/{rid}", json={"rating": 9})
    assert r2.status_code == 200
    assert r2.json()["rating"] == 9


# Updating a rating that doesn't exist is refused with 404 and creates or changes nothing
async def test_update_nonexistent_returns_404(client):
    await client.post("/ratings/", json={"product_name": "honey", "rating": 7})
    before = (await client.get("/ratings/")).json()
    r = await client.put("/ratings/9999", json={"rating": 5})
    assert r.status_code == 404
    assert (await client.get("/ratings/")).json() == before


# A deleted rating is gone from the list
async def test_delete_rating(client):
    r = await client.post("/ratings/", json={"product_name": "bread"})
    rid = r.json()["id"]
    r2 = await client.delete(f"/ratings/{rid}")
    assert r2.status_code == 204

    listed = await client.get("/ratings/")
    assert all(item["product_name"] != "bread" for item in listed.json())


# A score below 1 or above 10 is refused with 422, on create and on update, and nothing is saved
async def test_rating_validation_min_max(client):
    rid = (await client.post("/ratings/", json={"product_name": "honey", "rating": 7})).json()["id"]
    for score in (0, 11):
        assert (await client.post("/ratings/", json={"product_name": "jam", "rating": score})).status_code == 422
        assert (await client.put(f"/ratings/{rid}", json={"rating": score})).status_code == 422
    assert [(x["product_name"], x["rating"]) for x in (await client.get("/ratings/")).json()] == [("honey", 7)]


# The list returns every rating the user saved
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
