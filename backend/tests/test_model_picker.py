"""Tests for the model picker page (tools/model_picker.py, #240), with Ollama faked."""

import json
from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from services import llm
from services.model_settings import ModelSettingsFile
from tools import model_picker
from tools.model_picker import create_app, is_local_host, is_local_origin, ollama_models

MODELS = {"gemma4:e4b-it-qat": False, "qwen3:8b": True}


@pytest.fixture
def picker(tmp_path):
    """The picker's app on a temp settings file, with Ollama listing MODELS."""
    path = tmp_path / "model_settings.json"

    async def fake_models(url):
        return dict(MODELS)

    with patch("tools.model_picker.ollama_models", fake_models):
        yield create_app("http://ollama.test", path), path


def _client(app, host="127.0.0.1:8765", **headers):
    return AsyncClient(transport=ASGITransport(app=app), base_url=f"http://{host}", headers=headers)


# main() serves the page on 127.0.0.1 only, on the port given, and has no option for another address
def test_binds_to_localhost_only():
    with patch("uvicorn.run") as run:
        model_picker.main(["--port", "9001"])
    assert run.call_args.kwargs["host"] == "127.0.0.1" and run.call_args.kwargs["port"] == 9001
    with patch("uvicorn.run") as run:
        model_picker.main([])
    assert run.call_args.kwargs == {"host": "127.0.0.1", "port": 8765, "log_level": "warning"}
    with pytest.raises(SystemExit):
        model_picker.parse_args(["--host", "0.0.0.0"])


# Only this machine's names count as a local Host or Origin, on any port (a tunnel may use another)
def test_local_names():
    assert all(is_local_host(h) for h in ["127.0.0.1:8765", "localhost:9000", "[::1]:8765", "LOCALHOST"])
    assert not any(is_local_host(h) for h in [None, "", "evil.example", "127.0.0.1.evil.example:8765", "[::2]:80"])
    assert all(is_local_origin(o) for o in [None, "http://127.0.0.1:8765", "http://localhost:9000"])
    assert not any(is_local_origin(o) for o in ["null", "http://evil.example", "file://", "http://localhost.evil.example"])


# A request with another Host (DNS rebinding) is refused, the page and a save alike, and nothing is written
async def test_bad_host_rejected(picker):
    app, path = picker
    async with _client(app, host="evil.example:8765") as client:
        page = await client.get("/")
        saved = await client.post("/save", json={"chat": {"model": "qwen3:8b"}})
    assert page.status_code == saved.status_code == 403
    assert "qwen3" not in page.text and not path.exists()


# A save from another site's page (its Origin) is refused, even with a local Host
async def test_cross_site_save_rejected(picker):
    app, path = picker
    async with _client(app, origin="http://evil.example") as client:
        saved = await client.post("/save", json={"chat": {"model": "qwen3:8b"}})
    assert saved.status_code == 403 and not path.exists()


# The page lists Ollama's models per task and language, marks which can think, and escapes their names
async def test_page_lists_models_and_escapes(tmp_path):
    async def fake_models(url):
        return {"<script>alert(1)</script>": False, "qwen3:8b": True}

    with patch("tools.model_picker.ollama_models", fake_models):
        async with _client(create_app("http://ollama.test", tmp_path / "s.json")) as client:
            page = (await client.get("/")).text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert page.count('value="qwen3:8b" data-thinks="1"') == 9
    assert page.count('data-thinks="0"') == 9
    assert "default (.env" in page and "applies from the next request" in page.lower()


# A save writes the file and the backend's next call uses it, with no restart
async def test_save_reaches_the_backend(picker, monkeypatch):
    app, path = picker
    monkeypatch.setattr(llm, "MODEL_SETTINGS_PATH", path)
    monkeypatch.setattr(llm, "_model_settings", ModelSettingsFile())
    async with _client(app, origin="http://127.0.0.1:8765") as client:
        saved = await client.post("/save", json={
            "chat": {"model": "qwen3:8b", "think": True}, "tr": {"model": "gemma4:e4b-it-qat"}, "plan": None,
        })
        page = (await client.get("/")).text
    assert saved.status_code == 200
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "chat": {"model": "qwen3:8b", "think": True}, "tr": {"model": "gemma4:e4b-it-qat"},
    }
    assert llm.model_for("chat", "en") == ("qwen3:8b", True)
    assert 'value="qwen3:8b" data-thinks="1" selected' in page


# The think switch is only for a model that reports thinking: a think value for another is refused
async def test_think_only_for_thinking_models(picker):
    app, path = picker
    async with _client(app) as client:
        refused = await client.post("/save", json={"chat": {"model": "gemma4:e4b-it-qat", "think": False}})
        allowed = await client.post("/save", json={"chat": {"model": "qwen3:8b", "think": False}})
    assert refused.status_code == 422 and refused.json() == {"detail": model_picker.CANT_THINK}
    assert allowed.status_code == 200


# A body that isn't the settings' shape, names an unknown key or a model Ollama lacks gets a fixed 422 without its input
@pytest.mark.parametrize("body, detail", [
    ({"chat": {"model": "missing:1b"}}, model_picker.NOT_INSTALLED),
    ({"breakfast": {"model": "qwen3:8b"}}, model_picker.UNKNOWN_KEY),
    ({"chat": "qwen3:8b"}, model_picker.BAD_SHAPE),
    ({"chat": {"model": ""}}, model_picker.BAD_SHAPE),
    ({"chat": {"model": "qwen3:8b", "think": "yes"}}, model_picker.BAD_SHAPE),
    ({"chat": {"model": "qwen3:8b", "extra": 1}}, model_picker.BAD_SHAPE),
    (["qwen3:8b"], model_picker.BAD_SHAPE),
])
async def test_bad_bodies_refused(picker, body, detail):
    app, path = picker
    async with _client(app) as client:
        reply = await client.post("/save", json=body)
    assert reply.status_code == 422 and reply.json() == {"detail": detail}
    assert "missing" not in reply.text and "breakfast" not in reply.text and not path.exists()


# A body that isn't JSON, or is too big, is refused before Ollama is asked
async def test_not_json_or_too_big(picker):
    app, path = picker
    async with _client(app) as client:
        form = await client.post("/save", data={"chat": "qwen3:8b"})
        broken = await client.post("/save", content=b"{nope", headers={"Content-Type": "application/json"})
        big = await client.post("/save", content=b" " * (model_picker.MAX_BODY + 1), headers={"Content-Type": "application/json"})
    assert (form.status_code, broken.status_code, big.status_code) == (415, 422, 413)
    assert not path.exists()


# A model saved earlier that Ollama no longer lists can be kept as it is, so the other keys can still be saved
async def test_saved_model_can_stay(picker):
    app, path = picker
    path.write_text(json.dumps({"tr": {"model": "old:4b", "think": True}}), encoding="utf-8")
    async with _client(app) as client:
        page = (await client.get("/")).text
        kept = await client.post("/save", json={"tr": {"model": "old:4b", "think": True}, "chat": {"model": "qwen3:8b"}})
        changed = await client.post("/save", json={"tr": {"model": "old:4b", "think": False}})
    assert "old:4b (not in Ollama&#x27;s list)" in page
    assert kept.status_code == 200 and changed.status_code == 422


# With Ollama down the page still opens with a note, and a save is refused without writing
async def test_ollama_down(tmp_path):
    async def no_models(url):
        return None

    with patch("tools.model_picker.ollama_models", no_models):
        async with _client(create_app("http://ollama.test", tmp_path / "s.json")) as client:
            page = await client.get("/")
            saved = await client.post("/save", json={"chat": None})
    assert page.status_code == 200 and "isn&#x27;t reachable" in page.text
    assert saved.status_code == 503 and not (tmp_path / "s.json").exists()


# Ollama's list comes from /api/tags, and a model thinks only when /api/show lists the thinking capability
async def test_ollama_models_reads_capabilities():
    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3:8b"}, {"name": "gemma4:e4b-it-qat"}]})
        name = json.loads(request.content)["model"]
        caps = ["completion", "thinking"] if name == "qwen3:8b" else ["completion", "vision"]
        return httpx.Response(200, json={"capabilities": caps})

    real = httpx.AsyncClient
    with patch("tools.model_picker.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)):
        assert await ollama_models("http://ollama.test") == {"qwen3:8b": True, "gemma4:e4b-it-qat": False}

    def down(request):
        raise httpx.ConnectError("refused")

    with patch("tools.model_picker.httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(down), **kw)):
        assert await ollama_models("http://ollama.test") is None
