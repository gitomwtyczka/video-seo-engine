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
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from api.auth import get_current_user
from api.models.user import User
from sqlalchemy import select, desc

from api.db import AsyncSessionLocal
from api.models.job import TranscriptJob
from api.models.request import GenerateRequest
from api.models.response import GenerateResponse
from api.services.pipeline import run_generate

router = APIRouter(prefix="/v1", tags=["generate"])
logger = logging.getLogger(__name__)


def _parse_runtime_error(exc: RuntimeError) -> tuple[str, str]:
    """Parse RuntimeError into user-friendly Polish message and error_code.

    CO: Przekształca techniczne wyjątki RuntimeError na czytelne komunikaty po polsku.

    PO CO: Surowe komunikaty RuntimeError (np. 'No transcript available for xyz...')
    trafiały prosto do frontendu, dezorientując użytkownika. Frontend potrzebuje
    human-friendly message + machine-readable code do warunkowego renderowania UI.

    JAK: Sprawdza kluczowe frazy w treści wyjątku i zwraca odpowiedni
    komunikat PL + kod błędu. Fallback = oryginalny str(exc).

    Args:
        exc: RuntimeError z pipeline.run_generate().

    Returns:
        Tuple (error_message: str, error_code: str).
    """
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
    """Zapisuje schema_data do najnowszego job'u dla danego video_url.

    CO: Persystencja wyniku generowania w DB.

    PO CO: Bez tego schema jest utracona po zakończeniu HTTP response.
    Strona /historia potrzebuje dostępu do wygenerowanego contentu
    aby użytkownik mógł wrócić do wyników bez ponownego generowania.

    JAK: Szuka najnowszego job'u z status='fetched' dla danego video_url,
    aktualizuje schema_data i status na 'done'.
    """
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
                # Brak pasującego job'u — utwórz nowy ze statusem 'done'
                from datetime import datetime, timezone
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
        # Nie rzucamy wyjątku — zapis do DB jest best-effort,
        # użytkownik i tak dostał wynik w HTTP response


@router.post("/generate", response_model=GenerateResponse)
async def generate_endpoint(req: GenerateRequest, current_user: User = Depends(get_current_user)) -> GenerateResponse:
    """Fetch YouTube transcript and generate SEO schema via LLM.

    Does NOT write to WordPress. Returns the full schema_data dict
    which can be passed to /v1/inject later.
    Saves schema_data to transcript_jobs for /historia access.

    D6b: Accepts publication_type to control article format.
    D9: Accepts portal_id to select server-side YAML profile.
    FIX D: RuntimeError messages parsed to user-friendly Polish messages + error_code.
    FIX A: transcript_available and partial_result propagated from pipeline.
    """
    logger.info(
        "[/v1/generate] video_url=%s provider=%s type=%s portal_id=%s",
        req.video_url, req.llm_provider, req.publication_type, req.portal_id,
    )
    start = time.time()
    try:
        result = await run_generate(
            video_url=req.video_url,
            llm_provider=req.llm_provider,
            lang=req.lang,
            post_title_override=req.post_title,
            publication_type=req.publication_type,  # D6b
            portal_id=req.portal_id,  # D9
            user_id=str(current_user.id),  # OAuth: private video access
        )

        schema_data = result["seo"]

        # Persystuj schema do DB dla historii
        await _save_schema_to_job(req.video_url, schema_data, req.portal_id, current_user.id)

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
        )
    except ValueError as exc:
        logger.error("[/v1/generate] ValueError: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[/v1/generate] RuntimeError: %s", exc)
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
        raise HTTPException(status_code=500, detail=str(exc)) from exc
