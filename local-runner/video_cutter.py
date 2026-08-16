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
import os
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


def _check_binary(name: str) -> bool:
    """Sprawdza czy binary jest dostępne na PATH."""
    return shutil.which(name) is not None


def check_dependencies() -> dict[str, bool]:
    """Sprawdza dostępność wymaganych binarów.
    
    CO: Weryfikuje yt-dlp i ffmpeg przy starcie worke-ra.
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
    cookies_path: str = r"C:\ProgramData\VSELocalRunner\yt_cookies.txt"


def cut_video(config: CutConfig) -> dict[str, str]:
    """Wycina i eksportuje wideo. Zwraca sścieżki wyeksportowanych plików.
    
    CO: Główna funkcja renderowania shorta.
    PO CO: Produkuje dwa pliki: surowy (dla edytora) i social (gotowy do publikacji).
    JAK:
        1. Pobierz/otwiórz źródło → temp_raw.mp4
        2. Eksport surowy: -c copy (zero re-encode, dla Premiere/FinalCut)
        3. Eksport social: libx264 veryfast + scale/crop do 9:16 lub 16:9
    
    Returns:
        Dict z kluczami: 'raw', 'social', opcjonalnie 'srt'
    """
    os.makedirs(config.output_dir, exist_ok=True)
    
    # Auto-nazwa z timestampem
    if not config.output_name:
        import time
        ts = int(time.time())
        config.output_name = f"short_{ts}"
    
    base = os.path.join(config.output_dir, config.output_name)
    temp_path = base + "_temp.mp4"
    raw_path = base + "_raw.mp4"
    social_path = base + "_social.mp4"
    
    result: dict[str, str] = {}
    
    try:
        # KROK 1: Pobierz/wytnij źródło do temp
        if config.source == "youtube":
            _download_yt_segment(config, temp_path)
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


def _download_yt_segment(config: CutConfig, output_path: str) -> None:
    """Pobiera fragment wideo z YouTube przez yt-dlp.
    
    CO: Pobiera tylko wymagany fragment (start_sec–end_sec), nie cały film.
    JAK: yt-dlp --download-sections + cookies z pliku lub przeglądarki.
    """
    start = config.start_sec
    end = config.end_sec
    
    cmd = [
        "yt-dlp",
        "--download-sections", f"*{start:.3f}-{end:.3f}",
        "--force-keyframes-at-cuts",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_path,
        "--no-playlist",
    ]
    
    # Cookies
    if os.path.exists(config.cookies_path):
        cmd += ["--cookies", config.cookies_path]
        log.info("[yt-dlp] using cookies file: %s", config.cookies_path)
    else:
        # Fallback: cookies z przeglądarki
        for browser in ["chrome", "firefox", "edge"]:
            cmd_test = cmd + ["--cookies-from-browser", browser, config.yt_url]
            log.info("[yt-dlp] trying browser cookies: %s", browser)
            result = subprocess.run(cmd_test, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                return
            log.warning("[yt-dlp] browser %s failed: %s", browser, result.stderr[:200])
        # Ostatnia próba bez cookies
        cmd.append(config.yt_url)
    
    if config.cookies_path in cmd:
        cmd.append(config.yt_url)
    
    log.info("[yt-dlp] cmd: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed (rc={result.returncode}): {result.stderr[:500]}")
    log.info("[yt-dlp] downloaded segment: %s", output_path)


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
    log.info("[ffmpeg] cut local: %.1f–%.1fs from %s", config.start_sec, config.end_sec, config.local_path)
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
        # Pionowy: scale do wysokości 1920, crop do szerokości 1080
        vf = "scale=-2:1920,crop=1080:1920"
    else:
        # Poziomy 16:9: scale do 1920x1080
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
