"""Router: POST /v1/generate — generate SEO schema (no WP write).

CO: Endpoint generowania schema SEO z YouTube URL.

PO CO: Główna wartość produktu — użytkownik wkleja URL, dostaje gotowe
dane SEO. Wynik jest zapisywany do DB (transcript_jobs.schema_data)
aby był dostępny w historii.

JAK: Wywołuje pipeline.run_generate(), zapisuje wynik do job'u w DB,
zwraca GenerateResponse z pełnym schema_data.
"""
import json
import logging
import time

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, desc

from api.db import AsyncSessionLocal
from api.models.job import TranscriptJob
from api.models.request import GenerateRequest
from api.models.response import GenerateResponse
from api.services.pipeline import run_generate

router = APIRouter(prefix="/v1", tags=["generate"])
logger = logging.getLogger(__name__)


async def _save_schema_to_job(video_url: str, schema_data: dict) -> None:
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
                job.status = "done"
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
async def generate_endpoint(req: GenerateRequest) -> GenerateResponse:
    """Fetch YouTube transcript and generate SEO schema via LLM.

    Does NOT write to WordPress. Returns the full schema_data dict
    which can be passed to /v1/inject later.
    Saves schema_data to transcript_jobs for /historia access.
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

        schema_data = result["seo"]

        # Persystuj schema do DB dla historii
        await _save_schema_to_job(req.video_url, schema_data)

        return GenerateResponse(
            status="ok",
            video_id=result["video_id"],
            processing_time_s=round(time.time() - start, 2),
            schema_data=schema_data,
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
