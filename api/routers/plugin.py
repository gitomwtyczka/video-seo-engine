"""Router: /v1/plugin/* — WordPress Plugin v3.0 (vse-video-seo) Backend API.

CO: Obsługuje generowanie i walidację kluczy API dla wtyczki WordPress `vse-video-seo` (v3.0),
    pobieranie paczki `.zip` wtyczki (`GET/HEAD /v1/plugin/download`),
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
    "starter": 50,
    "pro": 250,
    "agency": 1000,
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

@router.api_route("/download", methods=["GET", "HEAD"])
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
        api_key=raw_key,\n        key_prefix=key_prefix,\n        name=new_key.name or "WordPress Plugin",\n        allowed_domain=new_key.allowed_domain,\n        is_active=bool(new_key.is_active),\n        created_at=new_key.created_at,\n    )\n\n\n@router.get("/keys", response_model=list[ApiKeyItemResponse])\nasync def list_plugin_api_keys(\n    current_user: User = Depends(get_current_user),\n    db: AsyncSession = Depends(get_db),\n) -> list[ApiKeyItemResponse]:\n    """List all plugin API keys belonging to the authenticated user."""\n    result = await db.execute(\n        select(ApiKey)\n        .where(ApiKey.user_id == current_user.id)\n        .order_by(ApiKey.created_at.desc())\n    )\n    keys = result.scalars().all()\n    return [\n        ApiKeyItemResponse(\n            id=str(k.id),\n            key_prefix=getattr(k, "key_prefix", None) or "vse_live_...",\n            name=getattr(k, "name", None) or "WordPress Plugin",\n            allowed_domain=getattr(k, "allowed_domain", None),\n            is_active=bool(k.is_active),\n            created_at=k.created_at,\n            last_used_at=getattr(k, "last_used_at", None),\n        )\n        for k in keys\n    ]\n\n\n@router.post("/validate", response_model=ValidateKeyResponse)\nasync def validate_plugin_api_key(\n    req: ValidateKeyRequest,\n    db: AsyncSession = Depends(get_db),\n) -> ValidateKeyResponse:\n    """Validate an API key from the WordPress plugin, auto-pair WpPortal, and return plan & quota usage."""\n    effective_domain_input = req.domain or req.site_url\n    api_key_obj, user = await _verify_api_key_and_domain(db, req.api_key, effective_domain_input)\n    plan_id, monthly_quota = _resolve_quota_for_user(user)\n    used = await _get_monthly_usage(db, user.id)\n    remaining = -1 if monthly_quota < 0 else max(0, monthly_quota - used)\n    extra_balance = int(getattr(user, "extra_quota_balance", 0) or 0)\n\n    # Auto-pairing WpPortal for 1-click connection (no WP Application Passwords needed)\n    norm_domain = _normalize_domain(req.domain or req.site_url or api_key_obj.allowed_domain)\n    paired_portal: Optional[WpPortal] = None\n\n    if norm_domain:\n        raw_site_url = (req.site_url or f"https://{norm_domain}").strip().rstrip("/")\n        if "://" not in raw_site_url:\n            raw_site_url = f"https://{raw_site_url}"\n        portal_url = raw_site_url\n        portal_name = (req.site_name or norm_domain).strip()[:255]\n\n        res_portals = await db.execute(\n            select(WpPortal).where(WpPortal.user_id == user.id)\n        )\n        user_portals = list(res_portals.scalars().all())\n\n        for p in user_portals:\n            if getattr(p, "api_key_id", None) == api_key_obj.id or _normalize_domain(p.url) == norm_domain:\n                paired_portal = p\n                break\n\n        if paired_portal is None:\n            is_default = len(user_portals) == 0\n            paired_portal = WpPortal(\n                user_id=user.id,\n                name=portal_name,\n                url=portal_url,\n                wp_username="",\n                wp_app_password="",\n                auth_mode="plugin_token",\n                api_key_id=api_key_obj.id,\n                is_default=is_default,\n            )\n            db.add(paired_portal)\n            await db.commit()\n            await db.refresh(paired_portal)\n            logger.info(\n                "[/v1/plugin/validate] Auto-paired new WpPortal '%s' (%s) for user %s via key %s",\n                portal_name, portal_url, user.id, api_key_obj.key_prefix,\n            )\n        else:\n            paired_portal.auth_mode = "plugin_token"\n            paired_portal.api_key_id = api_key_obj.id\n            paired_portal.url = portal_url\n            if req.site_name and (\n                not paired_portal.name or _normalize_domain(paired_portal.name) == norm_domain\n            ):\n                paired_portal.name = portal_name\n            await db.commit()\n            await db.refresh(paired_portal)\n            logger.info(\n                "[/v1/plugin/validate] Updated paired WpPortal '%s' (%s) to plugin_token for user %s",\n                paired_portal.name, portal_url, user.id,\n            )\n\n    multilang = await check_multilang_access(user.id, db, user=user)\n    multilang_enabled = bool(\n        multilang.get("allow_target_override", False) or multilang.get("has_multilang_addon", False)\n    )\n\n    return ValidateKeyResponse(\n        valid=True,\n        plan=plan_id,\n        monthly_quota=monthly_quota,\n        used_this_month=used,\n        remaining_quota=remaining,\n        extra_quota_balance=extra_balance,\n        allowed_domain=api_key_obj.allowed_domain,\n        portal_paired=paired_portal is not None,\n        portal_id=str(paired_portal.id) if paired_portal else None,\n        portal_name=paired_portal.name if paired_portal else None,\n        multilang_enabled=multilang_enabled,\n    )\n\n\n@router.post("/preview", response_model=PreviewResponse)\nasync def preview_video_seo(\n    req: PreviewRequest,\n) -> PreviewResponse:\n    """Analyze a YouTube video URL and return Video SEO Score + Google Rich Result preview."""\n    try:\n        video_id = extract_video_id(req.video_url.strip())\n    except ValueError as exc:\n        raise HTTPException(\n            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,\n            detail=f"Nieprawidłowy link YouTube: {exc}",\n        ) from exc\n\n    meta = await asyncio.to_thread(_fetch_video_metadata_fast, video_id)\n    description = meta.get("description", "") or ""\n    duration_sec = int(meta.get("duration_seconds") or 300)\n    duration_iso_str = meta.get("duration_iso") or iso_duration(duration_sec)\n    desc_chapters = _extract_description_chapters(description)\n\n    # Calculate baseline Video SEO Score (without VSE Schema in <head>)\n    before_score = 22\n    if len(meta.get("title", "")) >= 30:\n        before_score += 4\n    if len(description) >= 150:\n        before_score += 3\n    if desc_chapters:\n        before_score += 5\n\n    after_score = 96\n\n    missing_elements = [\n        "Brak czystego VideoObject JSON-LD w sekcji <head> (wp_kses_post wycina <script> z treści)",\n        "Brak znaczników Clip Schema (Key Moments) — Google nie wyświetli osi rozdziałów w SERP",\n        "Brak sekcji FAQPage Schema powiązanej z transkrypcją wideo",\n        "Brak automatycznej synchronizacji Focus Keyword z RankMath / Yoast / SEOPress",\n    ]\n\n    estimated_clips = len(desc_chapters) if len(desc_chapters) >= 3 else max(4, min(8, duration_sec // 90 or 5))\n    key_moments = desc_chapters if desc_chapters else [\n        {"time": 0, "timestamp": "00:00", "label": "Wprowadzenie i główny temat nagrania"},\n        {"time": max(30, duration_sec // 4), "timestamp": "01:30", "label": "Kluczowe argumenty i analiza"},\n        {"time": max(90, duration_sec // 2), "timestamp": "03:45", "label": "Praktyczne wnioski i przykłady"},\n        {"time": max(150, (duration_sec * 3) // 4), "timestamp": "06:10", "label": "Podsumowanie materiału"},\n    ]\n\n    rich_result = {\n        "video_id": video_id,\n        "title": meta.get("title") or f"Film YouTube ({video_id})",\n        "channel_title": meta.get("channel_title") or "YouTube",\n        "thumbnail_url": meta.get("thumbnail_url") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",\n        "duration_seconds": duration_sec,\n        "duration_iso": duration_iso_str,\n        "view_count": int(meta.get("view_count") or 0),\n        "has_chapters_in_description": bool(desc_chapters),\n        "estimated_clips": estimated_clips,\n        "key_moments": key_moments,\n        "recommendation": (\n            f"Twój wpis traci {after_score - before_score}/100 pkt Video SEO! "\n            "Wstrzyknij VideoObject + Clip Schema, aby odblokować odznakę Key Moments w Google."\n        ),\n    }\n\n    return PreviewResponse(\n        status="ok",\n        video_id=video_id,\n        before_score=before_score,\n        after_score=after_score,\n        score_gain=after_score - before_score,\n        missing_elements=missing_elements,\n        rich_result=rich_result,\n    )\n\n\n@router.post("/inject-data", response_model=InjectDataResponse)\nasync def inject_plugin_video_seo(\n    req: InjectDataRequest,\n    db: AsyncSession = Depends(get_db),\n) -> InjectDataResponse:\n    """Generate full VideoObject + Clip + FAQPage JSON-LD, SEO Article, TL;DR, FAQ and SEO meta for the WordPress plugin."""\n    _, user = await _verify_api_key_and_domain(db, req.api_key, req.domain)\n    plan_id, monthly_quota = _resolve_quota_for_user(user)\n    used = await _get_monthly_usage(db, user.id)\n\n    effective_lang = (req.target_lang or req.lang or "pl").strip().lower()[:2]\n    if effective_lang != "pl":\n        entitlements = await check_multilang_access(user.id, db, user=user)\n        if not entitlements.get("allow_target_override", False) and not entitlements.get("has_multilang_addon", False):\n            raise HTTPException(\n                status_code=status.HTTP_403_FORBIDDEN,\n                detail=(\n                    "Generowanie w języku innym niż polski wymaga Pakietu Wielojęzycznego (+29 zł/mies.) "\n                    "lub planu Pro / Agency."\n                ),\n            )\n\n    extra_balance = int(getattr(user, "extra_quota_balance", 0) or 0)\n    if monthly_quota != -1 and used >= monthly_quota:\n        if extra_balance > 0:\n            user.extra_quota_balance = extra_balance - 1\n            extra_balance = user.extra_quota_balance\n            await db.flush()\n        else:\n            raise HTTPException(\n                status_code=status.HTTP_429_TOO_MANY_REQUESTS,\n                detail=(\n                    f"Wykorzystano miesięczny limit filmów w planie {plan_id.upper()} "\n                    f"({used}/{monthly_quota}). Dokup pakiet Top-Up (+50 / +150 / +500 filmów) "\n                    "lub przejdź na wyższy plan na https://vse.impresjapr.pl/dashboard"\n                ),\n            )\n\n    try:\n        video_id = extract_video_id(req.video_url.strip())\n    except ValueError as exc:\n        raise HTTPException(\n            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,\n            detail=f"Nieprawidłowy link YouTube: {exc}",\n        ) from exc\n\n    effective_provider = "gemini" if plan_id in ("free", "starter") else os.getenv("DEFAULT_LLM_PROVIDER", "gemini")\n\n    try:\n        result = await run_generate(\n            video_url=req.video_url.strip(),\n            llm_provider=effective_provider,\n            lang=effective_lang,\n            post_title_override=req.post_title,\n            publication_type="full_analysis",\n            user_id=str(user.id),\n            target_lang=effective_lang,\n        )\n    except Exception as exc:\n        logger.error("[/v1/plugin/inject-data] Generation failed for %s: %s", video_id, exc)\n        await log_usage(\n            user_id=user.id,\n            db=db,\n            youtube_id=video_id,\n            success=False,\n            error_msg=str(exc),\n            endpoint="/v1/plugin/inject-data",\n            llm_provider=effective_provider,\n        )\n        raise HTTPException(\n            status_code=status.HTTP_502_BAD_GATEWAY,\n            detail=f"Nie udało się wygenerować danych Video SEO: {exc}",\n        ) from exc\n\n    seo = dict(result.get("seo") or {})\n    meta = result.get("meta") or {}\n    saas_data = result.get("saas_data") or {}\n\n    upload_date = (\n        meta.get("published_at")\n        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")\n    )\n    seo["video_id"] = video_id\n    seo["target_lang"] = effective_lang\n    seo["upload_date"] = upload_date\n\n    # Save generated result to transcript_jobs so it appears in VSE Dashboard history and WP Plugin history\n    saved_job_id: Optional[str] = None\n    try:\n        res_job = await db.execute(\n            select(TranscriptJob)\n            .where(TranscriptJob.video_url.contains(video_id))\n            .where(TranscriptJob.user_id == user.id)\n            .where(TranscriptJob.status.in_(["fetched", "processing", "pending", "cloud_fallback"]))\n            .order_by(desc(TranscriptJob.created_at))\n            .limit(1)\n        )\n        existing_job = res_job.scalar_one_or_none()\n        if existing_job:\n            existing_job.schema_data = seo\n            existing_job.status = "done"\n            await db.flush()\n            saved_job_id = str(existing_job.id)\n        else:\n            new_job = TranscriptJob(\n                user_id=user.id,\n                video_url=req.video_url.strip(),\n                status="done",\n                schema_data=seo,\n            )\n            db.add(new_job)\n            await db.flush()\n            saved_job_id = str(new_job.id)\n    except Exception as job_exc:\n        logger.warning("[/v1/plugin/inject-data] Could not save TranscriptJob for %s: %s", video_id, job_exc)\n\n    await log_usage(\n        user_id=user.id,\n        db=db,\n        youtube_id=video_id,\n        success=True,\n        endpoint="/v1/plugin/inject-data",\n        llm_provider=result.get("llm_provider") or effective_provider,\n        input_tokens=result.get("input_tokens", 0),\n        output_tokens=result.get("output_tokens", 0),\n        estimated_cost_usd=result.get("estimated_cost_usd", 0.0),\n    )\n\n    used_after = used + 1\n\n    return _build_inject_response_from_seo(\n        seo=seo,\n        video_id=video_id,\n        plan_id=plan_id,\n        monthly_quota=monthly_quota,\n        used_this_month=used_after,\n        extra_quota_balance=extra_balance,\n        job_id=saved_job_id,\n        target_lang=effective_lang,\n        saas_data=saas_data,\n        upload_date=upload_date,\n    )\n\n\n@router.post("/history", response_model=PluginHistoryResponse)\nasync def list_plugin_history(\n    req: PluginHistoryRequest,\n    db: AsyncSession = Depends(get_db),\n) -> PluginHistoryResponse:\n    """Return recent completed VSE generations for the user (Pull from VSE to WP without consuming quota)."""\n    _, user = await _verify_api_key_and_domain(db, req.api_key, req.domain)\n\n    result = await db.execute(\n        select(TranscriptJob)\n        .where(TranscriptJob.user_id == user.id)\n        .where(TranscriptJob.status.in_(["done", "completed"]))\n        .where(TranscriptJob.schema_data.isnot(None))\n        .order_by(desc(TranscriptJob.created_at))\n        .limit(req.limit)\n    )\n    jobs = result.scalars().all()\n\n    items: list[PluginHistoryItemSummary] = []\n    for j in jobs:\n        raw_schema = j.schema_data if isinstance(j.schema_data, dict) else {}\n        seo = raw_schema.get("seo") if isinstance(raw_schema.get("seo"), dict) else raw_schema\n        vid = str(seo.get("video_id") or "")\n        if not vid and j.video_url:\n            try:\n                vid = extract_video_id(j.video_url)\n            except Exception:\n                vid = ""\n        post_title = str(seo.get("post_title") or seo.get("seo_title") or vid or j.video_url)\n        seo_title = str(seo.get("seo_title") or post_title)\n        lang = str(seo.get("target_lang") or raw_schema.get("target_lang") or "pl")[:2]\n\n        items.append(\n            PluginHistoryItemSummary(\n                job_id=str(j.id),\n                video_url=j.video_url,\n                video_id=vid,\n                post_title=post_title,\n                seo_title=seo_title,\n                created_at=j.created_at.isoformat() if j.created_at else "",\n                lang=lang,\n            )\n        )\n\n    return PluginHistoryResponse(\n        status="ok",\n        items=items,\n        total=len(items),\n    )\n\n\n@router.post("/history-item", response_model=InjectDataResponse)\nasync def get_plugin_history_item(\n    req: PluginHistoryItemRequest,\n    db: AsyncSession = Depends(get_db),\n) -> InjectDataResponse:\n    """Fetch a specific completed VSE generation by job_id and return full InjectDataResponse (0 quota consumed)."""\n    _, user = await _verify_api_key_and_domain(db, req.api_key, req.domain)\n\n    try:\n        job_uuid = uuid.UUID(req.job_id.strip())\n    except ValueError as exc:\n        raise HTTPException(\n            status_code=status.HTTP_400_BAD_REQUEST,\n            detail="Nieprawidłowy format job_id.",\n        ) from exc\n\n    result = await db.execute(\n        select(TranscriptJob)\n        .where(TranscriptJob.id == job_uuid)\n        .where(TranscriptJob.user_id == user.id)\n    )\n    job = result.scalar_one_or_none()\n    if not job or not isinstance(job.schema_data, dict):\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="Nie znaleziono wygenerowanego materiału w historii VSE.",\n        )\n\n    raw_schema = job.schema_data\n    seo = raw_schema.get("seo") if isinstance(raw_schema.get("seo"), dict) else raw_schema\n    video_id = str(seo.get("video_id") or "")\n    if not video_id and job.video_url:\n        try:\n            video_id = extract_video_id(job.video_url)\n        except Exception:\n            video_id = "unknown"\n\n    target_lang = str(seo.get("target_lang") or raw_schema.get("target_lang") or "pl")[:2]\n    plan_id, monthly_quota = _resolve_quota_for_user(user)\n    used = await _get_monthly_usage(db, user.id)\n    extra_balance = int(getattr(user, "extra_quota_balance", 0) or 0)\n\n    return _build_inject_response_from_seo(\n        seo=seo,\n        video_id=video_id,\n        plan_id=plan_id,\n        monthly_quota=monthly_quota,\n        used_this_month=used,\n        extra_quota_balance=extra_balance,\n        job_id=str(job.id),\n        target_lang=target_lang,\n    )\n