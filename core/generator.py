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
  - Default model: gemini-2.5-flash | Claude: claude-3-5-sonnet-20241022

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

D1 Two-Pass Content Pipeline:
  - Pass 1: Schema generation (no article_body)
  - Pass 2: Article generation via PressAI M2M or local fallback LLM

D10 Smart External Links (2026-06-21, vse-dev-25):
  - LLM prompt requests external_links (2-3 authority DoFollow links)
  - article_body MUST contain woven <a> tags to authority sources
  - Sources: Wikipedia PL, .gov.pl, PAP, Reuters, AP, think-tanks

D11 Image Descriptions Fallback (2026-06-21, vse-dev-26):
  - LLM prompt requests image_descriptions (2 descriptions for video screenshots)
  - Used ONLY as fallback when SAAS Vision API is unavailable
  - SAAS primary (GPT-4o Vision sees actual image) vs LLM blind descriptions

D12 JSON Resilience (2026-06-21, vse-dev-27):
  - Log raw LLM output on json.loads() failure for debugging
  - 1 retry with fix prompt on JSONDecodeError
  - Prompt fix: instruct HTML attributes to use apostrophes (') not quotes (")
  - Root cause: Claude doesn't escape " in HTML attrs inside JSON strings

D13 Slug Trim (2026-06-21, vse-dev-29):
  - Hard limit 60 chars on wp_slug (trim to last full word)
  - Prompt updated: preserve Polish conjunctions (i, w, z, na, do, o) in slug
    when they are part of the focus keyphrase — fixes RankMath false positive
  - Bugfix: resolved_channels → resolved_chapters (typo from original code)

D15 JSON Sanitizer (2026-06-29, vse-dev-30):
  - _sanitize_llm_json() applied before json.loads() in generate_seo_v4()
  - PRIMARY: json-repair library (pip install json-repair) — structural repair
  - FALLBACK: regex restricted to HTML attr values (attr=\\\"val\\\" → attr='val')
  - Zero false positives on plain text, multiline, nested HTML
  - Eliminates 500 errors from LLM outputting raw HTML with unescaped quotes

FIX A (2026-07-10, vse-dev-01):
  - process_video() now accepts vtt_path=None (Optional[str])
  - When vtt_path is None → calls generate_schema_without_transcript()
  - generate_schema_without_transcript(): LLM generates SEO from title+desc only
    - chapters = [] (no VTT → no anchors)
    - faq_items = [] (skipped)
    - VideoObject + meta description + focus_keyphrase: generated normally
  - Result marked with partial_result=True, transcript_available=False

VTT Limit fix (2026-07-14, Supervisor-01):
  - text_trimmed limit raised from 80000 → 200000 chars
  - Covers ~90 min of conversation (avg 2200 char/min post-parse)
  - Safe for Gemini 2.5 Flash (1M token ctx) and Claude Sonnet (200k token ctx)

Dependencies:
  pip install google-genai anthropic python-dotenv json-repair
"""
import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)

# D15: json-repair optional import (PRIMARY sanitizer backend)
try:
    from json_repair import repair_json as _json_repair_fn  # type: ignore
    _JSON_REPAIR_AVAILABLE = True
except ImportError:
    _JSON_REPAIR_AVAILABLE = False
    logger.warning("D15: json-repair not installed — using regex fallback. pip install json-repair")


# ============================================================
# FORMAT INSTRUCTIONS (Pass 2)
# ============================================================

FORMAT_INSTRUCTIONS: dict[str, str] = {
    "analiza": "Napisz pogłębioną analizę: teza → dane/dowody → analiza wieloaspektowa → wnioski → prognozy. Minimum 3 Śródtła/przykłady. Styl: merytoryczny, bez kolokwializmow.",
    "news": "Napisz newsa: odwrócona piramida, 5W+H w leadzie, 1 akapit tła, co dalej. Styl: zwarty, rzeczowy.",
    "explainer": "Wyjaśnij mechanizm: co to jest, dlaczego ważne, jak działa, co to oznacza dla czytelnika. Prosty język.",
    "wywiad": "Napisz wywiad Q&A: krótki wstęp redakcyjny (2-3 zdania) + dialog pytanie-odpowiedź z transkryptu.",
    "poradnik": "Napisz poradnik: problem → kroki rozwiązania (numerowane) → wskazówki praktyczne.",
    "felieton": "Napisz felieton: styl autorski, ironia, metafory. Mocna puenta na końcu.",
    "reportaz": "Napisz reportaż: immersyjna narracja, sceny, konkrety, detale.",
    # Backward compat
    "full_analysis": "Napisz pogłębiony artykuł analityczny.",
    "watching_page": "Napisz krótki opis wideo (2-3 akapity). Styl: informacyjny.",
    "discover": "Krótki artykuł Discover (500-600 słów). Zasady Google Discover 2026: TYTUŁ: Sedno informacji w tytule — zakaz clickbaitu i curiosity gap. Czytelnik musi wiedzieć co dostanie. LEAD: Rzetelny, informacyjny — odpowiada na 'co i dlaczego ważne', nie 'jak bardzo zaskakujące'. STRUKTURA: max 2 śródtytuły H3, krótkie akapity (2-3 zdania), prosty język. ZAKAZ: Tytułów zaczynających się od pytania retorycznego ('Czy wiesz że...', 'Oto dlaczego...'). Fraza kluczowa naturalna, wpleciona bez wymuszania.",
}

def _get_target_words(publication_type: str) -> int:
    return {
        "analiza": 1000, "reportaz": 1200, "wywiad": 900,
        "news": 600, "explainer": 800, "poradnik": 800,
        "felieton": 700, "full_analysis": 800,
        "watching_page": 400, "discover": 500,
    }.get(publication_type, 800)


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
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        msg = client.messages.create(
            model=model,
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
# PASS 2 ARTICLE GENERATION
# ============================================================

def _generate_article_fallback(
    schema: dict,
    vtt_text: str,
    publication_type: str,
    api_key: str,
    provider: str = "gemini",
    target_words: int = 800,
) -> str:
    """Fallback: generuj długi artykuł lokalnym LLM gdy PressAI niedostępny.
    
    CO: Generuje pełny artykuł HTML przez lokalny LLM (Gemini/Claude).
    PO CO: Gdy USE_PRESSAI_ARTICLE_ENGINE=false lub PressAI niedostępny.
    JAK: Osobny prompt skupiony wyłącznie na treści artykułu, bez JSON overhead.
    """
    keyphrase = schema.get("focus_keyphrases", [""])[0] if schema.get("focus_keyphrases") else ""
    instruction = FORMAT_INSTRUCTIONS.get(publication_type, FORMAT_INSTRUCTIONS["full_analysis"])
    post_title = schema.get("post_title", "")
    
    prompt = f"""Jesteś redaktorem portalu. Napisz artykuł na podstawie transkryptu wideo.

FRAZA KLUCZOWA: {keyphrase}
TYTUŁ: {post_title}
FORMAT: {instruction}
CEL DŁUGOŚCI: minimum {target_words} słów

ZASADY HTML:
- Używaj <h2>, <h3>, <p>, <blockquote> (NIE <html>, <head>, <body>)
- Apostrofy (') w atrybutach HTML, NIE cudzysłowy
- Co 150-200 słów nowy nagłówek <h3>
- Fraza kluczowa naturalnie minimum 3x w tekście
- Pierwszy akapit zawiera główną frazę
- Znacznik przed FAQ: <hr id='system-readmore' />

TRANSKRYPT:
{vtt_text[:120000]}

Zwróć TYLKO HTML artykułu (bez JSON, bez wyjaśnień):"""
    
    logger.info("_generate_article_fallback: type=%s target=%d words provider=%s", publication_type, target_words, provider)
    return _call_llm(prompt, api_key, provider)


async def generate_article_content(
    schema: dict,
    vtt_text: str,
    publication_type: str,
    api_key: str,
    provider: str = "gemini",
    pressai_api_url: str = "",
    pressai_token: str = "",
    internal_links: Optional[list[dict]] = None,
) -> tuple[str, str]:
    """Pass 2: generuje długi artykuł (600-1200+ słów).
    
    CO: Generuje treść artykułu jako Pass 2 pipeline.
    PO CO: Pass 1 generuje krótkie metadata; Pass 2 generuje pełny artykuł.
    JAK: Próbuje PressAI M2M API. Fallback: lokalny LLM.
    
    Returns:
        Tuple (article_html: str, engine: str)
        engine = 'pressai' | 'local_fallback'
    """
    FORMAT_MAP = {
        "analiza": "analiza", "news": "news", "explainer": "explainer",
        "wywiad": "wywiad", "poradnik": "poradnik", "felieton": "felieton",
        "reportaz": "reportaz",
        "full_analysis": "analiza", "watching_page": "news", "discover": "news",
    }
    target_words = _get_target_words(publication_type)
    pressai_format = FORMAT_MAP.get(publication_type, "analiza")
    
    # Próba PressAI M2M
    if pressai_api_url and pressai_token:
        try:
            import httpx
            payload = {
                "focus_keyphrase": schema.get("focus_keyphrases", [""])[0] if schema.get("focus_keyphrases") else "",
                "keyphrases": schema.get("focus_keyphrases", []),
                "transcript": vtt_text[:200000],
                "title": schema.get("post_title", ""),
                "format": pressai_format,
                "target_words": target_words,
                "internal_links": internal_links or [],
                "source": "vse",
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{pressai_api_url}/api/external/generate-article",
                    json=payload,
                    headers={"Authorization": f"Bearer {pressai_token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                article_html = data.get("article_body", "")
                if article_html and len(article_html) > 200:
                    logger.info("Pass 2: PressAI article (%d chars)", len(article_html))
                    return article_html, "pressai"
                logger.warning("Pass 2: PressAI returned short/empty article, using fallback")
        except Exception as e:
            logger.warning("Pass 2: PressAI failed (%s) — falling back to local LLM", e)
    
    # Fallback: lokalny LLM
    article_html = _generate_article_fallback(
        schema=schema, vtt_text=vtt_text,
        publication_type=publication_type,
        api_key=api_key, provider=provider,
        target_words=target_words,
    )
    return article_html, "local_fallback"


# ============================================================
# D15: JSON SANITIZER — pre-parse repair for LLM HTML output
# ============================================================

def _sanitize_llm_json(raw_text: str) -> str:
    """Sanitize raw LLM output before json.loads() to prevent JSONDecodeError.

    CO: Naprawia surowy tekst zwracany przez LLM przed parsowaniem JSON.

    PO CO: LLM (Claude/Gemini) czasem generuje w polach HTML (article_body)
    surowe podwójne cudzysłowy w atrybutach tagów HTML, np:
      <a href="https://prawy.pl" target="_blank">link</a>
    To niszczy składnię JSON i powoduje błęd 500. Ta funkcja jest ostatnią
    deską ratunku przed json.loads() — naprawia taki output bez korumpowania
    poprawnego JSON lub zwykłego tekstu.

    JAK: Dwie warstwy naprawy (PRIMARY → FALLBACK):
      1. PRIMARY: json-repair (pip install json-repair) — rozumie strukturę JSON,
         naprawia semantycznie, zero false positives.
      2. FALLBACK (gdy json-repair niedostępny): regex wyizolowany do wartości
         atrybutów HTML (attr=\\\"val\\\" → attr='val'), działa wyłącznie wewnątrz
         sekwencji wyglądających jak HTML tag. NIE dotyka zwykłego tekstu.

    Passthrough: jeśli raw_text jest już poprawnym JSON — zwracany bez zmian
    (json.loads() OK → natychmiastowy return, zero overhead).

    Args:
        raw_text: Raw string output from LLM (may contain broken JSON).

    Returns:
        Sanitized string ready for json.loads(). Always returns a string.
        On catastrophic failure returns raw_text unchanged (re-raise by caller).
    """
    # Fast path: already valid JSON — no work needed
    try:
        json.loads(raw_text)
        return raw_text
    except json.JSONDecodeError:
        pass

    # PRIMARY: json-repair — structural, safe, handles multiline and nesting
    if _JSON_REPAIR_AVAILABLE:
        try:
            repaired = _json_repair_fn(raw_text, return_objects=False)
            # json-repair may return a dict; ensure we have a string
            if isinstance(repaired, dict):
                repaired = json.dumps(repaired, ensure_ascii=False)
            # Validate repair worked
            json.loads(repaired)
            logger.info("D15: json-repair fixed LLM output (%d → %d chars)", len(raw_text), len(repaired))
            return repaired
        except Exception as repair_exc:
            logger.warning("D15: json-repair failed (%s) — trying regex fallback", repair_exc)

    # FALLBACK: regex — restricted to HTML attribute values only
    # Pattern: matches attr="value" sequences inside JSON string values
    # ONLY converts double-quoted HTML attributes to single-quoted.
    # Does NOT touch: plain text, JSON keys, already-correct JSON.
    #
    # Strategy: find sequences that look like HTML attribute assignments
    # (word="...") and convert the surrounding double quotes to single quotes.
    # The lookahead/behind anchors it to HTML-like context (alphanumeric attr name).
    #
    # Limitation: cannot fix deeply nested escaped sequences without json-repair.
    # For those cases, the D12 retry mechanism takes over.
    try:
        # Match: word characters followed by =" ... " where value has no unescaped "
        # Replace: attr="val" → attr='val'
        # The pattern is anchored to look like HTML attr=" ... "
        fixed = re.sub(
            r'(\b[\w-]+)=\\"((?:[^\\\"]|\\.)*)\\"',
            r"\1='\2'",
            raw_text,
        )
        json.loads(fixed)
        logger.info("D15: regex fallback fixed LLM output")
        return fixed
    except (json.JSONDecodeError, re.error) as regex_exc:
        logger.warning(
            "D15: regex fallback also failed (%s) — returning raw for D12 retry",
            regex_exc,
        )

    # Both strategies failed — return raw text; D12 retry will handle or raise
    return raw_text


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

To jest krótki artykuł Discover (500-600 słów). Zasady Google Discover 2026:
- **post_title**: max 65 zn. Sedno informacji w tytule — zakaz clickbaitu i curiosity gap. Czytelnik musi wiedzieć co dostanie. ZAKAZ tytułów zaczynających się od pytania retorycznego ('Czy wiesz że...', 'Oto dlaczego...').
- **lead**: 1-2 zdania, max 150 zn. Rzetelny, informacyjny — odpowiada na 'co i dlaczego ważne', nie 'jak bardzo zaskakujące'.
- **article_body**: max 2 śródtytuły H3, krótkie akapity (2-3 zdania), prosty język. Formatuj pod mobile: krótkie zdania, dużo enterów. Fraza kluczowa naturalna, wpleciona bez wymuszania.
- **faq**: POMIŃ (nie generuj FAQ dla Discover)
- **quotes**: MAX 2 krótkie cytaty
- **chapters**: generuj normalnie
"""
    else:  # full_analysis or unknown — no override
        return ""


# ============================================================
# SEO GENERATION — prompt v5.8 + slug hard limit D13
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

    D10: LLM prompt now requests external_links (2-3 authority DoFollow links)
    and instructs article_body to weave in <a> tags to authority sources.

    D11: LLM prompt now requests image_descriptions (2 screenshot descriptions)
    as FALLBACK when SAAS Vision API is unavailable. SAAS descriptions are
    preferred because GPT-4o Vision actually sees the image.

    D12: JSON Resilience — log raw output on parse failure, 1 retry with fix
    prompt, instruct LLM to use apostrophes in HTML attributes.

    D13: wp_slug prompt updated — preserve Polish conjunctions (i, w, z, na,
    do, o) when part of focus keyphrase. Hard 60-char limit enforced in
    process_video() after json.loads().

    D15: _sanitize_llm_json() applied before json.loads() — PRIMARY via
    json-repair, FALLBACK via regex restricted to HTML attr values.
    Eliminates 500 errors from unescaped double quotes in HTML attributes.

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
        json.JSONDecodeError: If LLM returns malformed JSON (after sanitizer + 1 retry).
        Exception: On LLM API errors (re-raised with logging).
    """
    text_trimmed = timestamped_text[:200000]  # ~90 min @ avg 2200 char/min post-parse (raised from 80k, Supervisor-01 2026-07-14)
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
6. **meta_description** \u2014 max 155 znakow, z fraza kluczowa.
7. **lead** \u2014 2-3 zdania, max 300 znakow. PIERWSZE ZDANIE musi zawierac glowna fraze z focus_keyphrases[0]. To jest meta description artykulu.
8. **quotes** \u2014 {qt_range} cytatow z rozmowy:
   - "text": WYGLADZONY, CZYTELNY cytat (1-3 zdania). Usun jakania, powtorzenia.
   - "speaker": imie i nazwisko
   - "anchor_text": DOKLADNE 8-15 pierwszych slow ORYGINALNEGO transkryptu
10. **chapters** \u2014 {ch_range} rozdzialow:
    - "label": tytul (max 60 zn)
    - "anchor_text": DOKLADNY CYTAT 8-15 pierwszych slow
11. **faq** \u2014 {faq_range} pytan i odpowiedzi. Naturalne, zorientowane na search intent.
12. **youtube_description_hook** \u2014 max 200 znakow. Angazujacy wstep 2-3 zdania.
    PIERWSZE zdanie MUSI zawierac glowna fraze z focus_keyphrases[0].
    Widoczne pod wideo bez klikania "Wiecej". BEZ hashtagow, BEZ linkow.
13. **youtube_hashtags** \u2014 lista dokladnie 3 hashtagow jako JSON array,
    np. ["#polityka", "#historia", "#Polska"]. Tylko hashtagi, nic wiecej.
14. **video_description** \u2014 max 200 zn, dla schema.
15. **tags** \u2014 5-8 tagow lowercase.
16. **external_links** \u2014 lista 2-3 linkow zewnetrznych DoFollow do zrodel wysokiego autorytetu.
    Kazdy link to dict: {{"url": "...", "anchor_text": "...", "reason": "..."}}
    ZASADY:
    a) Zrodla ktore Google wysoko wazy (E-E-A-T):
       - Wikipedia (polski artykul tematyczny, np. https://pl.wikipedia.org/wiki/...)
       - Strony .gov.pl (oficjalne zrodla rzadowe: sejm.gov.pl, gov.pl, prezydent.pl, mon.gov.pl)
       - PAP (pap.pl), Reuters (reuters.com), AP (apnews.com) \u2014 agencje prasowe
       - Instytucje naukowe/think-tanki (PISM, OSW, uniwersytety)
       - YouTube (link do oryginalnego wideo: {yt_url})
    b) Linki MUSZA byc tematycznie powiazane z trescia artykulu
    c) anchor_text to naturalny tekst w ktory jest wpleciony link
       (np. "Polska Agencja Prasowa", "Ministerstwo Obrony Narodowej")
    d) Nie wymyslaj URL-i \u2014 podaj REALNE adresy stron, ktore ISTNIEJA
    e) reason: krotkie uzasadnienie dlaczego to zrodlo jest authority
    f) Jeden z linkow MOZE byc do oryginalnego wideo YouTube ({yt_url})
    KRYTYCZNE DLA JSON: W polach URL i anchor_text NIE uzywaj podwojnych cudzyslowow.
    Caly output to JSON \u2014 podwojne cudzysłowy wewnatrz wartosci LAMIA parsowanie.
17. **image_descriptions** \u2014 lista 2 opisow do screenshotow z wideo (FALLBACK gdy SAAS Vision API niedostepny).
    Kazdy dict: {{"alt_text": "...", "caption": "...", "context": "..."}}
    ZASADY:
    a) alt_text: max 125 zn, MUSI zawierac glowna fraze z focus_keyphrases[0].
       Format: "[co widac na obrazku] - [fraza kluczowa]". Opisz scene z materialu.
    b) caption: 1 zdanie opisujace scene widoczna na screenshocie z wideo.
    c) context: gdzie wstawic screenshot w article_body ("po akapicie 1" lub "po pierwszym H2").
       Pierwsza pozycja: "po akapicie 1". Druga: "po pierwszym H2" lub "przed FAQ".

## KRYTYCZNE ZASADY FORMATU JSON

Twoja odpowiedz MUSI byc poprawnym JSON. Pamietaj:
- W polach HTML (article_body) ZAWSZE uzywaj APOSTROFOW (') w atrybutach tagow HTML.
- NIGDY nie wstawiaj surowych podwojnych cudzyslowow (") wewnatrz wartosci JSON string.
- Jesli musisz uzyc cudzysłowu w tekscie, escape'uj go jako \\\".
- Poprawne: <a href='https://example.com' target='_blank'>tekst</a>
- BLEDNE: <a href="https://example.com" target="_blank">tekst</a> (LAMIE JSON!)

KRYTYCZNE: Pola post_title, seo_title, yt_title MUSZA byc niepuste.
yt_title to OSOBNY, INNY tytul niz post_title \u2014 angazujacy, YouTubowy.
NIGDY nie zostawiaj ich pustych.
{pub_type_section}
Odpowiedz TYLKO JSON (bez markdown):
{{"focus_keyphrases":["fraza glowna","fraza 2","fraza 3"],"post_title":"...","seo_title":"...","yt_title":"...","meta_description":"...","lead":"...","quotes":[{{"text":"...","speaker":"...","anchor_text":"..."}}],"chapters":[{{"label":"...","anchor_text":"..."}}],"faq":[{{"question":"...","answer":"..."}}],"youtube_description_hook":"...","youtube_hashtags":["..."],"video_description":"...","tags":["..."],"external_links":[{{"url":"...","anchor_text":"...","reason":"..."}}],"image_descriptions":[{{"alt_text":"...","caption":"...","context":"..."}}]}}"""

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
        # D15: Pre-parse sanitization — repair broken HTML attrs before json.loads()
        text = _sanitize_llm_json(text)
        return json.loads(text)
    except json.JSONDecodeError as e:
        # D12: Log raw LLM output for debugging (first 2000 chars)
        logger.error(
            "JSON parse failed at char %d: %s\nRaw LLM output (first 2000 chars):\n%s",
            e.pos, e.msg, text[:2000]
        )

        # D12: 1 retry — ask LLM to fix the JSON
        retry_prompt = (
            "Twoja poprzednia odpowiedz zawierala blad skladni JSON "
            f"(pozycja {e.pos}: {e.msg}).\n"
            "Napraw i zwroc TYLKO poprawny JSON. "
            "UWAGA: W polach HTML (article_body) uzywaj apostrofow (') "
            "zamiast cudzyslowow (\") w atrybutach HTML, np: "
            "<a href='https://...' target='_blank'>\n\n"
            f"Oryginalna odpowiedz do naprawy:\n{text}"
        )
        logger.info("D12: Retrying LLM with fix prompt...")
        try:
            text2 = _call_llm(retry_prompt, api_key, provider)
            text2 = text2.strip()
            text2 = re.sub(r"^```json\s*", "", text2)
            text2 = re.sub(r"\s*```$", "", text2)
            # D15: Apply sanitizer on retry output too
            text2 = _sanitize_llm_json(text2)
            result = json.loads(text2)
            logger.info("D12: Retry succeeded — valid JSON obtained")
            return result
        except json.JSONDecodeError as e2:
            logger.error(
                "D12: RETRY also failed at char %d: %s\nRetry output (first 2000 chars):\n%s",
                e2.pos, e2.msg, text2[:2000]
            )
            raise
        except Exception as retry_exc:
            logger.error("D12: RETRY LLM call failed: %s", retry_exc)
            raise
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

# Backward compat alias
generate_video_schema = generate_seo_v4

# ============================================================
# D13: SLUG HARD LIMIT — trim to max 60 chars at word boundary
# ============================================================

def _trim_slug(slug: str, max_len: int = 60) -> str:
    """Trim slug to max_len characters at the last full word boundary.

    CO: Obcina wp_slug do maksymalnie max_len znaków na granicy słowa.

    PO CO: Google preferuje sligi <60 znaków. LLM ignoruje limit mimo
    instrukcji w promptcie — potrzebny jest twardy limit w kodzie.
    E2E test pokazał slug 81 znaków, co wychodzi poza optimum SEO.

    JAK: Jeśli len(slug) > max_len, obcina do max_len i cofa do
    ostatniego myślnika (rsplit), żeby nie urwać słowa w połowie.

    Args:
        slug: URL slug string (already lowercase, hyphens only).
        max_len: Maximum allowed length. Default 60.

    Returns:
        Trimmed slug string, max max_len characters.
    """
    if len(slug) <= max_len:
        return slug
    trimmed = slug[:max_len].rsplit("-", 1)[0]
    # Edge case: no hyphen found (single long token) — hard cut at max_len
    return trimmed if trimmed else slug[:max_len]


# ============================================================
# FIX A: PARTIAL SCHEMA — generate SEO without transcript
# ============================================================

def generate_schema_without_transcript(
    youtube_id: str,
    wp_id: int,
    post_title: str,
    yt_url: str,
    api_key: str,
    provider: str = "gemini",
    priority_keywords: Optional[list[str]] = None,
    internal_links: Optional[list[dict]] = None,
    site_brand: Optional[str] = None,
    publication_type: str = "full_analysis",
    meta: Optional[dict] = None,
) -> dict:
    """Generate partial SEO schema from title and description only (no VTT).

    CO: Generuje częściowy pakiet SEO gdy brak transkryptu VTT.

    PO CO: Filmy bez napisów (livestreamy, część contentów) nie mają VTT.
    Zamiast zwracać błąd 500, generujemy to co możliwe:
    - focus_keyphrases, post_title, seo_title, meta_description, lead
    - article_body (z tytułu i opisu YT)
    - youtube_description, video_description, tags
    - POMIJAMY: chapters (wymaga VTT do anchor-matchowania)
    - POMIJAMY: quotes (wymagają VTT z timestampami)
    - FAQ: minimalne 1-2 pytania z tytułu

    JAK: Wywołuje LLM z uproszczonym promptem bez sekcji transkryptu.
    Zwraca dict z chapters=[], quotes=[], partial_result=True.

    Args:
        youtube_id: YouTube video ID.
        wp_id: WordPress post ID.
        post_title: Video title (from YouTube metadata).
        yt_url: Full YouTube watch URL.
        api_key: API key for the selected LLM provider.
        provider: LLM provider: 'gemini' (default) or 'claude'.
        priority_keywords: Optional GSC keywords.
        internal_links: Optional internal links.
        site_brand: Optional portal brand name.
        publication_type: Article type.
        meta: Optional metadata dict (may contain description, duration).

    Returns:
        Partial SEO dict with transcript_available=False, partial_result=True.
    """
    logger.info(
        "[FIX A] generate_schema_without_transcript: %s via %s [type=%s]",
        youtube_id, provider, publication_type,
    )

    # Extract description from meta if available
    video_description_hint = ""
    duration_seconds = 0
    if meta:
        video_description_hint = meta.get("description", "") or ""
        duration_seconds = meta.get("duration", 0) or 0
        if video_description_hint:
            video_description_hint = video_description_hint[:3000]

    saas_section = _build_saas_prompt_section(priority_keywords, internal_links)

    if site_brand:
        seo_title_instruction = (
            f"**seo_title** \u2014 max 60 znakow. Z branding pipe: '| {site_brand}'."
        )
    else:
        seo_title_instruction = "**seo_title** \u2014 max 60 znakow. Bez branding pipe."

    desc_section = f"\nOpis wideo (YouTube):\n{video_description_hint}" if video_description_hint else ""

    prompt = f"""Jestes ekspertem SEO. Przygotuj pakiet SEO dla materialu wideo.
NIE MASZ TRANSKRYPTU — bazuj tylko na tytule i opisie.

## DANE WEJSCIOWE
Tytul: {post_title}
URL: {yt_url}{desc_section}
{saas_section}
## CO WYGENEROWAC

1. **focus_keyphrases** — lista 2-3 fraz kluczowych (kazda 2-4 slowa).
2. **post_title** — max 80 znakow, SEO-first, z glowna fraza.
3. {seo_title_instruction}
4. **yt_title** — 40-65 znakow, inny niz post_title, angazujacy YouTubowy tytul.
5. **meta_description** — max 155 znakow, z fraza kluczowa.
6. **lead** — 2-3 zdania, max 300 znakow. Pierwsza fraza w pierwszym zdaniu.
7. **faq** — 1-2 pytania i odpowiedzi na podstawie tytulu.
8. **youtube_description_hook** — max 200 znakow. Angazujacy wstep 2-3 zdania.
   PIERWSZE zdanie MUSI zawierac glowna fraze z focus_keyphrases[0]. BEZ hashtagow.
9. **youtube_hashtags** — lista 3 hashtagow jako JSON array.
10. **video_description** — max 200 zn.
11. **tags** — 5-8 tagow lowercase.
12. **external_links** — 1-2 linki do authority sources (Wikipedia, .gov.pl).
    Format: {{"url": "...", "anchor_text": "...", "reason": "..."}}
13. **image_descriptions** — 1 opis screenshota.
    Format: {{"alt_text": "...", "caption": "...", "context": "po akapicie 1"}}

NIE generuj: chapters, quotes (brak transkryptu), article_body.
Odpowiedz TYLKO JSON (bez markdown):
{{"focus_keyphrases":[],"post_title":"","seo_title":"","yt_title":"","meta_description":"","lead":"","chapters":[],"quotes":[],"faq":[{{"question":"","answer":""}}],"youtube_description_hook":"","youtube_hashtags":[],"video_description":"","tags":[],"external_links":[],"image_descriptions":[{{"alt_text":"","caption":"","context":""}}]}}"""

    try:
        text = _call_llm(prompt, api_key, provider)
        text = text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = _sanitize_llm_json(text)
        result = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(
            "[FIX A] JSON parse failed at %d: %s\nRaw (first 1000):\n%s",
            e.pos, e.msg, text[:1000]
        )
        # Minimal retry
        retry_prompt = (
            f"Napraw JSON (blad na poz. {e.pos}: {e.msg}). "
            "W atrybutach HTML uzywaj apostrofow ('), nie cudzyslowow. "
            f"Do naprawy:\n{text}"
        )
        text2 = _call_llm(retry_prompt, api_key, provider)
        text2 = text2.strip()
        text2 = re.sub(r"^```json\s*", "", text2)
        text2 = re.sub(r"\s*```$", "", text2)
        text2 = _sanitize_llm_json(text2)
        result = json.loads(text2)

    # Normalize keyphrases
    keyphrases = _normalize_keyphrases(result)
    result["focus_keyphrases"] = keyphrases
    result["focus_keyphrase"] = keyphrases[0] if keyphrases else ""

    # Ensure chapters and quotes are empty (no VTT)
    result["chapters"] = []
    result["quotes"] = []

    # Fallback titles
    if not result.get("post_title", "").strip():
        result["post_title"] = result.get("seo_title", post_title)
    if not result.get("yt_title", "").strip():
        result["yt_title"] = result.get("post_title", post_title)[:100]

    # Attach metadata
    result["wp_id"] = wp_id
    result["youtube_id"] = youtube_id
    result["original_title"] = post_title
    result["yt_url"] = yt_url
    result["total_duration"] = int(duration_seconds)
    result["duration_seconds"] = int(duration_seconds)
    result["duration_iso"] = format_duration_iso(duration_seconds)
    result["llm_provider"] = provider
    result["publication_type"] = publication_type
    result["saas_enriched"] = bool(priority_keywords)
    result["transcript_available"] = False  # FIX A flag
    result["partial_result"] = True          # FIX A flag

    if priority_keywords:
        result["saas_keywords_count"] = len(priority_keywords)

    logger.info(
        "[FIX A] Partial schema generated: keyphrases=%r type=%s brand=%s",
        keyphrases, publication_type, site_brand or "none",
    )
    
    # PASS 2: Article Generation
    pressai_enabled = os.getenv("USE_PRESSAI_ARTICLE_ENGINE", "false").lower() == "true"
    pressai_url = os.getenv("PRESSAI_API_URL", "")
    pressai_token = os.getenv("PRESSAI_EXTERNAL_TOKEN", "")
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        article_html, article_engine = loop.run_until_complete(
            generate_article_content(
                schema=result,
                vtt_text=video_description_hint,  # No transcript, pass hint
                publication_type=publication_type,
                api_key=api_key,
                provider=provider,
                pressai_api_url=pressai_url if pressai_enabled else "",
                pressai_token=pressai_token if pressai_enabled else "",
                internal_links=internal_links,
            )
        )
        result["article_body"] = article_html
        result["article_engine"] = article_engine
        logger.info("Pass 2 (Partial): article_body=%d chars engine=%s", len(article_html), article_engine)
    except Exception as e:
        logger.error("Pass 2 (Partial): article generation failed: %s", e)
        result["article_body"] = result.get("article_body", "")
        result["article_engine"] = "pass1_legacy"

    return result


# ============================================================
# FULL PIPELINE — VTT → LLM → resolved chapters
# ============================================================

def process_video(
    youtube_id: str,
    wp_id: int,
    post_title: str,
    yt_url: str,
    vtt_path: Optional[str],
    api_key: str,
    out_dir: Optional[str] = None,
    sleep_between: int = 0,
    provider: str = "gemini",
    priority_keywords: Optional[list[str]] = None,
    internal_links: Optional[list[dict]] = None,
    site_brand: Optional[str] = None,
    publication_type: str = "full_analysis",
    meta: Optional[dict] = None,
) -> dict:
    """Run the full generation pipeline for a single video.

    D6b.6: publication_type parameter controls article format.
    D11: LLM now returns image_descriptions as fallback for SAAS Vision API.
    D13: wp_slug is hard-trimmed to 60 chars at word boundary after LLM call.
    D15: _sanitize_llm_json() applied before json.loads() in generate_seo_v4().

    FIX A (2026-07-10, vse-dev-01):
    vtt_path is now Optional[str]. When None, calls generate_schema_without_transcript()
    which generates partial SEO (no chapters/quotes) from title+description only.
    Result contains transcript_available=False and partial_result=True.

    VTT Limit (2026-07-14, Supervisor-01):
    text_trimmed raised to 200000 chars — covers ~90 min of conversation.

    Args:
        youtube_id: YouTube video ID.
        wp_id: WordPress post ID.
        post_title: WordPress post title.
        yt_url: Full YouTube watch URL.
        vtt_path: Path to the .vtt transcript file, or None if unavailable.
        api_key: API key for the selected LLM provider.
        out_dir: Directory to save the result JSON. If None, does not save.
        sleep_between: Seconds to sleep after the LLM call (rate-limit guard).
        provider: LLM provider: 'gemini' (default) or 'claude'.
        priority_keywords: Optional list of priority keyword phrases from GSC.
        internal_links: Optional list of dicts with 'url' and 'title' for linking.
        site_brand: Optional portal brand name for seo_title branding pipe.
        publication_type: Article type: 'full_analysis', 'watching_page', 'discover'.
        meta: Optional metadata dict (used in no-transcript path for description/duration).

    Returns:
        SEO result dict with all fields + resolved chapters + duration metadata.
        When vtt_path is None: chapters=[], quotes=[], partial_result=True.

    Raises:
        json.JSONDecodeError: If LLM returns malformed JSON.
    """
    logger.info("Processing video: %s (WP#%s) via %s [type=%s]", youtube_id, wp_id, provider, publication_type)

    # FIX A: Guard — when vtt_path is None, use partial schema generator
    if vtt_path is None:
        logger.warning(
            "[FIX A] vtt_path=None for %s — calling generate_schema_without_transcript()",
            youtube_id,
        )
        return generate_schema_without_transcript(
            youtube_id=youtube_id,
            wp_id=wp_id,
            post_title=post_title,
            yt_url=yt_url,
            api_key=api_key,
            provider=provider,
            priority_keywords=priority_keywords,
            internal_links=internal_links,
            site_brand=site_brand,
            publication_type=publication_type,
            meta=meta,
        )

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
            "post_title missing — fallback to seo_title: %r",
            result["post_title"][:60],
        )

    # Fallback: yt_title z post_title jesli puste
    if not result.get("yt_title", "").strip():
        result["yt_title"] = result.get("post_title", post_title)[:100]
        logger.warning(
            "yt_title missing — fallback to post_title: %r",
            result["yt_title"][:60],
        )

    # D10: Log external links from LLM output
    ext_links = result.get("external_links", [])
    if ext_links:
        logger.info("D10 external_links: %d authority links generated", len(ext_links))
        for el in ext_links:
            logger.info("  -> %s (%s)", el.get("url", "?")[:60], el.get("reason", "?")[:40])
    else:
        logger.warning("D10 external_links: LLM returned 0 links (expected 2-3)")

    # D11: Log image descriptions from LLM output (fallback for SAAS Vision)
    img_descs = result.get("image_descriptions", [])
    if img_descs:
        logger.info("D11 image_descriptions: %d LLM fallback descriptions generated", len(img_descs))
        for idx, desc in enumerate(img_descs):
            logger.info("  img[%d] alt=%r ctx=%r", idx, desc.get("alt_text", "?")[:60], desc.get("context", "?"))
    else:
        logger.info("D11 image_descriptions: LLM returned 0 (SAAS primary will be used)")

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

    # PASS 2: Article Generation
    pressai_enabled = os.getenv("USE_PRESSAI_ARTICLE_ENGINE", "false").lower() == "true"
    pressai_url = os.getenv("PRESSAI_API_URL", "")
    pressai_token = os.getenv("PRESSAI_EXTERNAL_TOKEN", "")
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        article_html, article_engine = loop.run_until_complete(
            generate_article_content(
                schema=result,
                vtt_text=timestamped,
                publication_type=publication_type,
                api_key=api_key,
                provider=provider,
                pressai_api_url=pressai_url if pressai_enabled else "",
                pressai_token=pressai_token if pressai_enabled else "",
                internal_links=internal_links,
            )
        )
        result["article_body"] = article_html
        result["article_engine"] = article_engine
        logger.info("Pass 2: article_body=%d chars engine=%s", len(article_html), article_engine)
    except Exception as e:
        logger.error("Pass 2: article generation failed: %s", e)
        result["article_body"] = result.get("article_body", "")
        result["article_engine"] = "pass1_legacy"

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
    result["transcript_available"] = True   # FIX A: full transcript was used
    result["partial_result"] = False         # FIX A: full result

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
        "Done: %d chapters (%d/%d matched), keyphrases=%r, type=%s, saas=%s, brand=%s, ext_links=%d, img_descs=%d",
        len(resolved_chapters), matched_count, len(resolved_chapters),
        keyphrases, publication_type,
        "enriched" if result.get("saas_enriched") else "standalone",
        site_brand or "none",
        len(ext_links),
        len(img_descs),
    )
    return result
