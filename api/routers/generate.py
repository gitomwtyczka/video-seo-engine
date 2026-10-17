"""Router: POST /v1/generate — generate SEO schema (no WP write).

CO: Endpoint generowania schema SEO z YouTube URL.

PO CO: Główna wartość produktu — użytkownik wkleja URL, dostaje gotowe
dane SEO. Wynik jest zapisywany do DB (transcript_jobs.schema_data)
aby był dostępny w historii.

JAK: Wywołuje pipeline.run_generate(), zapisuje wynik do job'u w DB,
zwraca GenerateResponse z pełnym schema_data.

D6b (2026-06-20, vse-dev-21):
  - Passes publication_type from request to pipeline.run_generate()

D9 (2026-06-20, vse-dev-23):
  - Passes portal_id from request to pipeline.run_generate()
  - Portal determines site_url for SAAS enrichment and site_brand for generator

FIX D (2026-07-10, vse-dev-01):
  - RuntimeError messages parsed into user-friendly Polish messages
  - error_code field added: 'NO_TRANSCRIPT', 'VIDEO_UNAVAILABLE', 'UNKNOWN_ERROR'

FIX A (2026-07-10, vse-dev-01):
  - transcript_available and partial_result propagated from pipeline result
"""
import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from api.auth import get_current_user
from api.db import AsyncSessionLocal, get_db
from api.models.user import User
from api.quota import check_quota, log_usage, check_multilang_access
from api.models.job import TranscriptJob
from api.models.request import GenerateRequest, AdaptMaterialRequest
from api.models.response import GenerateResponse
from api.services.pipeline import run_generate
from core.generator import adapt_material_language, current_llm_usage, calculate_cost_usd, SUPPORTED_LANGUAGES

router = APIRouter(prefix="/v1", tags=["generate"])
logger = logging.getLogger(__name__)


def _parse_runtime_error(exc: RuntimeError) -> tuple[str, str]:
    """Parse RuntimeError into user-friendly Polish message and error_code."""
    exc_str = str(exc)

    if "No transcript available" in exc_str:
        return (
            "Brak dostępnych napisów dla tego wideo. "
            "Film zostanie przetworzony na podstawie tytułu i opisu.",
            "NO_TRANSCRIPT",
        )

    if "metadata_fetch_failed" in exc_str or "VideoUnavailable" in exc_str:
        return (
            "Nie można pobrać danych wideo. "
            "Sprawdź czy link jest poprawny i film jest publiczny.",
            "VIDEO_UNAVAILABLE",
        )

    # Fallback: raw error message
    return exc_str, "UNKNOWN_ERROR"


async def _save_schema_to_job(video_url: str, schema_data: dict, portal_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """Zapisuje schema_data do najnowszego job'u dla danego video_url."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TranscriptJob)
                .where(TranscriptJob.video_url.contains(
                    video_url.split("v=")[-1][:11] if "v=" in video_url else video_url[:11]
                ))
                .where(TranscriptJob.status.in_(["fetched", "processing"]))
                .order_by(desc(TranscriptJob.created_at))
                .limit(1)
            )
            job = result.scalar_one_or_none()
            if job:
                job.schema_data = schema_data
                job.portal_id = portal_id
                job.status = "done"
                if user_id and job.user_id is None:
                    job.user_id = user_id
                await db.commit()
                logger.info(
                    "[generate] Saved schema_data to job %s (status=done)",
                    job.id,
                )
            else:
                new_job = TranscriptJob(
                    video_url=video_url,
                    status="done",
                    schema_data=schema_data,
                    portal_id=portal_id,
                    user_id=user_id,
                )
                db.add(new_job)
                await db.commit()
                await db.refresh(new_job)
                logger.info(
                    "[generate] Created new job %s with schema_data (no matching pending job)",
                    new_job.id,
                )
    except Exception as exc:
        logger.error("[generate] Failed to save schema_data to DB: %s", exc)


@router.post("/generate", response_model=GenerateResponse)
async def generate_endpoint(
    req: GenerateRequest,
    current_user: User = Depends(check_quota),
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Fetch YouTube transcript and generate SEO schema via LLM."""
    plan_id = getattr(current_user, "plan_id", "free") or "free"
    effective_provider = req.llm_provider
    if plan_id in ("free", "starter"):
        effective_provider = "gemini"
    elif not effective_provider:
        effective_provider = "gemini"

    ui_lang = (req.ui_lang or "pl").lower()[:2]
    target_lang = (req.target_lang or req.lang or ui_lang or "pl").lower()[:2]
    if target_lang not in SUPPORTED_LANGUAGES:
        target_lang = "pl"

    entitlements = await check_multilang_access(current_user.id, db, user=current_user)
    if target_lang != ui_lang and not entitlements.get("allow_target_override", False):
        raise HTTPException(
            status_code=403,
            detail="Wybór innego języka docelowego niż język panelu wymaga Pakietu Wielojęzycznego (+29 zł/mies.) lub planu Pro / Agency.",
        )

    logger.info(
        "[/v1/generate] video_url=%s requested_provider=%s effective_provider=%s plan=%s type=%s portal_id=%s target_lang=%s ui_lang=%s",
        req.video_url, req.llm_provider, effective_provider, plan_id, req.publication_type, req.portal_id, target_lang, ui_lang,
    )
    start = time.time()
    try:
        result = await run_generate(
            video_url=req.video_url,
            llm_provider=effective_provider,
            lang=target_lang,
            post_title_override=req.post_title,
            publication_type=req.publication_type,  # D6b
            portal_id=req.portal_id,  # D9
            user_id=str(current_user.id),  # OAuth: private video access
            target_lang=target_lang,
        )

        schema_data = result["seo"]

        # Persystuj schema do DB dla historii
        await _save_schema_to_job(req.video_url, schema_data, req.portal_id, current_user.id)

        # Loguj udane wykonanie do miesięcznego limitu
        video_id = result.get("video_id") or ""
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id=video_id,
            success=True,
            endpoint="/v1/generate",
            llm_provider=result.get("llm_provider") or effective_provider,
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            estimated_cost_usd=result.get("estimated_cost_usd", 0.0),
        )

        # FIX A: propagate transcript availability flags from pipeline
        has_transcript = result.get("has_transcript", True)
        is_partial = result.get("partial_result", False)

        return GenerateResponse(
            status="ok",
            video_id=result["video_id"],
            processing_time_s=round(time.time() - start, 2),
            schema_data=schema_data,
            transcript_available=has_transcript,
            partial_result=is_partial if is_partial else None,
            source_lang=result.get("source_lang", schema_data.get("source_lang", "pl")),
            target_lang=result.get("target_lang", schema_data.get("target_lang", target_lang)),
        )
    except ValueError as exc:
        logger.error("[/v1/generate] ValueError: %s", exc)
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id="",
            success=False,
            error_msg=str(exc),
            endpoint="/v1/generate",
            llm_provider=effective_provider,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[/v1/generate] RuntimeError: %s", exc)
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id="",
            success=False,
            error_msg=str(exc),
            endpoint="/v1/generate",
            llm_provider=effective_provider,
        )
        # FIX D: Parse error into user-friendly Polish message + error_code
        error_message, error_code = _parse_runtime_error(exc)
        return GenerateResponse(
            status="error",
            video_id="unknown",
            processing_time_s=round(time.time() - start, 2),
            error=error_message,
            error_code=error_code,
        )
    except Exception as exc:
        logger.exception("[/v1/generate] Unexpected error")
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id="",
            success=False,
            error_msg=str(exc),
            endpoint="/v1/generate",
            llm_provider=effective_provider,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/adapt-material")
async def adapt_material_endpoint(
    req: AdaptMaterialRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """On-demand per-material language adaptation (Article, YouTube, Meta, Quotes, Schema).

    Does NOT consume monthly video quota (logged with endpoint='adapt_material').
    Requires allow_per_material_adapt == True (Pro, Agency, or +29 PLN/mo Add-on).
    """
    entitlements = await check_multilang_access(current_user.id, db, user=current_user)
    if not entitlements.get("allow_per_material_adapt", False):
        raise HTTPException(
            status_code=403,
            detail="Tłumaczenie poszczególnych materiałów na inne języki wymaga Pakietu Wielojęzycznego (+29 zł/mies.) lub planu Pro / Agency.",
        )

    target_lang = (req.target_lang or "pl").lower()[:2]
    if target_lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"Nieobsługiwany język docelowy: {target_lang}")

    plan_id = (getattr(current_user, "plan_id", "free") or "free").lower()
    effective_provider = req.llm_provider or "gemini"
    if plan_id in ("free", "starter"):
        effective_provider = "gemini"

    start = time.time()

    def _run_sync_adapt() -> tuple[dict, dict]:
        token = current_llm_usage.set({
            "input_tokens": 0,
            "output_tokens": 0,
            "last_provider": effective_provider,
        })
        try:
            adapted = adapt_material_language(
                material_type=req.material_type,
                target_lang=target_lang,
                source_data=req.source_data,
                llm_provider=effective_provider,
            )
            usage = current_llm_usage.get() or {}
            return adapted, usage
        finally:
            current_llm_usage.reset(token)

    try:
        adapted_data, usage = await asyncio.to_thread(_run_sync_adapt)
        in_tok = int(usage.get("input_tokens", 0))
        out_tok = int(usage.get("output_tokens", 0))
        used_prov = usage.get("last_provider", effective_provider)
        cost_usd = calculate_cost_usd(used_prov, in_tok, out_tok)

        yt_id = req.youtube_id or req.source_data.get("youtube_id") or ""
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id=yt_id,
            success=True,
            endpoint="adapt_material",
            llm_provider=used_prov,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_cost_usd=cost_usd,
        )

        return {
            "status": "ok",
            "material_type": req.material_type,
            "target_lang": target_lang,
            "adapted_data": adapted_data,
            "processing_time_s": round(time.time() - start, 2),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[/v1/adapt-material] Error adapting material")
        await log_usage(
            user_id=current_user.id,
            db=db,
            youtube_id=req.youtube_id or "",
            success=False,
            error_msg=str(exc),
            endpoint="adapt_material",
            llm_provider=effective_provider,
        )
        raise HTTPException(status_code=500, detail=f"Błąd adaptacji językowej: {exc}") from exc

