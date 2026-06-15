"""VSE Jobs Router — Local Transcript Runner API.

CO: Router FastAPI obsługujący kolejkę zadąń transkrypcji.

PO CO: YouTube blokuje youtube-transcript-api z Oracle Cloud VPS IP.
Ten router to szyna komunikacji między API (VPS) a Local Runner’em
(Windows Service na PC Usera z normalnym IP). Bez transkryptu Claude
nie ma danych wejściowych — pipeline się nie może wykonać.

JAK:
1. POST /v1/jobs/         — użytkownik (JWT) tworzy job
2. GET  /v1/jobs/pending  — runner (Bearer LOCAL_RUNNER_TOKEN) pobiera zadania
3. POST /v1/jobs/{id}/result — runner zwraca transkrypt
4. GET  /v1/jobs/{id}     — polling statusu (JWT lub runner)

Security (SUPPLEMENT-VSE-DEV-04-20260615-SECURITY):
- LOCAL_RUNNER_TOKEN: min 256-bit entropy (secrets.token_urlsafe(32))
- Rate limit: 30 req/min per token na endpointach runnera
- Sanitizacja transkryptu: strip HTML, max 50k znaków, normalizacja whitespace
- Idempotent: drugi POST na 'fetched' job zwraca 200 bez zmiany danych
"""
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import AsyncSessionLocal
from api.models.job import TranscriptJob

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
MAX_TRANSCRIPT_LENGTH = 50_000  # ~6h wideo
_ALLOWED_CHARS = re.compile(r'<[^>]+>')


def sanitize_transcript(raw: str) -> str:
    """Sanitizuje transkrypt przed przekazaniem do Claude.

    CO: Oczyszcza tekst transkryptu z potencjalnie złośliwej treści.

    PO CO: Blokuje Fake Transcript Injection — ktoś z LOCAL_RUNNER_TOKEN
    mógłby POST-ować fałszywy HTML/skrypty jako transkrypt, które
    Claude przetworzy jak prawdą i wstrzyknie złośliwy schema do WP.

    JAK:
    1. Sprawdzenie typu i niepustości
    2. Strip tagów HTML (nie escaping — usuwanie)
    3. Normalizacja whitespace
    4. Obcięcie do MAX_TRANSCRIPT_LENGTH

    Args:
        raw: Surowy tekst transkryptu od runnera.

    Returns:
        Oczyszczony tekst gotowy do przekazania do generatora.

    Raises:
        ValueError: Jeśli raw nie jest niepustym stringiem.
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("Transcript must be a non-empty string")

    # Strip HTML tags
    clean = _ALLOWED_CHARS.sub(' ', raw)

    # Normalizuj whitespace
    clean = ' '.join(clean.split())

    # Ogranicz długość
    if len(clean) > MAX_TRANSCRIPT_LENGTH:
        clean = clean[:MAX_TRANSCRIPT_LENGTH]
        logger.warning(
            "Transcript truncated to %d chars (original: %d)",
            MAX_TRANSCRIPT_LENGTH, len(raw),
        )

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
    """Weryfikuje Bearer token runnera.

    PO CO: Endpointy /pending i /{id}/result są dostępne tylko dla
    autoryzowanego Local Runner’a. Chronione przez Bearer token
    z minimalną entropią 256 bitów.

    Raises:
        HTTPException 401: Brak lub nieprawidłowy token.
        HTTPException 503: Token nie skonfigurowany na serwerze.
    """
    expected = _get_local_runner_token()
    if not expected:
        logger.error("LOCAL_RUNNER_TOKEN not configured in env")
        raise HTTPException(503, "Local runner not configured on server")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")

    token = authorization[7:]  # strip 'Bearer '
    if token != expected:
        logger.warning("Runner auth: invalid token attempt")
        raise HTTPException(401, "Invalid LOCAL_RUNNER_TOKEN")

    # Rate limit check
    if not _check_rate_limit(token[:8]):  # tylko pierwsze 8 znaków do klucza
        raise HTTPException(429, "Rate limit exceeded: max 30 req/min")

    return token


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    body: CreateJobRequest,
    db: AsyncSession = Depends(_get_db),
) -> JobResponse:
    """Tworzy nowe zadanie transkrypcji w kolejce Local Runner’a.

    CO: Endpoint dla frontendu/użytkownika — inicjuje pipeline.
    PO CO: Zamiast próbować pobrać transkrypt na VPS (ban IP),
    tworzy job w kolejce — Local Runner pobierze lokalnie.

    Returns:
        201 Created z nowym JobResponse.
    """
    job = TranscriptJob(
        video_url=body.video_url,
        status="pending",
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
    """Zwraca listę jobów ze statusem 'pending' dla Local Runner’a.

    CO: Polling endpoint dla Windows Service.
    PO CO: Runner odpytuje ten endpoint co POLL_INTERVAL sekund,
    pobiera zadania i zaczyna fetch transkryptów lokalnie.
    Auth: Bearer LOCAL_RUNNER_TOKEN (rate limit: 30/min).

    Returns:
        Lista JobResponse ze statusem 'pending'.
    """
    result = await db.execute(
        select(TranscriptJob)
        .where(TranscriptJob.status == "pending")
        .order_by(TranscriptJob.created_at.asc())
        .limit(10)  # max 10 na raz, unika floodów
    )
    jobs = result.scalars().all()
    logger.info("[jobs] /pending: %d jobs returned for runner", len(jobs))
    return [_job_to_response(j) for j in jobs]


@router.post("/{job_id}/result", response_model=dict)
async def complete_job(
    job_id: uuid.UUID,
    result: JobResult,
    token: str = Depends(_verify_runner_token),
    db: AsyncSession = Depends(_get_db),
) -> dict:
    """Runner przesyła wynik transkrypcji (lub błąd).

    CO: Endpoint do którego Local Runner POST-uje po pobraniu transkryptu.
    PO CO: Transkrypt trafia do DB, pipeline może kontynuować generowanie.
    Auth: Bearer LOCAL_RUNNER_TOKEN.

    Security:
    - Idempotent: jeśli job już 'fetched', zwraca 200 bez zmiany danych.
    - Sanitizacja: strip HTML, limit 50k znaków przed zapisem.

    Returns:
        {"status": "fetched"} lub {"status": "already_processed"}.
    """
    job = await db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    # Idempotent: jeśli już przetworzony, zwroć 200 bez zmian
    if job.status != "pending":
        logger.warning(
            "[jobs] Job %s already in status '%s', ignoring duplicate result",
            job_id, job.status,
        )
        return {"status": "already_processed", "job_status": job.status}

    if result.status == "fetched" and result.transcript:
        try:
            sanitized = sanitize_transcript(result.transcript)
        except ValueError as e:
            logger.error("[jobs] Transcript sanitization failed for %s: %s", job_id, e)
            raise HTTPException(422, f"Invalid transcript: {e}")

        job.transcript = sanitized
        job.status = "fetched"
        job.error = None
        logger.info(
            "[jobs] Job %s: transcript received (%d chars)",
            job_id, len(sanitized),
        )
    elif result.status == "failed":
        job.status = "failed"
        job.error = result.error or "Runner reported failure"
        logger.error("[jobs] Job %s failed: %s", job_id, job.error)
    else:
        raise HTTPException(422, "status must be 'fetched' (with transcript) or 'failed'")

    job.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": job.status}


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
) -> JobResponse:
    """Pobiera status i dane zadania transkrypcji.

    CO: Endpoint do pollingu statusu przez frontend lub pipeline.
    PO CO: Frontend pokazuje użytkownikowi postęp, pipeline czeka na 'fetched'.
    Auth: Brak (dostęp publiczny w obrębie VPS — ID to UUID v4 = nieprzewidyąne).

    Returns:
        JobResponse z aktualnym statusem.
    """
    job = await db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return _job_to_response(job)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
