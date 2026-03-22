from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from fastapi import Depends
from config import CORS_ORIGINS
from database import init_db
from auth import require_user
from routers import analyst, auth, chat, ingredients, meals, preferences, profile, ratings, sessions, health_rules
from services.insights import refresh_insights


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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyst.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(ingredients.router)
app.include_router(meals.router)
app.include_router(preferences.router)
app.include_router(profile.router)
app.include_router(ratings.router)
app.include_router(sessions.router)
app.include_router(health_rules.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/auth")
async def health_auth(user_id: int = Depends(require_user)):
    return {"status": "ok", "user_id": user_id}
