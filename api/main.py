"""VSE API — FastAPI application entrypoint.

Multi-tenant Video SEO Engine service.
Port: 8085 (Docker: -p 8085:8085)

Endpoints:
  GET  /health                — health check
  POST /v1/generate           — fetch + generate schema (no WP write)
  POST /v1/process            — full pipeline: fetch + generate + inject
  POST /v1/inject             — inject pre-generated schema to WP
  POST /v1/monitor/start      — start background channel monitor
  POST /v1/sitemap            — generate video sitemap XML
  POST /v1/auth/register      — register new user
  POST /v1/auth/login         — login, returns JWT
  POST /v1/auth/refresh       — refresh access token
  GET  /v1/auth/google        — Google OAuth redirect
  GET  /v1/users/me           — current user profile + usage
  GET  /docs                  — Swagger UI
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import generate, inject, monitor, process, sitemap
from api.routers.auth import router as auth_router
from api.routers.users import router as users_router
from api.models.response import HealthResponse
from api.db import engine, Base

# Logging setup
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vse.impresjapr.pl")

app = FastAPI(
    title="VSE API",
    description="PressAI Video SEO Engine — multi-tenant FastAPI service",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core pipeline routers
for _router in [process.router, generate.router, inject.router,
                monitor.router, sitemap.router]:
    app.include_router(_router)

# Auth & user management routers
app.include_router(auth_router)
app.include_router(users_router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Health check endpoint. Returns 200 when service is ready."""
    return HealthResponse(
        status="ok",
        version="2.0.0",
        llm_default=os.getenv("DEFAULT_LLM_PROVIDER", "claude"),
    )


@app.on_event("startup")
async def startup_event() -> None:
    """Log startup info, verify env vars, create DB tables if missing."""
    logger.info("VSE API v2.0.0 starting on port 8085")

    # Auto-create tables on startup (safe: CREATE TABLE IF NOT EXISTS)
    try:
        # Import models to register them with Base
        from api.models.user import User, Plan, UsageLog, ApiKey  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created.")
    except Exception as e:
        logger.warning(f"DB init skipped (no DB configured?): {e}")

    provider = os.getenv("DEFAULT_LLM_PROVIDER", "claude")
    if provider == "claude" and not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set — claude requests will fail")
    if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        logger.warning("GEMINI_API_KEY not set — gemini requests will fail")
    logger.info("Default LLM provider: %s", provider)
