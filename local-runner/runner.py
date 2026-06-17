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
2. Dla każdego 'pending' joba: pobierz transkrypt przez yt-dlp (cookies) lub youtube-transcript-api
3. POST /v1/jobs/{id}/result z transkryptem lub błędem
4. Pętla się powtarza bez końca (SIGTERM = graceful stop)

Instalacja:
  Skopiuj plik .env z LOCAL_RUNNER_TOKEN i VSE_API_BASE
  Uruchom install.bat jako administrator (wymaga NSSM)

Log: %ProgramData%\VSELocalRunner\runner.log (lub stdout w trybie dev)

## Format transkryptu (VTT-like)

Od v2.0 runner wysyła transkrypt Z TIMESTAMPAMI w formacie:
  __VTT__\n[MM:SS] tekst\n[MM:SS] tekst...\n

To pozwala pipeline.py zamienić segmenty na prawdziwy plik .vtt który
generator.py parsuje do anchor-matching rozdziałów. Bez timestampów
generator nie może wyciągnąć rzeczywistych czasów → rozdziały = 0.

## Strategia pobierania transkryptu (v3.1 — 2026-06-17)

YouTube coraz agresywniej blokuje requesty bez cookies — nawet na domowym IP.

Aktualna strategia (primary → fallback):
1. yt-dlp --cookies-from-browser firefox  ← PRIMARY (działa, pobiera auth z Firefox)
2. yt-dlp --cookies-from-browser chrome   ← fallback 1
3. yt-dlp --cookies-from-browser edge     ← fallback 2
4. youtube-transcript-api (bez cookies)   ← last resort (może być zablokowane)

Format json3 → konwertujemy do __VTT__ z timestampami.
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import random
from pathlib import Path
from typing import Optional, Tuple

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

# Kolejność przeglądarek do cookies — zmień wg dostępności na PC
BROWSER_PRIORITY = ["firefox", "chrome", "edge", "chromium"]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    """Konfiguruje logger: stdout + plik (jeśli LOG_DIR dostępny).

    Poziom kontrolowany przez zmienną LOG_LEVEL (domyślnie INFO).
    Plik logu: {LOG_DIR}\runner.log
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


def _parse_json3_to_segments(json3_text: str) -> list:
    """Parsuje format json3 (yt-dlp) do listy segmentów [{text, start}].

    CO: YouTube json3 zawiera tStartMs, dDurationMs i segs[{utf8, tOffsetMs}].
    Konwertujemy do prostych [{text, start}] kompatybilnych z _format_segments_as_vtt.

    Args:
        json3_text: Zawartość pliku .json3 z yt-dlp.

    Returns:
        Lista dictów [{text: str, start: float}] w sekundach.
    """
    try:
        data = json.loads(json3_text)
    except json.JSONDecodeError as e:
        log.error("Failed to parse json3: %s", e)
        return []

    events = data.get("events", [])
    segments = []

    for event in events:
        t_start_ms = event.get("tStartMs", 0)
        segs = event.get("segs", [])
        if not segs:
            continue

        # Składamy tekst z segmentów wewnątrz eventu
        parts = []
        for seg in segs:
            utf8_text = seg.get("utf8", "").replace("\n", " ").strip()
            if utf8_text:
                parts.append(utf8_text)

        full_text = " ".join(parts).strip()
        if not full_text:
            continue

        start_sec = t_start_ms / 1000.0
        segments.append({"text": full_text, "start": start_sec})

    log.debug("Parsed %d segments from json3", len(segments))
    return segments


def fetch_transcript_ytdlp(video_url: str) -> Optional[str]:
    """Pobiera transkrypt przez yt-dlp z cookies przeglądarki (PRIMARY strategy).

    CO: Używa yt-dlp --cookies-from-browser do autentykacji YouTube.
    Omija blokadę IP przez cookies z zalogowanej przeglądarki.

    PO CO:
    - youtube-transcript-api coraz częściej blokowane nawet na domowym IP
    - YouTube wymaga cookies ("Sign in to confirm you're not a bot")
    - yt-dlp + cookies z przeglądarki = najpewniejsza metoda

    Strategia przeglądarek (BROWSER_PRIORITY):
    firefox → chrome → edge → chromium

    Format wyjściowy: __VTT__ z markerami [MM:SS] — identyczny jak v2.

    Args:
        video_url: YouTube URL lub ID.

    Returns:
        String __VTT__ z timestampami lub None jeśli wszystkie metody zawiodły.
    """
    video_id = extract_video_id(video_url)
    if not video_id:
        log.error("Cannot extract video ID from: %s", video_url)
        return None

    # Próbuj kolejne przeglądarki
    for browser in BROWSER_PRIORITY:
        result = _try_ytdlp_with_browser(video_id, browser)
        if result is not None:
            return result
        log.debug("Browser %s failed, trying next", browser)

    log.warning("All browsers failed for yt-dlp, falling back to transcript-api")
    return None


_BROWSER_UA = {
    "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "edge": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0",
    "chromium": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
}


def _try_ytdlp_with_browser(video_id: str, browser: str) -> Optional[str]:
    """Próbuje pobrać transkrypt przez yt-dlp z konkretną przeglądarką.

    Args:
        video_id: YouTube video ID (11 znaków).
        browser: Nazwa przeglądarki (firefox, chrome, edge, chromium).

    Returns:
        String __VTT__ lub None jeśli się nie powiodło.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Najpierw próbujemy pobrać napisy ręczne (pl), potem auto-generated
        for lang_spec in ["pl", "en"]:
            json3_path = Path(tmpdir) / f"{video_id}.{lang_spec}.json3"

            cmd = [
                "yt-dlp",
                "--no-update",
                "--cookies-from-browser", browser,
                "--user-agent", _BROWSER_UA.get(browser, _BROWSER_UA["chrome"]),
                "--sleep-subtitles", "5",
                "--skip-download",
                "--write-sub",
                "--write-auto-sub",
                "--sub-lang", lang_spec,
                "--sub-format", "json3",
                "--output", str(Path(tmpdir) / f"{video_id}.%(ext)s"),
                url,
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if proc.returncode != 0:
                    stderr_short = proc.stderr[:300] if proc.stderr else ""
                    # Specyficzne błędy wskazujące że przeglądarka niedostępna
                    if any(x in stderr_short for x in [
                        "Could not copy", "Failed to extract", "No cookies"
                    ]):
                        log.debug(
                            "Browser %s cookies unavailable: %s",
                            browser, stderr_short[:100]
                        )
                        return None  # Ta przeglądarka niedostępna — stop próbowania
                    log.debug(
                        "yt-dlp %s lang=%s exit=%d: %s",
                        browser, lang_spec, proc.returncode, stderr_short[:100]
                    )
                    continue

                # Sprawdź czy plik json3 został pobrany
                if json3_path.exists():
                    json3_text = json3_path.read_text(encoding="utf-8")
                    segments = _parse_json3_to_segments(json3_text)
                    if segments:
                        vtt = _format_segments_as_vtt(segments)
                        log.info(
                            "yt-dlp OK: browser=%s lang=%s segments=%d chars=%d",
                            browser, lang_spec, len(segments), len(vtt)
                        )
                        return vtt
                    log.debug("json3 parsed but 0 segments for lang=%s", lang_spec)
                else:
                    log.debug(
                        "json3 file not found for lang=%s: %s", lang_spec, tmpdir
                    )

            except subprocess.TimeoutExpired:
                log.warning(
                    "yt-dlp timeout for browser=%s lang=%s", browser, lang_spec
                )
            except FileNotFoundError:
                log.error("yt-dlp not found — install: pip install yt-dlp")
                return None
            except Exception as e:
                log.error("yt-dlp unexpected error (browser=%s): %s", browser, e)

    return None


def fetch_transcript_api(video_url: str) -> Optional[str]:
    """Pobiera transkrypt przez youtube-transcript-api (FALLBACK strategy).

    CO: Bezpośrednie pobieranie transkryptu bez cookies.

    PO CO: Fallback gdy yt-dlp + cookies nie zadziałały.
    Może być blokowane przez YouTube IP ban — ale warto spróbować.

    ZMIANA v2.0 (2026-06-16): Wysyłamy transkrypt Z TIMESTAMPAMI
    (format __VTT__) zamiast plain text.

    Args:
        video_url: YouTube URL lub ID.

    Returns:
        String z prefixem __VTT__ i timestampami, lub None jeśli brak.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        log.error(
            "youtube-transcript-api not installed. "
            "Run: pip install youtube-transcript-api"
        )
        return None

    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError(f"Cannot extract video ID from: {video_url}")

    log.debug("Fetching transcript via transcript-api for video_id=%s", video_id)

    try:
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

        seg_dicts = []
        for s in segments:
            if hasattr(s, "text"):
                seg_dicts.append({"text": s.text, "start": getattr(s, "start", 0.0)})
            elif isinstance(s, dict):
                seg_dicts.append(s)

        vtt_text = _format_segments_as_vtt(seg_dicts)
        total_chars = len(vtt_text)
        log.info(
            "transcript-api OK: %d chars, %d segments",
            total_chars, len(seg_dicts)
        )
        return vtt_text if seg_dicts else None

    except Exception as e:
        log.warning("transcript-api failed: %s", str(e)[:200])
        return None


def fetch_transcript(video_url: str) -> Optional[str]:
    """Pobiera transkrypt YouTube — próbuje wszystkie metody po kolei.

    CO: Główna funkcja pobierania transkryptu z full fallback chain.

    Strategia (v3.1 — 2026-06-17):
    1. yt-dlp + firefox cookies (PRIMARY — najniezawodniejsze)
    2. yt-dlp + chrome cookies (fallback 1)
    3. yt-dlp + edge cookies (fallback 2)
    4. youtube-transcript-api bez cookies (last resort)

    Args:
        video_url: YouTube URL lub ID.

    Returns:
        String __VTT__ z timestampami lub None jeśli wszystko zawodzi.

    Raises:
        ValueError: Gdy URL nieparsowalne.
    """
    log.info("Fetching transcript for: %s", video_url)

    # FIRST: youtube-transcript-api (lekki, 0 ryzyka cookies)
    result = fetch_transcript_api(video_url)
    if result:
        return result
    
    # FALLBACK: yt-dlp + browser cookies (cięższy, ale pewniejszy)
    log.info("API failed — falling back to yt-dlp + cookies")
    result = fetch_transcript_ytdlp(video_url)
    if result:
        return result

    log.error("All transcript methods failed for: %s", video_url)
    return None


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
    log.info("VSE Local Transcript Runner started (v3.1 — yt-dlp+cookies)")
    log.info("API: %s", API_BASE)
    log.info("Poll interval: %ds", POLL_INTERVAL)
    log.info("Log dir: %s", LOG_DIR)
    log.info("Transcript strategy: transcript-api → yt-dlp+firefox → yt-dlp+chrome → yt-dlp+edge")
    log.info("=" * 60)

    while True:
        try:
            jobs = get_pending_jobs()
            if jobs:
                log.info("%d pending job(s) found", len(jobs))
                for job in jobs:
                    process_job(job)
                    delay = random.uniform(5, 15)
                    log.debug("Anti-burst delay: %.1fs", delay)
                    time.sleep(delay)
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
