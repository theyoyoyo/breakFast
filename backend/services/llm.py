"""
LLM abstraction layer.
Tries Ollama; if unavailable, raises LLMUnavailableError and callers fall
back to the next line of FALLBACK_LYRICS.
"""

import json
from typing import AsyncGenerator

import httpx

from config import (
    DEFAULT_MODEL,
    DEFAULT_THINK,
    MODEL_SETTINGS_PATH,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_ROUTES,
    OLLAMA_THINK,
    OLLAMA_TIMEOUT,
)
from services.model_settings import ModelSettingsFile

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


_model_settings = ModelSettingsFile()


def routes() -> dict[str, tuple[str, bool | None]]:
    """Each task's and reply language's own (model, think): the model picker's file (#240), read again
    only when it changed, over `.env`'s OLLAMA_MODEL_<KEY> routes (#192). A key the file sets replaces
    its `.env` route whole. MODEL_SETTINGS_PATH None reads no file (the prompt test's --model)."""
    return {**OLLAMA_ROUTES, **_model_settings.routes(MODEL_SETTINGS_PATH)}


def model_for(task: str | None = None, language: str | None = None) -> tuple[str, bool | None]:
    """The model and think value for a call (#192): its reply language's model, else its task's
    (config.MODEL_TASKS), else OLLAMA_MODEL, each from routes() (the picker's file, then `.env`). The think
    value is that route's own, else OLLAMA_THINK, else DEFAULT_THINK for the default model and none for any
    other. A call resolves it once when it starts, so a call in flight keeps its model."""
    current = routes()
    model, think = current.get(language) or current.get(task) or (OLLAMA_MODEL, None)
    if think is None:
        think = OLLAMA_THINK
    if think is None and model == DEFAULT_MODEL:
        think = DEFAULT_THINK
    return model, think


async def chat_stream(
    system_prompt: str,
    messages: list[dict],
    temperature: float | None = None,
    task: str | None = None,
    language: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream response tokens from the model for this task and reply language. Raises
    LLMUnavailableError if Ollama is down.
    """
    if not await check_llm_availability():
        raise LLMUnavailableError(LLM_UNAVAILABLE_MESSAGE)

    async for chunk in _ollama_stream(system_prompt, messages, temperature=temperature, task=task, language=language):
        yield chunk


async def stream_response(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    temperature: float | None = None,
    task: str | None = None,
    language: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a reply to one user message after the conversation so far, from the model for this
    task and reply language (#192)."""
    messages = conversation_history + [{"role": "user", "content": user_message}]
    async for chunk in chat_stream(system_prompt, messages, temperature=temperature, task=task, language=language):
        yield chunk


async def chat_json(
    system_prompt: str,
    messages: list[dict],
    schema: dict,
    temperature: float | None = None,
    task: str | None = None,
    language: str | None = None,
) -> str:
    """Non-streaming call whose reply Ollama constrains to the JSON schema (structured outputs),
    sent to the model for this task and reply language.

    Returns the raw reply text; callers parse it. Needs Ollama 0.5 or later.
    """
    if not await check_llm_availability():
        raise LLMUnavailableError(LLM_UNAVAILABLE_MESSAGE)

    model, think = model_for(task, language)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": False,
        "format": schema,
        "options": _options(temperature),
        **_think(think),
    }
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
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


def _think(think: bool | None) -> dict:
    """The think field when the call's model has a think value, else nothing (the model's own default)."""
    return {} if think is None else {"think": think}


async def _ollama_stream(
    system_prompt: str,
    messages: list[dict],
    temperature: float | None = None,
    task: str | None = None,
    language: str | None = None,
) -> AsyncGenerator[str, None]:
    model, think = model_for(task, language)
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
        "options": _options(temperature),
        **_think(think),
    }
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
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
