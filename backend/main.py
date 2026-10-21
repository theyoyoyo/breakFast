from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from config import CORS_ORIGINS, CORS_ALLOW_CREDENTIALS, SERVE_FRONTEND
from database import init_db
from auth import require_user
from routers import analyst, auth, chat, favorites, favorite_ingredients, ingredients, kitchen, meals, preferences, profile, ratings, sessions, health_rules, shopping, scheduler
from services.insights import refresh_insights
from utils import resolve_static_file


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await refresh_insights()
    yield


app = FastAPI(
    title="break FAST API",
    description="Personal AI-powered breakfast planner backend.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(analyst.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(favorites.router)
app.include_router(favorite_ingredients.router)
app.include_router(ingredients.router)
app.include_router(kitchen.router)
app.include_router(meals.router)
app.include_router(preferences.router)
app.include_router(profile.router)
app.include_router(ratings.router)
app.include_router(sessions.router)
app.include_router(health_rules.router)
app.include_router(shopping.router)
app.include_router(scheduler.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/auth")
async def health_auth(user_id: int = Depends(require_user)):
    return {"status": "ok", "user_id": user_id}


# ---------------------------------------------------------------------------
# Static frontend serving (production only — SERVE_FRONTEND=true in .env)
# ---------------------------------------------------------------------------

_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

if SERVE_FRONTEND and _frontend_dist.exists():
    # Mount /assets first so Vite's hashed bundles are served directly
    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve the React SPA — returns index.html for any non-API route."""
        file_path = resolve_static_file(_frontend_dist, full_path)
        if file_path:
            return FileResponse(str(file_path))
        return FileResponse(str(_frontend_dist / "index.html"))
