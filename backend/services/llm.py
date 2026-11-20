"""
LLM abstraction layer.
Tries Ollama; if unavailable, raises LLMUnavailableError and callers fall
back to the next line of FALLBACK_LYRICS.
"""

import httpx
import json
from typing import AsyncGenerator

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
)


FALLBACK_LYRICS = [
    "Benim aklım ocakta kaldı~",
    "🎶 Dünkü menüyü kafana takma ne olursun...",
    "🎵 Onlar çaya simide gelir şeyler değil!",
    "💔 Menemen yapmam dedim; yalandı~",
    "🎶 Çay istemiyorum artık; palavra!",
    "🥯 Ellerimde simitler~",
    "☕ Kapında demlik elimde...",
    "👀 Ocakta görürsen şaşırma~",
    "🎵 Beni böyle aç susuz...",
    "🎶 Beni böyle kahvaltısız...",
    "🍳 Beni böyle sofrada yalnız bırakma!",
    "🙈 Son zamanlarda yediklerime bakma ne olursun~",
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


## Global singleton — all callers share the same counter so lyrics continue seamlessly
lyric_cycler = FallbackLyricCycler()


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


async def stream_response(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    temperature: float | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a reply to one user message after the conversation so far."""
    messages = conversation_history + [{"role": "user", "content": user_message}]
    async for chunk in chat_stream(system_prompt, messages, temperature=temperature):
        yield chunk


async def chat_json(
    system_prompt: str,
    messages: list[dict],
    schema: dict,
    temperature: float | None = None,
) -> str:
    """Non-streaming call whose reply Ollama constrains to the JSON schema (structured outputs).

    Returns the raw reply text; callers parse it. Needs Ollama 0.5 or later.
    """
    if not await check_llm_availability():
        raise LLMUnavailableError(LLM_UNAVAILABLE_MESSAGE)

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": False,
        "format": schema,
        "options": _options(temperature),
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise LLMUnavailableError(f"Ollama error {e.response.status_code}: model may not be downloaded") from e
        return response.json().get("message", {}).get("content", "")


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def _options(temperature: float | None) -> dict:
    """Options for one call: the same num_ctx every time, so Ollama never reloads the model."""
    options = {"num_ctx": OLLAMA_NUM_CTX}
    if temperature is not None:
        options["temperature"] = temperature
    return options


async def _ollama_stream(
    system_prompt: str,
    messages: list[dict],
    temperature: float | None = None,
) -> AsyncGenerator[str, None]:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
        "options": _options(temperature),
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
        ) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise LLMUnavailableError(f"Ollama error {e.response.status_code}: model may not be downloaded") from e
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
