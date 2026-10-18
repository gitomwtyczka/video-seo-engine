"""Router: /v1/plugin/* — WordPress Plugin v3.0 (vse-video-seo) Backend API.

CO: Obsługuje generowanie i walidację kluczy API dla wtyczki WordPress `vse-video-seo` (v3.0),
    pobieranie paczki `.zip` wtyczki (`GET /v1/plugin/download`),
    auto-parowanie portalu WordPress (`POST /v1/plugin/validate`),
    darmowy podgląd Video SEO Score + Google Rich Result (`POST /v1/plugin/preview`),
    generowanie pełnego pakietu VSE: Artykuł + TL;DR + Rozdziały + FAQ + Schema JSON-LD + Meta SEO
    (`POST /v1/plugin/inject-data`) oraz pobieranie historii generacji z VSE bez zużycia quota
    (`POST /v1/plugin/history` i `POST /v1/plugin/history-item`).

PO CO: Wtyczka `vse-video-seo` v3.0 łączy funkcję Lead Magnetu PLG z pełnym dwukierunkowym
       mostem publikacyjnym VSE <-> WordPress (bez konieczności konfigurowania WP Application Passwords).
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import io
import logging
import os
from pathlib import Path
import re
import secrets
from typing import Any, Optional
from urllib.parse import urlparse
import uuid
import zipfile

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
import requests
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.db import get_db
from api.models.job import TranscriptJob
from api.models.portal import WpPortal
from api.models.user import ApiKey, User, UsageLog
from api.quota import check_multilang_access, get_effective_monthly_quota, log_usage
from api.services.pipeline import run_generate
from core.fetcher import (
    extract_video_id,
    fetch_metadata_api_v3,
    fetch_metadata_ytdlp,
    iso_duration,
)
from core.injector import (
    _build_rankmath_meta,
    build_focus_keywords,
    build_schema_jsonld,
    build_wp_article_sections,
    build_wp_post_html,
)

router = APIRouter(prefix="/v1/plugin", tags=["plugin"])
logger = logging.getLogger(__name__)

PLAN_LIMITS: dict[str, int] = {
    "free": 5,
    "starter": 30,
    "pro": 110,
    "agency": 250,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_api_key(raw_key: str) -> str:
    """Return SHA-256 hex digest of an API key."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def _normalize_domain(domain_or_url: Optional[str]) -> Optional[str]:
    """Normalize domain name (strip scheme, path, port, and leading www.)."""
    if not domain_or_url:
        return None
    raw = domain_or_url.strip().lower()
    if not raw:
        return None
    if "://" in raw:
        parsed = urlparse(raw)
        host = parsed.hostname or ""
    else:
        host = raw.split("/")[0].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


async def _get_monthly_usage(db: AsyncSession, user_id: Any) -> int:
    """Count successful pipeline/plugin generations in the current UTC month (excluding adaptations and topup markers)."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.user_id == user_id)
        .where(UsageLog.success == True)  # noqa: E712
        .where(UsageLog.endpoint != "adapt_material")
        .where(~UsageLog.endpoint.like("topup:%"))
        .where(UsageLog.created_at >= month_start)
    )
    return int(result.scalar_one() or 0)


def _resolve_quota_for_user(user: User) -> tuple[str, int]:
    """Return (plan_id, effective_monthly_quota) for a User."""
    plan_id = (getattr(user, "plan_id", None) or "free").lower()
    custom_q = getattr(user, "custom_monthly_quota", None)
    if custom_q is not None:
        return plan_id, int(custom_q)
    if user.plan and user.plan.monthly_quota is not None:
        return plan_id, int(user.plan.monthly_quota)
    return plan_id, PLAN_LIMITS.get(plan_id, 5)


async def _verify_api_key_and_domain(
    db: AsyncSession,
    raw_key: str,
    domain: Optional[str] = None,
) -> tuple[ApiKey, User]:
    """Validate API key hash, active flag, and optional domain binding."""
    if not raw_key or not raw_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Brak klucza API VSE.",
        )

    key_hash = _hash_api_key(raw_key)
    result = await db.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.user).selectinload(User.plan))
        .where(ApiKey.key_hash == key_hash)
    )
    api_key_obj = result.scalar_one_or_none()

    if not api_key_obj or not api_key_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy lub nieaktywny klucz API VSE.",
        )

    user = api_key_obj.user
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Konto użytkownika powiązane z tym kluczem API jest nieaktywne.",
        )

    norm_domain = _normalize_domain(domain)
    norm_allowed = _normalize_domain(getattr(api_key_obj, "allowed_domain", None))

    if norm_domain:
        if not norm_allowed:
            # First use: bind domain automatically
            api_key_obj.allowed_domain = norm_domain
        elif norm_allowed != norm_domain and norm_domain not in ("localhost", "127.0.0.1"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Klucz API jest przypisany do domeny '{norm_allowed}', "
                    f"a zapytanie pochodzi z '{norm_domain}'."
                ),
            )

    api_key_obj.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return api_key_obj, user


def _fetch_video_metadata_fast(video_id: str) -> dict:
    """Fetch YouTube video metadata quickly for preview (API v3 -> oEmbed -> yt-dlp)."""
    yt_api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if yt_api_key:
        meta = fetch_metadata_api_v3(video_id, yt_api_key)
        if meta and meta.get("title"):
            return meta

    # Fast fallback: YouTube oEmbed endpoint (never blocked on cloud IPs)
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        resp = requests.get(oembed_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "video_id": video_id,
                "title": data.get("title", f"YouTube Video {video_id}"),
                "description": "",
                "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "duration_seconds": 360,
                "duration_iso": "PT6M",
                "view_count": 0,
                "thumbnail_url": data.get("thumbnail_url") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "channel_title": data.get("author_name", "YouTube"),
                "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
            }
    except Exception as exc:
        logger.debug("[plugin/preview] oEmbed fallback failed for %s: %s", video_id, exc)

    meta = fetch_metadata_ytdlp(video_id)
    if meta and meta.get("title"):
        return meta

    return {
        "video_id": video_id,
        "title": f"Film YouTube ({video_id})",
        "description": "",
        "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": 300,
        "duration_iso": "PT5M",
        "view_count": 0,
        "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "channel_title": "YouTube",
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
    }


def _extract_description_chapters(description: str) -> list[dict]:
    """Parse timestamps (e.g. 02:15 Label) from a YouTube video description if present."""
    if not description:
        return []
    chapters: list[dict] = []
    pattern = re.compile(r"(?:^|\s)(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]?\s*(.+)$", re.MULTILINE)
    for match in pattern.finditer(description):
        ts_str = match.group(1)
        label = match.group(2).strip()[:80]
        parts = [int(p) for p in ts_str.split(":")]
        if len(parts) == 3:
            sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            sec = parts[0] * 60 + parts[1]
        if label:
            chapters.append({"time": sec, "timestamp": ts_str, "label": label})
    return chapters[:12]


def _build_inject_response_from_seo(
    seo: dict[str, Any],
    video_id: str,
    plan_id: str,
    monthly_quota: int,
    used_this_month: int,
    extra_quota_balance: int,
    job_id: Optional[str] = None,
    target_lang: str = "pl",
    saas_data: Optional[dict] = None,
    upload_date: Optional[str] = None,
) -> "InjectDataResponse":
    """Construct a complete InjectDataResponse from a generated SEO dict."""
    resolved_upload_date = (
        upload_date
        or seo.get("upload_date")
        or seo.get("published_at")
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    )
    schemas = build_schema_jsonld(
        seo=seo,
        yt_id=video_id,
        upload_date=resolved_upload_date,
        target_lang=target_lang,
    )
    sections = build_wp_article_sections(
        seo=seo,
        yt_id=video_id,
        schemas=schemas,
        include_embed=True,
    )
    full_article_html = build_wp_post_html(
        seo=seo,
        yt_id=video_id,
        schemas=schemas,
        include_embed=True,
        post_format="full_article",
    )

    rm_meta = _build_rankmath_meta(seo, saas_data)
    post_title = sections["post_title"] or seo.get("post_title") or seo.get("seo_title") or ""
    seo_title = (
        rm_meta.get("rank_math_title")
        or seo.get("seo_title")
        or post_title
        or f"Film YouTube ({video_id})"
    )
    meta_description = rm_meta.get("rank_math_description") or seo.get("meta_description") or ""
    focus_keyword = (
        rm_meta.get("rank_math_focus_keyword")
        or build_focus_keywords(seo, saas_data)
        or seo.get("focus_keyphrase", "")
    )
    chapters = seo.get("chapters") or []
    remaining = -1 if monthly_quota < 0 else max(0, monthly_quota - used_this_month)

    return InjectDataResponse(
        status="ok",
        job_id=job_id,
        video_id=video_id,
        before_score=28,
        after_score=96,
        post_title=post_title,
        seo_title=seo_title,
        meta_description=meta_description,
        focus_keyword=focus_keyword,
        chapters=chapters,
        schema_json=schemas,
        full_article_html=full_article_html,
        article_body_html=sections["article_body_html"],
        tldr_html=sections["tldr_html"],
        chapters_html=sections["chapters_html"],
        faq_html=sections["faq_html"],
        summary_bullets=sections["summary_bullets"],
        faq=sections["faq"],
        quotes=sections["quotes"],
        target_lang=target_lang,
        plan=plan_id,
        monthly_quota=monthly_quota,
        used_this_month=used_this_month,
        remaining_quota=remaining,
        extra_quota_balance=extra_quota_balance,
    )


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class CreateKeyRequest(BaseModel):
    name: str = Field(default="WordPress Plugin", max_length=100)
    allowed_domain: Optional[str] = Field(default=None, max_length=255)


class CreateKeyResponse(BaseModel):
    id: str
    api_key: str
    key_prefix: str
    name: str
    allowed_domain: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None


class ApiKeyItemResponse(BaseModel):
    id: str
    key_prefix: str
    name: str
    allowed_domain: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


class ValidateKeyRequest(BaseModel):
    api_key: str
    domain: Optional[str] = None
    site_url: Optional[str] = None
    site_name: Optional[str] = None
    plugin_version: Optional[str] = None


class ValidateKeyResponse(BaseModel):
    valid: bool
    plan: str
    monthly_quota: int
    used_this_month: int
    remaining_quota: int
    extra_quota_balance: int = 0
    allowed_domain: Optional[str] = None
    portal_paired: bool = True
    portal_id: Optional[str] = None
    portal_name: Optional[str] = None
    multilang_enabled: bool = False
    upgrade_url: str = "https://vse.impresjapr.pl/cennik?utm_source=wp_plugin&utm_medium=settings"


class PreviewRequest(BaseModel):
    video_url: str
    api_key: Optional[str] = None
    domain: Optional[str] = None


class PreviewResponse(BaseModel):
    status: str = "ok"
    video_id: str
    before_score: int
    after_score: int
    score_gain: int
    missing_elements: list[str]
    rich_result: dict


class InjectDataRequest(BaseModel):
    api_key: str
    domain: Optional[str] = None
    video_url: str
    post_title: Optional[str] = None
    post_url: Optional[str] = None
    lang: str = "pl"
    target_lang: Optional[str] = None


class InjectDataResponse(BaseModel):
    status: str = "ok"
    job_id: Optional[str] = None
    video_id: str
    before_score: int
    after_score: int
    post_title: str = ""
    seo_title: str
    meta_description: str
    focus_keyword: str
    chapters: list[dict]
    schema_json: list[dict]
    full_article_html: str = ""
    article_body_html: str = ""
    tldr_html: str = ""
    chapters_html: str = ""
    faq_html: str = ""
    summary_bullets: list[str] = []
    faq: list[dict[str, Any]] = []
    quotes: list[dict[str, Any]] = []
    target_lang: str = "pl"
    plan: str
    monthly_quota: int
    used_this_month: int
    remaining_quota: int
    extra_quota_balance: int = 0
    upgrade_url: str = "https://vse.impresjapr.pl/cennik?utm_source=wp_plugin&utm_medium=gutenberg"


class PluginHistoryRequest(BaseModel):
    api_key: str
    domain: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


class PluginHistoryItemSummary(BaseModel):
    job_id: str
    video_url: str
    video_id: str
    post_title: str
    seo_title: str
    created_at: str
    lang: str = "pl"


class PluginHistoryResponse(BaseModel):
    status: str = "ok"
    items: list[PluginHistoryItemSummary]
    total: int


class PluginHistoryItemRequest(BaseModel):
    api_key: str
    domain: Optional[str] = None
    job_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/download")
async def download_wp_plugin_zip() -> Response:
    """Serve the official WordPress plugin `vse-video-seo.zip` package ready for 1-click WP Admin upload."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    plugin_dir = repo_root / "plugins" / "vse-video-seo"
    if not plugin_dir.exists() or not plugin_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Katalog wtyczki plugins/vse-video-seo nie został znaleziony na serwerze.",
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(plugin_dir.rglob("*")):
            if file_path.is_file():
                rel_path = file_path.relative_to(plugin_dir).as_posix()
                arcname = f"vse-video-seo/{rel_path}"
                zf.write(file_path, arcname=arcname)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="vse-video-seo.zip"',
            "Cache-Control": "no-cache",
        },
    )


@router.post("/keys", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_plugin_api_key(
    req: CreateKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateKeyResponse:
    """Generate a new `vse_live_<random>` license key for the authenticated user."""
    raw_key = f"vse_live_{secrets.token_hex(20)}"
    key_hash = _hash_api_key(raw_key)
    key_prefix = f"{raw_key[:14]}..."
    norm_domain = _normalize_domain(req.allowed_domain)

    new_key = ApiKey(
        user_id=current_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=(req.name or "WordPress Plugin").strip()[:100],
        allowed_domain=norm_domain,
        is_active=True,
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)

    logger.info(
        "[/v1/plugin/keys] Created API key %s for user %s (domain=%s)",
        key_prefix, current_user.id, norm_domain,
    )
    return CreateKeyResponse(
        id=str(new_key.id),
        api_key=raw_key,
        key_prefix=key_prefix,
        name=new_key.name or "WordPress Plugin",
        allowed_domain=new_key.allowed_domain,
        is_active=bool(new_key.is_active),
        created_at=new_key.created_at,
    )


@router.get("/keys", response_model=list[ApiKeyItemResponse])
async def list_plugin_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyItemResponse]:
    """List all plugin API keys belonging to the authenticated user."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        ApiKeyItemResponse(
            id=str(k.id),
            key_prefix=getattr(k, "key_prefix", None) or "vse_live_...",
            name=getattr(k, "name", None) or "WordPress Plugin",
            allowed_domain=getattr(k, "allowed_domain", None),
            is_active=bool(k.is_active),
            created_at=k.created_at,
            last_used_at=getattr(k, "last_used_at", None),
        )
        for k in keys
    ]


@router.post("/validate", response_model=ValidateKeyResponse)
async def validate_plugin_api_key(
    req: ValidateKeyRequest,
    db: AsyncSession = Depends(get_db),
) -> ValidateKeyResponse:
    """Validate an API key from the WordPress plugin, auto-pair WpPortal, and return plan & quota usage."""
    effective_domain_input = req.domain or req.site_url
    api_key_obj, user = await _verify_api_key_and_domain(db, req.api_key, effective_domain_input)
    plan_id, monthly_quota = _resolve_quota_for_user(user)
    used = await _get_monthly_usage(db, user.id)
    remaining = -1 if monthly_quota < 0 else max(0, monthly_quota - used)
    extra_balance = int(getattr(user, "extra_quota_balance", 0) or 0)

    # Auto-pairing WpPortal for 1-click connection (no WP Application Passwords needed)
    norm_domain = _normalize_domain(req.domain or req.site_url or api_key_obj.allowed_domain)
    paired_portal: Optional[WpPortal] = None

    if norm_domain:
        raw_site_url = (req.site_url or f"https://{norm_domain}").strip().rstrip("/")
        if "://" not in raw_site_url:
            raw_site_url = f"https://{raw_site_url}"
        portal_url = raw_site_url
        portal_name = (req.site_name or norm_domain).strip()[:255]

        res_portals = await db.execute(
            select(WpPortal).where(WpPortal.user_id == user.id)
        )
        user_portals = list(res_portals.scalars().all())

        for p in user_portals:
            if getattr(p, "api_key_id", None) == api_key_obj.id or _normalize_domain(p.url) == norm_domain:
                paired_portal = p
                break

        if paired_portal is None:
            is_default = len(user_portals) == 0
            paired_portal = WpPortal(
                user_id=user.id,
                name=portal_name,
                url=portal_url,
                wp_username="",
                wp_app_password="",
                auth_mode="plugin_token",
                api_key_id=api_key_obj.id,
                is_default=is_default,
            )
            db.add(paired_portal)
            await db.commit()
            await db.refresh(paired_portal)
            logger.info(
                "[/v1/plugin/validate] Auto-paired new WpPortal '%s' (%s) for user %s via key %s",
                portal_name, portal_url, user.id, api_key_obj.key_prefix,
            )
        else:
            paired_portal.auth_mode = "plugin_token"
            paired_portal.api_key_id = api_key_obj.id
            paired_portal.url = portal_url
            if req.site_name and (
                not paired_portal.name or _normalize_domain(paired_portal.name) == norm_domain
            ):
                paired_portal.name = portal_name
            await db.commit()
            await db.refresh(paired_portal)
            logger.info(
                "[/v1/plugin/validate] Updated paired WpPortal '%s' (%s) to plugin_token for user %s",
                paired_portal.name, portal_url, user.id,
            )

    multilang = await check_multilang_access(user.id, db, user=user)
    multilang_enabled = bool(
        multilang.get("allow_target_override", False) or multilang.get("has_multilang_addon", False)
    )

    return ValidateKeyResponse(
        valid=True,
        plan=plan_id,
        monthly_quota=monthly_quota,
        used_this_month=used,
        remaining_quota=remaining,
        extra_quota_balance=extra_balance,
        allowed_domain=api_key_obj.allowed_domain,
        portal_paired=paired_portal is not None,
        portal_id=str(paired_portal.id) if paired_portal else None,
        portal_name=paired_portal.name if paired_portal else None,
        multilang_enabled=multilang_enabled,
    )


@router.post("/preview", response_model=PreviewResponse)
async def preview_video_seo(
    req: PreviewRequest,
) -> PreviewResponse:
    """Analyze a YouTube video URL and return Video SEO Score + Google Rich Result preview."""
    try:
        video_id = extract_video_id(req.video_url.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nieprawidłowy link YouTube: {exc}",
        ) from exc

    meta = await asyncio.to_thread(_fetch_video_metadata_fast, video_id)
    description = meta.get("description", "") or ""
    duration_sec = int(meta.get("duration_seconds") or 300)
    duration_iso_str = meta.get("duration_iso") or iso_duration(duration_sec)
    desc_chapters = _extract_description_chapters(description)

    # Calculate baseline Video SEO Score (without VSE Schema in <head>)
    before_score = 22
    if len(meta.get("title", "")) >= 30:
        before_score += 4
    if len(description) >= 150:
        before_score += 3
    if desc_chapters:
        before_score += 5

    after_score = 96

    missing_elements = [
        "Brak czystego VideoObject JSON-LD w sekcji <head> (wp_kses_post wycina <script> z treści)",
        "Brak znaczników Clip Schema (Key Moments) — Google nie wyświetli osi rozdziałów w SERP",
        "Brak sekcji FAQPage Schema powiązanej z transkrypcją wideo",
        "Brak automatycznej synchronizacji Focus Keyword z RankMath / Yoast / SEOPress",
    ]

    estimated_clips = len(desc_chapters) if len(desc_chapters) >= 3 else max(4, min(8, duration_sec // 90 or 5))
    key_moments = desc_chapters if desc_chapters else [
        {"time": 0, "timestamp": "00:00", "label": "Wprowadzenie i główny temat nagrania"},
        {"time": max(30, duration_sec // 4), "timestamp": "01:30", "label": "Kluczowe argumenty i analiza"},
        {"time": max(90, duration_sec // 2), "timestamp": "03:45", "label": "Praktyczne wnioski i przykłady"},
        {"time": max(150, (duration_sec * 3) // 4), "timestamp": "06:10", "label": "Podsumowanie materiału"},
    ]

    rich_result = {
        "video_id": video_id,
        "title": meta.get("title") or f"Film YouTube ({video_id})",
        "channel_title": meta.get("channel_title") or "YouTube",
        "thumbnail_url": meta.get("thumbnail_url") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "duration_seconds": duration_sec,
        "duration_iso": duration_iso_str,
        "view_count": int(meta.get("view_count") or 0),
        "has_chapters_in_description": bool(desc_chapters),
        "estimated_clips": estimated_clips,
        "key_moments": key_moments,
        "recommendation": (
            f"Twój wpis traci {after_score - before_score}/100 pkt Video SEO! "
            "Wstrzyknij VideoObject + Clip Schema, aby odblokować odznakę Key Moments w Google."
        ),
    }

    return PreviewResponse(
        status="ok",
        video_id=video_id,
        before_score=before_score,
        after_score=after_score,
        score_gain=after_score - before_score,
        missing_elements=missing_elements,
        rich_result=rich_result,
    )


@router.post("/inject-data", response_model=InjectDataResponse)
async def inject_plugin_video_seo(
    req: InjectDataRequest,
    db: AsyncSession = Depends(get_db),
) -> InjectDataResponse:
    """Generate full VideoObject + Clip + FAQPage JSON-LD, SEO Article, TL;DR, FAQ and SEO meta for the WordPress plugin."""
    _, user = await _verify_api_key_and_domain(db, req.api_key, req.domain)
    plan_id, monthly_quota = _resolve_quota_for_user(user)
    used = await _get_monthly_usage(db, user.id)

    effective_lang = (req.target_lang or req.lang or "pl").strip().lower()[:2]
    if effective_lang != "pl":
        entitlements = await check_multilang_access(user.id, db, user=user)
        if not entitlements.get("allow_target_override", False) and not entitlements.get("has_multilang_addon", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Generowanie w języku innym niż polski wymaga Pakietu Wielojęzycznego (+29 zł/mies.) "
                    "lub planu Pro / Agency."
                ),
            )

    extra_balance = int(getattr(user, "extra_quota_balance", 0) or 0)
    if monthly_quota != -1 and used >= monthly_quota:
        if extra_balance > 0:
            user.extra_quota_balance = extra_balance - 1
            extra_balance = user.extra_quota_balance
            await db.flush()
        else:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Wykorzystano miesięczny limit filmów w planie {plan_id.upper()} "
                    f"({used}/{monthly_quota}). Dokup pakiet Top-Up (+50 / +150 / +500 filmów) "
                    "lub przejdź na wyższy plan na https://vse.impresjapr.pl/dashboard"
                ),
            )

    try:
        video_id = extract_video_id(req.video_url.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nieprawidłowy link YouTube: {exc}",
        ) from exc

    effective_provider = "gemini" if plan_id in ("free", "starter") else os.getenv("DEFAULT_LLM_PROVIDER", "gemini")

    try:
        result = await run_generate(
            video_url=req.video_url.strip(),
            llm_provider=effective_provider,
            lang=effective_lang,
            post_title_override=req.post_title,
            publication_type="full_analysis",
            user_id=str(user.id),
            target_lang=effective_lang,
        )
    except Exception as exc:
        logger.error("[/v1/plugin/inject-data] Generation failed for %s: %s", video_id, exc)
        await log_usage(
            user_id=user.id,
            db=db,
            youtube_id=video_id,
            success=False,
            error_msg=str(exc),
            endpoint="/v1/plugin/inject-data",
            llm_provider=effective_provider,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nie udało się wygenerować danych Video SEO: {exc}",
        ) from exc

    seo = dict(result.get("seo") or {})
    meta = result.get("meta") or {}
    saas_data = result.get("saas_data") or {}

    upload_date = (
        meta.get("published_at")
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    )
    seo["video_id"] = video_id
    seo["target_lang"] = effective_lang
    seo["upload_date"] = upload_date

    # Save generated result to transcript_jobs so it appears in VSE Dashboard history and WP Plugin history
    saved_job_id: Optional[str] = None
    try:
        res_job = await db.execute(
            select(TranscriptJob)
            .where(TranscriptJob.video_url.contains(video_id))
            .where(TranscriptJob.user_id == user.id)
            .where(TranscriptJob.status.in_(["fetched", "processing", "pending", "cloud_fallback"]))
            .order_by(desc(TranscriptJob.created_at))
            .limit(1)
        )
        existing_job = res_job.scalar_one_or_none()
        if existing_job:
            existing_job.schema_data = seo
            existing_job.status = "done"
            await db.flush()
            saved_job_id = str(existing_job.id)
        else:
            new_job = TranscriptJob(
                user_id=user.id,
                video_url=req.video_url.strip(),
                status="done",
                schema_data=seo,
            )
            db.add(new_job)
            await db.flush()
            saved_job_id = str(new_job.id)
    except Exception as job_exc:
        logger.warning("[/v1/plugin/inject-data] Could not save TranscriptJob for %s: %s", video_id, job_exc)

    await log_usage(
        user_id=user.id,
        db=db,
        youtube_id=video_id,
        success=True,
        endpoint="/v1/plugin/inject-data",
        llm_provider=result.get("llm_provider") or effective_provider,
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        estimated_cost_usd=result.get("estimated_cost_usd", 0.0),
    )

    used_after = used + 1

    return _build_inject_response_from_seo(
        seo=seo,
        video_id=video_id,
        plan_id=plan_id,
        monthly_quota=monthly_quota,
        used_this_month=used_after,
        extra_quota_balance=extra_balance,
        job_id=saved_job_id,
        target_lang=effective_lang,
        saas_data=saas_data,
        upload_date=upload_date,
    )


@router.post("/history", response_model=PluginHistoryResponse)
async def list_plugin_history(
    req: PluginHistoryRequest,
    db: AsyncSession = Depends(get_db),
) -> PluginHistoryResponse:
    """Return recent completed VSE generations for the user (Pull from VSE to WP without consuming quota)."""
    _, user = await _verify_api_key_and_domain(db, req.api_key, req.domain)

    result = await db.execute(
        select(TranscriptJob)
        .where(TranscriptJob.user_id == user.id)
        .where(TranscriptJob.status.in_(["done", "completed"]))
        .where(TranscriptJob.schema_data.isnot(None))
        .order_by(desc(TranscriptJob.created_at))
        .limit(req.limit)
    )
    jobs = result.scalars().all()

    items: list[PluginHistoryItemSummary] = []
    for j in jobs:
        raw_schema = j.schema_data if isinstance(j.schema_data, dict) else {}
        seo = raw_schema.get("seo") if isinstance(raw_schema.get("seo"), dict) else raw_schema
        vid = str(seo.get("video_id") or "")
        if not vid and j.video_url:
            try:
                vid = extract_video_id(j.video_url)
            except Exception:
                vid = ""
        post_title = str(seo.get("post_title") or seo.get("seo_title") or vid or j.video_url)
        seo_title = str(seo.get("seo_title") or post_title)
        lang = str(seo.get("target_lang") or raw_schema.get("target_lang") or "pl")[:2]

        items.append(
            PluginHistoryItemSummary(
                job_id=str(j.id),
                video_url=j.video_url,
                video_id=vid,
                post_title=post_title,
                seo_title=seo_title,
                created_at=j.created_at.isoformat() if j.created_at else "",
                lang=lang,
            )
        )

    return PluginHistoryResponse(
        status="ok",
        items=items,
        total=len(items),
    )


@router.post("/history-item", response_model=InjectDataResponse)
async def get_plugin_history_item(
    req: PluginHistoryItemRequest,
    db: AsyncSession = Depends(get_db),
) -> InjectDataResponse:
    """Fetch a specific completed VSE generation by job_id and return full InjectDataResponse (0 quota consumed)."""
    _, user = await _verify_api_key_and_domain(db, req.api_key, req.domain)

    try:
        job_uuid = uuid.UUID(req.job_id.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nieprawidłowy format job_id.",
        ) from exc

    result = await db.execute(
        select(TranscriptJob)
        .where(TranscriptJob.id == job_uuid)
        .where(TranscriptJob.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job or not isinstance(job.schema_data, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono wygenerowanego materiału w historii VSE.",
        )

    raw_schema = job.schema_data
    seo = raw_schema.get("seo") if isinstance(raw_schema.get("seo"), dict) else raw_schema
    video_id = str(seo.get("video_id") or "")
    if not video_id and job.video_url:
        try:
            video_id = extract_video_id(job.video_url)
        except Exception:
            video_id = "unknown"

    target_lang = str(seo.get("target_lang") or raw_schema.get("target_lang") or "pl")[:2]
    plan_id, monthly_quota = _resolve_quota_for_user(user)
    used = await _get_monthly_usage(db, user.id)
    extra_balance = int(getattr(user, "extra_quota_balance", 0) or 0)

    return _build_inject_response_from_seo(
        seo=seo,
        video_id=video_id,
        plan_id=plan_id,
        monthly_quota=monthly_quota,
        used_this_month=used,
        extra_quota_balance=extra_balance,
        job_id=str(job.id),
        target_lang=target_lang,
    )
