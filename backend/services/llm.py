"""
LLM abstraction layer.
Tries Ollama first; falls back to Claude API if Ollama is unavailable or returns an error.
Supports both regular (one-shot) calls and streaming (async generator).
"""

import httpx
import json
import time
from typing import AsyncGenerator
import anthropic

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
)


# ---------------------------------------------------------------------------
# Ollama availability — cached with a 30-second TTL to avoid a health-check
# round-trip on every single chat message.
# ---------------------------------------------------------------------------

_ollama_cache: dict = {"available": False, "checked_at": 0.0}
_OLLAMA_CACHE_TTL = 30.0  # seconds


async def _ollama_available() -> bool:
    """
    Returns True if the local Ollama server is reachable.
    Result is cached for 30 s to avoid blocking the hot path on every message.
    """
    now = time.monotonic()
    if now - _ollama_cache["checked_at"] < _OLLAMA_CACHE_TTL:
        return _ollama_cache["available"]

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            available = r.status_code == 200
    except Exception:
        available = False

    _ollama_cache["available"] = available
    _ollama_cache["checked_at"] = now
    return available


async def chat_stream(
    system_prompt: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """
    Stream response tokens.  Each yielded value is a string chunk (may be partial word).
    Tries Ollama first; invalidates the availability cache and falls back to Claude on error.
    """
    if await _ollama_available():
        try:
            async for chunk in _ollama_stream(system_prompt, messages):
                yield chunk
            return
        except Exception:
            # Ollama failed mid-stream — invalidate cache so next call re-checks
            _ollama_cache["checked_at"] = 0.0

    async for chunk in _claude_stream(system_prompt, messages):
        yield chunk


async def chat_complete(
    system_prompt: str,
    messages: list[dict],
) -> str:
    """Non-streaming call.  Returns the full response as a single string."""
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
) -> AsyncGenerator[str, None]:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
    }
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
# Claude API fallback
# ---------------------------------------------------------------------------

async def _claude_stream(
    system_prompt: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    if not ANTHROPIC_API_KEY:
        yield "[LLM unavailable: Ollama is down and no ANTHROPIC_API_KEY is set]"
        return

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    async with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text
