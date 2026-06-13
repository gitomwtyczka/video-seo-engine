"""Router: POST /v1/process — full pipeline (fetch + generate + inject)."""
import logging

from fastapi import APIRouter, HTTPException

from api.models.request import ProcessRequest
from api.models.response import ProcessResponse
from api.services.pipeline import run_process

router = APIRouter(prefix="/v1", tags=["process"])
logger = logging.getLogger(__name__)


@router.post("/process", response_model=ProcessResponse)
async def process_endpoint(req: ProcessRequest) -> ProcessResponse:
    """Run full VSE pipeline: fetch transcript, generate schema, inject to WordPress.

    - Accepts per-request WordPress credentials (multi-tenant, stateless).
    - Requires ANTHROPIC_API_KEY or GEMINI_API_KEY env var based on llm_provider.
    - If wp_post_id is omitted, schema is generated but injection is skipped.
    """
    logger.info(
        "[/v1/process] video_url=%s provider=%s auto_inject=%s",
        req.video_url, req.options.llm_provider, req.options.auto_inject,
    )
    try:
        result = await run_process(
            video_url=req.video_url,
            site_config=req.site_config.model_dump(),
            options=req.options.model_dump(),
            wp_post_id=req.wp_post_id,
        )
        return ProcessResponse(**result)
    except ValueError as exc:
        logger.error("[/v1/process] ValueError: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[/v1/process] RuntimeError: %s", exc)
        return ProcessResponse(
            status="error",
            video_id="unknown",
            error=str(exc),
        )
    except Exception as exc:
        logger.exception("[/v1/process] Unexpected error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
