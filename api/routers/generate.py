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

KROK B (2026-10-20, vse-dev-01):
  - Hard Anti-Confabulation Guard: gdy run_generate() rzuci ValueError (brak transkryptu),
    zwraca czytelny błąd HTTP 422 (lub event 'error' w /v1/generate/stream) BEZ naliczania
    zużycia kredytu (success=False / brak UsageLog(..., success=True)).

K4 (2026-10-21, vse-dev-k4):
  - Job per click: _save_schema_to_job aktualizuje rekord po PK (job_id),
    tworzony na starcie run_generate().
  - Zakres user_id (R1/R2): nigdy nie nadpisuj ani nie modyfikuj joba innego usera.
  - Zapis publication_type do wiersza joba.
"""
import asyncio
from datetime import datetime, timezone
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from api.auth import get_current_user
from api.db import AsyncSessionLocal, get_db
from api.models.user import User
from api.quota import check_quota, log_usage, check_multilang_access
from api.models.job import TranscriptJob
from api.models.request import GenerateRequest, AdaptMaterialRequest
from api.models.response import GenerateResponse
from api.services.pipeline import run_generate, _extract_video_id
from core.generator import adapt_material_language, current_llm_usage, calculate_cost_usd, SUPPORTED_LANGUAGES

router = APIRouter(prefix="/v1", tags=["generate"])
logger = logging.getLogger(__name__)


def _parse_runtime_error(exc: RuntimeError) -> tuple[str, str]:
    """Parse RuntimeError into user-friendly Polish message and error_code."""
    exc_str = str(exc)

    if "No transcript available" in exc_str or "Brak transkryptu" in exc_str:
        return (
            "Brak transkryptu wideo: nie udało się pobrać napisów z YouTube "
            "(sprawdź czy działa VSE Local Runner na komputerze lub czy film posiada napisy na YouTube). "
            "Generowanie zostało zatrzymane, aby zapobiec konfabulacji AI (0 pobranych kredytów).",
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


async def _save_schema_to_job(
    job_id: Optional[str | uuid.UUID] = None,
    schema_data: Optional[dict] = None,
    portal_id: Optional[str] = None,
    user_id: Optional[str | uuid.UUID] = None,
    publication_type: Optional[str] = None,
    video_url: Optional[str] = None,
) -> Optional[str]:
    """Zapisuje schema_data do job'u po PK (job_id) z kontrolą uprawnień user_id (R1/R2)."""
    try:
        uid = None
        if user_id:
            try:
                uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
            except (ValueError, TypeError):
                pass

        async with AsyncSessionLocal() as db:
            job = None
            if job_id:
                try:
                    job_uuid = uuid.UUID(str(job_id)) if not isinstance(job_id, uuid.UUID) else job_id
                    job = await db.get(TranscriptJob, job_uuid)
                except (ValueError, TypeError):
                    job = None

            if not job and video_url:
                # Fallback: create a new job if job_id was not found
                job = TranscriptJob(
                    video_url=video_url,
                    status="done",
                    schema_data=schema_data,
                    portal_id=portal_id,
                    publication_type=publication_type or "full_analysis",
                    user_id=uid,
                )
                db.add(job)
                await db.commit()
                await db.refresh(job)
                logger.info("[generate] Created new job %s with schema_data (no job_id found)", job.id)
                return str(job.id)

            if job:
                # R1/R2 Security: never overwrite or update another user's job
                if uid is not None and job.user_id is not None and job.user_id != uid:
                    logger.warning(
                        "[generate] R1/R2 violation attempt: user %s tried to update job %s owned by %s",
                        uid, job.id, job.user_id,
                    )
                    return None

                job.schema_data = schema_data
                if portal_id:
                    job.portal_id = portal_id
                if publication_type:
                    job.publication_type = publication_type
                job.status = "done"
                job.updated_at = datetime.now(timezone.utc)
                if uid is not None and job.user_id is None:
                    job.user_id = uid

                await db.commit()
                logger.info(
                    "[generate] Saved schema_data to job %s by PK (status=done, type=%s, user_id=%s)",
                    job.id, job.publication_type, job.user_id,
                )
                return str(job.id)
    except Exception as exc:
        logger.error("[generate] Failed to save schema_data to DB: %s", exc)
    return None


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
        job_id = result.get("job_id")

        # Persystuj schema do DB dla historii (aktualizacja po PK z kontrolą user_id)
        await _save_schema_to_job(
            job_id=job_id,
            schema_data=schema_data,
            portal_id=req.portal_id,
            user_id=current_user.id,
            publication_type=req.publication_type,
            video_url=req.video_url,
        )

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

        has_transcript = result.get("has_transcript", True)
        is_partial = result.get("partial_result", False)

        return GenerateResponse(
            status="ok",
            video_id=result["video_id"],
            job_id=str(job_id) if job_id else None,
            processing_time_s=round(time.time() - start, 2),
            schema_data=schema_data,
            transcript_available=has_transcript,
            partial_result=is_partial if is_partial else None,
            source_lang=result.get("source_lang", schema_data.get("source_lang", "pl")),
            target_lang=result.get("target_lang", schema_data.get("target_lang", target_lang)),
        )
    except ValueError as exc:
        logger.error("[/v1/generate] ValueError (0 credits charged): %s", exc)
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


@router.post("/generate/stream")
async def generate_stream_endpoint(
    req: GenerateRequest,
    current_user: User = Depends(check_quota),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream endpoint for /v1/generate with hard anti-confabulation guard (0 credits on missing transcript)."""
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

    async def _event_stream():
        start = time.time()
        yield f"data: {json.dumps({'event': 'stage', 'stage': 'fetching_transcript'}, ensure_ascii=False)}\n\n"
        try:
            result = await run_generate(
                video_url=req.video_url,
                llm_provider=effective_provider,
                lang=target_lang,
                post_title_override=req.post_title,
                publication_type=req.publication_type,
                portal_id=req.portal_id,
                user_id=str(current_user.id),
                target_lang=target_lang,
            )
            schema_data = result["seo"]
            job_id = result.get("job_id")
            await _save_schema_to_job(
                job_id=job_id,
                schema_data=schema_data,
                portal_id=req.portal_id,
                user_id=current_user.id,
                publication_type=req.publication_type,
                video_url=req.video_url,
            )

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
            payload = {
                "event": "done",
                "status": "ok",
                "job_id": str(job_id) if job_id else None,
                "video_id": result["video_id"],
                "processing_time_s": round(time.time() - start, 2),
                "schema_data": schema_data,
                "transcript_available": True,
                "partial_result": None,
                "source_lang": result.get("source_lang", schema_data.get("source_lang", "pl")),
                "target_lang": result.get("target_lang", schema_data.get("target_lang", target_lang)),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except ValueError as exc:
            logger.error("[/v1/generate/stream] ValueError (0 credits charged): %s", exc)
            err_payload = {
                "event": "error",
                "status": "error",
                "error_code": "NO_TRANSCRIPT",
                "detail": str(exc),
                "error": str(exc),
            }
            yield f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("[/v1/generate/stream] Error")
            err_payload = {
                "event": "error",
                "status": "error",
                "error_code": "UNKNOWN_ERROR",
                "detail": str(exc),
                "error": str(exc),
            }
            yield f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


async def _save_translation_to_job(
    db: AsyncSession,
    user_id,
    job_id: Optional[str],
    youtube_id: str,
    target_lang: str,
    material_type: str,
    adapted_data: dict,
) -> None:
    """Persist adapted translation inside TranscriptJob.schema_data['translations'][target_lang]."""
    try:
        from sqlalchemy.orm.attributes import flag_modified

        job = None
        if job_id:
            try:
                job_uuid = uuid.UUID(str(job_id))
                res = await db.execute(select(TranscriptJob).where(TranscriptJob.id == job_uuid))
                job = res.scalar_one_or_none()
            except ValueError:
                job = None

        if not job and youtube_id:
            clean_yt = youtube_id.split("v=")[-1][:11] if "v=" in youtube_id else youtube_id[:20]
            stmt = (
                select(TranscriptJob)
                .where(TranscriptJob.video_url.contains(clean_yt))
                .where(TranscriptJob.schema_data.isnot(None))
            )
            if user_id:
                stmt = stmt.where(TranscriptJob.user_id == user_id)
            stmt = stmt.order_by(desc(TranscriptJob.created_at)).limit(1)
            res = await db.execute(stmt)
            job = res.scalar_one_or_none()

            if not job:
                # Fallback without user_id filter if job was created with user_id=None
                stmt2 = (
                    select(TranscriptJob)
                    .where(TranscriptJob.video_url.contains(clean_yt))
                    .where(TranscriptJob.schema_data.isnot(None))
                    .order_by(desc(TranscriptJob.created_at))
                    .limit(1)
                )
                res2 = await db.execute(stmt2)
                job = res2.scalar_one_or_none()

        if not job or not isinstance(job.schema_data, dict):
            return

        new_schema = dict(job.schema_data)
        translations = dict(new_schema.get("translations") or {})
        lang_dict = dict(translations.get(target_lang) or {})

        m_type = (material_type or "article").lower().strip()
        if m_type == "all":
            for tab_key in ("article", "youtube", "chapters", "schema", "all"):
                existing_tab = dict(lang_dict.get(tab_key) or {})
                existing_tab.update(adapted_data)
                lang_dict[tab_key] = existing_tab
        else:
            existing_tab = dict(lang_dict.get(m_type) or {})
            existing_tab.update(adapted_data)
            lang_dict[m_type] = existing_tab
            if m_type == "youtube":
                existing_ch = dict(lang_dict.get("chapters") or {})
                existing_ch.update(adapted_data)
                lang_dict["chapters"] = existing_ch

        translations[target_lang] = lang_dict
        new_schema["translations"] = translations
        job.schema_data = new_schema
        flag_modified(job, "schema_data")
        await db.commit()
        logger.info(
            "[/v1/adapt-material] Persisted translation lang=%s type=%s to job %s",
            target_lang, m_type, job.id,
        )
    except Exception as exc:
        logger.warning("[/v1/adapt-material] Could not persist translation to job: %s", exc)


@router.post("/adapt-material")
async def adapt_material_endpoint(
    req: AdaptMaterialRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """On-demand per-material language adaptation (Article, YouTube, Meta, Quotes, Schema, All).

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
        await _save_translation_to_job(
            db=db,
            user_id=current_user.id,
            job_id=req.job_id,
            youtube_id=yt_id,
            target_lang=target_lang,
            material_type=req.material_type,
            adapted_data=adapted_data,
        )
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
