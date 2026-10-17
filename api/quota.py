"""
Quota middleware: checks user's monthly usage before allowing pipeline execution.
"""
from datetime import datetime, timezone
from typing import Any, Optional
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

    if plan.monthly_quota != -1 and used >= plan.monthly_quota:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Miesięczny limit filmów w Twoim planie został wyczerpany. Przejdź na wyższy plan."
        )

    return current_user


async def log_usage(
    user_id: Any,
    db: AsyncSession,
    youtube_id: str = None,
    success: bool = True,
    error_msg: str = None,
    endpoint: str = "/v1/generate",
    input_tokens: int = 0,
    output_tokens: int = 0,
    llm_provider: str = None,
    estimated_cost_usd: float = None,
) -> None:
    """Record a pipeline execution in usage_logs."""
    import uuid
    uid = user_id
    if isinstance(uid, str):
        try:
            uid = uuid.UUID(uid)
        except Exception:
            pass

    log = UsageLog(
        user_id=uid,
        endpoint=endpoint,
        youtube_id=youtube_id,
        success=success,
        error_msg=error_msg,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        llm_provider=llm_provider,
        estimated_cost_usd=estimated_cost_usd,
    )
    db.add(log)
    await db.commit()
