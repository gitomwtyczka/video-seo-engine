"""Router: POST /v1/inject — inject pre-generated schema into WordPress.

CO: FastAPI router obsługujący endpoint POST /v1/inject.

PO CO: Umożliwia dashboardowi opublikowanie wygenerowanych danych SEO bezpośrednio
na WordPress. Obsługuje dwa tryby autoryzacji portalu:
1) `plugin_token` (VSE WordPress Plugin v3.0): bezpośredni push do `/wp-json/vse/v1/publish`
   uwierzytelniany nagłówkami `X-VSE-Key-Hash` i `X-VSE-Key-Prefix` (bez WP App Passwords!).
2) `app_password` (legacy WP REST API `/wp-json/wp/v2/posts` z Basic Auth).
"""
from datetime import datetime, timezone
import json
import logging
from urllib.parse import urlparse
import uuid

from fastapi import APIRouter, Depends, HTTPException
import httpx
from sqlalchemy import select

from api.auth import get_current_user
from api.db import AsyncSessionLocal
from api.models.portal import WpPortal
from api.models.request import InjectRequest
from api.models.response import InjectResponse
from api.models.user import ApiKey, User
from api.models.job import TranscriptJob
from api.services.pipeline import _extract_video_id, run_inject
from core.injector import (
    _build_rankmath_meta,
    build_focus_keywords,
    build_schema_jsonld,
    build_wp_post_html,
)

router = APIRouter(prefix="/v1", tags=["inject"])
logger = logging.getLogger(__name__)


def _normalize_domain(url_or_domain: str | None) -> str | None:
    if not url_or_domain:
        return None
    raw = url_or_domain.strip().lower()
    if "://" in raw:
        host = urlparse(raw).hostname or ""
    else:
        host = raw.split("/")[0].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


async def _inject_via_plugin_endpoint(
    portal: WpPortal,
    user: User,
    req: InjectRequest,
) -> dict:
    """Push post + Schema JSON-LD + SEO Meta directly to WordPress via VSE Plugin v3.0 (/wp-json/vse/v1/publish)."""
    async with AsyncSessionLocal() as db:
        api_key_obj: ApiKey | None = None
        if getattr(portal, "api_key_id", None):
            res_k = await db.execute(
                select(ApiKey).where(
                    ApiKey.id == portal.api_key_id,
                    ApiKey.is_active == True,  # noqa: E712
                )
            )
            api_key_obj = res_k.scalar_one_or_none()

        if api_key_obj is None:
            portal_domain = _normalize_domain(portal.url)
            res_keys = await db.execute(
                select(ApiKey)
                .where(ApiKey.user_id == user.id, ApiKey.is_active == True)  # noqa: E712
                .order_by(ApiKey.created_at.desc())
            )
            all_keys = list(res_keys.scalars().all())
            for k in all_keys:
                if portal_domain and _normalize_domain(k.allowed_domain) == portal_domain:
                    api_key_obj = k
                    break

        if api_key_obj is None:
            raise HTTPException(
                status_code=400,
                detail="Brak aktywnego klucza API wtyczki VSE powiązanego z tym portalem. Wygeneruj i połącz klucz we wtyczce WordPress.",
            )

    video_id = _extract_video_id(req.video_url)
    seo = dict(req.schema_data or {})
    if not seo and req.job_id:
        try:
            async with AsyncSessionLocal() as db:
                j = await db.get(TranscriptJob, uuid.UUID(str(req.job_id)))
                if j and j.schema_data:
                    seo = dict(j.schema_data)
        except Exception as e:
            logger.warning("[inject] Could not load schema from job %s: %s", req.job_id, e)

    upload_date = (
        seo.get("upload_date")
        or seo.get("published_at")
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    )
    target_lang = str(seo.get("target_lang") or "pl").lower()[:2]
    schemas = build_schema_jsonld(
        seo=seo,
        yt_id=video_id,
        upload_date=upload_date,
        target_lang=target_lang,
    )
    post_content = build_wp_post_html(
        seo=seo,
        yt_id=video_id,
        schemas=schemas,
        include_embed=True,
        post_format="full_article",
    )

    rm_meta = _build_rankmath_meta(seo)
    post_title = (seo.get("post_title") or seo.get("seo_title") or f"Wideo {video_id}").strip()
    seo_title = (rm_meta.get("rank_math_title") or seo.get("seo_title") or post_title).strip()
    meta_description = (rm_meta.get("rank_math_description") or seo.get("meta_description") or "").strip()
    focus_keyword = (
        rm_meta.get("rank_math_focus_keyword")
        or build_focus_keywords(seo)
        or seo.get("focus_keyphrase")
        or ""
    ).strip()
    chapters = seo.get("chapters") or []

    publish_url = f"{portal.url.rstrip('/')}/wp-json/vse/v1/publish"
    payload = {
        "post_id": req.wp_post_id,
        "post_status": req.post_status or "draft",
        "post_title": post_title,
        "post_content": post_content,
        "video_url": req.video_url,
        "video_id": video_id,
        "seo_title": seo_title,
        "meta_description": meta_description,
        "focus_keyword": focus_keyword,
        "schema_json": json.dumps(schemas, ensure_ascii=False),
        "chapters_json": json.dumps(chapters, ensure_ascii=False),
        "seo_score": 96,
    }
    headers = {
        "X-VSE-Key-Hash": api_key_obj.key_hash,
        "X-VSE-Key-Prefix": api_key_obj.key_prefix or "",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(publish_url, json=payload, headers=headers)
    except Exception as exc:
        logger.error("[/v1/inject] Plugin publish connection error to %s: %s", publish_url, exc)
        raise RuntimeError(f"Nie udało się połączyć z wtyczką VSE na portalu {portal.url}: {exc}") from exc

    if resp.status_code not in (200, 201):
        logger.error(
            "[/v1/inject] Plugin publish HTTP %d from %s: %s",
            resp.status_code, publish_url, resp.text[:300],
        )
        raise RuntimeError(
            f"Wtyczka VSE na portalu {portal.url} zwróciła błąd HTTP {resp.status_code}: {resp.text[:200]}"
        )

    wp_data = resp.json() if resp.text.strip() else {}
    wp_post_id = wp_data.get("post_id") or req.wp_post_id
    post_url = wp_data.get("post_url") or wp_data.get("link")

    logger.info(
        "[/v1/inject] Published via VSE WP Plugin v3.0 to %s: post_id=%s url=%s",
        portal.url, wp_post_id, post_url,
    )
    return {
        "status": "ok" if wp_data.get("ok", True) else "error",
        "wp_post_id": int(wp_post_id) if wp_post_id is not None else None,
        "video_id": video_id,
        "rankmath_ok": True,
        "youtube_updated": False,
        "created": req.wp_post_id is None,
        "post_url": post_url,
        "yt_channels": [],
        "error": None,
    }


def build_yt_description(
    body: str,
    wp_url: str,
    mid_cta: str,
    chapters: list,
    credits: dict,
    footer_text: str,
    hashtags: list,
    youtube_id: str,
    site_url: str = "",
) -> str:
    """
    Składa pełny opis YouTube z modułów wg Spec v2.2-FINAL.
    Moduły: body → link → mid-CTA → timestamps → credits → footer → hashtagi
    """
    parts = [body.strip()]

    # M2: Link do artykułu
    if wp_url:
        parts.append(f"\n\n🔗 Pełny artykuł: {wp_url}")
    else:
        parts.append("\n\n🔗 Artykuł: [WSTAW LINK]")

    # M3: Mid-CTA
    if mid_cta:
        parts.append(f"\n\n{mid_cta}")

    # M4: Timestamps
    if chapters and len(chapters) >= 3:
        ch_lines = []
        for ch in chapters:
            ts = ch.get("time_str") or ch.get("timestamp") or ch.get("time") or ""
            if isinstance(ts, (int, float)):
                m, s = divmod(int(ts), 60)
                ts = f"{m:02d}:{s:02d}"
            ts = str(ts).strip()

            title_val = str(ch.get("label") or ch.get("title") or ch.get("name") or "").strip()

            if ts and title_val:
                if title_val.startswith(ts):
                    ch_lines.append(title_val)
                else:
                    ch_lines.append(f"{ts} {title_val}")
        if ch_lines:
            parts.append("\n\nROZDZIAŁY:\n" + "\n".join(ch_lines))

    # M5: Credits
    if credits:
        host = credits.get("host", "")
        guest = credits.get("guest", "")
        mat_type = credits.get("material_type", "")
        from datetime import date
        today = date.today().strftime("%d.%m.%Y")
        credit_lines = []
        if host:
            credit_lines.append(f"Prowadzący: {host}")
        if guest:
            credit_lines.append(f"Gość: {guest}")
        if mat_type:
            credit_lines.append(f"Typ materiału: {mat_type} | Stan informacji: {today}")
        if credit_lines:
            parts.append("\n\n" + " | ".join(credit_lines[:2]))
            if len(credit_lines) > 2:
                parts.append("\n" + credit_lines[2])

    # M7: Stopka per-kanał
    if footer_text:
        parts.append(f"\n\n{footer_text.strip()}")

    # M8: Hashtagi
    if hashtags:
        tags = " ".join(t if t.startswith("#") else f"#{t}" for t in hashtags)
        parts.append(f"\n\n---\n{tags}")

    result = "".join(parts)

    # Guard: limit YT 5000 zn
    if len(result) > 4990:
        result = result[:4987] + "..."

    return result


@router.post("/inject", response_model=InjectResponse)
async def inject_endpoint(
    req: InjectRequest,
    current_user: User = Depends(get_current_user),
) -> InjectResponse:
    """Inject a pre-generated SEO schema dict into a WordPress post."""
    logger.info(
        "[/v1/inject] user=%s wp_post_id=%s video_url=%s mode=%s format=%s yt_channels=%d job_id=%s",
        current_user.id,
        req.wp_post_id,
        req.video_url,
        "create" if req.wp_post_id is None else "update",
        req.post_format,
        len(req.yt_channel_ids) if req.yt_channel_ids else 0,
        req.job_id,
    )
    try:
        site_config_dict = {}
        use_plugin_token = False
        target_portal: WpPortal | None = None

        if req.site_config:
            site_config_dict = req.site_config.model_dump()
        elif req.portal_id:
            async with AsyncSessionLocal() as db:
                try:
                    uid = uuid.UUID(req.portal_id)
                    result_p = await db.execute(
                        select(WpPortal).where(
                            WpPortal.id == uid,
                            WpPortal.user_id == current_user.id,
                        )
                    )
                    target_portal = result_p.scalar_one_or_none()
                    if target_portal:
                        portal_auth_mode = getattr(target_portal, "auth_mode", "app_password") or "app_password"
                        if portal_auth_mode == "plugin_token" or not (target_portal.wp_app_password or "").strip():
                            use_plugin_token = True
                        site_config_dict = {
                            "wp_base_url": target_portal.url,
                            "wp_user": target_portal.wp_username or "",
                            "wp_app_password": target_portal.wp_app_password or "",
                        }
                    else:
                        raise HTTPException(
                            status_code=403,
                            detail="Portal not found or access denied",
                        )
                except HTTPException:
                    raise
                except ValueError as e:
                    raise ValueError(f"Invalid portal_id: {e}")
        else:
            raise ValueError("Either site_config or portal_id must be provided")

        if use_plugin_token and target_portal is not None:
            result = await _inject_via_plugin_endpoint(
                portal=target_portal,
                user=current_user,
                req=req,
            )
        else:
            result = await run_inject(
                wp_post_id=req.wp_post_id,
                video_url=req.video_url,
                schema_data=req.schema_data,
                site_config=site_config_dict,
                post_status=req.post_status,
                post_format=req.post_format,
                yt_channel_ids=req.yt_channel_ids,
                portal_id=req.portal_id,
                job_id=req.job_id,
            )

        # YouTube Immediate Publish — Scenariusz A
        if req.yt_channel_ids:
            from api.core.youtube_publish import update_youtube_metadata, _get_channel

            job_result = req.schema_data or {}
            video_id = _extract_video_id(req.video_url)
            wp_article_url = result.get("post_url")

            if req.yt_override_description:
                full_yt_description = req.yt_override_description
            else:
                footer_text = ""
                async with AsyncSessionLocal() as db_ft:
                    ft_channel = await _get_channel(db_ft, current_user.id, req.yt_channel_ids[0])
                    if ft_channel:
                        footer_text = ft_channel.footer_text or ""

                full_yt_description = build_yt_description(
                    body=job_result.get("youtube_description_body") or job_result.get("youtube_description_hook", ""),
                    wp_url=wp_article_url or "",
                    mid_cta=job_result.get("youtube_mid_cta", ""),
                    chapters=job_result.get("resolved_chapters") or job_result.get("chapters", []),
                    credits=job_result.get("youtube_credits", {}),
                    footer_text=footer_text,
                    hashtags=job_result.get("youtube_hashtags", []),
                    youtube_id=video_id,
                    site_url=site_config_dict.get("wp_base_url", ""),
                )

            if video_id:
                try:
                    async with AsyncSessionLocal() as db:
                        yt_results = await update_youtube_metadata(
                            db=db,
                            user_id=current_user.id,
                            channel_ids=req.yt_channel_ids,
                            video_id=video_id,
                            new_description=full_yt_description,
                            new_title=job_result.get("yt_title") or job_result.get("post_title"),
                        )
                except Exception as yt_err:
                    logger.error("[/v1/inject] YouTube update failed: %s", yt_err)
                    yt_results = {"error": str(yt_err)}
            else:
                yt_results = {"error": "video_id not found in job result"}

            result["yt_channels"] = [{"channel_id": k, "status": v} for k, v in yt_results.items()]
            result["youtube_updated"] = True

        return InjectResponse(**result)
    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("[/v1/inject] ValueError: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[/v1/inject] RuntimeError: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[/v1/inject] Unexpected error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
