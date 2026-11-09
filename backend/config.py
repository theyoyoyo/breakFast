import os
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


def _think(raw: str | None) -> bool | None:
    return {"true": True, "false": False}.get((raw or "").strip().lower())


# Ollama's think field, for models that can think before they answer: "true" or "false"
# sends it with every call to OLLAMA_MODEL. Unset sends nothing, so the model keeps its own
# default (Ollama refuses the field for a model that can't think); the default model sends false.
OLLAMA_THINK = _think(os.getenv("OLLAMA_THINK") or ("" if os.getenv("OLLAMA_MODEL", "").strip() else "false"))

# A model per task or reply language (#192): OLLAMA_MODEL_<KEY>, with its own OLLAMA_THINK_<KEY>
# (unset sends none), e.g. OLLAMA_MODEL_SHOPPING or OLLAMA_MODEL_TR. A call uses its reply
# language's model, else its task's, else OLLAMA_MODEL.
MODEL_TASKS = ("chat", "suggestion", "review", "analyst", "shopping", "plan", "weekly")
MODEL_LANGUAGES = ("en", "tr")
OLLAMA_ROUTES = {
    key: (model, _think(os.getenv(f"OLLAMA_THINK_{key.upper()}")))
    for key in MODEL_LANGUAGES + MODEL_TASKS
    if (model := os.getenv(f"OLLAMA_MODEL_{key.upper()}", "").strip())
}

DATABASE_PATH = os.getenv("DATABASE_PATH", "./breakFAST.db")

_cors_raw = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
# When CORS_ORIGINS is ["*"], credentials mode is disabled (CORS spec forbids
# wildcard + credentials). Bearer token auth via Authorization header still works.
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS

SERVE_FRONTEND = os.getenv("SERVE_FRONTEND", "").lower() in ("1", "true", "yes")

# Create a "demo" user with an empty PIN on startup (for trying the app locally)
DEMO_USER = os.getenv("DEMO_USER", "").lower() in ("1", "true", "yes")
