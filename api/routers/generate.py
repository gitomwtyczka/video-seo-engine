"""Router: POST /v1/generate — generate SEO schema (no WP write)."""
import logging
import time

from fastapi import APIRouter, HTTPException

from api.models.request import GenerateRequest
from api.models.response import GenerateResponse
from api.services.pipeline import run_generate

router = APIRouter(prefix="/v1", tags=["generate"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GenerateResponse)
async def generate_endpoint(req: GenerateRequest) -> GenerateResponse:
    """Fetch YouTube transcript and generate SEO schema via LLM.

    Does NOT write to WordPress. Returns the full schema_data dict
    which can be passed to /v1/inject later.
    """
    logger.info(
        "[/v1/generate] video_url=%s provider=%s",
        req.video_url, req.llm_provider,
    )
    start = time.time()
    try:
        result = await run_generate(
            video_url=req.video_url,
            llm_provider=req.llm_provider,
            lang=req.lang,
            post_title_override=req.post_title,
        )
        return GenerateResponse(
            status="ok",
            video_id=result["video_id"],
            processing_time_s=round(time.time() - start, 2),
            schema_data=result["seo"],
        )
    except ValueError as exc:
        logger.error("[/v1/generate] ValueError: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[/v1/generate] RuntimeError: %s", exc)
        return GenerateResponse(
            status="error",
            video_id="unknown",
            processing_time_s=round(time.time() - start, 2),
            error=str(exc),
        )
    except Exception as exc:
        logger.exception("[/v1/generate] Unexpected error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
