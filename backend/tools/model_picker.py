"""A small page on the server to choose each task's and reply language's model (#240).

    python -m tools.model_picker              # http://127.0.0.1:8765
    python -m tools.model_picker --port 9000

Not part of the app: run it on the server when you want to change models, open the page there or
through a tunnel (ssh -L 8765:127.0.0.1:8765 server), then stop it. It lists Ollama's models (/api/tags)
in a dropdown per task and reply language, with a think switch for the models that report thinking
(/api/show), and Save writes backend/model_settings.json, which the backend reads on its next Ollama
call (services/model_settings.py), so no restart. It listens on 127.0.0.1 only, and refuses a request
whose Host or Origin isn't this machine (a DNS-rebinding or cross-site page can't save).
"""

import argparse
import asyncio
import html
import json
import logging
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from config import MODEL_LANGUAGES, MODEL_SETTINGS_PATH, MODEL_TASKS, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_ROUTES
from services.model_settings import MODEL_KEYS, parse_model_settings, write_model_settings

HOST = "127.0.0.1"  # never another address: the page changes the server's models and has no login
DEFAULT_PORT = 8765
LOCAL_NAMES = {"127.0.0.1", "localhost", "::1"}
MAX_BODY = 16 * 1024

LABELS = {
    "chat": "Chat", "suggestion": "Suggestion (draft and reply text)", "review": "Review (reviser)",
    "analyst": "Nutrition analysis", "shopping": "Shopping suggestions", "plan": "Prep plan",
    "weekly": "Weekly review", "en": "English replies", "tr": "Turkish replies",
}

# Fixed replies: a refused request never sends its input back
NOT_LOCAL = "This page only answers on this machine."
NOT_JSON = "Send the settings as JSON."
TOO_BIG = "The settings are too big."
BAD_SHAPE = "Each setting must be a model name and an optional think value of true or false."
UNKNOWN_KEY = "Unknown setting."
NOT_INSTALLED = "That model isn't in Ollama's list."
CANT_THINK = "That model can't think, so it takes no think value."
NO_OLLAMA = "Ollama isn't reachable, so the models can't be checked. Nothing was saved."
SAVE_FAILED = "The settings file couldn't be written. Nothing was changed."


class Refused(Exception):
    """A request refused with a fixed message."""

    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


def _hostname(host: str) -> str:
    """The name in a Host header, without its port: "127.0.0.1:8765" → "127.0.0.1", "[::1]:8765" → "::1"."""
    host = host.strip().lower()
    if host.startswith("["):
        return host[1:host.find("]")] if "]" in host else ""
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def is_local_host(host: str | None) -> bool:
    """Whether a Host header names this machine (any port, since a tunnel may forward another one)."""
    return bool(host) and _hostname(host) in LOCAL_NAMES


def is_local_origin(origin: str | None) -> bool:
    """Whether an Origin header is a page on this machine; no header (curl) counts as local, "null" doesn't."""
    if origin is None:
        return True
    try:
        parts = urlsplit(origin)
        return parts.scheme in ("http", "https") and (parts.hostname or "") in LOCAL_NAMES
    except ValueError:
        return False


async def ollama_models(url: str) -> dict[str, bool] | None:
    """Ollama's models, each with whether it reports the thinking capability; None when Ollama can't be reached."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            tags = await client.get(f"{url}/api/tags")
            tags.raise_for_status()
            names = [m["name"] for m in tags.json().get("models", []) if isinstance(m.get("name"), str)]

            async def thinks(name: str) -> bool:
                try:
                    show = await client.post(f"{url}/api/show", json={"model": name})
                    show.raise_for_status()
                    return "thinking" in (show.json().get("capabilities") or [])
                except (httpx.HTTPError, ValueError, AttributeError, TypeError):
                    return False

            flags = await asyncio.gather(*(thinks(n) for n in names))
    except (httpx.HTTPError, ValueError, AttributeError, TypeError, KeyError):
        return None
    return dict(zip(names, flags))


def read_current(path: Path) -> tuple[dict[str, tuple[str, bool | None]], bool]:
    """The saved choices, and whether the file could be read (a missing file is read: no choices)."""
    try:
        return parse_model_settings(json.loads(Path(path).read_text(encoding="utf-8"))), True
    except FileNotFoundError:
        return {}, True
    except (OSError, ValueError):
        return {}, False


def validate(body, models: dict[str, bool], current: dict) -> dict[str, tuple[str, bool | None]]:
    """The routes a posted body asks for: {key: {"model": name, "think": bool?} or null}, every key known,
    every model in Ollama's list (or the one already saved for that key), think only for a model that thinks."""
    if not isinstance(body, dict):
        raise Refused(422, BAD_SHAPE)
    routes = {}
    for key, entry in body.items():
        if key not in MODEL_KEYS:
            raise Refused(422, UNKNOWN_KEY)
        if entry is None:
            continue
        if not isinstance(entry, dict) or set(entry) - {"model", "think"}:
            raise Refused(422, BAD_SHAPE)
        model, think = entry.get("model"), entry.get("think")
        if not isinstance(model, str) or not model.strip() or (think is not None and not isinstance(think, bool)):
            raise Refused(422, BAD_SHAPE)
        model = model.strip()
        if (model, think) == current.get(key):
            routes[key] = (model, think)  # kept as saved, even if Ollama no longer lists it
            continue
        if model not in models:
            raise Refused(422, NOT_INSTALLED)
        if think is not None and not models[model]:
            raise Refused(422, CANT_THINK)
        routes[key] = (model, think)
    return routes


def _env_label(key: str) -> str:
    """What "default (.env)" means for a key, for its first option."""
    if key in OLLAMA_ROUTES:
        return f"default (.env: {OLLAMA_ROUTES[key][0]})"
    if key in MODEL_LANGUAGES:
        return "default (.env: the task's model)"
    return f"default (.env: {OLLAMA_MODEL})"


def render_page(models: dict[str, bool] | None, current: dict, readable: bool) -> str:
    """The page: a dropdown and think switch per key. Every text from Ollama or the file is escaped."""
    e = html.escape
    rows = []
    for key in MODEL_TASKS + MODEL_LANGUAGES:
        saved_model, saved_think = current.get(key, (None, None))
        options = [f'<option value="">{e(_env_label(key))}</option>']
        names = dict(models or {})
        if saved_model and saved_model not in names:
            names[saved_model] = saved_think is not None  # keep a saved one Ollama no longer lists
        for name, thinks in names.items():
            note = "" if models is None or name in models else " (not in Ollama's list)"
            selected = " selected" if name == saved_model else ""
            options.append(
                f'<option value="{e(name)}" data-thinks="{1 if thinks else 0}"{selected}>{e(name + note)}</option>'
            )
        think = {None: "default", True: "on", False: "off"}[saved_think]
        think_options = "".join(
            f'<option value="{v}"{" selected" if v == think else ""}>{v}</option>' for v in ("default", "on", "off")
        )
        rows.append(
            f'<div class="row"><label for="model-{key}">{e(LABELS[key])}</label>'
            f'<select id="model-{key}" class="model" data-key="{key}">{"".join(options)}</select>'
            f'<span class="think" hidden><label for="think-{key}">Think</label>'
            f'<select id="think-{key}">{think_options}</select></span></div>'
        )
    notes = []
    if models is None:
        notes.append("Ollama isn't reachable, so the list shows only what's saved. Saving needs Ollama.")
    if not readable:
        notes.append("The settings file can't be read, so the backend keeps its last good settings. Saving replaces it.")
    note_html = "".join(f'<p class="note">{e(n)}</p>' for n in notes)
    return _PAGE.replace("{notes}", note_html).replace("{rows}", "".join(rows))  # rows last: names may hold braces


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model picker</title>
<style>
:root { color-scheme: light dark; }
body { margin: 0; padding: 16px; background: Canvas; color: CanvasText; font: 16px/1.4 system-ui, sans-serif; }
main { max-width: 640px; margin: 0 auto; }
h1 { font-size: 1.3rem; margin: 0 0 4px; }
.row { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; padding: 10px 0;
  border-bottom: 1px solid GrayText; }
.row > label { flex: 1 1 100%; font-weight: 600; }
select { font: inherit; max-width: 100%; min-width: 0; }
.model { flex: 1 1 14rem; }
.think { display: flex; gap: 6px; align-items: center; }
.think[hidden] { display: none; }
.note, .hint { color: GrayText; }
button { font: inherit; padding: 8px 18px; margin-top: 16px; }
#status { min-height: 1.4em; }
</style>
</head>
<body>
<main>
<h1>Model picker</h1>
<p class="hint">A model per task and reply language. A call uses its reply language's model, else its task's,
else the default. Saving applies from the next request, with no restart.</p>
{notes}
<form id="form">
{rows}
<button type="submit">Save</button>
<p id="status" role="status"></p>
</form>
</main>
<script>
const models = document.querySelectorAll("select.model");
function sync(select) {
  const option = select.selectedOptions[0];
  document.getElementById("think-" + select.dataset.key).parentElement.hidden =
    !(option && option.dataset.thinks === "1");
}
models.forEach((select) => { select.addEventListener("change", () => sync(select)); sync(select); });
document.getElementById("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = {};
  models.forEach((select) => {
    const key = select.dataset.key;
    if (!select.value) { body[key] = null; return; }
    const entry = { model: select.value };
    const think = document.getElementById("think-" + key);
    if (!think.parentElement.hidden && think.value !== "default") entry.think = think.value === "on";
    body[key] = entry;
  });
  const status = document.getElementById("status");
  status.textContent = "Saving...";
  try {
    const response = await fetch("/save", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const reply = await response.json();
    status.textContent = response.ok ? "Saved. Applies from the next request." : reply.detail;
  } catch (error) {
    status.textContent = "The picker isn't reachable.";
  }
});
</script>
</body>
</html>
"""

_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; "
        "frame-ancestors 'none'; form-action 'none'; base-uri 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}


def create_app(ollama_url: str = OLLAMA_BASE_URL, settings_path: Path = MODEL_SETTINGS_PATH) -> FastAPI:
    """The picker's app: GET / shows the page, POST /save writes the settings file."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        # Host on every request (DNS rebinding), Origin on writes (a cross-site page)
        if not is_local_host(request.headers.get("host")) or (
            request.method != "GET" and not is_local_origin(request.headers.get("origin"))
        ):
            return JSONResponse({"detail": NOT_LOCAL}, status_code=403, headers=_HEADERS)
        response = await call_next(request)
        response.headers.update(_HEADERS)
        return response

    @app.get("/", response_class=HTMLResponse)
    async def page():
        current, readable = read_current(settings_path)
        return HTMLResponse(render_page(await ollama_models(ollama_url), current, readable))

    @app.post("/save")
    async def save(request: Request):
        try:
            if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                raise Refused(415, NOT_JSON)
            raw = await request.body()
            if len(raw) > MAX_BODY:
                raise Refused(413, TOO_BIG)
            try:
                body = json.loads(raw)
            except ValueError:
                raise Refused(422, NOT_JSON) from None
            models = await ollama_models(ollama_url)
            if models is None:
                raise Refused(503, NO_OLLAMA)
            routes = validate(body, models, read_current(settings_path)[0])
            try:
                write_model_settings(settings_path, routes)
            except OSError:
                logging.exception("Model picker: writing %s failed", settings_path)
                raise Refused(500, SAVE_FAILED) from None
        except Refused as refused:
            return JSONResponse({"detail": refused.message}, status_code=refused.status)
        return {"saved": len(routes)}

    return app


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Choose each task's and reply language's Ollama model (#240).")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port on 127.0.0.1 (default: {DEFAULT_PORT})")
    parser.add_argument("--url", default=OLLAMA_BASE_URL, help="Ollama address (default: OLLAMA_BASE_URL)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    args = parse_args(argv)
    print(f"Model picker on http://{HOST}:{args.port} (Ctrl+C to stop). Saving writes {MODEL_SETTINGS_PATH}.")
    uvicorn.run(create_app(args.url), host=HOST, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
