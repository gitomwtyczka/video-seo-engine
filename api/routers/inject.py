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

from fastapi import APIRouter, HTTPException

from api.models.request import InjectRequest
from api.models.response import InjectResponse
from api.services.pipeline import run_inject

router = APIRouter(prefix="/v1", tags=["inject"])
logger = logging.getLogger(__name__)


@router.post("/inject", response_model=InjectResponse)
async def inject_endpoint(req: InjectRequest) -> InjectResponse:
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
        "[/v1/inject] wp_post_id=%s video_url=%s mode=%s format=%s",
        req.wp_post_id,
        req.video_url,
        "create" if req.wp_post_id is None else "update",
        req.post_format,
    )
    try:
        site_config_dict = {}
        if req.site_config:
            site_config_dict = req.site_config.model_dump()
        elif req.portal_id:
            from api.db import AsyncSessionLocal
            from api.models.portal import WpPortal
            import uuid
            
            async with AsyncSessionLocal() as db:
                try:
                    uid = uuid.UUID(req.portal_id)
                    portal = await db.get(WpPortal, uid)
                    if portal:
                        site_config_dict = {
                            "wp_base_url": portal.url,
                            "wp_user": portal.wp_username,
                            "wp_app_password": portal.wp_app_password
                        }
                    else:
                        raise ValueError(f"Portal not found: {req.portal_id}")
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
        )
        return InjectResponse(**result)
    except ValueError as exc:
        logger.error("[/v1/inject] ValueError: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[/v1/inject] RuntimeError: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[/v1/inject] Unexpected error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
