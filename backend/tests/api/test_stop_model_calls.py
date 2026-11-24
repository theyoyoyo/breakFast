"""Stop for the REST calls that wait on the model (#288): a client that goes away mid-call cancels the
model call on the server, the route saves nothing and logs at info level, and the call itself closes
its connection to Ollama. The routes are driven as raw ASGI calls, so the test decides when the
client disconnects; the model is faked."""

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from services import llm
from services.stoppable import STOPPED_STATUS, RequestStopped, unless_stopped

MEAL = {"meal_name": "Oats", "ingredients": [], "menu_items": [{"name": "Oats", "amount": 50, "unit": "g", "ingredients": []}]}


class HangingModel:
    """A model call that never answers: `started` is set once it runs, `cancelled` once it's cancelled."""

    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = False

    async def _hang(self):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def call(self, *args, **kwargs):
        """Stands in for chat_json."""
        await self._hang()

    async def stream(self, *args, **kwargs):
        """Stands in for stream_response (an async generator)."""
        await self._hang()
        yield ""


async def call_then_disconnect(client, method: str, path: str, started: asyncio.Event, body=None) -> list[dict]:
    """Call the app as a raw ASGI request, disconnect once the model call has started, and return
    what the app sent back."""
    from main import app

    data = json.dumps(body).encode() if body is not None else b""
    gone = asyncio.Event()
    sent = []
    first = True

    async def receive():
        nonlocal first
        if first:
            first = False
            return {"type": "http.request", "body": data, "more_body": False}
        await gone.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "root_path": "", "query_string": b"",
        "headers": [
            (b"host", b"test"),
            (b"authorization", client.headers["Authorization"].encode()),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(data)).encode()),
        ],
        "client": ("127.0.0.1", 1), "server": ("test", 80),
    }
    running = asyncio.create_task(app(scope, receive, send))
    await asyncio.wait_for(started.wait(), 5)
    gone.set()
    await asyncio.wait_for(running, 5)
    return sent


def status_of(sent: list[dict]) -> int:
    """The status the app answered with."""
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def assert_stopped_quietly(caplog):
    """The stop is logged at info level, and nothing at error level."""
    assert any(r.levelno == logging.INFO and "Stopped by the client" in r.getMessage() for r in caplog.records)
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


# A disconnect mid-call cancels Suggest Shopping's model call and nothing new reaches the suggestions list
async def test_shopping_suggestions_stop_cancels_the_call(client, db, caplog):
    caplog.set_level(logging.INFO)
    model = HangingModel()
    with patch("routers.shopping.chat_json", model.call):
        sent = await call_then_disconnect(client, "POST", "/shopping/suggestions/generate", model.started, {"exclude": []})
    assert status_of(sent) == STOPPED_STATUS
    assert model.cancelled
    async with db.execute("SELECT COUNT(*) AS n FROM shopping_suggestions") as cur:
        assert (await cur.fetchone())["n"] == 0
    assert_stopped_quietly(caplog)


# A disconnect mid-call cancels the weekly analyst and the week's earlier analysis stays as it was
async def test_weekly_review_stop_cancels_the_call_and_keeps_nothing(client, caplog):
    caplog.set_level(logging.INFO)
    await client.post("/meals/", json=MEAL)
    earlier = json.dumps({"narrative": "Earlier week.", "scores": [], "lacking": [], "more_than_enough": []})

    async def answer(*args, **kwargs):
        return earlier

    with patch("routers.meals.chat_json", answer):
        assert (await client.post("/meals/weekly-review")).status_code == 200

    model = HangingModel()
    with patch("routers.meals.chat_json", model.call):
        sent = await call_then_disconnect(client, "POST", "/meals/weekly-review", model.started)
    assert status_of(sent) == STOPPED_STATUS
    assert model.cancelled
    kept = (await client.get("/meals/weekly-review")).json()
    assert kept["narrative"] == "Earlier week."
    assert_stopped_quietly(caplog)


# A disconnect mid-call cancels a meal's nutrition analysis and nothing is cached for the meal
async def test_meal_analysis_stop_cancels_the_call_and_caches_nothing(client, caplog):
    caplog.set_level(logging.INFO)
    meal = (await client.post("/meals/", json=MEAL)).json()
    model = HangingModel()
    with patch("routers.analyst.stream_response", model.stream):
        sent = await call_then_disconnect(
            client, "POST", "/analyst/analyze", model.started,
            {"meal_name": "Oats", "ingredients": ["oats"], "meal_id": meal["id"]},
        )
    assert status_of(sent) == STOPPED_STATUS
    assert model.cancelled
    assert (await client.get(f"/meals/{meal['id']}")).json()["cached_nutrition"] is None
    assert_stopped_quietly(caplog)


def fake_request(disconnect: asyncio.Event | None = None):
    """A request whose channel gives its empty body, then the disconnect once `disconnect` is set
    (never when it's None)."""
    first = True
    gone = disconnect or asyncio.Event()

    async def receive():
        nonlocal first
        if first:
            first = False
            return {"type": "http.request", "body": b"", "more_body": False}
        await gone.wait()
        return {"type": "http.disconnect"}

    return SimpleNamespace(receive=receive, method="POST", url=SimpleNamespace(path="/test"))


# Without a disconnect the helper returns the call's result
async def test_unless_stopped_returns_the_result():
    async def work():
        await asyncio.sleep(0)
        return "reply"

    assert await unless_stopped(fake_request(), work()) == "reply"


# An error from the call itself reaches the route unchanged, so its fixed-message handling still applies
async def test_unless_stopped_passes_the_call_error_on():
    async def work():
        raise llm.LLMUnavailableError("down")

    with pytest.raises(llm.LLMUnavailableError):
        await unless_stopped(fake_request(), work())


@pytest.fixture
def hanging_ollama(monkeypatch):
    """Ollama is up, but its HTTP connection never answers: records each request it got and
    whether the request was cancelled (its connection closed) while it waited."""
    seen = {"started": asyncio.Event(), "cancelled": False}

    async def reachable():
        return True

    async def handle(self, request):
        seen["started"].set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            seen["cancelled"] = True
            raise

    monkeypatch.setattr(llm, "check_llm_availability", reachable)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle)
    return seen


async def _stop_when_started(seen, work):
    """Run `work` through the helper and disconnect once Ollama got its request; the helper must raise RequestStopped."""
    gone = asyncio.Event()
    stopping = asyncio.ensure_future(unless_stopped(fake_request(gone), work))
    await asyncio.wait_for(seen["started"].wait(), 5)
    gone.set()
    with pytest.raises(RequestStopped):
        await asyncio.wait_for(stopping, 5)


# A stop cancels chat_json's HTTP request to Ollama, so its connection is closed
async def test_stop_closes_the_ollama_connection_for_a_json_call(hanging_ollama):
    await _stop_when_started(hanging_ollama, llm.chat_json("system", [{"role": "user", "content": "hi"}], {}))
    assert hanging_ollama["cancelled"]


# A stop cancels a streamed call's HTTP request to Ollama, so its connection is closed
async def test_stop_closes_the_ollama_connection_for_a_stream(hanging_ollama):
    async def collect():
        return "".join([chunk async for chunk in llm.stream_response("system", [], "hi")])

    await _stop_when_started(hanging_ollama, collect())
    assert hanging_ollama["cancelled"]
