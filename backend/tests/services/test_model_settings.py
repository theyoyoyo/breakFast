"""Tests for the model picker's settings file (#240): read on each call, again only when it changed."""

import json
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import llm
from services.model_settings import ModelSettingsFile, parse_model_settings, write_model_settings


def _write(path, data, bump=0):
    """Write the file as text and move its modified time, so a change within one clock tick still shows."""
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    stat = os.stat(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + bump * 1_000_000_000))


@pytest.fixture
def settings(tmp_path, monkeypatch):
    """A settings file in a temp folder, with `.env` giving shopping and tr routes of their own."""
    path = tmp_path / "model_settings.json"
    monkeypatch.setattr(llm, "MODEL_SETTINGS_PATH", path)
    monkeypatch.setattr(llm, "_model_settings", ModelSettingsFile())
    monkeypatch.setattr(llm, "OLLAMA_MODEL", "main:4b")
    monkeypatch.setattr(llm, "OLLAMA_THINK", None)
    monkeypatch.setattr(llm, "OLLAMA_ROUTES", {"shopping": ("env-shop:2b", True), "tr": ("env-tr:4b", None)})
    return path


# A missing file changes nothing: every call uses `.env`'s routes, then OLLAMA_MODEL
def test_missing_file_means_no_overrides(settings):
    assert llm.model_for("shopping", "en") == ("env-shop:2b", True)
    assert llm.model_for("chat", "en") == ("main:4b", None)


# The file's key wins over `.env` for that key, with its own think value, and other keys keep `.env`'s
def test_file_wins_over_env(settings):
    _write(settings, {"shopping": {"model": "pick-shop:8b", "think": False}, "chat": {"model": "pick-chat:4b"}})
    assert llm.model_for("shopping", "en") == ("pick-shop:8b", False)
    assert llm.model_for("chat", "en") == ("pick-chat:4b", None)
    assert llm.model_for("chat", "tr") == ("env-tr:4b", None)  # a language's model still comes before a task's


# A picked model without think falls back to OLLAMA_THINK, not to the `.env` route's think meant for another model
def test_picked_model_without_think_uses_global_think(settings, monkeypatch):
    _write(settings, {"shopping": {"model": "pick-shop:8b"}})
    assert llm.model_for("shopping", "en") == ("pick-shop:8b", None)
    monkeypatch.setattr(llm, "OLLAMA_THINK", False)
    assert llm.model_for("shopping", "en") == ("pick-shop:8b", False)


# The file is parsed again only when its modified time changes, so an edit applies from the next call
def test_file_changed_while_running(settings):
    _write(settings, {"chat": {"model": "first:4b"}})
    assert llm.model_for("chat", "en")[0] == "first:4b"
    with patch("services.model_settings.parse_model_settings", side_effect=AssertionError("parsed again")):
        assert llm.model_for("chat", "en")[0] == "first:4b"  # unchanged file: not read again
    _write(settings, {"chat": {"model": "second:4b"}}, bump=5)
    assert llm.model_for("chat", "en")[0] == "second:4b"
    settings.unlink()
    assert llm.model_for("chat", "en")[0] == "main:4b"


# A broken or invalid file keeps the last good settings (or `.env` when there were none) and logs a warning
@pytest.mark.parametrize("bad", [
    "{not json",
    "[]",
    json.dumps({"chat": {"model": ""}}),
    json.dumps({"chat": {"model": "x:1b", "think": "yes"}}),
    json.dumps({"chat": "x:1b"}),
])
def test_broken_file_keeps_last_good(settings, caplog, bad):
    _write(settings, bad)
    with caplog.at_level(logging.WARNING):
        assert llm.model_for("chat", "en") == ("main:4b", None)
    assert "Model settings" in caplog.text
    _write(settings, {"chat": {"model": "good:4b"}}, bump=5)
    assert llm.model_for("chat", "en")[0] == "good:4b"
    _write(settings, bad, bump=10)
    assert llm.model_for("chat", "en")[0] == "good:4b"


# Unknown keys are ignored and a null entry is the same as no entry
def test_unknown_keys_ignored():
    assert parse_model_settings({"breakfast": {"model": "x"}, "chat": None, "tr": {"model": " t:4b ", "think": True}}) == {
        "tr": ("t:4b", True),
    }


# A call resolves its model once when it starts, so a change mid-stream doesn't switch the call
async def test_call_keeps_its_model_when_the_file_changes(settings):
    _write(settings, {"chat": {"model": "before:4b"}})

    class _Stream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def raise_for_status(self):
            pass

        async def aiter_lines(self):
            yield '{"message": {"content": "Hi"}}'
            _write(settings, {"chat": {"model": "after:4b"}}, bump=5)
            yield '{"message": {"content": " there"}}'

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.stream = MagicMock(return_value=_Stream())
    with patch("services.llm.check_llm_availability", return_value=True), \
         patch("services.llm.httpx.AsyncClient", return_value=client):
        tokens = [t async for t in llm.chat_stream("system", [], task="chat", language="en")]
    assert tokens == ["Hi", " there"]
    assert client.stream.call_count == 1 and client.stream.call_args.kwargs["json"]["model"] == "before:4b"
    assert llm.model_for("chat", "en")[0] == "after:4b"


# A save writes the whole file through a temp file and a replace, leaving no temp file behind
def test_atomic_save(tmp_path):
    path = tmp_path / "model_settings.json"
    path.write_text("old", encoding="utf-8")
    with patch("services.model_settings.os.replace", wraps=os.replace) as replace:
        write_model_settings(path, {"chat": ("c:4b", None), "tr": ("t:4b", False)})
    source, target = replace.call_args.args
    assert str(target) == str(path) and str(source) != str(path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"chat": {"model": "c:4b"}, "tr": {"model": "t:4b", "think": False}}
    assert [p.name for p in tmp_path.iterdir()] == ["model_settings.json"]


# A save that fails before the replace leaves the old file whole and no temp file
def test_failed_save_keeps_the_old_file(tmp_path):
    path = tmp_path / "model_settings.json"
    path.write_text('{"chat": {"model": "old:4b"}}', encoding="utf-8")
    with patch("services.model_settings.os.replace", side_effect=OSError("disk")), pytest.raises(OSError):
        write_model_settings(path, {"chat": ("new:4b", None)})
    assert json.loads(path.read_text(encoding="utf-8")) == {"chat": {"model": "old:4b"}}
    assert [p.name for p in tmp_path.iterdir()] == ["model_settings.json"]
