"""
Router: POST /v1/audio/generate & POST /v1/generate-audio — generate SEO schema from audio files (MP3/WAV/M4A).

CO: Endpoint generowania schema SEO z pliku audio (MP3/WAV/M4A/OGG/FLAC).
PO CO: Niezależność od YouTube — twórcy podcastów i audycji mogą wrzucać pliki audio
      i uzyskiwać pełny pakiet SEO, artykuł oraz propozycje ShortMachine.
JAK:
  1. Odbiera plik audio przez multipart/form-data
  2. Transkrybuje przez faster-whisper na VPS (transcribe_audio)
  3. Zapisuje VTT i tworzy job w transcript_jobs
  4. Uruchamia pipeline SEO (run_generate) z sentinelem audio://{media_id}
  5. Zwraca GenerateResponse z schema_data
"""
import asyncio
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db, AsyncSessionLocal
from api.models.job import TranscriptJob
from api.models.response import GenerateResponse
from api.models.user import User
from api.services.pipeline import run_generate
from api.services.whisper_service import transcribe_audio

router = APIRouter(tags=["audio"])
logger = logging.getLogger(__name__)

ALLOWED_AUDIO_EXTENSIONS = (
    ".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".wma", ".mp4"
)


def _parse_runtime_error(exc: RuntimeError) -> tuple[str, str]:
    """Parse RuntimeError into user-friendly Polish message and error_code."""
    exc_str = str(exc)
    if "No transcript available" in exc_str:
        return (
            "Brak transkrypcji dla tego pliku audio.",
            "NO_TRANSCRIPT",
        )
    return exc_str, "UNKNOWN_ERROR"


@router.post("/audio/generate", response_model=GenerateResponse)
@router.post("/generate-audio", response_model=GenerateResponse)
async def generate_audio_endpoint(
    file: UploadFile = File(...),
    publication_type: str = Form("full_analysis"),
    portal_id: Optional[str] = Form(None),
    post_title: Optional[str] = Form(None),
    lang: str = Form("pl"),
    llm_provider: str = Form("claude"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Odbiera plik audio, transkrybuje za pomocą faster-whisper i generuje pakiet SEO.

    Zwraca GenerateResponse identyczny jak /v1/generate.
    """
    start_time = time.time()
    original_filename = file.filename or "audio.mp3"
    ext = os.path.splitext(original_filename)[1].lower()

    if ext and ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Niedozwolony format pliku audio: {ext}. Dozwolone formaty: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}",
        )

    # 1. Synthetic media ID
    media_id = f"audio_{uuid.uuid4().hex[:8]}"
    safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", original_filename)
    tmp_audio_path = f"/tmp/{media_id}_{safe_filename}"
    tmp_vtt_path = f"/tmp/{media_id}.vtt"
    tmp_srt_path = f"/tmp/{media_id}.srt"

    logger.info(
        "[/v1/audio/generate] start: media_id=%s, file=%s, type=%s, portal_id=%s, user_id=%s",
        media_id,
        original_filename,
        publication_type,
        portal_id,
        current_user.id,
    )

    try:
        # 2. Zapisz plik na dysku
        with open(tmp_audio_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        logger.error("[audio] Failed to save uploaded audio file: %s", exc)
        raise HTTPException(status_code=500, detail=f"Błąd zapisu pliku: {exc}") from exc
    finally:
        await file.close()

    try:
        # 3. Transkrypcja przez faster-whisper (w osobnym wątku żeby nie blokować pętli zdarzeń)
        srt_text, vtt_text, info_dict = await asyncio.to_thread(
            transcribe_audio,
            audio_path=tmp_audio_path,
            quality="default",
            lang=lang if lang else "pl",
        )

        logger.info(
            "[audio] Transcription complete for %s: duration=%.1fs, segments=%d",
            media_id,
            info_dict.get("duration", 0),
            info_dict.get("segments_count", 0),
        )

        # 4. Zapisz pliki VTT i SRT do /tmp
        with open(tmp_vtt_path, "w", encoding="utf-8") as f_vtt:
            f_vtt.write(vtt_text)
        with open(tmp_srt_path, "w", encoding="utf-8") as f_srt:
            f_srt.write(srt_text)

        # 5. Utwórz job w transcript_jobs
        audio_url = f"audio://{media_id}"
        new_job = TranscriptJob(
            video_url=audio_url,
            status="fetched",
            transcript=vtt_text,
            portal_id=portal_id if portal_id and portal_id not in ("__manual__", "__add__") else None,
            user_id=str(current_user.id),
        )
        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)

        # 6. Określ tytuł
        title_to_use = (
            post_title.strip()
            if post_title and post_title.strip()
            else os.path.splitext(original_filename)[0].replace("_", " ").replace("-", " ").strip()
        )
        if not title_to_use:
            title_to_use = f"Nagranie {media_id}"

        # 7. Uruchom pipeline VSE
        portal_id_clean = (
            portal_id.strip()
            if portal_id and portal_id not in ("__manual__", "__add__")
            else None
        )
        result = await run_generate(
            video_url=audio_url,
            llm_provider=llm_provider,
            lang=lang,
            post_title_override=title_to_use,
            publication_type=publication_type,
            portal_id=portal_id_clean,
            user_id=str(current_user.id),
        )

        schema_data = result["seo"]
        schema_data["source"] = "audio"
        schema_data["media_id"] = media_id
        schema_data["audio_filename"] = original_filename
        schema_data["thumbnail_url"] = None

        # 8. Zaktualizuj job w DB na done ze schema_data
        new_job.schema_data = schema_data
        new_job.status = "done"
        await db.commit()

        processing_time = round(time.time() - start_time, 2)
        logger.info(
            "[/v1/audio/generate] Success for media_id=%s in %.2fs",
            media_id,
            processing_time,
        )

        return GenerateResponse(
            status="ok",
            video_id=media_id,
            processing_time_s=processing_time,
            schema_data=schema_data,
            transcript_available=True,
            partial_result=False,
        )

    except ValueError as exc:
        logger.error("[audio] ValueError: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("[audio] RuntimeError: %s", exc)
        error_message, error_code = _parse_runtime_error(exc)
        return GenerateResponse(
            status="error",
            video_id=media_id,
            processing_time_s=round(time.time() - start_time, 2),
            error=error_message,
            error_code=error_code,
        )
    except Exception as exc:
        logger.exception("[audio] Unexpected error during audio generation: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        # Usuń surowy plik audio z /tmp (zostawiamy .vtt i .srt dla szortów i historii)
        if os.path.exists(tmp_audio_path):
            try:
                os.remove(tmp_audio_path)
            except Exception as e:
                logger.warning("[audio] Could not remove temp audio file %s: %s", tmp_audio_path, e)
