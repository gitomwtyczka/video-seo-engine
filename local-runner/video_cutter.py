"""
video_cutter.py — wycinanie i eksport wideo przez yt-dlp + FFmpeg.

Działa wyłącznie na lokalnym PC użytkownika (Windows Service).

CO: Wycina fragment wideo ze źródła (YouTube lub plik lokalny) i eksportuje
    dwa pliki: surowy (stream copy) i social (zakodowany 9:16 lub 16:9).
PO CO: ShortMachine — użytkownik zatwierdza kandydata, worker wycina i zapisuje.
JAK: yt-dlp --download-sections dla YT | ffmpeg -ss -to dla plików lokalnych.
    Dwa eksporty: -c copy (surowy, dla Premiere/FinalCut) + libx264 veryfast (social).

Dependencies: yt-dlp (binary on PATH), ffmpeg (binary on PATH)
"""
import logging
import re
import unicodedata
import os
import subprocess
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


def _check_binary(name: str) -> bool:
    """Sprawdza czy binary jest dostępne na PATH."""
    return shutil.which(name) is not None


def check_dependencies() -> dict[str, bool]:
    """Sprawdza dostępność wymaganych binarów.

    CO: Weryfikuje yt-dlp i ffmpeg przy starcie workera.
    PO CO: Wczesne wykrycie braku narzędzi przed próbą renderowania.

    Returns:
        Dict {narzędzie: czy_dostępne}
    """
    deps = {
        "yt-dlp": _check_binary("yt-dlp"),
        "ffmpeg": _check_binary("ffmpeg"),
    }
    for name, ok in deps.items():
        if ok:
            log.info("[deps] %s: OK", name)
        else:
            log.warning("[deps] %s: NOT FOUND on PATH — ShortMachine render will fail", name)
    return deps


def _make_slug(candidate_data, start_sec: float, end_sec: float, max_len: int = 45) -> str:
    """
    CO: Generuje czytelny slug nazwy pliku z tekstu hooka i zakresu czasu.
    PO CO: Nazwy plików muszą odzwierciedlać treść nagrań (nie timestampy).
    JAK: Normalizuje Unicode -> ASCII, usuwa znaki specjalne, skraca do max_len.
    """
    hook = ''
    if candidate_data:
        if isinstance(candidate_data, dict):
            hook = (candidate_data.get('hook_text') or candidate_data.get('hook')
                    or candidate_data.get('text') or candidate_data.get('title') or '')
        elif isinstance(candidate_data, str):
            hook = candidate_data
    if not hook:
        import time
        return f"short_{int(time.time())}"
    text = unicodedata.normalize('NFKD', hook)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', '_', text.strip()).strip('_')
    if len(text) > max_len:
        text = text[:max_len].rstrip('_')
    def fmt(sec: float) -> str:
        m, s = int(sec) // 60, int(sec) % 60
        return f"{m}m{s:02d}s"
    return f"{text}_{fmt(start_sec)}-{fmt(end_sec)}"


@dataclass
class CutConfig:
    """Konfiguracja renderowania jednego shorta."""
    source: str                        # 'youtube' | 'local'
    start_sec: float
    end_sec: float
    output_dir: str = r"C:\VSE\Shorts"
    output_name: str = ""              # auto-generowany jeśli pusty
    yt_url: str = ""
    local_path: str = ""               # pełna ścieżka na dysku Windows
    render_format: str = "9:16"        # '9:16' | '16:9'
    subtitles: str = "none"           # 'none' | 'srt'
    candidate_data: Optional[dict] = None   # dane kandydata z AI (hook_text, etc.)
    cookies_path: str = r"C:\ProgramData\VSELocalRunner\yt_cookies.txt"


def cut_video(config: CutConfig) -> dict[str, str]:
    """Wycina i eksportuje wideo. Zwraca ścieżki wyeksportowanych plików.

    CO: Główna funkcja renderowania shorta.
    PO CO: Produkuje dwa pliki: surowy (dla edytora) i social (gotowy do publikacji).
    JAK:
        1. Pobierz/otwórz źródło -> temp_raw.mp4
        2. Eksport surowy: -c copy (zero re-encode, dla Premiere/FinalCut)
        3. Eksport social: libx264 veryfast + scale/crop do 9:16 lub 16:9

    Returns:
        Dict z kluczami: 'raw', 'social', opcjonalnie 'srt'
    """
    os.makedirs(config.output_dir, exist_ok=True)

    # Auto-nazwa z hooka (czytelna) lub timestamp jako fallback
    if not config.output_name:
        config.output_name = _make_slug(config.candidate_data, config.start_sec, config.end_sec)

    base = os.path.join(config.output_dir, config.output_name)
    temp_path = base + "_temp.mp4"
    raw_path = base + "_raw.mp4"
    social_path = base + "_social.mp4"

    result: dict[str, str] = {}

    try:
        # KROK 1: Pobierz/wytnij źródło do temp
        if config.source == "youtube":
            ok = _download_fragment(config.yt_url, config.start_sec, config.end_sec, temp_path)
            if not ok:
                raise RuntimeError(f"Failed to download YouTube fragment: {config.yt_url}")
        elif config.source == "local":
            _cut_local_segment(config, temp_path)
        else:
            raise ValueError(f"Unknown source: {config.source!r}")

        # KROK 2: Eksport surowy (stream copy — bez re-encode)
        _export_raw(temp_path, raw_path)
        result["raw"] = raw_path
        log.info("[cut] raw export: %s", raw_path)

        # KROK 3: Eksport social (libx264 veryfast + format wideo)
        _export_social(temp_path, social_path, config.render_format)
        result["social"] = social_path
        log.info("[cut] social export: %s", social_path)

    finally:
        # Usuń temp
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return result


def _download_fragment(youtube_url: str, start_sec: float, end_sec: float, output_path: str) -> bool:
    """
    CO: Pobiera fragment wideo z YouTube.
    PO CO: Unika pobierania całego wideo (może mieć GB) gdy potrzebujemy kilkudziesięciu sekund.
    JAK: 3-stopniowy fallback:
      1. yt-dlp --download-sections (najszybszy, natywny)
      2. yt-dlp -g + ffmpeg ze streamu (bez pobierania)
      3. pełne pobranie + ffmpeg cut (fallback)
    """
    import subprocess, shutil, tempfile, os

    # Spróbuj dopasowania lokalnego pliku
    try:
        from library_matcher import find_local_match
        local_match = find_local_match(youtube_url)
        if local_match:
            log.info("[cut] Using local file: %s", local_match)
            config_copy = CutConfig(
                source='local',
                local_path=local_match,
                start_sec=start_sec,
                end_sec=end_sec,
                output_dir=os.path.dirname(output_path),
                output_name=os.path.splitext(os.path.basename(output_path))[0].replace('_temp', ''),
            )
            _cut_local_segment(config_copy, output_path)
            return True
    except Exception as e:
        log.warning("[cut] library_matcher error (falling back to yt-dlp): %s", e)

    buf_start = max(0, start_sec - 2)
    buf_end = end_sec + 2

    # --- METODA 1: --download-sections ---
    try:
        cmd = [
            "yt-dlp",
            "--download-sections", f"*{buf_start:.0f}-{buf_end:.0f}",
            "--force-keyframes-at-cuts",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o", output_path,
            youtube_url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(output_path):
            log.info("download_fragment: method=download-sections OK")
            return True
        log.warning("download_fragment: method=download-sections failed: %s", result.stderr[:200])
    except Exception as e:
        log.warning("download_fragment: method=download-sections error: %s", e)

    # --- METODA 2: direct stream URL via yt-dlp -g + ffmpeg ---
    try:
        cmd_url = ["yt-dlp", "-g", "--no-playlist",
                   "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                   youtube_url]
        result_url = subprocess.run(cmd_url, capture_output=True, text=True, timeout=30)
        if result_url.returncode == 0:
            urls = result_url.stdout.strip().split("\n")
            video_url = urls[0]
            audio_url = urls[1] if len(urls) > 1 else None

            if audio_url:
                cmd_ff = [
                    "ffmpeg", "-y",
                    "-ss", str(buf_start), "-to", str(buf_end),
                    "-i", video_url,
                    "-ss", str(buf_start), "-to", str(buf_end),
                    "-i", audio_url,
                    "-c:v", "libx264", "-c:a", "aac",
                    "-map", "0:v:0", "-map", "1:a:0",
                    output_path
                ]
            else:
                cmd_ff = [
                    "ffmpeg", "-y",
                    "-ss", str(buf_start), "-to", str(buf_end),
                    "-i", video_url,
                    "-c", "copy",
                    output_path
                ]
            result_ff = subprocess.run(cmd_ff, capture_output=True, text=True, timeout=180)
            if result_ff.returncode == 0 and os.path.exists(output_path):
                log.info("download_fragment: method=stream+ffmpeg OK")
                return True
            log.warning("download_fragment: method=stream+ffmpeg failed: %s", result_ff.stderr[:200])
    except Exception as e:
        log.warning("download_fragment: method=stream+ffmpeg error: %s", e)

    # --- METODA 3: fallback pełne pobranie + cut ---
    try:
        log.warning("download_fragment: falling back to full download")
        tmp_dir = tempfile.mkdtemp()
        tmp_video = os.path.join(tmp_dir, "full.mp4")

        cmd_dl = ["yt-dlp", "-f", "best[ext=mp4]/best", "-o", tmp_video, youtube_url]
        result_dl = subprocess.run(cmd_dl, capture_output=True, text=True, timeout=600)
        if result_dl.returncode != 0:
            log.error("download_fragment: full download failed: %s", result_dl.stderr[:200])
            return False

        cmd_cut = [
            "ffmpeg", "-y",
            "-ss", str(start_sec), "-to", str(end_sec),
            "-i", tmp_video,
            "-c", "copy",
            output_path
        ]
        result_cut = subprocess.run(cmd_cut, capture_output=True, text=True, timeout=60)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if result_cut.returncode == 0 and os.path.exists(output_path):
            log.info("download_fragment: method=full+cut OK")
            return True
    except Exception as e:
        log.error("download_fragment: full download error: %s", e)

    return False


def _cut_local_segment(config: CutConfig, output_path: str) -> None:
    """Wycina fragment z lokalnego pliku przez FFmpeg."""
    if not os.path.exists(config.local_path):
        raise FileNotFoundError(f"Local video not found: {config.local_path!r}")

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(config.start_sec),
        "-to", str(config.end_sec),
        "-i", config.local_path,
        "-c", "copy",
        output_path,
    ]
    log.info("[ffmpeg] cut local: %.1f-%.1fs from %s", config.start_sec, config.end_sec, config.local_path)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg cut failed: {result.stderr[:500]}")


def _export_raw(input_path: str, output_path: str) -> None:
    """Eksport surowy — stream copy, zero re-encode (dla Premiere/FinalCut)."""
    cmd = ["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg raw export failed: {result.stderr[:500]}")


def _export_social(input_path: str, output_path: str, render_format: str = "9:16") -> None:
    """Eksport social — libx264 veryfast + scale/crop do formatu pionowego lub poziomego.

    CO: Koduje wideo pod publikację social media.
    PO CO: Gotowy plik .mp4 do wgrania na TikTok/Shorts/Reels (9:16) lub YT (16:9).
    JAK: libx264 veryfast crf23 — wysoka jakość, czas ~2-3s dla klipu 45s.
    """
    if render_format == "9:16":
        vf = "scale=-2:1920,crop=1080:1920"
    else:
        vf = "scale=1920:-2,crop=1920:1080"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-vf", vf,
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]
    log.info("[ffmpeg] social export (%s): %s", render_format, output_path)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg social export failed: {result.stderr[:500]}")
