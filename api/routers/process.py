"""Router: POST /v1/process — full pipeline (fetch + generate + inject)."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models.user import User
from api.quota import check_quota, log_usage, check_multilang_access
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
    """Run full VSE pipeline: fetch transcript, generate schema, inject to WordPress."""
    plan_id = getattr(current_user, "plan_id", "free") or "free"
    effective_provider = req.options.llm_provider
    if plan_id in ("free", "starter"):
        effective_provider = "gemini"
        req.options.llm_provider = "gemini"
    elif not effective_provider:
        effective_provider = "gemini"
        req.options.llm_provider = "gemini"

    ui_lang = (req.ui_lang or req.options.ui_lang or "pl").lower()[:2]
    target_lang = (req.target_lang or req.options.target_lang or req.options.lang or ui_lang or "pl").lower()[:2]
    req.options.target_lang = target_lang
    req.options.lang = target_lang

    entitlements = await check_multilang_access(current_user.id, db, user=current_user)
    if target_lang != ui_lang and not entitlements.get("allow_target_override", False):
        raise HTTPException(
            status_code=403,
            detail="Wybór innego języka docelowego niż język panelu wymaga Pakietu Wielojęzycznego (+29 zł/mies.) lub planu Pro / Agency.",
        )

    logger.info(
        "[/v1/process] video_url=%s provider=%s effective_provider=%s plan=%s auto_inject=%s target_lang=%s",
        req.video_url, req.options.llm_provider, effective_provider, plan_id, req.options.auto_inject, target_lang,
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
