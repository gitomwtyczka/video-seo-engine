"""
Portals router: CRUD for WordPress portals per user.

CO: Endpointy zarządzania portalami WordPress użytkownika.
PO CO: Użytkownik zapisuje portale WP w bazie (URL + credentials lub sparowana wtyczka VSE v3.0)
       i wybiera je z dropdown w InjectModal zamiast wpisywać ręcznie za każdym razem.
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
from api.routers.profiles import _generate_profile_yaml, CreateProfileRequest

router = APIRouter(prefix="/v1/portals", tags=["portals"])
logger = logging.getLogger(__name__)


# --- Pydantic schemas ---

class PortalCreate(BaseModel):
    """Request body for creating a new portal."""
    name: str
    url: str
    wp_username: Optional[str] = ""
    wp_app_password: Optional[str] = ""
    auth_mode: str = "app_password"  # "app_password" | "plugin_token"
    api_key_id: Optional[str] = None
    profile_id: Optional[str] = None
    is_default: bool = False


class PortalUpdate(BaseModel):
    """Request body for updating a portal (all fields optional)."""
    name: Optional[str] = None
    url: Optional[str] = None
    wp_username: Optional[str] = None
    wp_app_password: Optional[str] = None
    auth_mode: Optional[str] = None
    api_key_id: Optional[str] = None
    profile_id: Optional[str] = None
    is_default: Optional[bool] = None


class PortalResponse(BaseModel):
    """Portal data returned to frontend. NOTE: wp_app_password is NEVER returned."""
    id: str
    name: str
    url: str
    wp_username: str = ""
    auth_mode: str = "app_password"
    is_plugin_connected: bool = False
    api_key_id: Optional[str] = None
    profile_id: Optional[str] = None
    is_default: bool
    created_at: Optional[str] = None


class PortalFull(BaseModel):
    """Portal data WITH password — returned only on GET /v1/portals/{id}/full."""
    id: str
    name: str
    url: str
    wp_username: str = ""
    wp_app_password: str = ""
    auth_mode: str = "app_password"
    is_plugin_connected: bool = False
    api_key_id: Optional[str] = None
    profile_id: Optional[str] = None
    is_default: bool


class PortalListResponse(BaseModel):
    """List of portals for the current user."""
    portals: List[PortalResponse]
    total: int


# --- Helpers ---

def _portal_to_response(portal: WpPortal) -> PortalResponse:
    """Convert ORM WpPortal to PortalResponse (without password)."""
    auth_mode = getattr(portal, "auth_mode", None) or "app_password"
    api_key_id = getattr(portal, "api_key_id", None)
    return PortalResponse(
        id=str(portal.id),
        name=portal.name,
        url=portal.url,
        wp_username=portal.wp_username or "",
        auth_mode=auth_mode,
        is_plugin_connected=(auth_mode == "plugin_token"),
        api_key_id=str(api_key_id) if api_key_id else None,
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


def _auto_create_profile(
    portal_id: str,
    site_name: str,
    wp_url: str,
    wp_user: str,
    wp_password: str,
) -> None:
    """Auto-create a profile YAML when creating a portal without existing profile."""
    profiles_dir = os.path.join(os.getcwd(), "profiles")
    os.makedirs(profiles_dir, exist_ok=True)

    target_path = os.path.join(profiles_dir, f"{portal_id}.yaml")
    if os.path.exists(target_path):
        logger.info("[portals] Profile %s already exists, skipping auto-create", portal_id)
        return

    req = CreateProfileRequest(
        portal_id=portal_id,
        display_name=site_name,
        site_brand=site_name,
        wp_base_url=wp_url,
        default_type="full_analysis",
        seo_language="pl",
    )

    try:
        yaml_content = _generate_profile_yaml(req)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        logger.info(
            "[portals] Auto-created profile YAML: %s for portal '%s'",
            target_path, site_name,
        )
    except Exception as exc:
        logger.error("[portals] Failed to auto-create profile %s: %s", portal_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to auto-create profile: {exc}",
        )


# --- Endpoints ---

@router.get("", response_model=PortalListResponse)
async def list_portals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Zwraca listę portali WP zalogowanego użytkownika."""
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
    """Dodaje nowy portal WP do konta użytkownika (app_password lub plugin_token)."""
    if payload.profile_id:
        yaml_path = f"profiles/{payload.profile_id}.yaml"
        if not os.path.exists(yaml_path):
            _auto_create_profile(
                portal_id=payload.profile_id,
                site_name=payload.name,
                wp_url=payload.url,
                wp_user=payload.wp_username or "",
                wp_password=payload.wp_app_password or "",
            )

    if payload.is_default:
        existing = await db.execute(
            select(WpPortal)
            .where(WpPortal.user_id == current_user.id)
            .where(WpPortal.is_default == True)  # noqa: E712
        )
        for portal in existing.scalars().all():
            portal.is_default = False

    api_key_uuid = None
    if payload.api_key_id:
        try:
            api_key_uuid = uuid.UUID(payload.api_key_id)
        except ValueError:
            pass

    auth_mode = payload.auth_mode if payload.auth_mode in ("app_password", "plugin_token") else "app_password"

    portal = WpPortal(
        user_id=current_user.id,
        name=payload.name,
        url=payload.url.rstrip("/"),
        wp_username=payload.wp_username or "",
        wp_app_password=payload.wp_app_password or "",
        auth_mode=auth_mode,
        api_key_id=api_key_uuid,
        profile_id=payload.profile_id,
        is_default=payload.is_default,
    )
    db.add(portal)
    await db.commit()
    await db.refresh(portal)

    logger.info(
        "Portal created: %s (%s, auth_mode=%s) for user %s",
        portal.name, portal.url, auth_mode, current_user.email,
    )
    return _portal_to_response(portal)


@router.get("/{portal_id}/full", response_model=PortalFull)
async def get_portal_full(
    portal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Zwraca pełne dane portalu WŁĄCZNIE z hasłem."""
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

    auth_mode = getattr(portal, "auth_mode", None) or "app_password"
    api_key_id = getattr(portal, "api_key_id", None)
    return PortalFull(
        id=str(portal.id),
        name=portal.name,
        url=portal.url,
        wp_username=portal.wp_username or "",
        wp_app_password=portal.wp_app_password or "",
        auth_mode=auth_mode,
        is_plugin_connected=(auth_mode == "plugin_token"),
        api_key_id=str(api_key_id) if api_key_id else None,
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
    """Aktualizuje dane istniejącego portalu."""
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
    if payload.auth_mode is not None and payload.auth_mode in ("app_password", "plugin_token"):
        portal.auth_mode = payload.auth_mode
    if payload.api_key_id is not None:
        try:
            portal.api_key_id = uuid.UUID(payload.api_key_id) if payload.api_key_id else None
        except ValueError:
            pass
    if payload.profile_id is not None:
        portal.profile_id = payload.profile_id
    if payload.is_default is not None:
        if payload.is_default:
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
    """Usuwa portal WP z konta użytkownika."""
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
