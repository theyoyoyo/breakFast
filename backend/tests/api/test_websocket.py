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
from httpx import ASGITransport

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
    from services.llm import LLMUnavailableError, LLM_UNAVAILABLE_MESSAGE

    client = TestClient(app)

    # Mock build_system_prompt to return a simple string (avoids JSON template format issues)
    # and stream_response as an async generator that raises LLMUnavailableError
    async def mock_stream(*args, **kwargs):
        raise LLMUnavailableError(LLM_UNAVAILABLE_MESSAGE)
        yield  # makes this an async generator

    with patch("routers.chat.build_system_prompt", return_value="test prompt"), \
         patch("routers.chat.stream_response", mock_stream):
        with client.websocket_connect(f"/chat?token={token}") as ws:
            ws.send_text(json.dumps({"message": "hello"}))

            # Should get done message with fallback (LLM unavailable)
            msg = ws.receive_json()
            assert msg["type"] == "done"
            assert "aklım başımda değil" in msg["content"]
