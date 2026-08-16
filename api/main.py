"""VSE API — FastAPI application entrypoint.

Multi-tenant Video SEO Engine service.
Port: 8085 (Docker: -p 8085:8085)

Endpoints:
  GET  /health                — health check
  POST /v1/generate           — fetch + generate schema (no WP write)
  POST /v1/process            — full pipeline: fetch + generate + inject
  POST /v1/inject             — inject pre-generated schema to WP
  POST /v1/jobs/              — create transcript job for Local Runner
  GET  /v1/jobs/pending       — Local Runner polls pending jobs
  POST /v1/jobs/{id}/result   — Local Runner submits transcript result
  GET  /v1/jobs/{id}          — job status polling
  POST /v1/monitor/start      — start background channel monitor
  POST /v1/sitemap            — generate video sitemap XML
  POST /v1/auth/register      — register new user
  POST /v1/auth/login         — login, returns JWT
  POST /v1/auth/refresh       — refresh access token
  GET  /v1/auth/google        — Google OAuth redirect
  GET  /v1/users/me           — current user profile + usage
  GET  /v1/portals            — list user's WP portals
  POST /v1/portals            — add WP portal
  GET  /v1/portals/{id}/credentials — portal with password
  PATCH /v1/portals/{id}      — update portal
  DELETE /v1/portals/{id}     — delete portal
  GET  /v1/profiles           — list active YAML profiles (D9)
  GET  /v1/admin/users        — [ADMIN] list all users
  GET  /v1/admin/users/{id}   — [ADMIN] user details
  PATCH /v1/admin/users/{id}/plan — [ADMIN] change user plan
  GET  /v1/admin/stats        — [ADMIN] system statistics
  GET  /v1/admin/debug-mode   — [ADMIN] get debug mode state
  POST /v1/admin/debug-mode   — [ADMIN] set debug mode on/off
  POST /v1/payments/create-checkout-session — create Stripe Checkout Session
  POST /v1/payments/webhook   — Stripe webhook (subscription lifecycle)
  GET  /v1/payments/portal-session — Stripe Customer Portal URL
  GET  /v1/youtube/oauth/login — Redirect to Google OAuth for YT
  GET  /v1/youtube/oauth/callback — Callback from Google OAuth for YT
  GET  /v1/podcast/shows      — list podcast shows for profile
  GET  /v1/podcast/shows/{slug} — podcast show config
  POST /v1/podcast/link-mp3   — link MP3 to WordPress post
  GET  /docs                  — Swagger UI
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.routers import generate, inject, monitor, process, sitemap, shorts
from api.routers.auth import router as auth_router
from api.routers.users import router as users_router
from api.routers.jobs import router as jobs_router
from api.routers.admin import router as admin_router
from api.routers.portals import router as portals_router
from api.routers.profiles import router as profiles_router
from api.routers.payments import router as payments_router
from api.routers.youtube import router as youtube_router
from api.routers.podcast import router as podcast_router
from api.models.response import HealthResponse
from api.middleware.error_logging import ErrorLoggingMiddleware
from api.db import engine, Base, AsyncSessionLocal

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

# Error logging middleware — logs all 5xx with full stack trace
# CO: Przechwytuje wyjątki i odpowiedzi 500+, loguje do stdout (docker logs).
# PO CO: Diagnostyka błędów bez SSH na VPS. W trybie debug loguje każdy request.
app.add_middleware(ErrorLoggingMiddleware)

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

# Local Transcript Runner router
app.include_router(jobs_router)

# Shorts Router
app.include_router(shorts.router)

# Admin panel router (requires is_admin=True)
app.include_router(admin_router)

# Portal management router (requires authenticated user)
app.include_router(portals_router)

# Profile listing router (public — D9)
app.include_router(profiles_router)

# Payments / Stripe router
# CO: Obsługuje checkout, webhook Stripe i Customer Portal.
# PO CO: Umożliwia monetyzację VSE — user może kupić plan Starter/Pro/Agency.
app.include_router(payments_router)

# YouTube router (OAuth channels)
app.include_router(youtube_router)

# Podcast router (multi-show management)
app.include_router(podcast_router, prefix="/v1")


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Health check endpoint. Returns 200 when service is ready."""
    return HealthResponse(
        status="ok",
        version="2.0.0",
        llm_default=os.getenv("DEFAULT_LLM_PROVIDER", "claude"),
    )


async def _seed_plans() -> None:
    """Insert default subscription plans on startup if they don't exist.

    Uses ON CONFLICT DO NOTHING so it's safe to run on every startup
    (idempotent). Required because register endpoint has FK to plans table.
    """
    plans = [
        {"id": "free",    "display_name": "Free",    "monthly_quota": 5,    "wp_sites_limit": 1,   "api_access": False, "price_pln": 0},
        {"id": "starter", "display_name": "Starter", "monthly_quota": 50,   "wp_sites_limit": 3,   "api_access": True,  "price_pln": 49},
        {"id": "pro",     "display_name": "Pro",     "monthly_quota": 300,  "wp_sites_limit": 10,  "api_access": True,  "price_pln": 149},
        {"id": "agency",  "display_name": "Agency",  "monthly_quota": 9999, "wp_sites_limit": 999, "api_access": True,  "price_pln": 499},
    ]
    async with AsyncSessionLocal() as db:
        for plan in plans:
            await db.execute(
                text(
                    "INSERT INTO plans "
                    "(id, display_name, monthly_quota, wp_sites_limit, api_access, price_pln) "
                    "VALUES (:id, :display_name, :monthly_quota, :wp_sites_limit, :api_access, :price_pln) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                plan,
            )
        await db.commit()
    logger.info("Plans seeded (4 plans, ON CONFLICT DO NOTHING).")


@app.on_event("startup")
async def startup_event() -> None:
    """Log startup info, verify env vars, create DB tables and seed plans."""
    logger.info("VSE API v2.0.0 starting on port 8085")

    # Auto-create tables on startup (safe: CREATE TABLE IF NOT EXISTS)
    try:
        # Import models to register them with Base
        from api.models.user import User, Plan, UsageLog, ApiKey  # noqa: F401
        from api.models.job import TranscriptJob  # noqa: F401
        from api.models.app_settings import AppSettings  # noqa: F401
        from api.models.portal import WpPortal  # noqa: F401
        from api.models.youtube_channel import YouTubeChannel # noqa: F401
        from api.models.oauth_state import OAuthState # noqa: F401
        from api.models.short_job import ShortJob # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created (incl. transcript_jobs, app_settings, wp_portals, youtube_channels).")
        
        from sqlalchemy import delete
        from datetime import datetime, timezone
        async with AsyncSessionLocal() as session:
            await session.execute(delete(OAuthState).where(OAuthState.expires_at < datetime.now(timezone.utc)))
            await session.commit()
            
    except Exception as e:
        logger.warning(f"DB init skipped (no DB configured?): {e}")
        return

    # Seed default subscription plans (idempotent — ON CONFLICT DO NOTHING)
    try:
        await _seed_plans()
    except Exception as e:
        logger.error(f"Plans seed failed: {e}")

    provider = os.getenv("DEFAULT_LLM_PROVIDER", "claude")
    if provider == "claude" and not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set — claude requests will fail")
    if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        logger.warning("GEMINI_API_KEY not set — gemini requests will fail")
    logger.info("Default LLM provider: %s", provider)

    local_runner = os.getenv("LOCAL_RUNNER_MODE", "false").lower()
    if local_runner == "true":
        if not os.getenv("LOCAL_RUNNER_TOKEN"):
            logger.warning("LOCAL_RUNNER_MODE=true but LOCAL_RUNNER_TOKEN not set!")
        else:
            logger.info("Local Transcript Runner mode: ENABLED")
    else:
        logger.info("Local Transcript Runner mode: DISABLED (direct youtube-transcript-api)")

    if not os.getenv("STRIPE_SECRET_KEY"):
        logger.warning("STRIPE_SECRET_KEY not set — payment endpoints will return 503")
    else:
        logger.info("Stripe payments: ENABLED")
