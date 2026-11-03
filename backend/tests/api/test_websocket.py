"""
Tests for WebSocket /chat endpoint — auth and basic messaging.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import aiosqlite
import pytest
import pytest_asyncio

import database
from auth import hash_pin, create_token


@pytest_asyncio.fixture
async def ws_setup(tmp_path, monkeypatch):
    """Set up DB with a test user and return (app, valid_token, user_id)."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash) VALUES (?, ?)",
            ("wsuser", hash_pin("1234")),
        )
        await db.commit()
        async with db.execute("SELECT id FROM users WHERE name = 'wsuser'") as cur:
            user_id = (await cur.fetchone())[0]

    token = create_token(user_id)

    from main import app
    return app, token, user_id


@pytest.mark.asyncio
async def test_websocket_rejects_missing_token(ws_setup):
    """WebSocket without token query param should fail."""
    app, _, _ = ws_setup
    from starlette.testclient import TestClient

    client = TestClient(app)
    # Missing token — FastAPI returns 422 (validation error) for missing required query param
    with pytest.raises(Exception):
        with client.websocket_connect("/chat"):
            pass


@pytest.mark.asyncio
async def test_websocket_rejects_invalid_token(ws_setup):
    """WebSocket with invalid token should be closed with 4001."""
    app, _, _ = ws_setup
    from starlette.testclient import TestClient

    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/chat?token=invalid_token_xxx") as ws:
            # Should be closed immediately
            ws.receive_json()


@pytest.mark.asyncio
async def test_websocket_accepts_valid_token(ws_setup):
    """WebSocket with valid token should connect and accept messages."""
    app, token, _ = ws_setup
    from starlette.testclient import TestClient
    from unittest.mock import patch
    from services.llm import LLMUnavailableError, LLM_UNAVAILABLE_MESSAGE, FALLBACK_LYRICS

    client = TestClient(app)

    # Mock build_chat_prompt to return a simple string
    # and stream_response as an async generator that raises LLMUnavailableError
    async def mock_stream(*args, **kwargs):
        raise LLMUnavailableError(LLM_UNAVAILABLE_MESSAGE)
        yield  # makes this an async generator

    with patch("routers.chat.build_chat_prompt", return_value="test prompt"), \
         patch("routers.chat.stream_response", mock_stream):
        with client.websocket_connect(f"/chat?token={token}") as ws:
            ws.send_text(json.dumps({"message": "hello"}))

            # Should get done message with a fallback lyric line
            msg = ws.receive_json()
            assert msg["type"] == "done"
            assert msg["content"] in FALLBACK_LYRICS


@pytest.mark.asyncio
async def test_websocket_handles_generic_exception(ws_setup):
    """WebSocket should return fallback message on unexpected exceptions (not crash)."""
    app, token, _ = ws_setup
    from starlette.testclient import TestClient
    from unittest.mock import patch
    from services.llm import FALLBACK_LYRICS

    client = TestClient(app)

    async def mock_stream_crash(*args, **kwargs):
        raise RuntimeError("unexpected boom")
        yield

    with patch("routers.chat.build_chat_prompt", return_value="test prompt"), \
         patch("routers.chat.stream_response", mock_stream_crash):
        with client.websocket_connect(f"/chat?token={token}") as ws:
            ws.send_text(json.dumps({"message": "hello"}))

            msg = ws.receive_json()
            assert msg["type"] == "done"
            assert msg["content"] in FALLBACK_LYRICS


@pytest.mark.asyncio
async def test_websocket_build_chat_prompt_no_mock(ws_setup):
    """WebSocket should work with the real build_chat_prompt."""
    app, token, _ = ws_setup
    from starlette.testclient import TestClient
    from unittest.mock import patch
    from services.llm import LLMUnavailableError, LLM_UNAVAILABLE_MESSAGE, FALLBACK_LYRICS

    client = TestClient(app)

    # Only mock stream_response — let build_chat_prompt run for real
    # to verify the JSON template braces are properly escaped
    async def mock_stream(*args, **kwargs):
        raise LLMUnavailableError(LLM_UNAVAILABLE_MESSAGE)
        yield

    with patch("routers.chat.stream_response", mock_stream):
        with client.websocket_connect(f"/chat?token={token}") as ws:
            ws.send_text(json.dumps({"message": "hello"}))

            msg = ws.receive_json()
            assert msg["type"] == "done"
            assert msg["content"] in FALLBACK_LYRICS


@pytest.mark.asyncio
async def test_websocket_suggest_type_uses_pipeline(ws_setup):
    """WebSocket with type=suggest should route through the suggestion pipeline."""
    app, token, _ = ws_setup
    from starlette.testclient import TestClient
    from unittest.mock import patch, MagicMock

    client = TestClient(app)

    async def mock_pipeline(context, user_message, mode=None, temperature=None, chat_context=None):
        yield {"type": "progress", "step": "drafting"}
        yield {"type": "token", "content": "Merhaba"}
        yield {"type": "done", "content": "Merhaba"}

    mock_fn = MagicMock(side_effect=mock_pipeline)

    with patch("routers.chat.run_suggestion_pipeline", mock_fn):
        with client.websocket_connect(f"/chat?token={token}") as ws:
            ws.send_text(json.dumps({"message": "Bana kahvaltı öner", "type": "suggest"}))

            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] == "done":
                    break

            mock_fn.assert_called_once()
            progress_msgs = [m for m in messages if m["type"] == "progress"]
            assert len(progress_msgs) >= 1


@pytest.mark.asyncio
async def test_websocket_suggest_with_mode_passes_mode(ws_setup):
    """WebSocket with type=suggest and mode=favorites should pass mode to pipeline."""
    app, token, _ = ws_setup
    from starlette.testclient import TestClient
    from unittest.mock import patch, MagicMock

    client = TestClient(app)

    async def mock_pipeline(context, user_message, mode=None, temperature=None, chat_context=None):
        yield {"type": "done", "content": "OK"}

    mock_fn = MagicMock(side_effect=mock_pipeline)

    with patch("routers.chat.run_suggestion_pipeline", mock_fn):
        with client.websocket_connect(f"/chat?token={token}") as ws:
            ws.send_text(json.dumps({
                "message": "Sevdiğim yemeklerden öner",
                "type": "suggest",
                "mode": "favorites",
            }))

            msg = ws.receive_json()
            assert msg["type"] == "done"
            assert msg["content"] == "OK"  # not a lyric fallback
            mock_fn.assert_called_once()
            call_kwargs = mock_fn.call_args
            assert call_kwargs.kwargs.get("mode") == "favorites"


@pytest.mark.asyncio
async def test_save_suggestion_defaults_unit_by_language(ws_setup):
    """A simple menu item saved without a unit gets the count unit of the reply language."""
    _, _, user_id = ws_setup
    from routers.chat import _save_suggestion

    meal = {"menu_name": "Kahvaltı", "menu": [{"name": "Ayran", "amount": 1, "ingredients": []}]}
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        await db.execute("INSERT INTO chat_sessions (id, user_id) VALUES (?, ?)", ("s1", user_id))
        en_id = await _save_suggestion(db, user_id, "s1", meal, "en")
        tr_id = await _save_suggestion(db, user_id, "s1", meal, "tr")
        async with db.execute("SELECT id, ingredients FROM suggested_meals ORDER BY id") as cur:
            units = {row[0]: json.loads(row[1])[0]["unit"] for row in await cur.fetchall()}
    assert units == {en_id: "pcs", tr_id: "adet"}


# A chat reply saved into another user's session id doesn't touch that session
async def test_save_message_touches_only_own_session(ws_setup):
    _, _, user_id = ws_setup
    from routers.chat import _save_message

    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("INSERT INTO users (name, pin_hash) VALUES ('Bob', 'unused')")
        await db.execute(
            "INSERT INTO chat_sessions (id, user_id, updated_at) VALUES "
            "('own-session', ?, '2026-01-01 08:00:00'), "
            "('bob-session', (SELECT id FROM users WHERE name = 'Bob'), '2026-01-01 08:00:00')",
            (user_id,),
        )
        await db.commit()

        await _save_message(db, "own-session", user_id, "user", "Any eggs?")
        await _save_message(db, "bob-session", user_id, "user", "Any eggs?")

        async with db.execute("SELECT id, updated_at FROM chat_sessions") as cur:
            updated = {r["id"]: r["updated_at"] for r in await cur.fetchall()}
    assert updated["own-session"] != "2026-01-01 08:00:00"
    assert updated["bob-session"] == "2026-01-01 08:00:00"

