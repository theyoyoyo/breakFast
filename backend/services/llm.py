"""
LLM abstraction layer.
Tries Ollama; if unavailable, raises LLMUnavailableError.
Claude API fallback is commented out — to be re-enabled later.
"""

import httpx
import json
from typing import AsyncGenerator

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)


FALLBACK_LYRICS = [
    "Benim aklım başımda değil",
    "Sana söylediklerimi kafana takma ne olursun",
    "Onlar ipe sapa gelir şeyler değil",
    "Seni sevmiyorum dedim; yalandı",
    "İstemiyorum artık; palavra",
    "Ellerimde çiçekler",
    "Kapında sırıksıklam",
    "Görürsen bir gün şaşırma",
    "Beni böyle çaresiz",
    "Beni böyle derbeder",
    "Beni böyle ortalarda bırakma",
    "Son zamanlar yaptıklarıma bakma ne olursun",
]

# Keep for backwards compatibility with imports
LLM_UNAVAILABLE_MESSAGE = FALLBACK_LYRICS[0]


class FallbackLyricCycler:
    """Cycles through song lyrics on each call, looping back to start."""

    def __init__(self):
        self._index = 0

    def next(self) -> str:
        line = FALLBACK_LYRICS[self._index]
        self._index = (self._index + 1) % len(FALLBACK_LYRICS)
        return line


class LLMUnavailableError(Exception):
    """Raised when no LLM backend is reachable."""
    pass


async def check_llm_availability() -> bool:
    """
    Check if Ollama is reachable. Called before every message.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


async def chat_stream(
    system_prompt: str,
    messages: list[dict],
    temperature: float | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream response tokens. Raises LLMUnavailableError if Ollama is down.
    """
    if not await check_llm_availability():
        raise LLMUnavailableError(LLM_UNAVAILABLE_MESSAGE)

    async for chunk in _ollama_stream(system_prompt, messages, temperature=temperature):
        yield chunk


async def chat_complete(
    system_prompt: str,
    messages: list[dict],
) -> str:
    """Non-streaming call. Returns the full response as a single string."""
    chunks = []
    async for chunk in chat_stream(system_prompt, messages):
        chunks.append(chunk)
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

async def _ollama_stream(
    system_prompt: str,
    messages: list[dict],
    temperature: float | None = None,
) -> AsyncGenerator[str, None]:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
    }
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue


# ---------------------------------------------------------------------------
# Claude API fallback — commented out, to be re-enabled later
# ---------------------------------------------------------------------------
#
# import anthropic
# from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
#
# async def _claude_stream(
#     system_prompt: str,
#     messages: list[dict],
# ) -> AsyncGenerator[str, None]:
#     if not ANTHROPIC_API_KEY:
#         yield "[LLM unavailable: Ollama is down and no ANTHROPIC_API_KEY is set]"
#         return
#
#     client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
#     async with client.messages.stream(
#         model=CLAUDE_MODEL,
#         max_tokens=2048,
#         system=system_prompt,
#         messages=messages,
#     ) as stream:
#         async for text in stream.text_stream:
#             yield text
