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

Log: %ProgramData%\\VSELocalRunner\\runner.log (lub stdout w trybie dev)

## Format transkryptu (VTT-like)

Od v2.0 runner wysyła transkrypt Z TIMESTAMPAMI w formacie:
  __VTT__\n[MM:SS] tekst\n[MM:SS] tekst...\n

To pozwala pipeline.py zamienić segmenty na prawdziwy plik .vtt który
generator.py parsuje do anchor-matching rozdziałów. Bez timestampów
generator nie może wyciągnąć rzeczywistych czasów → rozdziały = 0.

## Strategia pobierania transkryptu (v3.3 — 2026-06-18)

YouTube blokuje requesty bez cookies. Serwis Windows działa jako LocalSystem,
które nie ma profilu przeglądarki — dlatego --cookies-from-browser failuje.

Rozwiązanie: dual-strategy cookies.

Aktualna strategia (primary → fallback):
1. yt-dlp --cookies COOKIES_FILE       ← PRIMARY (plik eksportowany przez Task Scheduler)
2. yt-dlp --cookies-from-browser ...  ← fallback (gdy serwis NIE jest LocalSystem)
3. youtube-transcript-api             ← last resort

COOKIES_FILE odnawiany przez Task Scheduler (export_cookies.bat) jako zalogowany user.
Plik w C:\\ProgramData\\VSELocalRunner\\yt_cookies.txt (dostepny dla LocalSystem).
"""
import glob
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import random
import threading
from pathlib import Path
from typing import Optional, Tuple

# ShortMachine imports
try:
    from video_cutter import CutConfig, cut_video, check_dependencies
    _VIDEO_CUTTER_OK = True
except ImportError:
    _VIDEO_CUTTER_OK = False

# Global stop event for loops
_stop_requested = threading.Event()


# Fix UnicodeEncodeError w Windows Service (cp1250 nie obsluguje strzalek Unicode)
# Musi byc przed inicjalizacja loggera
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

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

# Plik cookies eksportowany przez Task Scheduler jako zalogowany użytkownik
# Domyślna lokalizacja — tak samo jak LOG_DIR
COOKIES_FILE = os.getenv("COOKIES_FILE", r"C:\ProgramData\VSELocalRunner\yt_cookies.txt")

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

if _VIDEO_CUTTER_OK:
    deps = check_dependencies()
    if not deps.get("ffmpeg"):
        log.warning("ffmpeg not found — ShortMachine rendering will be unavailable")

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
    """Konwertuje segmenty do formatu VTT-like z markerami [MM:SS].

    CO: Zamienia listę [{text, start}] na wieloliniowy string
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
        segments: Lista dictów z polami: text (str), start (float).

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


def _parse_webvtt_to_segments(vtt_text: str) -> list:
    """Parsuje WebVTT string (z yt-dlp) do listy segmentów [{text, start}].

    CO: WebVTT z yt-dlp zawiera cue'y w formacie:
        00:00:01.000 --> 00:00:04.000
        tekst

    Konwertujemy do [{text: str, start: float}] kompatybilnych z _format_segments_as_vtt.

    Fix v3.2: zamiennik dla _parse_json3_to_segments — yt-dlp zapisuje VTT
    niezależnie od tego czy to ręczne czy auto-generated napisy.

    Args:
        vtt_text: Zawartość pliku .vtt z yt-dlp.

    Returns:
        Lista dictów [{text: str, start: float}] w sekundach.
    """
    segments = []
    # Pattern: HH:MM:SS.mmm --> HH:MM:SS.mmm
    cue_pattern = re.compile(
        r'(\d{2}):(\d{2}):(\d{2})\.\d+ --> \d{2}:\d{2}:\d{2}\.\d+'
    )

    lines = vtt_text.splitlines()
    i = 0
    while i < len(lines):
        m = cue_pattern.match(lines[i].strip())
        if m:
            h, mn, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            start_sec = h * 3600 + mn * 60 + s
            # Zbierz linie tekstu po timestampie
            text_parts = []
            i += 1
            while i < len(lines) and lines[i].strip() and not cue_pattern.match(lines[i].strip()):
                # Pomijamy linie z <c> (color tags) i numer cue
                clean = re.sub(r'<[^>]+>', '', lines[i]).strip()
                if clean and not clean.isdigit():
                    text_parts.append(clean)
                i += 1
            text = " ".join(text_parts).strip()
            if text:
                segments.append({"text": text, "start": float(start_sec)})
        else:
            i += 1

    log.debug("Parsed %d segments from WebVTT", len(segments))
    return segments


def _get_segments_duration(segments: list) -> float:
    """Zwraca czas ostatniego segmentu w sekundach."""
    if not segments:
        return 0.0
    last = max(segments, key=lambda s: s.get("start", 0.0))
    return float(last.get("start", 0.0))

def fetch_transcript_ytdlp(video_url: str) -> Optional[str]:
    """Pobiera transkrypt przez yt-dlp z cookies (PRIMARY strategy v3.3).

    CO: Dual-strategy cookies:
    1. Plik cookies (COOKIES_FILE) — eksportowany przez Task Scheduler jako user.
       Działa gdy serwis = LocalSystem (brak profilu przeglądarki).
    2. --cookies-from-browser — fallback gdy plik nie istnieje.

    PO CO: Serwis Windows (LocalSystem) nie ma dostępu do profili przeglądarek.
    Plik cookies jest eksportowany przez oddzielny Task Scheduler task (jako user)
    i zapisywany w miejscu dostępnym dla LocalSystem.

    Args:
        video_url: YouTube URL lub ID.

    Returns:
        String __VTT__ z timestampami lub None jeśli wszystkie metody zawiodły.
    """
    video_id = extract_video_id(video_url)
    if not video_id:
        log.error("Cannot extract video ID from: %s", video_url)
        return None

    # STRATEGY 1: Plik cookies (działa dla LocalSystem)
    cookies_file = Path(COOKIES_FILE)
    if cookies_file.exists() and cookies_file.stat().st_size > 100:
        log.info("Using cookies file: %s (%d bytes)", COOKIES_FILE, cookies_file.stat().st_size)
        result = _try_ytdlp_with_cookies_file(video_id, str(cookies_file))
        if result is not None:
            return result
        log.warning("Cookies file failed — trying browser cookies fallback")
    else:
        log.info("Cookies file not found or empty: %s — trying browser cookies", COOKIES_FILE)

    # STRATEGY 2: --cookies-from-browser (działa gdy runner uruchomiony jako user)
    for browser in BROWSER_PRIORITY:
        result = _try_ytdlp_with_browser(video_id, browser)
        if result is not None:
            return result
        log.debug("Browser %s failed, trying next", browser)

    log.warning("All yt-dlp cookie strategies failed")
    return None


def _try_ytdlp_with_cookies_file(video_id: str, cookies_path: str) -> Optional[str]:
    """Próbuje pobrać transkrypt przez yt-dlp z plikiem cookies (Netscape format).

    CO: Używa --cookies FILE zamiast --cookies-from-browser.
    Działa dla każdego konta serwisu (LocalSystem, NetworkService itd.)
    bo plik jest dostępny w C:\\ProgramData.

    Args:
        video_id: YouTube video ID.
        cookies_path: Ŝieżka do pliku cookies (Netscape format).

    Returns:
        String __VTT__ lub None.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        for lang_spec in ["pl", "en"]:
            cmd = [
                "yt-dlp",
                "--no-update",
                "--cookies", cookies_path,
                "--skip-download",
                "--write-sub",
                "--write-auto-sub",
                "--sub-lang", lang_spec,
                "--sub-format", "vtt",
                "--extractor-args", "youtube:player_client=tv_embedded",
                "--no-part",
                "--retries", "10",
                "--fragment-retries", "10",
                "--output", str(Path(tmpdir) / f"{video_id}.%(ext)s"),
                url,
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                vtt_files = glob.glob(str(Path(tmpdir) / f"{video_id}*.vtt"))
                if vtt_files:
                    vtt_text = Path(vtt_files[0]).read_text(encoding="utf-8")
                    segments = _parse_webvtt_to_segments(vtt_text)
                    if segments:
                        seg_duration = _get_segments_duration(segments)
                        log.info(
                            "VTT coverage: last segment at %.0fs (%dm %02ds) — %d segments",
                            seg_duration, int(seg_duration // 60), int(seg_duration % 60), len(segments)
                        )
                        vtt_out = _format_segments_as_vtt(segments)
                        log.info(
                            "yt-dlp+cookies_file OK: lang=%s file=%s segments=%d chars=%d",
                            lang_spec, Path(vtt_files[0]).name, len(segments), len(vtt_out)
                        )
                        return vtt_out
                    log.debug("VTT parsed 0 segments for lang=%s", lang_spec)
                else:
                    log.debug(
                        "cookies_file: No VTT for lang=%s exit=%d stderr=%s",
                        lang_spec, proc.returncode, proc.stderr[:150] if proc.stderr else ""
                    )

            except subprocess.TimeoutExpired:
                log.warning("yt-dlp+cookies_file timeout lang=%s", lang_spec)
            except FileNotFoundError:
                log.error("yt-dlp not found")
                return None
            except Exception as e:
                log.error("yt-dlp+cookies_file error: %s", e)

    return None


_BROWSER_UA = {
    "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "edge": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0",
    "chromium": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
}


def _try_ytdlp_with_browser(video_id: str, browser: str) -> Optional[str]:
    """Próbuje pobrać transkrypt przez yt-dlp z konkretną przeglądarką.

    Fix v3.2: używa formatu 'vtt' zamiast 'json3' (json3 był niekompatybilny
    z yt-dlp --write-auto-sub — plik zapisywany pod inną nazwą niż oczekiwana).
    Używa glob do znalezienia pliku VTT niezależnie od sufiksu (-auto itp).

    Args:
        video_id: YouTube video ID (11 znaków).
        browser: Nazwa przeglądarki (firefox, chrome, edge, chromium).

    Returns:
        String __VTT__ lub None jeśli się nie powiodło.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        for lang_spec in ["pl", "en"]:
            cmd = [
                "yt-dlp",
                "--no-update",
                "--cookies-from-browser", browser,
                "--user-agent", _BROWSER_UA.get(browser, _BROWSER_UA["chrome"]),
                "--skip-download",
                "--write-sub",
                "--write-auto-sub",
                "--sub-lang", lang_spec,
                "--sub-format", "vtt",
                "--extractor-args", "youtube:player_client=tv_embedded",
                "--no-part",
                "--retries", "10",
                "--fragment-retries", "10",
                "--output", str(Path(tmpdir) / f"{video_id}.%(ext)s"),
                url,
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if proc.returncode != 0:
                    stderr_short = proc.stderr[:300] if proc.stderr else ""
                    # Specyficzne błędy wskazujące że przeglądarka niedostępna
                    if any(x in stderr_short for x in [
                        "Could not copy", "Failed to extract", "No cookies",
                        "Cookies from browser",
                    ]):
                        log.debug(
                            "Browser %s cookies unavailable: %s",
                            browser, stderr_short[:150]
                        )
                        return None  # Ta przeglądarka niedostępna — stop próbowania
                    log.debug(
                        "yt-dlp %s lang=%s exit=%d: %s",
                        browser, lang_spec, proc.returncode, stderr_short[:150]
                    )
                    # Kontynuuj — może inny lang zadziała

                # Fix v3.2: glob zamiast hardcoded path
                # yt-dlp może zapisać jako: {id}.pl.vtt, {id}.pl-auto.vtt itp.
                vtt_files = glob.glob(str(Path(tmpdir) / f"{video_id}*.vtt"))
                if vtt_files:
                    vtt_path = vtt_files[0]  # bierz pierwszy znaleziony
                    vtt_text = Path(vtt_path).read_text(encoding="utf-8")
                    segments = _parse_webvtt_to_segments(vtt_text)
                    if segments:
                        seg_duration = _get_segments_duration(segments)
                        log.info(
                            "VTT coverage: last segment at %.0fs (%dm %02ds) — %d segments",
                            seg_duration, int(seg_duration // 60), int(seg_duration % 60), len(segments)
                        )
                        vtt_out = _format_segments_as_vtt(segments)
                        log.info(
                            "yt-dlp OK: browser=%s lang=%s file=%s segments=%d chars=%d",
                            browser, lang_spec,
                            Path(vtt_path).name,
                            len(segments), len(vtt_out)
                        )
                        return vtt_out
                    log.debug("VTT parsed but 0 segments for lang=%s (file=%s)",
                              lang_spec, Path(vtt_path).name)
                else:
                    log.debug(
                        "No VTT file found for lang=%s in tmpdir=%s stdout=%s",
                        lang_spec, tmpdir, proc.stdout[:100] if proc.stdout else ""
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

    Strategia (v3.2 — 2026-06-18):
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

    # PRIMARY: yt-dlp + browser cookies
    result = fetch_transcript_ytdlp(video_url)
    if result:
        return result

    # LAST RESORT: youtube-transcript-api bez cookies
    log.info("yt-dlp failed — trying transcript-api as last resort")
    result = fetch_transcript_api(video_url)
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
# ShortMachine Jobs Processing
# ---------------------------------------------------------------------------

def _submit_short_result(job_id: str, status: str, result_paths: dict = None, error: str = None) -> None:
    """Raportuje wynik zadania ShortMachine do VSE API."""
    payload = {"status": status}
    if result_paths:
        payload["result_paths"] = result_paths
    if error:
        payload["error"] = error
    
    url = f"{API_BASE}/v1/shorts/{job_id}/result"
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[shorts] Failed to submit result for %s: %s", job_id, e)


def _process_short_job(job: dict) -> None:
    """Przetwarza jedno zadanie wycinania shorta."""
    job_id = job["id"]
    log.info("[shorts] Processing short job %s", job_id)
    
    render_config = job.get("render_config", {})
    
    source = "youtube" if job.get("youtube_url") else "local"
    
    config = CutConfig(
        source=source,
        start_sec=float(job["start_sec"]),
        end_sec=float(job["end_sec"]),
        yt_url=job.get("youtube_url", ""),
        local_path=job.get("local_path", ""),
        output_dir=render_config.get("output_dir", r"C:\VSE\Shorts"),
        render_format=render_config.get("format", "9:16"),
        subtitles=render_config.get("subtitles", "none"),
    )
    
    try:
        result_paths = cut_video(config)
        _submit_short_result(job_id, status="done", result_paths=result_paths)
        log.info("[shorts] Job %s done: %s", job_id, result_paths)
    except Exception as e:
        log.error("[shorts] Job %s failed: %s", job_id, e, exc_info=True)
        _submit_short_result(job_id, status="error", error=str(e))


def _short_jobs_loop() -> None:
    """Wątek pollingu dla zadań ShortMachine."""
    if not _VIDEO_CUTTER_OK:
        log.warning("[shorts_loop] video_cutter unavailable — loop disabled")
        return
    
    log.info("[shorts_loop] starting")
    while not _stop_requested.is_set():
        try:
            url = f"{API_BASE}/v1/shorts/pending"
            resp = requests.get(url, headers=_headers(), timeout=15)
            if resp.status_code == 429:
                log.warning("[shorts_loop] rate limited, waiting 60s")
                _stop_requested.wait(60)
                continue
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobs", [])
            if jobs:
                log.info("[shorts_loop] %d short job(s) pending", len(jobs))
                for job in jobs:
                    if _stop_requested.is_set():
                        break
                    _process_short_job(job)
        except Exception as e:
            log.error("[shorts_loop] error: %s", e)
        
        _stop_requested.wait(5)  # Polling co 5 sekund
    
    log.info("[shorts_loop] stopped")


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
    log.info("VSE Local Transcript Runner started (v3.3 — cookies_file+browser fallback)")
    log.info("API: %s", API_BASE)
    log.info("Poll interval: %ds", POLL_INTERVAL)
    log.info("Log dir: %s", LOG_DIR)
    log.info("Cookies file: %s (exists=%s)", COOKIES_FILE, Path(COOKIES_FILE).exists())
    log.info("Transcript strategy: cookies_file -> yt-dlp+browser -> transcript-api")
    log.info("=" * 60)

    # Start ShortMachine worker thread
    shorts_thread = threading.Thread(target=_short_jobs_loop, name="shorts_loop", daemon=True)
    shorts_thread.start()

    # Library indexer (background)
    try:
        from library_matcher import start_background_indexer, FPCALC
        FPCALC_AVAILABLE = FPCALC is not None
    except ImportError:
        FPCALC_AVAILABLE = False

    default_library = r"C:\Users\tomas2\Videos"
    library_dirs_raw = os.getenv("LOCAL_VIDEO_LIBRARY", default_library)
    library_dirs = [d.strip() for d in library_dirs_raw.split(";") if d.strip()]
    if library_dirs and FPCALC_AVAILABLE:  # sprawdz czy fpcalc jest dostępny
        start_background_indexer(library_dirs, stop_event=_stop_requested)
        log.info("Library indexer started for: %s", library_dirs)
    else:
        log.info("Library indexer: LOCAL_VIDEO_LIBRARY not set or fpcalc unavailable, skipping")

    while not _stop_requested.is_set():
        try:
            jobs = get_pending_jobs()
            if jobs:
                log.info("%d pending job(s) found", len(jobs))
                for job in jobs:
                    if _stop_requested.is_set():
                        break
                    process_job(job)
                    delay = random.uniform(5, 15)
                    log.debug("Anti-burst delay: %.1fs", delay)
                    _stop_requested.wait(delay)
            else:
                log.debug("No pending jobs")

        except KeyboardInterrupt:
            log.info("KeyboardInterrupt — stopping VSE Local Runner")
            _stop_requested.set()
            break
        except Exception as e:
            log.error("Unexpected error in main loop: %s", e, exc_info=True)

        _stop_requested.wait(POLL_INTERVAL)


if __name__ == "__main__":
    main()
