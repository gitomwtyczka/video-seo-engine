"""
Quota middleware: checks user's monthly usage before allowing pipeline execution.
"""
from datetime import datetime, timezone
from typing import Any, Optional
import uuid
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from api.db import get_db
from api.auth import get_current_user
from api.models.user import User, UsageLog, Subscription

ALLOWED_LANGUAGES = ["pl", "en", "de", "es", "fr", "it", "uk", "pt"]


def get_effective_monthly_quota(user: User) -> int:
    """Return effective monthly quota for user (custom_monthly_quota overrides plan.monthly_quota)."""
    custom_q = getattr(user, "custom_monthly_quota", None)
    if custom_q is not None:
        return int(custom_q)
    if user.plan and user.plan.monthly_quota is not None:
        return int(user.plan.monthly_quota)
    return 5


def get_multilang_entitlements(plan_name: str, has_addon: bool = False) -> dict:
    """Return Multi-Language & Cross-Language ('Złoty Środek') entitlements for a plan + add-on."""
    plan_key = (plan_name or "free").lower().strip()

    if plan_key == "agency":
        return {
            "allow_cross_lang_input": True,
            "allow_target_override": True,
            "allow_per_material_adapt": True,
            "max_adaptations_per_video": 999,
            "allowed_languages": ALLOWED_LANGUAGES,
            "has_multilang_addon": True,
        }
    if plan_key == "pro":
        return {
            "allow_cross_lang_input": True,
            "allow_target_override": True,
            "allow_per_material_adapt": True,
            "max_adaptations_per_video": 20,
            "allowed_languages": ALLOWED_LANGUAGES,
            "has_multilang_addon": True,
        }
    if has_addon:
        return {
            "allow_cross_lang_input": True,
            "allow_target_override": True,
            "allow_per_material_adapt": True,
            "max_adaptations_per_video": 5,
            "allowed_languages": ALLOWED_LANGUAGES,
            "has_multilang_addon": True,
        }
    # free or starter without add-on
    return {
        "allow_cross_lang_input": True,
        "allow_target_override": False,
        "allow_per_material_adapt": False,
        "max_adaptations_per_video": 0,
        "allowed_languages": ALLOWED_LANGUAGES,
        "has_multilang_addon": False,
    }


async def check_multilang_access(user_id: Any, db: AsyncSession, user: Optional[User] = None) -> dict:
    """Resolve user's plan + has_multilang_addon from User & Subscription tables and return entitlements."""
    uid = user_id
    if isinstance(uid, str):
        try:
            uid = uuid.UUID(uid)
        except Exception:
            pass

    if user is None and uid is not None:
        res_u = await db.execute(select(User).where(User.id == uid))
        user = res_u.scalar_one_or_none()

    plan_name = (user.plan_id if user and user.plan_id else "free").lower()
    has_addon = bool(getattr(user, "has_multilang_addon", False)) if user else False

    if uid is not None:
        try:
            res_sub = await db.execute(select(Subscription).where(Subscription.user_id == uid))
            sub = res_sub.scalar_one_or_none()
            if sub and sub.has_multilang_addon:
                has_addon = True
        except Exception:
            pass

    if user and getattr(user, "is_admin", False):
        return get_multilang_entitlements("agency", has_addon=True)

    return get_multilang_entitlements(plan_name, has_addon=has_addon)


async def check_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency: block request if user exceeded monthly quota and has no Top-Up credits.
    If monthly quota is exceeded but extra_quota_balance > 0, consumes 1 Top-Up credit.
    Attach user to request for downstream use.
    """
    plan = current_user.plan
    if plan is None and getattr(current_user, "custom_monthly_quota", None) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active plan found"
        )

    effective_monthly_quota = get_effective_monthly_quota(current_user)

    # Unlimited plan / custom quota
    if effective_monthly_quota == -1:
        return current_user

    # Count this month's successful video executions (exclude per-material adaptations and topup markers)
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.user_id == current_user.id)
        .where(UsageLog.success == True)  # noqa: E712
        .where(UsageLog.endpoint != "adapt_material")
        .where(~UsageLog.endpoint.like("topup:%"))
        .where(UsageLog.created_at >= month_start)
    )
    used_this_month = int(result.scalar_one() or 0)

    if effective_monthly_quota != -1 and used_this_month >= effective_monthly_quota:
        extra_balance = int(getattr(current_user, "extra_quota_balance", 0) or 0)
        if extra_balance > 0:
            current_user.extra_quota_balance = extra_balance - 1
            await db.flush()
        else:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Miesięczny limit filmów ({used_this_month}/{effective_monthly_quota}) został wyczerpany. "
                    "Dokup pakiet Top-Up (+50 / +150 / +500 filmów) lub przejdź na wyższy plan."
                ),
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
