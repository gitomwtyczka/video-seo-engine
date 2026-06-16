"""VSE Local Transcript Runner.

CO: Skrypt Python'a działający jako Windows Service (przez NSSM).
Polluje API VSE po zadania transkrypcji i pobiera je lokalnie.

PO CO:
YouTube blokuje youtube-transcript-api wywoływane z Oracle Cloud VPS IP
(data center IP ban). Ten runner działa na lokalnym PC Usera, który ma
normalne IP domowe/biurowe — YouTube nie blokuje. Pattern: GitHub Actions
self-hosted runner.

JAK:
1. Poll GET /v1/jobs/pending co POLL_INTERVAL sekund
2. Dla każdego 'pending' joba: pobierz transkrypt przez youtube-transcript-api
3. POST /v1/jobs/{id}/result z transkryptem lub błędem
4. Pętla się powtarza bez końca (SIGTERM = graceful stop)

Instalacja:
  Skopiuj plik .env z LOCAL_RUNNER_TOKEN i VSE_API_BASE
  Uruchom install.bat jako administrator (wymaga NSSM)

Log: %ProgramData%\\VSELocalRunner\\runner.log (lub stdout w trybie dev)

## Format transkryptu (VTT-like)

Od v2.0 runner wysyła transkrypt Z TIMESTAMPAMI w formacie:
  __VTT__\n[MM:SS] tekst\n[MM:SS] tekst...\n

To pozwala pipeline.py zamienić segmenty na prawdziwy plik .vtt który
generator.py parsuje do anchor-matching rozdziałów. Bez timestampów
generator nie może wyciągnąć rzeczywistych czasów → rozdziały = 0.
"""
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

API_BASE = os.getenv("VSE_API_BASE", "https://vse.impresjapr.pl")
TOKEN = os.getenv("LOCAL_RUNNER_TOKEN", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))  # sekund
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", r"C:\ProgramData\VSELocalRunner")
LANG_PRIORITY = ["pl", "en", "en-US", "en-GB"]  # kolejność preferowanych języków

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    """Konfiguruje logger: stdout + plik (jeśli LOG_DIR dostępny).

    Poziom kontrolowany przez zmienną LOG_LEVEL (domyślnie INFO).
    Plik logu: {LOG_DIR}\\runner.log
    """
    logger = logging.getLogger("vse_runner")
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Zawsze stdout
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # Plik logu (opcjonalnie)
    try:
        log_path = Path(LOG_DIR)
        log_path.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path / "runner.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning("Could not create log file in %s: %s", LOG_DIR, e)

    return logger


log = _setup_logging()

# ---------------------------------------------------------------------------
# YouTube Transcript Fetching
# ---------------------------------------------------------------------------

_YT_ID_PATTERNS = [
    re.compile(r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})'),
    re.compile(r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})'),
    re.compile(r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})'),
    re.compile(r'(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})'),
]


def extract_video_id(url: str) -> Optional[str]:
    """Wyodrębnia YouTube video ID z URL lub zwraca None.

    Args:
        url: YouTube URL lub ID (11 znaków).

    Returns:
        11-znakowe video ID lub None jeśli nieparsowalne.
    """
    for pat in _YT_ID_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    # Bezpośrednio ID (11 znaków)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url
    return None


def _format_segments_as_vtt(segments: list) -> str:
    """Konwertuje segmenty youtube-transcript-api do formatu VTT-like z markerami.

    CO: Zamienia listę [{text, start, duration}] na wieloliniowy string
    z markerami [MM:SS] co segment.

    PO CO: generator.py (parse_vtt_full) oczekuje pliku .vtt z prawdziwymi
    timestampami. Jeśli runner wyśle plain text (bez czasów), generator
    nie może dopasować rozdziałów do rzeczywistych momentów wideo →
    wszystkie chaptery pokazują czas=0.

    Ten format __VTT__ to "VTT-like" — pipeline.py konwertuje go do
    prawdziwego WebVTT zanim zapisze do pliku tymczasowego dla generatora.

    Format wyjściowy:
        __VTT__\n[MM:SS] tekst\n[MM:SS] tekst...\n

    Args:
        segments: Lista dictów z polami: text (str), start (float), duration (float).

    Returns:
        Wieloliniowy string z prefixem __VTT__ i markerami [MM:SS].
    """
    lines = ["__VTT__"]
    for seg in segments:
        start = seg.get("start", 0.0)
        text = seg.get("text", "").strip()
        if not text:
            continue
        m = int(start // 60)
        s = int(start % 60)
        lines.append(f"[{m:02d}:{s:02d}] {text}")
    return "\n".join(lines)


def fetch_transcript(video_url: str) -> Optional[str]:
    """Pobiera transkrypt YouTube przez youtube-transcript-api Z TIMESTAMPAMI.

    CO: Lokalne pobranie transkryptu na PC Usera w formacie VTT-like.

    PO CO: Oracle Cloud VPS ma zbanowane IP — tutaj działamy z normalnego IP.
    youtube-transcript-api nie wymaga klucza API.

    ZMIANA v2.0 (2026-06-16): Wysyłamy teraz transkrypt Z TIMESTAMPAMI
    (format __VTT__) zamiast plain text. Bez timestampów generator nie
    może anchor-matchować rozdziałów → wszystkie chaptery = time:0.

    JAK:
    1. Wyodrębnienie video ID z URL
    2. Listowanie dostępnych transkryptów
    3. Fetch w kolejności LANG_PRIORITY (pl, en, en-US, en-GB)
    4. Fallback: pierwszy dostępny transkrypt
    5. Formatowanie segmentów jako [MM:SS] tekst z prefixem __VTT__

    Args:
        video_url: YouTube URL lub ID.

    Returns:
        String z prefixem __VTT__ i timestampami, lub None jeśli brak transkryptu.

    Raises:
        Exception: Gdy youtube-transcript-api zgłosi błąd.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise RuntimeError(
            "youtube-transcript-api not installed. "
            "Run: pip install youtube-transcript-api"
        )

    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError(f"Cannot extract video ID from: {video_url}")

    log.debug("Fetching transcript for video_id=%s", video_id)

    ytt = YouTubeTranscriptApi()

    # Lista dostępnych transkryptów
    transcript_list = ytt.list(video_id)

    # Próbuj w kolejności priorytetów językowych
    transcript = None
    for lang in LANG_PRIORITY:
        try:
            transcript = transcript_list.find_transcript([lang])
            log.debug("Found transcript in language: %s", lang)
            break
        except Exception:
            continue

    # Fallback: pierwszy dostępny
    if transcript is None:
        try:
            transcript = next(iter(transcript_list))
            log.debug("Using fallback transcript (first available)")
        except StopIteration:
            return None

    # Fetch segmentów Z TIMESTAMPAMI
    segments = transcript.fetch()

    # Konwertuj do formatu VTT-like z markerami [MM:SS]
    # segments to lista FetchedTranscriptSnippet lub dict-like z polami:
    # text, start, duration
    seg_dicts = []
    for s in segments:
        if hasattr(s, "text"):
            seg_dicts.append({"text": s.text, "start": getattr(s, "start", 0.0)})
        elif isinstance(s, dict):
            seg_dicts.append(s)

    vtt_text = _format_segments_as_vtt(seg_dicts)
    total_chars = len(vtt_text)
    log.info("Transcript fetched with timestamps: %d chars, %d segments", total_chars, len(seg_dicts))
    return vtt_text if seg_dicts else None


# ---------------------------------------------------------------------------
# API Communication
# ---------------------------------------------------------------------------

def _headers() -> dict:
    """Zwraca nagłówki HTTP z Bearer token runnera."""
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }


def get_pending_jobs() -> list:
    """Pobiera listę pending jobów z API.

    Returns:
        Lista dictów z job'ami lub pusta lista przy błędzie.
    """
    try:
        r = requests.get(
            f"{API_BASE}/v1/jobs/pending",
            headers=_headers(),
            timeout=15,
        )
        if r.status_code == 429:
            log.warning("Rate limit hit — waiting 60s")
            time.sleep(60)
            return []
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError as e:
        log.warning("Connection error polling /v1/jobs/pending: %s", e)
        return []
    except Exception as e:
        log.error("Unexpected error polling /v1/jobs/pending: %s", e)
        return []


def submit_result(job_id: str, transcript: Optional[str], error: Optional[str] = None) -> bool:
    """Wysyła wynik transkrypcji do API.

    Args:
        job_id: UUID job'u.
        transcript: Tekst transkryptu z __VTT__ prefix (None jeśli status=failed).
        error: Opis błędu (None jeśli OK).

    Returns:
        True jeśli sukces, False przy błędzie.
    """
    status = "fetched" if transcript else "failed"
    payload = {
        "transcript": transcript,
        "status": status,
        "error": error,
    }
    try:
        r = requests.post(
            f"{API_BASE}/v1/jobs/{job_id}/result",
            json=payload,
            headers=_headers(),
            timeout=30,
        )
        r.raise_for_status()
        log.debug("Job %s result submitted: status=%s", job_id, r.json().get("status"))
        return True
    except Exception as e:
        log.error("Failed to submit result for job %s: %s", job_id, e)
        return False


# ---------------------------------------------------------------------------
# Job Processing
# ---------------------------------------------------------------------------

def process_job(job: dict) -> None:
    """Przetwarza pojedyncze zadanie transkrypcji.

    CO: Główna logika przetwarzania — pobierz i wyślij.

    PO CO: Enkapsuluje obsługę jednego job'u — błędy jednego joba
    nie przerywają pętli głównej.

    Args:
        job: Dict z polami: id, video_url, status.
    """
    job_id = job.get("id")
    video_url = job.get("video_url", "")

    if not job_id or not video_url:
        log.warning("Skipping malformed job: %s", job)
        return

    log.info("Processing job %s: %s", job_id, video_url)

    try:
        text = fetch_transcript(video_url)
        if text:
            submit_result(job_id, transcript=text)
            log.info("Job %s: OK (%d chars, VTT timestamps included)", job_id, len(text))
        else:
            submit_result(job_id, transcript=None, error="No transcript available for this video")
            log.warning("Job %s: no transcript found", job_id)
    except Exception as e:
        err_msg = str(e)[:500]
        log.error("Job %s error: %s", job_id, err_msg)
        submit_result(job_id, transcript=None, error=err_msg)


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Główna pętla Local Runner'a.

    Działa w nieskończonej pętli (Windows Service pattern).
    Zatrzymanie: SIGTERM lub Ctrl+C (SIGINT).
    Restart po awarii: NSSM automatycznie restartuje po 5s.
    """
    if not TOKEN:
        log.error(
            "LOCAL_RUNNER_TOKEN not set! "
            "Create .env file with LOCAL_RUNNER_TOKEN=your_token"
        )
        sys.exit(1)

    log.info("=" * 60)
    log.info("VSE Local Transcript Runner started")
    log.info("API: %s", API_BASE)
    log.info("Poll interval: %ds", POLL_INTERVAL)
    log.info("Log dir: %s", LOG_DIR)
    log.info("Transcript format: __VTT__ with [MM:SS] timestamps")
    log.info("=" * 60)

    while True:
        try:
            jobs = get_pending_jobs()
            if jobs:
                log.info("%d pending job(s) found", len(jobs))
                for job in jobs:
                    process_job(job)
            else:
                log.debug("No pending jobs")

        except KeyboardInterrupt:
            log.info("KeyboardInterrupt — stopping VSE Local Runner")
            break
        except Exception as e:
            log.error("Unexpected error in main loop: %s", e, exc_info=True)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
