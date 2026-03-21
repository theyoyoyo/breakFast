"""
Tests for /sessions endpoints — chat session management and message persistence.
"""

import pytest


@pytest.mark.asyncio
async def test_create_session(client):
    r = await client.post("/sessions/")
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert len(data["session_id"]) == 36  # UUID format


@pytest.mark.asyncio
async def test_get_active_session_creates_if_none(client):
    """First call to /sessions/active should auto-create a session."""
    r = await client.get("/sessions/active")
    assert r.status_code == 200
    data = r.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_get_active_session_returns_latest(client):
    """Should return the most recently updated session."""
    r1 = await client.post("/sessions/")
    sid1 = r1.json()["session_id"]

    r2 = await client.post("/sessions/")
    sid2 = r2.json()["session_id"]

    r = await client.get("/sessions/active")
    assert r.json()["id"] == sid2


@pytest.mark.asyncio
async def test_list_sessions(client):
    await client.post("/sessions/")
    await client.post("/sessions/")

    r = await client.get("/sessions/")
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) >= 2


@pytest.mark.asyncio
async def test_get_messages_empty(client):
    r = await client.post("/sessions/")
    sid = r.json()["session_id"]

    r = await client.get(f"/sessions/{sid}/messages")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_delete_session(client):
    """Deleting a session should remove it and its messages."""
    r = await client.post("/sessions/")
    sid = r.json()["session_id"]

    r = await client.delete(f"/sessions/{sid}")
    assert r.status_code == 204

    # Session should be gone from list
    r = await client.get("/sessions/")
    ids = [s["id"] for s in r.json()]
    assert sid not in ids


@pytest.mark.asyncio
async def test_delete_session_goes_back_to_previous(client):
    """After deleting active session, previous session should become active."""
    r1 = await client.post("/sessions/")
    sid1 = r1.json()["session_id"]

    r2 = await client.post("/sessions/")
    sid2 = r2.json()["session_id"]

    # Delete the newer session
    await client.delete(f"/sessions/{sid2}")

    # Active should now be the older session
    r = await client.get("/sessions/active")
    assert r.json()["id"] == sid1


@pytest.mark.asyncio
async def test_messages_persist_via_websocket(client, tmp_path, monkeypatch):
    """Messages sent via WebSocket should be persisted and retrievable."""
    import json
    import database
    from auth import create_token, get_user_id_from_token
    from starlette.testclient import TestClient
    from unittest.mock import patch
    from services.llm import LLMUnavailableError, LLM_UNAVAILABLE_MESSAGE

    # Create a session first
    r = await client.post("/sessions/")
    sid = r.json()["session_id"]

    # Get the token from client headers
    token = client.headers["Authorization"].replace("Bearer ", "")

    from main import app
    sync_client = TestClient(app)

    async def mock_stream(*args, **kwargs):
        raise LLMUnavailableError(LLM_UNAVAILABLE_MESSAGE)
        yield

    with patch("routers.chat.build_chat_prompt", return_value="test prompt"), \
         patch("routers.chat.stream_response", mock_stream):
        with sync_client.websocket_connect(f"/chat?token={token}") as ws:
            ws.send_text(json.dumps({"message": "hello", "session_id": sid}))
            msg = ws.receive_json()
            assert msg["type"] == "done"

    # Now check messages are persisted
    r = await client.get(f"/sessions/{sid}/messages")
    messages = r.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert messages[1]["role"] == "assistant"
