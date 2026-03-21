"""
Tests for LLM availability check and fallback behavior.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from services.llm import check_llm_availability, chat_stream, LLMUnavailableError, LLM_UNAVAILABLE_MESSAGE


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
    """Fallback message is the expected Turkish string."""
    assert LLM_UNAVAILABLE_MESSAGE == "Benim aklım başımda değil"
