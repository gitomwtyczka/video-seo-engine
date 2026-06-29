"""
Portals router: CRUD for WordPress portals per user.

CO: Endpointy zarządzania portalami WordPress użytkownika.
PO CO: Użytkownik zapisuje portale WP w bazie (URL + credentials) i wybiera
       je z dropdown w InjectModal zamiast wpisywać ręcznie za każdym razem.
       Eliminuje potrzebę hardcode’owania credentials i localStorage.
JAK: CRUD pod /v1/portals, chroniony przez get_current_user (JWT).
     Każdy user widzi tylko swoje portale. Odpowiedź GET NIE zawiera
     wp_app_password (write-only — bezpieczeństwo).
"""
import logging
import uuid
import os
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.db import get_db
from api.auth import get_current_user
from api.models.user import User
from api.models.portal import WpPortal

router = APIRouter(prefix="/v1/portals", tags=["portals"])
logger = logging.getLogger(__name__)


# --- Pydantic schemas ---

class PortalCreate(BaseModel):
    """Request body for creating a new portal."""
    name: str
    url: str
    wp_username: str
    wp_app_password: str
    profile_id: Optional[str] = None
    is_default: bool = False


class PortalUpdate(BaseModel):
    """Request body for updating a portal (all fields optional)."""
    name: Optional[str] = None
    url: Optional[str] = None
    wp_username: Optional[str] = None
    wp_app_password: Optional[str] = None
    profile_id: Optional[str] = None
    is_default: Optional[bool] = None


class PortalResponse(BaseModel):
    """Portal data returned to frontend. NOTE: wp_app_password is NEVER returned."""
    id: str
    name: str
    url: str
    wp_username: str
    profile_id: Optional[str] = None
    is_default: bool
    created_at: Optional[str] = None


class PortalFull(BaseModel):
    """Portal data WITH password — returned only on GET /v1/portals/{id}/full."""
    id: str
    name: str
    url: str
    wp_username: str
    wp_app_password: str
    profile_id: Optional[str] = None
    is_default: bool


class PortalListResponse(BaseModel):
    """List of portals for the current user."""
    portals: List[PortalResponse]
    total: int


# --- Helpers ---

def _portal_to_response(portal: WpPortal) -> PortalResponse:
    """Convert ORM WpPortal to PortalResponse (without password)."""
    return PortalResponse(
        id=str(portal.id),
        name=portal.name,
        url=portal.url,
        wp_username=portal.wp_username,
        profile_id=portal.profile_id,
        is_default=portal.is_default or False,
        created_at=portal.created_at.isoformat() if portal.created_at else None,
    )


def _validate_profile_id(profile_id: str):
    """Check if profile YAML file exists."""
    if not os.path.exists(f"profiles/{profile_id}.yaml"):
        raise HTTPException(
            status_code=400,
            detail=f"Profile '{profile_id}' does not exist."
        )


# --- Endpoints ---

@router.get("", response_model=PortalListResponse)
async def list_portals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CO: Zwraca listę portali WP zalogowanego użytkownika.
    PO CO: Frontend InjectModal wyświetla dropdown z zapisanymi portalami.
    JAK: SELECT wp_portals WHERE user_id = current_user.id ORDER BY is_default DESC.
    """
    result = await db.execute(
        select(WpPortal)
        .where(WpPortal.user_id == current_user.id)
        .order_by(WpPortal.is_default.desc(), WpPortal.created_at.desc())
    )
    portals = result.scalars().all()
    return PortalListResponse(
        portals=[_portal_to_response(p) for p in portals],
        total=len(portals),
    )


@router.post("", response_model=PortalResponse, status_code=status.HTTP_201_CREATED)
async def create_portal(
    payload: PortalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CO: Dodaje nowy portal WP do konta użytkownika.
    PO CO: Użytkownik zapisuje credentials portalu raz — potem wybiera z listy.
    JAK: INSERT wp_portals. Jeśli is_default=True, resetuje poprzedni default.
    """
    if payload.profile_id:
        _validate_profile_id(payload.profile_id)

    # If setting as default, unset other defaults
    if payload.is_default:
        existing = await db.execute(
            select(WpPortal)
            .where(WpPortal.user_id == current_user.id)
            .where(WpPortal.is_default == True)  # noqa: E712
        )
        for portal in existing.scalars().all():
            portal.is_default = False

    portal = WpPortal(
        user_id=current_user.id,
        name=payload.name,
        url=payload.url.rstrip("/"),  # Normalize URL
        wp_username=payload.wp_username,
        wp_app_password=payload.wp_app_password,
        profile_id=payload.profile_id,
        is_default=payload.is_default,
    )
    db.add(portal)
    await db.commit()
    await db.refresh(portal)

    logger.info(
        "Portal created: %s (%s) for user %s",
        portal.name, portal.url, current_user.email,
    )
    return _portal_to_response(portal)


@router.get("/{portal_id}/full", response_model=PortalFull)
async def get_portal_full(
    portal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CO: Zwraca pełne dane portalu WŁĄCZNIE z hasłem.
    PO CO: Do użytku wewnętrznego, żeby pipeline mógł uzyskać hasło.
    JAK: SELECT wp_portals WHERE id AND user_id (security: user widzi tylko swoje).
    """
    try:
        uid = uuid.UUID(portal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid portal ID format")

    result = await db.execute(
        select(WpPortal)
        .where(WpPortal.id == uid)
        .where(WpPortal.user_id == current_user.id)
    )
    portal = result.scalar_one_or_none()
    if not portal:
        raise HTTPException(status_code=404, detail="Portal not found")

    return PortalFull(
        id=str(portal.id),
        name=portal.name,
        url=portal.url,
        wp_username=portal.wp_username,
        wp_app_password=portal.wp_app_password,
        profile_id=portal.profile_id,
        is_default=portal.is_default or False,
    )


@router.patch("/{portal_id}", response_model=PortalResponse)
async def update_portal(
    portal_id: str,
    payload: PortalUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CO: Aktualizuje dane istniejącego portalu.
    PO CO: Użytkownik może zmienić nazwę, URL lub credentials bez usuwania portalu.
    JAK: PATCH wp_portals SET ... WHERE id AND user_id.
    """
    try:
        uid = uuid.UUID(portal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid portal ID format")
        
    if payload.profile_id is not None:
        _validate_profile_id(payload.profile_id)

    result = await db.execute(
        select(WpPortal)
        .where(WpPortal.id == uid)
        .where(WpPortal.user_id == current_user.id)
    )
    portal = result.scalar_one_or_none()
    if not portal:
        raise HTTPException(status_code=404, detail="Portal not found")

    if payload.name is not None:
        portal.name = payload.name
    if payload.url is not None:
        portal.url = payload.url.rstrip("/")
    if payload.wp_username is not None:
        portal.wp_username = payload.wp_username
    if payload.wp_app_password is not None:
        portal.wp_app_password = payload.wp_app_password
    if payload.profile_id is not None:
        portal.profile_id = payload.profile_id
    if payload.is_default is not None:
        if payload.is_default:
            # Unset other defaults
            others = await db.execute(
                select(WpPortal)
                .where(WpPortal.user_id == current_user.id)
                .where(WpPortal.is_default == True)  # noqa: E712
                .where(WpPortal.id != uid)
            )
            for other in others.scalars().all():
                other.is_default = False
        portal.is_default = payload.is_default

    await db.commit()
    await db.refresh(portal)

    logger.info("Portal updated: %s for user %s", portal.name, current_user.email)
    return _portal_to_response(portal)


@router.delete("/{portal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portal(
    portal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CO: Usuwa portal WP z konta użytkownika.
    PO CO: Użytkownik może usunąć nieaktualny portal (np. zmienił hosting).
    JAK: DELETE wp_portals WHERE id AND user_id.
    """
    try:
        uid = uuid.UUID(portal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid portal ID format")

    result = await db.execute(
        select(WpPortal)
        .where(WpPortal.id == uid)
        .where(WpPortal.user_id == current_user.id)
    )
    portal = result.scalar_one_or_none()
    if not portal:
        raise HTTPException(status_code=404, detail="Portal not found")

    portal_name = portal.name
    await db.delete(portal)
    await db.commit()

    logger.info("Portal deleted: %s for user %s", portal_name, current_user.email)
    return None
