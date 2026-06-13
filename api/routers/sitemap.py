"""Router: POST /v1/sitemap — generate video sitemap XML."""
import asyncio
import logging

from fastapi import APIRouter, HTTPException

from api.models.request import SitemapRequest
from api.models.response import SitemapResponse

router = APIRouter(prefix="/v1", tags=["sitemap"])
logger = logging.getLogger(__name__)


@router.post("/sitemap", response_model=SitemapResponse)
async def sitemap_endpoint(req: SitemapRequest) -> SitemapResponse:
    """Generate a video sitemap XML for the configured WordPress site.

    Fetches all posts with embedded YouTube videos and produces
    a sitemap compliant with Google Video Sitemap spec.
    """
    logger.info("[/v1/sitemap] site=%s", req.site_config.wp_base_url)
    try:
        from core.sitemap import generate_sitemap  # type: ignore

        output_path = req.output_path
        result = await asyncio.to_thread(
            generate_sitemap,
            req.site_config.wp_base_url,
            req.site_config.wp_user,
            req.site_config.wp_app_password,
            output_path,
        )
        count = result.get("videos_count", 0) if isinstance(result, dict) else 0
        out = result.get("output_path") if isinstance(result, dict) else output_path
        return SitemapResponse(
            status="ok",
            videos_count=count,
            output_path=out,
        )
    except Exception as exc:
        logger.exception("[/v1/sitemap] Error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
