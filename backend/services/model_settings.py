"""The model picker's settings file (#240): a model, and optionally a think value, per task or reply
language, written by tools/model_picker.py and read by services/llm.py on each Ollama call.

    {"shopping": {"model": "gemma4:e2b-it-q4_K_M", "think": true}, "tr": {"model": "qwen3:8b"}}

A key left out uses `.env` (OLLAMA_MODEL_<KEY>, OLLAMA_THINK_<KEY>), then the default. A key's entry
replaces that key's `.env` route whole, since a think value belongs to its model: an entry without
"think" falls back to OLLAMA_THINK, like a route without OLLAMA_THINK_<KEY>.
"""

import json
import logging
import os
from pathlib import Path

from config import MODEL_LANGUAGES, MODEL_TASKS

MODEL_KEYS = MODEL_TASKS + MODEL_LANGUAGES


def parse_model_settings(data) -> dict[str, tuple[str, bool | None]]:
    """The routes in a settings file's JSON, as {key: (model, think)}. Unknown keys are ignored; a
    known key whose value isn't {"model": non-empty text, "think": true, false or absent} raises
    ValueError, so a file that's half wrong is never half applied."""
    if not isinstance(data, dict):
        raise ValueError("settings must be an object")
    routes = {}
    for key in MODEL_KEYS:
        entry = data.get(key)
        if entry is None:
            continue
        if not isinstance(entry, dict):
            raise ValueError(f"{key}: not an object")
        model, think = entry.get("model"), entry.get("think")
        if not isinstance(model, str) or not model.strip():
            raise ValueError(f"{key}: model must be a non-empty string")
        if think is not None and not isinstance(think, bool):
            raise ValueError(f"{key}: think must be true or false")
        routes[key] = (model.strip(), think)
    return routes


def dump_model_settings(routes: dict[str, tuple[str, bool | None]]) -> dict:
    """The file's JSON for routes as parse_model_settings returns them."""
    return {
        key: {"model": model, **({} if think is None else {"think": think})}
        for key, (model, think) in routes.items()
    }


def write_model_settings(path: Path, routes: dict[str, tuple[str, bool | None]]) -> None:
    """Write the file atomically: a temp file beside it, then a replace, so a reader never sees half a file."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(dump_model_settings(routes), f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


class ModelSettingsFile:
    """Reads the settings file again only when its modified time (or size) changed. A missing file
    means no overrides; a broken or invalid one keeps the last good settings and logs a warning once,
    so a bad edit never fails a request."""

    def __init__(self):
        self._stamp = None
        self._routes: dict[str, tuple[str, bool | None]] = {}

    def routes(self, path: Path | None) -> dict[str, tuple[str, bool | None]]:
        if path is None:
            return {}
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            self._stamp, self._routes = None, {}
            return {}
        except OSError:
            logging.warning("Model settings: can't read %s, keeping the last good settings", path)
            return dict(self._routes)
        stamp = (str(path), stat.st_mtime_ns, stat.st_size)
        if stamp != self._stamp:
            self._stamp = stamp
            try:
                with open(path, encoding="utf-8") as f:
                    self._routes = parse_model_settings(json.load(f))
            except (OSError, ValueError) as e:  # json.JSONDecodeError and UnicodeDecodeError are ValueErrors
                logging.warning("Model settings: ignoring %s (%s), keeping the last good settings", path, e)
        return dict(self._routes)
