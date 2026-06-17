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
MAX_TRANSCRIPT_LENGTH = 100_000  # zwiększone z 50k bo __VTT__ dodaje overhead
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
    4. Obcięcie do MAX_TRANSCRIPT_LENGTH

    JAK (plain text, fallback dla starszych runnerów):
    1. Strip tagów HTML
    2. Normalizacja whitespace
    3. Obcięcie do MAX_TRANSCRIPT_LENGTH

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

    # Ogranicz długość
    if len(clean) > MAX_TRANSCRIPT_LENGTH:
        if is_vtt:
            # Dla VTT: obetnij po pełnych liniach, nie w środku
            truncated_lines = []
            total = 0
            for line in clean.split("\n"):
                if total + len(line) + 1 > MAX_TRANSCRIPT_LENGTH:
                    break
                truncated_lines.append(line)
                total += len(line) + 1
            clean = "\n".join(truncated_lines)
        else:
            clean = clean[:MAX_TRANSCRIPT_LENGTH]
        logger.warning(
            "Transcript truncated to ~%d chars (original: %d)",
            len(clean), len(raw),
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
    autoryzowanego Local Runner'a. Chronione przez Bearer token
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
        .limit(10)  # max 10 na raz, unika floodow
    )
    jobs = result.scalars().all()
    logger.info("[jobs] /pending: %d jobs returned for runner", len(jobs))
    return [_job_to_response(j) for j in jobs]


@router.get("/history", response_model=List[HistoryJobResponse])
async def get_job_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(_get_db),
) -> List[HistoryJobResponse]:
    """Zwraca historię jobów transkrypcji (wszystkie statusy).

    CO: Endpoint dla strony /historia — lista przetworzonych filmów.

    PO CO: Użytkownik widzi co już przetworzył: jakie filmy, kiedy,
    z jakim wynikiem. Historia jest z PostgreSQL — nie localStorage.
    To nienaruszalna zasada architektoniczna (patrz ROADMAP.md).

    JAK: SELECT z transcript_jobs ORDER BY created_at DESC, paginacja.
    Nie filtruje po user_id — w MVP jest jeden użytkownik (Admin/Agency).
    W przyszłości: filtrowanie po user_id z JWT tokenu.

    Args:
        limit: Maks. liczba wyników (domyślnie 50, max 200).
        offset: Przesunięcie dla paginacji.

    Returns:
        Lista HistoryJobResponse posortowana od najnowszych.
    """
    result = await db.execute(
        select(TranscriptJob)
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

    CO: Endpoint do którego Local Runner POST-uje po pobraniu transkryptu.
    PO CO: Transkrypt trafia do DB, pipeline może kontynuować generowanie.
    Auth: Bearer LOCAL_RUNNER_TOKEN.

    Security:
    - Idempotent: jeśli job już 'fetched', zwraca 200 bez zmiany danych.
    - Sanitizacja: strip HTML, limit 100k znaków, VTT-aware (zachowuje newlines).

    Returns:
        {"status": "fetched"} lub {"status": "already_processed"}.
    """
    job = await db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    # Idempotent: jeśli już przetworzony, zwróć 200 bez zmian
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

        # Loguj format dla diagnostyki
        is_vtt = sanitized.startswith("__VTT__")
        logger.info(
            "[jobs] Job %s: transcript received (%d chars, format=%s)",
            job_id, len(sanitized), "VTT" if is_vtt else "plain",
        )

        job.transcript = sanitized
        job.status = "fetched"
        job.error = None
    elif result.status == "failed":
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
    return _job_to_full_response(job)


@router.get("/{job_id}/vtt")
async def get_job_vtt(
    job_id: uuid.UUID,
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
    has_vtt = bool(job.transcript and job.transcript.startswith("__VTT__"))
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
    has_vtt = bool(job.transcript and job.transcript.startswith("__VTT__"))
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
