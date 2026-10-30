"""
Tests for LLM availability check and fallback behavior.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, AsyncMock
from services.llm import check_llm_availability, chat_stream, LLMUnavailableError, LLM_UNAVAILABLE_MESSAGE, FallbackLyricCycler, FALLBACK_LYRICS, lyric_cycler


@pytest.mark.asyncio
async def test_check_llm_availability_ollama_up():
    """When Ollama responds 200, availability is True."""
    mock_response = AsyncMock()
    mock_response.status_code = 200

    with patch("services.llm.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await check_llm_availability()
        assert result is True


@pytest.mark.asyncio
async def test_check_llm_availability_ollama_down():
    """When Ollama is unreachable, availability is False."""
    with patch("services.llm.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_cls.return_value = mock_client

        result = await check_llm_availability()
        assert result is False


@pytest.mark.asyncio
async def test_chat_stream_raises_when_llm_unavailable():
    """When LLM is unavailable, chat_stream raises LLMUnavailableError."""
    with patch("services.llm.check_llm_availability", return_value=False):
        with pytest.raises(LLMUnavailableError) as exc_info:
            async for _ in chat_stream("system", []):
                pass
        assert str(exc_info.value) == LLM_UNAVAILABLE_MESSAGE


@pytest.mark.asyncio
async def test_fallback_message_content():
    """Fallback message is the expected Turkish string (first lyric line)."""
    assert LLM_UNAVAILABLE_MESSAGE == "Benim aklım ocakta kaldı~"


def test_lyric_cycler_cycles_through_all_lines():
    """Cycler returns each lyric line in order, then loops back to the start."""
    cycler = FallbackLyricCycler()
    for i, expected in enumerate(FALLBACK_LYRICS):
        assert cycler.next() == expected
    # After all 12 lines, loops back to first
    assert cycler.next() == FALLBACK_LYRICS[0]


def test_lyric_cycler_independent_instances():
    """Each cycler instance tracks its own position independently."""
    c1 = FallbackLyricCycler()
    c2 = FallbackLyricCycler()
    c1.next()  # advance c1 to index 1
    c1.next()  # advance c1 to index 2
    assert c1.next() == FALLBACK_LYRICS[2]
    assert c2.next() == FALLBACK_LYRICS[0]  # c2 still at start


def test_global_lyric_cycler_is_singleton():
    """Module-level lyric_cycler is a single shared instance for all callers."""
    from services.llm import lyric_cycler as lc2
    assert lc2 is lyric_cycler


def test_fallback_lyrics_has_12_lines():
    """Song has exactly 12 lines."""
    assert len(FALLBACK_LYRICS) == 12


@pytest.mark.asyncio
async def test_chat_json_sends_schema_as_format():
    """chat_json asks Ollama for one non-streamed reply shaped by the schema and returns its text."""
    from unittest.mock import MagicMock
    from services.llm import chat_json

    response = MagicMock()
    response.json.return_value = {"message": {"content": '{"items": []}'}}
    with patch("services.llm.check_llm_availability", return_value=True), \
         patch("services.llm.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=response)
        mock_client_cls.return_value = mock_client

        schema = {"type": "object"}
        reply = await chat_json("system", [{"role": "user", "content": "hi"}], schema, temperature=0.6)

    payload = mock_client.post.call_args.kwargs["json"]
    assert reply == '{"items": []}'
    assert payload["format"] == schema
    assert payload["stream"] is False
    assert payload["options"] == {"temperature": 0.6}


@pytest.mark.asyncio
async def test_chat_json_raises_when_llm_unavailable():
    """chat_json raises LLMUnavailableError so callers can fall back to a lyric."""
    from services.llm import chat_json

    with patch("services.llm.check_llm_availability", return_value=False):
        with pytest.raises(LLMUnavailableError):
            await chat_json("system", [], {"type": "object"})
