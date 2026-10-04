from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import engine
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.chapters import router as chapters_router
from app.api.styles import router as styles_router
from app.api.export import router as export_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the pgvector extension exists. Table/index creation is owned by
    # Alembic migrations, which run via `alembic upgrade head` at startup
    # (see docker-compose). This statement is idempotent and kept as a safety
    # net so the app can still boot if migrations were run without it.
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    yield


app = FastAPI(
    title="AI Novel Writing Platform",
    description="Backend API for AI-assisted novel writing",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(chapters_router)
app.include_router(styles_router)
app.include_router(export_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "ai-novel-writing-platform"}
