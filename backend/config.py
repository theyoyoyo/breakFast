import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
# Context length sent with every call. Chat history is about 6000 tokens, so
# Ollama's own 4096 would drop the oldest messages without saying so.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

DATABASE_PATH = os.getenv("DATABASE_PATH", "./breakFAST.db")

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
