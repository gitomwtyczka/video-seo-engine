"""VSE Jobs Router — Local Transcript Runner API.

CO: Router FastAPI obsługujący kolejkę zadań transkrypcji.

PO CO: YouTube blokuje youtube-transcript-api z Oracle Cloud VPS IP.
Ten router to szyna komunikacji między API (VPS) a Local Runner'em
(Windows Service na PC Usera z normalnym IP). Bez transkryptu Claude
nie ma danych wejściowych — pipeline się nie może wykonać.

JAK:
1. POST /v1/jobs/         — użytkownik (JWT) tworzy job
2. GET  /v1/jobs/pending  — runner (Bearer LOCAL_RUNNER_TOKEN) pobiera zadania
3. POST /v1/jobs/{id}/result — runner zwraca transkrypt
4. GET  /v1/jobs/{id}     — polling statusu (JWT lub runner)
5. GET  /v1/jobs/{id}/vtt — pobieranie pliku VTT transkrypcji
6. GET  /v1/jobs/history  — lista jobów (dla strony /historia)

Security (SUPPLEMENT-VSE-DEV-04-20260615-SECURITY):
- LOCAL_RUNNER_TOKEN: min 256-bit entropy (secrets.token_urlsafe(32))
- Rate limit: 30 req/min per token na endpointach runnera
- Sanitizacja transkryptu: strip HTML, max 50k znaków, normalizacja whitespace
- Idempotent: drugi POST na 'fetched' job zwraca 200 bez zmiany danych

## Format __VTT__ (od v2.0, 2026-06-16)

Local Runner wysyła transkrypt z timestampami w formacie:
  __VTT__\n[MM:SS] tekst\n[MM:SS] tekst...\n

Sanitize_transcript wykrywa ten prefix i zachowuje strukturę wieloliniową
zamiast normalizować whitespace. Pipeline.py konwertuje __VTT__ do
prawdziwego WebVTT dla generatora.
"""
import hashlib
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import AsyncSessionLocal
from api.models.job import TranscriptJob
from api.auth import get_current_user
from api.models.user import User, ApiKey

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

# ---------------------------------------------------------------------------
# Rate Limiting (in-memory, single-process — wystarczy dla 1 runnera)
# ---------------------------------------------------------------------------
_rate_limit_store: dict = defaultdict(list)
RATE_LIMIT_WINDOW = 60   # sekund
RATE_LIMIT_MAX = 30      # max req per okno per token


def _check_rate_limit(token: str) -> bool:
    """Sprawdza rate limit: max 30 req/min per token.

    PO CO: Flood GET /v1/jobs/pending obciąża DB. Jeden runner powinien
    pytać co 10s (6/min) — limit 30/min daje marże na błędy.

    Returns:
        True jeśli request dozwolony, False jeśli przekroczony limit.
    """
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    recent = [t for t in _rate_limit_store[token] if t > window_start]
    _rate_limit_store[token] = recent
    if len(recent) >= RATE_LIMIT_MAX:
        return False
    _rate_limit_store[token].append(now)
    return True


# ---------------------------------------------------------------------------
# Transcript Sanitization (RYZYKO 1 z Security Supplement)
# ---------------------------------------------------------------------------
# MAX_TRANSCRIPT_LENGTH — brak limitu (obsługa wielogodzinnych transmisji)
_HTML_TAGS = re.compile(r'<[^>]+>')
# Wzorzec dopuszczalny w liniach VTT: [MM:SS] tekst
_VTT_LINE = re.compile(r'^\[\d{2}:\d{2}\] .+')


def sanitize_transcript(raw: str) -> str:
    """Sanitizuje transkrypt przed przekazaniem do pipeline.

    CO: Oczyszcza tekst transkryptu z potencjalnie złośliwej treści.

    PO CO: Blokuje Fake Transcript Injection — ktoś z LOCAL_RUNNER_TOKEN
    mógłby POST-ować fałszywy HTML/skrypty jako transkrypt, które
    Claude przetworzy jak prawdą i wstrzyknie złośliwy schema do WP.

    JAK (format __VTT__, od v2.0):
    1. Sprawdzenie typu i niepustości
    2. Wykrycie formatu __VTT__ (zachowaj strukturę wieloliniową!)
    3. Strip tagów HTML z każdej linii

    JAK (plain text, fallback dla starszych runnerów):
    1. Strip tagów HTML
    2. Normalizacja whitespace

    Args:
        raw: Surowy tekst transkryptu od runnera.

    Returns:
        Oczyszczony tekst. Dla __VTT__: zachowuje newlines i markery.
        Dla plain text: jednoliniowy string.

    Raises:
        ValueError: Jeśli raw nie jest niepustym stringiem.
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("Transcript must be a non-empty string")

    # Wykryj format __VTT__ (runner v2.0+)
    is_vtt = raw.startswith("__VTT__")

    if is_vtt:
        # Zachowaj strukturę wieloliniową — nie normalizuj whitespace!
        # Przetwarzaj linię po linii: strip HTML, zachowaj markery [MM:SS]
        lines = raw.split("\n")
        clean_lines = []
        for line in lines:
            # Strip tagów HTML z każdej linii
            clean_line = _HTML_TAGS.sub(' ', line)
            # Usuń nadmiarowe spacje wewnątrz linii (nie newlines!)
            clean_line = ' '.join(clean_line.split())
            if clean_line:
                clean_lines.append(clean_line)
        clean = "\n".join(clean_lines)
    else:
        # Fallback: plain text (stary runner bez timestampów)
        clean = _HTML_TAGS.sub(' ', raw)
        clean = ' '.join(clean.split())

    # Brak limitu długości — obsługujemy wielogodzinne transmisje
    logger.debug("Transcript sanitized: %d chars", len(clean))
    return clean


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
_LOCAL_RUNNER_TOKEN: Optional[str] = None


def _get_local_runner_token() -> str:
    """Pobiera LOCAL_RUNNER_TOKEN z env (lazy load)."""
    global _LOCAL_RUNNER_TOKEN
    if _LOCAL_RUNNER_TOKEN is None:
        _LOCAL_RUNNER_TOKEN = os.getenv("LOCAL_RUNNER_TOKEN", "")
    return _LOCAL_RUNNER_TOKEN


def _verify_runner_token(authorization: str = Header(None)) -> str:
    """Weryfikuje Bearer token runnera (globalny LOCAL_RUNNER_TOKEN lub indywidualny klucz vse_live_*)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")

    token = authorization[7:].strip()  # strip 'Bearer '
    if not token:
        raise HTTPException(401, "Empty token")

    # Rate limit check
    if not _check_rate_limit(token[:12]):
        raise HTTPException(429, "Rate limit exceeded: max 30 req/min")

    if token.startswith("vse_"):
        return token

    expected = _get_local_runner_token()
    if not expected:
        logger.error("LOCAL_RUNNER_TOKEN not configured in env")
        raise HTTPException(503, "Local runner not configured on server")

    if token != expected:
        logger.warning("Runner auth: invalid token attempt")
        raise HTTPException(401, "Invalid LOCAL_RUNNER_TOKEN")

    return token


async def _resolve_runner_user_id(token: str, db: AsyncSession) -> Optional[uuid.UUID]:
    """Jeśli token to indywidualny klucz API (vse_*), weryfikuje go w bazie, aktualizuje last_used_at i zwraca user_id."""
    if not token.startswith("vse_"):
        return None
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    res = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)  # noqa: E712
    )
    api_key = res.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(401, "Invalid or inactive VSE Desktop Runner API key")
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return api_key.user_id


async def _get_db():
    """Dependency: AsyncSession dla endpointow jobs."""
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CreateJobRequest(BaseModel):
    """Request body dla POST /v1/jobs/ — tworzy nowe zadanie transkrypcji."""
    video_url: str = Field(..., description="YouTube video URL lub ID")


class JobResult(BaseModel):
    """Body POST /v1/jobs/{id}/result — runner zwraca wynik transkrypcji."""
    transcript: Optional[str] = Field(None, description="Tekst transkryptu (None jeśli status=failed)")
    status: str = Field(..., description="'fetched' lub 'failed'")
    error: Optional[str] = Field(None, description="Opis błędu przy status=failed")


class JobResponse(BaseModel):
    """Odpowiedź z informacją o zadaniu transkrypcji."""
    id: str
    video_url: str
    status: str
    error: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class FullJobResponse(BaseModel):
    """Pełna odpowiedź z job'u — zawiera schema_data dla historii.

    CO: Rozszerzony model odpowiedzi zwracający wygenerowane dane SEO.
    PO CO: Strona /historia po kliknięciu 'Otwórz wyniki' ładuje pełne
    dane z tego endpointu i wyświetla je na dashboardzie.
    """
    id: str
    video_url: str
    video_id: Optional[str] = None
    status: str
    error: Optional[str] = None
    has_vtt: bool = False
    schema_data: Optional[dict] = None
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class HistoryJobResponse(BaseModel):
    """Rozszerzony response dla historii — zawiera tytuł z YT URL.

    CO: Model odpowiedzi dla endpointu GET /v1/jobs/history.
    PO CO: Strona /historia potrzebuje więcej danych niż JobResponse
    — tytuł wideo, czas przetworzenia, link do YouTube.
    """
    id: str
    video_url: str
    video_id: Optional[str] = None
    status: str
    error: Optional[str] = None
    has_vtt: bool = False
    has_schema: bool = False
    post_title: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    body: CreateJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(_get_db),
) -> JobResponse:
    """Tworzy nowe zadanie transkrypcji w kolejce Local Runner'a.

    CO: Endpoint dla frontendu/użytkownika — inicjuje pipeline.
    PO CO: Zamiast próbować pobrać transkrypt na VPS (ban IP),
    tworzy job w kolejce — Local Runner pobierze lokalnie.

    Returns:
        201 Created z nowym JobResponse.
    """
    job = TranscriptJob(
        video_url=body.video_url,
        status="pending",
        user_id=current_user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    logger.info("[jobs] Created job %s for %s", job.id, body.video_url)
    return _job_to_response(job)


@router.get("/pending", response_model=List[JobResponse])
async def get_pending_jobs(
    token: str = Depends(_verify_runner_token),
    db: AsyncSession = Depends(_get_db),
) -> List[JobResponse]:
    """Zwraca listę jobów ze statusem 'pending' dla Local Runner'a.

    CO: Polling endpoint dla Windows Service lub VSE Desktop Runner.
    PO CO: Runner odpytuje ten endpoint co POLL_INTERVAL sekund,
    pobiera zadania i zaczyna fetch transkryptów lokalnie.
    Auth: Bearer LOCAL_RUNNER_TOKEN lub indywidualny klucz vse_live_* (rate limit: 30/min).
    """
    runner_user_id = await _resolve_runner_user_id(token, db)
    query = select(TranscriptJob).where(TranscriptJob.status == "pending")
    if runner_user_id is not None:
        query = query.where(TranscriptJob.user_id == runner_user_id)

    result = await db.execute(
        query.order_by(TranscriptJob.created_at.asc()).limit(10)
    )
    jobs = result.scalars().all()
    logger.info("[jobs] /pending: %d jobs returned for runner (user_id=%s)", len(jobs), runner_user_id)
    return [_job_to_response(j) for j in jobs]


@router.get("/history", response_model=List[HistoryJobResponse])
async def get_job_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(_get_db),
) -> List[HistoryJobResponse]:
    """Zwraca historię jobów transkrypcji (wszystkie statusy)."""
    query = select(TranscriptJob)
    if not current_user.is_admin:
        query = query.where(TranscriptJob.user_id == current_user.id)

    result = await db.execute(
        query
        .order_by(desc(TranscriptJob.created_at))
        .offset(offset)
        .limit(limit)
    )
    jobs = result.scalars().all()
    return [_job_to_history_response(j) for j in jobs]


@router.post("/{job_id}/result", response_model=dict)
async def complete_job(
    job_id: uuid.UUID,
    result: JobResult,
    token: str = Depends(_verify_runner_token),
    db: AsyncSession = Depends(_get_db),
) -> dict:
    """Runner przesyła wynik transkrypcji (lub błąd).

    KROK B.B: Przyjmuje wynik również gdy job przeszedł w status 'cloud_fallback'
    lub 'processing' (oraz zawsze gdy nie ma jeszcze zapisanego transkryptu),
    aby wynik z Local Runnera nigdy nie przepadał.
    """
    runner_user_id = await _resolve_runner_user_id(token, db)
    job = await db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    if runner_user_id is not None and job.user_id is not None and job.user_id != runner_user_id:
        raise HTTPException(403, "Job belongs to another user")

    if job.status not in ("pending", "cloud_fallback", "processing") and job.transcript:
        logger.warning(
            "[jobs] Job %s already has transcript in status '%s', ignoring duplicate result",
            job_id, job.status,
        )
        return {"status": "already_processed", "job_status": job.status}

    if result.status == "fetched" and result.transcript:
        try:
            sanitized = sanitize_transcript(result.transcript)
        except ValueError as e:
            logger.error("[jobs] Transcript sanitization failed for %s: %s", job_id, e)
            raise HTTPException(422, f"Invalid transcript: {e}")

        is_vtt = sanitized.startswith("__VTT__")
        logger.info(
            "[jobs] Job %s: transcript received (%d chars, format=%s, prev_status=%s)",
            job_id, len(sanitized), "VTT" if is_vtt else "plain", job.status,
        )

        job.transcript = sanitized
        # Jeśli schema_data już istnieje, ustawiamy status 'done'; w przeciwnym razie 'fetched' (pipeline czeka na 'fetched' lub 'done')
        job.status = "done" if job.schema_data else "fetched"
        job.error = None
    elif result.status == "failed":
        if not job.transcript:
            job.status = "failed"
            job.error = result.error or "Runner reported failure"
            logger.error("[jobs] Job %s failed: %s", job_id, job.error)
    else:
        raise HTTPException(422, "status must be 'fetched' (with transcript) or 'failed'")

    job.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": job.status}


@router.get("/{job_id}", response_model=FullJobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(_get_db),
) -> FullJobResponse:
    """Pobiera pełne dane zadania transkrypcji (w tym schema_data).

    CO: Endpoint do pollingu statusu i pobierania wyników.
    PO CO: Strona /historia używa tego endpointu do załadowania
    wygenerowanego contentu (artykuł, rozdziay, FAQ, schema JSON-LD)
    po kliknięciu 'Otwórz wyniki'.
    Auth: Brak (dostęp publiczny w obrębie VPS — ID to UUID v4 = nieprzewidywalne).

    Returns:
        FullJobResponse z aktualnym statusem i schema_data (jeśli dostępne).
    """
    job = await db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    if job.user_id is not None and job.user_id != current_user.id:
        if not current_user.is_admin:
            raise HTTPException(403, "Access denied")
    return _job_to_full_response(job)


@router.get("/{job_id}/vtt")
async def get_job_vtt(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(_get_db),
) -> Response:
    """Pobiera transkrypt VTT jako plik do pobrania.

    CO: Endpoint serwujący transkrypt w formacie WebVTT.

    PO CO: Badge VTT w /historia jest klikalnym linkiem prowadzącym
    do tego endpointu. Użytkownik może pobrać / podejrzeć transkrypt
    bez szukania go w bazie danych ręcznie.

    JAK:
    1. Pobiera job z DB po UUID.
    2. Sprawdza czy transkrypt istnieje i jest w formacie __VTT__.
    3. Konwertuje __VTT__ do prawdziwego WebVTT (pipeline._vtt_runner_to_webvtt).
    4. Zwraca jako text/vtt z Content-Disposition: inline.
    Dla plain text transkryptów — zwraca text/plain.

    Returns:
        Response z treścią VTT i odpowiednim Content-Type.
    """
    job = await db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    if job.user_id is not None and job.user_id != current_user.id:
        if not current_user.is_admin:
            raise HTTPException(403, "Access denied")

    if not job.transcript:
        raise HTTPException(404, "No transcript available for this job")

    video_id = _extract_video_id_from_url(job.video_url) if job.video_url else "transcript"
    filename = f"{video_id or 'transcript'}.vtt"

    if job.transcript.startswith("__VTT__"):
        # Konwertuj __VTT__ runner format do prawdziwego WebVTT
        from api.services.pipeline import _vtt_runner_to_webvtt
        webvtt_content = _vtt_runner_to_webvtt(job.transcript)
        return Response(
            content=webvtt_content,
            media_type="text/vtt",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )
    else:
        # Plain text transkrypt — zwróć jako text/plain
        return Response(
            content=job.transcript,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'inline; filename="{video_id or "transcript"}.txt"',
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_video_id_from_url(url: str) -> Optional[str]:
    """Wyciąga YouTube video ID z URL."""
    import re
    patterns = [
        r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def _job_to_response(job: TranscriptJob) -> JobResponse:
    """Konwertuje ORM model na Pydantic response."""
    return JobResponse(
        id=str(job.id),
        video_url=job.video_url,
        status=job.status,
        error=job.error,
        created_at=job.created_at.isoformat() if job.created_at else "",
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
    )


def _job_to_full_response(job: TranscriptJob) -> FullJobResponse:
    """Konwertuje ORM model na pełny response z schema_data."""
    video_id = _extract_video_id_from_url(job.video_url) if job.video_url else None
    has_vtt = bool(job.transcript and (job.transcript.startswith("__VTT__") or job.transcript.startswith("WEBVTT")))
    return FullJobResponse(
        id=str(job.id),
        video_url=job.video_url,
        video_id=video_id,
        status=job.status,
        error=job.error,
        has_vtt=has_vtt,
        schema_data=job.schema_data,
        created_at=job.created_at.isoformat() if job.created_at else "",
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
    )


def _job_to_history_response(job: TranscriptJob) -> HistoryJobResponse:
    """Konwertuje ORM model na rozszerzony response dla historii."""
    video_id = _extract_video_id_from_url(job.video_url) if job.video_url else None
    has_vtt = bool(job.transcript and (job.transcript.startswith("__VTT__") or job.transcript.startswith("WEBVTT")))
    has_schema = job.schema_data is not None
    post_title = None
    if has_schema and isinstance(job.schema_data, dict):
        post_title = job.schema_data.get("post_title")
    return HistoryJobResponse(
        id=str(job.id),
        video_url=job.video_url,
        video_id=video_id,
        status=job.status,
        error=job.error,
        has_vtt=has_vtt,
        has_schema=has_schema,
        post_title=post_title,
        created_at=job.created_at.isoformat() if job.created_at else "",
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
    )
