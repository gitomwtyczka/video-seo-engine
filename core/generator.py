"""AI Schema Generator — VideoObject, Clip (chapters), FAQPage via Gemini API.

Migrated from: test_full_seo_v4.py (shadow-perihelion / D:\\Biblioteki\\prawy.pl)
Migration by: vse-architect-01 | DISPATCH-VSE-ARCHITECT-02 | 2026-05-13

Responsibilities:
  - Parse VTT transcript into timestamped segments
  - Call Gemini API to generate SEO-optimized titles, descriptions, chapters, FAQ
  - Anchor-match Gemini chapter labels to exact VTT timestamps (fuzzy)
  - Return schema-ready dict for injector.py

Schema standards (Google 2026):
  - duration: ISO 8601 (PT#H#M#S)
  - uploadDate: ISO 8601 with timezone (e.g. 2026-01-15T10:00:00+01:00)
  - interactionStatistic: WatchAction + userInteractionCount (from YouTube)
  - SeekToAction: added for completeness (not rendered for PL content)
  - Quotation: NOT added (Google does not render; keep if existing)
  - Model: gemini-2.5-flash

Dependencies:
  pip install google-genai python-dotenv
"""
import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# DURATION UTILS
# ============================================================

def format_duration_iso(seconds: float) -> str:
    """Convert total seconds to ISO 8601 duration string (PT#H#M#S).

    Args:
        seconds: Total duration in seconds.

    Returns:
        ISO 8601 duration string, e.g. 'PT1H23M45S'.
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    parts = "PT"
    if h:
        parts += f"{h}H"
    parts += f"{m}M{s}S"
    return parts


# ============================================================
# VTT PARSER
# ============================================================

def parse_vtt_full(vtt_path: str) -> tuple[str, list[tuple[float, str]], float]:
    """Parse a WebVTT file into timestamped text, segments list, and total duration.

    Args:
        vtt_path: Absolute path to the .vtt file.

    Returns:
        Tuple of:
          - timestamped_text: Human-readable text with [MM:SS] markers every 30s.
          - segments: List of (start_sec, text) tuples for anchor matching.
          - total_duration: Duration of the video in seconds.

    Raises:
        FileNotFoundError: If vtt_path does not exist.
        ValueError: If VTT file is empty or unparseable.
    """
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()

    segments: list[tuple[float, str]] = []
    current_time = 0.0
    max_time = 0.0

    for line in content.split("\n"):
        line = line.strip()
        ts_match = re.match(r"^(\d{2}):(\d{2}):(\d{2}[\.,]\d+)\s*-->", line)
        if ts_match:
            h, m, s = ts_match.groups()
            s = s.replace(",", ".")
            current_time = int(h) * 3600 + int(m) * 60 + float(s)
            if current_time > max_time:
                max_time = current_time
            continue
        if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.match(r"^\d+$", line):
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        clean = clean.replace("&gt;&gt;", "").strip()
        if clean and len(clean) > 3:
            segments.append((current_time, clean))

    # Deduplicate — keep first occurrence of each line
    seen: set[str] = set()
    unique: list[tuple[float, str]] = []
    for ts, text in segments:
        if text not in seen:
            seen.add(text)
            unique.append((ts, text))

    if not unique:
        raise ValueError(f"VTT file parsed to 0 usable segments: {vtt_path}")

    # Build marked text with 30s interval markers
    parts: list[str] = []
    last_marker = -30.0
    for ts, text in unique:
        if ts - last_marker >= 30:
            minutes = int(ts // 60)
            seconds = int(ts % 60)
            parts.append(f"\n[{minutes:02d}:{seconds:02d}] ")
            last_marker = ts
        parts.append(text + " ")

    return "".join(parts), unique, max_time


# ============================================================
# ANCHOR MATCHING — fuzzy VTT lookup
# ============================================================

def find_anchor_in_vtt(anchor_text: str, segments: list[tuple[float, str]]) -> int:
    """Find the VTT timestamp where anchor_text first appears.

    Uses exact substring match first, then sliding-window fuzzy match
    via SequenceMatcher. Accepts fuzzy matches with ratio > 0.5.

    Args:
        anchor_text: 8-15 word quote from Gemini output.
        segments: List of (start_sec, text) tuples from parse_vtt_full().

    Returns:
        Timestamp in seconds (int), or -1 if not found.
    """
    anchor_clean = anchor_text.lower().strip()
    best_score = 0.0
    best_time = -1

    for window_size in [3, 5, 2, 1]:
        for i in range(len(segments) - window_size + 1):
            window_text = " ".join(seg[1] for seg in segments[i : i + window_size]).lower()

            if anchor_clean in window_text:
                return int(segments[i][0])

            score = SequenceMatcher(None, anchor_clean, window_text[: len(anchor_clean) * 2]).ratio()
            if score > best_score:
                best_score = score
                best_time = int(segments[i][0])

    if best_score > 0.5:
        return best_time

    return -1


# ============================================================
# GEMINI CALL — prompt v5.3 anchor-based chapters
# ============================================================

def generate_seo_v4(
    title: str,
    timestamped_text: str,
    total_duration: float,
    yt_url: str,
    api_key: str,
) -> dict:
    """Call Gemini to generate full SEO package for a video.

    Generates: focus_keyphrase, post_title, seo_title, yt_title, wp_slug,
    meta_description, lead, article_body, quotes (with anchor_text),
    chapters (with anchor_text), faq, youtube_description, video_description, tags.

    Args:
        title: WordPress post title.
        timestamped_text: VTT text with [MM:SS] markers from parse_vtt_full().
        total_duration: Video duration in seconds.
        yt_url: Full YouTube watch URL.
        api_key: Gemini API key.

    Returns:
        Parsed JSON dict from Gemini response.

    Raises:
        json.JSONDecodeError: If Gemini returns malformed JSON.
        Exception: On Gemini API errors (re-raised with logging).
    """
    from google import genai  # type: ignore

    client = genai.Client(api_key=api_key)
    text_trimmed = timestamped_text[:80000]
    total_min = int(total_duration // 60)

    if total_min <= 15:
        faq_range, ch_range, qt_range = "2-3", "5-7", "2-3"
    elif total_min <= 30:
        faq_range, ch_range, qt_range = "3-5", "6-10", "3-5"
    elif total_min <= 45:
        faq_range, ch_range, qt_range = "4-6", "8-12", "4-6"
    else:
        faq_range, ch_range, qt_range = "5-8", "10-15", "5-7"

    total_sec = int(total_duration % 60)

    prompt = f"""Jestes ekspertem SEO i redaktorem portalu prawy.pl.

Na podstawie transkryptu nagrania wideo przygotuj PELNY PAKIET SEO.

## DANE WEJSCIOWE
Tytul: {title}
URL: {yt_url}
Czas nagrania: {total_min}:{total_sec:02d} ({total_min} minut)

Transkrypt z markerami [MM:SS]:
{text_trimmed}

## KLUCZOWE ZASADY DLA ROZDZIALOW

Dla kazdego rozdzialu MUSISZ podac pole "anchor_text" — jest to DOKLADNY CYTAT 8-15 slow z transkryptu, ktore sa PIERWSZYMI slowami wypowiadanymi na poczatku danego tematu/rozdzialu.
Ten cytat musi byc DOKLADNIE TAKI jak w transkrypcie powyzej (dokladny tekst, male/wielkie litery bez znaczenia).
NIE parafrazuj, NIE streszczaj — kopiuj dokladny fragment.

Rozdzialy musza:
- Pokrywac CALY material od poczatku do konca (~{total_min} min)
- Byc rownomiernie rozlozone (co 3-7 minut)
- Miec {ch_range} rozdzialow (skaluj z dlugoscia materialu)
- Pierwszy zaczyna sie od samego poczatku rozmowy

## CO WYGENEROWAC

1. **focus_keyphrase** — 2-4 slowa, naturalna fraza Google.
2. **post_title** — max 80 znakow. SEO-first tytul artykulu (tag h1). MUSI zawierac focus_keyphrase. Naturalne slowa kluczowe, bez clickbaitu. Polska gramatyka.
3. **seo_title** — max 60 znakow, dla tagu <title> i RankMath. Z branding pipe: "| Prawy TV". Moze byc krotsza wersja post_title.
4. **yt_title** — max 100 znakow. Angazujacy tytul YouTube. MUSI zawierac focus_keyphrase. Pytanie lub emocja. NIE moze byc identyczny z post_title. Pisany jak naglowek viralowy.
5. **wp_slug** — max 60 znakow. URL-slug artykulu WP. Tylko male litery, myslniki zamiast spacji, bez polskich znakow (transliteruj: a->a, e->e, s->s, o->o, etc.), bez stop-words (i, w, z, na, do, ze, sie). Musi zawierac slowa kluczowe z focus_keyphrase. Optymalna dlugosc 40-60 znakow.
6. **meta_description** — max 155 znakow, z fraza kluczowa.
7. **lead** — 2-3 zdania, max 300 znakow, z fraza kluczowa.
8. **article_body** — HTML: 3-5 <p>, 1-2 <h2> z fraza, ~1000-1500 zn. Opisz KONKRETNE watki.
9. **quotes** — {qt_range} cytatow z rozmowy:
   - "text": WYGLADZONY, CZYTELNY cytat (1-3 zdania). Usun jakania (yyy, eee), powtorzenia, urwane zdania. Zachowaj SENS i STYL mowcy ale napisz to poprawna, plynna polszczyzna. Cytat musi brzmiec jak profesjonalny wywiad w prasie — nie jak surowy transkrypt.
   - "speaker": imie i nazwisko
   - "anchor_text": DOKLADNE 8-15 pierwszych slow ORYGINALNEGO transkryptu (surowe, bez edycji!) z tego fragmentu — potrzebne do odnalezienia momentu w nagraniu
10. **chapters** — {ch_range} rozdzialow:
    - "label": tytul (max 60 zn)
    - "anchor_text": DOKLADNY CYTAT 8-15 pierwszych slow tego fragmentu z transkryptu
11. **faq** — {faq_range} pytan i odpowiedzi z tresci.
12. **youtube_description** — max 500 zn, z hashtagami.
13. **video_description** — max 200 zn, dla schema.
14. **tags** — 5-8 tagow lowercase.

Odpowiedz TYLKO JSON (bez markdown):
{{"focus_keyphrase":"...","seo_title":"...","meta_description":"...","lead":"...","article_body":"...","quotes":[{{"text":"...","speaker":"...","anchor_text":"..."}}],"chapters":[{{"label":"...","anchor_text":"..."}}],"faq":[{{"question":"...","answer":"..."}}],"youtube_description":"...","video_description":"...","tags":["..."]}}"""

    logger.info("Calling Gemini (gemini-2.5-flash) for: %s", title[:60])
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except Exception as exc:
        logger.error("Gemini call failed: %s", exc)
        raise


# ============================================================
# FULL PIPELINE — VTT → Gemini → resolved chapters
# ============================================================

def process_video(
    youtube_id: str,
    wp_id: int,
    post_title: str,
    yt_url: str,
    vtt_path: str,
    api_key: str,
    out_dir: Optional[str] = None,
    sleep_between: int = 0,
) -> dict:
    """Run the full generation pipeline for a single video.

    Parses VTT, calls Gemini, resolves anchor timestamps, saves JSON.

    Args:
        youtube_id: YouTube video ID.
        wp_id: WordPress post ID.
        post_title: WordPress post title.
        yt_url: Full YouTube watch URL.
        vtt_path: Path to the .vtt transcript file.
        api_key: Gemini API key.
        out_dir: Directory to save the result JSON. If None, does not save.
        sleep_between: Seconds to sleep after the Gemini call (rate-limit guard).

    Returns:
        SEO result dict with all fields + resolved chapters + duration metadata.

    Raises:
        FileNotFoundError: If vtt_path does not exist.
        json.JSONDecodeError: If Gemini returns malformed JSON.
    """
    logger.info("Processing video: %s (WP#%s)", youtube_id, wp_id)

    timestamped, segments, duration = parse_vtt_full(vtt_path)
    dur_min = int(duration // 60)
    dur_sec = int(duration % 60)
    logger.info(
        "VTT parsed: %d chars | %d segments | %d:%02d",
        len(timestamped), len(segments), dur_min, dur_sec,
    )

    result = generate_seo_v4(post_title, timestamped, duration, yt_url, api_key)

    # Anchor-match chapters to exact VTT timestamps
    resolved_chapters: list[dict] = []
    for ch in result.get("chapters", []):
        anchor = ch.get("anchor_text", "")
        ts = find_anchor_in_vtt(anchor, segments)
        matched = ts >= 0
        resolved_chapters.append({
            "time": max(0, ts),
            "label": ch["label"],
            "anchor_text": anchor,
            "matched": matched,
        })
        status = f"{ts // 60:02d}:{ts % 60:02d}" if matched else "NOT FOUND"
        logger.info("  chapter [%s] %s", status, ch["label"][:50])

    resolved_chapters.sort(key=lambda x: x["time"])
    if resolved_chapters and resolved_chapters[0]["time"] != 0:
        resolved_chapters[0]["time"] = 0

    result["chapters"] = resolved_chapters

    # Anchor-match quotes
    for q in result.get("quotes", []):
        anchor = q.get("anchor_text", q.get("text", "")[:40])
        ts = find_anchor_in_vtt(anchor, segments)
        q["time"] = max(0, ts)

    # Attach metadata
    result["wp_id"] = wp_id
    result["youtube_id"] = youtube_id
    result["original_title"] = post_title
    result["yt_url"] = yt_url
    result["total_duration"] = int(duration)
    result["duration_seconds"] = int(duration)
    result["duration_iso"] = format_duration_iso(duration)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{youtube_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("Saved: %s", out_path)

    if sleep_between > 0:
        time.sleep(sleep_between)

    matched_count = sum(1 for c in resolved_chapters if c.get("matched"))
    logger.info(
        "Done: %d chapters (%d/%d matched), focus=%s",
        len(resolved_chapters), matched_count, len(resolved_chapters),
        result.get("focus_keyphrase", "?"),
    )
    return result
