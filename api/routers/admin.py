"""
Admin router: user management for administrators.

CO: Endpointy zarządzania użytkownikami — lista, szczegóły, zmiana planu.
PO CO: Admin może zarządzać subskrypcjami bez logowania do bazy SQL na VPS.
       Wcześniej zmiana planu wymagała ręcznego SQL (np. tobroz@gmail.com → agency).
JAK: Używa get_current_admin dependency (wymaga is_admin=True na koncie).
     Endpointy pod /v1/admin/* — chronione przez JWT + is_admin check.
"""
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from api.db import get_db
from api.auth import get_current_admin
from api.models.user import User, Plan, UsageLog

router = APIRouter(prefix="/v1/admin", tags=["admin"])


# --- Pydantic schemas ---

class PlanSummary(BaseModel):
    id: str
    display_name: str
    monthly_quota: int


class UserAdminView(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    is_verified: bool
    plan_id: str
    plan_name: str
    usage_this_month: int
    created_at: Optional[str]


class UserListResponse(BaseModel):
    users: List[UserAdminView]
    total: int


class PlanChangeRequest(BaseModel):
    plan_id: str  # e.g. 'free', 'starter', 'pro', 'agency'


class PlanChangeResponse(BaseModel):
    user_id: str
    email: str
    old_plan: str
    new_plan: str
    message: str


class AdminStatsResponse(BaseModel):
    total_users: int
    users_by_plan: dict
    active_users_30d: int
    generations_today: int


# --- Helpers ---

async def _count_usage_this_month(db: AsyncSession, user_id) -> int:
    """Count successful generations by user in current calendar month."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.user_id == user_id)
        .where(UsageLog.success == True)  # noqa: E712
        .where(UsageLog.created_at >= month_start)
    )
    return result.scalar_one() or 0


# --- Endpoints ---

@router.get("/users", response_model=UserListResponse)
async def list_users(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """
    CO: Zwraca paginowaną listę wszystkich użytkowników z ich planami i statystykami.
    PO CO: Admin może zobaczyć kto jest w systemie i jaki ma plan — bez SQL.
    JAK: SELECT users + eager load plans (selectinload), zlicza usage_logs bieżącego miesiąca.
         selectinload wymagany — bez niego async SQLAlchemy rzuca MissingGreenlet przy u.plan.
    """
    result = await db.execute(
        select(User)
        .options(selectinload(User.plan))  # eager load — fixes MissingGreenlet
        .offset(skip)
        .limit(limit)
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    # Total count
    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar_one() or 0

    user_views = []
    for user in users:
        usage = await _count_usage_this_month(db, user.id)
        plan = user.plan
        user_views.append(UserAdminView(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_admin=user.is_admin,
            is_verified=user.is_verified,
            plan_id=user.plan_id or "free",
            plan_name=plan.display_name if plan else "Free",
            usage_this_month=usage,
            created_at=user.created_at.isoformat() if user.created_at else None,
        ))

    return UserListResponse(users=user_views, total=total)


@router.get("/users/{user_id}", response_model=UserAdminView)
async def get_user(
    user_id: str,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    CO: Szczegóły konkretnego użytkownika.
    PO CO: Deep dive na konkretne konto — debug, weryfikacja planu.
    JAK: SELECT users WHERE id = user_id + selectinload(User.plan).
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    result = await db.execute(
        select(User)
        .options(selectinload(User.plan))  # eager load — fixes MissingGreenlet
        .where(User.id == uid)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    usage = await _count_usage_this_month(db, user.id)
    plan = user.plan
    return UserAdminView(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        is_verified=user.is_verified,
        plan_id=user.plan_id or "free",
        plan_name=plan.display_name if plan else "Free",
        usage_this_month=usage,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.patch("/users/{user_id}/plan", response_model=PlanChangeResponse)
async def change_user_plan(
    user_id: str,
    payload: PlanChangeRequest,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    CO: Zmienia plan subskrypcji wskazanego użytkownika.
    PO CO: Jedyna operacja zapisu w panelu admin. Zastępuje ręczny SQL.
           Przykład: tobroz@gmail.com free → agency (jedna akcja w UI).
    JAK: Weryfikuje że plan_id istnieje w tabeli plans, potem UPDATE users SET plan_id.
         selectinload dodany prewencyjnie na wypadek odwołania do user.plan po commit.
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Verify target plan exists
    valid_plans = ["free", "starter", "pro", "agency"]
    if payload.plan_id not in valid_plans:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan_id. Must be one of: {valid_plans}"
        )

    result = await db.execute(
        select(User)
        .options(selectinload(User.plan))  # eager load — fixes MissingGreenlet
        .where(User.id == uid)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_plan = user.plan_id or "free"
    user.plan_id = payload.plan_id
    await db.commit()
    await db.refresh(user)

    return PlanChangeResponse(
        user_id=str(user.id),
        email=user.email,
        old_plan=old_plan,
        new_plan=payload.plan_id,
        message=f"Plan changed: {old_plan} → {payload.plan_id}"
    )


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    CO: Statystyki systemu — liczba userów, podział planów, generacje.
    PO CO: Dashboard overview dla admina — quick health check produktu.
    JAK: Aggregate queries na users + usage_logs.
         Nie odwołuje się do User.plan — selectinload nie potrzebny.
    """
    # Total users
    total_result = await db.execute(select(func.count(User.id)))
    total_users = total_result.scalar_one() or 0

    # Users by plan
    plan_result = await db.execute(
        select(User.plan_id, func.count(User.id))
        .group_by(User.plan_id)
    )
    users_by_plan = {row[0] or "free": row[1] for row in plan_result.all()}

    # Active users last 30 days (at least 1 generation)
    now = datetime.now(timezone.utc)
    thirty_days_ago = now.replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = thirty_days_ago.replace(
        day=max(1, thirty_days_ago.day - 30)
    )
    active_result = await db.execute(
        select(func.count(func.distinct(UsageLog.user_id)))
        .where(UsageLog.created_at >= thirty_days_ago)
    )
    active_users_30d = active_result.scalar_one() or 0

    # Generations today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.created_at >= today_start)
        .where(UsageLog.success == True)  # noqa: E712
    )
    generations_today = today_result.scalar_one() or 0

    return AdminStatsResponse(
        total_users=total_users,
        users_by_plan=users_by_plan,
        active_users_30d=active_users_30d,
        generations_today=generations_today,
    )
