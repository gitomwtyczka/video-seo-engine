"""
Users router: current user profile, usage stats.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from api.db import get_db
from api.auth import get_current_user
from api.models.user import User, UsageLog

router = APIRouter(prefix="/v1/users", tags=["users"])


class PlanInfo(BaseModel):
    id: str
    display_name: str
    monthly_quota: int
    wp_sites_limit: int
    api_access: bool


class UsageInfo(BaseModel):
    used_this_month: int
    quota: int  # -1 = unlimited
    percent: float


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_verified: bool
    is_admin: bool
    plan: PlanInfo
    usage: UsageInfo
    created_at: str


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return current user profile with plan and monthly usage."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.user_id == current_user.id)
        .where(UsageLog.success == True)  # noqa: E712
        .where(UsageLog.created_at >= month_start)
    )
    used = result.scalar_one()
    quota = current_user.plan.monthly_quota if current_user.plan else 5
    percent = 0.0 if quota == -1 else round(used / quota * 100, 1) if quota > 0 else 0.0

    plan = current_user.plan
    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_verified=current_user.is_verified,
        is_admin=current_user.is_admin,
        plan=PlanInfo(
            id=plan.id,
            display_name=plan.display_name,
            monthly_quota=plan.monthly_quota,
            wp_sites_limit=plan.wp_sites_limit,
            api_access=plan.api_access
        ) if plan else PlanInfo(id="free", display_name="Free", monthly_quota=5, wp_sites_limit=0, api_access=False),
        usage=UsageInfo(
            used_this_month=used,
            quota=quota,
            percent=percent
        ),
        created_at=current_user.created_at.isoformat() if current_user.created_at else ""
    )
