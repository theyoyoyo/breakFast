"""Integration tests for the /health-rules endpoints."""


# Empty list when no rules exist
async def test_list_health_rules_empty(client):
    r = await client.get("/health-rules/")
    assert r.status_code == 200
    assert r.json() == []


# Create a rule with default priority (high)
async def test_create_health_rule_default_priority(client):
    r = await client.post("/health-rules/", json={"rule_text": "Avoid refined sugars"})
    assert r.status_code == 201
    data = r.json()
    assert data["rule_text"] == "Avoid refined sugars"
    assert data["priority"] == "high"


# Create a rule with explicit priority
async def test_create_health_rule_with_priority(client):
    r = await client.post("/health-rules/", json={"rule_text": "Favor omega-3 sources", "priority": "critical"})
    assert r.status_code == 201
    assert r.json()["priority"] == "critical"


# Update rule text and priority
async def test_update_health_rule(client):
    rule = (await client.post("/health-rules/", json={"rule_text": "Low sodium"})).json()
    r = await client.put(f"/health-rules/{rule['id']}", json={"priority": "low"})
    assert r.status_code == 200
    assert r.json()["priority"] == "low"
    assert r.json()["rule_text"] == "Low sodium"


# Update only rule text, keeping priority
async def test_update_health_rule_text_only(client):
    rule = (await client.post("/health-rules/", json={"rule_text": "Old text", "priority": "critical"})).json()
    r = await client.put(f"/health-rules/{rule['id']}", json={"rule_text": "New text"})
    assert r.status_code == 200
    assert r.json()["rule_text"] == "New text"
    assert r.json()["priority"] == "critical"


# Delete a health rule
async def test_delete_health_rule(client):
    rule = (await client.post("/health-rules/", json={"rule_text": "Temporary rule"})).json()
    r = await client.delete(f"/health-rules/{rule['id']}")
    assert r.status_code == 204
    rules = (await client.get("/health-rules/")).json()
    assert len(rules) == 0


# Update nonexistent rule returns 404
async def test_update_nonexistent_rule(client):
    r = await client.put("/health-rules/9999", json={"priority": "low"})
    assert r.status_code == 404


# Invalid priority returns 422
async def test_invalid_priority_rejected(client):
    r = await client.post("/health-rules/", json={"rule_text": "Test", "priority": "mega"})
    assert r.status_code == 422
