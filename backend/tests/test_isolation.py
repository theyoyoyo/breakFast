"""The tests' own settings and network guard (conftest.py): a developer's .env or shell can't change
results, and no test reaches the network."""

import socket
from pathlib import Path

import httpx
import pytest

import config
from services import llm


# Every setting config.py reads is at the tests' value, whatever the machine's .env or shell says
def test_settings_ignore_the_machine():
    assert config.OLLAMA_BASE_URL == "http://ollama.invalid"
    assert (config.DEMO_USER, config.API_DOCS, config.SERVE_FRONTEND) == (False, False, False)
    assert (config.OLLAMA_MODEL, config.OLLAMA_THINK, config.OLLAMA_ROUTES) == (config.DEFAULT_MODEL, None, {})
    assert (config.OLLAMA_NUM_CTX, config.OLLAMA_TIMEOUT, config.CORS_ORIGINS) == (8192, 150, ["*"])
    assert Path(config.DATABASE_PATH).parent != Path(config.__file__).resolve().parent


# Ollama counts as unreachable unless a test fakes it, so a call falls back without a connection
async def test_ollama_unreachable_by_default(no_network):
    assert await llm.check_llm_availability() is False
    with pytest.raises(llm.LLMUnavailableError):
        await llm.chat_json("system", [], {"type": "object"})
    assert no_network == []


# A real HTTP request, a name lookup or a connect to another host is refused and recorded, so the test fails
async def test_network_attempts_are_refused(no_network):
    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.ConnectError):
            await client.get("http://localhost:11434/api/tags")
    with httpx.Client() as client, pytest.raises(httpx.ConnectError):
        client.get("http://example.com/")
    with pytest.raises(httpx.ConnectError):
        socket.getaddrinfo("example.com", 80)
    for connect in (socket.socket.connect, socket.socket.connect_ex):
        with socket.socket() as sock, pytest.raises(httpx.ConnectError):
            connect(sock, ("192.0.2.1", 80))  # TEST-NET-1, refused before any packet is sent
    assert len(no_network) == 5
    no_network.clear()  # the attempts were the point; don't fail this test at teardown


# Lookups and connections on this machine stay allowed (the event loop's own socket pair needs them)
def test_local_sockets_allowed(no_network):
    assert socket.getaddrinfo("localhost", 80)
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        with socket.socket() as first, socket.socket() as second:
            first.connect(server.getsockname())
            assert second.connect_ex(server.getsockname()) == 0
    assert no_network == []
