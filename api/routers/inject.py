"""Router: POST /v1/inject — inject pre-generated schema into WordPress.

CO: FastAPI router obsługujący endpoint POST /v1/inject.

PO CO: Umożliwia dashboardowi (plan pro/agency) opublikowanie wygenerowanych
danych SEO bezpośrednio na WordPress. Klient może podać wp_post_id (aktualizacja)
lub pominąć go (tworzenie nowego posta). To eliminuje konieczność ręcznego szukania
ID artykułu przed publikacją.

JAK:
- wp_post_id obecny → pipeline.run_inject() → inject_video() na istniejącym poście
- wp_post_id = None  → pipeline.run_inject() → _create_wp_post() (POST /wp/v2/posts)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from api.models.user import User
from api.models.request import InjectRequest
from api.models.response import InjectResponse
from api.services.pipeline import run_inject

router = APIRouter(prefix="/v1", tags=["inject"])
logger = logging.getLogger(__name__)


@router.post("/inject", response_model=InjectResponse)
async def inject_endpoint(
    req: InjectRequest,
    current_user: User = Depends(get_current_user),
) -> InjectResponse:
    """Inject a pre-generated SEO schema dict into a WordPress post.

    Behaviour depends on wp_post_id:
    - **Provided**: Updates the existing post (PATCH /wp/v2/posts/{id}).
    - **Omitted / null**: Creates a new WordPress post, then injects SEO schema.
      New post status is controlled by `post_status` field ('draft' by default).
      Post format is controlled by `post_format` field ('video' by default).

    Use this when you already have schema_data from /v1/generate
    and want to push it to WP without re-running the full pipeline.
    """
    logger.info(
        "[/v1/inject] user=%s wp_post_id=%s video_url=%s mode=%s format=%s yt_channels=%d",
        current_user.id,
        req.wp_post_id,
        req.video_url,
        "create" if req.wp_post_id is None else "update",
        req.post_format,
        len(req.yt_channel_ids) if req.yt_channel_ids else 0,
    )
    try:
        site_config_dict = {}
        if req.site_config:
            site_config_dict = req.site_config.model_dump()
        elif req.portal_id:
            from api.db import AsyncSessionLocal
            from api.models.portal import WpPortal
            from sqlalchemy.future import select
            import uuid

            async with AsyncSessionLocal() as db:
                try:
                    uid = uuid.UUID(req.portal_id)
                    result = await db.execute(
                        select(WpPortal).where(
                            WpPortal.id == uid,
                            WpPortal.user_id == current_user.id,
                        )
                    )
                    portal = result.scalar_one_or_none()
                    if portal:
                        site_config_dict = {
                            "wp_base_url": portal.url,
                            "wp_user": portal.wp_username,
                            "wp_app_password": portal.wp_app_password
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

        result = await run_inject(
            wp_post_id=req.wp_post_id,
            video_url=req.video_url,
            schema_data=req.schema_data,
            site_config=site_config_dict,
            post_status=req.post_status,
            post_format=req.post_format,
            yt_channel_ids=req.yt_channel_ids,
        )

        # YouTube Immediate Publish — Scenariusz A
        # ROADMAP F2B: integracja youtube_publish.py — commit [ten commit]
        if req.yt_channel_ids:
            from api.core.youtube_publish import update_youtube_description
            from api.db import AsyncSessionLocal
            
            job_result = req.schema_data or {}
            hook = job_result.get("youtube_description_hook") or job_result.get("youtube_description", "")
            hashtags_list = job_result.get("youtube_hashtags", [])
            hashtags_str = " ".join(hashtags_list) if isinstance(hashtags_list, list) else ""
            
            chapters = job_result.get("resolved_chapters") or job_result.get("chapters", [])
            chapters_text = ""
            if isinstance(chapters, list) and chapters:
                lines = []
                for ch in chapters:
                    time_str = ch.get("time_str", "00:00")
                    label = ch.get("label", "")
                    if label:
                        lines.append(f"{time_str} - {label}")
                chapters_text = "\n".join(lines)
            
            wp_article_url = result.get("post_url")
            full_yt_description = hook
            if wp_article_url:
                full_yt_description += f"\n\n🔗 Pełny artykuł: {wp_article_url}"
            if chapters_text:
                full_yt_description += f"\n\n⏱️ Rozdziały:\n{chapters_text}"
            if hashtags_str:
                full_yt_description += f"\n\n---\n{hashtags_str}"
            
            video_id = job_result.get("video_id") or job_result.get("youtube_id", "")
            if video_id:
                try:
                    async with AsyncSessionLocal() as db:
                        yt_results = await update_youtube_description(
                            db=db,
                            user_id=current_user.id,
                            channel_ids=req.yt_channel_ids,
                            video_id=video_id,
                            new_description=full_yt_description,
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
