import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# The model every call uses unless a task or reply language has its own (below). The default
# won the blind model tests (docs/MODEL_TESTS.md) and comes with thinking off.
DEFAULT_MODEL = "gemma4:e4b-it-qat"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip() or DEFAULT_MODEL
# Context length sent with every call. Chat history is about 6000 tokens, so
# Ollama's own 4096 would drop the oldest messages without saying so.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
# Seconds a call may wait for Ollama (to connect, and between the bytes of a reply). A
# JSON reply comes all at once, so a model that thinks first must finish within it.
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "150"))


def _think(raw: str | None) -> bool | None:
    return {"true": True, "false": False}.get((raw or "").strip().lower())


# Ollama's think field, for models that can think before they answer: "true" or "false" sends it
# with every call that has no think setting of its own (below). Unset sends nothing, so each model
# keeps its own default (Ollama refuses the field for a model that can't think), except the
# default model, which runs with DEFAULT_THINK.
OLLAMA_THINK = _think(os.getenv("OLLAMA_THINK"))
DEFAULT_THINK = False

# A model per task or reply language (#192): OLLAMA_MODEL_<KEY>, with its own OLLAMA_THINK_<KEY>
# (unset falls back to OLLAMA_THINK), e.g. OLLAMA_MODEL_SHOPPING or OLLAMA_MODEL_TR. A call uses
# its reply language's model, else its task's, else OLLAMA_MODEL (services/llm.py, model_for).
MODEL_TASKS = ("chat", "suggestion", "review", "analyst", "shopping", "plan", "weekly")
MODEL_LANGUAGES = ("en", "tr")
OLLAMA_ROUTES = {
    key: (model, _think(os.getenv(f"OLLAMA_THINK_{key.upper()}")))
    for key in MODEL_LANGUAGES + MODEL_TASKS
    if (model := os.getenv(f"OLLAMA_MODEL_{key.upper()}", "").strip())
}
# The model picker's choices (tools/model_picker.py, #240), git-ignored and read on each Ollama call:
# a key set there wins over its OLLAMA_MODEL_<KEY> route (services/model_settings.py).
MODEL_SETTINGS_PATH = Path(__file__).resolve().parent / "model_settings.json"


def resolve_database_path(value: str) -> str:
    """The database file's full path. A relative one counts from this folder (backend/),
    not from the folder the program was started in: started elsewhere, the server or the
    admin CLI would otherwise open a new, empty database there."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return os.path.abspath(path)


DATABASE_PATH = resolve_database_path(os.getenv("DATABASE_PATH") or "./breakFAST.db")

_cors_raw = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
# When CORS_ORIGINS is ["*"], credentials mode is disabled (CORS spec forbids
# wildcard + credentials). Bearer token auth via Authorization header still works.
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

SERVE_FRONTEND = os.getenv("SERVE_FRONTEND", "").lower() in ("1", "true", "yes")

# Serve FastAPI's /docs, /redoc and /openapi.json (off by default)
API_DOCS = os.getenv("API_DOCS", "").lower() in ("1", "true", "yes")

# Create a "demo" user with an empty PIN on startup (for trying the app locally)
DEMO_USER = os.getenv("DEMO_USER", "").lower() in ("1", "true", "yes")
