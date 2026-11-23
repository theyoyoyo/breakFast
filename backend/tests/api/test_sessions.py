"""
Tests for /sessions endpoints — chat session management and message persistence.
"""

import json

import pytest

from tests.chat_socket import open_chat


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
    await client.post("/sessions/")

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
    from unittest.mock import patch

    from starlette.testclient import TestClient

    from services.llm import LLM_UNAVAILABLE_MESSAGE, LLMUnavailableError

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
        with open_chat(sync_client, token) as ws:
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


async def _add_session(db, user_name: str, session_id: str) -> None:
    """A session for the named user (created if missing) last touched long ago."""
    await db.execute("INSERT OR IGNORE INTO users (name, pin_hash) VALUES (?, 'unused')", (user_name,))
    await db.execute(
        "INSERT INTO chat_sessions (id, user_id, updated_at) "
        "SELECT ?, id, '2026-01-01 08:00:00' FROM users WHERE name = ?",
        (session_id, user_name),
    )
    await db.commit()


async def _updated_at(db, session_id: str) -> str:
    async with db.execute("SELECT updated_at FROM chat_sessions WHERE id = ?", (session_id,)) as cur:
        return (await cur.fetchone())[0]


async def _message_count(db, session_id: str) -> int:
    async with db.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,)) as cur:
        return (await cur.fetchone())[0]


# Saving a message touches the user's own session, but not another user's session with that id
async def test_save_message_touches_only_own_session(client, db):
    await _add_session(db, "testuser", "own-session")
    await _add_session(db, "Bob", "bob-session")

    r = await client.post("/sessions/own-session/messages", json={"role": "assistant", "content": "Menemen"})
    assert r.status_code == 200
    r = await client.post("/sessions/bob-session/messages", json={"role": "assistant", "content": "Menemen"})
    assert r.status_code == 404

    assert await _updated_at(db, "own-session") != "2026-01-01 08:00:00"
    assert await _updated_at(db, "bob-session") == "2026-01-01 08:00:00"


# A message for another user's session or a session that doesn't exist gets 404 and stores nothing
@pytest.mark.parametrize("session_id", ["bob-session", "made-up-session"])
async def test_save_message_to_session_not_own_gets_404(client, db, session_id):
    await _add_session(db, "Bob", "bob-session")

    r = await client.post(f"/sessions/{session_id}/messages", json={"role": "user", "content": "Menemen", "select": True})

    assert r.status_code == 404
    assert await _message_count(db, session_id) == 0


# A role other than user or assistant is refused with 422 and stores nothing
@pytest.mark.parametrize("role", ["system", "admin", "", 5, None])
async def test_save_message_with_unknown_role_gets_422(client, db, role):
    await _add_session(db, "testuser", "own-session")

    r = await client.post("/sessions/own-session/messages", json={"role": role, "content": "Menemen"})

    assert r.status_code == 422
    assert await _message_count(db, "own-session") == 0


# Content that isn't text, or a select that isn't a bool, is refused with 422 and stores nothing
@pytest.mark.parametrize("body", [
    {"role": "assistant", "content": 5},
    {"role": "assistant", "content": ["Menemen"]},
    {"role": "assistant", "content": {"text": "Menemen"}},
    {"role": "assistant", "content": "Menemen", "select": "maybe"},
])
async def test_save_message_with_bad_body_gets_422(client, db, body):
    await _add_session(db, "testuser", "own-session")

    r = await client.post("/sessions/own-session/messages", json=body)

    assert r.status_code == 422
    assert await _message_count(db, "own-session") == 0


# A body with no role is saved as the assistant's, as meals sent to chat are
async def test_save_message_role_defaults_to_assistant(client, db):
    await _add_session(db, "testuser", "own-session")

    r = await client.post("/sessions/own-session/messages", json={"content": "Menemen"})

    assert r.status_code == 200
    messages = (await client.get("/sessions/own-session/messages")).json()
    assert [(m["role"], m["content"]) for m in messages] == [("assistant", "Menemen")]


# A message edit whose content isn't text is refused with 422 and leaves the message as it was
@pytest.mark.parametrize("content", [5, ["new"], {"text": "new"}])
async def test_update_message_with_non_text_content_gets_422(client, db, content):
    await _add_session(db, "testuser", "own-session")
    message_id = (await client.post("/sessions/own-session/messages", json={"content": "old"})).json()["id"]

    r = await client.put(f"/sessions/own-session/messages/{message_id}", json={"content": content})

    assert r.status_code == 422
    assert (await client.get("/sessions/own-session/messages")).json()[0]["content"] == "old"


# A saved "Today I ate" version is cleared by a null, and the edit changes only that field
async def test_update_message_null_ate_draft_clears_it(client, db):
    await _add_session(db, "testuser", "own-session")
    url = "/sessions/own-session/messages"
    message_id = (await client.post(url, json={"content": "card"})).json()["id"]
    draft = {"menu_name": "Plate", "menu": [{"name": "Olives", "amount": 5, "unit": "pcs", "ingredients": []}]}

    assert (await client.put(f"{url}/{message_id}", json={"ate_draft": draft})).status_code == 200
    assert (await client.get(url)).json()[0]["ate_draft"] == draft
    assert (await client.put(f"{url}/{message_id}", json={"ate_draft": None})).status_code == 200

    saved = (await client.get(url)).json()[0]
    assert (saved["content"], saved["ate_draft"]) == ("card", None)


# A selected card id that is a bool or a list is refused with 422
@pytest.mark.parametrize("message_id", [True, [1], 1.5])
async def test_select_message_with_bad_id_gets_422(client, db, message_id):
    await _add_session(db, "testuser", "own-session")

    r = await client.put("/sessions/own-session/selected", json={"message_id": message_id})

    assert r.status_code == 422


def _socket_chat(token: str, frames: list[dict]) -> None:
    """Send chat frames over a socket, each message frame waiting for its reply, with the LLM faked."""
    import json
    from unittest.mock import patch

    from starlette.testclient import TestClient

    from main import app

    async def mock_stream(*args, **kwargs):
        yield "Reply."

    with patch("routers.chat.build_chat_prompt", return_value="test prompt"), \
         patch("routers.chat.stream_response", mock_stream):
        with open_chat(TestClient(app), token) as ws:
            for frame in frames:
                ws.send_text(json.dumps(frame))
                if "message" in frame:
                    while ws.receive_json()["type"] != "done":
                        pass


# A message frame naming another user's session or a made-up one stores nothing under it;
# the message goes to the user's own latest session
@pytest.mark.parametrize("session_id", ["bob-session", "made-up-session"])
async def test_socket_message_for_session_not_own_is_saved_in_own_session(client, db, session_id):
    await _add_session(db, "testuser", "own-session")
    await _add_session(db, "Bob", "bob-session")
    token = client.headers["Authorization"].replace("Bearer ", "")

    _socket_chat(token, [{"message": "hello", "session_id": session_id}])

    assert await _message_count(db, session_id) == 0
    assert await _updated_at(db, "bob-session") == "2026-01-01 08:00:00"
    assert await _message_count(db, "own-session") == 2


# A Suggest press naming another user's session saves its suggestion and meal card in the user's own session
async def test_socket_suggestion_for_session_not_own_is_saved_in_own_session(client, db):
    import json
    from unittest.mock import patch

    from starlette.testclient import TestClient

    from main import app

    await _add_session(db, "testuser", "own-session")
    await _add_session(db, "Bob", "bob-session")
    token = client.headers["Authorization"].replace("Bearer ", "")
    meal = {"menu_name": "Plate", "menu": [{"name": "Olives", "amount": 5, "unit": "pcs", "ingredients": []}]}

    async def pipeline(**kwargs):
        yield {"type": "done", "content": "Try this.\n\n```json\n" + json.dumps(meal) + "\n```"}

    with patch("routers.chat.run_suggestion_pipeline", pipeline):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "bob-session"}))
            while ws.receive_json()["type"] != "meal_logged":
                pass

    async with db.execute("SELECT session_id FROM suggested_meals") as cur:
        assert [r[0] for r in await cur.fetchall()] == ["own-session"]
    assert await _message_count(db, "bob-session") == 0
    async with db.execute("SELECT selected_message_id FROM chat_sessions WHERE id = 'bob-session'") as cur:
        assert (await cur.fetchone())[0] is None


# A session-only frame naming another user's session keeps the socket on the user's current session
async def test_socket_session_frame_for_session_not_own_is_ignored(client, db):
    await _add_session(db, "testuser", "older-session")
    await _add_session(db, "testuser", "current-session")
    await _add_session(db, "Bob", "bob-session")
    token = client.headers["Authorization"].replace("Bearer ", "")

    _socket_chat(token, [{"session_id": "older-session"}, {"session_id": "bob-session"}, {"message": "hello"}])

    assert await _message_count(db, "bob-session") == 0
    assert await _message_count(db, "older-session") == 2
    assert await _message_count(db, "current-session") == 0


# A favorite sent to chat is saved as a card whose meal block carries the favorite's icon
async def test_favorite_sent_to_chat_keeps_its_emoji(client, db):
    from utils import extract_json_block

    await _add_session(db, "testuser", "own-session")
    fav_id = (await client.post("/favorites/", json={"meal_name": "Plate", "emoji": "🥯"})).json()["id"]
    fav = next(f for f in (await client.get("/favorites/")).json() if f["id"] == fav_id)
    content = f"⭐ From favorites: Plate\n\n```json\n{json.dumps(fav, ensure_ascii=False)}\n```"

    r = await client.post("/sessions/own-session/messages", json={"content": content, "select": True})
    assert r.status_code == 200
    saved = (await client.get("/sessions/own-session/messages")).json()[0]
    assert extract_json_block(saved["content"])["emoji"] == "🥯"
