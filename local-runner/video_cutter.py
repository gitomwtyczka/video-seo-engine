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
import json
import re
import unicodedata
import os
import subprocess
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

OVERRIDES_PATH = r"C:\ProgramData\VSELocalRunner\local_overrides.json"


def _load_local_overrides() -> dict:
    """
    CO: Wczytuje manualne mapowanie YouTube ID → ścieżka lokalna.
    PO CO: Pozwala renderować wideo prywatne lub gdy automatyczne dopasowanie
           (fingerprint) nie działa — np. plik nie ma ID YouTube w nazwie.
    JAK: Czyta JSON z OVERRIDES_PATH.
         Format: {"YOUTUBE_ID": "C:\\ścieżka\\do\\pliku.mp4"}
         Plik edytowalny przez użytkownika ręcznie lub przez UI.
    """
    if not os.path.exists(OVERRIDES_PATH):
        return {}
    try:
        with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.warning("[cut] local_overrides.json load error: %s", e)
        return {}


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


def _generate_srt(vtt_segments: list, clip_start_sec: float, clip_end_sec: float, single_line: bool = False) -> str:
    """
    CO: Generuje plik SRT z dynamicznymi napisami karaoke (słowa narastają na ekranie).
    PO CO: Efekt karaoke (YouTube Shorts / TikTok) — słowa pojawiają się po kolei,
           max 3 słowa na linię, max 2 linie na ekran (6 słów), potem czyszczenie ekranu.
    JAK: Obsługuje format 'ts' (core/shorts.py) i 'start'/'end' (ogólny VTT).
         1. Filtruje segmenty w oknie klipu i przelicza na czas względny.
         2. Usuwa overlapy czasowe między segmentami i deduplikuje tekst sliding window.
         3. Spłaszcza segmenty do listy słów z timingiem (proporcjonalny podział).
         4. Grupuje krótkie słowa (< 0.35s) w kroki (steps).
         5. Grupuje kroki w ekrany (screens, max 6 słów) i buduje narastające wpisy SRT.
         6. Formatuje do standardu SRT.
    """
    def to_srt_ts(sec: float) -> str:
        sec = max(0.0, sec)
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int(round((sec % 1) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _clean_speech_text(text: str) -> str:
        """Czyści tekst mowy z fillerów i powtórzeń (YouTube auto-captions)."""
        import re

        # 1. Usuń fillery: słowa składające się tylko z liter y/e (np. y, yy, yyy, yyyy, ee, eee)
        text = re.sub(r'(?<![\w])[yeYE]+(?![\w])', '', text)

        # 2. Usuń powtórzenia kolejnych identycznych słów (tak tak → tak, no no → no)
        # Obsługuje 2+ powtórzeń, case-insensitive
        text = re.sub(r'\b(\w+)(\s+\1)+\b', r'\1', text, flags=re.IGNORECASE)

        # 3. Wyczyść wielokrotne spacje (po usunięciach mogą powstać)
        text = re.sub(r' +', ' ', text).strip()

        # 4. Usuń wiodące przecinki i spacje (jeśli filler był na początku: ", słowo")
        text = re.sub(r'^[\s,\.]+', '', text).strip()

        return text

    # Deduplikacja sliding window YouTube auto-captions
    def _remove_text_overlap(prev_text: str, curr_text: str) -> str:
        """Usuwa prefix curr_text który pokrywa się z końcem prev_text (YouTube sliding window)."""
        prev_words = prev_text.split()
        curr_words = curr_text.split()
        max_check = min(len(prev_words), len(curr_words), 20)  # max 20 słów overlap
        for n in range(max_check, 2, -1):  # min 3 słowa overlap żeby nie być agresywnym
            if prev_words[-n:] == curr_words[:n]:
                return " ".join(curr_words[n:]).strip()
        return curr_text

    def _flush_screen(steps: list, all_chunks: list, words_per_line: int, gap: float, single_line: bool = False) -> None:
        """
        Generuje narastające wpisy SRT dla jednego ekranu.
        Każdy step dodaje słowa do wyświetlanego tekstu.
        """
        if not steps:
            return
        accumulated_words = []
        for j, step in enumerate(steps):
            accumulated_words.extend(step['words'])

            # Formatuj tekst: podział na linie
            if single_line:
                text = ' '.join(accumulated_words)  # całość w jednej linii
            else:
                line1 = ' '.join(accumulated_words[:words_per_line])
                line2_words = accumulated_words[words_per_line:]
                text = line1
                if line2_words:
                    text = line1 + '\n' + ' '.join(line2_words)

            # Timing: od startu tego step do startu następnego
            start = step['start']
            if j + 1 < len(steps):
                end = steps[j + 1]['start']  # zero gap — płynne przejście między słowami
            else:
                end = step['end']

            if end - start < 0.1:
                end = start + 0.15  # minimum widoczności

            all_chunks.append({
                'text': text,
                'rel_start': start,
                'rel_end': end
            })

        # Przerwa SCREEN_GAP po ostatnim wpisie — obsluży się przez gap między screenami
        if all_chunks:
            all_chunks[-1]['rel_end'] = steps[-1]['end'] - gap

    clip_duration = clip_end_sec - clip_start_sec
    if clip_duration <= 0 or not vtt_segments:
        return ""

    # FAZA 1: Zbierz segmenty w oknie klipu (filtrowanie)
    raw_segments = []
    for seg in vtt_segments:
        # Obsługa obu formatów: 'ts' (core/shorts.py) i 'start' (ogólny VTT)
        seg_start = seg.get('start') if seg.get('start') is not None else seg.get('ts', 0.0)
        seg_end = seg.get('end') if seg.get('end') is not None else (seg_start + 3.0)

        # Przesuń względem startu klipu
        rel_start = seg_start - clip_start_sec
        rel_end = seg_end - clip_start_sec

        # Pomiń segmenty spoza zakresu klipu
        if rel_end <= 0:
            continue
        if rel_start >= clip_duration:
            break

        rel_start = max(0.0, rel_start)
        rel_end = min(rel_end, clip_duration)
        text = seg.get('text', '').strip()
        if not text:
            continue

        raw_segments.append({
            'rel_start': rel_start,
            'rel_end': rel_end,
            'text': text
        })

    if not raw_segments:
        return ""

    # FAZA 2: Fix overlapów + deduplikacja tekstu
    clean_segments = []
    prev_seg_text = ""
    for i, seg in enumerate(raw_segments):
        rel_start = seg['rel_start']
        rel_end = seg['rel_end']

        # End nie może przekraczać startu następnego segmentu (eliminacja overlapów)
        if i + 1 < len(raw_segments):
            next_rel_start = raw_segments[i + 1]['rel_start']
            if next_rel_start > rel_start:
                rel_end = min(rel_end, next_rel_start)
            else:
                rel_end = max(rel_start + 0.1, rel_end)

        text = seg['text']
        # Usuń overlap z poprzednim segmentem (YouTube sliding window)
        if prev_seg_text:
            text = _remove_text_overlap(prev_seg_text, text)
        if not text:
            continue
        prev_seg_text = text

        clean_segments.append({
            'rel_start': rel_start,
            'rel_end': max(rel_start + 0.1, rel_end),
            'text': text
        })

    # PARAMETRY
    WORDS_PER_LINE = 3      # słowa per linia
    LINES_PER_SCREEN = 2    # linie per screen (potem clear)
    WORDS_PER_SCREEN = 6    # = WORDS_PER_LINE * LINES_PER_SCREEN
    MIN_WORD_DURATION = 0.35  # jeśli słowo krótsze — połącz z następnym w jeden step
    SCREEN_GAP = 0.05       # przerwa między screenami (s)

    # FAZA 3A: Spłaszcz segmenty do listy słów z timing
    word_timing = []  # lista {'word': str, 'start': float, 'end': float}
    for seg in clean_segments:
        # NOWE: Oczyść tekst z fillerów i powtórzeń
        cleaned_text = _clean_speech_text(seg['text'])
        words = cleaned_text.split()
        if not words:
            continue
        seg_dur = max(0.1, seg['rel_end'] - seg['rel_start'])
        word_dur = seg_dur / len(words)
        for i, word in enumerate(words):
            word_timing.append({
                'word': word,
                'start': seg['rel_start'] + i * word_dur,
                'end': seg['rel_start'] + (i + 1) * word_dur
            })

    # FAZA 3B: Grupuj słowa w steps (1 lub 2 słowa gdy szybko)
    steps = []  # lista {'words': [str], 'start': float, 'end': float}
    i = 0
    while i < len(word_timing):
        w = word_timing[i]
        if w['end'] - w['start'] < MIN_WORD_DURATION and i + 1 < len(word_timing):
            # Połącz z następnym
            w2 = word_timing[i + 1]
            steps.append({'words': [w['word'], w2['word']], 'start': w['start'], 'end': w2['end']})
            i += 2
        else:
            steps.append({'words': [w['word']], 'start': w['start'], 'end': w['end']})
            i += 1

    # FAZA 3C: Grupuj steps w screens po WORDS_PER_SCREEN słów
    all_chunks = []
    screen_steps = []
    screen_word_count = 0

    for step in steps:
        screen_steps.append(step)
        screen_word_count += len(step['words'])
        if screen_word_count >= WORDS_PER_SCREEN:
            # Flush screen — generuj narastające wpisy SRT
            _flush_screen(screen_steps, all_chunks, WORDS_PER_LINE, SCREEN_GAP, single_line)
            screen_steps = []
            screen_word_count = 0

    # Ostatni niepełny screen
    if screen_steps:
        _flush_screen(screen_steps, all_chunks, WORDS_PER_LINE, SCREEN_GAP, single_line)

    # FAZA 4: Generuj linie SRT z chunków
    lines = []
    idx = 1
    for chunk in all_chunks:
        lines.append(str(idx))
        lines.append(f"{to_srt_ts(chunk['rel_start'])} --> {to_srt_ts(chunk['rel_end'])}")
        lines.append(chunk['text'])
        lines.append('')
        idx += 1

    return '\n'.join(lines)


def cut_video(config: CutConfig) -> dict[str, str]:
    """Wycina i eksportuje wideo. Zwraca ścieżki wyeksportowanych plików.

    CO: Główna funkcja renderowania shorta.
    PO CO: Produkuje dwa pliki: surowy (dla edytora) i social (gotowy do publikacji).
          Opcjonalnie plik .srt z napisami (do importu w edytorze lub uploadu).
    JAK:
        1. Pobierz/otwórz źródło -> temp_raw.mp4
        2. Generuj .srt jeśli subtitles='srt'
        3. Eksport surowy: -c copy (zero re-encode, dla Premiere/FinalCut)
        4. Eksport social: libx264 veryfast + scale/crop do 9:16 lub 16:9

    Returns:
        Dict z kluczami: 'raw', 'social', opcjonalnie 'srt'
    """
    os.makedirs(config.output_dir, exist_ok=True)

    # Auto-nazwa z hooka (czytelna) lub timestamp jako fallback
    if not config.output_name:
        config.output_name = _make_slug(config.candidate_data, config.start_sec, config.end_sec)

    result: dict[str, str] = {}

    # Generuj SRT jeśli subtitles='srt' i są segmenty
    if config.subtitles == 'srt' and config.candidate_data:
        vtt_segs = config.candidate_data.get('vtt_segments', [])
        if vtt_segs:
            srt_content = _generate_srt(vtt_segs, config.start_sec, config.end_sec)
            if srt_content.strip():
                srt_path = os.path.join(config.output_dir, config.output_name) + '.srt'
                with open(srt_path, 'w', encoding='utf-8') as _f:
                    _f.write(srt_content)
                result['srt'] = srt_path
                log.info('[cut] SRT saved: %s (%d segments)', srt_path, len(vtt_segs))

                # Generuj single-line SRT dla SubMachine
                srt_sm_content = _generate_srt(vtt_segs, config.start_sec, config.end_sec, single_line=True)
                srt_sm_path = str(srt_path).replace('.srt', '_submachine.srt')
                try:
                    with open(srt_sm_path, 'w', encoding='utf-8') as _f:
                        _f.write(srt_sm_content)
                    log.info("SubMachine SRT saved: %s", srt_sm_path)
                except Exception as e:
                    log.warning("Could not save SubMachine SRT: %s", e)
            else:
                log.warning('[cut] No SRT content from %d segments (check vtt_segments format)', len(vtt_segs))
        else:
            log.warning('[cut] subtitles=srt but no vtt_segments in candidate_data')

    base = os.path.join(config.output_dir, config.output_name)
    temp_path = base + "_temp.mp4"
    raw_path = base + "_raw.mp4"
    social_path = base + "_social.mp4"

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
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return result


def _download_fragment(youtube_url: str, start_sec: float, end_sec: float, output_path: str) -> bool:
    """
    CO: Pobiera fragment wideo z YouTube.
    PO CO: Unika pobierania całego wideo (może mieć GB) gdy potrzebujemy kilkudziesięciu sekund.
    JAK: 4-stopniowy fallback:
      0. local_overrides.json — manualne mapowanie YT ID → plik lokalny (zero sieci)
      1. find_local_by_yt_id — ID w nazwie pliku (zero sieci)
      2. find_local_match — audio fingerprint (wymaga YT audio sample)
      3. yt-dlp --download-sections (najszybszy, natywny)
      4. yt-dlp -g + ffmpeg ze streamu
      5. pełne pobranie + ffmpeg cut (ostatni fallback)
    """
    import subprocess, shutil, tempfile, os

    # Priorytet 0: local_overrides.json — manualne mapowanie YT ID → plik lokalny
    try:
        _m = re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})', youtube_url) \
             or re.match(r'^([A-Za-z0-9_-]{11})$', youtube_url)
        if _m:
            _ov = _load_local_overrides().get(_m.group(1))
            if _ov and os.path.exists(_ov):
                log.info("[cut] local_overrides match: %s -> %s", _m.group(1), _ov)
                _cut_local_segment(CutConfig(
                    source='local', local_path=_ov,
                    start_sec=start_sec, end_sec=end_sec,
                    output_dir=os.path.dirname(output_path),
                    output_name=os.path.splitext(os.path.basename(output_path))[0].replace('_temp', ''),
                ), output_path)
                return True
    except Exception as _e:
        log.warning("[cut] local_overrides error: %s", _e)

    # Priorytet 1+2: dopasowanie lokalnego pliku przez library_matcher
    try:
        from library_matcher import find_local_by_yt_id, find_local_match

        # Priorytet 1: szukaj po YouTube ID w nazwie pliku (szybkie, zero sieci)
        local_match = find_local_by_yt_id(youtube_url)

        # Priorytet 2: fingerprint audio (wymaga pobrania probki z YouTube)
        if not local_match:
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

        cmd_dl = ["yt-dlp", "-f", "bestvideo+bestaudio/best",
                  "--merge-output-format", "mp4",
                  "-o", tmp_video, youtube_url]
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
