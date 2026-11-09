"""Tests for the options every Ollama call sends (context length, temperature)."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import config
from services import llm


class _FakeStream:
    """Stands in for httpx's streamed response: one reply line."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        yield '{"message": {"content": "Hi"}}'


def _mock_client():
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# A JSON call sends the configured num_ctx, plus the temperature only when one is given
@pytest.mark.parametrize("temperature, expected", [
    (0.6, {"num_ctx": 12288, "temperature": 0.6}),
    (None, {"num_ctx": 12288}),
])
async def test_chat_json_sends_num_ctx(monkeypatch, temperature, expected):
    monkeypatch.setattr(llm, "OLLAMA_NUM_CTX", 12288)
    response = MagicMock()
    response.json.return_value = {"message": {"content": "{}"}}
    client = _mock_client()
    client.post = AsyncMock(return_value=response)
    with patch("services.llm.check_llm_availability", return_value=True), \
         patch("services.llm.httpx.AsyncClient", return_value=client):
        await llm.chat_json("system", [], {"type": "object"}, temperature=temperature)

    assert client.post.call_args.kwargs["json"]["options"] == expected


# A streamed call sends the configured num_ctx, plus the temperature only when one is given
@pytest.mark.parametrize("temperature, expected", [
    (0.3, {"num_ctx": 12288, "temperature": 0.3}),
    (None, {"num_ctx": 12288}),
])
async def test_chat_stream_sends_num_ctx(monkeypatch, temperature, expected):
    monkeypatch.setattr(llm, "OLLAMA_NUM_CTX", 12288)
    client = _mock_client()
    client.stream = MagicMock(return_value=_FakeStream())
    with patch("services.llm.check_llm_availability", return_value=True), \
         patch("services.llm.httpx.AsyncClient", return_value=client):
        tokens = [t async for t in llm.chat_stream("system", [], temperature=temperature)]

    assert tokens == ["Hi"]
    assert client.stream.call_args.kwargs["json"]["options"] == expected


# OLLAMA_NUM_CTX from the environment replaces the 8192 default
def test_num_ctx_env_var_overrides_default(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)  # a local .env can't interfere
    try:
        monkeypatch.delenv("OLLAMA_NUM_CTX", raising=False)
        assert importlib.reload(config).OLLAMA_NUM_CTX == 8192
        monkeypatch.setenv("OLLAMA_NUM_CTX", "16384")
        assert importlib.reload(config).OLLAMA_NUM_CTX == 16384
    finally:
        monkeypatch.undo()
        importlib.reload(config)


# OLLAMA_THINK unset sends no think field (the model's own default); set, both calls send it
@pytest.mark.parametrize("think, expected", [(None, None), (False, False), (True, True)])
async def test_calls_send_think_only_when_set(monkeypatch, think, expected):
    monkeypatch.setattr(llm, "OLLAMA_THINK", think)
    response = MagicMock()
    response.json.return_value = {"message": {"content": "{}"}}
    client = _mock_client()
    client.post = AsyncMock(return_value=response)
    client.stream = MagicMock(return_value=_FakeStream())
    with patch("services.llm.check_llm_availability", return_value=True), \
         patch("services.llm.httpx.AsyncClient", return_value=client):
        await llm.chat_json("system", [], {"type": "object"})
        [t async for t in llm.chat_stream("system", [])]

    for payload in (client.post.call_args.kwargs["json"], client.stream.call_args.kwargs["json"]):
        assert payload.get("think") == expected
        assert ("think" in payload) == (think is not None)


# With a model set, OLLAMA_THINK reads true or false in any case; anything else leaves it unset
@pytest.mark.parametrize("value, expected", [("", None), ("true", True), ("False", False), ("maybe", None)])
def test_think_env_var(monkeypatch, value, expected):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    try:
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")
        monkeypatch.setenv("OLLAMA_THINK", value)
        assert importlib.reload(config).OLLAMA_THINK is expected
    finally:
        monkeypatch.undo()
        importlib.reload(config)


# With no model set, the default model runs with thinking off unless OLLAMA_THINK says otherwise
def test_default_model_thinks_off(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    try:
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        monkeypatch.delenv("OLLAMA_THINK", raising=False)
        reloaded = importlib.reload(config)
        assert (reloaded.OLLAMA_MODEL, reloaded.OLLAMA_THINK) == (reloaded.DEFAULT_MODEL, False)
        monkeypatch.setenv("OLLAMA_THINK", "true")
        assert importlib.reload(config).OLLAMA_THINK is True
    finally:
        monkeypatch.undo()
        importlib.reload(config)


# OLLAMA_MODEL_<KEY> gives a task or reply language its own model, with its own OLLAMA_THINK_<KEY> (#192)
def test_routes_env_vars(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    try:
        monkeypatch.setenv("OLLAMA_MODEL_SHOPPING", "gemma4:e2b-it-q4_K_M")
        monkeypatch.setenv("OLLAMA_THINK_SHOPPING", "true")
        monkeypatch.setenv("OLLAMA_MODEL_TR", "gemma4:e2b-it-q4_K_M")
        monkeypatch.setenv("OLLAMA_MODEL_BREAKFAST", "ignored:1b")
        routes = importlib.reload(config).OLLAMA_ROUTES
        assert routes == {"tr": ("gemma4:e2b-it-q4_K_M", None), "shopping": ("gemma4:e2b-it-q4_K_M", True)}
    finally:
        monkeypatch.undo()
        importlib.reload(config)


# A call uses its reply language's model, else its task's, else OLLAMA_MODEL with OLLAMA_THINK, and sends
# only its own model's think value (#192)
async def test_calls_use_the_model_for_their_task_and_language(monkeypatch):
    monkeypatch.setattr(llm, "OLLAMA_ROUTES", {"tr": ("turkish:4b", True), "shopping": ("shop:2b", None)})
    monkeypatch.setattr(llm, "OLLAMA_MODEL", "main:4b")
    monkeypatch.setattr(llm, "OLLAMA_THINK", False)
    assert llm.model_for("shopping", "tr") == ("turkish:4b", True)
    assert llm.model_for("shopping", "en") == ("shop:2b", None)
    assert llm.model_for("chat", "en") == llm.model_for() == ("main:4b", False)
    response = MagicMock()
    response.json.return_value = {"message": {"content": "{}"}}
    client = _mock_client()
    client.post = AsyncMock(return_value=response)
    client.stream = MagicMock(return_value=_FakeStream())
    with patch("services.llm.check_llm_availability", return_value=True), \
         patch("services.llm.httpx.AsyncClient", return_value=client):
        await llm.chat_json("system", [], {"type": "object"}, task="shopping", language="en")
        [t async for t in llm.chat_stream("system", [], task="chat", language="tr")]
    sent, streamed = client.post.call_args.kwargs["json"], client.stream.call_args.kwargs["json"]
    assert sent["model"] == "shop:2b" and "think" not in sent
    assert streamed["model"] == "turkish:4b" and streamed["think"] is True
