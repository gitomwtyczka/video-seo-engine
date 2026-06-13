"""Router: POST /v1/inject — inject pre-generated schema into WordPress."""
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

    Use this when you already have schema_data from /v1/generate
    and want to push it to WP without re-running the full pipeline.
    """
    logger.info(
        "[/v1/inject] wp_post_id=%s video_url=%s",
        req.wp_post_id, req.video_url,
    )
    try:
        result = await run_inject(
            wp_post_id=req.wp_post_id,
            video_url=req.video_url,
            schema_data=req.schema_data,
            site_config=req.site_config.model_dump(),
        )
        return InjectResponse(**result)
    except ValueError as exc:
        logger.error("[/v1/inject] ValueError: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[/v1/inject] Unexpected error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
