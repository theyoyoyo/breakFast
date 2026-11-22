import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
# Context length sent with every call. Chat history is about 6000 tokens, so
# Ollama's own 4096 would drop the oldest messages without saying so.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
# Seconds a call may wait for Ollama (to connect, and between the bytes of a reply). A
# JSON reply comes all at once, so a model that thinks first must finish within it.
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "150"))
# Ollama's think field, for models that can think before they answer: "true" or "false"
# sends it with every call. Unset sends nothing, so each model keeps its own default
# (Ollama refuses the field for a model that can't think).
OLLAMA_THINK = {"true": True, "false": False}.get(os.getenv("OLLAMA_THINK", "").strip().lower())


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
