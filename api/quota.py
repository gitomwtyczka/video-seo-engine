"""
Quota middleware: checks user's monthly usage before allowing pipeline execution.
"""
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from api.db import get_db
from api.auth import get_current_user
from api.models.user import User, UsageLog


async def check_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency: block request if user exceeded monthly quota.
    Attach user to request for downstream use.
    """
    plan = current_user.plan
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active plan found"
        )

    # Unlimited plan
    if plan.monthly_quota == -1:
        return current_user

    # Count this month's successful executions
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.user_id == current_user.id)
        .where(UsageLog.success == True)  # noqa: E712
        .where(UsageLog.created_at >= month_start)
    )
    used = result.scalar_one()

    if used >= plan.monthly_quota:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Monthly quota exceeded ({used}/{plan.monthly_quota}). "
                "Upgrade your plan at https://vse.impresjapr.pl/pricing"
            )
        )

    return current_user


async def log_usage(
    user_id: str,
    db: AsyncSession,
    youtube_id: str = None,
    success: bool = True,
    error_msg: str = None
) -> None:
    """Record a pipeline execution in usage_logs."""
    log = UsageLog(
        user_id=user_id,
        youtube_id=youtube_id,
        success=success,
        error_msg=error_msg
    )
    db.add(log)
    await db.commit()
