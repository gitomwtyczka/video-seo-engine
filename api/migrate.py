"""
Database migration script: creates all tables and seeds default plans.
Run once on fresh database: python -m api.migrate
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from api.db import DATABASE_URL, Base, AsyncSessionLocal
from api.models.user import Plan  # noqa: F401 - ensures Plan is registered
from api.models.user import User, UsageLog, ApiKey  # noqa: F401
from api.models.portal import WpPortal  # noqa: F401

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DEFAULT_PLANS = [
    {"id": "free",    "display_name": "Free",    "monthly_quota": 5,   "wp_sites_limit": 0, "api_access": False, "price_pln": 0},
    {"id": "starter", "display_name": "Starter", "monthly_quota": 50,  "wp_sites_limit": 1, "api_access": False, "price_pln": 2900},
    {"id": "pro",     "display_name": "Pro",     "monthly_quota": -1,  "wp_sites_limit": 5, "api_access": True,  "price_pln": 9900},
    {"id": "agency",  "display_name": "Agency",  "monthly_quota": -1,  "wp_sites_limit": -1, "api_access": True, "price_pln": 29900},
]


async def run_migration():
    """Create tables and seed plans (idempotent)."""
    engine = create_async_engine(DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        log.info("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        
        # Migration: add profile_id column and clear old records
        try:
            await conn.execute(text("ALTER TABLE wp_portals ADD COLUMN IF NOT EXISTS profile_id VARCHAR(100)"))
            log.info("Ensured profile_id column exists on wp_portals")
            await conn.execute(text("DELETE FROM wp_portals"))
            log.info("Cleared old records from wp_portals")
            
            await conn.execute(text("ALTER TABLE transcript_jobs ALTER COLUMN portal_id TYPE VARCHAR(50)"))
            log.info("Ensured portal_id is VARCHAR in transcript_jobs")
        except Exception as e:
            log.warning(f"Error during manual migrations: {e}")

        log.info("Tables created.")

    async with AsyncSessionLocal() as session:
        for plan_data in DEFAULT_PLANS:
            result = await session.execute(
                text("SELECT id FROM plans WHERE id = :id"),
                {"id": plan_data["id"]}
            )
            if not result.fetchone():
                plan = Plan(**plan_data)
                session.add(plan)
                log.info(f"Seeded plan: {plan_data['id']}")
            else:
                log.info(f"Plan already exists: {plan_data['id']}")
        await session.commit()

    log.info("Migration complete.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())
