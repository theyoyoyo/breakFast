import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

DATABASE_PATH = os.getenv("DATABASE_PATH", "./breakFAST.db")

BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))

_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]

NUTRITION_USER_AGENT = "breakFAST/1.0 (personal project)"
OPEN_FOOD_FACTS_BASE_URL = "https://world.openfoodfacts.org"
