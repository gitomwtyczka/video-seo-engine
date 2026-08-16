"""
library_matcher.py — dopasowanie lokalnych plików wideo do YouTube URL.

CO: Skanuje lokalną bibliotekę wideo i matchuje pliki do YouTube URL
    przez porównanie audio fingerprintów (Chromaprint).
PO CO: Klienci mają oryginalne pliki wideo (wyższa jakość niż YouTube).
    Zamiast ściągać skompresowane wideo z YT, użycz lokalnego pliku.
    Zero load na VPS, zero opóźnień pobierania.
JAK: fpcalc.exe generuje fingerprint → SQLite cache → porównanie z YT audio.

Dependencies: fpcalc.exe (Chromaprint binary na PATH lub w C:\\VSE\\tools\\)
              yt-dlp (pobieranie audio do porównania)
              sqlite3 (wbudowany w Python)
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Ścieżka do bazy SQLite z indexem biblioteki
DB_PATH = os.getenv(
    "LIBRARY_INDEX_DB",
    r"C:\ProgramData\VSELocalRunner\library_index.db",
)

# Obsługiwane rozszerzenia wideo
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".mts", ".m2ts", ".wmv"}

# Próg podobieństwa fingerprintów (0.0-1.0)
MATCH_THRESHOLD = 0.85

# Lock dla operacji na DB
_db_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Chromaprint helpers
# ---------------------------------------------------------------------------

def _find_fpcalc() -> Optional[str]:
    """Szuka fpcalc.exe na PATH lub w standardowych lokalizacjach."""
    import shutil
    # Sprawdź PATH
    if shutil.which("fpcalc"):
        return "fpcalc"
    # Sprawdź typowe lokalizacje
    candidates = [
        r"C:\VSE\tools\fpcalc.exe",
        r"C:\Program Files\Chromaprint\fpcalc.exe",
        r"C:\ProgramData\chocolatey\bin\fpcalc.exe",
        os.path.join(os.path.dirname(__file__), "fpcalc.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


FPCALC = _find_fpcalc()


def _get_fingerprint(media_path: str, duration_limit: int = 120) -> Optional[tuple[float, str]]:
    """
    Generuje fingerprint audio dla pliku wideo/audio.
    
    CO: Uruchamia fpcalc.exe na pliku i zwraca (duration, fingerprint).
    PO CO: Fingerprint to kompaktowa sygnatura dźwiękowa do porównywania.
    JAK: fpcalc analizuje pierwsze `duration_limit` sekund audio.
    
    Returns:
        Tuple (duration_sec, fingerprint_string) lub None jeśli błąd.
    """
    if not FPCALC:
        log.warning("fpcalc not found — library matching unavailable")
        return None
    try:
        cmd = [FPCALC, "-json", "-length", str(duration_limit), media_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            log.warning("fpcalc error for %s: %s", media_path, result.stderr[:200])
            return None
        data = json.loads(result.stdout)
        return float(data["duration"]), data["fingerprint"]
    except Exception as e:
        log.warning("fpcalc exception for %s: %s", media_path, e)
        return None


def _fingerprint_similarity(fp1: str, fp2: str) -> float:
    """
    Porównuje dwa fingerprinty Chromaprint.
    
    CO: Oblicza podobieństwo między dwoma fingerprint-ami (0.0-1.0).
    PO CO: Decyduje czy pliki zawierają tę samą ścieżkę dźwiękową.
    JAK: Chromaprint fingerprints są kompresowanymi int-ami.
         Dekodujemy i liczymy bit-overlap (Hamming similarity).
    """
    try:
        import base64
        import struct

        def decode_fp(fp: str) -> list[int]:
            # Chromaprint base64url → lista int32
            padded = fp + "=" * (4 - len(fp) % 4)
            raw = base64.urlsafe_b64decode(padded)
            # Pomiń 4-bajtowy nagłówek
            count = (len(raw) - 4) // 4
            return list(struct.unpack(f"<{count}i", raw[4:4 + count * 4]))

        ints1 = decode_fp(fp1)
        ints2 = decode_fp(fp2)
        
        # Porównaj na wspólnej długości
        length = min(len(ints1), len(ints2))
        if length == 0:
            return 0.0
        
        matches = sum(
            (32 - bin((a ^ b) & 0xFFFFFFFF).count("1")) / 32.0  # proporcja zgodnych bitów
            for a, b in zip(ints1[:length], ints2[:length])
        )
        return matches / length
    except Exception as e:
        log.warning("fingerprint_similarity error: %s", e)
        return 0.0


# ---------------------------------------------------------------------------
# SQLite Index
# ---------------------------------------------------------------------------

def _init_db(db_path: str) -> sqlite3.Connection:
    """Inicjalizuje bazę SQLite z tabelą index."""
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS library_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            filesize INTEGER,
            duration REAL,
            fingerprint TEXT NOT NULL,
            indexed_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_filename ON library_index(filename)")
    conn.commit()
    return conn


def index_library(library_dirs: list[str], force_reindex: bool = False) -> int:
    """
    Skanuje katalogi i buduje/aktualizuje fingerprint index.
    
    CO: Indeksuje wszystkie pliki wideo w podanych katalogach.
    PO CO: Buduje lokalną bazę fingerprintów do szybkiego matchowania.
    JAK: Iteruje pliki, generuje fingerprint przez fpcalc, zapisuje do SQLite.
    
    Returns:
        Liczba zaindeksowanych/zaktualizowanych plików.
    """
    if not FPCALC:
        log.warning("index_library: fpcalc not available, skipping")
        return 0
    
    with _db_lock:
        conn = _init_db(DB_PATH)
        indexed = 0
        
        for lib_dir in library_dirs:
            if not os.path.isdir(lib_dir):
                log.warning("index_library: directory not found: %s", lib_dir)
                continue
            
            for root, dirs, files in os.walk(lib_dir):
                for fname in files:
                    ext = Path(fname).suffix.lower()
                    if ext not in VIDEO_EXTENSIONS:
                        continue
                    
                    filepath = os.path.join(root, fname)
                    try:
                        filesize = os.path.getsize(filepath)
                    except OSError:
                        continue
                    
                    # Sprawdź czy już zaindeksowany i rozmiar się nie zmienił
                    if not force_reindex:
                        row = conn.execute(
                            "SELECT filesize FROM library_index WHERE filepath = ?",
                            (filepath,)
                        ).fetchone()
                        if row and row[0] == filesize:
                            log.debug("index_library: skip (cached) %s", fname)
                            continue
                    
                    log.info("index_library: indexing %s (%d MB)", fname, filesize // 1_000_000)
                    fp_result = _get_fingerprint(filepath)
                    if not fp_result:
                        continue
                    
                    duration, fingerprint = fp_result
                    conn.execute(
                        """INSERT OR REPLACE INTO library_index
                           (filepath, filename, filesize, duration, fingerprint)
                           VALUES (?, ?, ?, ?, ?)""",
                        (filepath, fname, filesize, duration, fingerprint)
                    )
                    conn.commit()
                    indexed += 1
                    log.info("index_library: indexed %s (%.1fs)", fname, duration)
        
        conn.close()
        return indexed


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _extract_yt_id(youtube_url: str) -> Optional[str]:
    """Ekstrahuje YouTube ID z różnych formatów URL."""
    m = re.search(r"(?:v=|youtu\.be/|/v/)([a-zA-Z0-9_-]{11})", youtube_url)
    return m.group(1) if m else None


def _download_yt_audio_sample(youtube_url: str, duration: int = 90) -> Optional[str]:
    """
    Pobiera krótki fragment audio z YouTube do porównania.
    
    CO: Pobiera tylko audio (nie wideo!) z YouTube, pierwsze `duration` sekund.
    PO CO: Porównanie fingerprintów bez pobierania całego pliku wideo.
           Audio mp3 90s to tylko ~1.5MB vs kilka GB dla full wideo.
    JAK: yt-dlp -x --audio-format mp3 --download-sections
    
    Returns:
        Ścieżka do tymczasowego pliku audio lub None jeśli błąd.
    """
    import shutil
    if not shutil.which("yt-dlp"):
        return None
    
    tmp_dir = tempfile.mkdtemp(prefix="vse_match_")
    tmp_audio = os.path.join(tmp_dir, "sample.%(ext)s")
    
    try:
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--download-sections", f"*0-{duration}",
            "--audio-quality", "5",  # niższa jakość = szybsze pobieranie
            "-o", tmp_audio,
            "--no-playlist",
            youtube_url,
        ]
        
        # Dodaj cookies jeśli dostępne
        cookies_path = r"C:\ProgramData\VSELocalRunner\yt_cookies.txt"
        if os.path.exists(cookies_path):
            cmd += ["--cookies", cookies_path]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            log.warning("yt audio sample failed: %s", result.stderr[:200])
            return None
        
        # Znajdź pobrany plik
        for f in os.listdir(tmp_dir):
            if f.startswith("sample."):
                return os.path.join(tmp_dir, f)
        return None
    except Exception as e:
        log.warning("download_yt_audio_sample error: %s", e)
        return None


def find_local_match(youtube_url: str) -> Optional[str]:
    """
    Szuka lokalnego pliku wideo pasującego do YouTube URL.
    
    CO: Główna funkcja matchowania — YouTube URL → lokalna ścieżka pliku.
    PO CO: Używa lokalnego pliku (wyższa jakość) zamiast pobierać z YT.
    JAK:
        1. Pobierz 90s audio z YT
        2. Wygeneruj fingerprint
        3. Porównaj z indexem SQLite
        4. Jeśli similarity > MATCH_THRESHOLD → zwraca ścieżkę
    
    Returns:
        Pełna ścieżka do lokalnego pliku lub None jeśli nie znaleziono.
    """
    if not FPCALC:
        log.debug("find_local_match: fpcalc unavailable, skipping")
        return None
    
    with _db_lock:
        conn = _init_db(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM library_index").fetchone()[0]
        if count == 0:
            log.debug("find_local_match: library index empty")
            conn.close()
            return None
        indexed_files = conn.execute(
            "SELECT filepath, fingerprint, duration FROM library_index"
        ).fetchall()
        conn.close()
    
    log.info("find_local_match: comparing against %d indexed files", len(indexed_files))
    
    # Pobierz audio sample z YT
    tmp_audio = _download_yt_audio_sample(youtube_url)
    if not tmp_audio:
        log.warning("find_local_match: could not download YT audio sample")
        return None
    
    try:
        yt_fp_result = _get_fingerprint(tmp_audio)
        if not yt_fp_result:
            return None
        _, yt_fingerprint = yt_fp_result
        
        # Porównaj z każdym plikiem w indexie
        best_match: Optional[str] = None
        best_score = 0.0
        
        for filepath, fingerprint, duration in indexed_files:
            if not os.path.exists(filepath):
                continue  # plik usunięty
            score = _fingerprint_similarity(yt_fingerprint, fingerprint)
            log.debug("find_local_match: %s score=%.3f", os.path.basename(filepath), score)
            if score > best_score:
                best_score = score
                best_match = filepath
        
        if best_score >= MATCH_THRESHOLD:
            log.info("find_local_match: MATCH %s (score=%.3f)", best_match, best_score)
            return best_match
        
        log.info("find_local_match: no match (best=%.3f < %.2f)", best_score, MATCH_THRESHOLD)
        return None
    finally:
        # Usuń tymczasowy plik audio
        try:
            import shutil as _shutil
            _shutil.rmtree(os.path.dirname(tmp_audio), ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Background Indexer Thread
# ---------------------------------------------------------------------------

def start_background_indexer(
    library_dirs: list[str],
    interval_seconds: int = 3600,  # Re-skanuj co godzinę
    stop_event=None,
) -> threading.Thread:
    """
    Uruchamia wątek tła który cyklicznie indeksuje bibliotekę.
    
    CO: Background thread skanujący LOCAL_VIDEO_LIBRARY.
    PO CO: Index jest zawsze aktualny bez ingerencji użytkownika.
    JAK: Indeksuje przy starcie, potem co `interval_seconds` sekund.
    """
    def _loop():
        log.info("[library_indexer] starting, dirs=%s", library_dirs)
        while True:
            try:
                n = index_library(library_dirs)
                log.info("[library_indexer] indexed %d files", n)
            except Exception as e:
                log.error("[library_indexer] error: %s", e)
            
            if stop_event and stop_event.wait(timeout=interval_seconds):
                break
            elif not stop_event:
                import time
                time.sleep(interval_seconds)
    
    t = threading.Thread(target=_loop, name="library_indexer", daemon=True)
    t.start()
    return t
