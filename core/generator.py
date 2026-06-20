"""AI Schema Generator — VideoObject, Clip (chapters), FAQPage via Gemini API.

Migrated from: test_full_seo_v4.py (shadow-perihelion / D:\\Biblioteki\\prawy.pl)
Migration by: vse-architect-01 | DISPATCH-VSE-ARCHITECT-02 | 2026-05-13

Responsibilities:
  - Parse VTT transcript into timestamped segments
  - Call LLM (Gemini or Claude) to generate SEO-optimized titles, descriptions, chapters, FAQ
  - Anchor-match LLM chapter labels to exact VTT timestamps (fuzzy)
  - Return schema-ready dict for injector.py

Schema standards (Google 2026):
  - duration: ISO 8601 (PT#H#M#S)
  - uploadDate: ISO 8601 with timezone (e.g. 2026-01-15T10:00:00+01:00)
  - interactionStatistic: WatchAction + userInteractionCount (from YouTube)
  - SeekToAction: added for completeness (not rendered for PL content)
  - Quotation: NOT added (Google does not render; keep if existing)
  - Default model: gemini-2.5-flash | Claude: claude-sonnet-4-5

SAAS Enrichment (2026-06-17, vse-dev-14):
  - generate_seo_v4() accepts optional priority_keywords and internal_links

Branding fix (2026-06-19, vse-dev-17):
  - generate_seo_v4() accepts optional site_brand parameter

D5 Multi-keyword (2026-06-20, vse-dev-19):
  - LLM prompt now requests focus_keyphrases (list of 2-3 phrases)

D6b Publication types (2026-06-20, vse-dev-21):
  - generate_seo_v4() and process_video() accept publication_type parameter
  - Three types: full_analysis (default), watching_page, discover
  - Each type modifies the LLM prompt for article_body length/format

Dependencies:
  pip install google-genai anthropic python-dotenv
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
        anchor_text: 8-15 word quote from LLM output.
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
# LLM ABSTRACTION — Gemini + Claude
# ============================================================

def _call_llm(prompt: str, api_key: str, provider: str = "gemini") -> str:
    """Call LLM provider with prompt, return raw text response.

    Supports: gemini (default), claude.

    Args:
        prompt: Full prompt string to send to the model.
        api_key: API key for the selected provider.
        provider: LLM provider name: 'gemini' or 'claude'.

    Returns:
        Raw text response from the LLM.

    Raises:
        ValueError: If unsupported provider is specified.
        Exception: On API errors (re-raised with logging).
    """
    if provider == "claude":
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    elif provider == "gemini":
        from google import genai  # type: ignore
        client = genai.Client(api_key=api_key)
        return client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        ).text
    else:
        raise ValueError(f"Unsupported LLM provider: {provider!r}. Use 'gemini' or 'claude'.")


# ============================================================
# SAAS ENRICHMENT — build prompt section from GSC data
# ============================================================

def _build_saas_prompt_section(
    priority_keywords: Optional[list[str]] = None,
    internal_links: Optional[list[dict]] = None,
) -> str:
    """Build an additional prompt section with SAAS enrichment data.

    CO: Generuje sekcję promptu z danymi z SAAS (frazy GSC + linki wewn.).

    PO CO: Jeśli SAAS zwraca dane, chcemy żeby LLM wiedział o priorytetowych
    frazach portalu i mógł wpleść je w generowany artykuł. To podnosi
    trafność SEO — artykuł używa fraz które portal JUŻ rankuje w Google.

    JAK: Buduje markdown section która jest doklejana do głównego promptu.
    Jeśli brak danych → pusty string (prompt bez zmian).

    Args:
        priority_keywords: Lista fraz kluczowych z GSC.
        internal_links: Lista dictów z 'url' i 'title' do linkowania.

    Returns:
        String z sekcją promptu lub pusty string.
    """
    sections = []

    if priority_keywords:
        kw_list = ", ".join(f'"{ kw}"' for kw in priority_keywords[:15])
        sections.append(f"""## PRIORYTETOWE FRAZY KLUCZOWE Z GSC PORTALU

Poniższe frazy są faktycznie wyszukiwane przez użytkowników Google i portal już na nie rankuje.
Użyj ich naturalnie w article_body, meta_description, lead i FAQ — ale TYLKO jeśli pasują
tematycznie do tego materiału wideo. Nie forsuj fraz na siłę.

Frazy: {kw_list}""")

    if internal_links:
        links_text = "\n".join(
            f"- {link['url']} ({link.get('title', '')})" for link in internal_links[:10]
        )
        sections.append(f"""## PROPOZYCJE LINKOW WEWNETRZNYCH

Poniższe strony to najpopularniejsze artykuły portalu. Jeśli którykolwiek jest tematycznie
powiązany z omawianym materiałem wideo, wstaw link w article_body jako naturalny anchor
(np. "jak pisaliśmy w [temat](url)"). Max 2-3 linki, tylko jeśli pasują.

{links_text}""")

    if not sections:
        return ""

    return "\n\n" + "\n\n".join(sections) + "\n"


# ============================================================
# D6b.6: PUBLICATION TYPE PROMPT OVERRIDES
# ============================================================

def _get_publication_type_override(publication_type: str) -> str:
    """Get prompt override section for a specific publication type.

    CO: Zwraca nadpisanie promptu zależne od typu publikacji.

    PO CO: Różne witryny potrzebują różnych formatów artykułów:
           - full_analysis: pełny artykuł SEO (domyślny)
           - watching_page: krótki z embedem i chapterami
           - discover: format pod Google Discover

    JAK: Zwraca sekcję promptu która nadpisuje instrukcje
         dot. article_body i związanych pól.

    Args:
        publication_type: 'full_analysis', 'watching_page', or 'discover'.

    Returns:
        Prompt override string (appended to main prompt).
        Empty string for 'full_analysis' (no changes needed).
    """
    if publication_type == "watching_page":
        return """

## UWAGA — TYP PUBLIKACJI: WATCHING PAGE

To jest krótki artykuł typu "strona oglądania" z embedem wideo.
Zastosuj ZMODYFIKOWANE reguły:
- **article_body**: MAX 2 krótkie akapity <p> (300-500 zn). Skup się na
  krótkim opisie o czym jest materiał i dlaczego warto obejrzeć.
  NIE pisz rozbudowanej analizy.
- **chapters**: generuj normalnie (pełna lista)
- **faq**: MAX 2 pytania (krótkie, najważniejsze)
- **quotes**: MAX 2 cytaty
- Reszta pól (tytuły, meta, lead) — bez zmian
"""
    elif publication_type == "discover":
        return """

## UWAGA — TYP PUBLIKACJI: GOOGLE DISCOVER

To jest artykuł zoptymalizowany pod Google Discover.
Zastosuj ZMODYFIKOWANE reguły:
- **article_body**: 3-4 krótkie akapity (każdy max 2-3 zdania).
  Pierwszy akapit to HOOK — przyciągający uwagę, emocjonalny.
  Reszta: krótkie fakty, konkrety, bez akademickiego stylu.
  Formatuj pod mobile: krótkie zdania, dużo enterów.
- **post_title**: max 65 zn, z emocjonalnym hakiem (Discover lubi klikalne tytuły)
- **faq**: POMIŃ (nie generuj FAQ dla Discover)
- **quotes**: MAX 2 krótkie cytaty
- **chapters**: generuj normalnie
- **lead**: 1-2 zdania, MAX 150 zn, hook style
"""
    else:  # full_analysis or unknown — no override
        return ""


# ============================================================
# SEO GENERATION — prompt v5.5 multi-keyphrases + YT title formats
# ============================================================

def generate_seo_v4(
    title: str,
    timestamped_text: str,
    total_duration: float,
    yt_url: str,
    api_key: str,
    provider: str = "gemini",
    priority_keywords: Optional[list[str]] = None,
    internal_links: Optional[list[dict]] = None,
    site_brand: Optional[str] = None,
    publication_type: str = "full_analysis",
) -> dict:
    """Call LLM to generate full SEO package for a video.

    D6b.6: publication_type parameter controls article format/length.
    Three types supported:
      - 'full_analysis': full SEO article (default, unchanged)
      - 'watching_page': short article with embed focus
      - 'discover': Google Discover optimized format

    Args:
        title: WordPress post title.
        timestamped_text: VTT text with [MM:SS] markers from parse_vtt_full().
        total_duration: Video duration in seconds.
        yt_url: Full YouTube watch URL.
        api_key: API key for the selected LLM provider.
        provider: LLM provider: 'gemini' (default) or 'claude'.
        priority_keywords: Optional list of priority keyword phrases from GSC.
        internal_links: Optional list of dicts with 'url' and 'title' for linking.
        site_brand: Optional portal brand name for seo_title branding pipe.
        publication_type: Article type: 'full_analysis', 'watching_page', 'discover'.

    Returns:
        Parsed JSON dict from LLM response.

    Raises:
        json.JSONDecodeError: If LLM returns malformed JSON.
        Exception: On LLM API errors (re-raised with logging).
    """
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

    # Build SAAS enrichment section (empty string if no data)
    saas_section = _build_saas_prompt_section(priority_keywords, internal_links)

    # Build seo_title instruction based on site_brand availability
    if site_brand:
        seo_title_instruction = (
            f"**seo_title** \u2014 max 60 znakow, dla tagu <title> i RankMath. "
            f'Z branding pipe: "| {site_brand}". Moze byc krotsza wersja post_title.'
        )
    else:
        seo_title_instruction = (
            "**seo_title** \u2014 max 60 znakow, dla tagu <title> i RankMath. "
            "Moze byc krotsza wersja post_title. Bez branding pipe."
        )

    # D6b.6: Publication type override
    pub_type_section = _get_publication_type_override(publication_type)

    prompt = f"""Jestes ekspertem SEO i redaktorem portalu prawy.pl.

Na podstawie transkryptu nagrania wideo przygotuj PELNY PAKIET SEO.

## DANE WEJSCIOWE
Tytul: {title}
URL: {yt_url}
Czas nagrania: {total_min}:{total_sec:02d} ({total_min} minut)

Transkrypt z markerami [MM:SS]:
{text_trimmed}
{saas_section}
## KLUCZOWE ZASADY DLA ROZDZIALOW

Dla kazdego rozdzialu MUSISZ podac pole "anchor_text" \u2014 jest to DOKLADNY CYTAT 8-15 slow z transkryptu, ktore sa PIERWSZYMI slowami wypowiadanymi na poczatku danego tematu/rozdzialu.
Ten cytat musi byc DOKLADNIE TAKI jak w transkrypcie powyzej (dokladny tekst, male/wielkie litery bez znaczenia).
NIE parafrazuj, NIE streszczaj \u2014 kopiuj dokladny fragment.

Rozdzialy musza:
- Pokrywac CALY material od poczatku do konca (~{total_min} min)
- Byc rownomiernie rozlozone (co 3-7 minut)
- Miec {ch_range} rozdzialow (skaluj z dlugoscia materialu)
- Pierwszy zaczyna sie od samego poczatku rozmowy

## CO WYGENEROWAC

1. **focus_keyphrases** \u2014 lista 2-3 naturalnych fraz kluczowych Google (kazda 2-4 slowa). Pierwsza fraza to glowna, reszta to warianty tematyczne. Format: lista stringow.
2. **post_title** \u2014 max 80 znakow. SEO-first tytul artykulu (tag h1). MUSI zawierac glowna focus_keyphrase. Naturalne slowa kluczowe, bez clickbaitu. Polska gramatyka.
3. {seo_title_instruction}
4. **yt_title** \u2014 KRYTYCZNE ZASADY:
   - Dlugosc: 40-65 znakow (HARD MAX: 100). Optymalna dlugosc to 50-62 znaki.
   - Zacznij od tematu glownego lub nazwiska goscia (front-loading dla suggest feed).
   - MUSI byc INNY niz post_title i seo_title \u2014 inne ustawienie slow, inny ton.
   - NIE dodawaj brandingu ("| prawy.pl", "Prawy TV") \u2014 YouTube dodaje kanal automatycznie.
   - NIE uzywaj ogolnikow: "wazne", "ciekawe", "cos szokujacego".
   - Wybierz jeden z formatow:
     A \u2014 NAPIECIE:    [Nazwisko/Temat]: [akcja] \u2014 [stawka/skutek]
     B \u2014 UJAWNIENIE:  [Temat]: [co ujawnia] \u2014 [kulisy]
     C \u2014 PYTANIE:     Dlaczego [podmiot] milczy o [temat]?
     D \u2014 POWER WORD:  [Prawda/Kulisy/Skandal]: [temat] + podmiot
   - Cel: widz klika nawet nie znajac goscia z imienia.
   - KRYTYCZNE: pole yt_title NIGDY nie moze byc puste.
5. **wp_slug** \u2014 max 60 znakow. URL-slug artykulu WP. Tylko male litery, myslniki zamiast spacji, bez polskich znakow (transliteruj), bez stop-words. Musi zawierac slowa kluczowe z focus_keyphrases.
6. **meta_description** \u2014 max 155 znakow, z fraza kluczowa.
7. **lead** \u2014 2-3 zdania, max 300 znakow, z fraza kluczowa.
8. **article_body** \u2014 HTML: 3-5 <p>, 1-2 <h2> z fraza, ~1000-1500 zn. Opisz KONKRETNE watki.
9. **quotes** \u2014 {qt_range} cytatow z rozmowy:
   - "text": WYGLADZONY, CZYTELNY cytat (1-3 zdania). Usun jakania, powtorzenia.
   - "speaker": imie i nazwisko
   - "anchor_text": DOKLADNE 8-15 pierwszych slow ORYGINALNEGO transkryptu
10. **chapters** \u2014 {ch_range} rozdzialow:
    - "label": tytul (max 60 zn)
    - "anchor_text": DOKLADNY CYTAT 8-15 pierwszych slow
11. **faq** \u2014 {faq_range} pytan i odpowiedzi. Naturalne, zorientowane na search intent.
12. **youtube_description** \u2014 max 500 zn, z hashtagami.
13. **video_description** \u2014 max 200 zn, dla schema.
14. **tags** \u2014 5-8 tagow lowercase.

KRYTYCZNE: Pola post_title, seo_title, yt_title MUSZA byc niepuste.
yt_title to OSOBNY, INNY tytul niz post_title \u2014 angazujacy, YouTubowy.
NIGDY nie zostawiaj ich pustych.
{pub_type_section}
Odpowiedz TYLKO JSON (bez markdown):
{{"focus_keyphrases":["fraza glowna","fraza 2","fraza 3"],"post_title":"...","seo_title":"...","yt_title":"...","wp_slug":"...","meta_description":"...","lead":"...","article_body":"...","quotes":[{{"text":"...","speaker":"...","anchor_text":"..."}}],"chapters":[{{"label":"...","anchor_text":"..."}}],"faq":[{{"question":"...","answer":"..."}}],"youtube_description":"...","video_description":"...","tags":["..."]}}""" 

    logger.info("Calling %s for: %s [type=%s]", provider, title[:60], publication_type)
    if priority_keywords:
        logger.info(
            "SAAS enrichment active: %d keywords, %d links",
            len(priority_keywords),
            len(internal_links) if internal_links else 0,
        )
    if site_brand:
        logger.info("site_brand: %r", site_brand)
    if publication_type != "full_analysis":
        logger.info("Publication type override: %s", publication_type)
    try:
        text = _call_llm(prompt, api_key, provider)
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except Exception as exc:
        logger.error("%s call failed: %s", provider, exc)
        raise


# ============================================================
# KEYPHRASES NORMALIZATION (D5, vse-dev-19)
# ============================================================

def _normalize_keyphrases(result: dict) -> list[str]:
    """Normalize LLM output to always have focus_keyphrases as a list.

    Args:
        result: Raw LLM JSON output dict.

    Returns:
        List of keyphrase strings (1-3 items typically).
    """
    # New format: focus_keyphrases (list)
    keyphrases = result.get("focus_keyphrases", [])
    if isinstance(keyphrases, list) and keyphrases:
        return [kp.strip() for kp in keyphrases if isinstance(kp, str) and kp.strip()]

    # Old format: focus_keyphrase (string) — backward compat
    keyphrase = result.get("focus_keyphrase", "").strip()
    if keyphrase:
        return [keyphrase]

    return []


# ============================================================
# FULL PIPELINE — VTT → LLM → resolved chapters
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
    provider: str = "gemini",
    priority_keywords: Optional[list[str]] = None,
    internal_links: Optional[list[dict]] = None,
    site_brand: Optional[str] = None,
    publication_type: str = "full_analysis",
) -> dict:
    """Run the full generation pipeline for a single video.

    D6b.6: publication_type parameter controls article format.

    Args:
        youtube_id: YouTube video ID.
        wp_id: WordPress post ID.
        post_title: WordPress post title.
        yt_url: Full YouTube watch URL.
        vtt_path: Path to the .vtt transcript file.
        api_key: API key for the selected LLM provider.
        out_dir: Directory to save the result JSON. If None, does not save.
        sleep_between: Seconds to sleep after the LLM call (rate-limit guard).
        provider: LLM provider: 'gemini' (default) or 'claude'.
        priority_keywords: Optional list of priority keyword phrases from GSC.
        internal_links: Optional list of dicts with 'url' and 'title' for linking.
        site_brand: Optional portal brand name for seo_title branding pipe.
        publication_type: Article type: 'full_analysis', 'watching_page', 'discover'.

    Returns:
        SEO result dict with all fields + resolved chapters + duration metadata.

    Raises:
        FileNotFoundError: If vtt_path does not exist.
        json.JSONDecodeError: If LLM returns malformed JSON.
    """
    logger.info("Processing video: %s (WP#%s) via %s [type=%s]", youtube_id, wp_id, provider, publication_type)

    timestamped, segments, duration = parse_vtt_full(vtt_path)
    dur_min = int(duration // 60)
    dur_sec = int(duration % 60)
    logger.info(
        "VTT parsed: %d chars | %d segments | %d:%02d",
        len(timestamped), len(segments), dur_min, dur_sec,
    )

    result = generate_seo_v4(
        post_title, timestamped, duration, yt_url, api_key, provider,
        priority_keywords=priority_keywords,
        internal_links=internal_links,
        site_brand=site_brand,
        publication_type=publication_type,
    )

    # D5: Normalize keyphrases — always store as list
    keyphrases = _normalize_keyphrases(result)
    result["focus_keyphrases"] = keyphrases
    # Backward compat: keep focus_keyphrase (singular) as first item for old consumers
    result["focus_keyphrase"] = keyphrases[0] if keyphrases else ""
    logger.info("focus_keyphrases: %r", keyphrases)

    # Fallback: post_title z seo_title jesli puste
    if not result.get("post_title", "").strip():
        result["post_title"] = result.get("seo_title", post_title)
        logger.warning(
            "post_title missing \u2014 fallback to seo_title: %r",
            result["post_title"][:60],
        )

    # Fallback: yt_title z post_title jesli puste
    if not result.get("yt_title", "").strip():
        result["yt_title"] = result.get("post_title", post_title)[:100]
        logger.warning(
            "yt_title missing \u2014 fallback to post_title: %r",
            result["yt_title"][:60],
        )

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
    result["llm_provider"] = provider
    result["publication_type"] = publication_type  # D6b.6: track type in output

    # Track SAAS enrichment in result metadata
    if priority_keywords:
        result["saas_enriched"] = True
        result["saas_keywords_count"] = len(priority_keywords)
    else:
        result["saas_enriched"] = False

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
        "Done: %d chapters (%d/%d matched), keyphrases=%r, type=%s, saas=%s, brand=%s",
        len(resolved_chapters), matched_count, len(resolved_chapters),
        keyphrases, publication_type,
        "enriched" if result.get("saas_enriched") else "standalone",
        site_brand or "none",
    )
    return result
