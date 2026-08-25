"""\r
Database migration script: creates all tables and seeds default plans.\r
Run once on fresh database: python -m api.migrate\r
"""\r
import asyncio\r
import logging\r
from sqlalchemy.ext.asyncio import create_async_engine\r
from sqlalchemy import text\r
\r
from api.db import DATABASE_URL, Base, AsyncSessionLocal\r
from api.models.user import Plan  # noqa: F401 - ensures Plan is registered\r
from api.models.user import User, UsageLog, ApiKey  # noqa: F401\r
from api.models.portal import WpPortal  # noqa: F401\r
from api.models.short_candidate import ShortCandidateSet # noqa: F401\r
from api.models.short_job import ShortJob # noqa: F401\r
\r
logging.basicConfig(level=logging.INFO)\r
log = logging.getLogger(__name__)\r
\r
DEFAULT_PLANS = [\r
    {"id": "free",    "display_name": "Free",    "monthly_quota": 5,   "wp_sites_limit": 0, "api_access": False, "price_pln": 0},\r
    {"id": "starter", "display_name": "Starter", "monthly_quota": 50,  "wp_sites_limit": 1, "api_access": False, "price_pln": 2900},\r
    {"id": "pro",     "display_name": "Pro",     "monthly_quota": -1,  "wp_sites_limit": 5, "api_access": True,  "price_pln": 9900},\r
    {"id": "agency",  "display_name": "Agency",  "monthly_quota": -1,  "wp_sites_limit": -1, "api_access": True, "price_pln": 29900},\r
]\r
\r
\r
async def run_migration():\r
    """Create tables and seed plans (idempotent)."""\r
    engine = create_async_engine(DATABASE_URL, echo=True)\r
\r
    async with engine.begin() as conn:\r
        log.info("Creating tables...")\r
        await conn.run_sync(Base.metadata.create_all)\r
        \r
        # Migration: add profile_id column and clear old records\r
        try:\r
            await conn.execute(text("ALTER TABLE wp_portals ADD COLUMN IF NOT EXISTS profile_id VARCHAR(100)"))\r
            log.info("Ensured profile_id column exists on wp_portals")\r
            await conn.execute(text("DELETE FROM wp_portals"))\r
            log.info("Cleared old records from wp_portals")\r
            \r
            await conn.execute(text("ALTER TABLE transcript_jobs ALTER COLUMN portal_id TYPE VARCHAR(50)"))\r
            log.info("Ensured portal_id is VARCHAR in transcript_jobs")\r
        except Exception as e:\r
            log.warning(f"Error during manual migrations: {e}")\r
\r
        log.info("Tables created.")\r
\r
    async with AsyncSessionLocal() as session:\r
        for plan_data in DEFAULT_PLANS:\r
            result = await session.execute(\r
                text("SELECT id FROM plans WHERE id = :id"),\r
                {"id": plan_data["id"]}\r
            )\r
            if not result.fetchone():\r
                plan = Plan(**plan_data)\r
                session.add(plan)\r
                log.info(f"Seeded plan: {plan_data['id']}")\r
            else:\r
                log.info(f"Plan already exists: {plan_data['id']}")\r
        await session.commit()\r
\r
    log.info("Migration complete.")\r
    await engine.dispose()\r
\r
\r
if __name__ == "__main__":\r
    asyncio.run(run_migration())\r
