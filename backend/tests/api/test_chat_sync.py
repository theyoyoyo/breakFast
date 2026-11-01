"""
Tests for live chat sync — a user's other chat sockets get session_updated after a reply,
a REST save or a message edit, supplements_updated after a supplement change and
shopping_suggestions_updated after a suggestions list change; no other user's socket does.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from contextlib import ExitStack
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio
from fastapi import WebSocketDisconnect
from starlette.testclient import TestClient

import database
from auth import hash_pin, create_token
from services import chat_sync


@pytest_asyncio.fixture
async def sync_setup(tmp_path, monkeypatch):
    """DB with two users and one chat session each; returns (app, {name: (token, user_id, session_id)})."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    users = {}
    async with aiosqlite.connect(db_path) as db:
        for name in ("ada", "bob"):
            await db.execute("INSERT INTO users (name, pin_hash) VALUES (?, ?)", (name, hash_pin("1234")))
            async with db.execute("SELECT id FROM users WHERE name = ?", (name,)) as cur:
                user_id = (await cur.fetchone())[0]
            session_id = f"session-{name}"
            await db.execute("INSERT INTO chat_sessions (id, user_id) VALUES (?, ?)", (session_id, user_id))
            users[name] = (create_token(user_id), user_id, session_id)
        await db.commit()

    from main import app
    return app, users


async def _reply(*args, **kwargs):
    """A chat reply streamed in two tokens."""
    yield "Hi"
    yield " there"


def _fake_llm():
    """Patch the chat prompt and the LLM stream for the duration of a test."""
    stack = ExitStack()
    stack.enter_context(patch("routers.chat.build_chat_prompt", return_value="test prompt"))
    stack.enter_context(patch("routers.chat.stream_response", _reply))
    return stack


def _chat(ws, message="hello", session_id=None):
    """Send a chat message and return everything the socket receives up to that reply's done.
    Pushes sent to this socket before the reply arrive first, so a missing push fails instead of hanging."""
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    ws.send_text(json.dumps(payload))
    received = []
    while True:
        msg = ws.receive_json()
        received.append(msg)
        if msg["type"] == "done":
            return received


def _pushes(received, kind="session_updated"):
    return [m for m in received if m["type"] == kind]


# The user's other socket is told about the saved reply, without its tokens; the socket that asked isn't told.
@pytest.mark.asyncio
async def test_second_socket_gets_session_updated_after_reply(sync_setup):
    app, users = sync_setup
    token, _, session_id = users["ada"]
    with _fake_llm(), TestClient(app) as client:
        with client.websocket_connect(f"/chat?token={token}") as phone, \
             client.websocket_connect(f"/chat?token={token}") as desktop:
            asked = _chat(phone, session_id=session_id)
            assert _pushes(asked) == []
            assert asked[-1]["content"] == "Hi there"
            assert isinstance(asked[-1]["message_id"], int)

            seen = _chat(desktop)
            assert seen[0] == {"type": "session_updated", "session_id": session_id}
            assert [m for m in seen if m["type"] == "token"] == [
                {"type": "token", "content": "Hi"}, {"type": "token", "content": " there"},
            ]  # only the desktop's own reply was streamed to it


# A reply in one user's chat never reaches another user's socket.
@pytest.mark.asyncio
async def test_other_users_socket_gets_nothing(sync_setup):
    app, users = sync_setup
    ada_token, _, ada_session = users["ada"]
    bob_token, _, _ = users["bob"]
    with _fake_llm(), TestClient(app) as client:
        with client.websocket_connect(f"/chat?token={ada_token}") as ada, \
             client.websocket_connect(f"/chat?token={bob_token}") as bob:
            _chat(ada, session_id=ada_session)
            assert _pushes(_chat(bob)) == []


# A message saved over REST tells every socket of that user, and no other user's.
@pytest.mark.asyncio
async def test_rest_save_notifies_users_sockets(sync_setup):
    app, users = sync_setup
    ada_token, _, ada_session = users["ada"]
    bob_token, _, _ = users["bob"]
    with _fake_llm(), TestClient(app) as client:
        with client.websocket_connect(f"/chat?token={ada_token}") as ada, \
             client.websocket_connect(f"/chat?token={bob_token}") as bob:
            r = client.post(
                f"/sessions/{ada_session}/messages",
                json={"role": "assistant", "content": "📊 Analysis"},
                headers={"Authorization": f"Bearer {ada_token}"},
            )
            assert r.status_code == 200
            assert isinstance(r.json()["id"], int)
            assert _pushes(_chat(ada)) == [{"type": "session_updated", "session_id": ada_session}]
            assert _pushes(_chat(bob)) == []


# PUT rewrites the user's own message and tells their sockets; another user's message is out of reach.
@pytest.mark.asyncio
async def test_message_edit_replaces_content_and_notifies(sync_setup):
    app, users = sync_setup
    ada_token, _, ada_session = users["ada"]
    bob_token, _, _ = users["bob"]
    ada_auth = {"Authorization": f"Bearer {ada_token}"}
    with _fake_llm(), TestClient(app) as client:
        message_id = client.post(
            f"/sessions/{ada_session}/messages", json={"role": "assistant", "content": "old"}, headers=ada_auth,
        ).json()["id"]
        with client.websocket_connect(f"/chat?token={ada_token}") as ada:
            r = client.put(f"/sessions/{ada_session}/messages/{message_id}", json={"content": "new"}, headers=ada_auth)
            assert r.status_code == 200
            assert _pushes(_chat(ada)) == [{"type": "session_updated", "session_id": ada_session}]

        messages = client.get(f"/sessions/{ada_session}/messages", headers=ada_auth).json()
        assert (messages[0]["id"], messages[0]["content"]) == (message_id, "new")

        r = client.put(
            f"/sessions/{ada_session}/messages/{message_id}",
            json={"content": "hijacked"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert r.status_code == 404


# Marking a pill and every supplement change in Settings tell the user's sockets, and no other user's.
@pytest.mark.asyncio
async def test_supplement_changes_notify_users_sockets(sync_setup):
    app, users = sync_setup
    ada_token, _, _ = users["ada"]
    bob_token, _, _ = users["bob"]
    ada_auth = {"Authorization": f"Bearer {ada_token}"}
    with _fake_llm(), TestClient(app) as client:
        with client.websocket_connect(f"/chat?token={ada_token}") as ada, \
             client.websocket_connect(f"/chat?token={bob_token}") as bob:
            supp_id = client.post("/profile/supplements", json={"name": "Vitamin D"}, headers=ada_auth).json()["id"]
            edit = {"name": "Vitamin D3", "contents": "1000 IU", "frequency": "sometimes"}
            assert client.put(f"/profile/supplements/{supp_id}", json=edit, headers=ada_auth).status_code == 200
            assert client.post(f"/profile/supplements/{supp_id}/toggle", json={"taken": True}, headers=ada_auth).status_code == 200
            assert client.delete(f"/profile/supplements/{supp_id}", headers=ada_auth).status_code == 204

            assert _pushes(_chat(ada), "supplements_updated") == [{"type": "supplements_updated"}] * 4
            assert _pushes(_chat(bob), "supplements_updated") == []


# A shopping suggestions change tells the user's sockets, and no other user's.
@pytest.mark.asyncio
async def test_shopping_suggestions_change_notifies_users_sockets(sync_setup):
    app, users = sync_setup
    ada_token, _, _ = users["ada"]
    bob_token, _, _ = users["bob"]
    with _fake_llm(), TestClient(app) as client:
        with client.websocket_connect(f"/chat?token={ada_token}") as ada,              client.websocket_connect(f"/chat?token={bob_token}") as bob:
            r = client.put(
                "/shopping/suggestions",
                json={"items": [{"name": "Salmon", "reason": "Omega-3"}]},
                headers={"Authorization": f"Bearer {ada_token}"},
            )
            assert r.status_code == 200
            assert _pushes(_chat(ada), "shopping_suggestions_updated") == [{"type": "shopping_suggestions_updated"}]
            assert _pushes(_chat(bob), "shopping_suggestions_updated") == []


class _DroppingSocket:
    """A chat socket whose device drops (a locked phone) as soon as the reply starts streaming."""

    def __init__(self, payload):
        self._incoming = [json.dumps(payload)]

    async def accept(self):
        pass

    async def receive_text(self):
        if self._incoming:
            return self._incoming.pop(0)
        raise WebSocketDisconnect(code=1006)

    async def send_json(self, data):
        raise WebSocketDisconnect(code=1006)


class _RecordingSocket:
    """Another open chat socket of the same user that records what it is sent."""

    def __init__(self):
        self.sent = []

    async def send_json(self, data):
        self.sent.append(data)


# A device dropping mid-reply doesn't stop the reply: it is saved whole and the user's other socket is told.
@pytest.mark.asyncio
async def test_reply_is_saved_when_socket_drops_mid_stream(sync_setup):
    _, users = sync_setup
    token, user_id, session_id = users["ada"]
    from routers.chat import chat_endpoint

    other = _RecordingSocket()
    chat_sync.register(user_id, other)
    try:
        with _fake_llm():
            await chat_endpoint(_DroppingSocket({"message": "hello", "session_id": session_id}), token=token)
    finally:
        chat_sync.unregister(user_id, other)

    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        async with db.execute("SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id", (session_id,)) as cur:
            rows = [tuple(r) for r in await cur.fetchall()]
    assert rows == [("user", "hello"), ("assistant", "Hi there")]
    assert other.sent == [{"type": "session_updated", "session_id": session_id}]


# A socket that can't be sent to is dropped from the registry; the user's working socket still gets the push.
@pytest.mark.asyncio
async def test_notify_forgets_a_socket_that_fails():
    class Broken:
        async def send_json(self, data):
            raise RuntimeError("closed")

    broken, working = Broken(), _RecordingSocket()
    chat_sync.register(99, broken)
    chat_sync.register(99, working)
    try:
        await chat_sync.notify_session_updated(99, "s1")
        await chat_sync.notify_session_updated(99, "s2")
    finally:
        chat_sync.unregister(99, working)
    assert working.sent == [
        {"type": "session_updated", "session_id": "s1"},
        {"type": "session_updated", "session_id": "s2"},
    ]
    assert 99 not in chat_sync._sockets
