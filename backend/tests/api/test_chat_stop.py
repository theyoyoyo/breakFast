"""
Tests for Stop and the one-request-per-user slot on the /chat socket (#266): Stop closes the model
call and saves no reply, a second request while one runs gets a note, every frame of a reply names
its chat, and the slot is freed however a request ends.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import asyncio
import json
import threading
from unittest.mock import patch

import aiosqlite
import httpx
import pytest
import pytest_asyncio
from starlette.testclient import TestClient

import database
from auth import create_token, hash_pin
from services import chat_tasks
from services.chat_tasks import BUSY_TEXTS
from tests.chat_socket import open_chat

MEAL = {"menu_name": "Plate", "menu": [{"name": "Olives", "amount": 5, "unit": "pcs", "ingredients": []}]}
MEAL_REPLY = "Try this.\n\n```json\n" + json.dumps(MEAL) + "\n```"


@pytest_asyncio.fixture
async def stop_setup(tmp_path, monkeypatch):
    """A user with two chats, 's1' and 's2'; returns (app, token, user_id)."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()
    async with aiosqlite.connect(db_path) as db:
        await db.execute("INSERT INTO users (name, pin_hash) VALUES ('ada', ?)", (hash_pin("123456"),))
        async with db.execute("SELECT id FROM users WHERE name = 'ada'") as cur:
            user_id = (await cur.fetchone())[0]
        await db.execute("INSERT INTO chat_sessions (id, user_id) VALUES ('s1', ?), ('s2', ?)", (user_id, user_id))
        await db.commit()
    from main import app
    return app, create_token(user_id), user_id


async def _set_language(user_id: int, language: str) -> None:
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO user_preferences (user_id, key, value) VALUES (?, 'response_language', ?)", (user_id, language),
        )
        await db.commit()


async def _saved() -> dict:
    """Every saved message per chat as (role, content), the suggestions and each chat's selected card."""
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        async with db.execute("SELECT session_id, role, content FROM chat_messages ORDER BY id") as cur:
            rows = await cur.fetchall()
        async with db.execute("SELECT COUNT(*) FROM suggested_meals") as cur:
            suggestions = (await cur.fetchone())[0]
        async with db.execute("SELECT id, selected_message_id FROM chat_sessions ORDER BY id") as cur:
            selected = {r[0]: r[1] for r in await cur.fetchall()}
    messages = {}
    for session_id, role, content in rows:
        messages.setdefault(session_id, []).append((role, content))
    return {"messages": messages, "suggestions": suggestions, "selected": selected}


async def _wait_for(flag: threading.Event) -> None:
    """Wait on the app's loop until the test thread sets the flag."""
    while not flag.is_set():
        await asyncio.sleep(0.005)


def _until(ws, kind: str) -> list[dict]:
    """Every frame the socket receives up to and including the first of this type."""
    received = []
    while True:
        received.append(ws.receive_json())
        if received[-1]["type"] == kind:
            return received


class _HeldReply:
    """The chat model: its first words at once, the rest once the test sets `go`; Stop cancels it meanwhile."""

    def __init__(self):
        self.calls = 0
        self.go = threading.Event()
        self.cancelled = threading.Event()

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        yield "Hel"
        try:
            await _wait_for(self.go)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        yield "lo"


class _HeldOllamaStream(httpx.AsyncByteStream):
    """Ollama's streamed reply over HTTP: the first words, then nothing more until the request is closed."""

    def __init__(self):
        self.closed = threading.Event()

    async def __aiter__(self):
        yield b'{"message": {"content": "Hel"}, "done": false}\n'
        await asyncio.Event().wait()

    async def aclose(self):
        self.closed.set()


def _fake_ollama(monkeypatch, handler) -> list[httpx.AsyncClient]:
    """Ollama up, its HTTP calls answered by `handler`; returns the clients the calls opened."""
    from services import llm

    real_client = httpx.AsyncClient
    clients = []

    def client(*args, **kwargs):
        clients.append(real_client(*args, **{**kwargs, "transport": httpx.MockTransport(handler)}))
        return clients[-1]

    async def reachable():
        return True

    monkeypatch.setattr(llm, "check_llm_availability", reachable)
    monkeypatch.setattr(llm.httpx, "AsyncClient", client)
    return clients


# Stop during a chat reply closes Ollama's stream and its client, saves no reply (the typed message stays), and frees the slot
async def test_stop_during_chat_reply_closes_the_ollama_stream(stop_setup, monkeypatch):
    app, token, user_id = stop_setup
    stream = _HeldOllamaStream()
    clients = _fake_ollama(monkeypatch, lambda request: httpx.Response(200, stream=stream))

    with open_chat(TestClient(app), token) as ws:
        ws.send_text(json.dumps({"message": "Something warm?", "session_id": "s1"}))
        assert ws.receive_json() == {"type": "token", "content": "Hel", "session_id": "s1"}
        ws.send_text(json.dumps({"type": "stop"}))
        assert ws.receive_json() == {"type": "stopped", "session_id": "s1"}
        assert stream.closed.is_set()
        assert clients and all(c.is_closed for c in clients)
        assert not chat_tasks.is_busy(user_id)

    assert (await _saved())["messages"] == {"s1": [("user", "Something warm?")]}


# Stop during a Suggest press ends the pipeline: no message, no suggestion and no selected card is saved
async def test_stop_during_suggest_saves_nothing_and_selects_nothing(stop_setup):
    app, token, user_id = stop_setup
    cancelled = threading.Event()

    async def pipeline(**kwargs):
        yield {"type": "progress", "step": "drafting"}
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        yield {"type": "done", "content": MEAL_REPLY}

    with patch("routers.chat.run_suggestion_pipeline", pipeline):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            assert ws.receive_json() == {"type": "progress", "step": "drafting", "session_id": "s1"}
            ws.send_text(json.dumps({"type": "stop"}))
            assert ws.receive_json() == {"type": "stopped", "session_id": "s1"}
            assert cancelled.is_set()

    assert await _saved() == {"messages": {}, "suggestions": 0, "selected": {"s1": None, "s2": None}}


# A Suggest press's structured call to Ollama is closed when the press is stopped
async def test_stopped_structured_call_closes_its_client(monkeypatch):
    from services import llm

    cancelled = asyncio.Event()

    async def handler(request):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    clients = _fake_ollama(monkeypatch, handler)
    call = asyncio.create_task(llm.chat_json("system", [{"role": "user", "content": "hi"}], schema={"type": "object"}))
    while not clients:
        await asyncio.sleep(0.005)
    await asyncio.sleep(0.02)
    call.cancel()
    await asyncio.wait({call})

    assert call.cancelled() and cancelled.is_set()
    assert clients[0].is_closed


# Stop once the reply is made waits for its save, which runs whole: the suggestion, its messages and the selected card
async def test_stop_while_saving_lets_the_save_finish(stop_setup):
    app, token, _ = stop_setup
    from routers import chat

    entered, go = threading.Event(), threading.Event()
    real_save = chat._save_suggestion

    async def held_save(*args, **kwargs):
        entered.set()
        await _wait_for(go)
        return await real_save(*args, **kwargs)

    async def pipeline(**kwargs):
        yield {"type": "done", "content": MEAL_REPLY}

    with patch("routers.chat.run_suggestion_pipeline", pipeline), patch("routers.chat._save_suggestion", held_save):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            assert entered.wait(5)
            ws.send_text(json.dumps({"type": "stop"}))
            go.set()
            frames = _until(ws, "stopped")

    assert [f["type"] for f in frames] == ["done", "meal_logged", "stopped"]
    saved = await _saved()
    assert saved["messages"]["s1"][0] == ("user", "Suggest Breakfast")
    assert saved["suggestions"] == 1 and saved["selected"]["s1"] is not None


# Stop with nothing running is answered at once, with no chat named
async def test_stop_with_nothing_running_is_acknowledged(stop_setup):
    app, token, _ = stop_setup
    with open_chat(TestClient(app), token) as ws:
        ws.send_text(json.dumps({"type": "stop"}))
        assert ws.receive_json() == {"type": "stopped", "session_id": None}


# A second message on the same device while a reply runs gets the busy note, starts no model call and isn't saved
async def test_second_request_on_the_same_device_gets_the_note(stop_setup):
    app, token, _ = stop_setup
    reply = _HeldReply()

    with patch("routers.chat.stream_response", reply):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "First", "session_id": "s1"}))
            assert ws.receive_json()["content"] == "Hel"
            ws.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            assert ws.receive_json() == {"type": "busy", "content": BUSY_TEXTS["en"], "session_id": "s1"}
            ws.send_text(json.dumps({"message": "Second", "session_id": "s2"}))
            assert ws.receive_json() == {"type": "busy", "content": BUSY_TEXTS["en"], "session_id": "s2"}
            assert reply.calls == 1
            ws.send_text(json.dumps({"type": "stop"}))
            _until(ws, "stopped")
            assert reply.cancelled.is_set()

    assert (await _saved())["messages"] == {"s1": [("user", "First")]}


# A message from the user's other device while a reply runs gets the note in the reply language and starts no model call
async def test_second_request_on_another_device_gets_the_note(stop_setup):
    app, token, user_id = stop_setup
    await _set_language(user_id, "tr")
    reply = _HeldReply()

    with patch("routers.chat.stream_response", reply), TestClient(app) as client:
        with open_chat(client, token) as phone, open_chat(client, token) as desktop:
            phone.send_text(json.dumps({"message": "First", "session_id": "s1"}))
            assert phone.receive_json()["content"] == "Hel"
            desktop.send_text(json.dumps({"message": "Other", "session_id": "s2"}))
            # The phone's typed message was pushed to the desktop first
            frames = _until(desktop, "busy")
            assert frames[-1] == {"type": "busy", "content": BUSY_TEXTS["tr"], "session_id": "s2"}
            assert reply.calls == 1
            # The phone's reply goes on, and the desktop can ask once it's done
            reply.go.set()
            assert _until(phone, "done")[-1]["content"] == "Hello"
            desktop.send_text(json.dumps({"message": "Other", "session_id": "s2"}))
            assert _until(desktop, "done")[-1]["content"] == "Hello"

    assert (await _saved())["messages"] == {
        "s1": [("user", "First"), ("assistant", "Hello")],
        "s2": [("user", "Other"), ("assistant", "Hello")],
    }


# A reply still on its way when the device switches chats keeps its chat: its frames name it and it's saved there
async def test_reply_stays_in_its_chat_after_switching(stop_setup):
    app, token, _ = stop_setup
    reply = _HeldReply()

    with patch("routers.chat.stream_response", reply):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "In the first chat", "session_id": "s1"}))
            assert ws.receive_json() == {"type": "token", "content": "Hel", "session_id": "s1"}
            ws.send_text(json.dumps({"session_id": "s2"}))
            reply.go.set()
            frames = _until(ws, "done")
            assert [(f["type"], f["session_id"]) for f in frames] == [("token", "s1"), ("done", "s1")]
            # The socket is on the second chat now, so a message without a chat goes there
            ws.send_text(json.dumps({"message": "In the second chat"}))
            assert _until(ws, "done")[-1]["session_id"] == "s2"

    assert (await _saved())["messages"] == {
        "s1": [("user", "In the first chat"), ("assistant", "Hello")],
        "s2": [("user", "In the second chat"), ("assistant", "Hello")],
    }


async def _crashing_stream(*args, **kwargs):
    raise RuntimeError("boom")
    yield


async def _unreachable_stream(*args, **kwargs):
    from services.llm import LLMUnavailableError

    raise LLMUnavailableError("down")
    yield


async def _crashing_pipeline(**kwargs):
    raise RuntimeError("boom")
    yield


async def _deleting_pipeline(**kwargs):
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        await db.execute("DELETE FROM chat_sessions WHERE id = 's1'")
        await db.commit()
    yield {"type": "done", "content": MEAL_REPLY}


async def _quick_reply(*args, **kwargs):
    yield "Fine."


async def _quick_pipeline(**kwargs):
    yield {"type": "done", "content": "Fine."}


# However a request ends (a crash, Ollama down, a failed pipeline, its chat deleted), the slot is free and the next one is answered
@pytest.mark.parametrize("target, fake, kind", [
    ("routers.chat.stream_response", _crashing_stream, "chat"),
    ("routers.chat.stream_response", _unreachable_stream, "chat"),
    ("routers.chat.run_suggestion_pipeline", _crashing_pipeline, "suggest"),
    ("routers.chat.run_suggestion_pipeline", _deleting_pipeline, "suggest"),
])
async def test_slot_is_free_after_every_ending(stop_setup, target, fake, kind):
    app, token, user_id = stop_setup
    with patch(target, fake):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "First", "type": kind, "session_id": "s1"}))
            last = ws.receive_json()
            while last["type"] not in ("done", "error"):
                last = ws.receive_json()
            assert last["content" if last["type"] == "done" else "message"] not in BUSY_TEXTS.values()
            assert not chat_tasks.is_busy(user_id)

    with patch("routers.chat.stream_response", _quick_reply), patch("routers.chat.run_suggestion_pipeline", _quick_pipeline):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "Next", "type": kind, "session_id": "s2"}))
            assert _until(ws, "done")[-1]["content"] == "Fine."


# An unexpected failure while saving closes the socket, so the device stops waiting, and frees the slot
async def test_failed_save_closes_the_socket_and_frees_the_slot(stop_setup):
    app, token, user_id = stop_setup
    from starlette.websockets import WebSocketDisconnect

    async def broken_save(*args, **kwargs):
        raise RuntimeError("database gone")

    with patch("routers.chat.run_suggestion_pipeline", _quick_pipeline), \
         patch("routers.chat._save_message", broken_save):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_json()
    assert closed.value.code == 1011
    assert not chat_tasks.is_busy(user_id)


# A request stopped before its task ever ran still frees the slot (a phone's tap can send Stop right behind Suggest)
async def test_stop_before_the_task_runs_frees_the_slot():
    ran = []

    async def work():
        ran.append(True)

    request = chat_tasks.claim(7, "s1")
    chat_tasks.start(7, request, work())
    # No await between start and stop, so the task is cancelled before its first step
    assert await chat_tasks.stop(request) is True
    assert ran == []
    assert not chat_tasks.is_busy(7)


# Suggest and Stop sent back to back are both answered, the slot is free, and the next press runs
async def test_suggest_then_stop_at_once_leaves_the_user_free(stop_setup):
    app, token, user_id = stop_setup
    with patch("routers.chat.run_suggestion_pipeline", _quick_pipeline):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            ws.send_text(json.dumps({"type": "stop"}))
            _until(ws, "stopped")
            assert not chat_tasks.is_busy(user_id)
            ws.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            frames = _until(ws, "done")
            assert all(f["type"] != "busy" for f in frames)
            assert frames[-1]["content"] == "Fine."


# A device that got the busy note is told once the running request ends, so it can clear the note
async def test_busy_device_is_told_when_the_request_ends(stop_setup):
    app, token, _ = stop_setup
    reply = _HeldReply()

    with patch("routers.chat.stream_response", reply), TestClient(app) as client:
        with open_chat(client, token) as phone, open_chat(client, token) as desktop:
            phone.send_text(json.dumps({"message": "First", "session_id": "s1"}))
            assert phone.receive_json()["content"] == "Hel"
            for _ in range(2):
                desktop.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s2"}))
                assert _until(desktop, "busy")[-1]["session_id"] == "s2"
            reply.go.set()
            assert _until(phone, "done")[-1]["content"] == "Hello"
            assert _until(desktop, "request_ended")[-1] == {"type": "request_ended"}
            # Told once, though it got the note twice: the next frames answer its new message
            desktop.send_text(json.dumps({"message": "Hi", "session_id": "s2"}))
            assert "request_ended" not in [f["type"] for f in _until(desktop, "done")]


# The busy device is told about a stopped request too
async def test_busy_device_is_told_when_the_request_is_stopped(stop_setup):
    app, token, _ = stop_setup
    reply = _HeldReply()

    with patch("routers.chat.stream_response", reply), TestClient(app) as client:
        with open_chat(client, token) as phone, open_chat(client, token) as desktop:
            phone.send_text(json.dumps({"message": "First", "session_id": "s1"}))
            assert phone.receive_json()["content"] == "Hel"
            desktop.send_text(json.dumps({"message": "Other", "session_id": "s2"}))
            _until(desktop, "busy")
            phone.send_text(json.dumps({"type": "stop"}))
            _until(phone, "stopped")
            assert _until(desktop, "request_ended")[-1] == {"type": "request_ended"}


async def _retry_pipeline(**kwargs):
    from services.pipeline import RETRY_TEXTS

    yield {"type": "done", "content": RETRY_TEXTS["en"]}


async def _saved_kinds() -> list[tuple]:
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        async with db.execute("SELECT role, kind FROM chat_messages ORDER BY id") as cur:
            return [tuple(r) for r in await cur.fetchall()]


# A press that got the retry note saves it as a notice, and the chat persona's next history leaves it out
async def test_retry_note_is_saved_as_a_notice_and_read_by_no_persona(stop_setup):
    from services.pipeline import RETRY_TEXTS

    app, token, _ = stop_setup
    histories = []

    async def chat_model(system_prompt, history, message, **kwargs):
        histories.append(history)
        yield "Sure."

    with patch("routers.chat.run_suggestion_pipeline", _retry_pipeline), patch("routers.chat.stream_response", chat_model):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            assert _until(ws, "done")[-1]["content"] == RETRY_TEXTS["en"]
            ws.send_text(json.dumps({"message": "Something warm", "session_id": "s1"}))
            _until(ws, "done")

    assert await _saved_kinds() == [("user", None), ("assistant", "notice"), ("user", None), ("assistant", None)]
    assert all(m["content"] != RETRY_TEXTS["en"] for m in histories[0])


# A chat reply that is a lyric (Ollama down) is saved as a notice, and a real reply is plain
async def test_lyric_reply_is_a_notice(stop_setup):
    app, token, _ = stop_setup
    with patch("routers.chat.stream_response", _unreachable_stream):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "Hi", "session_id": "s1"}))
            _until(ws, "done")
    with patch("routers.chat.stream_response", _quick_reply):
        with open_chat(TestClient(app), token) as ws:
            ws.send_text(json.dumps({"message": "Hi again", "session_id": "s1"}))
            _until(ws, "done")
    assert await _saved_kinds() == [("user", None), ("assistant", "notice"), ("user", None), ("assistant", None)]


# A device that got the busy note can stop the request running on another device: the model call ends, both devices hear it, the slot is free
async def test_busy_device_stops_the_other_devices_request(stop_setup):
    app, token, user_id = stop_setup
    reply = _HeldReply()

    with patch("routers.chat.stream_response", reply), TestClient(app) as client:
        with open_chat(client, token) as phone, open_chat(client, token) as desktop:
            phone.send_text(json.dumps({"message": "First", "session_id": "s1"}))
            assert phone.receive_json()["content"] == "Hel"
            desktop.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s2"}))
            _until(desktop, "busy")
            desktop.send_text(json.dumps({"type": "stop"}))
            frames = _until(desktop, "stopped")
            assert frames[-1] == {"type": "stopped", "session_id": "s1"}
            assert _until(phone, "stopped")[-1] == {"type": "stopped", "session_id": "s1"}
            assert reply.cancelled.is_set()
            assert not chat_tasks.is_busy(user_id)

    # The typed message stays, and no reply is saved
    assert (await _saved())["messages"] == {"s1": [("user", "First")]}


class _HeldPipeline:
    """The suggestion pipeline: its first step at once, the rest once the test sets `go`; Stop cancels it meanwhile."""

    def __init__(self):
        self.go = threading.Event()
        self.cancelled = threading.Event()

    async def __call__(self, **kwargs):
        yield {"type": "progress", "step": "drafting"}
        try:
            await _wait_for(self.go)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        yield {"type": "progress", "step": "analyzing"}
        yield {"type": "done", "content": MEAL_REPLY}


# A socket opened while a Suggest press runs (a reloaded phone) is told where it stands, then gets its later frames and its card
async def test_reopened_socket_picks_up_the_running_suggest(stop_setup):
    app, token, _ = stop_setup
    pipeline = _HeldPipeline()

    with patch("routers.chat.run_suggestion_pipeline", pipeline), TestClient(app) as client:
        with open_chat(client, token) as old:
            old.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            assert old.receive_json()["step"] == "drafting"
            with open_chat(client, token) as reloaded:
                assert reloaded.receive_json() == {
                    "type": "running", "session_id": "s1", "kind": "suggest", "step": "drafting", "content": "",
                }
                pipeline.go.set()
                frames = _until(reloaded, "meal_logged")
                reply = [f for f in frames if f["type"] != "session_updated"]
                assert [(f["type"], f["session_id"]) for f in reply] == [
                    ("progress", "s1"), ("done", "s1"), ("meal_logged", "s1"),
                ]
                assert reply[0]["step"] == "analyzing"
                assert reply[1]["message_id"] is not None
            assert _until(old, "meal_logged")[-1]["meal"]["menu_name"] == "Plate"


# A socket opened while a chat reply streams gets the words so far in the running frame, then the later tokens and the reply
async def test_reopened_socket_picks_up_the_streaming_reply(stop_setup):
    app, token, _ = stop_setup
    reply = _HeldReply()

    with patch("routers.chat.stream_response", reply), TestClient(app) as client:
        with open_chat(client, token) as old:
            old.send_text(json.dumps({"message": "Something warm?", "session_id": "s1"}))
            assert old.receive_json()["content"] == "Hel"
            with open_chat(client, token) as reloaded:
                assert reloaded.receive_json() == {
                    "type": "running", "session_id": "s1", "kind": "chat", "step": None, "content": "Hel",
                }
                reply.go.set()
                frames = [f for f in _until(reloaded, "done") if f["type"] != "session_updated"]
                assert frames[0] == {"type": "token", "content": "lo", "session_id": "s1"}
                assert [(f["type"], f["content"], f["session_id"]) for f in frames[1:]] == [("done", "Hello", "s1")]
            _until(old, "done")


# Stop from the reopened socket cancels the request: the model call ends, both sockets hear it, nothing is saved and the slot is free
async def test_reopened_socket_stops_the_running_request(stop_setup):
    app, token, user_id = stop_setup
    pipeline = _HeldPipeline()

    with patch("routers.chat.run_suggestion_pipeline", pipeline), TestClient(app) as client:
        with open_chat(client, token) as old:
            old.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            old.receive_json()
            with open_chat(client, token) as reloaded:
                assert reloaded.receive_json()["type"] == "running"
                reloaded.send_text(json.dumps({"type": "stop"}))
                assert reloaded.receive_json() == {"type": "stopped", "session_id": "s1"}
                assert pipeline.cancelled.is_set()
                assert not chat_tasks.is_busy(user_id)
            assert _until(old, "stopped")[-1] == {"type": "stopped", "session_id": "s1"}

    assert await _saved() == {"messages": {}, "suggestions": 0, "selected": {"s1": None, "s2": None}}


# A socket opened while nothing runs gets no running frame: its first frame answers its own Stop
async def test_socket_opened_while_idle_gets_no_running_frame(stop_setup):
    app, token, _ = stop_setup
    with open_chat(TestClient(app), token) as ws:
        ws.send_text(json.dumps({"type": "stop"}))
        assert ws.receive_json() == {"type": "stopped", "session_id": None}


# Another user's socket opened while a request runs gets no running frame, none of its frames, and its Stop leaves that request running
async def test_other_user_never_picks_up_the_running_request(stop_setup):
    app, token, user_id = stop_setup
    async with aiosqlite.connect(database.DATABASE_PATH) as db:
        cur = await db.execute("INSERT INTO users (name, pin_hash) VALUES ('bob', ?)", (hash_pin("654321"),))
        await db.commit()
        bob_token = create_token(cur.lastrowid)
    reply = _HeldReply()

    with patch("routers.chat.stream_response", reply), TestClient(app) as client:
        with open_chat(client, token) as ada:
            ada.send_text(json.dumps({"message": "Something warm?", "session_id": "s1"}))
            assert ada.receive_json()["content"] == "Hel"
            with open_chat(client, bob_token) as bob:
                bob.send_text(json.dumps({"type": "stop"}))
                assert bob.receive_json() == {"type": "stopped", "session_id": None}
                assert chat_tasks.is_busy(user_id) and not reply.cancelled.is_set()
                reply.go.set()
                assert _until(ada, "done")[-1]["content"] == "Hello"
                # Bob's next frame answers his own Stop again: nothing of Ada's reply reached him
                bob.send_text(json.dumps({"type": "stop"}))
                assert bob.receive_json() == {"type": "stopped", "session_id": None}


# A request that fails unexpectedly tells the sockets that picked it up it has ended, as a Stop would, and frees the slot
async def test_reopened_socket_is_told_when_the_request_fails(stop_setup):
    app, token, user_id = stop_setup
    pipeline = _HeldPipeline()

    async def broken_save(*args, **kwargs):
        raise RuntimeError("database gone")

    with patch("routers.chat.run_suggestion_pipeline", pipeline), patch("routers.chat._save_message", broken_save), \
         TestClient(app) as client:
        with open_chat(client, token) as old:
            old.send_text(json.dumps({"message": "Suggest Breakfast", "type": "suggest", "session_id": "s1"}))
            old.receive_json()
            with open_chat(client, token) as reloaded:
                assert reloaded.receive_json()["type"] == "running"
                pipeline.go.set()
                assert _until(reloaded, "stopped")[-1] == {"type": "stopped", "session_id": "s1"}
    # The slot is freed by the task's done callback, right after that frame: checked once the sockets closed
    assert not chat_tasks.is_busy(user_id)
