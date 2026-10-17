"""Router: POST /v1/process — full pipeline (fetch + generate + inject)."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models.user import User
from api.quota import check_quota, log_usage
from api.models.request import ProcessRequest
from api.models.response import ProcessResponse
from api.services.pipeline import run_process

router = APIRouter(prefix="/v1", tags=["process"])
logger = logging.getLogger(__name__)


@router.post("/process", response_model=ProcessResponse)
async def process_endpoint(
    req: ProcessRequest,
    current_user: User = Depends(check_quota),
    db: AsyncSession = Depends(get_db),
) -> ProcessResponse:
    """Run full VSE pipeline: fetch transcript, generate schema, inject to WordPress.

    - Accepts per-request WordPress credentials (multi-tenant, stateless).
    - Requires ANTHROPIC_API_KEY or GEMINI_API_KEY env var based on llm_provider.
    - If wp_post_id is omitted, schema is generated but injection is skipped.
    - Protected by check_quota & model tiering (Free/Starter = gemini).
    """
    plan_id = getattr(current_user, "plan_id", "free") or "free"
    effective_provider = req.options.llm_provider
    if plan_id in ("free", "starter"):
        effective_provider = "gemini"
        req.options.llm_provider = "gemini"
    elif not effective_provider:
        effective_provider = "gemini"
        req.options.llm_provider = "gemini"

    logger.info(
        "[/v1/process] video_url=%s provider=%s effective_provider=%s plan=%s auto_inject=%s",
        req.video_url, req.options.llm_provider, effective_provider, plan_id, req.options.auto_inject,
    )
    try:
        result = await run_process(
            video_url=req.video_url,
            site_config=req.site_config.model_dump(),
            options=req.options.model_dump(),
            wp_post_id=req.wp_post_id,
            user_id=str(current_user.id),
        )

        video_id = result.get("video_id") or ""
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id=video_id,
            success=True,
            endpoint="/v1/process",
            llm_provider=result.get("llm_provider") or effective_provider,
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            estimated_cost_usd=result.get("estimated_cost_usd", 0.0),
        )

        return ProcessResponse(**result)
    except ValueError as exc:
        logger.error("[/v1/process] ValueError: %s", exc)
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id="",
            success=False,
            error_msg=str(exc),
            endpoint="/v1/process",
            llm_provider=effective_provider,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[/v1/process] RuntimeError: %s", exc)
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id="",
            success=False,
            error_msg=str(exc),
            endpoint="/v1/process",
            llm_provider=effective_provider,
        )
        return ProcessResponse(
            status="error",
            video_id="unknown",
            error=str(exc),
        )
    except Exception as exc:
        logger.exception("[/v1/process] Unexpected error")
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id="",
            success=False,
            error_msg=str(exc),
            endpoint="/v1/process",
            llm_provider=effective_provider,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
